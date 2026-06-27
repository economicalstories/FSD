#!/usr/bin/env python3
"""
fsd-analyse-entity : load downloaded Transparency Portal data, map it to the
dashboard's indicators, compute peer benchmarks, and inject the seed into index.html.

Reads what fsd-fetch-entity wrote under sources/<slug>/ and, for every entity:
  1. picks the most recent reporting period that has the full statement set;
  2. maps each financial-statement line item to the dashboard's ratio inputs
     (works for both non-corporate and corporate entities; flow figures are taken
     as magnitudes so the differing NCE/CCE sign conventions don't matter);
  3. builds multi-year trend series;
  4. records per-figure provenance (line item, statement, period, backlink).

It then computes, for each comparison group (entity type, and functional class),
the distribution of every ratio and where each entity sits within it — so the
dashboard can rank relative standing instead of pinning absolute "concern" labels
on whole classes of entity. Writes sources/seed.json + sources/benchmarks.json and
injects the seed into index.html.

No value is invented. Every figure is verbatim from an audited annual report.

Usage:
    python3 analyse.py                 # analyse every entity present under sources/
    python3 analyse.py "Department of the Treasury" [more ...]
"""
import json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SOURCES = os.path.join(ROOT, "sources")
INDEX = os.path.join(ROOT, "index.html")

# Logical statement -> the content-type codenames that carry it (NCE first, CCE second).
STATEMENTS = {
    "CI": ["extract_dept__statement_of_comp_income___nce_23_24",
           "extract_dept__statement_of_comp_income___cce_23_24"],
    "FP": ["extract_of_statement_of_financial_position_____cop",
           "extract_of_statement_of_financial_position___cce"],
    "CF": ["extract_of_cash_flow_statement___nce_23_24_",
           "extract_of_dept_cash_flow_statement_cce_23_24"],
    "CD": ["dept__current_distinction___assets_and_liab__nce_23_24",
           "dept__current_distinction___assets_and_liab__cce_23_24"],
}
STMT_LABEL = {
    "CI": "Statement of Comprehensive Income",
    "FP": "Statement of Financial Position",
    "CF": "Cash Flow Statement",
    "CD": "Assets & liabilities — current/non-current distinction",
}

BASE_YEAR = 2018
N_YEARS = 7

# Entities abolished / merged away with no continuing identity — evidence-based, not
# inferred from missing data. These are tagged "historical" and hidden from the default
# (currently-active) view, available via the dashboard's historical toggle.
CURATED_HISTORICAL = {
    "Australian National Preventive Health Agency (ANPHA)":
        "Abolished 30 June 2014; functions returned to the Department of Health "
        "(Australian National Preventive Health Agency (Abolition) Act 2014).",
}
# Active entities that publish no (or exempt) financial statements on the Transparency
# Portal — chiefly the intelligence/security community and on-base services. Absence of
# financial data must NOT be read as defunct for these.
ACTIVE_EXEMPT = {
    "Australian Secret Intelligence Service",
    "Office of National Intelligence",
    "Australian Crime Commission (Australian Criminal Intelligence Commission)",
    "Army and Air Force Canteen Service (Frontline Defence Services)",
}
# Reporting periods at or before this are treated as "no longer reporting" (superseded),
# unless the entity is in ACTIVE_EXEMPT.
STALE_CUTOFF = "2022-23"


# ---- ratio definitions mirror index.html; dir: high=higher healthier, low=lower healthier, band ----
RATIO_DIR = {"lta": "low", "fatl": "high", "cur": "high", "cto": "band", "liq": "high"}


def functionOf(name):
    """Functional class — must match functionOf() in index.html."""
    n = name.lower()
    if re.match(r"^department of|^attorney-general's department", n):
        return "Department of State"
    if "research and development corporation" in n or "rural industries" in n:
        return "Research & Development Corporation"
    if re.search(r"land council|land and sea|aboriginal|torres strait|indigenous|anindilyakwa|tiwi", n):
        return "Indigenous body"
    if re.search(r"museum|gallery|library|archives|memorial|portrait|film|broadcasting|screen|creative|arts|maritime museum", n):
        return "Cultural / collecting / media"
    if re.search(r"trust fund|canteen|relief|welfare|residences", n):
        return "Defence trust / canteen"
    if re.search(r"commission|authority|regulator|ombudsman|inspector|safety|standards|tribunal", n):
        return "Regulator / oversight"
    if re.search(r"research|institute|science|studies|meteorology|geoscience|nuclear|marine science", n):
        return "Research / scientific"
    if re.search(r"finance corporation|reinsurance|superannuation|future fund|financial management|housing australia|reserve bank|export finance", n):
        return "Financial corporation / fund"
    return "Other agency"


def register():
    """name -> {type, function} from the dashboard's entity register."""
    html = open(INDEX, encoding="utf-8").read()
    m = re.search(r'<script id="entity-data" type="application/json">(.*?)</script>', html, re.S)
    out = {}
    for e in json.loads(m.group(1)):
        out[e["name"]] = {"type": e["type"], "function": functionOf(e["name"])}
    return out


def norm_df(df):
    """Normalise a datafields dict: strip whitespace from item & column in every key."""
    out = {}
    for k, v in df.items():
        if "|" not in k:
            continue
        item, col = k.split("|", 1)
        out[(item.strip().lower(), col.strip().lower())] = v
    return out


def num(ndf, items, col="current year", absolute=False):
    """First matching line item -> float ($'000), or None. `items` may be a list of
    candidate names; `absolute` returns the magnitude (NCE/CCE sign conventions differ)."""
    if isinstance(items, str):
        items = [items]
    for it in items:
        v = ndf.get((it.strip().lower(), col))
        if v is None or str(v).strip() == "":
            continue
        try:
            f = float(str(v).replace(",", ""))
            return abs(f) if absolute else f
        except ValueError:
            continue
    return None


def period_index(period):
    try:
        return next(i for i in [int(period.split("-")[0]) - BASE_YEAR] if 0 <= i < N_YEARS)
    except (ValueError, AttributeError, StopIteration):
        return None


def prev_period(period):
    try:
        a, b = period.split("-")
        return f"{int(a) - 1}-{str(int(b) - 1).zfill(2)}"
    except Exception:
        return None


def statement_maps(records):
    """logical statement -> {period: normalised datafields}."""
    maps = {key: {} for key in STATEMENTS}
    for key, codenames in STATEMENTS.items():
        for r in records:
            if r.get("contentType") in codenames:
                df = r.get("datafields")
                df = df if isinstance(df, dict) else (df[0] if df else {})
                maps[key][r.get("reportingPeriod")] = norm_df(df)
    return maps


def backlink(manifest, period):
    for p in manifest.get("periods", []):
        if p["reportingPeriod"] == period:
            url = p["annualReportUrl"]
            anchor = p.get("financialStatementsAnchor") or ""
            return (url + ("#" + anchor if anchor else ""), p.get("annualReportTitle") or "",
                    p.get("sourceEntityName") or manifest.get("registerName"))
    return (None, "", manifest.get("registerName"))


# candidate line-item names per field (handles NCE/CCE wording differences)
CASH = "cash at the end of reporting period"
OPCASH = ["total cash used for operating act.", "total cash used operating act."]
FINCASH = ["total cash used financing act."]
NETINV = ["net cash from investing act."]


def analyse_entity(manifest, records):
    maps = statement_maps(records)
    ci, fp, cf, cd = maps["CI"], maps["FP"], maps["CF"], maps["CD"]

    complete = sorted(set(ci) & set(fp) & set(cf) & set(cd), reverse=True)
    if not complete:
        return None, "no period has the full statement set"
    period = complete[0]
    link, title, src_name = backlink(manifest, period)
    dci, dfp, dcf, dcd = ci[period], fp[period], cf[period], cd[period]

    assets = num(dfp, "assets - total assets")
    liab   = num(dfp, "liabilities - total liabilities")
    finass = num(dfp, "assets - total financial assets")
    nfass  = num(dfp, "assets - total non-financial assets")
    cash   = num(dcf, CASH, absolute=True)
    opcash = num(dcf, OPCASH, absolute=True)
    fincash = num(dcf, FINCASH, absolute=True)
    netinv = num(dcf, NETINV, absolute=True)        # magnitude of net investing flow
    netpur = netinv
    ca = num(dcd, "assets - no more than 12 months")
    cl = num(dcd, "liabilities - no more than 12 months")

    def fnum(x):
        return None if x is None else (str(int(x)) if float(x).is_integer() else str(x))

    ratios, prov = {}, {}

    def put(rid, mapping):
        seeded = {k: fnum(v) for k, (v, _i, _s) in mapping.items()}
        if all(v is not None for v in seeded.values()):
            ratios[rid] = seeded
            prov[rid] = {k: {"item": item, "statement": STMT_LABEL[stmt], "period": period}
                         for k, (v, item, stmt) in mapping.items()}

    put("lta",  {"liab": (liab, "Total liabilities", "FP"), "assets": (assets, "Total assets", "FP")})
    put("fatl", {"finassets": (finass, "Total financial assets", "FP"), "liab": (liab, "Total liabilities", "FP")})
    put("cur",  {"ca": (ca, "Assets — no more than 12 months", "CD"), "cl": (cl, "Liabilities — no more than 12 months", "CD")})
    put("cto",  {"netpur": (netpur, "Net cash used in investing (net non-financial asset acquisition)", "CF"),
                 "nfassets": (nfass, "Total non-financial assets", "FP")})
    put("liq",  {"cash": (cash, "Cash at end of reporting period", "CF"),
                 "opcash": (opcash, "Cash used in operating activities", "CF"),
                 "fincash": (fincash, "Cash used in financing activities", "CF"),
                 "netpur": (netpur, "Net cash used in investing", "CF")})

    def series(by, item, transform=None):
        arr = [None] * N_YEARS
        for per, df in by.items():
            for col, p in (("current year", per), ("previous year", prev_period(per))):
                i = period_index(p)
                if i is None or arr[i] is not None:
                    continue
                v = num(df, item, col)
                if v is None:
                    continue
                v = transform(v, df, col) if transform else v
                if v is not None:
                    arr[i] = round(v, 2)
        return arr

    def emp_ratio(v, df, col):
        rev = num(df, "revenue from government", col) or 0
        own = num(df, "total own-source revenue", col) or 0
        denom = rev + own
        return (v / denom * 100) if denom else None

    trends = {
        "oppresult": series(ci, "surplus/(deficit) after income tax"),
        "empexp":    series(ci, "employee benefits expense", emp_ratio),
        "cashtrend": series(cf, CASH),
    }
    trends = {k: v for k, v in trends.items() if sum(x is not None for x in v) >= 2}

    seed = {
        "registerName": manifest["registerName"],
        "period": period,
        "sourceEntityName": src_name,
        "renamed": manifest.get("renamed", False),
        "annualReportUrl": link,
        "annualReportTitle": title,
        "ratios": ratios,
        "ratioProvenance": prov,
        "trends": trends,
    }
    return seed, f"period {period}, {len(ratios)} ratios, {len(trends)} trends"


# ----------------------------- benchmarking -----------------------------
def ratio_value(rid, inputs):
    v = {k: float(x) for k, x in inputs.items()}
    try:
        if rid == "lta":  return v["liab"] / v["assets"] if v["assets"] else None
        if rid == "fatl": return v["finassets"] / v["liab"] if v["liab"] else None
        if rid == "cur":  return v["ca"] / v["cl"] if v["cl"] else None
        if rid == "cto":  return v["netpur"] / v["nfassets"] if v["nfassets"] else None
        if rid == "liq":
            d = v["opcash"] + v["fincash"] + v["netpur"]
            return v["cash"] / d if d else None
    except (KeyError, ZeroDivisionError):
        return None
    return None


def quantile(sorted_vals, q):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    frac = pos - lo
    if lo + 1 < len(sorted_vals):
        return sorted_vals[lo] + frac * (sorted_vals[lo + 1] - sorted_vals[lo])
    return sorted_vals[lo]


def benchmarks(seed_map, reg):
    """For each grouping basis and group, the distribution of every ratio and each
    entity's relative standing (percentile + concern rank, 1 = furthest toward the
    less-healthy tail vs peers). Documents the relative ranking the dashboard shows."""
    # entity -> {rid: value}
    vals = {}
    for name, s in seed_map.items():
        vals[name] = {rid: ratio_value(rid, inp) for rid, inp in s["ratios"].items()}
        vals[name] = {k: v for k, v in vals[name].items() if v is not None}

    def group_key(name, basis):
        info = reg.get(name, {})
        return info.get("type") if basis == "type" else info.get("function")

    report = {}
    for basis in ("type", "function"):
        groups = {}
        for name in seed_map:
            groups.setdefault(group_key(name, basis), []).append(name)
        report[basis] = {}
        for g, members in groups.items():
            if not g:
                continue
            rd = {}
            for rid, direction in RATIO_DIR.items():
                series = sorted(vals[m][rid] for m in members if rid in vals[m])
                if len(series) < 2:
                    continue
                med = quantile(series, 0.5)
                dist = {"n": len(series), "min": round(series[0], 4), "q1": round(quantile(series, .25), 4),
                        "median": round(med, 4), "q3": round(quantile(series, .75), 4),
                        "max": round(series[-1], 4), "mean": round(sum(series) / len(series), 4)}
                # concern score: more concerning = larger score
                def concern(v):
                    if direction == "high": return -v
                    if direction == "low":  return v
                    return abs(v - med)            # band: outlier-ness from peer median
                ranked = sorted((m for m in members if rid in vals[m]),
                                key=lambda m: concern(vals[m][rid]), reverse=True)
                ent = {}
                for rank, m in enumerate(ranked, 1):
                    v = vals[m][rid]
                    below = sum(1 for x in series if x < v)
                    pct = below / (len(series) - 1) if len(series) > 1 else 0.0
                    ent[m] = {"value": round(v, 4), "concernRank": rank, "percentile": round(pct, 3)}
                rd[rid] = {"direction": direction, "distribution": dist, "entities": ent}
            report[basis][g] = rd
    return report


def start_year(period):
    try:
        return int(str(period)[:4])
    except (ValueError, TypeError):
        return None


def compute_status(reg_names, manifests):
    """Per register entity: active vs historical (defunct/superseded), with a reason.
    Defunct is evidence-based (curated) or inferred only from a clearly stale last
    report — never from mere absence of data (intelligence/exempt bodies stay active)."""
    out = {}
    for name in reg_names:
        m = manifests.get(name)
        pers = [p["reportingPeriod"] for p in (m or {}).get("periods", [])]
        latest = max(pers) if pers else None
        sy = start_year(latest)
        if name in CURATED_HISTORICAL:
            out[name] = {"status": "historical", "reason": CURATED_HISTORICAL[name], "latestPeriod": latest}
        elif sy is not None and sy < 2023 and name not in ACTIVE_EXEMPT:
            out[name] = {"status": "historical",
                         "reason": f"No annual report since {latest} — likely superseded by a machinery-of-government change.",
                         "latestPeriod": latest}
        else:
            reason = ("Active — financial statements not published on the Transparency Portal (exempt)."
                      if (name in ACTIVE_EXEMPT or not latest) else "Active — currently reporting.")
            out[name] = {"status": "active", "reason": reason, "latestPeriod": latest}
    return out


def inject_block(marker_id, start, end, payload):
    block = (f'<script id="{marker_id}" type="application/json">'
             + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "</script>")
    wrapped = f"{start}\n{block}\n{end}"
    with open(INDEX) as f:
        html = f.read()
    if start in html:
        html = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda m: wrapped, html, flags=re.S)
    else:
        anchor = '<script id="entity-data"'
        html = html.replace(anchor, wrapped + "\n" + anchor, 1)
    with open(INDEX, "w") as f:
        f.write(html)


def main(argv):
    if not os.path.isdir(SOURCES):
        print("No sources/ directory — run fsd-fetch-entity first.", file=sys.stderr)
        return 1
    reg = register()
    want = set(argv) if argv else None
    seed_map, manifests = {}, {}
    for d in sorted(os.listdir(SOURCES)):
        mpath = os.path.join(SOURCES, d, "manifest.json")
        if not os.path.isfile(mpath):
            continue
        manifest = json.load(open(mpath))
        name = manifest["registerName"]
        manifests[name] = manifest
        if want and name not in want:
            continue
        records = json.load(open(os.path.join(SOURCES, d, "transparency_raw.json")))
        seed, msg = analyse_entity(manifest, records)
        if seed:
            seed_map[name] = seed
            print(f"[ok]   {name}: {msg}")
        else:
            print(f"[skip] {name}: {msg}")

    # Active vs historical (defunct) status for EVERY register entity.
    status = compute_status(list(reg.keys()), manifests)
    hist = [n for n, s in status.items() if s["status"] == "historical"]

    with open(os.path.join(SOURCES, "seed.json"), "w") as f:
        json.dump(seed_map, f, indent=2, ensure_ascii=False)
    report = benchmarks(seed_map, reg)
    with open(os.path.join(SOURCES, "benchmarks.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(os.path.join(SOURCES, "status.json"), "w") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)

    inject_block("seed-data", "<!--SEED-START-->", "<!--SEED-END-->", seed_map)
    inject_block("status-data", "<!--STATUS-START-->", "<!--STATUS-END-->", status)
    print(f"\nInjected seed for {len(seed_map)} entities + status for {len(status)} into index.html")
    print(f"Historical (defunct/superseded): {len(hist)} — {', '.join(hist) or 'none'}")
    print(f"Wrote benchmarks for {sum(len(v) for v in report.values())} groups across "
          f"{len(report)} comparison bases")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
fsd-analyse-entity : load downloaded Transparency Portal data, map it to the
dashboard's indicators, compute the seed, and inject it into index.html.

Reads what fsd-fetch-entity wrote under sources/<slug>/ and:
  1. picks, per entity, the most recent reporting period that has the full set of
     departmental financial statements needed to compute the ratios;
  2. maps each financial-statement line item to the dashboard's ratio inputs;
  3. builds multi-year trend series (operating result, employee expense ratio,
     cash reserves) using both the current- and previous-year columns;
  4. records per-figure provenance (line item, statement, period, backlink);
  5. writes the consolidated seed to sources/seed.json and injects it into
     index.html between the SEED markers.

No value is invented. Every figure is a verbatim public figure from an audited
annual report financial statement, carried with a click-through to its source.

Usage:
    python3 analyse.py                 # analyse every entity present under sources/
    python3 analyse.py "Department of the Treasury" [more ...]
"""
import json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SOURCES = os.path.join(ROOT, "sources")
INDEX = os.path.join(ROOT, "index.html")

CI = "extract_dept__statement_of_comp_income___nce_23_24"   # Statement of Comprehensive Income
FP = "extract_of_statement_of_financial_position_____cop"    # Statement of Financial Position
CF = "extract_of_cash_flow_statement___nce_23_24_"           # Cash Flow Statement
CD = "dept__current_distinction___assets_and_liab__nce_23_24"  # current/non-current distinction

STMT_LABEL = {
    CI: "Statement of Comprehensive Income (departmental)",
    FP: "Statement of Financial Position (departmental)",
    CF: "Cash Flow Statement (departmental)",
    CD: "Departmental assets & liabilities — current/non-current distinction",
}

# Trend frame shown in the dashboard: 7 financial years, baseYear 2018 => 2018-19 .. 2024-25.
BASE_YEAR = 2018
N_YEARS = 7


def num(df, item, col="current year"):
    """Return a financial-statement value ($'000) as float, or None if blank/missing."""
    v = df.get(f"{item}|{col}")
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def period_index(period):
    """'2023-24' -> index into the trend frame (2018-19 == 0)."""
    try:
        start = int(period.split("-")[0])
    except (ValueError, AttributeError):
        return None
    i = start - BASE_YEAR
    return i if 0 <= i < N_YEARS else None


def prev_period(period):
    try:
        a, b = period.split("-")
        return f"{int(a) - 1}-{str(int(b) - 1).zfill(2)}"
    except Exception:
        return None


def records_by(records, content_type):
    """period -> datafields dict, for one content type."""
    out = {}
    for r in records:
        if r.get("contentType") == content_type:
            df = r.get("datafields")
            df = df if isinstance(df, dict) else (df[0] if df else {})
            out[r.get("reportingPeriod")] = df
    return out


def backlink(manifest, period):
    for p in manifest.get("periods", []):
        if p["reportingPeriod"] == period:
            url = p["annualReportUrl"]
            anchor = p.get("financialStatementsAnchor") or ""
            return (url + ("#" + anchor if anchor else ""), p.get("annualReportTitle") or "",
                    p.get("sourceEntityName") or manifest.get("registerName"))
    return (None, "", manifest.get("registerName"))


def analyse_entity(slug, manifest, records):
    ci, fp, cf, cd = (records_by(records, t) for t in (CI, FP, CF, CD))

    # Latest period with every statement needed to compute the full ratio set.
    complete = sorted(set(ci) & set(fp) & set(cf) & set(cd), reverse=True)
    if not complete:
        return None, "no period has the full statement set"
    period = complete[0]
    link, title, src_name = backlink(manifest, period)

    dci, dfp, dcf, dcd = ci[period], fp[period], cf[period], cd[period]

    # --- raw line items (verbatim, $'000) ---
    assets   = num(dfp, "assets - total assets")
    liab     = num(dfp, "liabilities - total liabilities")
    finass   = num(dfp, "assets - total financial assets")
    nfass    = num(dfp, "assets - total non-financial assets")
    cash     = num(dcf, "cash at the end of reporting period")
    opcash   = num(dcf, "total cash used for operating act.")
    fincash  = num(dcf, "total cash used financing act.")
    net_inv  = num(dcf, "net cash from investing act.")          # net non-financial asset acquisition (outflow)
    netpur   = abs(net_inv) if net_inv is not None else None
    ca       = num(dcd, "assets - no more than 12 months")
    cl       = num(dcd, "liabilities - no more than 12 months")

    def fnum(x):
        return None if x is None else (str(int(x)) if float(x).is_integer() else str(x))

    # --- ratio input seeds (only fully-mapped ratios) + per-input provenance ---
    ratios, prov = {}, {}

    def put(rid, mapping):
        seeded = {k: fnum(v) for k, (v, _item, _stmt) in mapping.items()}
        if all(v is not None for v in seeded.values()):
            ratios[rid] = seeded
            prov[rid] = {k: {"item": item, "statement": STMT_LABEL[stmt], "period": period}
                         for k, (v, item, stmt) in mapping.items()}

    put("lta",  {"liab": (liab, "liabilities - total liabilities", FP),
                 "assets": (assets, "assets - total assets", FP)})
    put("fatl", {"finassets": (finass, "assets - total financial assets", FP),
                 "liab": (liab, "liabilities - total liabilities", FP)})
    put("cur",  {"ca": (ca, "assets - no more than 12 months", CD),
                 "cl": (cl, "liabilities - no more than 12 months", CD)})
    put("cto",  {"netpur": (netpur, "net cash from investing act. (net non-financial asset acquisition)", CF),
                 "nfassets": (nfass, "assets - total non-financial assets", FP)})
    put("liq",  {"cash": (cash, "cash at the end of reporting period", CF),
                 "opcash": (opcash, "total cash used for operating act.", CF),
                 "fincash": (fincash, "total cash used financing act.", CF),
                 "netpur": (netpur, "net cash from investing act. (net non-financial asset acquisition)", CF)})

    # --- multi-year trends (current + previous columns densify the series) ---
    def series(by, item, transform=None):
        arr = [None] * N_YEARS
        for per, df in by.items():
            for col, p in (("current year", per), ("previous year", prev_period(per))):
                i = period_index(p)
                if i is None:
                    continue
                v = num(df, item, col)
                if v is None:
                    continue
                v = transform(v, df, col) if transform else v
                if v is not None and arr[i] is None:
                    arr[i] = round(v, 2)
        return arr

    def emp_ratio(v, df, col):
        rev = num(df, "revenue from government", col)
        own = num(df, "total own-source revenue", col)
        denom = (rev or 0) + (own or 0)
        return (v / denom * 100) if denom else None

    trends = {
        "oppresult": series(ci, "surplus/(deficit) after income tax"),
        "empexp":    series(ci, "employee benefits expense", emp_ratio),
        "cashtrend": series(cf, "cash at the end of reporting period"),
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


def inject(seed_map):
    block = ('<script id="seed-data" type="application/json">'
             + json.dumps(seed_map, ensure_ascii=False, separators=(",", ":"))
             + "</script>")
    wrapped = "<!--SEED-START-->\n" + block + "\n<!--SEED-END-->"
    with open(INDEX) as f:
        html = f.read()
    if "<!--SEED-START-->" in html:
        html = re.sub(r"<!--SEED-START-->.*?<!--SEED-END-->", lambda m: wrapped, html, flags=re.S)
    else:
        # Insert immediately before the entity-data script block.
        marker = '<script id="entity-data"'
        html = html.replace(marker, wrapped + "\n" + marker, 1)
    with open(INDEX, "w") as f:
        f.write(html)


def main(argv):
    if not os.path.isdir(SOURCES):
        print("No sources/ directory — run fsd-fetch-entity first.", file=sys.stderr)
        return 1
    slugs = []
    if argv:
        # accept entity names; resolve to slugs via each manifest
        want = set(argv)
        for d in sorted(os.listdir(SOURCES)):
            mpath = os.path.join(SOURCES, d, "manifest.json")
            if os.path.isfile(mpath):
                m = json.load(open(mpath))
                if m.get("registerName") in want:
                    slugs.append(d)
    else:
        slugs = [d for d in sorted(os.listdir(SOURCES))
                 if os.path.isfile(os.path.join(SOURCES, d, "manifest.json"))]

    seed_map = {}
    for d in slugs:
        base = os.path.join(SOURCES, d)
        manifest = json.load(open(os.path.join(base, "manifest.json")))
        records = json.load(open(os.path.join(base, "transparency_raw.json")))
        seed, msg = analyse_entity(d, manifest, records)
        name = manifest["registerName"]
        if seed:
            seed_map[name] = seed
            print(f"[ok]   {name}: {msg}")
        else:
            print(f"[skip] {name}: {msg}")

    with open(os.path.join(SOURCES, "seed.json"), "w") as f:
        json.dump(seed_map, f, indent=2, ensure_ascii=False)
    inject(seed_map)
    print(f"\nInjected seed for {len(seed_map)} entities into index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

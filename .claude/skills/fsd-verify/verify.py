#!/usr/bin/env python3
"""
fsd-verify : independently fact-check the dashboard's seeded data.

For a sample of entities this:
  1. re-fetches their financial statements from the Transparency Portal API on a
     SEPARATE code path (so a bug in fsd-analyse-entity can't hide itself),
  2. re-derives the ratio inputs and compares them to what is stored in
     sources/seed.json (and embedded in index.html),
  3. confirms each sampled entity's source backlink resolves (HTTP 200), and
  4. sanity-checks headline findings (e.g. entities whose liabilities exceed assets).

Exit code is non-zero if any figure mismatches or any backlink is broken.

Usage:
    python3 verify.py                         # curated diverse sample
    python3 verify.py --sample 12             # first N entities from seed.json
    python3 verify.py "Department of the Treasury" "Wine Australia"   # specific entities
"""
import json, os, re, sys, urllib.request, urllib.error

API = "https://data.transparency.gov.au/api/datasets/simplified"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SEED = os.path.join(ROOT, "sources", "seed.json")

FP = ["extract_of_statement_of_financial_position_____cop", "extract_of_statement_of_financial_position___cce"]
CF = ["extract_of_cash_flow_statement___nce_23_24_", "extract_of_dept_cash_flow_statement_cce_23_24"]
CD = ["dept__current_distinction___assets_and_liab__nce_23_24", "dept__current_distinction___assets_and_liab__cce_23_24"]

# A deliberately diverse default sample: large/small, NCE/CCE, and a negative-net-assets case.
DEFAULT_SAMPLE = [
    "Department of the Treasury", "Australian Broadcasting Corporation",
    "Department of Social Services", "Department of Defence",
    "Wine Australia", "Australian Electoral Commission",
]


def post(body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def norm_df(df):
    out = {}
    for k, v in df.items():
        if "|" in k:
            item, col = k.split("|", 1)
            out[(item.strip().lower(), col.strip().lower())] = v
    return out


def num(ndf, items, absolute=False):
    for it in (items if isinstance(items, list) else [items]):
        v = ndf.get((it.strip().lower(), "current year"))
        if v not in (None, ""):
            try:
                f = float(str(v).replace(",", ""))
                return abs(f) if absolute else f
            except ValueError:
                pass
    return None


def fresh_inputs(source_name, period):
    """Independently re-derive the five ratios' inputs for one entity/period.
    `source_name` is the exact name the figures were reported under (seed's
    sourceEntityName), which differs from the register name for aliased entities."""
    resp = post({"contentType": FP + CF + CD, "entity": [source_name], "entityCodename": [],
                 "reportingPeriod": [], "portfolio": [], "filter": "*"})
    by = {}
    for r in resp.get("entityData", []):
        ct, per = r.get("contentType"), r.get("reportingPeriod")
        if per != period:
            continue
        df = r.get("datafields"); df = df if isinstance(df, dict) else (df[0] if df else {})
        grp = "FP" if ct in FP else "CF" if ct in CF else "CD" if ct in CD else None
        if grp:
            by[grp] = norm_df(df)
    if not all(g in by for g in ("FP", "CF", "CD")):
        return None
    fp, cf, cd = by["FP"], by["CF"], by["CD"]
    netpur = num(cf, ["net cash from investing act."], absolute=True)
    return {
        "lta":  {"liab": num(fp, "liabilities - total liabilities"), "assets": num(fp, "assets - total assets")},
        "fatl": {"finassets": num(fp, "assets - total financial assets"), "liab": num(fp, "liabilities - total liabilities")},
        "cur":  {"ca": num(cd, "assets - no more than 12 months"), "cl": num(cd, "liabilities - no more than 12 months")},
        "cto":  {"netpur": netpur, "nfassets": num(fp, "assets - total non-financial assets")},
        "liq":  {"cash": num(cf, ["cash at the end of reporting period"], absolute=True),
                 "opcash": num(cf, ["total cash used for operating act.", "total cash used operating act."], absolute=True),
                 "fincash": num(cf, ["total cash used financing act."], absolute=True), "netpur": netpur},
    }


def backlink_ok(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.getcode() == 200
    except Exception:
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=40) as r:
                return r.getcode() == 200
        except Exception:
            return False


def main(argv):
    seed = json.load(open(SEED))
    if argv and argv[0] == "--sample":
        names = list(seed.keys())[:int(argv[1])]
    elif argv:
        names = argv
    else:
        names = [n for n in DEFAULT_SAMPLE if n in seed]

    mismatches, broken, checked = 0, 0, 0
    print(f"Verifying {len(names)} entities against the live Transparency Portal API…\n")
    for name in names:
        s = seed.get(name)
        if not s:
            print(f"[skip] {name}: not in seed.json"); continue
        checked += 1
        period = s["period"]
        source_name = s.get("sourceEntityName") or name
        fresh = fresh_inputs(source_name, period)
        if fresh is None:
            print(f"[WARN] {name}: could not re-fetch full {period} statement set"); mismatches += 1; continue
        diffs = []
        for rid, inputs in s["ratios"].items():
            for k, seeded in inputs.items():
                live = fresh.get(rid, {}).get(k)
                if live is None or abs(float(seeded) - live) > 0.5:
                    diffs.append(f"{rid}.{k}: seed={seeded} live={live}")
        link = backlink_ok(s["annualReportUrl"])
        if not link:
            broken += 1
        status = "OK" if (not diffs and link) else "FAIL"
        if status == "FAIL":
            mismatches += 1 if diffs else 0
        print(f"[{status}] {name} ({period}) — figures {'match' if not diffs else 'MISMATCH'}, backlink {'200' if link else 'BROKEN'}")
        for d in diffs:
            print(f"        ✗ {d}")

    # headline sanity: liabilities > assets
    neg = []
    for name, s in seed.items():
        r = s["ratios"].get("lta")
        if r and float(r["assets"]) and float(r["liab"]) / float(r["assets"]) > 1:
            neg.append((name, round(float(r["liab"]) / float(r["assets"]), 3)))
    print(f"\nHeadline check — {len(neg)} entities with liabilities exceeding assets (L/A > 1):")
    for name, la in sorted(neg, key=lambda x: -x[1]):
        print(f"        {la}  {name}")

    print(f"\n{'PASS' if mismatches == 0 and broken == 0 else 'FAIL'}: "
          f"{checked} checked · {mismatches} with figure mismatches · {broken} broken backlinks")
    return 1 if (mismatches or broken) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

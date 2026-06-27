#!/usr/bin/env python3
"""
fsd-fetch-entity : search & download public financial data for a Commonwealth entity.

Source: Australian Government Transparency Portal data API (data.transparency.gov.au),
the same machine-readable backend that powers https://www.transparency.gov.au/.
Each entity's annual report financial-statement *extracts* are published there as
structured datasets (Statement of Comprehensive Income, Statement of Financial
Position, Cash Flow Statement, current/non-current distinction, etc.).

Everything written under sources/ is verbatim public data plus the backlinks needed
to click through to the original annual report on the Transparency Portal.

Usage:
    python3 fetch.py "Department of the Treasury" ["Another Entity" ...]
    python3 fetch.py --departments      # all 19 Departments of State (incl. parliamentary)

Output (per entity):
    sources/<slug>/transparency_raw.json   raw API records (verbatim)
    sources/<slug>/manifest.json           provenance: periods, content types, backlinks
"""
import json, os, re, sys, time, urllib.request, urllib.error

API = "https://data.transparency.gov.au/api/datasets/simplified"
PORTAL = "https://www.transparency.gov.au/publications"

# Departmental financial-statement extract datasets published per non-corporate
# Commonwealth entity (departments are NCEs). Codenames are the Transparency
# Portal's own dataset content-type identifiers.
CONTENT_TYPES = [
    "extract_dept__statement_of_comp_income___nce_23_24",      # Statement of Comprehensive Income (departmental)
    "extract_of_statement_of_financial_position_____cop",       # Statement of Financial Position (multi-year)
    "extract_of_cash_flow_statement___nce_23_24_",             # Cash Flow Statement (departmental)
    "dept__current_distinction___assets_and_liab__nce_23_24",  # Current / non-current assets & liabilities
    "extract_of_admin__statement_of_comp__income_nce_23_24",   # Statement of Comprehensive Income (administered)
    "extract_admin__of_assets_and_liabilities_nce_23_24",      # Administered assets & liabilities
]

# Some departments publish recent years under a renamed entity (machinery-of-government
# changes) or carry a Transparency Portal footnote marker like "[i]". Map each register
# name to every API entity-name variant that is its recognised continuation, newest first.
# The exact source entity name is preserved on every record, so renames stay visible.
ALIASES = {
    "Department of Education": [
        "Department of Education [i]",
        "Department of Education",
    ],
    "Department of Infrastructure, Transport, Regional Development, Communications and the Arts": [
        "Department of Infrastructure, Transport, Regional Development, Communications, Sport and the Arts",
        "Department of Infrastructure, Transport, Regional Development, Communications and the Arts",
    ],
}

# The 19 Departments of State (incl. the three Parliamentary departments), exactly
# as named in the entity register the dashboard ships with.
DEPARTMENTS = [
    "Department of Agriculture, Fisheries and Forestry",
    "Attorney-General's Department",
    "Department of Climate Change, Energy, the Environment and Water",
    "Department of Defence",
    "Department of Education",
    "Department of Employment and Workplace Relations",
    "Department of Finance",
    "Department of Foreign Affairs and Trade",
    "Department of Health and Aged Care",
    "Department of Home Affairs",
    "Department of Industry, Science and Resources",
    "Department of Infrastructure, Transport, Regional Development, Communications and the Arts",
    "Department of the Prime Minister and Cabinet",
    "Department of Social Services",
    "Department of the Treasury",
    "Department of Veterans' Affairs",
    "Department of Parliamentary Services",
    "Department of the House of Representatives",
    "Department of the Senate",
]

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SOURCES = os.path.join(ROOT, "sources")


def slug(name):
    s = name.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def post(body, retries=4):
    data = json.dumps(body).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(API, data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"API request failed after {retries} attempts: {last}")


def fetch_entity(name):
    query_names = ALIASES.get(name, [name])
    body = {
        "contentType": CONTENT_TYPES,
        "entity": query_names,
        "entityCodename": [],
        "reportingPeriod": [],
        "portfolio": [],
        "filter": "*",
    }
    resp = post(body)
    records = resp.get("entityData", [])
    out_dir = os.path.join(SOURCES, slug(name))
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "transparency_raw.json"), "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # Build provenance manifest: one backlink per (period -> annual report).
    periods = {}
    for r in records:
        p = r.get("reportingPeriod")
        ar = r.get("annualReportUrl") or ""
        if p and ar and p not in periods:
            periods[p] = {
                "reportingPeriod": p,
                "sourceEntityName": r.get("entity"),
                "annualReportTitle": r.get("annualReportTitle") or "",
                "annualReportUrl": (PORTAL + ar) if ar.startswith("/") else ar,
                "financialStatementsAnchor": r.get("datasetUrl") or "",
            }
    source_names = sorted({r.get("entity") for r in records})
    manifest = {
        "registerName": name,
        "sourceEntityNames": source_names,
        "renamed": source_names != [name],
        "entityCodeName": next((r.get("entityCodeName") for r in records if r.get("entityCodeName")), None),
        "portfolio": next((r.get("portfolio") for r in records if r.get("portfolio")), None),
        "source": "Australian Government Transparency Portal (transparency.gov.au)",
        "sourceApi": API,
        "license": "CC BY 4.0 (Commonwealth of Australia, Transparency Portal terms)",
        "retrievedRecordCount": len(records),
        "contentTypes": sorted({r.get("contentType") for r in records}),
        "periods": [periods[k] for k in sorted(periods)],
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return len(records), sorted(periods)


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    targets = DEPARTMENTS if argv[0] == "--departments" else argv
    os.makedirs(SOURCES, exist_ok=True)
    index = []
    for name in targets:
        try:
            n, periods = fetch_entity(name)
            status = "ok" if n else "NO DATA"
            print(f"[{status}] {name}: {n} records, periods {periods}")
            index.append({"entity": name, "slug": slug(name), "records": n, "periods": periods})
        except Exception as e:
            print(f"[ERROR] {name}: {e}", file=sys.stderr)
            index.append({"entity": name, "slug": slug(name), "error": str(e)})
    with open(os.path.join(SOURCES, "index.json"), "w") as f:
        json.dump({"source": "transparency.gov.au data API", "entities": index}, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len([i for i in index if i.get('records')])} entity source folders under sources/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

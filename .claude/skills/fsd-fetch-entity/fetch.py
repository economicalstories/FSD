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
    python3 fetch.py --all              # every entity in the register (NCEs + CCEs)
    python3 fetch.py --audit-names      # flag register names whose recent data sits under a renamed entity

Output (per entity):
    sources/<slug>/transparency_raw.json   raw API records (verbatim)
    sources/<slug>/manifest.json           provenance: periods, content types, backlinks
"""
import json, os, re, sys, time, urllib.request, urllib.error

API = "https://data.transparency.gov.au/api/datasets/simplified"
PORTAL = "https://www.transparency.gov.au/publications"

# Financial-statement extract datasets the Transparency Portal publishes per entity.
# Both the non-corporate (NCE) and corporate (CCE) variants are requested; the API
# returns whichever exist for a given entity, so the same call works for any entity.
CONTENT_TYPES = [
    # --- non-corporate Commonwealth entities (NCE) ---
    "extract_dept__statement_of_comp_income___nce_23_24",      # Statement of Comprehensive Income
    "extract_of_statement_of_financial_position_____cop",       # Statement of Financial Position (multi-year)
    "extract_of_cash_flow_statement___nce_23_24_",             # Cash Flow Statement
    "dept__current_distinction___assets_and_liab__nce_23_24",  # Current / non-current assets & liabilities
    "extract_of_admin__statement_of_comp__income_nce_23_24",   # Comprehensive Income (administered)
    "extract_admin__of_assets_and_liabilities_nce_23_24",      # Administered assets & liabilities
    # --- corporate Commonwealth entities (CCE) ---
    "extract_dept__statement_of_comp_income___cce_23_24",      # Statement of Comprehensive Income
    "extract_of_statement_of_financial_position___cce",        # Statement of Financial Position (multi-year)
    "extract_of_dept_cash_flow_statement_cce_23_24",           # Cash Flow Statement
    "dept__current_distinction___assets_and_liab__cce_23_24",  # Current / non-current assets & liabilities
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
    # Active — now reports under an expanded name (same entity).
    "Organ and Tissue Authority": [
        "Organ and Tissue Authority (Australian Organ and Tissue Donation and Transplantation Authority)",
        "Organ and Tissue Authority",
    ],
    # Active — publishes under its current legal name (register carries a former/trading name).
    "Australian Crime Commission (Australian Criminal Intelligence Commission)": [
        "Australian Criminal Intelligence Commission",
        "Australian Crime Commission (Australian Criminal Intelligence Commission)",
    ],
    "Army and Air Force Canteen Service (Frontline Defence Services)": [
        "Army and Air Force Canteen Service",
        "Army and Air Force Canteen Service (Frontline Defence Services)",
    ],
}

# Transparency Portal appends footnote markers like " [i]" / " [1]" to some entity
# names. These are not renames — strip them before deciding whether an entity was
# genuinely renamed by a machinery-of-government change.
def canon_name(n):
    return re.sub(r"\s*\[[^\]]*\]\s*$", "", (n or "")).strip()

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
INDEX = os.path.join(ROOT, "index.html")


def register_names():
    """All entity names from the register the dashboard ships with."""
    html = open(INDEX, encoding="utf-8").read()
    m = re.search(r'<script id="entity-data" type="application/json">(.*?)</script>', html, re.S)
    return [e["name"] for e in json.loads(m.group(1))]


FP_TYPES = ["extract_of_statement_of_financial_position_____cop",
            "extract_of_statement_of_financial_position___cce"]
_STOP = {"the", "of", "and", "for", "department", "authority", "commission", "australian",
         "australia", "agency", "office", "national", "commonwealth", "corporation",
         "service", "services", "council"}


def _norm(n):
    return re.sub(r"[^a-z0-9 ]", " ", canon_name(n).lower()).strip()


def _tokens(n):
    return {w for w in _norm(n).split() if len(w) > 3 and w not in _STOP}


def audit_names():
    """Flag register names that have no recent data under their own name (or a known
    alias), and suggest near-match entity names — so machinery-of-government renames
    are caught proactively rather than after someone notices stale figures."""
    cutoff = int(os.environ.get("FSD_ACTIVE_SINCE_FY", "2023"))
    resp = post({"contentType": FP_TYPES, "entity": [], "entityCodename": [],
                 "reportingPeriod": [], "portfolio": [], "filter": "*"})
    universe = {}
    for r in resp.get("entityData", []):
        nm, per = r.get("entity"), r.get("reportingPeriod")
        if nm and per:
            universe.setdefault(nm, set()).add(per)
    syr = lambda p: int(str(p)[:4]) if str(p)[:4].isdigit() else 0
    recent = {nm for nm, ps in universe.items() if max((syr(p) for p in ps), default=0) >= cutoff}
    recent_norm = {_norm(nm) for nm in recent}
    reg = register_names()
    print(f"Auditing {len(reg)} register names against {len(recent)} entities reporting FY>={cutoff}...\n")
    flagged = 0
    for name in reg:
        checks = ALIASES.get(name, [name])
        if any(_norm(c) in recent_norm for c in checks):
            continue
        flagged += 1
        rt = _tokens(name)
        scored = sorted(((len(rt & _tokens(c)) / len(rt | _tokens(c)), c, max(universe[c]))
                         for c in recent if rt and _tokens(c) and len(rt & _tokens(c)) / len(rt | _tokens(c)) >= 0.5),
                        reverse=True)
        print(f"[CHECK] {name!r} — no FY>={cutoff} data under this name")
        if scored:
            for j, cand, latest in scored[:3]:
                print(f"        ~ likely match: {cand!r} (latest {latest}, token overlap {j:.2f}) → consider ALIASES")
        else:
            print(f"        (no near-match; likely genuinely defunct or financially exempt — see analyse.py CURATED_HISTORICAL / ACTIVE_EXEMPT)")
    print(f"\n{flagged} register names need review. Names already covered by ALIASES are skipped.")
    return 0


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
    # Genuinely renamed only if a source name (ignoring footnote markers) differs
    # from the register name — not merely a "[i]" footnote.
    renamed = any(canon_name(s) != canon_name(name) for s in source_names)
    manifest = {
        "registerName": name,
        "sourceEntityNames": source_names,
        "renamed": renamed,
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
    if argv[0] == "--audit-names":
        return audit_names()
    if argv[0] == "--departments":
        targets = DEPARTMENTS
    elif argv[0] == "--all":
        targets = register_names()
    else:
        targets = argv
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

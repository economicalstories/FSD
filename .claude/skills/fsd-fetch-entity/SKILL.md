---
name: fsd-fetch-entity
description: >-
  Search and download public financial data for an Australian Commonwealth entity
  from the Government Transparency Portal (transparency.gov.au) into the sources/
  folder, with backlinks. Use when populating the Financial Stability Dashboard
  with real figures for a department, agency or corporate Commonwealth entity, or
  refreshing an entity's source data. Step 1 of the fetch→analyse pipeline.
---

# fsd-fetch-entity — download an entity's public financial data

Downloads an entity's annual-report **financial-statement extracts** from the
Australian Government Transparency Portal and stores them under `sources/`, with a
provenance manifest that backlinks to the original annual report. This is step 1
of the pipeline; `fsd-analyse-entity` is step 2.

## Data source

The Transparency Portal (https://www.transparency.gov.au/) is backed by a public
data API at `https://data.transparency.gov.au/api/datasets/simplified`. It is a
`POST` endpoint taking a JSON body; the useful filters are:

```json
{
  "contentType": ["<dataset codename>", ...],   // which datasets (statements)
  "entity":      ["<exact entity name>", ...],   // filters to these entities
  "entityCodename": [], "reportingPeriod": [], "portfolio": [],
  "filter": "*"                                  // required; "*" = no extra filter
}
```

It returns `{ "entityData": [ <record>, ... ] }`. Each record has `datafields`
(the statement line items, keyed `"<line item>|current year"` etc., values in
`$'000`), plus `contentType`, `entity`, `reportingPeriod`, and the backlinks
`annualReportUrl` / `annualReportTitle` / `datasetUrl`.

The departmental financial-statement datasets fetched are:

| Codename | Statement |
|---|---|
| `extract_dept__statement_of_comp_income___nce_23_24` | Statement of Comprehensive Income (departmental) |
| `extract_of_statement_of_financial_position_____cop` | Statement of Financial Position (multi-year) |
| `extract_of_cash_flow_statement___nce_23_24_` | Cash Flow Statement (departmental) |
| `dept__current_distinction___assets_and_liab__nce_23_24` | Current/non-current assets & liabilities |
| `extract_of_admin__statement_of_comp__income_nce_23_24` | Statement of Comprehensive Income (administered) |
| `extract_admin__of_assets_and_liabilities_nce_23_24` | Administered assets & liabilities |

## Run it

```bash
# A single entity (name must match the entity register exactly)
python3 .claude/skills/fsd-fetch-entity/fetch.py "Department of the Treasury"

# All 19 Departments of State (incl. parliamentary departments)
python3 .claude/skills/fsd-fetch-entity/fetch.py --departments
```

## Output

```
sources/<slug>/transparency_raw.json   verbatim API records for the entity
sources/<slug>/manifest.json           provenance: periods, content types, backlinks
sources/index.json                     summary of what was fetched
```

## Notes & gotchas

- **Exact names.** The API filters on the entity's exact published name. Names
  drift with machinery-of-government changes (e.g. recent years of *Department of
  Education* are published as `Department of Education [i]`; *Infrastructure...*
  gained *Sport* in 2024-25). `ALIASES` in `fetch.py` maps a register name to its
  recognised continuations; the source entity name is preserved on every record
  and surfaced in the manifest (`renamed`, `sourceEntityNames`).
- **No transformation here.** This step only downloads and records provenance.
  Mapping to indicators and computing ratios happens in `fsd-analyse-entity`.
- **Network.** The API is large; requests retry with exponential backoff.

## Chain to step 2

After fetching, analyse and load into the dashboard:

```bash
python3 .claude/skills/fsd-analyse-entity/analyse.py "Department of the Treasury"
```

Or run the whole pipeline for the departments at once:

```bash
bash scripts/run_departments.sh
```

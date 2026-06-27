# Data sources

Public financial data downloaded for the Financial Stability Dashboard. This
folder is produced by the `fsd-fetch-entity` and `fsd-analyse-entity` skills and
is safe to regenerate at any time:

```bash
bash scripts/run_departments.sh
```

## Where it comes from

All data here is from the **Australian Government Transparency Portal**
(https://www.transparency.gov.au/) via its public data API
(`https://data.transparency.gov.au/api/datasets/simplified`). It is the annual
report **financial-statement extracts** that Commonwealth entities are required to
publish after their audited financial statements are tabled in Parliament.

© Commonwealth of Australia. Transparency Portal content is published under
CC BY 4.0. Figures are in `$'000` unless stated otherwise.

## Layout

```
sources/
  index.json                  what was fetched (entity → records, periods)
  seed.json                   consolidated seed injected into index.html
  <entity-slug>/
    transparency_raw.json     verbatim API records for the entity
    manifest.json             provenance: periods, content types, backlinks
```

## Scope (this pass)

The **19 Departments of State** (including the three Parliamentary departments),
used to validate the approach before extending to the other ~156 Commonwealth
entities. Each entity is seeded from the most recent reporting period that has the
full statement set — generally **2024-25** (2023-24 where 2024-25 is not yet
published).

## Provenance & caveats

- Every figure in the dashboard clicks through to the exact annual-report page it
  came from (`manifest.json` → `periods[].annualReportUrl`).
- Some departments report recent years under a **renamed** entity after
  machinery-of-government changes; the manifest records this (`renamed: true`,
  `sourceEntityNames`) and the dashboard surfaces it in the provenance bar.
- Ratio **formulas and thresholds remain illustrative** — see the dashboard's own
  caveats. Two ratios (Days Operating Cash on Hand, Capital Sustainability) need
  note-level lease figures not present in these extracts and are left blank rather
  than guessed.

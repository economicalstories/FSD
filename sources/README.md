# Data sources

Public financial data downloaded for the Financial Stability Dashboard. This
folder is produced by the `fsd-fetch-entity` and `fsd-analyse-entity` skills and
is safe to regenerate at any time:

```bash
bash scripts/run_all.sh           # every entity in the register (NCEs + CCEs)
bash scripts/run_departments.sh   # just the 19 Departments of State
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
  benchmarks.json             per-group ratio distributions + each entity's rank
  status.json                 active vs historical (defunct) status per entity, with reason
  <entity-slug>/
    transparency_raw.json     verbatim API records for the entity
    manifest.json             provenance: periods, content types, backlinks
```

## Scope

The **whole register** — non-corporate and corporate Commonwealth entities (~169 of
175 have a complete statement set and are seeded; the rest lack one of the required
statements for the latest period). Each entity is seeded from the most recent period
with the full statement set — generally **2024-25** (2023-24 where 2024-25 is not yet
published). The 19 Departments of State were the first validation pass.

## Relative benchmarking

`benchmarks.json` records, for each comparison group (entity type, and functional
category) and each ratio, the distribution (min/quartiles/median/max/mean) and every
entity's **concern rank** (1 = furthest toward the less-favourable tail) and
percentile. The dashboard computes the same thing live, so indicators are read
relative to peers rather than against absolute thresholds.

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

---
name: fsd-analyse-entity
description: >-
  Load downloaded Transparency Portal data from sources/, map it to the Financial
  Stability Dashboard's indicators, compute the ratios, trends and peer benchmarks,
  and inject the seed into index.html with per-figure backlinks. Use after
  fsd-fetch-entity has downloaded an entity's data. Step 2 of the fetch→analyse pipeline.
---

# fsd-analyse-entity — load, analyse & benchmark an entity's data

Reads the raw financial-statement extracts that `fsd-fetch-entity` saved under
`sources/`, maps each line item to the dashboard's ratio inputs (for non-corporate
**and** corporate entities), computes multi-year trends, works out the
**distribution of each ratio within each comparison group**, and injects a **seed**
block into `index.html` so the dashboard ships pre-loaded with real, sourced figures
that are ranked relative to peers rather than against fixed thresholds. Step 2 of
the pipeline.

## NCE vs CCE

Corporate entities publish the same statements under different content-type
codenames, with minor field-name differences (a trailing space in the cash key,
`used operating act.` vs `used for operating act.`) and **negative** signs on
cash outflows. The mapping accepts both name variants and takes flow figures as
**magnitudes**, so one code path handles every entity.

## What it does

1. **Pick the period.** For each entity, choose the most recent reporting period
   that has the *full* set of statements needed to compute the ratios
   (Comprehensive Income + Financial Position + Cash Flow + current/non-current).
2. **Map line items → indicator inputs** (verbatim figures, `$'000`):

   | Ratio | Inputs ← line item (statement) |
   |---|---|
   | Total liabilities / Total assets | `liabilities - total liabilities`, `assets - total assets` (Financial Position) |
   | Financial assets / Total liabilities | `assets - total financial assets`, `liabilities - total liabilities` (Financial Position) |
   | Current ratio | `assets - no more than 12 months`, `liabilities - no more than 12 months` (current/non-current) |
   | Capital turnover | `net cash from investing act.` (abs), `assets - total non-financial assets` |
   | Liquidity | `cash at the end of reporting period`, `total cash used for operating act.`, `total cash used financing act.`, `net cash from investing act.` (abs) |

   The two ratios needing note-level breakouts not in these extracts (Days
   Operating Cash on Hand, Capital Sustainability — they require lease payments
   and interest-on-leases) are deliberately left for manual entry. Honest gaps
   over guessed numbers.
3. **Build trends** (operating result, employee-expense ratio, cash reserves)
   across years, densified using both the *current year* and *previous year*
   columns of each statement.
4. **Record provenance** for every seeded figure (line item, statement, period,
   backlink) so each value clicks through to its audited source.
5. **Benchmark.** For each comparison group (entity type, and functional category)
   and each ratio, compute the distribution (min/quartiles/median/max/mean) and
   each entity's relative standing — a **concern rank** (1 = furthest toward the
   less-favourable tail) and percentile. Written to `sources/benchmarks.json`.
6. **Inject** the consolidated seed into `index.html` between
   `<!--SEED-START-->` / `<!--SEED-END-->` and write `sources/seed.json`.

## Active vs historical (defunct) status

The skill also tags every register entity **active** or **historical** and injects a
`status-data` block (and `sources/status.json`). The dashboard shows active entities
by default and hides historical (defunct/superseded) ones behind a toggle; historical
entities are also excluded from peer benchmarks.

- **historical** = either a curated, evidence-based defunct entity (`CURATED_HISTORICAL`,
  e.g. ANPHA, abolished 2014) **or** an entity whose latest annual report predates
  FY2023-24 (clearly stopped reporting → superseded).
- Absence of financial data is **not** treated as defunct: intelligence/security and
  on-base bodies (`ACTIVE_EXEMPT`) are active but don't publish statements.
- Footnote markers like `[i]` are stripped before deciding an entity was renamed, so a
  continuing department (e.g. Education) is not mislabelled as machinery-of-government'd.

## Relative, not absolute

The dashboard reads every indicator **relative to peers** in the selected group
(default: the entity's own like-for-like category), so a whole class of entity is
never blanket-labelled. The dashboard computes this live from the working store
(so it reflects edits and group changes); `benchmarks.json` is the same computation
captured for transparency/validation. Direction per ratio: lower-is-healthier
(`lta`), higher-is-healthier (`fatl`, `cur`, `liq`), or band/outlier (`cto`).

## Run it

```bash
# Analyse everything currently in sources/
python3 .claude/skills/fsd-analyse-entity/analyse.py

# Or specific entities
python3 .claude/skills/fsd-analyse-entity/analyse.py "Department of the Treasury"
```

## How the dashboard consumes the seed

`index.html` parses the `seed-data` JSON and, on load, merges seeded values into
its working store **non-destructively** — a seeded figure only fills a slot the
analyst has not already edited, so manual entries are never overwritten. Seeded
entities show a provenance bar ("Financial figures pre-loaded from the 2024-25
audited financial statements …"), each ratio lists the exact line items it used,
and source links point at the precise annual-report financial-statements page.

## No synthetic data

Every seeded number is a verbatim figure from a published, audited financial
statement, carried with a click-through to its source. Thresholds and the ratio
formulas themselves remain illustrative (see the dashboard's own caveats).

## Chain from step 1

```bash
python3 .claude/skills/fsd-fetch-entity/fetch.py "Department of the Treasury"   # download
python3 .claude/skills/fsd-analyse-entity/analyse.py "Department of the Treasury" # analyse + inject
# ...or both, for all departments:
bash scripts/run_departments.sh
```

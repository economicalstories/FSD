# Commonwealth Entity Financial Stability — Early Warning Dashboard (Prototype)

> **⚠ Prototype demonstration only — not for reliance.** This is a non-production demo and must
> not be relied upon for any purpose. No automated assessment, ranking or conclusion it produces
> is authoritative.

A single, self-contained HTML dashboard (`index.html`) that frames an early-warning approach for
monitoring the financial sustainability of Australian Government **non-corporate** and **corporate**
Commonwealth entities — surfacing leading indicators of financial pressure so they can be engaged
earlier, rather than managed as a crisis.

Open `index.html` in any modern browser. No build step, no server, no dependencies.

## Scope

In scope: **175 entities** — 101 non-corporate Commonwealth entities (NCEs) and 74 corporate
Commonwealth entities (CCEs) — taken from the Department of Finance
[*Flipchart of PGPA Act Commonwealth entities and companies*](https://www.finance.gov.au/about-us/glossary/pgpa/flipchart-pgpa-act-commonwealth-entities-and-companies)
(1 March 2024). The 16 Commonwealth companies (Corporations Act 2001 companies) are **excluded**
per scope.

## No synthetic data — everything clicks through to its source

The dashboard ships with **zero dummy or synthetic financial data**. Pre-loaded content is either
public structural information or real, sourced figures:

- the entity register (names, portfolios, governance flags) from the Flipchart;
- the indicator definitions (formulas, the exact financial-statement line items, illustrative thresholds); and
- **real audited financial figures for ~169 Commonwealth entities** (non-corporate and corporate),
  downloaded from the [Transparency Portal](https://www.transparency.gov.au/) and pre-loaded with a
  backlink to the exact annual-report financial statements each figure came from
  (see [Data pipeline](#data-pipeline-fetch--analyse)).

Every quantitative value is either pre-loaded from a cited public source, entered by the user from a
cited public source, or left blank with a link to where that figure is published. Seeded figures are
merged **non-destructively** — they never overwrite an analyst's own entries. Each entity links to:

- its annual report & audited financial statements on [transparency.gov.au](https://www.transparency.gov.au/publications),
- the Transparency Portal's own published [financial-sustainability ratios](https://www.transparency.gov.au/),
- the [ANAO financial-statement audit reports](https://www.anao.gov.au/pubs/financial-statement-audit), and
- its [Flipchart](https://www.finance.gov.au/about-us/glossary/pgpa/flipchart-pgpa-act-commonwealth-entities-and-companies) entry.

User-entered figures and analyst notes are stored **locally in the browser only** (localStorage); nothing is transmitted.

## Features

- **Period selection** — day / month / year (annual is the primary audited cycle).
- **Entity selection** — search and filter all 175 entities by **entity type** (corporate /
  non-corporate), **like-for-like category** (department, regulator, RDC, cultural body, …), and portfolio.
- **Currently-active by default** — defunct / superseded entities (abolished or merged by
  machinery-of-government changes, e.g. ANPHA) are tagged *Defunct*, hidden by default behind a
  *Show historical* toggle, and excluded from peer benchmarks. Status is evidence-based (curated
  abolitions + Administrative Arrangements Orders), not inferred from missing data — so active but
  financially-exempt bodies (intelligence agencies) stay visible.
- **Relative (peer-benchmarked) indicators** — instead of pass/fail thresholds, each ratio is read
  against the **distribution of its peers** in the selected comparison group. Every indicator card shows
  the entity's value, its rank (*n of N from the less-favourable end*) and a distribution strip (this
  entity vs the peer median and middle-50%). This avoids blanket-labelling whole classes of entity (e.g.
  departments, which all hold little cash, are no longer all flagged on liquidity).
- **Peer ranking** — a league table of the comparison group ordered by a composite of relative standing,
  surfacing *who is first* for attention **without objectively labelling anyone**.
- **Ratio indicators** — Liquidity, Total Liabilities/Total Assets, Financial Assets/Total Liabilities,
  Capital Turnover, Current Ratio (computed from audited statements), plus Days Operating Cash on Hand
  and Capital Sustainability (need note-level lease figures — left for manual entry).
- **Trend indicators** — cash reserves, employee expenses as % of revenue, operating result, with
  multi-year sparklines.
- **Forecast accuracy (MAPE)**, budget / terminating-funding / audit prompts.
- **Qualitative insights** — analyst commentary to distinguish signal from noise.
- **Data quality & provenance** panel with explicit limitations (timeliness, comparability, data gaps).

## Design principles encoded

Indicators are relative to peers, never absolute pass/fail; no single indicator is determinative;
a high rank prompts investigation, never concludes; comparisons are like-for-like; thresholds are
illustrative defaults, not endorsed benchmarks; and corporate trading bodies are compared with peers,
not departments.

## Data pipeline (fetch → analyse)

Real data is populated by two chained, reusable skills under `.claude/skills/`:

1. **`fsd-fetch-entity`** — searches and downloads an entity's annual-report financial-statement
   extracts from the Transparency Portal data API into `sources/<entity>/`, with a provenance
   manifest of periods and backlinks. No transformation.
2. **`fsd-analyse-entity`** — loads that data (non-corporate and corporate), picks the latest period
   with the full statement set, maps each line item to the dashboard's ratio inputs, computes
   multi-year trends, **benchmarks each ratio across every comparison group**, records per-figure
   provenance, and injects the seed into `index.html` (and writes `sources/benchmarks.json`).

Run the whole chain across the full register (NCEs + CCEs):

```bash
bash scripts/run_all.sh           # every entity
bash scripts/run_departments.sh   # just the 19 Departments of State
```

…or one entity at a time:

```bash
python3 .claude/skills/fsd-fetch-entity/fetch.py   "Department of the Treasury"
python3 .claude/skills/fsd-analyse-entity/analyse.py "Department of the Treasury"
```

Downloaded data and provenance live under [`sources/`](sources/README.md). The Departments of State
were the first validation pass; the pipeline now covers the whole register.

Five ratios per entity are computed directly from the audited statements (Total liabilities/Total
assets, Financial assets/Total liabilities, Current ratio, Capital turnover, Liquidity). Two ratios
that require note-level lease figures absent from the extracts (Days Operating Cash on Hand, Capital
Sustainability) are left blank for manual entry rather than estimated. Each indicator is then read
**relative to the entity's peer group**, not against a fixed threshold.

## Sources

- Department of Finance — [finance.gov.au](https://www.finance.gov.au/) (Flipchart / PGPA register)
- [transparency.gov.au](https://www.transparency.gov.au/) (annual reports, financial statements, financial ratios)
- Australian National Audit Office — [anao.gov.au](https://www.anao.gov.au/) (financial-statement audits)
- **GFS sector** (GGS / PNFC / PFC) — Dept. of Finance glossary
  ([GGS](https://www.finance.gov.au/about-us/glossary/pgpa/term-general-government-sector-ggs),
  [PNFC](https://www.finance.gov.au/about-us/glossary/pgpa/term-public-non-financial-corporations),
  [PFC](https://www.finance.gov.au/about-us/glossary/pgpa/term-public-financial-corporations-pfc-0)) and the
  PGPA Flipchart markers; the authoritative list of entities outside the GGS is **Budget Paper No. 1,
  Statement 10, Appendix A** ([budget.gov.au](https://budget.gov.au/)). The dashboard derives each entity's
  sector from the Flipchart flags and exposes it as a comparison-group basis.
- **Entity status** (active / defunct) — Administrative Arrangements Orders and the Finance
  [Machinery of Government Changes Guide](https://www.finance.gov.au/government/machinery-government-changes-guide).

This dashboard is not endorsed by the Australian Government, the Department of Finance or the ANAO.

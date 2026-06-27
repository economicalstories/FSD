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

The dashboard ships with **zero dummy or synthetic financial data**. The only pre-loaded content is
public, verifiable structural information:

- the entity register (names, portfolios, governance flags) from the Flipchart, and
- the indicator definitions (formulas, the exact financial-statement line items, illustrative thresholds).

Every quantitative value is either entered by the user from a cited public source, or left blank with
a link to where that figure is published. Each entity links to:

- its annual report & audited financial statements on [transparency.gov.au](https://www.transparency.gov.au/publications),
- the Transparency Portal's own published [financial-sustainability ratios](https://www.transparency.gov.au/),
- the [ANAO financial-statement audit reports](https://www.anao.gov.au/pubs/financial-statement-audit), and
- its [Flipchart](https://www.finance.gov.au/about-us/glossary/pgpa/flipchart-pgpa-act-commonwealth-entities-and-companies) entry.

User-entered figures and analyst notes are stored **locally in the browser only** (localStorage); nothing is transmitted.

## Features

- **Period selection** — day / month / year (annual is the primary audited cycle).
- **Entity selection** — search and filter all 175 entities by portfolio and type.
- **Ratio indicators** — Days Operating Cash on Hand, Capital Sustainability, Liquidity, Total
  Liabilities/Total Assets, Financial Assets/Total Liabilities, Capital Turnover, Current Ratio. Each
  states its formula, maps inputs to financial-statement line items, computes on entry, and flags
  against *illustrative* thresholds.
- **Trend indicators** — cash reserves, employee expenses as % of revenue, operating result, and
  staffing levels, with multi-year sparklines.
- **Forecast accuracy (MAPE)**, budget / terminating-funding / audit prompts, and **peer comparison**
  by portfolio, entity type, GFS classification, materiality or function.
- **Qualitative insights** — analyst commentary to distinguish signal from noise.
- **Data quality & provenance** panel with explicit limitations (timeliness, comparability, data gaps).

## Design principles encoded

No single indicator is determinative; flags prompt investigation, never conclude; thresholds are
illustrative defaults, not endorsed benchmarks; and corporate trading bodies are compared with peers,
not departments.

## Sources

- Department of Finance — [finance.gov.au](https://www.finance.gov.au/) (Flipchart / PGPA register)
- [transparency.gov.au](https://www.transparency.gov.au/) (annual reports, financial statements, financial ratios)
- Australian National Audit Office — [anao.gov.au](https://www.anao.gov.au/) (financial-statement audits)

This dashboard is not endorsed by the Australian Government, the Department of Finance or the ANAO.

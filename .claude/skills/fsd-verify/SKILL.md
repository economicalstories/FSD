---
name: fsd-verify
description: >-
  Independently fact-check the Financial Stability Dashboard's seeded data: re-fetch
  a sample of entities from the Transparency Portal on a separate code path, compare
  to sources/seed.json, confirm source backlinks resolve, and sanity-check headline
  findings. Use before committing a data change, before sharing the dashboard, or to
  audit data integrity.
---

# fsd-verify — fact-check the seeded data

Confirms the dashboard's pre-loaded figures are faithful to the source, on a code
path independent of `fsd-analyse-entity` (so a bug there can't vouch for itself).

## What it checks

1. **Figures** — for each sampled entity, re-fetches its financial statements from
   the Transparency Portal API, re-derives the five ratios' inputs with its own
   extractor, and compares to `sources/seed.json`. Any difference > 0.5 ($'000) is a
   mismatch.
2. **Backlinks** — confirms each sampled entity's `annualReportUrl` returns HTTP 200.
3. **Headline sanity** — lists every entity whose liabilities exceed assets (L/A > 1),
   so the most attention-worthy findings are easy to eyeball against the source.

Exit code is non-zero if any figure mismatches or any backlink is broken — so it can
gate a commit or CI step.

## Run it

```bash
python3 .claude/skills/fsd-verify/verify.py                       # curated diverse sample (NCE+CCE, large/small, a negative-net-assets case)
python3 .claude/skills/fsd-verify/verify.py --sample 12           # first 12 entities in seed.json
python3 .claude/skills/fsd-verify/verify.py "Department of the Treasury" "Wine Australia"
```

## When to run

- After `fsd-analyse-entity` / `fsd-refresh`, before committing.
- Before publishing or sharing the dashboard.
- Periodically, to catch source-side restatements (the Portal occasionally revises
  prior-year figures).

A full-coverage pass is `--sample 999` (every seeded entity); the curated default is
the quick confidence check.

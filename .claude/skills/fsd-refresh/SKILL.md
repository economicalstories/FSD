---
name: fsd-refresh
description: >-
  Re-pull the latest Transparency Portal data and report exactly what changed before
  committing — new/lost entities, entities moved to a newer reporting period, active↔
  defunct status flips, and figure changes. Use when new annual reports are published
  (the audited cycle lands ~Oct–Dec each year) to keep the dashboard current.
---

# fsd-refresh — update the data and diff what changed

Keeps the dashboard current without surprises. It snapshots the committed
seed/status, re-runs the `fsd-fetch-entity` → `fsd-analyse-entity` pipeline, then
diffs the result so you review the change set before committing.

## What it reports

- **Newly seeded / no longer seeded** entities (data appeared or disappeared).
- **Moved to a newer period** — e.g. an entity that flipped from 2023-24 to 2024-25.
- **Status flips** — active ↔ historical (a new abolition, or a previously-stale
  entity that resumed reporting).
- **Count of entities with any figure change.**

It does **not** commit, and does **not** edit the curated lists for you.

## Run it

```bash
python3 .claude/skills/fsd-refresh/refresh.py                  # fetch --all + analyse, then diff
python3 .claude/skills/fsd-refresh/refresh.py --active-since 2024   # also bump the "currently active" FY threshold
python3 .claude/skills/fsd-refresh/refresh.py --skip-fetch     # re-analyse existing sources/ only (fast)
```

## Annual refresh checklist

1. **`fetch.py --audit-names`** — catch machinery-of-government renames; add any to
   `ALIASES` in `fsd-fetch-entity/fetch.py`.
2. **`refresh.py --active-since <new FY>`** — bump the threshold so last year's
   leftovers age out; review the diff.
3. Update `CURATED_HISTORICAL` (new abolitions) and `ACTIVE_EXEMPT` in
   `fsd-analyse-entity/analyse.py` if the status diff flags anything.
4. **`fsd-verify`** — confirm the new figures match source.
5. Commit; if hosting via GitHub Pages it republishes automatically.

The maintenance knobs all live in two files: `ALIASES` (fetch.py) and
`ACTIVE_SINCE_FY` / `CURATED_HISTORICAL` / `ACTIVE_EXEMPT` (analyse.py).

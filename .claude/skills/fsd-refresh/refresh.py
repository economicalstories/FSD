#!/usr/bin/env python3
"""
fsd-refresh : re-pull the latest public data and report exactly what changed.

Run this when new annual reports are published (the audited cycle lands ~Oct–Dec
each year). It snapshots the current seed/status, re-runs the fetch→analyse
pipeline, then DIFFS the result so you can see — and sanity-check — what moved
before committing:

  • entities newly seeded / no longer seeded
  • entities now on a newer reporting period
  • status flips (active ↔ historical)
  • how many entities had any figure change

It never commits and never edits the curated lists for you — review the diff,
update ALIASES / CURATED_HISTORICAL / ACTIVE_EXEMPT (and bump --active-since) as
needed, then re-run.

Usage:
    python3 refresh.py                      # full refresh: fetch --all + analyse, then diff
    python3 refresh.py --active-since 2024  # also bump the "currently active" FY threshold
    python3 refresh.py --skip-fetch         # re-analyse existing sources/ only (fast), then diff
"""
import json, os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SOURCES = os.path.join(ROOT, "sources")
FETCH = os.path.join(ROOT, ".claude", "skills", "fsd-fetch-entity", "fetch.py")
ANALYSE = os.path.join(ROOT, ".claude", "skills", "fsd-analyse-entity", "analyse.py")


def load(path):
    return json.load(open(path)) if os.path.isfile(path) else {}


def snapshot():
    return {"seed": load(os.path.join(SOURCES, "seed.json")),
            "status": load(os.path.join(SOURCES, "status.json"))}


def diff(before, after):
    bs, as_ = before["seed"], after["seed"]
    bst, ast = before["status"], after["status"]
    bk, ak = set(bs), set(as_)

    added = sorted(ak - bk)
    removed = sorted(bk - ak)
    period_moves, figure_changes = [], 0
    for n in sorted(ak & bk):
        if bs[n].get("period") != as_[n].get("period"):
            period_moves.append((n, bs[n].get("period"), as_[n].get("period")))
        if json.dumps(bs[n].get("ratios"), sort_keys=True) != json.dumps(as_[n].get("ratios"), sort_keys=True):
            figure_changes += 1
    status_flips = [(n, bst.get(n, {}).get("status"), ast[n]["status"])
                    for n in sorted(ast) if bst.get(n, {}).get("status") != ast[n]["status"]]

    print("\n================ REFRESH DIFF ================")
    print(f"Seeded entities: {len(bk)} → {len(ak)}")
    print(f"\nNewly seeded ({len(added)}):");      [print(f"  + {n}") for n in added] or print("  (none)")
    print(f"\nNo longer seeded ({len(removed)}):"); [print(f"  - {n}") for n in removed] or print("  (none)")
    print(f"\nMoved to a newer period ({len(period_moves)}):")
    [print(f"  ~ {n}: {a} → {b}") for n, a, b in period_moves] or print("  (none)")
    print(f"\nStatus flips ({len(status_flips)}):")
    [print(f"  ! {n}: {a} → {b}") for n, a, b in status_flips] or print("  (none)")
    print(f"\nEntities with any figure change: {figure_changes}")
    print("=============================================")
    print("\nReview the above, update the curated lists if needed, run fsd-verify, then commit.")


def run(script, *args):
    print(f"\n$ python3 {os.path.relpath(script, ROOT)} {' '.join(args)}")
    r = subprocess.run([sys.executable, script, *args], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"step failed: {script}")


def main(argv):
    env_year = None
    skip_fetch = "--skip-fetch" in argv
    if "--active-since" in argv:
        env_year = argv[argv.index("--active-since") + 1]
        os.environ["FSD_ACTIVE_SINCE_FY"] = env_year
        print(f"Active-since FY set to {env_year} for this run.")

    before = snapshot()
    if not skip_fetch:
        run(FETCH, "--all")
    else:
        print("Skipping fetch — re-analysing existing sources/ only.")
    run(ANALYSE)
    after = snapshot()
    diff(before, after)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

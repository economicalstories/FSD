#!/usr/bin/env bash
#
# Chain the two skills across the WHOLE register: download public data for every
# Commonwealth entity (NCEs + CCEs) from the Transparency Portal, then analyse,
# benchmark and inject the seed into index.html.
#
#   fsd-fetch-entity   →  sources/<slug>/{transparency_raw.json,manifest.json}
#   fsd-analyse-entity →  sources/seed.json + sources/benchmarks.json + index.html
#
# Re-runnable: refetches the latest published figures and rebuilds seed + benchmarks.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Step 1/2  fetch: downloading every register entity from transparency.gov.au"
python3 .claude/skills/fsd-fetch-entity/fetch.py --all

echo
echo "==> Step 2/2  analyse: mapping to indicators, benchmarking, injecting seed"
python3 .claude/skills/fsd-analyse-entity/analyse.py

echo
echo "Done. Open index.html; indicators are ranked relative to each entity's peer group."

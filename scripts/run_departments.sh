#!/usr/bin/env bash
#
# Chain the two skills: download public data for every Department of State from the
# Transparency Portal, then analyse it and inject the seed into index.html.
#
#   fsd-fetch-entity  →  sources/<slug>/{transparency_raw.json,manifest.json}
#   fsd-analyse-entity →  sources/seed.json  +  index.html (seed block)
#
# Re-runnable: refetches the latest published figures and rebuilds the seed.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Step 1/2  fetch: downloading Departments of State from transparency.gov.au"
python3 .claude/skills/fsd-fetch-entity/fetch.py --departments

echo
echo "==> Step 2/2  analyse: mapping to indicators and injecting seed into index.html"
python3 .claude/skills/fsd-analyse-entity/analyse.py

echo
echo "Done. Open index.html and select any department to see pre-loaded figures."

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
(cd server && "$ROOT/.venv/bin/python" -m unittest discover -s tests -v)
(cd workers/price_tracker && "$ROOT/.venv/bin/python" -m unittest discover -s tests -v)
node --check web/dashboard.js
(cd server && node tests/test_orbit_devices_ui.js)
node server/tests/test_tracking_ui.js
node server/tests/test_navigation_ui.js
node server/tests/test_amule_ui.js
node server/tests/test_phone_ui.js

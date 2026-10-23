#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TEST_STATE_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_STATE_DIR"' EXIT
(cd server && EMBY_STATE_DB="$TEST_STATE_DIR/state.sqlite3" "$ROOT/.venv/bin/python" -m unittest discover -s tests -v)
(cd workers/price_tracker && "$ROOT/.venv/bin/python" -m unittest discover -s tests -v)
node --check web/dashboard.js
node --check web/operations.js
node --check web/api.js
node --check web/anime-calendar.js
node --check web/scheduled-tasks.js
node --check web/tonetti.js
node server/tests/test_api_ui.js
(cd server && node tests/test_orbit_devices_ui.js)
node server/tests/test_tracking_ui.js
node server/tests/test_navigation_ui.js
node server/tests/test_amule_ui.js
node server/tests/test_phone_ui.js

node server/tests/test_shared_layout_ui.js

node server/tests/test_operations_ui.js

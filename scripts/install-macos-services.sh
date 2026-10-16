#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/server/scripts/install-macos-services.sh"
"$ROOT/.venv/bin/python" "$ROOT/workers/price_tracker/scripts/launch_agent.py" install

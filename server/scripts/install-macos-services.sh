#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
ENV_FILE="$PROJECT_ROOT/.env"
VENV_DIR="$(cd "$PROJECT_ROOT/.." && pwd)/.venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ Falta $ENV_FILE"
  echo "   Copia .env.example a .env y rellena tus credenciales."
  exit 1
fi

mkdir -p "$LAUNCH_AGENTS" "$HOME/Library/Logs" "$(dirname "$VENV_DIR")"

if [ ! -x "$PYTHON" ]; then
  echo "📦 Creando entorno virtual..."
  python3 -c 'import sys; assert sys.version_info >= (3, 12), "Se necesita Python 3.12 o posterior"'
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON" -m pip install -r "$PROJECT_ROOT/../requirements.txt"

read_env_path() {
  local key="$1"
  local fallback="$2"
  "$PYTHON" - "$ENV_FILE" "$key" "$fallback" <<'PY2'
from pathlib import Path
import sys
from dotenv import dotenv_values

env_file, key, fallback = sys.argv[1:]
value = dotenv_values(env_file).get(key) or fallback
print(Path(value).expanduser())
PY2
}

INBOX_DIR="$(read_env_path INBOX_DIR "$HOME/Documents/Torrent")"
TORRENT_DROP_DIR="$(read_env_path TORRENT_DROP_DIR "$HOME/Downloads")"
GAME_DOWNLOAD_DIR="$(read_env_path GAME_DOWNLOAD_DIR "$HOME/Downloads/Games")"

mkdir -p "$INBOX_DIR" "$TORRENT_DROP_DIR" "$GAME_DOWNLOAD_DIR"

render_plist() {
  local template="$1"
  local output="$2"

  /usr/bin/python3 - "$template" "$output" "$PROJECT_ROOT" "$HOME" "$PYTHON" <<'PY2'
from pathlib import Path
import sys

src, dst, project, home, python = sys.argv[1:]

text = Path(src).read_text(encoding="utf-8")
text = (
    text
    .replace("__PROJECT_ROOT__", project)
    .replace("__HOME__", home)
    .replace("__PYTHON__", python)
)

Path(dst).write_text(text, encoding="utf-8")
PY2
}

render_plist "$PROJECT_ROOT/launchd/com.tone.emby-organizer.plist.template" \
  "$LAUNCH_AGENTS/com.tone.emby-organizer.plist"
render_plist "$PROJECT_ROOT/launchd/com.tone.telegram-download-bot.plist.template" \
  "$LAUNCH_AGENTS/com.tone.telegram-download-bot.plist"
render_plist "$PROJECT_ROOT/launchd/com.tone.emby-log-viewer.plist.template" \
  "$LAUNCH_AGENTS/com.tone.emby-log-viewer.plist"
render_plist "$PROJECT_ROOT/launchd/com.tone.emby-log-alerts.plist.template" \
  "$LAUNCH_AGENTS/com.tone.emby-log-alerts.plist"

for label in \
  com.tone.emby-organizer \
  com.tone.telegram-download-bot \
  com.tone.emby-log-viewer \
  com.tone.emby-log-alerts
do
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
done

launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS/com.tone.emby-organizer.plist"
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS/com.tone.telegram-download-bot.plist"
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS/com.tone.emby-log-viewer.plist"
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENTS/com.tone.emby-log-alerts.plist"

echo "✅ Servicios instalados y arrancados."
echo "   Organizer:  launchctl print gui/$(id -u)/com.tone.emby-organizer"
echo "   Telegram:   launchctl print gui/$(id -u)/com.tone.telegram-download-bot"
echo "   Log viewer: launchctl print gui/$(id -u)/com.tone.emby-log-viewer"
echo "   Log alerts: launchctl print gui/$(id -u)/com.tone.emby-log-alerts"

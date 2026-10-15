#!/usr/bin/env bash
set -euo pipefail
: "${EMBY_WATCH_DIR:?EMBY_WATCH_DIR is required}"
: "${EMBY_URL:?EMBY_URL is required}"
: "${EMBY_API_KEY:?EMBY_API_KEY is required}"
COOLDOWN="${COOLDOWN:-180}"
MIN_REFRESH_INTERVAL="${MIN_REFRESH_INTERVAL:-300}"
RETRY_INTERVAL="${RETRY_INTERVAL:-30}"
for value in "$COOLDOWN" "$MIN_REFRESH_INTERVAL" "$RETRY_INTERVAL"; do
  [[ "$value" =~ ^[0-9]+$ ]] || { echo 'Invalid refresh interval' >&2; exit 1; }
done
# One scheduler owns the pending refresh: events never launch background timers.
# Refresh only published videos; creating a directory or .uploading file is not completion.
last_refresh=-1000000000
pending=0
deadline=0
exec 3< <(inotifywait -m -r -e close_write -e moved_to -e delete -e moved_from \
  --format '%e|%w%f' "$EMBY_WATCH_DIR")
watcher_pid=$!
trap 'kill "$watcher_pid" 2>/dev/null || true' EXIT
while true; do
  timeout=1
  if (( pending )); then
    timeout=$((deadline - SECONDS))
    (( timeout > 0 )) || timeout=1
  fi
  if IFS='|' read -r -t "$timeout" event file <&3; then
    [[ "$file" == *"/.Trash"* ]] && continue
    if [[ "$event" == *ISDIR* ]]; then
      # A completed directory can also be moved into/out of the watched tree.
      [[ "$event" == *MOVED_TO* || "$event" == *MOVED_FROM* || "$event" == *DELETE* ]] || continue
      file="directory.mkv"
    fi
    case "$(printf '%s' "$file" | tr '[:upper:]' '[:lower:]')" in
      *.mkv|*.avi|*.mp4|*.m4v|*.ts|*.mov)
        pending=1
        deadline=$((SECONDS + COOLDOWN))
        minimum=$((last_refresh + MIN_REFRESH_INTERVAL))
        (( deadline >= minimum )) || deadline=$minimum
        ;;
    esac
  else
    # Bash 3 reports both EOF and a timed read as 1. Check the producer too.
    # Let systemd restart us if inotifywait dies instead of silently hanging.
    kill -0 "$watcher_pid" 2>/dev/null || exit 1
  fi
  if (( pending && SECONDS >= deadline )); then
    if curl --connect-timeout 10 --max-time 60 -fsS -X POST \
      "${EMBY_URL%/}/Library/Refresh?api_key=${EMBY_API_KEY}" >/dev/null; then
      last_refresh=$SECONDS
      pending=0
      echo 'Emby: actualización solicitada'
      if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
        curl --connect-timeout 10 --max-time 15 -fsS -X POST \
          "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode $'text=📺 Emby actualizado\n🎬 Biblioteca actualizada' >/dev/null || true
      fi
    else
      deadline=$((SECONDS + RETRY_INTERVAL))
      echo 'Emby: fallo de actualización; se reintentará' >&2
    fi
  fi
done

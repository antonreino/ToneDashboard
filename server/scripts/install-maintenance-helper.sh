#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${TONE_MAINTENANCE_APP:-$HOME/Applications/ToneMaintenanceRunner.app}"
mkdir -p "$APP/Contents/MacOS"
xcrun swiftc "$ROOT/native/MaintenanceRunner.swift" -o "$APP/Contents/MacOS/ToneMaintenanceRunner"
"$ROOT/../.venv/bin/python" - "$APP" "$ROOT" <<'PY'
from pathlib import Path
import plistlib,sys
app,root=map(Path,sys.argv[1:])
info={'CFBundleIdentifier':'ovh.tonecas.maintenance-runner','CFBundleName':'ToneMaintenanceRunner','CFBundleExecutable':'ToneMaintenanceRunner','CFBundlePackageType':'APPL','CFBundleVersion':'2','LSUIElement':True,'NSLocalNetworkUsageDescription':'Revisar y mantener tu servidor Proxmox y tu PS5 mediante tareas autorizadas del Dashboard.','TonePython':str(root.parent/'.venv/bin/python'),'ToneScript':str(root/'scripts/maintenance_bridge.py')}
(app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
PY
IDENTITY="$(security find-identity -v -p codesigning | sed -nE '/Apple Development:/s/.* ([A-F0-9]{40}) .*/\1/p' | head -1)"
if [ -z "$IDENTITY" ]; then IDENTITY=-; fi
codesign --force --sign "$IDENTITY" --identifier ovh.tonecas.maintenance-runner "$APP"
codesign --verify --deep --strict "$APP"
echo 'Asistente puntual de mantenimiento instalado; sin daemon ni servicio permanente adicional.'

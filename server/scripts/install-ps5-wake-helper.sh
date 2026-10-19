#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/TonePS5Wake.app"
mkdir -p "$APP/Contents/MacOS"
/usr/bin/xcrun swiftc "$ROOT/native/PS5Wake.swift" -o "$APP/Contents/MacOS/TonePS5Wake"
"${TONE_PYTHON:-$ROOT/../.venv/bin/python}" - "$APP" "$ROOT" <<'PYTHON'
import plistlib,sys
from pathlib import Path
app,root=map(Path,sys.argv[1:])
info={'CFBundleIdentifier':'ovh.tonecas.ps5-wake','CFBundleName':'TonePS5Wake','CFBundleExecutable':'TonePS5Wake','CFBundlePackageType':'APPL','CFBundleVersion':'1','LSUIElement':True,'NSLocalNetworkUsageDescription':'Despertar tu PS5 desde reposo al solicitar el código de Orbit.','TonePython':str(root.parent/'.venv/bin/python'),'ToneScript':str(root/'ps5_wake.py')}
(app/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
PYTHON
/usr/bin/codesign --force --sign - --identifier ovh.tonecas.ps5-wake "$APP"
echo 'Asistente puntual PS5 instalado; autoriza Red local si macOS lo solicita.'

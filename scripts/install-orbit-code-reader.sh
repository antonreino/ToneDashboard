#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HOME/Applications/ToneOrbitCodeReader.app"
mkdir -p "$DEST/Contents/MacOS"
/usr/bin/swiftc "$ROOT/native/OrbitCodeReader.swift" -o "$DEST/Contents/MacOS/ToneOrbitCodeReader" -framework AppKit -framework ApplicationServices
cat > "$DEST/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.tone.OrbitCodeReader</string>
<key>CFBundleName</key><string>ToneOrbitCodeReader</string>
<key>CFBundleExecutable</key><string>ToneOrbitCodeReader</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSUIElement</key><true/>
</dict></plist>
PLIST
/usr/bin/codesign --force --sign - --identifier com.tone.OrbitCodeReader "$DEST"
printf 'Lector instalado. Autorízalo en Ajustes del Sistema → Privacidad y seguridad → Accesibilidad: %s\n' "$DEST"
"$DEST/Contents/MacOS/ToneOrbitCodeReader" --request-permission >/dev/null || true

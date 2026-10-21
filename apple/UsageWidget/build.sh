#!/bin/bash
set -euo pipefail
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SOURCE_DIR/../.." && pwd)"
DESTINATION="${1:-/private/tmp/ToneUsageWidget.app}"
mkdir -p "$DESTINATION/Contents/MacOS"
xcrun swiftc -swift-version 5 -O -parse-as-library "$SOURCE_DIR/UsageModel.swift" "$SOURCE_DIR/UsageWidget.swift" -o "$DESTINATION/Contents/MacOS/ToneUsageWidget" -framework AppKit -framework SwiftUI
PUBLIC_VERSION="$(cat "$PROJECT_DIR/VERSION")"
cat > "$DESTINATION/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>ToneUsageWidget</string>
<key>CFBundleIdentifier</key><string>ovh.tone.UsageWidget</string>
<key>CFBundleName</key><string>Tone Usage</string>
<key>CFBundleDisplayName</key><string>Tone Usage</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>$PUBLIC_VERSION</string>
<key>CFBundleVersion</key><string>2</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>LSUIElement</key><true/>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --sign - --options runtime "$DESTINATION"
codesign --verify --strict "$DESTINATION"
echo "$DESTINATION"

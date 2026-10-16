#!/bin/zsh
set -e
cd "$(dirname "$0")"
if ! command -v xcodegen >/dev/null 2>&1; then
  echo "Falta XcodeGen. Instálalo una sola vez con: brew install xcodegen"
  exit 1
fi
xcodegen generate
open ToneDashboardApps.xcodeproj

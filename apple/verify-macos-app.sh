#!/usr/bin/env bash
# Verify the actual distributable, rather than treating a successful build as a launch check.
set -euo pipefail
APP="${1:?Indica la ruta de ToneDashboardApps.app}"
BINARY="$APP/Contents/MacOS/ToneDashboardApps"
test -f "$BINARY"
if /usr/bin/otool -L "$BINARY" | /usr/bin/grep -q 'ToneDashboardApps.debug.dylib'; then
  echo 'Error: no distribuir la biblioteca de depuración de Xcode.' >&2
  exit 1
fi
if test -f "$APP/Contents/MacOS/ToneDashboardApps.debug.dylib"; then
  echo 'Error: el paquete conserva archivos de una compilación Debug anterior.' >&2
  exit 1
fi
/usr/bin/codesign --verify --deep --strict "$APP"
echo 'Paquete macOS: firma válida, sin dependencia de biblioteca Debug.'

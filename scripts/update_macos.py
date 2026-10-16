#!/usr/bin/env python3
"""Actualiza una instalación existente conservando .env, .git y datos locales."""
import os
import tempfile
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent
TARGET = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path('/Volumes/Datos/Proyectos/Scripts/emby-organizer')
FILES = [
    '.env.example',
    '.gitignore',
    'README.md',
    'MACOS_MIGRATION.md',
    'requirements.txt',
    'emby_organizer.py',
    'state_db.py',
    'torrent_utils.py',
    'download_security.py',
    'request_security.py',
    'orbit_pairing.py',
    'orbit_devices.py',
    'orbit_devices.js',
    'orbit_devices.css',
    'native/OrbitCodeReader.swift',
    'scripts/install-orbit-code-reader.sh',
    'static/app-icon.png',
    'scripts/log-viewer.py',
    'orbit_dashboard_proxy.py',
    'orbit_bridge_shim.js',
    'orbit_dashboard_control.py',
    'scripts/telegram_torrent_bot.py',
    'scripts/log-error-watcher.py',
    'scripts/install-macos-services.sh',
    'scripts/status-macos.sh',
    'scripts/open-logs-macos.sh',
    'scripts/update_macos.py',
    'launchd/com.tone.emby-organizer.plist.template',
    'launchd/com.tone.telegram-download-bot.plist.template',
    'launchd/com.tone.emby-log-viewer.plist.template',
    'launchd/com.tone.emby-log-alerts.plist.template',
]
SERVICES = [
    'com.tone.emby-organizer',
    'com.tone.telegram-download-bot',
    'com.tone.emby-log-viewer',
    'com.tone.emby-log-alerts',
]

def apply_update(source, target):
    source, target = source.resolve(), target.resolve()
    if source == target:
        raise ValueError('El paquete origen debe estar en una carpeta distinta de la instalación.')
    if not target.is_dir() or not (target / '.env').is_file():
        raise ValueError('El destino debe ser una instalación existente con .env.')
    # Validate everything before replacing the first installed file.
    for rel in FILES:
        src, dst = source / rel, target / rel
        if not src.is_file() or src.is_symlink():
            raise ValueError(f'Falta un archivo del paquete: {rel}')
        if dst.is_symlink() or any(parent.is_symlink() for parent in dst.parents if parent != target.parent):
            raise ValueError(f'No se actualizan rutas simbólicas: {rel}')
        if rel.endswith('.py'):
            compile(src.read_bytes(), rel, 'exec')
    backup = target / '.update-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    replaced = []
    with tempfile.TemporaryDirectory(prefix='.update-stage-', dir=target) as staging:
        stage = Path(staging)
        for rel in FILES:
            staged = stage / rel
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / rel, staged)
            dst = target / rel
            if dst.exists():
                saved = backup / rel
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, saved)
        try:
            for rel in FILES:
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage / rel, dst)
                replaced.append(rel)
        except BaseException:
            for rel in reversed(replaced):
                dst, saved = target / rel, backup / rel
                if saved.exists():
                    shutil.copy2(saved, dst)
                else:
                    dst.unlink(missing_ok=True)
            raise
    return backup


def main():
    try:
        backup = apply_update(SOURCE, TARGET)
    except (OSError, ValueError, SyntaxError) as exc:
        raise SystemExit(f'Actualización abortada: {exc}') from exc
    uid = subprocess.check_output(['id', '-u'], text=True).strip()
    failed = []
    for label in SERVICES:
        result = subprocess.run(['launchctl', 'kickstart', '-k', f'gui/{uid}/{label}'], check=False)
        if result.returncode:
            failed.append(label)
    print(f'ToneDashboard actualizado en {TARGET}. Copia de seguridad: {backup}')
    if failed:
        print('Servicios que no se han podido reiniciar: ' + ', '.join(failed))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

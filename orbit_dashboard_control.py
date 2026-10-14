"""Acciones mínimas sobre Orbit Zero. Nunca inspecciona llaveros ni códigos de emparejamiento.

El arranque requiere autenticación HTTP del dashboard (comprobada por el handler),
una segunda contraseña y una solicitud same-origin con cabecera no simple.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path
import socket
import subprocess
import sys
from urllib.parse import urlsplit

ZERO_PORT = 34179
MAC_APP = Path('/Applications/Orbit Zero.app')


def running():
    try:
        with socket.create_connection(('127.0.0.1', ZERO_PORT), timeout=0.7):
            return True
    except OSError:
        return False


def get_status():
    password = os.getenv('ORBIT_CONTROL_PASSWORD', '')
    return {
        'running': running(),
        'can_start': sys.platform == 'darwin' and MAC_APP.is_dir() and len(password) >= 12,
        'start_configured': len(password) >= 12,
        'pair_code_available': False,
    }


def _same_origin(headers):
    origin = headers.get('Origin', '')
    host = headers.get('Host', '')
    try:
        parsed = urlsplit(origin)
        # Nginx Proxy Manager forwards the public Host; no external Origin allowed.
        return parsed.scheme in ('https', 'http') and bool(host) and parsed.netloc.lower() == host.lower()
    except ValueError:
        return False


def start_app(headers, client_address):
    """Devuelve (JSON, código HTTP); nunca acepta nombres ni comandos externos."""
    if not _same_origin(headers) or headers.get('X-Orbit-Action') != 'start':
        return {'error': 'Solicitud de origen no autorizado.'}, 403
    if headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/json':
        return {'error': 'Petición JSON requerida.'}, 415
    expected = os.getenv('ORBIT_CONTROL_PASSWORD') or ''
    provided = headers.get('X-Orbit-Control-Password') or ''
    if len(expected) < 12 or not provided or not hmac.compare_digest(provided, expected):
        return {'error': 'Contraseña adicional incorrecta o no configurada.'}, 403
    if running():
        return {'running': True, 'message': 'Orbit ya está disponible.'}, 200
    if sys.platform != 'darwin' or not MAC_APP.is_dir():
        return {'error': 'Orbit Zero no está instalado en /Applications/Orbit Zero.app.'}, 503
    try:
        subprocess.Popen(['/usr/bin/open', '-g', '-a', str(MAC_APP)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
    except OSError:
        return {'error': 'macOS no ha podido iniciar Orbit Zero.'}, 502
    return {'running': False, 'message': 'Arranque solicitado; verifica el estado en unos segundos.'}, 202

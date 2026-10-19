"""One-shot LAN discovery/wake for the owner's PS5. No daemon or PSN connection.
Protocol reference: chiaki-ng lib/src/discovery.c and lib/include/chiaki/discovery.h.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import re
import socket
import stat
import time
import threading
import subprocess
import tempfile
import sys

_wake_lock = threading.Lock()
_last_attempt = 0.0
_last_helper_wake = 0.0

HOST = '192.168.1.50'
PORT = 9302
PROTOCOL = '00030010'
CONFIG = Path.home() / '.config/tone-maintenance/ps5-wake.json'
SEARCH = f'SRCH * HTTP/1.1\ndevice-discovery-protocol-version:{PROTOCOL}\n\0'.encode()


def parse_state(data):
    lines = data.decode('ascii', errors='replace').strip('\0').splitlines()
    if not lines:
        return 'unknown'
    headers = dict(line.lower().split(':', 1) for line in lines[1:] if ':' in line)
    if headers.get('device-discovery-protocol-version', '').strip() != PROTOCOL:
        return 'unknown'
    status = lines[0].split()
    if len(status) < 2 or status[0] != 'HTTP/1.1':
        return 'unknown'
    return {'200': 'ready', '620': 'standby'}.get(status[1], 'unknown')


def bind_local(sock):
    for port in range(9303, 9320):
        try:
            sock.bind(("", port))
            return
        except OSError:
            continue
    raise OSError("No hay puerto local Remote Play disponible")


def discover(timeout=3):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        bind_local(sock)
        sock.settimeout(timeout)
        sock.sendto(SEARCH, (HOST, PORT))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(.01, deadline - time.monotonic()))
            try:
                data, peer = sock.recvfrom(4096)
            except socket.timeout:
                break
            if peer == (HOST, PORT):
                return parse_state(data)
    return 'unreachable'


def load_key(path=CONFIG):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('La credencial debe ser un archivo propio con permisos 600')
    config = json.loads(path.read_text())
    if config.get('host') != HOST:
        raise ValueError('La credencial no corresponde a la PS5 configurada')
    key = config.get('registration_key', '')
    if not isinstance(key, str) or not re.fullmatch(r'[0-9a-fA-F]{1,16}', key):
        raise ValueError('Falta una clave de registro Remote Play válida')
    return int(key, 16)


def wake_packet(key):
    return (f'WAKEUP * HTTP/1.1\nclient-type:vr\nauth-type:R\nmodel:w\n'
            f'app-type:r\nuser-credential:{key}\ndevice-discovery-protocol-version:{PROTOCOL}\n\0').encode()


def _run(wake=False, wait=60):
    state = discover()
    result = {'state': state, 'wake_sent': False}
    if not wake or state != 'standby':
        return result
    try:
        key = load_key()
    except FileNotFoundError:
        result['pending'] = 'Falta emparejar Remote Play en este Mac'
        return result
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        bind_local(sock)
        sock.sendto(wake_packet(key), (HOST, PORT))
    result['wake_sent'] = True
    deadline = time.monotonic() + min(max(wait, 0), 60)
    while time.monotonic() < deadline:
        time.sleep(min(2, max(0, deadline - time.monotonic())))
        result['state'] = discover(timeout=min(3, max(.01, deadline - time.monotonic())))
        if result['state'] == 'ready':
            return result
    result['pending'] = 'Despertar no confirmado; no se repite el envío'
    return result


def run(wake=False, wait=60):
    global _last_attempt
    with _wake_lock:
        if wake and time.monotonic() - _last_attempt < 90:
            return {'state': discover(), 'wake_sent': False, 'pending': 'Espera antes de repetir el encendido'}
        result = _run(wake, wait)
        if result.get('wake_sent'):
            _last_attempt = time.monotonic()
        return result


def ensure_console(wake=True):
    """Only call after the dashboard has authorized an explicit user action."""
    try:
        result = run(wake=wake, wait=30)
    except (OSError, ValueError) as exc:
        logging.warning('PS5 wake failed: %s errno=%s', type(exc).__name__, getattr(exc, 'errno', None))
        return {'error': 'No se pudo comprobar o despertar la PS5. Revisa el emparejamiento local.'}
    if result['state'] != 'ready':
        return {'error': result.get('pending') or 'La PS5 no responde. Si está apagada del todo, enciéndela manualmente.'}
    # Remote Play ready does not imply the Orbit payload survived rest mode.
    deadline = time.monotonic() + 8
    while True:
        try:
            with socket.create_connection((HOST, 34177), timeout=1):
                return {'console_woken': result['wake_sent']}
        except OSError:
            if time.monotonic() >= deadline:
                return {'error': 'La PS5 está encendida, pero Orbit no responde. Comprueba la cadena en la consola; no se ha vuelto a ejecutar el jailbreak.'}
            time.sleep(.5)


HELPER = Path.home() / 'Applications/TonePS5Wake.app'


def ensure_from_dashboard():
    """Launch the one-shot helper with its own macOS Local Network identity."""
    global _last_helper_wake
    if sys.platform != 'darwin':
        return ensure_console()
    check_only = bool(_last_helper_wake and time.monotonic() - _last_helper_wake < 90)
    if not HELPER.is_dir():
        return {'error': 'Instala el asistente local de encendido PS5 en el Mac.'}
    with tempfile.TemporaryDirectory(prefix='tone-ps5-wake-') as directory:
        fifo = Path(directory) / 'response'
        os.mkfifo(fifo, 0o600)
        fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
        try:
            command = ['/usr/bin/open', '-n', '-g', '-W', '--stdout', str(fifo),
                '--stderr', '/dev/null', str(HELPER)]
            if check_only:
                command += ['--args', '--check-only']
            result = subprocess.run(command, capture_output=True, timeout=55, check=False)
            data = json.loads(os.read(fd, 4096))
            if result.returncode or not isinstance(data, dict):
                raise ValueError('Invalid helper response')
            if data.get('error'):
                return {'error': str(data['error'])[:300]}
            if type(data.get('console_woken')) is not bool:
                raise ValueError('Invalid helper result')
            if data['console_woken']:
                _last_helper_wake = time.monotonic()
            return {'console_woken': data['console_woken']}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {'error': 'No se pudo consultar el asistente de PS5. Revisa su permiso de red local en el Mac.'}
        finally:
            os.close(fd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wake', action='store_true')
    parser.add_argument('--dashboard-helper', action='store_true')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(ensure_console(wake=not args.check_only) if args.dashboard_helper else run(args.wake), ensure_ascii=False))
    except (OSError, ValueError):
        print(json.dumps({'state': 'error', 'error': 'No se pudo comprobar la red o la credencial local'}))
        raise SystemExit(1)

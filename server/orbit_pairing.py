"""Password-gated, on-demand reading of the code visible in Orbit's desktop UI."""
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time

from request_security import allowed_mutation

READER = Path.home() / 'Applications/ToneOrbitCodeReader.app/Contents/MacOS/ToneOrbitCodeReader'
_lock = threading.Lock()
_failures = {}


def invoke_reader():
    # LaunchServices gives the reader its own macOS privacy identity, rather than
    # inheriting the background Python service's identity. The FIFO stores no
    # code on disk and lives in a directory accessible only to this user.
    with tempfile.TemporaryDirectory(prefix='tone-orbit-code-') as directory:
        fifo = Path(directory) / 'response'
        os.mkfifo(fifo, 0o600)
        descriptor = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
        try:
            app = READER.parent.parent.parent
            result = subprocess.run(
                ['/usr/bin/open', '-n', '-g', '-W', '--stdout', str(fifo),
                 '--stderr', '/dev/null', str(app)],
                capture_output=True, text=True, timeout=15, check=False)
            payload = os.read(descriptor, 4096).decode('utf-8')
            return subprocess.CompletedProcess([], result.returncode, payload)
        finally:
            os.close(descriptor)


def reveal_code(headers, client_address):
    if not allowed_mutation(headers) or headers.get('X-Orbit-Action') != 'reveal-code':
        return {'error': 'Solicitud de origen no autorizado.'}, 403
    expected = os.getenv('ORBIT_PAIR_CODE_PASSWORD', '')
    if len(expected) < 12:
        return {'error': 'Configura ORBIT_PAIR_CODE_PASSWORD con al menos 12 caracteres en .env.'}, 503
    # The reader runs only after authorization. Never cache a previous Orbit code.
    with _lock:
        now = time.monotonic()
        key = client_address[0]
        attempts, until = _failures.get(key, (0, 0))
        if until > now:
            return {'error': 'Demasiados intentos. Espera un minuto.'}, 429
        provided = headers.get('X-Orbit-Pair-Password', '')
        if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
            attempts += 1
            _failures[key] = (attempts if attempts < 5 else 0, now + 60 if attempts >= 5 else 0)
            if len(_failures) > 1024:
                _failures.clear()
                _failures[key] = (0, now + 60)
            return {'error': 'Contraseña incorrecta.'}, 403
        _failures.pop(key, None)
        if not READER.is_file():
            return {'error': 'Instala el lector local con scripts/install-orbit-code-reader.sh.'}, 503
        try:
            result = invoke_reader()
            data = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {'error': 'No se pudo consultar el lector local de Orbit.'}, 502
        if not isinstance(data, dict):
            return {'error': 'Respuesta inválida del lector local.'}, 502
        code = data.get('code')
        if result.returncode == 0 and isinstance(code, str) and re.fullmatch(r'[0-9]{6}', code):
            return {'code': code, 'display_seconds': 60}, 200
        errors = {
            'permission': 'Activa ToneOrbitCodeReader en Ajustes del Sistema → Privacidad y seguridad → Accesibilidad.',
            'not_running': 'Abre Orbit Zero en el Mac.',
            'not_visible': 'Orbit no muestra el código. Conecta la PS5 en Orbit y comprueba Consola → Cómo funciona en el Mac.',
        }
        return {'error': errors.get(data.get('error'), 'No se pudo leer el código vigente de Orbit.')}, 503

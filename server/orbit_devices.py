"""Revocable browser authorizations. Codes and Orbit sessions are never persisted."""
from contextlib import contextmanager
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sqlite3
import threading
import time

import orbit_pairing
from request_security import allowed_mutation, same_origin

COOKIE = 'toneOrbitDevice'
TTL = 30 * 86400
DB_PATH = Path.home() / '.local/share/emby_organizer/orbit-devices.sqlite3'
_lock = threading.RLock()
_sessions = {}
_retry = {}


def _owner():
    return hashlib.sha256(json.dumps([os.getenv(k, '') for k in (
        'DASHBOARD_USER', 'DASHBOARD_PASSWORD', 'ORBIT_PAIR_CODE_PASSWORD')]).encode()).hexdigest()


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(DB_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    os.chmod(DB_PATH, 0o600)
    db = sqlite3.connect(DB_PATH)
    db.execute('CREATE TABLE IF NOT EXISTS devices (digest TEXT PRIMARY KEY, owner TEXT, expires REAL)')
    try:
        with db:
            yield db
    finally:
        db.close()


def token(headers):
    try:
        jar = SimpleCookie(); jar.load(headers.get('Cookie', ''))
        value = jar[COOKIE].value if COOKIE in jar else ''
        return value if re.fullmatch(r'[a-f0-9]{64}', value) else ''
    except Exception:
        return ''


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def valid(value):
    if not value:
        return False
    with _lock, _db() as db:
        row = db.execute('SELECT expires FROM devices WHERE digest=? AND owner=?',
                         (_digest(value), _owner())).fetchone()
        return bool(row and row[0] > time.time())


def cookie_header(headers):
    value = token(headers)
    if value:
        with _lock:
            return _sessions.get(_digest(value), '') if valid(value) else ''
    try:
        jar = SimpleCookie(); jar.load(headers.get('Cookie', ''))
        value = jar['orbitZero'].value if 'orbitZero' in jar else ''
        return 'orbitZero=' + value if re.fullmatch(r'[a-f0-9]{64}', value) else ''
    except Exception:
        return ''


def accept_manual_session(headers, cookie):
    """Keep manual pairing usable without exposing broker sessions to clients."""
    value = token(headers)
    with _lock:
        if not valid(value):
            return False
        try:
            jar = SimpleCookie(); jar.load(cookie)
            session = jar['orbitZero'].value if 'orbitZero' in jar else ''
            if re.fullmatch(r'[a-f0-9]{64}', session):
                _sessions[_digest(value)] = 'orbitZero=' + session
                _retry.pop(_digest(value), None)
        except Exception:
            pass
        return True


def _pair(code):
    connection = http.client.HTTPConnection('127.0.0.1', 34179, timeout=10)
    try:
        connection.request('POST', '/api/pair', json.dumps({'code': code}), {
            'Origin': 'http://127.0.0.1:34179', 'X-Orbit-Zero': '1',
            'Content-Type': 'application/json'})
        response = connection.getresponse()
        response.read(4096)
        if response.status != 200:
            raise ValueError('Pairing rejected')
        jar = SimpleCookie(); jar.load(response.getheader('Set-Cookie', ''))
        value = jar['orbitZero'].value if 'orbitZero' in jar else ''
        if not re.fullmatch(r'[a-f0-9]{64}', value):
            raise ValueError('Invalid session')
        return 'orbitZero=' + value
    finally:
        connection.close()


def recover(headers):
    """Called only after Orbit explicitly reports needsPairing; one attempt/minute."""
    if headers.get('Sec-Fetch-Site', '').lower() in ('cross-site', 'same-site'):
        return False
    if headers.get('Origin') is not None and not same_origin(headers):
        return False
    value = token(headers)
    with _lock:
        if not valid(value):
            return False
        key = _digest(value)
        if _retry.get(key, 0) > time.monotonic():
            return False
        _retry[key] = time.monotonic() + 60
        try:
            result = orbit_pairing.invoke_reader()
            data = json.loads(result.stdout)
            code = data.get('code') if isinstance(data, dict) else None
            if result.returncode or not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
                return False
            _sessions[key] = _pair(code)
            return True
        except (OSError, ValueError, http.client.HTTPException, subprocess.TimeoutExpired):
            return False


def action(headers, address, forget=False):
    if not allowed_mutation(headers):
        return {'error': 'Origen no autorizado'}, 403, None
    with _lock:
        if forget:
            value = token(headers)
            if value:
                key = _digest(value)
                with _db() as db:
                    db.execute('DELETE FROM devices WHERE digest=?', (key,))
                _sessions.pop(key, None); _retry.pop(key, None)
            return {'remembered': False}, 200, f'{COOKIE}=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Strict'
        if headers.get('X-Orbit-Action') != 'remember-device':
            return {'error': 'Acción no autorizada'}, 403, None
        authorized = dict(headers)
        authorized['X-Orbit-Action'] = 'reveal-code'
        result, status = orbit_pairing.reveal_code(authorized, address)
        if status != 200:
            return result, status, None
        try:
            session = _pair(result['code'])
        except (OSError, ValueError, http.client.HTTPException):
            return {'error': 'Orbit no aceptó la vinculación. Comprueba que está conectado.'}, 502, None
        value = secrets.token_hex(32)
        key = _digest(value)
        with _db() as db:
            db.execute('DELETE FROM devices WHERE expires<=? OR owner<>?', (time.time(), _owner()))
            if db.execute('SELECT COUNT(*) FROM devices').fetchone()[0] >= 128:
                return {'error': 'Se ha alcanzado el límite de dispositivos.'}, 409, None
            active = {row[0] for row in db.execute('SELECT digest FROM devices')}
            for cache in (_sessions, _retry):
                for stale in set(cache) - active:
                    cache.pop(stale, None)
            old = token(headers)
            if old:
                db.execute('DELETE FROM devices WHERE digest=?', (_digest(old),))
                _sessions.pop(_digest(old), None); _retry.pop(_digest(old), None)
            db.execute('INSERT INTO devices VALUES (?,?,?)', (key, _owner(), time.time() + TTL))
        _sessions[key] = session
        return {'remembered': True, 'days': 30}, 200, f'{COOKIE}={value}; Max-Age={TTL}; Path=/; HttpOnly; Secure; SameSite=Strict'

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import orbit_devices as devices
import orbit_pairing

class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'devices.sqlite3'
        p = patch.object(devices, 'DB_PATH', self.path); p.start(); self.addCleanup(p.stop)
        p = patch.dict(os.environ, {'DASHBOARD_USER': 'test', 'DASHBOARD_PASSWORD': 'test-password',
                                   'ORBIT_PAIR_CODE_PASSWORD': 'pair-password-test'}); p.start(); self.addCleanup(p.stop)
        devices._sessions.clear(); devices._retry.clear(); orbit_pairing._failures.clear()
        self.headers = {'X-Dashboard-Action': 'write', 'X-Orbit-Action': 'remember-device',
                        'X-Orbit-Pair-Password': 'pair-password-test'}

    def register(self):
        with patch.object(orbit_pairing, 'reveal_code', return_value=({'code': '123456'}, 200)), patch.object(devices, '_pair', return_value='orbitZero=' + 'b'*64):
            result, status, cookie = devices.action(self.headers, ('127.0.0.1', 1))
        self.assertEqual(status, 200)
        value = cookie.split(';')[0].split('=')[1]
        self.headers['Cookie'] = cookie.split(';')[0]
        return value, cookie

    def test_hash_only_private_storage_and_secure_cookie(self):
        value, cookie = self.register()
        self.assertTrue(devices.valid(value))
        self.assertNotIn(value.encode(), self.path.read_bytes())
        self.assertNotIn(b'123456', self.path.read_bytes())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        for flag in ('Secure', 'HttpOnly', 'SameSite=Strict', 'Max-Age=2592000'):
            self.assertIn(flag, cookie)

    def test_password_failure_never_pairs_or_writes(self):
        self.headers['X-Orbit-Pair-Password'] = 'wrong'
        with patch.object(devices, '_pair') as pair:
            self.assertEqual(devices.action(self.headers, ('127.0.0.1', 1))[1], 403)
            pair.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_cross_origin_rejected(self):
        self.headers.update(Origin='https://evil.test', Host='dashboard.test')
        with patch.object(orbit_pairing, 'invoke_reader') as reader:
            self.assertEqual(devices.action(self.headers, ('127.0.0.1', 1))[1], 403)
            reader.assert_not_called()

    def test_revocation_and_expiry(self):
        value, _ = self.register()
        self.assertTrue(devices.cookie_header(self.headers))
        devices.action(self.headers, ('127.0.0.1', 1), forget=True)
        self.assertFalse(devices.valid(value)); self.assertFalse(devices.cookie_header(self.headers))
        value, _ = self.register()
        with devices._db() as db:
            db.execute('UPDATE devices SET expires=?', (time.time()-1,))
        self.assertFalse(devices.valid(value))

    def test_password_rotation_revokes(self):
        value, _ = self.register()
        with patch.dict(os.environ, {'ORBIT_PAIR_CODE_PASSWORD': 'replacement-password'}):
            self.assertFalse(devices.valid(value))
            self.assertFalse(devices.cookie_header(self.headers))

    def test_restart_recovers_fresh_session_without_storing_code(self):
        value, _ = self.register(); devices._sessions.clear()
        self.assertEqual(devices.cookie_header(self.headers), '')
        with patch.object(orbit_pairing, 'invoke_reader', return_value=subprocess.CompletedProcess([], 0, '{"code":"654321"}')) as reader, patch.object(devices, '_pair', return_value='orbitZero='+'c'*64) as pair:
            self.assertTrue(devices.recover(self.headers))
            pair.assert_called_once_with('654321'); reader.assert_called_once()
            self.assertFalse(devices.recover(self.headers))
        self.assertEqual(devices.cookie_header(self.headers), 'orbitZero='+'c'*64)

    def test_invalid_or_cross_origin_never_reads(self):
        for headers in ({}, {'Cookie': devices.COOKIE+'='+'a'*64}):
            with patch.object(orbit_pairing, 'invoke_reader') as reader:
                self.assertFalse(devices.recover(headers)); reader.assert_not_called()
        self.register(); self.headers['Sec-Fetch-Site'] = 'cross-site'
        with patch.object(orbit_pairing, 'invoke_reader') as reader:
            self.assertFalse(devices.recover(self.headers)); reader.assert_not_called()

    def test_concurrent_recovery_reads_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        self.register()
        with patch.object(orbit_pairing, 'invoke_reader', return_value=subprocess.CompletedProcess([], 0, '{"code":"654321"}')) as reader, patch.object(devices, '_pair', return_value='orbitZero='+'c'*64):
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: devices.recover(self.headers), range(4)))
            self.assertEqual(sum(results), 1)
            reader.assert_called_once()

    def test_failed_reader_backoff_and_manual_fallback(self):
        self.register()
        with patch.object(orbit_pairing, 'invoke_reader', return_value=subprocess.CompletedProcess([], 1, '{"error":"not_visible"}')) as reader:
            self.assertFalse(devices.recover(self.headers)); self.assertFalse(devices.recover(self.headers))
            reader.assert_called_once()
        self.assertEqual(devices.cookie_header({'Cookie':'other=secret; orbitZero='+'d'*64}), 'orbitZero='+'d'*64)

    def test_manual_pairing_replaces_stale_broker_session(self):
        value, _ = self.register()
        self.assertTrue(devices.accept_manual_session(self.headers, 'orbitZero='+'e'*64+'; Path=/'))
        self.assertEqual(devices.cookie_header(self.headers), 'orbitZero='+'e'*64)
        devices.action(self.headers, ('127.0.0.1',1), forget=True)
        self.assertFalse(devices.accept_manual_session(self.headers, 'orbitZero='+'e'*64))

    def test_failed_pair_never_issues_authorization(self):
        with patch.object(orbit_pairing, 'reveal_code', return_value=({'code':'123456'},200)), patch.object(devices, '_pair', side_effect=OSError):
            result, status, cookie = devices.action(self.headers, ('127.0.0.1',1))
        self.assertEqual(status,502); self.assertIsNone(cookie); self.assertFalse(self.path.exists())

class PairTransportTests(unittest.TestCase):
    def test_pair_uses_fixed_loopback_origin_no_dashboard_credentials(self):
        from unittest.mock import MagicMock
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 200
        response.getheader.return_value = 'orbitZero=' + 'a'*64 + '; HttpOnly; Path=/'
        with patch.object(devices.http.client, 'HTTPConnection', return_value=connection) as factory:
            self.assertEqual(devices._pair('123456'), 'orbitZero='+'a'*64)
        factory.assert_called_once_with('127.0.0.1', 34179, timeout=10)
        args = connection.request.call_args.args
        self.assertEqual(args[:2], ('POST','/api/pair'))
        self.assertEqual(json.loads(args[2]), {'code':'123456'})
        self.assertNotIn('Authorization', args[3])
        self.assertEqual(args[3]['Origin'], 'http://127.0.0.1:34179')
        connection.close.assert_called_once()

    def test_proxy_does_not_forward_passwords_or_device_cookie(self):
        from types import SimpleNamespace
        from orbit_dashboard_proxy import _proxy_headers
        headers={'Authorization':'Basic secret', 'Cookie':'unrelated=secret; orbitZero='+'b'*64,
                 'X-Orbit-Pair-Password':'secret', 'X-Orbit-Control-Password':'secret'}
        forwarded=_proxy_headers(SimpleNamespace(headers=headers),'zero','127.0.0.1',34179)
        self.assertEqual(forwarded['Cookie'],'orbitZero='+'b'*64)
        self.assertNotIn('secret',repr(forwarded))

    def test_proxy_retries_state_once_after_recovery(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        import io
        import orbit_dashboard_proxy as proxy
        handler = MagicMock()
        handler.headers = {'Cookie': devices.COOKIE+'='+'a'*64}
        handler.command = 'GET'; handler.rfile=io.BytesIO(); handler.wfile=io.BytesIO()
        first=MagicMock(); first.status=200; first.read.return_value=b'{"needsPairing":true}'
        second=MagicMock(); second.status=200; second.read.return_value=b'{"paired":true}'
        for response in (first,second):
            response.getheader.side_effect=lambda key,default='': 'application/json' if key=='Content-Type' else default
            response.getheaders.return_value=[]
        c1=MagicMock(); c1.getresponse.return_value=first
        c2=MagicMock(); c2.getresponse.return_value=second
        with patch.object(proxy.http.client,'HTTPConnection',side_effect=[c1,c2]), patch.object(devices,'recover',return_value=True) as recover, patch.object(devices,'cookie_header',return_value='orbitZero='+'c'*64):
            proxy._http(handler,'zero','127.0.0.1',34179,'/api/state')
        recover.assert_called_once_with(handler.headers)
        self.assertEqual(handler.wfile.getvalue(),b'{"paired":true}')
        self.assertEqual(c2.request.call_args.kwargs['headers']['Cookie'],'orbitZero='+'c'*64)

import http.client
import importlib.util
import io
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import download_security as downloads
from request_security import allowed_mutation, same_origin

PUBLIC_DNS = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]


class DownloadSecurityTests(unittest.TestCase):
    def test_internal_and_special_addresses_rejected(self):
        for host in ('127.0.0.1', '10.0.0.1', '192.168.0.1', '169.254.169.254',
                     '0.0.0.0', '::1', 'fc00::1', '::ffff:127.0.0.1', '224.0.0.1',
                     '2002:c0a8:0101::1'):
            with self.subTest(host=host), mock.patch.object(downloads.socket, 'getaddrinfo',
                    return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', (host, 80))]):
                with self.assertRaises(downloads.UnsafeDownload):
                    downloads.validate_url('http://example.com/file')

    def test_unsafe_syntax_rejected_before_dns(self):
        for url in ('file:///etc/passwd', 'http://user:pass@example.com/',
                    'http://example.com:34179/', 'http://example.com/\r\nX:1',
                    'http://example.com\\@localhost/', 'http://example.com:bad/'):
            with self.subTest(url=url), mock.patch.object(downloads.socket, 'getaddrinfo') as dns:
                with self.assertRaises(downloads.UnsafeDownload): downloads.validate_url(url)
                dns.assert_not_called()

    def test_mixed_dns_answers_rejected(self):
        with mock.patch.object(downloads.socket, 'getaddrinfo', return_value=PUBLIC_DNS +
                [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 443))]):
            with self.assertRaises(downloads.UnsafeDownload): downloads.validate_url('https://example.com/')

    def test_connection_is_pinned(self):
        conn = mock.MagicMock()
        conn.getresponse.return_value.status = 200
        with mock.patch.object(downloads.socket, 'getaddrinfo', return_value=PUBLIC_DNS), \
             mock.patch.object(downloads.socket, 'create_connection') as connect, \
             mock.patch.object(downloads.http.client, 'HTTPConnection', return_value=conn):
            response = downloads.open_public('http://example.com/file')
            connect.assert_called_once_with(('93.184.216.34', 80), timeout=30)
            self.assertEqual(response.public_url, 'http://example.com/file')

    def test_redirect_to_private_network_never_connects(self):
        conn = mock.MagicMock()
        conn.getresponse.return_value.status = 302
        conn.getresponse.return_value.getheader.return_value = 'http://127.0.0.1/private'
        with mock.patch.object(downloads.socket, 'getaddrinfo', side_effect=[PUBLIC_DNS,
                    [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 80))]]), \
             mock.patch.object(downloads.socket, 'create_connection') as connect, \
             mock.patch.object(downloads.http.client, 'HTTPConnection', return_value=conn):
            with self.assertRaises(downloads.UnsafeDownload): downloads.open_public('http://example.com/')
            self.assertEqual(connect.call_count, 1)

    def test_tls_uses_original_hostname(self):
        conn = mock.MagicMock(); conn.getresponse.return_value.status = 200
        with mock.patch.object(downloads.socket, 'getaddrinfo', return_value=PUBLIC_DNS), \
             mock.patch.object(downloads.socket, 'create_connection') as connect, \
             mock.patch.object(downloads.ssl, 'create_default_context') as context, \
             mock.patch.object(downloads.http.client, 'HTTPConnection', return_value=conn):
            downloads.open_public('https://example.com/')
            context.return_value.wrap_socket.assert_called_once_with(connect.return_value, server_hostname='example.com')

    def test_resume_and_server_ignoring_range(self):
        for status, content_range, expected in ((206, 'bytes 3-5/6', b'abcdef'), (200, None, b'def')):
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / 'file'; target.write_bytes(b'abc')
                response = mock.MagicMock(status=status)
                response.getheader.side_effect = lambda name, default=None: {'Content-Range': content_range, 'Content-Length': '3'}.get(name, default)
                response.read.side_effect = [b'def', b'']
                with mock.patch.object(downloads, 'open_public', return_value=response) as opened:
                    downloads.download_public('https://example.com/', target)
                    self.assertEqual(target.read_bytes(), expected)
                    self.assertEqual(opened.call_args.kwargs['headers']['Range'], 'bytes=3-')

    def test_wrong_partial_response_does_not_modify_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'file'; target.write_bytes(b'abc')
            response = mock.MagicMock(status=206)
            response.getheader.return_value = 'bytes 0-2/6'
            with mock.patch.object(downloads, 'open_public', return_value=response):
                with self.assertRaises(OSError): downloads.download_public('https://example.com/', target)
            self.assertEqual(target.read_bytes(), b'abc')


class OriginTests(unittest.TestCase):
    def test_browser_and_native(self):
        self.assertTrue(allowed_mutation({'Host': 'dashboard.test', 'Origin': 'https://dashboard.test'}))
        self.assertTrue(allowed_mutation({'X-Dashboard-Action': 'write'}))
        self.assertFalse(allowed_mutation({}))
        self.assertFalse(allowed_mutation({'Origin': 'null', 'X-Dashboard-Action': 'write'}))
        self.assertFalse(allowed_mutation({'Sec-Fetch-Site': 'cross-site', 'X-Dashboard-Action': 'write'}))

    def test_exact_origin_and_malformed_values(self):
        for origin in ('https://evil.test', 'https://dashboard.test.evil.test',
                       'https://dashboard.test:444', 'https://user@dashboard.test',
                       'https://dashboard.test/path', 'https://dashboard.test:bad'):
            with self.subTest(origin=origin):
                self.assertFalse(same_origin({'Host': 'dashboard.test', 'Origin': origin}))
        self.assertTrue(same_origin({'Host': 'dashboard.test:443', 'Origin': 'https://dashboard.test'}))


class UpdateTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('updater', ROOT / 'scripts/update_macos.py')
        self.updater = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, 'argv', ['update_macos.py']): spec.loader.exec_module(self.updater)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'source'; self.source.mkdir()
        self.target = Path(self.tmp.name) / 'target'; self.target.mkdir()
        (self.target / '.env').write_text('preserve')
        self.updater.FILES = ['first.py', 'second.py']
        for rel in self.updater.FILES: (self.source / rel).write_text('value = 2\n')
        (self.target / 'first.py').write_text('value = 1\n')

    def test_invalid_package_leaves_installation_untouched(self):
        (self.source / 'second.py').write_text('invalid !')
        with self.assertRaises(SyntaxError): self.updater.apply_update(self.source, self.target)
        self.assertEqual((self.target / 'first.py').read_text(), 'value = 1\n')

    def test_replace_failure_rolls_back(self):
        replace = self.updater.os.replace
        def fail_second(src, dst):
            if Path(dst).name == 'second.py': raise OSError('simulated')
            return replace(src, dst)
        with mock.patch.object(self.updater.os, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError): self.updater.apply_update(self.source, self.target)
        self.assertEqual((self.target / 'first.py').read_text(), 'value = 1\n')
        self.assertFalse((self.target / 'second.py').exists())
        self.assertEqual((self.target / '.env').read_text(), 'preserve')

    def test_update_preserves_env_and_backup(self):
        backup = self.updater.apply_update(self.source, self.target)
        self.assertEqual((backup / 'first.py').read_text(), 'value = 1\n')
        self.assertEqual((self.target / 'first.py').read_text(), 'value = 2\n')
        self.assertEqual((self.target / '.env').read_text(), 'preserve')

class DashboardEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('hardening_dashboard', ROOT / 'scripts/log-viewer.py')
        cls.dashboard = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.dashboard
        spec.loader.exec_module(cls.dashboard)

    def handler(self, path, headers):
        handler = object.__new__(self.dashboard.Handler)
        handler.path = path
        handler.headers = headers
        handler.client_address = ('127.0.0.1', 1234)
        handler._require_auth = mock.Mock(return_value=True)
        handler.send_bytes = mock.Mock()
        handler.rfile = io.BytesIO(b'{"url":"http://127.0.0.1/private"}')
        handler.command = 'POST'
        return handler

    def test_cross_origin_never_queues_or_writes(self):
        for path in ('/api/download', '/api/torrent', '/api/orbit/start', '/orbit-bridge/zero/api/action'):
            handler = self.handler(path, {'Host': 'dashboard.test', 'Origin': 'https://evil.test'})
            with mock.patch.object(self.dashboard, 'queue_download_request') as queue, \
                 mock.patch.object(self.dashboard, 'save_torrent_bytes') as save:
                handler.do_POST()
                self.assertEqual(handler.send_bytes.call_args.args[2], 403)
                queue.assert_not_called(); save.assert_not_called()

    def test_missing_origin_and_action_never_queues(self):
        handler = self.handler('/api/download', {})
        handler.do_POST()
        self.assertEqual(handler.send_bytes.call_args.args[2], 403)

    def test_native_private_download_rejected(self):
        data = b'{"url":"http://127.0.0.1/private"}'
        handler = self.handler('/api/download', {'X-Dashboard-Action': 'write', 'Content-Length': str(len(data))})
        with mock.patch.object(self.dashboard, 'TELEGRAM_CHAT_ID', 'test'), \
             mock.patch.object(self.dashboard, 'queue_download_request') as queue, \
             mock.patch.object(downloads.socket, 'getaddrinfo', return_value=[
                 (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 80))]):
            handler.do_POST()
            self.assertEqual(handler.send_bytes.call_args.args[2], 400)
            queue.assert_not_called()

    def test_failed_authentication_stops_before_mutation(self):
        handler = self.handler('/api/download', {'X-Dashboard-Action': 'write'})
        handler._require_auth.return_value = False
        handler.do_POST()
        handler.send_bytes.assert_not_called()

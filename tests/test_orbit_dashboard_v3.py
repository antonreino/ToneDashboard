import base64
import http.server
import importlib.util
import os
from pathlib import Path
import threading
import unittest
from unittest import mock
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
proxy=load('orbit_dashboard_proxy')
control=load('orbit_dashboard_control')
DASHBOARD_USER='tester'
DASHBOARD_PASSWORD='test-pass'

class FakeOrbit(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/':
            data=b'<html><head><script src="/assets/app.js"></script></head><body><img src="/art/cover.jpg"></body></html>'
            ct='text/html';self.send_response(200)
            self.send_header('Content-Security-Policy',"default-src 'self'; frame-ancestors 'none'")
            self.send_header('X-Frame-Options','DENY')
        elif self.path=='/art/cover.jpg':
            data=b'fake-image';ct='image/jpeg';self.send_response(200)
        elif self.path=='/api/pair':
            data=b'{"pair":"demo"}';ct='application/json';self.send_response(200)
        else:
            data=b'not-found';ct='text/plain';self.send_response(404)
        self.send_header('Content-Type',ct);self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
class FakeDashboard(http.server.BaseHTTPRequestHandler):
    def _require_auth(self):
        correct='Basic '+base64.b64encode(b'tester:test-pass').decode()
        if self.headers.get('Authorization')!=correct:
            self.send_error(401);return False
        return True
    def do_GET(self):
        if not proxy.serve(self):self.send_error(404)
    def log_message(self,*args):pass
class OrbitV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.up=http.server.ThreadingHTTPServer(('127.0.0.1',0),FakeOrbit)
        cls.down=http.server.ThreadingHTTPServer(('127.0.0.1',0),FakeDashboard)
        cls.oldport=proxy.ZERO_PORT;proxy.ZERO_PORT=cls.up.server_address[1]
        cls.servers=(cls.up,cls.down)
        for server in cls.servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        proxy.ZERO_PORT=cls.oldport
        for server in cls.servers:server.shutdown();server.server_close()
    def fetch(self,path,auth=True):
        h={}
        if auth:h['Authorization']='Basic '+base64.b64encode(b'tester:test-pass').decode()
        try:return urlopen(Request('http://127.0.0.1:'+str(self.down.server_address[1])+path,headers=h),timeout=3)
        except HTTPError as err:return err
    def test_rewrite_html_images(self):
        with self.fetch('/orbit-bridge/zero/') as resp:
            html=resp.read().decode()
            self.assertIn('src="/orbit-bridge/zero/art/cover.jpg"',html)
            self.assertIn('src="/orbit-bridge/zero/__bridge.js"',html)
            self.assertNotIn('X-Frame-Options',resp.headers)
    def test_image_caching(self):
        with self.fetch('/orbit-bridge/zero/art/cover.jpg') as resp:
            self.assertEqual(resp.read(),b'fake-image')
            self.assertIn('private',resp.headers['Cache-Control'])
    def test_pairing_not_cached(self):
        with self.fetch('/orbit-bridge/zero/api/pair') as resp:self.assertEqual(resp.headers['Cache-Control'],'no-store')
    def test_no_ps5_proxy(self):
        self.assertIsNone(proxy._target('/orbit-bridge/ps5/'))
        self.assertIsNone(proxy._target('/orbit-bridge/evil.example/'))
    def test_requires_dashboard_password(self):
        with self.fetch('/orbit-bridge/zero/',False) as resp:self.assertEqual(resp.status,401)
    def test_start_wrong_password(self):
        h={'Host':'dashboard.local','Origin':'http://dashboard.local','Content-Type':'application/json',
           'X-Orbit-Action':'start','X-Orbit-Control-Password':'wrong'}
        with mock.patch.dict(os.environ,{'ORBIT_CONTROL_PASSWORD':'secret-123456789'}):
            _,status=control.start_app(h,('127.0.0.1',0))
        self.assertEqual(status,403)
    def test_cross_origin_blocked(self):
        h={'Host':'dashboard.local','Origin':'https://evil.example','Content-Type':'application/json',
           'X-Orbit-Action':'start','X-Orbit-Control-Password':'secret-123456789'}
        with mock.patch.dict(os.environ,{'ORBIT_CONTROL_PASSWORD':'secret-123456789'}):
            _,status=control.start_app(h,('127.0.0.1',0))
        self.assertEqual(status,403)
    def test_start_uses_fixed_app_not_client_command(self):
        h={'Host':'dashboard.local','Origin':'http://dashboard.local','Content-Type':'application/json',
           'X-Orbit-Action':'start','X-Orbit-Control-Password':'secret-123456789','App':'/bin/sh'}
        with mock.patch.dict(os.environ,{'ORBIT_CONTROL_PASSWORD':'secret-123456789'}),\
             mock.patch.object(control,'running',return_value=False),\
             mock.patch.object(control.sys,'platform','darwin'),\
             mock.patch.object(control,'MAC_APP',type('MockApp',(),{'is_dir':lambda self:True,'__str__':lambda self:'/Applications/Orbit Zero.app'})()),\
             mock.patch.object(control.subprocess,'Popen') as launch:
            _,status=control.start_app(h,('127.0.0.1',0))
        self.assertEqual(status,202)
        self.assertEqual(launch.call_args[0][0][:4],['/usr/bin/open','-g','-a','/Applications/Orbit Zero.app'])
    def test_legacy_removed_frontend(self):
        s=(ROOT/'scripts/log-viewer.py').read_text()
        self.assertNotIn('ps5StoreState',s)
        self.assertNotIn('orbitModeLegacy',s)
        self.assertNotIn('/api/ps5/catalog',s)
        self.assertIn('/api/orbit/start',s)
        self.assertNotIn("method:'HEAD'",s)
    def test_dynamic_image_shim(self):
        js=(ROOT/'orbit_bridge_shim.js').read_text()
        self.assertIn("patchProperty(window.HTMLImageElement, 'src'",js)
        self.assertIn('MutationObserver',js)

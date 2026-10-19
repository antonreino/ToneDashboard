import base64
import http.client
import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from runtime_support import BoundedHTTPServer

class OperationalHTTPTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('operational_http',Path(__file__).resolve().parents[1]/'scripts/log-viewer.py');self.viewer=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.viewer)
        self.viewer.DASHBOARD_USER='test';self.viewer.DASHBOARD_PASSWORD='only-test'
        self.server=BoundedHTTPServer(('127.0.0.1',0),self.viewer.Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,method,path,body=b'{}',**headers):
        h={'Authorization':'Basic '+base64.b64encode(b'test:only-test').decode(),'X-Dashboard-Action':'write'};h.update(headers)
        conn=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        try:
            conn.request(method,path,body,h);r=conn.getresponse();return r.status,dict(r.getheaders()),r.read()
        finally:conn.close()
    def test_operations_need_auth_origin_and_bounded_object_body(self):
        with patch('operations.post',return_value=({'ok':True},202)) as post:
            for path in ['/api/downloads/control','/api/organizer/review','/api/deals/preferences','/api/organizer/rules/remove']:
                self.assertEqual(self.request('POST',path,Authorization='')[0],401)
                self.assertEqual(self.request('POST',path,Origin='https://evil.test')[0],403)
                self.assertEqual(self.request('POST',path,b'[]')[0],400)
                self.assertEqual(self.request('POST',path,b'not-json')[0],400)
                self.assertEqual(self.request('POST',path,**{'Content-Length':'4097'})[0],400)
            post.assert_not_called()
            self.assertEqual(self.request('POST','/api/downloads/control',b'{"id":1,"action":"pause"}')[0],202)
            post.assert_called_once()
    def test_isolated_host_cannot_read_dashboard_even_with_dashboard_credentials(self):
        with patch.dict(os.environ,{'DASHBOARD_PUBLIC_ORIGIN':'https://dashboard.test','ORBIT_ISOLATED_ORIGIN':'https://orbit.test'}):
            status,headers,_=self.request('GET','/api/dashboard',Host='orbit.test')
            self.assertEqual(status,403);self.assertNotIn('WWW-Authenticate',headers)
            self.assertEqual(self.request('POST','/api/downloads/control',Host='orbit.test')[0],403)
    def test_html_security_headers_preserve_current_embed(self):
        status,headers,body=self.request('GET','/')
        self.assertEqual(status,200);self.assertEqual(headers['X-Content-Type-Options'],'nosniff');self.assertIn("frame-src 'self'",headers['Content-Security-Policy']);self.assertIn(b'operationsDialog',body)
    def test_diagnostics_deny_unauthenticated_export(self):
        with patch('operations.get',return_value=({'ok':True},200)) as get:
            self.assertEqual(self.request('GET','/api/diagnostics',Authorization='')[0],401);get.assert_not_called()

    def test_calendar_feed_is_scoped_and_subscription_requires_auth(self):
        import anime_calendar
        import tempfile
        with tempfile.TemporaryDirectory() as folder, patch.object(anime_calendar,'ROOT',Path(folder)):
            self.assertEqual(self.request('POST','/api/anime-calendar/subscribe',Authorization='')[0],401)
            self.assertEqual(self.request('POST','/api/anime-calendar/subscribe',Origin='https://evil.test')[0],403)
            self.assertEqual(self.request('GET','/api/anime-calendar',Authorization='')[0],401)
            status,_,body=self.request('POST','/api/anime-calendar/subscribe')
            self.assertEqual(status,200);path=json.loads(body)['path']
            status,headers,body=self.request('GET',path,Authorization='')
            self.assertEqual(status,200);self.assertIn('text/calendar',headers['Content-Type'])
            self.assertIn(b'BEGIN:VCALENDAR',body);self.assertNotIn(b'only-test',body)
            self.assertEqual(self.request('GET','/calendar/anime/wrong.ics',Authorization='')[0],404)
            self.request('POST','/api/anime-calendar/subscribe?rotate=1')
            self.assertEqual(self.request('GET',path,Authorization='')[0],404)

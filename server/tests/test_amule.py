import hashlib
import os
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from amule_ec import Tag,encode_tag,decode_packet,ECClient,AmuleError,MAX_PACKET
from amule_dashboard import AmuleDashboard,RequestError,files,handle
HASH='0123456789abcdef0123456789abcdef'
def filetag(name='Example <title>.mkv',sources=7):
    return Tag(0x700,123,[Tag(0x31e,bytes.fromhex(HASH)),Tag(0x301,name),Tag(0x303,2**34),Tag(0x30a,sources),Tag(0x306,2**33)])
class CodecTests(unittest.TestCase):
    def test_nested_unicode_hash_and_large_integer_roundtrip(self):
        item=filetag('Título muy largo '+('x'*300))
        packet=b'\x28\x00\x01'+encode_tag(item)
        op,tags=decode_packet(packet);self.assertEqual(op,0x28);self.assertEqual(tags,[item])
        f=files(tags)[0];self.assertEqual(f['hash'],HASH);self.assertEqual(f['size'],2**34);self.assertEqual(f['progress'],50)
    def test_malformed_packets_and_depth_rejected(self):
        for raw in (b'',b'\x28',b'\x28\x00\x01',b'\x01\x00\x00junk',b'\x28\x00\x01'+struct.pack('!HBI',1,2,0)+b'\0\0'):
            with self.subTest(raw=raw),self.assertRaises(AmuleError):decode_packet(raw)
        item=Tag(1,1)
        for _ in range(15):item=Tag(1,1,[item])
        with self.assertRaises(AmuleError):decode_packet(b'\x01\x00\x01'+encode_tag(item))
    def test_files_without_hash_are_not_actionable(self):
        self.assertEqual(files([Tag(0x700,22,[Tag(0x301,'no hash')])]),[])
    def test_bounded_response_and_socket_close_on_auth_error(self):
        sock=mock.Mock();sock.recv.side_effect=[struct.pack('!II',0x20,MAX_PACKET+1)]
        with mock.patch('amule_ec.socket.create_connection',return_value=sock),self.assertRaises(AmuleError):
            with ECClient('a'*32):pass
        sock.close.assert_called_once()
    def test_salted_auth_uses_loopback_and_never_sends_plain_secret(self):
        replies=[]
        for op,tags in [(0x4f,[Tag(11,123456)]),(4,[])]:
            body=bytes([op])+struct.pack('!H',len(tags))+b''.join(encode_tag(t) for t in tags)
            replies.extend([struct.pack('!II',0x20,len(body)),body])
        sock=mock.Mock();sock.recv.side_effect=replies
        with mock.patch('amule_ec.socket.create_connection',return_value=sock) as connect:
            with ECClient('a'*32):pass
        connect.assert_called_once_with(('127.0.0.1',4712),timeout=4)
        sent=sock.sendall.call_args_list[1].args[0]
        expected=hashlib.md5(('a'*32+hashlib.md5(b'1E240').hexdigest()).encode()).digest()
        self.assertIn(expected,sent);self.assertNotIn(b'a'*32,sent);sock.close.assert_called_once()
class Core:
    def __init__(self):self.calls=[];self.queue=[];self.found=[filetag()]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def request(self,op,tags=()):
        self.calls.append((op,tags))
        if op==0x0a:return 0xc,[Tag(0x201,100),Tag(0x21b,200)]
        if op==0x0d:return 0x1f,self.queue
        if op==0x28:return 0x28,self.found
        if op==0x29:return 0x29,[Tag(0x708,50)]
        if op==0x2a:
            self.queue=[filetag()];return 6,[]
        return 1,[]
class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.core=Core();self.now=100;self.b=AmuleDashboard(lambda:self.core,clock=lambda:self.now)
    def start(self):return self.b.search({'query':'Example','network':'kad'})
    def test_search_snapshot_then_exact_hash_download_and_duplicate(self):
        sid=self.start()['search_id'];snap=self.b.snapshot();self.assertEqual(len(snap['results']),1)
        self.b.download({'hash':HASH,'search_id':sid})
        tag=next(tags[0] for op,tags in self.core.calls if op==0x2a)
        self.assertEqual(tag.value,bytes.fromhex(HASH));self.assertEqual(tag.get(0x30f),0)
        self.assertTrue(self.b.download({'hash':HASH,'search_id':sid})['already_queued'])
        self.assertEqual(sum(op==0x2a for op,_ in self.core.calls),1)
    def test_stale_search_and_removed_results_never_download(self):
        sid=self.start()['search_id'];self.b.snapshot()
        for body in [{'hash':HASH,'search_id':'old'},{'hash':'f'*32,'search_id':sid},{'hash':'../../bad','search_id':sid}]:
            with self.assertRaises(RequestError):self.b.download(body)
        self.core.found=[]
        with self.assertRaises(RequestError):self.b.download({'hash':HASH,'search_id':sid})
        self.assertFalse(any(op==0x2a for op,_ in self.core.calls))
    def test_invalid_queries_and_options_never_reach_core(self):
        for body in [{'query':''},{'query':'x'*161},{'query':'ok\nshutdown'},{'query':'ok','network':'bad'},{'query':'ok','type':'bad'}]:
            with self.assertRaises(RequestError):self.b.search(body)
        self.assertEqual(self.core.calls,[])
    def test_search_throttle_cache_and_new_generation(self):
        sid=self.start()['search_id'];self.b.snapshot();count=len(self.core.calls);self.b.snapshot();self.assertEqual(len(self.core.calls),count)
        with self.assertRaises(RequestError):self.start()
        self.now+=6;new=self.start()['search_id'];self.assertNotEqual(new,sid);self.assertEqual(self.b.results,{})
    def test_download_is_not_reported_successful_without_queue_confirmation(self):
        sid=self.start()['search_id'];self.b.snapshot()
        original=self.core.request
        def request(op,tags=()):
            if op==0x2a:return 6,[]
            return original(op,tags)
        self.core.request=request
        with self.assertRaises(AmuleError):self.b.download({'hash':HASH,'search_id':sid})
    def test_unavailable_core_returns_safe_error(self):
        with mock.patch('amule_dashboard.bridge') as bridge:
            bridge.snapshot.side_effect=OSError('private internal error')
            result,status=handle('GET','/api/amule')
            self.assertEqual(status,503);self.assertNotIn('private',result['error'])
    def test_control_uses_exact_existing_hash_and_never_deletes_partials(self):
        self.core.queue=[filetag()]
        for action,opcode in [('pause',0x19),('resume',0x1a),('stop',0x1b)]:
            self.assertTrue(self.b.control({'hash':HASH,'action':action})['ok'])
            tag=next(tags[0] for op,tags in self.core.calls if op==opcode)
            self.assertEqual(tag.value,bytes.fromhex(HASH))
        self.assertFalse(any(op==0x1d for op,_ in self.core.calls))
        with self.assertRaises(RequestError):self.b.control({'hash':'f'*32,'action':'pause'})
        with self.assertRaises(RequestError):self.b.control({'hash':HASH,'action':'delete'})
    def test_disabled_configuration(self):
        with mock.patch.dict(os.environ,{'AMULE_ENABLED':'false'}),self.assertRaises(RequestError):AmuleDashboard().snapshot()

class HTTPTests(unittest.TestCase):
    def test_auth_origin_body_and_operation_routes(self):
        import base64,http.client,importlib.util,json,threading
        from http.server import ThreadingHTTPServer
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('amule_test_http',root/'scripts/log-viewer.py')
        viewer=importlib.util.module_from_spec(spec);spec.loader.exec_module(viewer)
        viewer.DASHBOARD_USER='test';viewer.DASHBOARD_PASSWORD='test-only'
        server=ThreadingHTTPServer(('127.0.0.1',0),viewer.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        credentials='Basic '+base64.b64encode(b'test:test-only').decode()
        def request(method,path,body=b'{}',headers=None):
            h={'Authorization':credentials,'X-Dashboard-Action':'write'};h.update(headers or {})
            c=http.client.HTTPConnection(*server.server_address,timeout=5)
            try:
                c.request(method,path,body=body,headers=h);r=c.getresponse();return r.status,r.read()
            finally:c.close()
        try:
            with mock.patch('amule_dashboard.handle',return_value=({'ok':True},200)) as route:
                self.assertEqual(request('GET','/api/amule',headers={'Authorization':''})[0],401)
                self.assertEqual(request('POST','/api/amule/search',headers={'Origin':'https://evil.test'})[0],403)
                route.assert_not_called()
                self.assertEqual(request('POST','/api/amule/search',b'[]')[0],400)
                self.assertEqual(request('POST','/api/amule/search',b'not-json')[0],400)
                self.assertEqual(request('POST','/api/amule/search',headers={'Content-Length':'2049'})[0],400)
                route.assert_not_called()
                self.assertEqual(request('GET','/api/amule')[0],200)
                self.assertEqual(request('POST','/api/amule/search',b'{"query":"test"}')[0],200)
                route.assert_called_with('POST','/api/amule/search',{'query':'test'})
                self.assertEqual(request('POST','/api/amule/download',b'{"hash":"test"}')[0],200)
                self.assertEqual(route.call_count,3)
        finally:server.shutdown();server.server_close();thread.join()

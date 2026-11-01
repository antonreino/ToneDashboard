import base64
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import tonetti
spec=importlib.util.spec_from_file_location('chat_http',Path(__file__).resolve().parents[1]/'scripts/log-viewer.py');viewer=importlib.util.module_from_spec(spec);spec.loader.exec_module(viewer)
class ChatHTTP(unittest.TestCase):
 def test_auth_origin_files_and_conversations(self):
  with tempfile.TemporaryDirectory() as root,patch.object(tonetti,'ROOT',Path(root)),patch.object(viewer,'DASHBOARD_USER','test'),patch.object(viewer,'DASHBOARD_PASSWORD','test'):
   server=viewer.ThreadingHTTPServer(('127.0.0.1',0),viewer.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   def request(method,path,body=None,headers=None):
    conn=http.client.HTTPConnection(*server.server_address);conn.request(method,path,json.dumps(body) if body is not None else None,headers or {});response=conn.getresponse();result=response.status,dict(response.getheaders()),response.read();conn.close();return result
   auth={'Authorization':'Basic '+base64.b64encode(b'test:test').decode(),'X-Dashboard-Action':'write','Content-Type':'application/json'}
   try:
    for path in ['/api/tonetti/conversations','/api/tonetti/attachments','/api/tonetti/task-plans','/api/tonetti/task-plans/execute','/api/tonetti/task-plans/status']:
     self.assertEqual(request('POST',path,{}, {})[0],401);self.assertEqual(request('POST',path,{},dict(auth,Origin='https://evil.test'))[0],403)
    import tonetti_tasks as plans
    task={'id':'dashboard-backups','name':'Copias','description':'Copias consistentes','requirements':['Mac'],'enabled':True,'can_run':True}
    with patch.object(plans,'ROOT',Path(root)/'plans'),patch.object(plans.catalogue,'snapshot',return_value={'tasks':[task]}),patch.object(plans.runner,'start',return_value=({'state':'running','started_at':'synthetic'},202)) as launch,patch.object(plans.runner,'state',return_value={'state':'ok','started_at':'synthetic','message':'Prueba completa'}):
     code,_,raw=request('POST','/api/tonetti/task-plans',{'id':'dashboard-backups'},auth);self.assertEqual(code,201);token=json.loads(raw)['token'];launch.assert_not_called()
     self.assertEqual(request('POST','/api/tonetti/task-plans/execute',{'token':token,'prompt':'evil'},auth)[0],400)
     self.assertEqual(request('POST','/api/tonetti/task-plans/execute',{'token':token},auth)[0],202)
     self.assertEqual(request('POST','/api/tonetti/task-plans/execute',{'token':token},auth)[0],409);self.assertEqual(launch.call_count,1)
     code,_,raw=request('POST','/api/tonetti/task-plans/status',{'token':token},auth);self.assertEqual(code,200);self.assertEqual(json.loads(raw)['result']['state'],'ok')
    code,_,body=request('POST','/api/tonetti/conversations',{'title':'Casa'},auth);self.assertEqual(code,200);cid=json.loads(body)['id']
    code,_,body=request('GET','/api/tonetti?conversation='+str(cid),headers=auth);self.assertEqual(code,200);self.assertEqual(json.loads(body)['messages'],[])
    code,_,body=request('POST','/api/tonetti/attachments',{'name':'note.html','data':base64.b64encode(b'<script>alert(1)</script>').decode()},auth);self.assertEqual(code,201);aid=json.loads(body)['id']
    path='/api/tonetti/attachment/'+aid
    self.assertEqual(request('GET',path)[0],401)
    code,headers,raw=request('GET',path,headers=auth);self.assertEqual(code,200);self.assertEqual(headers['Content-Type'],'application/octet-stream');self.assertTrue(headers['Content-Disposition'].startswith('attachment;'));self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
    self.assertEqual(request('GET','/api/tonetti/attachment/../../../etc/passwd',headers=auth)[0],404)
   finally:server.shutdown();server.server_close();thread.join()

import base64
import http.client
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('ean_dashboard',Path(__file__).resolve().parents[1]/'scripts/log-viewer.py')
viewer=importlib.util.module_from_spec(spec);spec.loader.exec_module(viewer)
class DashboardEANTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.db=Path(self.tmp.name)/'prices.sqlite3';self.config=Path(self.tmp.name)/'config.json';self.config.write_text(json.dumps({'sources':[{'name':'Test','enabled':True}]}))
  with sqlite3.connect(self.db) as c:
   c.executescript('CREATE TABLE offers(source TEXT,payload TEXT,seen REAL,active INTEGER,price INTEGER); CREATE TABLE sources(name TEXT,ok INTEGER); CREATE TABLE published_notifications(body TEXT,created REAL); CREATE TABLE source_events(id INTEGER,name TEXT,level TEXT,detail TEXT,created REAL); INSERT INTO sources VALUES ("Test",1);')
   for model,price in [('slim_disc',60000),('ean:0711719021247',20000),('slim_disc',40000)]:c.execute('INSERT INTO offers VALUES (?,?,?,?,?)',('Test',json.dumps({'model':model,'title':'Producto','price':price,'source':'Test'}),1,1,price))
  for name,value in [('PRICE_BOT_DB',self.db),('PRICE_BOT_CONFIG',self.config),('PRICE_BOT_LOG',Path(self.tmp.name)/'empty.log')]:
   p=patch.object(viewer,name,value);p.start();self.addCleanup(p.stop)
 def test_snapshot_group_and_numeric_sort(self):
  with patch.object(viewer,'_price_bot_policy',return_value=({'Test'},None)),patch.object(viewer,'tracked_products',return_value=[{'ean':'0711719021247','name':'EAN 0711719021247'}]):d=viewer.price_bot_snapshot()
  self.assertTrue(d['available']);self.assertEqual([o['price'] for o in d['active_offers']],[20000,40000,60000]);self.assertEqual(d['active_offers'][0]['family'],'ean');self.assertEqual(d['active_offers'][0]['ean'],'0711719021247');self.assertEqual(d['products'][0]['name'],'Producto')
 def test_http_mutation_requires_auth_origin_and_valid_body(self):
  with patch.object(viewer,'DASHBOARD_USER','test'),patch.object(viewer,'DASHBOARD_PASSWORD','secret'),patch.object(viewer,'_tracked_products_module') as registry:
   registry.return_value.add_product.return_value={'ean':'0711719021247','name':'Producto'}
   server=viewer.ThreadingHTTPServer(('127.0.0.1',0),viewer.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   try:
    def post(body,headers):
     conn=http.client.HTTPConnection(*server.server_address);conn.request('POST','/api/deals/products',body,headers);r=conn.getresponse();result=(r.status,r.read());conn.close();return result
    auth={'Authorization':'Basic '+base64.b64encode(b'test:secret').decode(),'X-Dashboard-Action':'write'}
    self.assertEqual(post('{}',{})[0],401);self.assertEqual(post('{}',dict(auth,Origin='https://evil.test'))[0],403);registry.return_value.add_product.assert_not_called()
    self.assertEqual(post('{bad',auth)[0],400);self.assertEqual(post('[]',auth)[0],400);self.assertEqual(post('x'*1025,auth)[0],400)
    self.assertEqual(post('{"ean":"0711719021247"}',auth)[0],200);registry.return_value.add_product.assert_called_once_with(self.db,'0711719021247')
    conn=http.client.HTTPConnection(*server.server_address);registry.return_value.remove_product.return_value=True;conn.request('POST','/api/deals/products/remove','{"ean":"0711719021247"}',auth);response=conn.getresponse();self.assertEqual(response.status,200);self.assertTrue(json.loads(response.read())['removed']);conn.close();registry.return_value.remove_product.assert_called_once_with(self.db,'0711719021247')
    for action,method in [('remove','remove_tracking'),('restore','restore_tracking')]:
     getattr(registry.return_value,method).return_value=True
     conn=http.client.HTTPConnection(*server.server_address);conn.request('POST','/api/deals/products/'+action,'{"id":"ps5"}',auth);response=conn.getresponse();self.assertEqual(response.status,200);response.read();conn.close();getattr(registry.return_value,method).assert_called_once_with(self.db,'ps5')
   finally:server.shutdown();server.server_close();thread.join()
 def test_web_form_and_group_exist(self):
  for token in ['id="eanProductForm"','id="eanProductInput"','id="eanProductCards"','/api/deals/products','d.products||[]']:self.assertIn(token,viewer.HTML)
if __name__=='__main__':unittest.main()

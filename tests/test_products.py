import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ps5bot.products import validate_ean, add_product, list_products, product_sources, remove_product
from ps5bot.parsers import parse_page, discover_product_urls
from ps5bot.models import Offer
from ps5bot.store import Store
from ps5bot.app import collect
EAN='0711719021247'
SOURCE=dict(name='Tienda · EAN '+EAN,parser='pccomponentes',family='ean',kind='retailer',product_ean=EAN)
def page(data):return '<script type="application/ld+json">'+json.dumps(data)+'</script>'
def product(ean=EAN,price='149.95',url='https://www.pccomponentes.com/producto'):
 return {'@type':'Product','name':'Cafetera','gtin13':ean,'url':url,'offers':{'@type':'Offer','price':price,'priceCurrency':'EUR','availability':'https://schema.org/InStock'}}
class ProductTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'prices.sqlite3'
 def tearDown(self):self.tmp.cleanup()
 def test_valid_eans_leading_zero(self):
  self.assertEqual(validate_ean(' '+EAN+' '),EAN);self.assertEqual(validate_ean('96385074'),'96385074')
 def test_invalid_values(self):
  for value in [None,711719021247,'',EAN[:-1]+'8','１２３４５６７８','../'+EAN,'123456789012','12345678901234']:
   with self.subTest(value=value),self.assertRaises(ValueError):validate_ean(value)
 def test_idempotent_persistent(self):
  a=add_product(self.path,EAN);self.assertEqual(add_product(self.path,EAN),a);self.assertEqual(list_products(self.path),[a])
 def test_concurrent_add(self):
  add_product(self.path,EAN)
  with concurrent.futures.ThreadPoolExecutor(6) as pool:list(pool.map(lambda _:add_product(self.path,'96385074'),range(12)))
  self.assertEqual(len(list_products(self.path)),2)
 def test_limit_duplicate_at_limit(self):
  for i in range(20):
   prefix=f'{i+100:012d}';total=sum(int(n)*(3 if j%2==0 else 1) for j,n in enumerate(reversed(prefix)));add_product(self.path,prefix+str((-total)%10))
  with self.assertRaises(ValueError):add_product(self.path,EAN)
  first=list_products(self.path)[0];self.assertEqual(add_product(self.path,first['ean']),first)
 def test_disabled_sources_respected(self):
  cfg=[dict(name=p,parser=p,family='ps5',kind='retailer',enabled=p!='amazon') for p in ['amazon','pccomponentes']]
  sources=product_sources([{'ean':EAN}],cfg);self.assertEqual(len(sources),1);self.assertEqual(sources[0]['family'],'ean');self.assertIn(EAN,sources[0]['urls'][0])
 def test_exact_ean(self):
  offers=parse_page(page(product()),'https://www.pccomponentes.com/x',SOURCE);self.assertEqual(len(offers),1);self.assertEqual(offers[0].price,14995);self.assertEqual(offers[0].model,'ean:'+EAN)
 def test_search_query_not_identity(self):
  p=product();p.pop('gtin13');self.assertEqual(parse_page(page(p),'https://www.pccomponentes.com/search/?query='+EAN,SOURCE),[])
 def test_no_cross_product_ean(self):
  offers=parse_page(page([product(price='249'),product('96385074',price='1')]),'https://www.pccomponentes.com/x',SOURCE);self.assertEqual([o.price for o in offers],[24900])
 def test_explicit_wrong_gtin_overrides_title(self):
  p=product('96385074');p['name']='Cafetera '+EAN
  self.assertEqual(parse_page(page(p),'https://www.pccomponentes.com/x',SOURCE),[])
 def test_detail_failure_preserves_previous_state(self):
  from ps5bot.network import FetchError
  listing=product();listing.pop('gtin13')
  with patch('ps5bot.app.fetch_source_url',side_effect=[page(listing),FetchError('HTTP 403')]):
   with self.assertRaises(FetchError):collect(dict(SOURCE,urls=['https://www.pccomponentes.com/search']),{})
 def test_wrong_currency_and_aggregate(self):
  p=product();p['offers']['priceCurrency']='USD';self.assertEqual(parse_page(page(p),'https://www.pccomponentes.com/x',SOURCE),[])
  p=product();p['offers']['@type']='AggregateOffer';self.assertEqual(parse_page(page(p),'https://www.pccomponentes.com/x',SOURCE),[])
 def test_used_rejected(self):
  p=product();p['itemCondition']='UsedCondition';self.assertEqual(parse_page(page(p),'https://www.pccomponentes.com/x',SOURCE),[])
 def test_discovery_bounded(self):
  data=[product(url='https://www.pccomponentes.com/p'+str(i)) for i in range(10)];self.assertEqual(len(discover_product_urls(page(data),'https://www.pccomponentes.com/search',SOURCE)),3)
 def test_discovery_rejects_other_origins(self):
  data=[product(url=u) for u in ['http://127.0.0.1/p','https://evil.test/p','https://www.pccomponentes.com:123/p']];self.assertEqual(discover_product_urls(page(data),'https://www.pccomponentes.com/search',SOURCE),[])
 def test_rss_exact_ean(self):
  xml='<rss><channel><item><title>Aspirador 99€</title><description>EAN '+EAN+'</description><link>https://www.chollometro.com/ofertas/test</link></item></channel></rss>';s=dict(SOURCE,parser='chollometro',kind='deal')
  self.assertEqual(len(parse_page(xml,'https://www.chollometro.com/rss/nuevos',s)),1);self.assertEqual(parse_page(xml.replace(EAN,'96385074'),'https://www.chollometro.com/rss/nuevos',s),[])
 def test_generic_price_alert(self):
  add_product(self.path,EAN);store=Store(self.path,['1']);o=Offer(SOURCE['name'],'https://www.pccomponentes.com/x','Cafetera','ean:'+EAN,10000);store.source_result(o.source,[o],now=1);store.source_result(o.source,[Offer(o.source,o.url,o.title,o.model,9000)],now=2);self.assertIn('Cafetera',store.pending()['body']);store.db.close()
 def test_scheduler_adds_product_without_restart(self):
  import threading
  from ps5bot.app import run
  stop=threading.Event(); timer=threading.Timer(4,stop.set);seen=[];calls=[0]
  source=dict(name='PcComponentes',parser='pccomponentes',family='ps5',kind='retailer',urls=['https://www.pccomponentes.com/search'],enabled=True)
  def catalog(_):
   calls[0]+=1
   return [] if calls[0]==1 else [{'ean':EAN}]
  def result(name,*args,**kwargs):
   seen.append(name)
   if 'EAN' in name:stop.set()
  class Sink:
   source_result=staticmethod(result)
  tick=[0]
  def clock():tick[0]+=16;return tick[0]
  timer.start()
  try:
   with patch('ps5bot.app.list_products',side_effect=catalog),patch('ps5bot.app.collect',return_value=[]),patch('ps5bot.app.time.monotonic',side_effect=clock):run({'sources':[source],'interval_seconds':30},Sink(),stop)
  finally:timer.cancel()
  self.assertTrue(any('EAN '+EAN in n for n in seen));self.assertGreaterEqual(calls[0],2)
 def test_first_offer_notifies_all_existing_chats_and_removal_cancels_queue(self):
  tracked=add_product(self.path,EAN);store=Store(self.path,['1','2']);o=Offer(SOURCE['name'],'https://www.pccomponentes.com/x','Cafetera','ean:'+EAN,10000)
  store.source_result(o.source,[o],generation=tracked['created'])
  rows=store.db.execute('SELECT chat,product_ean FROM outbox ORDER BY chat').fetchall()
  self.assertEqual([(r['chat'],r['product_ean']) for r in rows],[('1',EAN),('2',EAN)])
  store.queue('Aviso de otro producto',chat='1')
  self.assertTrue(remove_product(self.path,EAN));self.assertFalse(remove_product(self.path,EAN))
  self.assertEqual(store.db.execute('SELECT count(*) FROM outbox').fetchone()[0],1)
  self.assertEqual(store.db.execute('SELECT active FROM offers').fetchone()[0],0)
  store.source_result(o.source,[o],generation=tracked['created'])
  self.assertEqual(store.db.execute('SELECT active FROM offers').fetchone()[0],0)
  self.assertEqual(store.db.execute('SELECT count(*) FROM published_notifications').fetchone()[0],1);store.db.close()
 def test_deleted_and_readded_ignores_old_generation(self):
  tracked=add_product(self.path,EAN);store=Store(self.path,['1']);remove_product(self.path,EAN);current=add_product(self.path,EAN)
  self.assertNotEqual(current['created'],tracked['created'])
  o=Offer(SOURCE['name'],'https://www.pccomponentes.com/x','Cafetera','ean:'+EAN,10000)
  store.source_result(o.source,[o],generation=tracked['created']);self.assertIsNone(store.pending())
  store.source_result(o.source,[o],generation=current['created']);self.assertIsNotNone(store.pending());store.db.close()
 def test_generic_price_and_stock_alerts_reach_all_chats(self):
  from dataclasses import replace
  add_product(self.path,EAN);store=Store(self.path,['1','2']);o=Offer(SOURCE['name'],'https://www.pccomponentes.com/x','Cafetera','ean:'+EAN,10000,availability='in_stock');store.source_result(o.source,[o]);store.db.execute('DELETE FROM outbox');store.db.commit()
  for changed,expected in [(replace(o,price=9000),'Bajada'),(replace(o,price=11000),'Subida')]:
   store.source_result(o.source,[changed]);rows=store.db.execute('SELECT chat,body FROM outbox').fetchall();self.assertEqual({r['chat'] for r in rows},{'1','2'});self.assertTrue(all(expected in r['body'] for r in rows));store.db.execute('DELETE FROM outbox');store.db.commit()
  store.source_result(o.source,[replace(o,availability='out_of_stock')]);self.assertIsNone(store.pending());store.source_result(o.source,[o]);self.assertIn('Vuelve el stock',store.pending()['body']);store.db.close()
 def test_legacy_outbox_migration_preserves_other_messages(self):
  import sqlite3
  with sqlite3.connect(self.path) as c:c.execute('CREATE TABLE outbox(id INTEGER PRIMARY KEY, chat TEXT,body TEXT,attempts INTEGER DEFAULT 0,due REAL DEFAULT 0)');c.execute('INSERT INTO outbox(chat,body) VALUES (?,?)',('1','otro mensaje'))
  store=Store(self.path,['1']);self.assertIn('product_ean',[r[1] for r in store.db.execute('PRAGMA table_info(outbox)')]);self.assertEqual(store.pending()['body'],'otro mensaje');store.db.close()
 def test_telegram_transport_delivers_ean_to_both_chats(self):
  import threading
  from ps5bot.app import notifications
  add_product(self.path,EAN);store=Store(self.path,['1','2']);o=Offer(SOURCE['name'],'https://www.pccomponentes.com/x','Cafetera','ean:'+EAN,10000);store.source_result(o.source,[o])
  stop=threading.Event();sent=[]
  class API:
   def send(self,chat,body):
    sent.append((chat,body))
    if len(sent)==2:stop.set()
  notifications(API(),store,stop);self.assertEqual({x[0] for x in sent},{'1','2'});self.assertTrue(all('Cafetera' in x[1] for x in sent));self.assertIsNone(store.pending());store.db.close()
 def test_collect_resolves_detail(self):
  listing=product();listing.pop('gtin13')
  with patch('ps5bot.app.fetch_source_url',side_effect=[page(listing),page(product())]) as fetch:offers=collect(dict(SOURCE,urls=['https://www.pccomponentes.com/search']),{})
  self.assertEqual(len(offers),1);self.assertEqual(fetch.call_count,2)
if __name__=='__main__':unittest.main()

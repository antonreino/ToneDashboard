#!/usr/bin/env python3
"""Read-only fake environment for responsive browser checks. No .env, services or real data."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from web_assets import dashboard_html
sample=json.loads((ROOT/'server/tests/contract-fixtures/dashboard.json').read_text())
sample['downloads']=[dict(sample['downloads'][0],id=1,name='Example download',status='active')]
sample['history']=[]
DEALS={'available':True,'products':[{'id':'ps5','family':'ps5','name':'PlayStation 5'}],'inactive_products':[],'active_offers':[{'family':'ps5','price':50000,'title':'Example offer','source':'Fixture','url':'https://example.test/offer','availability':'in_stock'}],'history':[],'events':[],'log':''}
REVIEW={'id':1,'name':'Example movie.mkv','reason':'Clasificación pendiente','status':'pending','decision':None}
DIAGNOSTIC={'version':'fixture','checked_at':'2026-10-17T00:00:00Z','services':sample['services'],'amule':{'available':True,'kad_nodes':100,'downloads':1},'orbit':{'running':False},'emby_system':{'available':False},'emby_storage':{'available':False},'backups':{'ok':True,'checked_at':'2026-10-17T00:00:00Z'}}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        data={'/api/dashboard':sample,'/api/deals':DEALS,'/api/logs':{'logs':{}},'/api/amule':{'ok':True,'downloads':[{'hash':'a'*32,'name':'Example aMule file','size':100,'completed':20,'progress':20,'speed':1,'sources':2}],'results':[]},'/api/organizer/reviews':{'items':[REVIEW]},'/api/organizer/rules':{'items':[]},'/api/diagnostics':DIAGNOSTIC,'/api/activity':{'items':[]},'/api/deals/preferences':{'recipients':['123'],'preferences':[]},'/api/history':{'items':[]},'/api/downloads':{'active':[],'history':[]},'/api/orbit/status':{'running':False,'can_start':False}}
        body=dashboard_html().encode() if path=='/' else json.dumps(data.get(path,{'error':'Fixture route not found'})).encode()
        self.send_response(200 if path=='/' or path in data else 404);self.send_header('Content-Type','text/html; charset=utf-8' if path=='/' else 'application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        # Deliberately refuse mutations: visual QA must never start downloads or modify files.
        self.send_response(405);self.send_header('Content-Length','0');self.end_headers()
    def log_message(self,*args):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',int(sys.argv[1]) if len(sys.argv)>1 else 8877),Handler).serve_forever()

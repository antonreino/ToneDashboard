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
SCHEDULED={'checked_at':'2026-10-21T12:00:00Z','summary':{'total':3,'active':3,'paused':0,'attention':1},'tasks':[
    {'id':'anime','name':'Anime: Japón y avisos','description':'Comprueba todas las series y los doblajes castellanos. Conserva las bajas manuales.','executor':'Codex','enabled':True,'schedule':'Cada 3 horas','status':'ok','last_run':'2026-10-21T11:54:37Z','logs':[{'at':'2026-10-21T11:54:37Z','status':'ok','message':'35 series verificadas, sin avisos pendientes.'}],'requirements':['Mac y Codex disponibles']},
    {'id':'ps5','name':'Mantener payloads de PS5','description':'Comprueba versiones oficiales y prepara actualizaciones compatibles. Aplaza cambios cuando no puede certificar actividad segura.','executor':'Codex','enabled':True,'schedule':'Cada día a las 10:00','status':'partial','last_run':'2026-10-21T08:01:36Z','logs':[{'at':'2026-10-21T08:01:36Z','status':'partial','message':'Actualizaciones preparadas. Instalación aplazada.'}],'requirements':['Consola accesible','Sin juegos o transferencias activos']},
    {'follow_up':{'at':'2026-10-21T13:00:00Z','message':'Una incidencia antigua se resolvió después del último informe; no modifica aquel resultado.'},'id':'future','name':'Comprobación futura','description':'Una tarea añadida después de publicar esta pantalla aparece automáticamente.','executor':'Codex','enabled':True,'schedule':'Cada lunes a las 08:00','status':'unknown','last_run':None,'logs':[],'requirements':['Mac disponible']}
],'warnings':[]}
for task in SCHEDULED['tasks']:
    task['can_run']=True
    task['outcome']={'title':'Pasos pendientes' if task['status']=='partial' else 'Resultado de la revisión','reason':'Gestor accesible; actualizaciones preparadas.','console':'Despertada correctamente.','next_step':'Verificar transferencias antes de instalar.'}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        data={'/api/scheduled-tasks':SCHEDULED,'/api/dashboard':sample,'/api/deals':DEALS,'/api/logs':{'logs':{}},'/api/amule':{'ok':True,'downloads':[{'hash':'a'*32,'name':'Example aMule file','size':100,'completed':20,'progress':20,'speed':1,'sources':2}],'results':[]},'/api/organizer/reviews':{'items':[REVIEW]},'/api/organizer/rules':{'items':[]},'/api/diagnostics':DIAGNOSTIC,'/api/activity':{'items':[]},'/api/deals/preferences':{'recipients':['123'],'preferences':[]},'/api/history':{'items':[]},'/api/downloads':{'active':[],'history':[]},'/api/orbit/status':{'running':False,'can_start':False}}
        body=dashboard_html().encode() if path=='/' else json.dumps(data.get(path,{'error':'Fixture route not found'})).encode()
        self.send_response(200 if path=='/' or path in data else 404);self.send_header('Content-Type','text/html; charset=utf-8' if path=='/' else 'application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        # Deliberately refuse mutations: visual QA must never start downloads or modify files.
        self.send_response(405);self.send_header('Content-Length','0');self.end_headers()
    def log_message(self,*args):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',int(sys.argv[1]) if len(sys.argv)>1 else 8877),Handler).serve_forever()

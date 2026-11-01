"""Dashboard adapter for the versioned, independent Tonetti dependency."""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request  # Shared urllib module retained for transport tests.

VENDOR=Path(__file__).resolve().parent/'vendor'
manifest=json.loads((VENDOR/'tonetti.json').read_text())
package=VENDOR/('tonetti_core-'+manifest['version']+'.zip')
if hashlib.sha256(package.read_bytes()).hexdigest()!=manifest['sha256']:
    raise RuntimeError('La dependencia Tonetti no supera la comprobación de integridad')
if str(package) not in sys.path:sys.path.insert(0,str(package))
from tonetti_core import service,storage
ROOT=Path(__file__).resolve().parents[1]/'data'/'tonetti'
MODEL='openclaw/tonetti'
_LOCK=service.LOCK

# Keep Tonetti's established Dashboard history, attachments and asynchronous API,
# while delegating reasoning and tool use to the single OpenClaw agent.
from openclaw_tonetti import generate as _openclaw_generate
service.generate=_openclaw_generate

def refresh_sources():
    # Explicit local trees only; read and index source, never execute it.
    from tonetti_core.knowledge import index_files
    dashboard=Path(__file__).resolve().parents[1]
    paths=[]
    for name in ('server','web','docs','workers/price_tracker','apple/ToneDashboardApps','scripts','.github/workflows'):
        paths.extend((dashboard/name).rglob('*'))
    index_files(ROOT,dashboard,paths)
    assistant=dashboard.parent/'tonetti'
    assistant_paths=[]
    for name in ('tonetti_core','scripts','docs'):
        assistant_paths.extend((assistant/name).rglob('*'))
    index_files(ROOT,assistant,assistant_paths)

def catalogue():
    from scheduled_tasks import snapshot as tasks
    return tasks()

def connect():return storage.connect(ROOT)
def context():return service.context(ROOT)
def snapshot(conversation_id=1,before=None):return service.snapshot(ROOT,MODEL,conversation_id,before)
def conversation(body):return service.conversation(ROOT,body)
def attachment_context(ids):
    from tonetti_attachments import context
    return context(ROOT,ids,storage.connect)
def upload(body):
    from tonetti_attachments import upload as ingest
    return ingest(ROOT,body,storage.connect)
def attachment(ident,preview=False):
    from tonetti_attachments import get
    return get(ROOT,ident,storage.connect,preview)
def start(body):
    if isinstance(body,dict) and set(body)<= {'message','conversation_id','attachments'} and isinstance(body.get('message'),str) and 0<len(body['message'])<=4000 and not _LOCK.locked() and any(w in body['message'].casefold() for w in ('código','codigo','script','parche','parser','función','funcion','fuente')):
        refresh_sources()
    return service.start(ROOT,MODEL,body,catalogue,attachment_context)

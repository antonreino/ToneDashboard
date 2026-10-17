"""Persistent commands, review decisions and file activity. No client paths or shell commands."""
from contextlib import closing
import json
import re
from pathlib import Path
import time
import threading
import state_db as db

SCHEMA='''
CREATE TABLE IF NOT EXISTS job_commands(id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL,action TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',error TEXT,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS file_activity(id INTEGER PRIMARY KEY,path TEXT NOT NULL,name TEXT NOT NULL,stage TEXT NOT NULL,detail TEXT NOT NULL,created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS activity_path_idx ON file_activity(path,id);
CREATE TABLE IF NOT EXISTS organizer_reviews(id INTEGER PRIMARY KEY,path TEXT UNIQUE NOT NULL,name TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',decision TEXT,signature TEXT NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS file_links(path TEXT PRIMARY KEY,root TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS organizer_rules(id INTEGER PRIMARY KEY,pattern TEXT UNIQUE NOT NULL,decision TEXT NOT NULL,created REAL NOT NULL);
'''

_schema_lock=threading.Lock()
_schema_ready=set()
def connection():
    db.init_db();conn=db.connect()
    with _schema_lock:
        key=str(db.DB_PATH)
        if key not in _schema_ready:
            conn.executescript(SCHEMA);_schema_ready.add(key)
    return conn

def activity(path,stage,detail=''):
    with closing(connection()) as conn,conn:
        alias=conn.execute('SELECT root FROM file_links WHERE path=?',(str(path),)).fetchone()
        path=alias['root'] if alias else str(path)
        last=conn.execute('SELECT stage,detail FROM file_activity WHERE path=? ORDER BY id DESC LIMIT 1',(str(path),)).fetchone()
        if last and last['stage']==stage and last['detail']==str(detail)[:2000]:return
        conn.execute('INSERT INTO file_activity(path,name,stage,detail,created) VALUES (?,?,?,?,?)',(str(path),Path(path).name,stage,str(detail)[:2000],time.time()))

def activities(before=None,limit=40,file_id=None):
    with closing(connection()) as conn:
        extra='';params=[]
        if file_id:
            row=conn.execute('SELECT path FROM file_activity WHERE id=?',(int(file_id),)).fetchone()
            if not row:return {'items':[],'next_cursor':None}
            extra=' AND path=?';params=[row['path']]
        rows=[dict(r) for r in conn.execute('SELECT id,name,stage,detail,created FROM file_activity WHERE id<?'+extra+' ORDER BY id DESC LIMIT ?', [int(before) if before else 2**63-1,*params,max(1,min(int(limit),100))+1])]
    return {'items':rows[:limit],'next_cursor':rows[limit-1]['id'] if len(rows)>limit else None}

def command(job_id,action):
    if type(job_id) is not int or job_id<1 or action not in ('pause','resume','cancel','retry'):raise ValueError('Acción o descarga no válida')
    allowed={'pause':('queued','active'),'resume':('paused',),'cancel':('queued','active','paused'),'retry':('failed','cancelled')}
    with closing(connection()) as conn,conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT status FROM downloads WHERE id=?',(job_id,)).fetchone()
        if row is None or row['status'] not in allowed[action]:raise ValueError('La descarga ya no admite esta acción. Actualiza la cola.')
        if conn.execute("SELECT 1 FROM job_commands WHERE job_id=? AND status IN ('pending','processing')",(job_id,)).fetchone():raise ValueError('Ya hay una acción pendiente para esta descarga')
        ident=conn.execute('INSERT INTO job_commands(job_id,action,created) VALUES (?,?,?)',(job_id,action,time.time())).lastrowid
        return {'ok':True,'command_id':ident,'status':'pending'}

def pending_commands():
    with closing(connection()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM job_commands WHERE status='pending' ORDER BY id LIMIT 20")]

def finish_command(ident,error=None):
    with closing(connection()) as conn,conn:
        conn.execute('UPDATE job_commands SET status=?,error=? WHERE id=?',('failed' if error else 'confirmed',str(error)[:200] if error else None,ident))

def download_record(ident):
    with closing(connection()) as conn:
        row=conn.execute('SELECT * FROM downloads WHERE id=?',(ident,)).fetchone();return dict(row) if row else None

def signature(path):
    st=Path(path).stat();return json.dumps([st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns])

def review(path,reason):
    with closing(connection()) as conn,conn:
        conn.execute("INSERT INTO organizer_reviews(path,name,reason,signature,updated) VALUES (?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET status='pending',reason=excluded.reason,signature=excluded.signature,updated=excluded.updated",(str(Path(path).resolve()),Path(path).name,str(reason)[:2000],signature(path),time.time()))

def reviews():
    with closing(connection()) as conn:
        return [dict(r) for r in conn.execute("SELECT id,name,reason,status,decision,updated FROM organizer_reviews WHERE status!='done' ORDER BY updated DESC LIMIT 100")]

def validate_decision(body):
    title=body.get('title');category=body.get('category')
    if not isinstance(title,str) or not 1<=len(title.strip())<=180 or re.search(r'[\x00-\x1f/\\]',title) or title.strip() in ('.','..'):raise ValueError('Título no válido')
    if category not in ('movies','series','anime'):raise ValueError('Categoría no válida')
    result={'title':title.strip(),'category':category}
    for name,low,high in [('year',1880,2200),('season',0,999),('episode',1,99999)]:
        value=body.get(name)
        if value not in (None,''):
            if type(value) is not int or not low<=value<=high:raise ValueError('Año, temporada o episodio no válido')
            result[name]=value
    if category!='movies' and ('season' not in result or 'episode' not in result):raise ValueError('Indica temporada y episodio')
    return result

def decide_review(body):
    decision=validate_decision(body);ident=body.get('id')
    if type(ident) is not int:raise ValueError('Revisión no válida')
    pattern=body.get('pattern','').strip()
    if len(pattern)>160 or any(ord(c)<32 for c in pattern):raise ValueError('Regla no válida')
    # Rules are literal case-insensitive fragments, never user-supplied regex or code.
    if pattern and len(pattern)<4:raise ValueError('La regla necesita al menos cuatro caracteres')
    with closing(connection()) as conn,conn:
        row=conn.execute("SELECT * FROM organizer_reviews WHERE id=? AND status IN ('pending','failed')",(ident,)).fetchone()
        if not row:raise ValueError('La revisión ya no está pendiente')
        if signature(row['path'])!=row['signature']:raise ValueError('El archivo ha cambiado; vuelve a revisarlo')
        conn.execute("UPDATE organizer_reviews SET decision=?,status='approved',updated=? WHERE id=?",(json.dumps(decision),time.time(),ident))
        if pattern:
            rule={k:v for k,v in decision.items() if k not in ('season','episode')}
            conn.execute('INSERT INTO organizer_rules(pattern,decision,created) VALUES (?,?,?) ON CONFLICT(pattern) DO UPDATE SET decision=excluded.decision',(pattern.casefold(),json.dumps(rule),time.time()))
    return {'ok':True,'status':'approved'}

def approved_reviews():
    with closing(connection()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM organizer_reviews WHERE status='approved' ORDER BY id")]

def finish_review(ident,error=None):
    with closing(connection()) as conn,conn:
        conn.execute('UPDATE organizer_reviews SET status=?,reason=?,updated=? WHERE id=?',('failed' if error else 'done',str(error)[:2000] if error else '',time.time(),ident))

def rule_for(path):
    with closing(connection()) as conn:
        rows=conn.execute('SELECT pattern,decision FROM organizer_rules ORDER BY length(pattern) DESC').fetchall()
    return next((json.loads(r['decision']) for r in rows if r['pattern'] in Path(path).name.casefold()),None)


def relocate(source,target):
    with closing(connection()) as conn,conn:
        row=conn.execute('SELECT root FROM file_links WHERE path=?',(str(source),)).fetchone()
        conn.execute('INSERT OR REPLACE INTO file_links VALUES (?,?)',(str(target),row['root'] if row else str(source)))

def register_existing(path):
    current=signature(path)
    with closing(connection()) as conn,conn:
        row=conn.execute('SELECT signature FROM organizer_reviews WHERE path=?',(str(Path(path).resolve()),)).fetchone()
        if row and row['signature']==current:return
        conn.execute("INSERT INTO organizer_reviews(path,name,reason,signature,updated) VALUES (?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET signature=excluded.signature,status='pending',decision=NULL,reason=excluded.reason,updated=excluded.updated",(str(Path(path).resolve()),Path(path).name,'Archivo en cuarentena pendiente de revisión',current,time.time()))

def rules():
    with closing(connection()) as conn:return [dict(r) for r in conn.execute('SELECT id,pattern,decision FROM organizer_rules ORDER BY id')]

def remove_rule(ident):
    if type(ident) is not int:raise ValueError('Regla no válida')
    with closing(connection()) as conn,conn:conn.execute('DELETE FROM organizer_rules WHERE id=?',(ident,))
    return {'ok':True}

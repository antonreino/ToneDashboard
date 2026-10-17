"""Safe operational API, using existing workers and data stores."""
from contextlib import closing
from pathlib import Path
import json
from datetime import datetime,timezone
import threading
import time
import state_db
import task_store
from runtime_support import backup_database


def diagnostics(services,price_db):
    from amule_dashboard import handle
    from orbit_dashboard_control import get_status
    amule,status=handle('GET','/api/amule')
    def reading(value):
        # Deliberately omit filesystem locations, raw logs and exception strings.
        result={k:value.get(k) for k in ('available','stale','updated_at','stored_at')}
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(value.get('updated_at') or '')).total_seconds()
            result['stale']=bool(result['stale'] or age>600)
            result['age_seconds']=max(0,int(age))
        except (ValueError,TypeError):result['stale']=True
        return result
    return {'version':(Path(__file__).resolve().parent.parent/'VERSION').read_text().strip(),
            'checked_at':state_db.utc_now(),'services':services,
            'amule':{'available':status==200,'kad_nodes':amule.get('kad_nodes',0),'downloads':len(amule.get('downloads',[]))},
            'orbit':{'running':bool(get_status().get('running'))},
            'emby_system':reading(state_db.emby_system_snapshot()),'emby_storage':reading(state_db.emby_storage_snapshot()),
            'organizer':state_db.get_runtime_state('organizer_heartbeat'),
            'backups':state_db.get_runtime_state('backup_status')}


def backup_all(price_db):
    files=[]
    for source in (state_db.DB_PATH,Path(price_db)):
        if source.is_file():
            target=backup_database(source,state_db.DB_PATH.parent/'backups'/source.stem)
            files.append({'database':source.name,'snapshot':target.name})
    value={'ok':True,'checked_at':state_db.utc_now(),'files':files}
    state_db.set_runtime_state('backup_status',value)
    return value


def maintenance_loop(price_db,stop):
    while not stop.is_set():
        try:backup_all(price_db)
        except Exception:
            state_db.set_runtime_state('backup_status',{'ok':False,'checked_at':state_db.utc_now(),'error':'No se pudo completar la copia verificada'})
        stop.wait(24*3600)


def get(path,query,services,price_db):
    if path=='/api/organizer/reviews':return {'items':task_store.reviews()},200
    if path=='/api/activity':return task_store.activities(query.get('before',[None])[0],file_id=query.get('file',[None])[0]),200
    if path=='/api/organizer/rules':return {'items':task_store.rules()},200
    if path=='/api/diagnostics':return diagnostics(services,price_db),200
    if path=='/api/deals/preferences':
        from ps5bot.preferences import list_preferences
        from ps5bot.products import connection
        with connection(price_db) as conn:return list_preferences(conn),200
    return {'error':'Ruta no válida'},404


def post(path,body,price_db):
    if path=='/api/downloads/control':return task_store.command(body.get('id'),body.get('action')),202
    if path=='/api/organizer/rules/remove':return task_store.remove_rule(body.get('id')),200
    if path=='/api/organizer/review':return task_store.decide_review(body),202
    if path=='/api/deals/preferences':
        from ps5bot.preferences import save
        from ps5bot.products import connection
        with connection(price_db) as conn:return save(conn,body),200
    return {'error':'Ruta no válida'},404

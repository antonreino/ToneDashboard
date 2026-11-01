"""User-confirmed task plans. No model output is accepted as an operation.

The owner already authenticates through Dashboard. Plans are private, durable,
single-use, expire after ten minutes and bind to the exact approved procedure.
A dispatch interrupted by a crash is uncertain, never automatically retried.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

import scheduled_tasks as catalogue
import task_runner as runner

ROOT = Path(__file__).resolve().parent.parent / 'data' / 'tonetti-task-plans'
TTL = 600
LIMITS = {
 'mantener-payloads-de-ps5': ['Despertar solo desde reposo con emparejamiento válido, una vez.', 'Comprobar juegos y transferencias antes de instalar; copia y hash antes y después.', 'Sin reinicio, jailbreak, cambios de firmware o red ni AutoLog. Arranque pendiente: intervención manual.'],
 'mantenimiento-semanal-proxmox-y-emby': ['Comprobar acceso, actividad, copias consistentes y simulaciones antes de actualizar.', 'Conservar datos y adaptaciones; validar servicios y registrar recuperación si falla.', 'Sin reinicio del host ni migración mayor. Aplazar interrupciones con actividad.'],
 'anime-espa-a-estrenos-y-avisos': ['Conservar altas, bajas manuales, historial y carteles locales.', 'Contrastar fuentes y emisión real; fecha prevista no significa capítulo disponible.', 'Avisar solo al propietario, sin duplicar; conservar datos si una fuente falla.'],
 'tonetti-revisi-n-diaria-de-calidad': ['Comprobar cuota, chat, bloqueo y presión de memoria; aplazar si no procede.', 'Unitarias y como máximo dos inferencias locales, con revisión de respuestas completas.', 'Sin entrenar pesos, cambiar modelo, ejecutar propuestas ni tocar infraestructura.'],
 'dashboard-backups': ['Crear copias consistentes de bases y memoria; comprobar integridad.', 'Aplicar únicamente la retención configurada; conservar originales activos.'],
 'dashboard-amule-recovery': ['Comprobar el proceso y abrir aMule si está caído, respetando el intervalo de recuperación.', 'Proceso abierto no garantiza conexión a la red; consultar el diagnóstico.'],
}


def _db():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    path=ROOT/'plans.sqlite3'
    fd=os.open(path, os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
    os.close(fd)
    db=sqlite3.connect(path, timeout=5)
    db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS plans (token TEXT PRIMARY KEY, task TEXT, created REAL, expires REAL, fingerprint TEXT, body TEXT, state TEXT, result TEXT, started TEXT)')
    db.commit()
    return db


def _task(task_id):
    if not isinstance(task_id,str) or task_id not in runner.ALLOWED or task_id not in LIMITS:
        raise ValueError('Tarea no admitida')
    task=next((x for x in catalogue.snapshot()['tasks'] if x['id']==task_id),None)
    if not task or not task.get('enabled') or not task.get('can_run'):
        raise ValueError('Tarea no disponible o pausada')
    return task


def _fingerprint(task):
    procedure=runner._prompt(task['id']) if task['id'] in catalogue._PROFILES else task['id']
    content={'procedure':procedure,'name':task['name'],'description':task['description'],'requirements':task.get('requirements',[]),'limits':LIMITS[task['id']]}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),hashlib.sha256(procedure.encode()).hexdigest()


def create(body):
    if not isinstance(body,dict) or set(body)!={'id'}:raise ValueError('Selecciona una tarea del catálogo')
    task=_task(body['id']);fingerprint,_=_fingerprint(task)
    now=time.time();token=secrets.token_hex(24)
    plan={'token':token,'id':task['id'],'name':task['name'],'description':task['description'],'requirements':task.get('requirements',[]),'checks':LIMITS[task['id']], 'expires_at':now+TTL,'executor':'Ejecutor limitado de Codex' if task['id'] in catalogue._PROFILES else 'Operación interna del Dashboard','notice':'Preparado, todavía sin ejecutar. Confirmar puede aplicar los cambios ya autorizados. El Mac debe permanecer encendido. El modelo local no ejecuta comandos.'}
    with closing(_db()) as db,db:
        # Bound unused previews without discarding consumed audit records.
        db.execute("DELETE FROM plans WHERE state='prepared' AND expires<?",(now-86400,))
        if db.execute("SELECT count(*) FROM plans WHERE state='prepared' AND expires> ?",(now,)).fetchone()[0]>=100:
            raise ValueError('Hay demasiados planes pendientes; espera a su caducidad.')
        db.execute('INSERT INTO plans VALUES (?,?,?,?,?,?,?,?,?)',(token,task['id'],now,now+TTL,fingerprint,json.dumps(plan,ensure_ascii=False),'prepared',None,None))
    return plan,201


def _token(body):
    if not isinstance(body,dict) or set(body)!={'token'} or not isinstance(body['token'],str) or not re.fullmatch('[a-f0-9]{48}',body['token']):raise ValueError('Plan no válido')
    return body['token']


def execute(body,price_db):
    token=_token(body)
    # Serializes consumption across HTTP threads and Dashboard processes.
    with closing(_db()) as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM plans WHERE token=?',(token,)).fetchone()
        if not row:db.rollback();return {'error':'Plan no encontrado'},404
        if row['state']!='prepared':db.rollback();return {'error':'Este plan ya se utilizó. Consulta el resultado antes de preparar otro.'},409
        if time.time()>=row['expires']:db.rollback();return {'error':'Plan caducado. Prepara uno nuevo.'},409
        task=_task(row['task']);fingerprint,prompt_digest=_fingerprint(task)
        if fingerprint!=row['fingerprint']:db.rollback();return {'error':'El procedimiento ha cambiado. Prepara un plan nuevo.'},409
        db.execute("UPDATE plans SET state='dispatching' WHERE token=?",(token,));db.commit()
    # Consumption precedes launch. Never retry a launch whose response was lost.
    try:
        result,code=runner.start(row['task'],price_db,expected_prompt_digest=prompt_digest)
        started=result.get('started_at') if code==202 else None
    except Exception:
        result,code={'error':'No se pudo confirmar el lanzamiento. Consulta Tareas programadas antes de repetir.'},503
        started=None
    with closing(_db()) as db,db:
        db.execute('UPDATE plans SET state=?,result=?,started=? WHERE token=?',('accepted' if code==202 else 'not_confirmed',json.dumps(result),started,token))
    return result,code


def status(body):
    token=_token(body)
    with closing(_db()) as db:row=db.execute('SELECT * FROM plans WHERE token=?',(token,)).fetchone()
    if not row:return {'error':'Plan no encontrado'},404
    state=row['state'];result=json.loads(row['result']) if row['result'] else {}
    if state=='accepted':
        execution=runner.state(row['task'])
        if execution and execution.get('started_at')==row['started']:result=execution
        else:result={'state':'unknown','message':'El registro actual corresponde a otra ejecución; consulta el historial de la tarea.'}
    if state=='dispatching':result={'state':'unknown','message':'Lanzamiento sin confirmar; consulta los registros antes de repetir. No se reintentará automáticamente.'}
    return {'id':row['task'],'plan_state':state,'result':result},200

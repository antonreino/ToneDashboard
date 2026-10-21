"""Explicit manual executions; fixed task IDs, bounded workers and private results."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import tomllib

import scheduled_tasks as catalogue

CODEX = Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex')
CODEX_MANUAL_ENABLED = True  # Limited approve-for-me profile explicitly authorized by the owner.
_LOCK = threading.Lock()
_ACTIVE = None
_LAST_START = 0.0
ALLOWED = frozenset(catalogue._PROFILES) | {'dashboard-backups', 'dashboard-amule-recovery'}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _folder(task_id):
    if task_id not in ALLOWED:
        raise ValueError('Esta tarea no admite ejecución manual.')
    return catalogue.AUDIT_ROOT / 'scheduled-tasks' / task_id


def state(task_id):
    folder = _folder(task_id)
    value = catalogue._json(folder / 'manual-state.json', catalogue.AUDIT_ROOT) or {}
    if not value:
        return None
    result = {k: value.get(k) for k in ('state', 'started_at', 'finished_at')}
    result['message'] = catalogue._text(value.get('message'), 1000)
    if result['state'] == 'running' and _ACTIVE != task_id:
        result.update(state='interrupted', message='El ejecutor se interrumpió. Comprueba el informe antes de repetir: no se garantiza que no haya cambios aplicados.')
    return result


def _prompt(task_id):
    path = catalogue.AUTOMATIONS_ROOT / task_id / 'automation.toml'
    raw = catalogue._read(path, catalogue.AUTOMATIONS_ROOT)
    try:
        data = tomllib.loads(raw or '')
    except ValueError:
        raise ValueError('No se puede leer la configuración de esta tarea.') from None
    if data.get('id') != task_id or data.get('status') != 'ACTIVE' or not isinstance(data.get('prompt'), str):
        raise ValueError('La tarea está pausada o su configuración no es válida.')
    return data['prompt'] + '\nEjecución manual autorizada desde Tone Dashboard. Respeta todos los límites de la tarea; no modifiques código ni automatizaciones, no reinicies host/consola ni ejecutes jailbreak. Usa los informes técnicos existentes y devuelve un resumen JSON: status ok/partial/error y message con comprobado, instalado y pendiente. Un proceso que acaba sin errores no prueba que el mantenimiento esté completo. No publiques secretos. Si falta acceso o aprobación, informa partial sin eludir controles. No envíes mensajes a otros chats. No lances subagentes. Espera los procesos iniciados hasta obtener su resultado; no cierres la revisión con el refresco aún en curso. No cambies manual-state.json ni los permisos del ejecutor.'


def _codex(prompt, descriptor):
    # Prompt via stdin; never accept a model, command, directory or flag from HTTP.
    with tempfile.TemporaryDirectory(prefix='tone-task-') as tmp:
        root = Path(tmp)
        schema = root / 'schema.json'
        answer = root / 'answer.json'
        schema.write_text(json.dumps({'type':'object','properties':{'status':{'type':'string','enum':['ok','partial','error']},'message':{'type':'string'}},'required':['status','message'],'additionalProperties':False}))
        command = [str(CODEX), 'exec', '--approve-for-me', '--skip-git-repo-check', '-C', str(catalogue.PROJECT_ROOT.parent), '--output-schema', str(schema), '-o', str(answer), '-']
        completed = subprocess.run(command, input=prompt, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, pass_fds=(descriptor,))
        if completed.returncode:
            return {'status':'error','message':'Codex no pudo completar la ejecución. Comprueba la sesión, el límite de uso y la disponibilidad del ejecutor en el Mac. No se afirma que las comprobaciones ni los cambios se hayan completado.'}
        if not answer.is_file() or answer.stat().st_size > 128_000:
            return {'status':'partial','message':'La ejecución terminó sin un informe final válido; revisar los informes técnicos antes de repetir.'}
        result = json.loads(answer.read_text())
        if result.get('status') not in {'ok','partial','error'} or not isinstance(result.get('message'),str):
            raise ValueError('Informe final no válido')
        return {'status':result['status'],'message':catalogue._text(result['message'],2400)}


def _work(task_id, price_db, prompt, descriptor, started):
    global _ACTIVE
    folder = _folder(task_id)
    try:
        if task_id == 'dashboard-backups':
            from operations import backup_all
            backup_all(price_db)
            result = {'status':'ok','message':'Copia manual completada y verificada.'}
        elif task_id == 'dashboard-amule-recovery':
            from amule_recovery import ensure_running
            value = ensure_running()
            result = {'status':'ok' if value['state']=='running' else 'partial','message':'aMule disponible o proceso abierto.' if value['state']=='running' else 'Comprobación realizada; estado: '+value['state']+'. Consulta el diagnóstico de aMule.'}
        else:
            result = _codex(prompt, descriptor)
    except Exception:
        result = {'status':'error','message':'No se pudo completar la ejecución manual. Revisa los informes técnicos; no repitas cambios hasta confirmar su estado.'}
    finally:
        try:
            at = now()
            report = {'at':at, **result}
            _write(folder / (at.replace(':','').replace('+0000','Z')+'-manual.json'), report)
            _write(folder / 'manual-state.json', {'state':result['status'],'started_at':started,'finished_at':at,'message':result['message']})
        finally:
            os.close(descriptor)
            with _LOCK:
                _ACTIVE = None


def start(task_id, price_db):
    global _ACTIVE, _LAST_START
    import time
    folder = _folder(task_id)
    prompt = None
    if task_id in catalogue._PROFILES:
        if not CODEX_MANUAL_ENABLED:
            raise ValueError('Pendiente autorizar el perfil limitado de ejecución de Codex en el Mac.')
        if not CODEX.is_file():
            raise ValueError('Codex no está instalado en el Mac; no se puede lanzar la revisión completa.')
        prompt = _prompt(task_id)
    with _LOCK:
        if _ACTIVE:
            return {'error':'Ya hay una tarea manual en ejecución. Espera a su resultado.'},409
        if time.monotonic() - _LAST_START < 10:
            return {'error':'Espera unos segundos antes de iniciar otra tarea.'},429
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        lockfile = catalogue.AUDIT_ROOT / 'scheduled-tasks' / 'manual.lock'
        descriptor = os.open(lockfile, os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
        try:
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            return {'error':'Ya hay un mantenimiento manual en ejecución.'},409
        started = now()
        try:
            _write(folder/'manual-state.json',{'state':'running','started_at':started,'message':'Ejecutando la tarea solicitada; todavía no hay resultado.'})
            _ACTIVE = task_id
            worker = threading.Thread(target=_work,args=(task_id,price_db,prompt,descriptor,started),daemon=True)
            worker.start()
            _LAST_START = time.monotonic()
        except Exception:
            _ACTIVE = None
            os.close(descriptor)
            raise
    return {'ok':True,'state':'running','message':'Ejecución iniciada. Consulta el estado y el informe final en esta tarjeta.'},202

"""One-shot signed-app bridge. Same limited Codex profile; no persistent service."""
from pathlib import Path
import fcntl
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

SERVER=Path(__file__).resolve().parents[1]
TASKS=frozenset({'mantenimiento-semanal-proxmox-y-emby','mantener-payloads-de-ps5'})


def validate_job(value):
    raw=Path(value);root=raw.resolve()
    bases=(Path(tempfile.gettempdir()).resolve(),Path('/private/tmp'))
    if raw.is_symlink() or not root.name.startswith('tone-task-') or not any(root.is_relative_to(base) for base in bases):raise ValueError('Directorio de tarea no válido')
    info=root.stat()
    if info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('Directorio de tarea no privado')
    for name,limit in (('prompt.txt',128000),('task.json',1000)):
        path=root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:raise ValueError('Solicitud no válida')
    task=json.loads((root/'task.json').read_text())
    if not isinstance(task,dict) or set(task)!={'id'} or task['id'] not in TASKS:raise ValueError('Tarea no autorizada para este asistente')
    if (root/'answer.json').exists():raise ValueError('La tarea ya tiene respuesta')
    return root


def main():
    if sys.argv[1:]==['--probe-ps5']:
        try:
            with socket.create_connection(('192.168.1.50',8084),timeout=4):
                print(json.dumps({'host':'192.168.1.50','port':8084,'state':'open'}))
                return 0
        except OSError as exc:
            print(json.dumps({'host':'192.168.1.50','port':8084,'state':'unreachable','errno':exc.errno}))
            return 2
    if sys.argv[1:]==['--probe']:
        # Stay alive long enough for macOS to show the permission prompt.
        command=[sys.executable,str(SERVER.parent.parent/'infra-maintenance/remote.py'),'--probe']
        result=None
        for attempt in range(5):
            result=subprocess.run(command,capture_output=True,text=True,timeout=12)
            if result.returncode==0:break
            if attempt<4:time.sleep(3)
        print(result.stdout.strip());return result.returncode
    if len(sys.argv)!=2:return 2
    root=validate_job(sys.argv[1])
    sys.path.insert(0,str(SERVER))
    import task_runner as runner
    lock=runner.catalogue.AUDIT_ROOT/'scheduled-tasks'/'maintenance-helper.lock'
    lock.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:result={'status':'partial','message':'Ya hay una revisión de mantenimiento en ejecución; no se inicia otra.'}
        else:result=runner._codex((root/'prompt.txt').read_text(),fd)
        runner._write(root/'answer.json',result)
    finally:os.close(fd)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception:sys.exit(2)

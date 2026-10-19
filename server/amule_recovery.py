"""Keep aMule available from Dashboard's existing maintenance loop; never kill it."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

_LOCK=threading.Lock()
_LAST_ATTEMPT=None
_STATE={'state':'disabled'}
APP=Path('/Applications/aMule.app')

def status():return dict(_STATE)

def ensure_running(clock=time.monotonic):
    global _LAST_ATTEMPT,_STATE
    if sys.platform!='darwin' or os.getenv('AMULE_ENABLED','').lower()!='true' or os.getenv('AMULE_AUTOSTART','').lower()!='true':
        _STATE={'state':'disabled'};return status()
    with _LOCK:
        try:
            with socket.create_connection(('127.0.0.1',4712),timeout=.5):
                _STATE={'state':'running'};return status()
        except OSError:pass
        try:
            process=subprocess.run(['/usr/bin/pgrep','-u',str(os.getuid()),'-x','(aMule|amule|amuled)'],capture_output=True,timeout=3,check=False)
            if process.returncode==0:
                _STATE={'state':'running'};return status()
            if process.returncode!=1:
                _STATE={'state':'unknown','error':'No se pudo comprobar el proceso de aMule'};return status()
            now=clock()
            if _LAST_ATTEMPT is not None and now-_LAST_ATTEMPT<120:return status()
            _LAST_ATTEMPT=now
            if not (APP/'Contents/MacOS/aMule').is_file():
                _STATE={'state':'failed','error':'aMule no está instalado en la ruta configurada'};return status()
            launched=subprocess.run(['/usr/bin/open','-g','-a',str(APP)],capture_output=True,timeout=8,check=False)
            _STATE={'state':'starting'} if launched.returncode==0 else {'state':'failed','error':'macOS no pudo iniciar aMule'}
        except (OSError,subprocess.TimeoutExpired):_STATE={'state':'failed','error':'No se pudo comprobar o iniciar aMule'}
        return status()

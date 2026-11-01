"""Private snapshots of explicitly named curated memory files, never arbitrary paths."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

NAMES=('infrastructure.md','tone-profile.md','runbooks.md','projects.json','runtime-model.json','current-facts.json')

def backup_context(root,directory,retain=14):
    root=Path(root);directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    name='context-'+str(time.time_ns());stage=directory/(name+'.partial');stage.mkdir(mode=0o700)
    files=[]
    try:
        for name in NAMES:
            source=root/name
            if source.is_symlink():raise ValueError('Curated context must not be a symlink')
            if not source.exists():continue
            if not source.is_file() or source.stat().st_size>1024*1024:raise ValueError('Invalid curated context file')
            data=source.read_bytes();target=stage/name
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(data)
            digest=hashlib.sha256(data).hexdigest()
            if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('Context snapshot verification failed')
            files.append({'name':name,'bytes':len(data),'sha256':digest})
        manifest=stage/'manifest.json';manifest.write_text(json.dumps({'files':files},indent=2)+'\n');manifest.chmod(0o600)
        final=stage.with_suffix('');os.replace(stage,final)
        old=sorted((p for p in directory.glob('context-*') if p.is_dir() and not p.is_symlink() and p.name.removeprefix('context-').isdigit()),key=lambda p:p.name,reverse=True)
        for folder in old[retain:]:shutil.rmtree(folder)
        return {'snapshot':final.name,'files':files}
    except Exception:
        shutil.rmtree(stage,ignore_errors=True);raise

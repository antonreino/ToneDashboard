"""Copias SQLite verificadas, sin eliminar el origen ni cambiar sus datos."""
from contextlib import closing
import hashlib
import json
import sqlite3
from pathlib import Path


def database_manifest(path):
    path = Path(path).resolve()
    # A verification must never create an empty database at a mistaken path.
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise ValueError('SQLite integrity check failed')
        tables = {}
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted = '"' + name.replace('"','""') + '"'
            rows = conn.execute('SELECT * FROM ' + quoted).fetchall()
            encoded = sorted(json.dumps(row,ensure_ascii=False,default=lambda x:x.hex()) for row in rows)
            tables[name] = {'rows':len(rows),'sha256':hashlib.sha256('\n'.join(encoded).encode()).hexdigest()}
        return tables


def verified_database_copy(source, target):
    source,target=Path(source),Path(target)
    if source.resolve() == target.resolve():
        raise ValueError('Source and target must differ')
    before = database_manifest(source)
    target.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(source)) as src,closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
    after = database_manifest(target)
    if before != after:
        raise ValueError('Database copy does not match source')
    target.chmod(0o600)
    return before

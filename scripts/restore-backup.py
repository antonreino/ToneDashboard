#!/usr/bin/env python3
"""Restore a verified snapshot to a NEW path; never overwrite a running database."""
import argparse
from contextlib import closing
from pathlib import Path
import os
import sqlite3


def restore(source,target):
    source,target=Path(source).resolve(),Path(target).resolve()
    if not source.is_file() or target.exists():raise ValueError('La copia debe existir y el destino debe ser un archivo nuevo')
    fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(target)) as dst:
            if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Copia dañada')
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Restauración dañada')
        return target
    except Exception:target.unlink(missing_ok=True);raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('snapshot');p.add_argument('new_destination');args=p.parse_args()
    print(restore(args.snapshot,args.new_destination))
    print('Copia verificada. Detén los servicios afectados antes de sustituir la base activa; conserva la anterior y sus archivos WAL/SHM para recuperación.')

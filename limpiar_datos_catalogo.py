#!/usr/bin/env python3
"""Purgado opcional y con copia de seguridad de las tablas del catálogo PS5 anterior.

No toca el estado de Orbit Zero ni las tablas del dashboard principal.
"""
from __future__ import annotations
import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
LEGACY_TABLES = (
    'ps5_catalog_url_archive', 'ps5_auto_sources', 'ps5_jd_sources',
    'ps5_jd_jobs', 'ps5_sgdb_art', 'ps5_releases', 'ps5_games',
    'ps5_catalog_versions',
)


def database_path():
    value = dotenv_values(ROOT / '.env').get('EMBY_STATE_DB')
    return Path(value).expanduser() if value else Path.home() / '.local/share/emby_organizer/state.sqlite3'


def purge(db: Path, backup: Path | None = None):
    """Sólo elimina tablas con nombres conocidos y conserva copia SQLite consistente."""
    if not db.is_file():
        raise FileNotFoundError(f'No existe la base de datos: {db}')
    with sqlite3.connect(db,timeout=30) as conn:
        tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        found=[name for name in LEGACY_TABLES if name in tables]
        if backup is None or not found:
            return found
        backup.parent.mkdir(parents=True,exist_ok=True)
        if backup.exists(): raise FileExistsError(f'Backup ya existe: {backup}')
        with sqlite3.connect(backup,timeout=30) as copy:
            conn.backup(copy)
            if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup de SQLite inválido; no se modificó el original')
        conn.execute('PRAGMA foreign_keys=OFF')
        try:
            with conn:
                for name in found:
                    conn.execute(f'DROP TABLE IF EXISTS "{name}"')
        finally:
            conn.execute('PRAGMA foreign_keys=ON')
        return found


def main():
    parser=argparse.ArgumentParser(description='Eliminar únicamente tablas del viejo catálogo PS5')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--confirm',choices=['ELIMINAR'])
    parser.add_argument('--database',type=Path,help='ruta explícita para depuración (si se omite, lee .env)')
    args=parser.parse_args()
    db=(args.database or database_path()).expanduser()
    if not db.is_file():
        parser.error(f'No existe SQLite: {db}')
    if args.apply and args.confirm!='ELIMINAR':
        parser.error('Debes confirmar expresamente: --apply --confirm ELIMINAR')
    backup=ROOT/'.patch-backups'/('legacy-sqlite-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3') if args.apply else None
    found=purge(db,backup)
    print('Tablas de catálogo antiguo:', ', '.join(found) if found else '(ninguna)')
    if args.apply:
        print('Copia SQLite:',backup if found else 'no necesaria')
        print('OK. Emby, Telegram, historial y Orbit intactos.')
    else:print('SIMULACIÓN. Ninguna tabla eliminada.')

if __name__=='__main__':main()

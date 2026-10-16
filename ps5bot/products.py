"""Registro compartido por dashboard y monitor; SQLite conserva ceros iniciales."""
from contextlib import contextmanager
import re
import sqlite3
import time
from pathlib import Path

MAX_PRODUCTS = 20
BUILTINS = {
    'ps5': ('PlayStation 5', ('fat_digital', 'fat_disc', 'slim_digital', 'slim_disc')),
    'switch2': ('Nintendo Switch 2 · Zelda', ('switch2_zelda40',)),
}


def validate_ean(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9]{8}|[0-9]{13})', value.strip()):
        raise ValueError('Introduce un EAN de 8 o 13 cifras.')
    value = value.strip()
    if not int(value):
        raise ValueError('El EAN no puede ser cero.')
    total = sum(int(n) * (3 if i % 2 == 0 else 1) for i, n in enumerate(reversed(value[:-1])))
    if (10 - total % 10) % 10 != int(value[-1]):
        raise ValueError('El dígito de control del EAN no es válido.')
    return value


@contextmanager
def connection(path):
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE IF NOT EXISTS tracked_products (ean TEXT PRIMARY KEY, name TEXT NOT NULL, created REAL NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS tracked_families (family TEXT PRIMARY KEY, enabled INTEGER NOT NULL, generation REAL NOT NULL)')
    conn.executemany('INSERT OR IGNORE INTO tracked_families VALUES (?,1,0)', [(k,) for k in BUILTINS])
    conn.commit()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_products(path):
    if not Path(path).exists():
        return []
    with connection(path) as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM tracked_products ORDER BY created,ean')]


def add_product(path, value):
    ean = validate_ean(value)
    with connection(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM tracked_products WHERE ean=?', (ean,)).fetchone()
        if row:
            return dict(row)
        if conn.execute('SELECT count(*) FROM tracked_products').fetchone()[0] >= MAX_PRODUCTS:
            raise ValueError('Máximo 20 productos en seguimiento.')
        conn.execute('INSERT INTO tracked_products VALUES (?,?,?)', (ean, 'EAN ' + ean, time.time()))
        return dict(conn.execute('SELECT * FROM tracked_products WHERE ean=?', (ean,)).fetchone())


def product_sources(products, configured):
    # Respetar las fuentes desactivadas: un EAN no reactiva CAPTCHA/403.
    templates = {s['parser']: s for s in configured if s.get('family', 'ps5') == 'ps5'}
    urls = {
        'amazon': 'https://www.amazon.es/s?k={ean}',
        'idealo': 'https://www.idealo.es/resultados.html?q={ean}',
        'chollometro': 'https://www.chollometro.com/rss/nuevos',
        'pccomponentes': 'https://www.pccomponentes.com/search/?query={ean}',
        'mediamarkt': 'https://www.mediamarkt.es/es/search.html?query={ean}',
    }
    result = []
    for product in products:
        ean = validate_ean(product['ean'])
        for parser, url in urls.items():
            template = templates.get(parser)
            if not template or not template.get('enabled', True):
                continue
            source = dict(template, name=f'{template["name"]} · EAN {ean}', family='ean',
                          product_ean=ean, product_generation=product.get('created'), urls=[url.format(ean=ean)], initial_delay_seconds=0,
                          interval_seconds=max(900, template.get('interval_seconds', 900)))
            result.append(source)
    return result


def remove_product(path, value):
    """Dejar de seguir sin borrar el historial de avisos publicados."""
    ean = validate_ean(value)
    with connection(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        removed = bool(conn.execute('DELETE FROM tracked_products WHERE ean=?', (ean,)).rowcount)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'offers' in tables:
            conn.execute('UPDATE offers SET active=0 WHERE model=?', ('ean:' + ean,))
        if 'outbox' in tables:
            columns = {r[1] for r in conn.execute('PRAGMA table_info(outbox)')}
            if 'product_ean' in columns:
                conn.execute('DELETE FROM outbox WHERE product_ean=? OR (product_ean IS NULL AND instr(body,?)>0)', (ean, 'EAN ' + ean))
            else:
                conn.execute('DELETE FROM outbox WHERE instr(body,?)>0', ('EAN ' + ean,))
        return removed



def list_tracking(path, enabled=True):
    with connection(path) as conn:
        families = [dict(id=r['family'], ean='', name=BUILTINS[r['family']][0], family=r['family'])
                    for r in conn.execute('SELECT * FROM tracked_families WHERE enabled=? ORDER BY family', (int(enabled),)) if r['family'] in BUILTINS]
    return families + ([dict(p, id='ean:'+p['ean'], family='ean') for p in list_products(path)] if enabled else [])


def configured_sources(path, configured):
    with connection(path) as conn:
        states = {r['family']: dict(r) for r in conn.execute('SELECT * FROM tracked_families')}
    return [dict(s, tracking_generation=states[s.get('family', 'ps5')]['generation']) for s in configured
            if s.get('enabled', True) and states.get(s.get('family', 'ps5'), {}).get('enabled')]


def remove_tracking(path, ident):
    if not isinstance(ident, str):
        raise ValueError('Identificador de seguimiento no válido')
    if ident not in BUILTINS:
        return remove_product(path, ident.removeprefix('ean:'))
    with connection(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        changed = bool(conn.execute('UPDATE tracked_families SET enabled=0,generation=? WHERE family=? AND enabled=1', (time.time(),ident)).rowcount)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'offers' in tables:
            for model in BUILTINS[ident][1]:conn.execute('UPDATE offers SET active=0 WHERE model=?',(model,))
        if 'outbox' in tables:
            columns = {r[1] for r in conn.execute('PRAGMA table_info(outbox)')}
            if 'product_family' in columns:conn.execute('DELETE FROM outbox WHERE product_family=?',(ident,))
            # Compatibilidad con avisos antiguos, sin borrar avisos de EAN.
            if 'product_ean' in columns:
                for label in (('PS5 ',) if ident=='ps5' else ('Nintendo Switch 2',)):
                    conn.execute('DELETE FROM outbox WHERE product_ean IS NULL AND instr(body,?)>0',(label,))
        return changed


def restore_tracking(path, ident):
    if not isinstance(ident, str) or ident not in BUILTINS:
        raise ValueError('Solo PS5 y Switch se restauran aquí; los demás productos se añaden por EAN.')
    with connection(path) as conn:
        conn.execute('UPDATE tracked_families SET enabled=1,generation=? WHERE family=? AND enabled=0',(time.time(),ident))
    return True

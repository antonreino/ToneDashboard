"""Registro compartido por dashboard y monitor; SQLite conserva ceros iniciales."""
from contextlib import contextmanager
import re
import sqlite3
import time
from pathlib import Path

MAX_PRODUCTS = 20


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
                          product_ean=ean, urls=[url.format(ean=ean)], initial_delay_seconds=0,
                          interval_seconds=max(900, template.get('interval_seconds', 900)))
            result.append(source)
    return result

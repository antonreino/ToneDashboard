"""Per-product and per-recipient notification policy, defaulting to existing behaviour."""
import time

def ensure(conn):
    conn.executescript('''CREATE TABLE IF NOT EXISTS notification_preferences(product TEXT NOT NULL,chat TEXT NOT NULL,target_cents INTEGER,min_drop REAL NOT NULL DEFAULT 0,restock INTEGER NOT NULL DEFAULT 1,muted_until REAL NOT NULL DEFAULT 0,PRIMARY KEY(product,chat));
CREATE TABLE IF NOT EXISTS notification_recipients(chat TEXT PRIMARY KEY);''')

def list_preferences(conn):
    ensure(conn)
    return {'recipients':[r[0] for r in conn.execute('SELECT chat FROM notification_recipients ORDER BY chat')], 'preferences':[dict(r) for r in conn.execute('SELECT * FROM notification_preferences ORDER BY product,chat')]}

def save(conn,body):
    ensure(conn)
    product,chat=body.get('product'),body.get('chat','')
    if not isinstance(product,str) or (product not in ('ps5','switch2') and not (product.startswith('ean:') and conn.execute('SELECT 1 FROM tracked_products WHERE ean=?',(product[4:],)).fetchone())):raise ValueError('Producto no válido')
    if not isinstance(chat,str) or (chat and not conn.execute('SELECT 1 FROM notification_recipients WHERE chat=?',(chat,)).fetchone()):raise ValueError('Destinatario no configurado')
    target,drop,restock,hours=body.get('target_cents'),body.get('min_drop',0),body.get('restock',True),body.get('mute_hours',0)
    if target is not None and (type(target) is not int or not 1<=target<=100000000):raise ValueError('Precio objetivo no válido')
    if type(drop) not in (int,float) or not 0<=drop<=100 or type(hours) not in (int,float) or not 0<=hours<=8760 or type(restock) is not bool:raise ValueError('Preferencias no válidas')
    conn.execute('INSERT INTO notification_preferences VALUES (?,?,?,?,?,?) ON CONFLICT(product,chat) DO UPDATE SET target_cents=excluded.target_cents,min_drop=excluded.min_drop,restock=excluded.restock,muted_until=excluded.muted_until',(product,chat,target,drop,int(restock),time.time()+hours*3600 if hours else 0))
    if hours:
        if product.startswith('ean:'):
            conn.execute('DELETE FROM outbox WHERE product_ean=?'+(' AND chat=?' if chat else ''),(product[4:],chat) if chat else (product[4:],))
        else:
            conn.execute('DELETE FROM outbox WHERE product_family=?'+(' AND chat=?' if chat else ''),(product,chat) if chat else (product,))
    conn.commit()
    return {'ok':True}

def eligible(conn,product,chat,offer,old,now):
    row=conn.execute('SELECT * FROM notification_preferences WHERE product=? AND chat IN (?,\'\') ORDER BY (chat=?) DESC LIMIT 1',(product,str(chat),str(chat))).fetchone()
    if row is None:return True
    if row['muted_until']>now:return False
    if row['target_cents'] is not None and offer.price>row['target_cents']:return False
    if old and __import__('json').loads(old['payload']).get('availability')=='out_of_stock' and offer.availability in ('in_stock','preorder') and not row['restock']:return False
    if row['min_drop']:
        if not old or old['price']<=0 or (old['price']-offer.price)*100/old['price']<row['min_drop']:return False
    return True

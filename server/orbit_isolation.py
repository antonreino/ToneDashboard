"""Optional second HTTPS origin for Orbit, served by the existing listener.

Disabled unless both origins are configured. Dashboard credentials never leave
its origin. A one-use 60-second ticket grants ONLY access to the Orbit proxy.
"""
from http.cookies import SimpleCookie
import hashlib
import os
import secrets
import threading
import time
from urllib.parse import urlsplit,parse_qs

_lock=threading.Lock();_tickets={};_sessions={}
COOKIE='__Host-tone_orbit_scope'

def origins():
    result=[]
    for key in ('DASHBOARD_PUBLIC_ORIGIN','ORBIT_ISOLATED_ORIGIN'):
        value=os.getenv(key,'').strip().rstrip('/')
        try:
            p=urlsplit(value)
            if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment:return None
            _=p.port
        except ValueError:return None
        result.append(value)
    if result[0].lower()==result[1].lower():return None
    return tuple(result)

def isolated_host(headers):
    configured=origins()
    return bool(configured and headers.get('Host','').lower()==urlsplit(configured[1]).netloc.lower())

def _prune(now):
    for items in (_tickets,_sessions):
        for key,expires in list(items.items()):
            if expires<=now:items.pop(key,None)

def entry():
    configured=origins()
    if not configured:raise ValueError('El origen aislado de Orbit no está configurado')
    with _lock:
        _prune(time.monotonic())
        if len(_tickets)>=100:raise ValueError('Demasiadas solicitudes de conexión')
        ticket=secrets.token_urlsafe(32);_tickets[hashlib.sha256(ticket.encode()).hexdigest()]=time.monotonic()+60
    return {'url':configured[1]+'/orbit-session?ticket='+ticket}

def valid(headers):
    if not isolated_host(headers):return False
    try:
        cookie=SimpleCookie();cookie.load(headers.get('Cookie',''));token=cookie[COOKIE].value
    except (KeyError,ValueError):return False
    with _lock:
        _prune(time.monotonic());return hashlib.sha256(token.encode()).hexdigest() in _sessions

def handle_entry(handler):
    if not isolated_host(handler.headers) or urlsplit(handler.path).path!='/orbit-session':return False
    ticket=parse_qs(urlsplit(handler.path).query).get('ticket',[''])[0]
    with _lock:
        now=time.monotonic();_prune(now)
        accepted=bool(_tickets.pop(hashlib.sha256(ticket.encode()).hexdigest(),None))
        if accepted and len(_sessions)<1000:
            token=secrets.token_urlsafe(32);_sessions[hashlib.sha256(token.encode()).hexdigest()]=now+12*3600
        else:accepted=False
    handler.send_response(303 if accepted else 403)
    if accepted:
        handler.send_header('Set-Cookie',f'{COOKIE}={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=43200')
        handler.send_header('Location','/orbit-bridge/zero/')
    handler.send_header('Referrer-Policy','no-referrer');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length','0');handler.end_headers();return True

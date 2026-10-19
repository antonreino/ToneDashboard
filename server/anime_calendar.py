"""Private, read-only iCalendar subscription. Only verified dated releases, no recurrence."""
import argparse
from datetime import date, datetime, timezone
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import threading
import unicodedata
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path.home()/'.local/share/emby_organizer/anime-calendar'
LOCK = threading.RLock()
CATALOG = Path(__file__).with_name('anime_calendar_seed.json')


def validate(data):
    if not isinstance(data,dict) or not isinstance(data.get('series'),list) or not isinstance(data.get('events'),list):
        raise ValueError('Calendario no válido')
    ids=set()
    for series in data['series']:
        if not re.fullmatch('[a-z0-9-]{1,50}',series.get('id','')) or series['id'] in ids:
            raise ValueError('Serie no válida')
        ids.add(series['id'])
        if 'tracking' in series and type(series['tracking']) is not bool:raise ValueError('Seguimiento no válido')
        if series.get('status')=='finished' and series.get('conclusion_confirmed') is not True:raise ValueError('Final definitivo no confirmado')
        if series.get('status') not in ('active','archived','finished'):raise ValueError('Estado no válido')
        if not isinstance(series.get('title'),str) or not 1<=len(series['title'])<=150:raise ValueError('Título no válido')
    keys=set()
    for event in data['events']:
        if event.get('series') not in ids or event.get('version') not in ('sub-es','dub-es'):raise ValueError('Versión no válida')
        if type(event.get('episode')) is not int or not 1<=event['episode']<=99999:raise ValueError('Episodio no válido')
        day=date.fromisoformat(event['date'])
        source=event.get('source','')
        parsed=urlsplit(source)
        if event.get('region')!='ES' or parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or any(ord(c)<32 for c in source):raise ValueError('Fuente/región no válida')
        if 'available' in event and type(event['available']) is not bool:raise ValueError('Disponibilidad no válida')
        key=(event['series'],event.get('season',1),event['episode'],event['version'])
        if type(event.get('season',1)) is not int or not 0<=event.get('season',1)<=999 or key in keys:raise ValueError('Evento duplicado/no válido')
        keys.add(key)
    return data


def snapshot():
    with LOCK:
        path=ROOT/'schedule.json'
        data=validate(json.loads((path if path.exists() else CATALOG).read_text()))
    today=datetime.now(ZoneInfo('Europe/Madrid')).date().isoformat()
    active={s['id'] for s in data['series'] if s['status']=='active' and s.get('tracking',True)}
    visible=[s for s in data['series'] if s['status']!='finished' and s.get('tracking',True)]
    return {**data,'series':visible,'events':sorted([e for e in data['events'] if e['series'] in active and e['date']>=today],key=lambda e:(e['date'],e['series'],e['version']))}


def set_status(series_id,status,confirmed=False):
    if status not in ('active','archived','finished'):raise ValueError('Estado no válido')
    if status=='finished' and confirmed is not True:raise ValueError('Confirma que la historia ha terminado definitivamente')
    with LOCK:
        path=ROOT/'schedule.json'
        data=validate(json.loads((path if path.exists() else CATALOG).read_text()))
        series=next((s for s in data['series'] if s['id']==series_id),None)
        if not series:raise ValueError('Anime no encontrado')
        series.update(status=status,conclusion_confirmed=bool(confirmed))
        private_write(path,validate(data))
    return {'ok':True}


def manage_series(action,title=None,series_id=None):
    """Unfollow preserves history and notification IDs; adding the same title restores it."""
    with LOCK:
        path=ROOT/'schedule.json'
        data=validate(json.loads((path if path.exists() else CATALOG).read_text()))
        if action=='remove':
            series=next((s for s in data['series'] if s['id']==series_id),None)
            if not series:raise ValueError('Anime no encontrado')
            series['tracking']=False
        elif action=='add':
            if not isinstance(title,str):raise ValueError('Introduce el título del anime')
            title=' '.join(unicodedata.normalize('NFKC',title).split())
            if not 1<=len(title)<=150 or any(unicodedata.category(c).startswith('C') for c in title):raise ValueError('Título no válido (máximo 150 caracteres)')
            normalize=lambda value:unicodedata.normalize('NFKC',value).casefold()
            series=next((s for s in data['series'] if normalize(s['title'])==normalize(title)),None)
            if series:
                if series.get('tracking',True):raise ValueError('Este anime ya está en seguimiento')
                series['tracking']=True
            else:
                if len(data['series'])>=500:raise ValueError('Límite de 500 animes alcanzado')
                series={'id':'custom-'+secrets.token_hex(10),'title':title,'status':'archived','tracking':True,'added_on':datetime.now(ZoneInfo('Europe/Madrid')).date().isoformat(),
                        'season_note':'Añadido por ti. Pendiente de identificar portada y próximos estrenos en la revisión automática.',
                        'dub_status':'Castellano: pendiente de confirmación'}
                data['series'].append(series)
        else:raise ValueError('Acción no válida')
        private_write(path,validate(data))
        return {'ok':True,'id':series['id']}


def private_write(path,data):
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    tmp=ROOT/(secrets.token_hex(12)+'.tmp')
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False)
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def subscription(rotate=False):
    with LOCK:
        path=ROOT/'subscription.json'
        data=json.loads(path.read_text()) if path.exists() and not rotate else {'token':secrets.token_urlsafe(32)}
        if not path.exists() or rotate:private_write(path,data)
        return '/calendar/anime/'+data['token']+'.ics'


def authorized(token):
    if not re.fullmatch('[a-zA-Z0-9_-]{43}',token):return False
    try:
        return hmac.compare_digest(token,json.loads((ROOT/'subscription.json').read_text())['token'])
    except (OSError,ValueError,KeyError):return False


def escape(value):
    return str(value).replace('\\','\\\\').replace('\r','').replace('\n','\\n').replace(';','\\;').replace(',','\\,')


def calendar(data=None):
    data=snapshot() if data is None else data
    titles={s['id']:s['title'] for s in data['series']}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Tone Dashboard//Anime ES//ES','CALSCALE:GREGORIAN','X-WR-CALNAME:Tone · Anime España','REFRESH-INTERVAL;VALUE=DURATION:PT6H','X-PUBLISHED-TTL:PT6H']
    for e in data['events']:
        day=date.fromisoformat(e['date']).strftime('%Y%m%d')
        version='Subtitulado España' if e['version']=='sub-es' else 'Doblaje castellano'
        uid=f"{e['series']}-s{e.get('season',1)}-e{e['episode']}-{e['version']}@tone-dashboard"
        lines+=['BEGIN:VEVENT','UID:'+uid,'DTSTAMP:'+stamp,'DTSTART;VALUE=DATE:'+day,
                'SUMMARY:'+escape(f"{titles[e['series']]} · T{e.get('season',1)} E{e['episode']} · {version}"),
                'DESCRIPTION:'+escape('Disponible en España. Día de estreno; hora no confirmada. Fuente: '+e['source']),
                'URL:'+e['source'],'TRANSP:TRANSPARENT','END:VEVENT']
    lines+=['END:VCALENDAR']
    # Fold by UTF-8 octets, without splitting characters (RFC 5545).
    folded=[]
    for line in lines:
        chunk=''
        for char in line:
            if len((chunk+char).encode())>74:folded.append(chunk);chunk=' '
            chunk+=char
        folded.append(chunk)
    return ('\r\n'.join(folded)+'\r\n').encode()


def notify_available(sender=None):
    import fcntl
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd=os.open(ROOT/'notify.lock',os.O_CREAT|os.O_RDWR,0o600)
    with os.fdopen(fd,'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        data=validate(json.loads((ROOT/'schedule.json' if (ROOT/'schedule.json').exists() else CATALOG).read_text()))
        ledger_path=ROOT/'notifications.json'
        ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
        titles={s['id']:s['title'] for s in data['series'] if s['status']!='finished' and s.get('tracking',True)}
        added={s['id']:s.get('added_on','0001-01-01') for s in data['series']}
        sent=0
        if sender is None:
            from dotenv import dotenv_values
            import requests
            cfg=dotenv_values(Path(__file__).with_name('.env'))
            token,chat=cfg.get('TELEGRAM_BOT_TOKEN'),cfg.get('TELEGRAM_CHAT_ID')
            if not token or not chat:raise ValueError('Telegram del propietario no está configurado')
            def sender(message):
                session=requests.Session();session.trust_env=False
                try:
                    response=session.post('https://api.telegram.org/bot'+token+'/sendMessage',json={'chat_id':chat,'text':message},timeout=20)
                    if response.status_code!=200 or not response.json().get('ok'):raise ValueError('Telegram rechazó el aviso')
                except requests.RequestException:raise RuntimeError('Envío incierto; no se repetirá automáticamente') from None
                finally:session.close()
        for e in data['events']:
            if e['series'] not in titles or e.get('available') is not True or e['date']>datetime.now(ZoneInfo('Europe/Madrid')).date().isoformat():continue
            if e['date']<added.get(e['series'],'0001-01-01'):continue
            key=f"{e['series']}-s{e.get('season',1)}-e{e['episode']}-{e['version']}"
            if ledger.get(key) in ('sent','sending','uncertain'):continue
            ledger[key]='sending';private_write(ledger_path,ledger)
            version='Doblaje castellano' if e['version']=='dub-es' else 'Subtitulado en España'
            try:sender(f"🎬 {titles[e['series']]} · T{e.get('season',1)} E{e['episode']}\n{version} disponible.\n{e['source']}")
            except ValueError:
                ledger[key]='failed';private_write(ledger_path,ledger);raise ValueError('Telegram no ha confirmado el aviso') from None
            except Exception:
                ledger[key]='uncertain';private_write(ledger_path,ledger);raise RuntimeError('Aviso pendiente de comprobar; no se reenvía para evitar duplicados') from None
            ledger[key]='sent';private_write(ledger_path,ledger);sent+=1
        return {'sent':sent,'uncertain':sum(v in ('sending','uncertain') for v in ledger.values())}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--import-file',type=Path);parser.add_argument('--notify',action='store_true');args=parser.parse_args()
    if args.import_file:
        data=validate(json.loads(args.import_file.read_text()))
        with LOCK:private_write(ROOT/'schedule.json',data)
        print('Calendario validado y guardado; enlace privado conservado')
    if args.notify:print(json.dumps(notify_available()))

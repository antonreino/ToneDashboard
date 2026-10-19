"""Bounded public catalogue lookup. Only TVmaze API and its image CDN are fetched."""
import re
import unicodedata
import threading
import time

_API_LOCK=threading.Lock()
_LAST_REQUEST=0.0
from urllib.parse import urlsplit
import requests

ALIASES={'espiritusdelinframundo':'Daemons of the Shadow Realm','labrujadelsilencio':'Secrets of the Silent Witch','aoashi':'Aoashi','wistoriadevarasyespadas':'Wistoria: Wand and Sword'}

ALIASES.update({'mushokutensei':'Mushoku Tensei: Jobless Reincarnation','theunawareateliermeister':'The Unaware Atelier Master','hellsparadisejigokuraku':"Hell's Paradise",'easygoingterritorydefensebytheoptimisticlord':'Easygoing Territory Defense by the Optimistic Lord: Production Magic Turns a Nameless Village into the Strongest Fortified City','areturnermagicshouldbespecial':"A Returner's Magic Should Be Special"})

def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum())

def get_json(session,url,**kwargs):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname!='api.tvmaze.com' or parsed.port not in (None,443) or parsed.username or parsed.password:raise ValueError('Fuente de catálogo no permitida')
    global _LAST_REQUEST
    with _API_LOCK:
        pause=.55-(time.monotonic()-_LAST_REQUEST)
        if pause>0:time.sleep(pause)
        _LAST_REQUEST=time.monotonic()
        response=session.get(url,timeout=(4,12),allow_redirects=False,**kwargs)
    response.raise_for_status()
    if len(response.content)>2_000_000:raise ValueError('Respuesta de catálogo demasiado grande')
    return response.json()

def lookup(title):
    query=ALIASES.get(normalize(title),title)
    session=requests.Session();session.trust_env=False
    try:
        rows=get_json(session,'https://api.tvmaze.com/search/shows',params={'q':query})
        candidates=[r['show'] for r in rows if r['show'].get('type')=='Animation' and (r['show'].get('language')=='Japanese' or 'Anime' in r['show'].get('genres',[]))]
        matches=[s for s in candidates if normalize(s['name'])==normalize(query)]
        if len(matches)!=1:raise ValueError('No hay una coincidencia única. Prueba el título completo o su nombre en inglés.')
        show=matches[0];image=(show.get('image') or {}).get('original') or (show.get('image') or {}).get('medium')
        parsed=urlsplit(image or '')
        if parsed.scheme!='https' or parsed.hostname!='static.tvmaze.com' or parsed.username or parsed.password or parsed.port not in (None,443):raise ValueError('El catálogo todavía no tiene una portada válida para este anime')
        with session.get(image,timeout=(4,12),allow_redirects=False,stream=True) as response:
            response.raise_for_status();chunks=[];size=0
            for chunk in response.iter_content(65536):
                size+=len(chunk)
                if size>4_000_000:raise ValueError('Portada demasiado grande')
                chunks.append(chunk)
            poster=b''.join(chunks)
        if not poster.startswith(b'\xff\xd8\xff'):raise ValueError('La portada no es una imagen JPEG válida')
        result={'catalogue_title':show['name'],'tvmaze_id':show['id'],'metadata_source':show['url'],'cover_source':image,'catalogue_status':show['status'],'_poster_bytes':poster}
        next_link=show.get('_links',{}).get('nextepisode',{}).get('href','')
        country=(show.get('network') or show.get('webChannel') or {}).get('country') or {}
        if next_link and country.get('code')=='JP' and re.fullmatch(r'https://api\.tvmaze\.com/episodes/\d+',next_link):
            episode=get_json(session,next_link)
            from datetime import datetime
            from zoneinfo import ZoneInfo
            stamp=episode.get('airstamp')
            if stamp and type(episode.get('number')) is int and type(episode.get('season')) is int:
                result['_next_event']={'season':episode['season'],'episode':episode['number'],'date':datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Tokyo')).date().isoformat(),'version':'jp-original','region':'JP','source':episode['url']}
        return result
    except requests.RequestException:
        raise ValueError('No se pudo consultar el catálogo o descargar la portada. Inténtalo de nuevo.') from None
    finally:session.close()

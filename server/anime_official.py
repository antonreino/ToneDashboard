"""Small audited registry of official season announcements, separate from episodes."""
from datetime import date
from html import unescape
import re
import requests

SOURCES = {
    69007: {'url': 'https://anime.shangrilafrontier.com/onair/', 'season': 3, 'anchor': '3rd Season'},
}


def parse_premiere(text, source):
    text = unescape(re.sub(r'<[^>]+>', ' ', text))
    text = re.sub(r'\s+', ' ', text)
    matches=[]
    for anchor in re.finditer(re.escape(source['anchor']),text):
        match=re.search(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日',text[anchor.end():anchor.end()+700])
        if match:matches.append(match)
    if not matches:return None
    if len({m.groups() for m in matches})!=1:return None
    match=matches[0]
    day = date(*map(int, match.groups())).isoformat()
    return {'season': source['season'], 'date': day, 'region': 'JP', 'source': source['url'], 'basis': 'official-announcement'}


def lookup_premiere(tvmaze_id):
    source = SOURCES.get(tvmaze_id)
    if not source:return None
    session = requests.Session();session.trust_env = False
    try:
        with session.get(source['url'],timeout=(4,10),allow_redirects=False,stream=True) as response:
            response.raise_for_status();parts=[];size=0
            for part in response.iter_content(65536):
                size += len(part)
                if size > 700000:raise ValueError('Anuncio oficial demasiado grande')
                parts.append(part)
        result=parse_premiere(b''.join(parts).decode('utf-8'),source)
        if result is None:raise ValueError('No se pudo identificar una fecha inequívoca en la fuente oficial')
        return result
    finally:session.close()

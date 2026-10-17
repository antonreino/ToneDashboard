"""Dashboard adapter for the existing local aMule instance (one shared search)."""
import os
import re
import threading
import time
import uuid
from amule_ec import ECClient, Tag, AmuleError

class RequestError(Exception):
    def __init__(self,message,status=400):self.status=status;super().__init__(message)

def files(tags):
    result=[]
    for tag in tags:
        if tag.name not in (0x300,0x700):continue
        digest=tag.get(0x31e,tag.value)
        if not isinstance(digest,bytes) or len(digest)!=16:continue
        name=tag.get(0x301,'');size=tag.get(0x303,0);done=tag.get(0x306,0)
        if not isinstance(name,str) or not isinstance(size,int):continue
        result.append({'hash':digest.hex(),'name':name,'size':size,
                       'sources':tag.get(0x30a,0),'completed':done,
                       'speed':tag.get(0x307,0),'state':tag.get(0x308,0),
                       'progress':round(min(100,100*done/size),1) if size else 0})
    return sorted(result,key=lambda r:(-r['sources'],r['name'].casefold(),r['hash']))

class AmuleDashboard:
    def __init__(self,client_factory=None,clock=time.monotonic):
        self.lock=threading.Lock();self.clock=clock;self.factory=client_factory
        self.search_id='';self.query='';self.network='kad';self.started=0
        self.results={};self.cached=None;self.cached_at=0
    def client(self):
        if self.factory:return self.factory()
        credential=os.getenv('AMULE_EC_PASSWORD_HASH','')
        if os.getenv('AMULE_ENABLED','').lower()!='true' or not re.fullmatch(r'[0-9a-fA-F]{32}',credential):
            raise RequestError('El control local de aMule no está configurado.',503)
        return ECClient(credential)
    def _read(self,c):
        _,stats=c.request(0x0a);_,queue=c.request(0x0d,[Tag(4,2)])
        status={t.name:t.value for t in stats}
        results=[];progress=None
        if self.search_id:
            _,found=c.request(0x28,[Tag(4,2)]);results=files(found)
            _,p=c.request(0x29);progress=next((t.value for t in p if t.name==0x708),None)
        self.results={r['hash']:r for r in results}
        value={'ok':True,'query':self.query,'network':self.network,'search_id':self.search_id,
               'progress':progress if isinstance(progress,int) and progress<=100 else None,
               'results':results[:500],'total':len(results),'downloads':files(queue),
               'download_speed':status.get(0x201,0),'upload_speed':status.get(0x200,0),
               'kad_nodes':status.get(0x21b,0)}
        self.cached=value;self.cached_at=self.clock();return value
    def snapshot(self):
        with self.lock:
            if self.cached is not None and self.clock()-self.cached_at<2:return self.cached
            with self.client() as c:return self._read(c)
    def search(self,body):
        query=body.get('query');network=body.get('network','kad');kind=body.get('type','')
        if not isinstance(query,str) or not 2<=len(query.strip())<=160 or any(ord(x)<32 or ord(x)==127 for x in query):
            raise RequestError('Escribe una búsqueda de entre 2 y 160 caracteres.')
        if network not in ('kad','local','global') or kind not in ('','Video','Audio','Doc','Iso','Arc','Pro','Image'):
            raise RequestError('Red o tipo de archivo no válido.')
        with self.lock:
            if self.search_id and self.clock()-self.started<5:raise RequestError('Espera unos segundos antes de iniciar otra búsqueda.',429)
            with self.client() as c:
                c.request(0x26,[Tag(0x701,{'local':0,'global':1,'kad':2}[network],[Tag(0x702,query.strip()),Tag(0x705,kind)])])
            self.query=query.strip();self.network=network;self.search_id=uuid.uuid4().hex
            self.started=self.clock();self.results={};self.cached=None
            return {'ok':True,'search_id':self.search_id,'query':self.query}
    def download(self,body):
        digest=body.get('hash');search_id=body.get('search_id')
        if not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{32}',digest):raise RequestError('Resultado no válido.')
        with self.lock:
            if not self.search_id or search_id!=self.search_id:raise RequestError('La búsqueda ha cambiado. Actualiza los resultados.',409)
            if digest not in self.results:raise RequestError('Este resultado ya no está disponible. Actualiza la búsqueda.',409)
            with self.client() as c:
                _,queue=c.request(0x0d,[Tag(4,2)])
                if any(r['hash']==digest for r in files(queue)):return {'ok':True,'already_queued':True}
                # Verify that aMule still knows this exact hash, even if its GUI performed another search.
                _,current=c.request(0x28,[Tag(4,2)])
                if digest not in {r['hash'] for r in files(current)}:raise RequestError('La búsqueda de aMule ha cambiado. Actualiza los resultados.',409)
                op,_=c.request(0x2a,[Tag(0x300,bytes.fromhex(digest),[Tag(0x30f,0)])])
                if op not in (1,6):raise AmuleError('aMule no confirmó la descarga')
                _,confirmed=c.request(0x0d,[Tag(4,2)])
                if digest not in {r['hash'] for r in files(confirmed)}:raise AmuleError('La descarga no aparece en la cola de aMule')
                self.cached=None
                return {'ok':True,'already_queued':False}

bridge=AmuleDashboard()
def handle(method,path,body=None):
    try:
        if method=='GET' and path=='/api/amule':return bridge.snapshot(),200
        if method=='POST' and path=='/api/amule/search':return bridge.search(body),202
        if method=='POST' and path=='/api/amule/download':return bridge.download(body),202
        return {'error':'Ruta aMule no válida'},404
    except RequestError as exc:return {'error':str(exc)},exc.status
    except (AmuleError,OSError,ValueError):return {'error':'No se pudo comunicar con aMule. Comprueba que esté abierto y conectado.'},503

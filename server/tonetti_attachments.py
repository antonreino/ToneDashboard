"""Private, bounded attachment ingestion; never execute uploaded content."""
import base64
from datetime import datetime,timezone
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import threading

UPLOAD_LOCK=threading.Lock()
import uuid
import zipfile
import xml.etree.ElementTree as ET

MAX_FILE=8*1024*1024
TEXT_SUFFIXES={'.txt','.md','.csv','.json','.log','.py','.js','.ts','.css','.html','.xml','.yaml','.yml','.swift','.sh'}


def extract(raw,suffix):
    if suffix in {'.jpg','.jpeg','.png','.webp'}:
        from PIL import Image,ImageOps
        Image.MAX_IMAGE_PIXELS=16000000
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            im=Image.open(io.BytesIO(raw))
            if im.format not in {'JPEG','PNG','WEBP'}:raise ValueError('Formato de imagen no admitido')
            im.load();im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1280,1280))
            output=io.BytesIO();im.save(output,'JPEG',quality=85)
        return 'image','Imagen preparada para el modelo visual.',output.getvalue()
    if suffix=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:raise ValueError('El PDF está cifrado; adjunta una copia sin contraseña')
        if len(reader.pages)>50:raise ValueError('Máximo 50 páginas por documento')
        parts=[];size=0
        for page in reader.pages:
            text=page.extract_text() or '';parts.append(text);size+=len(text)
            if size>60000:break
        text='\n'.join(parts)
    elif suffix=='.docx':
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(x.file_size for x in archive.infolist())>40*1024*1024:raise ValueError('Documento expandido demasiado grande')
            info=archive.getinfo('word/document.xml')
            if info.file_size>4*1024*1024:raise ValueError('Documento demasiado grande')
            document=ET.fromstring(archive.read(info))
            text='\n'.join(''.join(p.itertext()) for p in document.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
    elif suffix in TEXT_SUFFIXES:
        text=raw.decode('utf-8-sig')
        if '\x00' in text:raise ValueError('El archivo no es texto UTF-8')
    else:raise ValueError('Formato no admitido: utiliza foto, PDF, DOCX o texto UTF-8')
    if not text.strip():raise ValueError('No se encontró texto; los PDF escaneados necesitan OCR o adjuntar sus páginas como fotos')
    return 'document',text[:60000]+('\n[Texto limitado a 60.000 caracteres]' if len(text)>60000 else ''),b''


def upload(root,body,connect):
    if not UPLOAD_LOCK.acquire(blocking=False):return {"error":"Ya hay un adjunto procesándose; espera a que termine"},409
    try:return _upload(root,body,connect)
    finally:UPLOAD_LOCK.release()

def _upload(root,body,connect):
    if not isinstance(body,dict) or set(body)!={'name','data'}:raise ValueError('Adjunto no válido')
    name=body['name'];encoded=body['data']
    if not isinstance(name,str) or not 1<=len(name)<=160 or any(ord(c)<32 for c in name) or '/' in name or '\\' in name:raise ValueError('Nombre de archivo no válido')
    if not isinstance(encoded,str) or len(encoded)>11200000:raise ValueError('Máximo 8 MB por adjunto')
    try:raw=base64.b64decode(encoded,validate=True)
    except Exception:raise ValueError('Adjunto no válido') from None
    if not 0<len(raw)<=MAX_FILE:raise ValueError('Máximo 8 MB por adjunto')
    folder=Path(root)/'attachments';folder.mkdir(mode=0o700,exist_ok=True)
    if sum(p.stat().st_size for p in folder.iterdir() if p.is_file())+len(raw)>512*1024*1024:raise ValueError('Almacenamiento de adjuntos lleno (512 MB)')
    # Parse hostile documents in a disposable process with a time and memory limit.
    with tempfile.TemporaryDirectory(prefix='tone-attachment-') as temporary:
        source=Path(temporary)/'input';target=Path(temporary)/'output'
        source.write_bytes(raw);source.chmod(0o600)
        with source.open('rb') as inp,target.open('w+b') as out:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),Path(name).suffix.lower()],stdin=inp,stdout=out,stderr=subprocess.DEVNULL)
            deadline=time.monotonic()+20
            try:
                while process.poll() is None:
                    if time.monotonic()>deadline:raise ValueError('El archivo tardó demasiado en procesarse')
                    if sys.platform=='darwin':
                        rss=subprocess.run(['/bin/ps','-o','rss=','-p',str(process.pid)],capture_output=True,text=True,timeout=1)
                        if rss.stdout.strip().isdigit() and int(rss.stdout.strip())>1536*1024:raise ValueError('El archivo requiere demasiada memoria')
                    time.sleep(.1)
                if process.returncode:
                    out.seek(0)
                    if process.returncode==2:
                        issue=json.loads(out.read(2048));raise ValueError(str(issue['error'])[:200])
                    raise ValueError('No se pudo leer el adjunto. Comprueba formato, tamaño y que no esté cifrado.')
                out.seek(0);result=out.read(4*1024*1024)
            finally:
                if process.poll() is None:process.kill()
                process.wait()
    data=json.loads(result);ident=uuid.uuid4().hex
    try:
        for ending,content in (('.original',raw),('.jpg',base64.b64decode(data['preview']))):
            if not content:continue
            fd=os.open(folder/(ident+ending),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as handle:handle.write(content)
        with connect(root) as db:db.execute('INSERT INTO attachments VALUES(?,?,?,?,?)',(ident,name,data['kind'],data['text'],datetime.now(timezone.utc).isoformat()))
    except Exception:
        for p in folder.glob(ident+'.*'):p.unlink()
        raise
    return {'id':ident,'name':name,'kind':data['kind'],'note':'Imagen para análisis visual' if data['kind']=='image' else 'Texto extraído; hasta 60.000 caracteres. El contexto de cada respuesta es limitado.'},201


def get(root,ident,connect,preview=False):
    if not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Adjunto no encontrado')
    with connect(root) as db:row=db.execute('SELECT name,kind,text FROM attachments WHERE id=?',(ident,)).fetchone()
    if not row:raise ValueError('Adjunto no encontrado')
    path=Path(root)/'attachments'/(ident+('.jpg' if preview else '.original'))
    if path.is_symlink() or not path.is_file():raise ValueError('Adjunto no encontrado')
    return row,path


def context(root,ids,connect):
    texts=[];images=[]
    for ident in ids:
        row,path=get(root,ident,connect,preview=False)
        name,kind,text=row
        if kind=='image':
            _,preview=get(root,ident,connect,preview=True)
            images.append(base64.b64encode(preview.read_bytes()).decode())
        else:texts.append(name+':\n'+text[:12000])
    if len(images)>2:raise ValueError('Máximo dos imágenes por mensaje')
    return '\n\n'.join(texts)[:20000],images


if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))
    # macOS reserves a large address space; RLIMIT_AS is not supported reliably there.
    if sys.platform!='darwin':resource.setrlimit(resource.RLIMIT_AS,(1536*1024*1024,1536*1024*1024))
    try:
        kind,text,preview=extract(sys.stdin.buffer.read(MAX_FILE+1),sys.argv[1])
        print(json.dumps({'kind':kind,'text':text,'preview':base64.b64encode(preview).decode()}))
    except ValueError as exc:
        print(json.dumps({"error":str(exc)[:200]}));sys.exit(2)
    except Exception:sys.exit(1)


def backup_files(root,directory):
    """Copy immutable attachment objects once; daily SQLite snapshots share the archive."""
    import hashlib
    import shutil
    source=Path(root)/'attachments';directory=Path(directory)
    if not source.is_dir():return 0
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    def digest(path):
        with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()
    count=0
    for path in source.iterdir():
        if path.is_symlink() or not path.is_file() or not re.fullmatch('[a-f0-9]{32}\\.(original|jpg)',path.name):continue
        target=directory/path.name
        if target.is_symlink():raise ValueError('Destino de copia no válido')
        if target.exists():
            if digest(target)!=digest(path):raise ValueError('Un adjunto inmutable cambió; revisar la copia')
        else:
            temporary=directory/(uuid.uuid4().hex+'.partial')
            try:
                fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'wb') as out,path.open('rb') as inp:shutil.copyfileobj(inp,out)
                if digest(temporary)!=digest(path):raise ValueError('La copia del adjunto no coincide')
                os.replace(temporary,target)
            finally:temporary.unlink(missing_ok=True)
        count+=1
    return count

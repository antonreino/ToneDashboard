"""Small synchronous aMule EC 0x0204 client. Loopback only; no shell commands.

Wire format and opcode identifiers: official aMule EC protocol (src/libs/ec).
We advertise no compression/UTF8-number capabilities, so replies use fixed
network-order integers. Every connection is bounded and closed after use.
"""
from dataclasses import dataclass, field
import hashlib
import socket
import struct

MAX_PACKET=8*1024*1024
class AmuleError(Exception): pass

@dataclass
class Tag:
    name:int
    value:object
    children:list=field(default_factory=list)
    def get(self,name,default=None):
        return next((t.value for t in self.children if t.name==name),default)

def encode_tag(tag):
    v=tag.value
    if isinstance(v,str):kind,data=6,v.encode('utf8')+b'\0'
    elif isinstance(v,bytes):kind,data=9,v
    elif isinstance(v,int) and 0<=v<2**64:
        width=next(n for n in (1,2,4,8) if v<2**(8*n));kind={1:2,2:3,4:4,8:5}[width];data=v.to_bytes(width,'big')
    else:raise AmuleError('Tipo EC no válido')
    nested=b''.join(encode_tag(t) for t in tag.children)
    return struct.pack('!HBI',(tag.name<<1)|bool(tag.children),kind,len(data)+len(nested))+(struct.pack('!H',len(tag.children)) if tag.children else b'')+nested+data

def decode_packet(data):
    pos=0;total=0
    def take(n):
        nonlocal pos
        if n<0 or pos+n>len(data):raise AmuleError('Respuesta aMule incompleta')
        value=data[pos:pos+n];pos+=n;return value
    def tags(depth=0):
        nonlocal total
        if depth>12:raise AmuleError('Respuesta aMule demasiado anidada')
        count=int.from_bytes(take(2),'big');result=[]
        total+=count
        if total>40000:raise AmuleError('Demasiados campos EC')
        for _ in range(count):
            name,kind,length=struct.unpack('!HBI',take(7));start=pos
            if length>MAX_PACKET:raise AmuleError('Campo EC demasiado grande')
            children=tags(depth+1) if name&1 else []
            children_bytes=pos-start-(2 if name&1 else 0)
            raw=take(length-children_bytes)
            if kind in (2,3,4,5):
                if len(raw)!={2:1,3:2,4:4,5:8}[kind]:raise AmuleError('Entero EC inválido')
                value=int.from_bytes(raw,'big')
            elif kind==6:value=raw.rstrip(b'\0').decode('utf8',errors='replace')
            else:value=raw
            result.append(Tag(name>>1,value,children))
        return result
    opcode=take(1)[0];result=tags()
    if pos!=len(data):raise AmuleError('Datos EC sobrantes')
    return opcode,result

class ECClient:
    def __init__(self,password_hash,timeout=4):
        self.password_hash=password_hash;self.timeout=timeout;self.sock=None
    def __enter__(self):
        try:
            self.sock=socket.create_connection(('127.0.0.1',4712),timeout=self.timeout)
            op,tags=self.request(2,[Tag(0x100,'ToneDashboard'),Tag(0x101,'1.0.0'),Tag(2,0x0204)])
            salt=next((t.value for t in tags if t.name==11),None)
            if op!=0x4f or not isinstance(salt,int):raise AmuleError('aMule no acepta la autenticación EC')
            salted=hashlib.md5(format(salt,'X').encode()).hexdigest()
            digest=hashlib.md5((self.password_hash.lower()+salted).encode()).digest()
            op,_=self.request(0x50,[Tag(1,digest)])
            if op!=4:raise AmuleError('Credencial local de aMule rechazada')
            return self
        except Exception:
            self.__exit__(None,None,None);raise
    def __exit__(self,*args):
        if self.sock:self.sock.close();self.sock=None
    def _read(self,n):
        value=b''
        while len(value)<n:
            part=self.sock.recv(n-len(value))
            if not part:raise AmuleError('aMule cerró la conexión')
            value+=part
        return value
    def request(self,opcode,tags=()):
        body=bytes([opcode])+struct.pack('!H',len(tags))+b''.join(encode_tag(t) for t in tags)
        self.sock.sendall(struct.pack('!II',0x20,len(body))+body)
        flags,length=struct.unpack('!II',self._read(8))
        if flags!=0x20 or not 3<=length<=MAX_PACKET:raise AmuleError('Formato o tamaño EC no compatible')
        op,reply=decode_packet(self._read(length))
        if op==5:raise AmuleError('aMule no pudo completar la operación')
        return op,reply

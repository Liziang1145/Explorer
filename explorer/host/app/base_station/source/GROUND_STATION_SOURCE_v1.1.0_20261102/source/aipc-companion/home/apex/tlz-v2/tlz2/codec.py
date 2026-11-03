import dataclasses,math,struct

MAX_MESSAGE=1100
HEADER=struct.Struct('!4sBBHHHIQIIQQIIQ')
TYPES={0x101,0x102,0x103,0x104,0x105,0x201,0x202,0x203,0x204,0x205,0x301,0x302,0x303,0x401,0x402}
SIZES={1:10,2:16,3:16,4:22}
class Invalid(ValueError):pass
def uint(v,bits=64):
 if type(v)!=int or not 0<=v<1<<bits:raise Invalid('unsigned integer required')
 return v
def _head(major,n):
 if n<24:return bytes([major*32+n])
 for size,add in [(1,24),(2,25),(4,26),(8,27)]:
  if n<1<<(8*size):return bytes([major*32+add])+n.to_bytes(size,'big')
 raise Invalid('integer overflow')
def dumps(v,depth=0):
 if depth>8:raise Invalid('CBOR depth')
 if v is None:return b'\xf6'
 if type(v)==bool:return b'\xf5' if v else b'\xf4'
 if type(v)==int:return _head(0,v) if v>=0 else _head(1,-1-v)
 if type(v)==float:
  if not math.isfinite(v):raise Invalid('nonfinite float')
  try:return b'\xfa'+struct.pack('!f',v)
  except OverflowError:raise Invalid('float32 overflow')
 if type(v) in (bytes,str):
  raw=v.encode('utf-8') if type(v)==str else v
  return _head(3 if type(v)==str else 2,len(raw))+raw
 if type(v) in (tuple,list):return _head(4,len(v))+b''.join(dumps(x,depth+1) for x in v)
 if type(v)==dict:
  for k in v:uint(k)
  return _head(5,len(v))+b''.join(dumps(k,depth+1)+dumps(v[k],depth+1) for k in sorted(v))
 raise Invalid('unsupported CBOR type')
def loads(raw,limit=MAX_MESSAGE):
 if not isinstance(raw,bytes) or len(raw)>limit:raise Invalid('CBOR size')
 pos=0
 def take(n):
  nonlocal pos
  if n<0 or pos+n>len(raw):raise Invalid('truncated CBOR')
  b=raw[pos:pos+n];pos+=n;return b
 def read(depth=0):
  if depth>8:raise Invalid('CBOR depth')
  b=take(1)[0];major,add=b>>5,b&31
  if major==7:
   if add in (20,21):return add==21
   if add==22:return None
   if add==26:
    f=struct.unpack('!f',take(4))[0]
    if not math.isfinite(f):raise Invalid('nonfinite float')
    return f
   raise Invalid('only float32 / bool / null allowed')
  if major==6 or add>=28:raise Invalid('tag or indefinite CBOR forbidden')
  n=add if add<24 else int.from_bytes(take({24:1,25:2,26:4,27:8}[add]),'big')
  if major==0:return n
  if major==1:return -1-n
  if major in (2,3):
   b=take(n)
   try:return b if major==2 else b.decode('utf-8')
   except UnicodeError:raise Invalid('UTF8')
  if n>len(raw):raise Invalid('container too large')
  if major==4:return [read(depth+1) for _ in range(n)]
  if major==5:
   out={}
   for _ in range(n):
    k=read(depth+1);uint(k)
    if k in out:raise Invalid('duplicate CBOR key')
    out[k]=read(depth+1)
   return out
  raise Invalid('CBOR type')
 v=read()
 if pos!=len(raw):raise Invalid('trailing CBOR')
 return v
@dataclasses.dataclass(frozen=True)
class Packet:
 kind:int;session:int;source:int;stream:int;seq:int;origin:int;epoch:int;ttl:int;trace:int;body:dict
 def encode(self):
  for value,bits in [(self.kind,16),(self.session,64),(self.source,32),(self.stream,32),(self.seq,64),(self.origin,64),(self.epoch,32),(self.ttl,32),(self.trace,64)]:uint(value,bits)
  body=dumps(self.body);raw=HEADER.pack(b'TLZ2',2,0,self.kind,0,64,len(body),self.session,self.source,self.stream,self.seq,self.origin,self.epoch,self.ttl,self.trace)+body
  if len(raw)>MAX_MESSAGE:raise Invalid('application message exceeds 1100 bytes')
  return raw
 def relay(self,session,body=None):return dataclasses.replace(self,session=session,body=self.body if body is None else body)
def decode(raw):
 if not isinstance(raw,bytes) or not 64<=len(raw)<=MAX_MESSAGE:raise Invalid('packet size')
 magic,major,minor,kind,flags,hlen,n,sess,source,stream,seq,origin,epoch,ttl,trace=HEADER.unpack(raw[:64])
 if (magic,major,minor,flags,hlen)!=(b'TLZ2',2,0,0,64) or n!=len(raw)-64 or kind not in TYPES or not seq:raise Invalid('header/version/type/length')
 body=loads(raw[64:])
 if type(body)!=dict:raise Invalid('body map')
 return Packet(kind,sess,source,stream,seq,origin,epoch,ttl,trace,body)
def vec(v,n=3):
 if not isinstance(v,list) or len(v)!=n or any(type(x)!=float or not math.isfinite(x) for x in v):raise Invalid('float32 vector')
 return v
def pose(v,frames):
 if type(v)!=dict or uint(v.get(0),32) not in frames:raise Invalid('unknown reference frame')
 vec(v.get(1));q=vec(v.get(2),4);norm=math.sqrt(sum(x*x for x in q))
 if abs(norm-1)>1e-3:raise Invalid('quaternion normalization')
def control(b,frames,revision,limits):
 for k in [0,1,2,3,4,5,6,15,16]:uint(b.get(k))
 if 19 in b:raise Invalid('operator cannot supply relay trace')
 if b[1]&~63 or b[2]&~255 or b[3]>2 or b[4]>2 or b[5]>2:raise Invalid('mode or mask')
 if b[6]!=revision:raise Invalid('BAD_REFERENCE')
 fields={0:7,1:8,2:9,3:10,4:11,5:12,6:13,7:14}
 for bit,key in fields.items():
  if b[2]&(1<<bit) and key not in b:raise Invalid('valid field missing')
 for key in (7,9,10):
  if key in b:pose(b[key],frames)
 for key in (11,12):
  if key in b:
   if any(abs(x)>limits['joint_rad'] for x in vec(b[key],6)):raise Invalid('joint range')
 if 8 in b:
  t=b[8]
  if t.get(0)!=limits['base_frame_id']:raise Invalid('twist frame')
  if any(abs(x)>limits['base_mps'] for x in vec(t.get(1))) or any(abs(x)>limits['base_radps'] for x in vec(t.get(2))):raise Invalid('twist range')
 for key in (13,14):
  if key in b:
   g=b[key];mode=g.get(0);x=g.get(1)
   if type(x)!=float or mode not in (0,1,2) or not math.isfinite(x) or (mode==0 and not 0<=x<=1) or (mode==1 and not 0<=x<=limits['gripper_m']) or (mode==2 and not -1<=x<=1):raise Invalid('gripper range')
 for mode,options in [(b[3],{1:0,2:1}),(b[4],{1:2,2:4}),(b[5],{1:3,2:5})]:
  if mode and not b[2]&(1<<options[mode]):raise Invalid('mode target missing')
 return b

"""TLZV v1 validation and lossless AVC fMP4 packaging using original microsecond PTS."""
import re,struct
HEADER=struct.Struct('!4sBBHIQHHII')
def parse_header(raw):
 if len(raw)!=32:raise ValueError('TLZV header length')
 magic,version,flags,length,seq,pts,width,height,size,reserved=HEADER.unpack(raw)
 if magic!=b'TLZV' or version!=1 or flags&~1 or length!=32 or reserved:raise ValueError('Invalid TLZV header')
 if not 0<size<=8*1024*1024 or not 1<=width<=1920 or not 1<=height<=1920:raise ValueError('Invalid TLZV dimensions or payload size')
 return {'seq':seq,'pts':pts,'width':width,'height':height,'size':size,'key':bool(flags&1)}
def box(kind,data=b''):return struct.pack('!I4s',len(data)+8,kind.encode())+data
def full(kind,data=b'',version=0,flags=0):return box(kind,bytes([version])+flags.to_bytes(3,'big')+data)
def u32(*values):return struct.pack('!'+'I'*len(values),*values)
MATRIX=u32(65536,0,0,0,65536,0,0,0,1073741824)
def nals(data):
 parts=re.split(b'\x00\x00\x00\x01|\x00\x00\x01',data)
 if parts[0]:raise ValueError('Expected Annex-B access unit')
 result=[p for p in parts[1:] if p]
 if not result:raise ValueError('Empty H264 access unit')
 return result
def initialization(sps,pps,width,height):
 if len(sps)<4 or len(sps)>65535 or not pps or len(pps)>65535:raise ValueError('Invalid SPS/PPS')
 avcc=bytes([1])+sps[1:4]+b'\xff\xe1'+len(sps).to_bytes(2,'big')+sps+b'\x01'+len(pps).to_bytes(2,'big')+pps
 entry=struct.pack('!6sH16sHHIIIH32sHH',b'\0'*6,1,b'\0'*16,width,height,0x480000,0x480000,0,1,b'\0'*32,24,65535)
 stbl=box('stbl',full('stsd',u32(1)+box('avc1',entry+box('avcC',avcc)))+full('stts',u32(0))+full('stsc',u32(0))+full('stsz',u32(0,0))+full('stco',u32(0)))
 dinf=box('dinf',full('dref',u32(1)+full('url ',flags=1)))
 minf=box('minf',full('vmhd',b'\0'*8,flags=1)+dinf+stbl)
 mdia=box('mdia',full('mdhd',u32(0,0,1000000,0)+struct.pack('!HH',0x55c4,0))+full('hdlr',u32(0)+b'vide'+b'\0'*12+b'VR view\0')+minf)
 tkhd=full('tkhd',u32(0,0,1,0,0)+b'\0'*8+b'\0'*8+MATRIX+u32(width<<16,height<<16),flags=7)
 mvhd=full('mvhd',u32(0,0,1000000,0,65536)+struct.pack('!H',256)+b'\0'*10+MATRIX+b'\0'*24+u32(2))
 return box('ftyp',b'isom'+u32(512)+b'isomiso6avc1mp41')+box('moov',mvhd+box('trak',tkhd+mdia)+box('mvex',full('trex',u32(1,1,0,0,0))))
def fragment(seq,pts,duration,access_unit,key):
 sample=b''.join(u32(len(nal))+nal for nal in nals(access_unit) if nal[0]&31 not in (7,8,9))
 if not sample:raise ValueError('No coded frame in access unit')
 def moof(offset):return box('moof',full('mfhd',u32(seq))+box('traf',full('tfhd',u32(1),flags=0x020000)+full('tfdt',struct.pack('!Q',pts),version=1)+full('trun',u32(1,offset,duration,len(sample),0x02000000 if key else 0x01010000),flags=0x701)))
 header=moof(0);return moof(len(header)+8)+box('mdat',sample)
class Muxer:
 def __init__(self):self.init=None;self.codec=None;self.pending=None;self.base=None;self.count=0;self.signature=None
 def push(self,meta,data):
  ns=nals(data);sps=next((n for n in ns if n[0]&31==7),None);pps=next((n for n in ns if n[0]&31==8),None)
  if sps and pps:
   signature=(sps,pps,meta['width'],meta['height'])
   if self.signature and signature!=self.signature:raise ValueError('Encoder configuration changed; reconnect required')
   self.signature=signature;self.init=initialization(*signature);self.codec='avc1.'+sps[1:4].hex().upper()
  if self.base is None:
   if not meta['key'] or self.init is None:return None
   self.base=meta['pts']
  previous=self.pending;self.pending=(meta,data)
  if not previous:return None
  old,payload=previous;duration=meta['pts']-old['pts']
  if not 0<duration<=10000000:raise ValueError('Non-monotonic or discontinuous VR PTS')
  self.count+=1;return {'data':fragment(self.count,old['pts']-self.base,duration,payload,old['key']),'key':old['key'],'pts_us':str(old['pts']),'seq':old['seq'],'width':old['width'],'height':old['height']}

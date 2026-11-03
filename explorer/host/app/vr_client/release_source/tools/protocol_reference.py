"""Legacy VR wire helpers. No sockets, no vehicle commands are sent by this file."""
import math,struct

def f32(v):return struct.unpack('<f',struct.pack('<f',v))[0]

def crc_legacy_bits(data,bits):
    """Match CRCpp CalculateBits exactly, including its partial-byte XOR behavior."""
    crc=0;whole,tail=divmod(bits,8)
    for byte in data[:whole]:
        crc^=byte
        for _ in range(8):crc=(crc>>1)^(0x8408 if crc&1 else 0)
    if tail:
        crc^=data[whole]
        for _ in range(tail):crc=(crc>>1)^(0x8408 if crc&1 else 0)
    return crc&0xffff

def encode_float(value,bits,limit):
    value,limit=f32(value),f32(limit)
    if not math.isfinite(value) or not -limit<=value<=limit:raise ValueError('Value out of protocol range')
    return int(f32(value+limit)/(2.0*limit)*((1<<bits)-1)+.5)

def decode_float(value,bits,limit):return (value&((1<<bits)-1))/((1<<bits)-1)*(2*limit)-limit
def encode3(v,limit):return (encode_float(v[0],10,limit)<<20)|(encode_float(v[1],10,limit)<<10)|encode_float(v[2],10,limit)
def decode3(v,limit):return tuple(decode_float(v>>s,10,limit) for s in (20,10,0))
def encode2(v):return (encode_float(v[0],16,1)<<16)|encode_float(v[1],16,1)
def encode_quaternion(q):
    q=tuple(map(f32,q))
    if abs(sum(v*v for v in q)-1)>.001:raise ValueError('Quaternion must be normalized, x/y/z/w order')
    index=max(range(4),key=lambda i:abs(q[i]));sign=1 if q[index]>=0 else -1
    rest=[sign*q[i] for i in range(4) if i!=index]
    return (index<<30)|encode3(rest,.70710678118)
def decode_quaternion(word):
    index=word>>30;rest=iter(decode3(word,.70710678118));q=[]
    xyz=decode3(word,.70710678118);major=math.sqrt(max(0,1-sum(x*x for x in xyz)))
    for i in range(4):q.append(major if i==index else next(rest))
    return tuple(q)

def encode_status(*,mask=0,count=0,time=0,base=(0,0,0),base_q=(0,0,0,1),grips=None,forces=(0,0)):
    """70-byte state. Gripper positions are relative to robot base."""
    if grips is None:grips=[((0,0,0),(0,0,0,1)) for _ in range(4)]
    out=bytearray(70);struct.pack_into('<HHIQ3fI',out,0,0xdcdc,mask,count,time,*base,encode_quaternion(base_q))
    for i,(position,quaternion) in enumerate(grips):struct.pack_into('<II',out,32+i*8,encode3(position,1.2),encode_quaternion(quaternion))
    struct.pack_into('<I',out,64,encode2(forces));struct.pack_into('<H',out,68,crc_legacy_bits(out,68));return bytes(out)

def decode_control(data):
    if len(data)!=78 or data[:2]!=b'\xfb\xfb':raise ValueError('Expected 78-byte control packet')
    if struct.unpack_from('<H',data,76)[0]!=crc_legacy_bits(data,76):raise ValueError('Legacy CRC mismatch')
    header,mask,count,time=struct.unpack_from('<HHIQ',data)
    word=lambda off:struct.unpack_from('<I',data,off)[0]
    return {'mask':mask,'count':count,'time':time,'base':struct.unpack_from('<3f',data,16),'base_q':decode_quaternion(word(28)),
            'left_hand':decode3(word(56),1.2),'left_q':decode_quaternion(word(60)),
            'right_hand':decode3(word(64),1.2),'right_q':decode_quaternion(word(68)),
            'grips':(decode_float(word(72)>>16,16,1),decode_float(word(72),16,1))}

def morton(x,y,z):
    axes=[math.floor(f32(f32(v)*100))+1048576 for v in (x,y,z)]
    if any(not 0<=v<(1<<21) for v in axes):raise ValueError('Point coordinate outside Morton range')
    code=0
    for axis,value in enumerate(axes):
        for bit in range(21):code|=((value>>bit)&1)<<(bit*3+axis)
    return code

def cloud_packet(points,packet_id=0):
    """points: (x,y,z,0xRRGGBBAA[,normal_flags]); pads by repeating last point.
    Use full 84-point packets to avoid the legacy receiver's short-packet gaps.
    """
    if not 1<=len(points)<=84:raise ValueError('Need 1..84 points')
    points=list(points)+[points[-1]]*(84-len(points))
    out=bytearray(struct.pack('<HHHHI',0xd0fd,packet_id,84,0,84))
    for point in points:
        x,y,z,color=point[:4];normal=point[4] if len(point)>4 else 0
        out+=struct.pack('<IIQ',normal,color,morton(x,y,z))
    assert len(out)==1356;return bytes(out)

if __name__=='__main__':
    print('status_zero:',encode_status().hex())
    print('one point padded packet length:',len(cloud_packet([(1,2,3,0xffffffff)])))

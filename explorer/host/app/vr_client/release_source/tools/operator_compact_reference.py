"""Independent server-side OPC1 codec and Java interoperability vector checks.

Python 3 + cbor2==5.6.5. No network/robot operations. All structs are network byte order.
"""
from pathlib import Path
import argparse, copy, json, math, struct, sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'v2_deps' / 'test_python'))
import cbor2

def validate_face_buttons(value):
    if not isinstance(value,dict) or not {0,1,2} <= set(value) or set(value)-{0,1,2,3,4}: raise ValueError('ABXY keys')
    if any(type(key) is not int for key in value): raise ValueError('ABXY integer keys')
    if type(value[0]) is not int or value[0]!=1: raise ValueError('ABXY revision')
    for key in value:
        if type(value[key]) is not int: raise ValueError('ABXY integer value')
    if not 0<=value[1]<=15 or not 0<=value[2]<=15 or value[2]&~value[1]: raise ValueError('ABXY validity')
    if (3 in value)!=(4 in value): raise ValueError('ABXY touch pair')
    if 3 in value and (not 0<=value[3]<=15 or not 0<=value[4]<=15 or value[3]&~value[4]): raise ValueError('ABXY touch validity')

def _pose_write(pose, quantized):
    xyz, q = pose[1], pose[2]
    if len(xyz) != 3 or len(q) != 4 or not all(math.isfinite(x) for x in xyz+q):
        raise ValueError('pose shape/finite')
    if abs(math.sqrt(sum(x*x for x in q))-1) > .001:
        raise ValueError('quaternion norm')
    if not quantized:
        return struct.pack('!7f', *(xyz+q))
    def rnd(value, scale, lo, hi):
        n=math.copysign(math.floor(abs(value*scale)+.5),value)
        if not lo <= n <= hi: raise ValueError('quantization range')
        return int(n)
    return struct.pack('!3i4h', *[rnd(x,10000,-2147483648,2147483647) for x in xyz],
                       *[rnd(x,32767,-32767,32767) for x in q])

def pack(source, profile='opbin1'):
    if 13 in source: validate_face_buttons(source[13])
    if profile not in ('opbin1','opq1') or 12 in source: raise ValueError('profile/collision')
    mask=0; valid=0; poses=[]
    for bit,key in enumerate((3,4,5)):
        if key in source: mask|=1<<bit;poses.append(source[key])
    if source.get(1,0)&7 != mask&7: raise ValueError('tracking presence')
    if 6 in source:
        view=source[6]
        if set(view)!={0,1,2,3} or not mask&1: raise ValueError('view shape')
        mask|=8;poses += [view[0],view[2]]
    if 11 in source:
        controls=source[11];valid=controls[7]
        if controls[0]!=1 or not isinstance(valid,int) or valid<0 or valid&~63: raise ValueError('input revision/validity')
        if set(controls)!={0,7}|{i+1 for i in range(6) if valid&(1<<i)}: raise ValueError('input keys')
        mask|=16
    frame=0
    for pose in poses:
        if set(pose)!={0,1,2} or not 1<=pose[0]<=0xffffffff: raise ValueError('pose fields/frame')
        if frame and frame!=pose[0]: raise ValueError('mixed pose frames')
        frame=pose[0]
    quantized=profile=='opq1'
    blob=bytearray(struct.pack('!2sBBBBHI',b'OP',1,int(quantized),mask,valid,0,frame))
    for pose in poses: blob.extend(_pose_write(pose,quantized))
    if mask&8:
        fov=source[6][1]+source[6][3]
        if len(fov)!=8 or not all(math.isfinite(x) for x in fov): raise ValueError('FOV')
        blob.extend(struct.pack('!8f',*fov))
    if mask&16:
        for bit in range(6):
            if valid&(1<<bit):
                values=[source[11][bit+1]] if bit<4 else source[11][bit+1]
                if len(values)!=(1 if bit<4 else 2): raise ValueError('input shape')
                if not all(math.isfinite(v) and (0<=v<=1 if bit<4 else -1<=v<=1) for v in values): raise ValueError('input range')
                blob.extend(struct.pack('!'+'f'*len(values),*values))
    out={k:copy.deepcopy(v) for k,v in source.items() if k not in (3,4,5,6,11)}
    out[12]=bytes(blob)
    return out

def expand(envelope, negotiated):
    if 13 in envelope: validate_face_buttons(envelope[13])
    if any(k in envelope for k in (3,4,5,6,11)): raise ValueError('mixed format')
    blob=envelope.get(12)
    if not isinstance(blob,bytes) or len(blob)<12: raise ValueError('missing OPC1')
    magic,revision,codec,mask,valid,reserved,frame=struct.unpack_from('!2sBBBBHI',blob)
    if (magic,revision)!=(b'OP',1) or codec not in (0,1) or mask&~31 or valid&~63 or reserved: raise ValueError('OPC1 header')
    if negotiated!=('opq1' if codec else 'opbin1'): raise ValueError('not negotiated')
    if not mask&16 and valid or mask&8 and not mask&1: raise ValueError('presence')
    poses=(mask&7).bit_count()+(2 if mask&8 else 0)
    floats=(valid&15).bit_count()+2*(valid&48).bit_count()
    if len(blob)!=12+poses*(20 if codec else 28)+(32 if mask&8 else 0)+floats*4: raise ValueError('exact length')
    if poses and frame==0 or not poses and frame!=0 or envelope.get(1,0)&7 != mask&7: raise ValueError('frame/tracking')
    offset=12
    def pose_read():
        nonlocal offset
        if not codec:
            values=list(struct.unpack_from('!7f',blob,offset));offset+=28;xyz,q=values[:3],values[3:]
        else:
            values=struct.unpack_from('!3i4h',blob,offset);offset+=20
            if -32768 in values[3:]: raise ValueError('quaternion sentinel')
            xyz=[x/10000 for x in values[:3]];q=[x/32767 for x in values[3:]]
        if not all(math.isfinite(x) for x in xyz+q): raise ValueError('finite pose')
        norm=math.sqrt(sum(x*x for x in q))
        if abs(norm-1)>.001: raise ValueError('quaternion norm')
        if codec:q=[x/norm for x in q]
        return {0:frame,1:xyz,2:q}
    out={k:copy.deepcopy(v) for k,v in envelope.items() if k!=12}
    for bit,key in enumerate((3,4,5)):
        if mask&(1<<bit):out[key]=pose_read()
    if mask&8:
        left,right=pose_read(),pose_read();fov=list(struct.unpack_from('!8f',blob,offset));offset+=32
        if not all(math.isfinite(x) for x in fov): raise ValueError('FOV finite')
        out[6]={0:left,1:fov[:4],2:right,3:fov[4:]}
    if mask&16:
        controls={0:1,7:valid}
        for bit in range(6):
            if valid&(1<<bit):
                count=1 if bit<4 else 2;values=list(struct.unpack_from('!'+'f'*count,blob,offset));offset+=count*4
                if not all(math.isfinite(v) and (0<=v<=1 if bit<4 else -1<=v<=1) for v in values): raise ValueError('input range')
                controls[bit+1]=values[0] if count==1 else values
        out[11]=controls
    return out

def check_vectors(path):
    vectors=json.loads(Path(path).read_text(encoding='utf-8'));raw=bytes.fromhex(vectors['operator_state_hex'])
    original=cbor2.loads(raw[64:]);lengths={};checks=0
    for name,profile in [('operator_lossless_hex','opbin1'),('operator_quantized_hex','opq1')]:
        packet=bytes.fromhex(vectors[name]);envelope=cbor2.loads(packet[64:]);decoded=expand(envelope,profile)
        assert envelope[12]==pack(original,profile)[12];checks+=1
        if profile=='opbin1':assert decoded==original;checks+=1
        else:
            assert decoded[11]==original[11];checks+=1
            for key in (3,4,5):
                assert max(abs(a-b) for a,b in zip(decoded[key][1],original[key][1]))<=.000050001;checks+=1
                q0,q1=decoded[key][2],original[key][2]
                cosine=abs(sum(a*b for a,b in zip(q0,q1))/math.sqrt(sum(x*x for x in q0)*sum(x*x for x in q1)))
                assert math.degrees(2*math.acos(min(1,cosine)))<.01;checks+=1
        lengths[profile]=len(packet)
        for bitmask in range(64):
            sample=copy.deepcopy(original);sample[11]={k:v for k,v in original[11].items() if k in (0,7) or bitmask&(1<<(k-1))};sample[11][7]=bitmask
            assert expand(pack(sample,profile),profile)[11]==sample[11];checks+=1
        for offset,value in [(2,2),(3,3),(4,128),(5,128),(6,1)]:
            broken=copy.deepcopy(envelope);blob=bytearray(broken[12]);blob[offset]=value;broken[12]=bytes(blob)
            try:expand(broken,profile)
            except ValueError:checks+=1
            else:raise AssertionError('Malformed OPC1 accepted')
        for blob in (envelope[12][:-1],envelope[12]+b'\0'):
            broken=copy.deepcopy(envelope);broken[12]=blob
            try:expand(broken,profile)
            except ValueError:checks+=1
            else:raise AssertionError('Wrong length accepted')
    if 13 in original:
        assert original[13]=={0:1,1:15,2:9};checks+=1
        for valid in range(16):
            for pressed in range(16):
                if pressed&~valid: continue
                sample=copy.deepcopy(original);sample[13]={0:1,1:valid,2:pressed}
                compact=pack(sample,'opbin1');assert 13 in compact and expand(compact,'opbin1')[13]==sample[13];checks+=1
        for invalid in ({0:True,1:15,2:0},{0:2,1:15,2:0},{0:1,1:0,2:1},{0:1,1:16,2:0},{0:1,1:15,2:0,3:0},{0:1,1:15,2:0,3:2,4:1}):
            try:validate_face_buttons(invalid)
            except ValueError:checks+=1
            else:raise AssertionError('Malformed ABXY accepted')
    print(json.dumps({'result':'PASS' ,'independent_checks':checks,'uncompressed_bytes':len(raw),**lengths},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--vectors',required=True)
    args=parser.parse_args();check_vectors(args.vectors)

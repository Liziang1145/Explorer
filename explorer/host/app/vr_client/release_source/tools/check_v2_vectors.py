"""Independent Python CBOR validation of Java-produced interoperability vectors.

Install cbor2==5.6.5 into tools/v2_deps/test_python (not the system environment).
"""
from pathlib import Path
import hashlib, json, struct, sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools/v2_deps/test_python'))
import cbor2
vectors=json.loads((root/'vr/build/v2-contract-vectors.json').read_text(encoding='utf-8'))
header=struct.Struct('!4sBBHHHIQIIQQIIQ')
bodies={}
for name in ['control_hex','map_chunk_0_hex','map_chunk_1_hex','operator_state_hex']:
 raw=bytes.fromhex(vectors[name]);h=header.unpack_from(raw)
 assert h[0]==b'TLZ2' and h[1:3]==(2,0) and h[5]==64 and h[6]==len(raw)-64
 bodies[name]=cbor2.loads(raw[64:])
 assert len(raw)<=1100
control=bodies['control_hex']
assert control[7][1]==[1.,2.,3.]
assert control[11]==[1.,2.,3.,4.,5.,6.] and control[12]==[6.,5.,4.,3.,2.,1.]
obj=bodies['map_chunk_0_hex'][12]+bodies['map_chunk_1_hex'][12]
assert obj==bytes.fromhex(vectors['map_object_hex']) and len(obj)==40
assert hashlib.sha256(obj).digest()==bodies['map_chunk_0_hex'][25]
operator=bodies['operator_state_hex'];raw=operator[11]
assert operator[0]==0 and raw[0]==1 and raw[7]==63
assert set(raw)==set(range(8)) and raw[1]==1.0 and raw[2]==1.0 and raw[3]==.25 and raw[4]==.75
assert raw[5]==[0.,0.] and raw[6]==[.5,-.5]
assert bytes.fromhex('fa3e800000') in bytes.fromhex(vectors['operator_state_hex'])
assert len(bytes.fromhex(vectors['operator_state_hex']))==vectors['operator_bytes']<=1100
print('PASS: independent Python cbor2 validates Java headers, control, operator key11 float32, maps and SHA-256.')

# Key14 geometry is unchanged by old OPC1 encodings; reuse key4/key5 quaternions.
import math
boxes=operator[14]
assert boxes[0]==1
for side in (1,2):
 box=boxes[side];pose=operator[box[0]]
 assert box[0]==side+3 and box[1]==side-1
 lo,hi=box[2][:3],box[2][3:]
 assert len(box[3])==24
 x,y,z,w=pose[2]
 for corner in range(8):
  a,b,c=[hi[k] if corner&(1<<k) else lo[k] for k in range(3)]
  # Independent explicit quaternion rotation matrix in FLU.
  expected=[(1-2*y*y-2*z*z)*a+2*(x*y-z*w)*b+2*(x*z+y*w)*c,
            2*(x*y+z*w)*a+(1-2*x*x-2*z*z)*b+2*(y*z-x*w)*c,
            2*(x*z-y*w)*a+2*(y*z+x*w)*b+(1-2*x*x-2*y*y)*c]
  for k in range(3): assert abs(box[3][corner*3+k]-expected[k]-pose[1][k])<2e-6
for name in ('operator_lossless_hex','operator_quantized_hex'):
 packed=cbor2.loads(bytes.fromhex(vectors[name])[64:])
 assert packed[14]==boxes and 12 in packed and 4 not in packed
print('PASS: Python verifies key14 sources, corner order, rotated/translated geometry and OPC1 compatibility; full bytes=',vectors['operator_bytes'])

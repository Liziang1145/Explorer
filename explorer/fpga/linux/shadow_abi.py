"""Offline ABI encoder/decoder. No MMIO, SocketCAN, device access or control."""
import struct
MAGIC=0x4b504c31
BUILD=0x26110201

def crc32c(data):
    c=0xffffffff
    for b in data:
        c^=b
        for _ in range(8): c=(c>>1)^(0x82f63b78 if c&1 else 0)
    return c^0xffffffff

def encode_command(*,epoch,seq,trace_id,apply_cycle,expire_cycle,channel,kind,
                   joints_mdeg=(0,0,0,0,0,0),gripper_um=0,torque_mnm=0,
                   ps_mono_ns=0,transform_revision=0):
    if channel not in (0,1) or kind not in (1,2): raise ValueError('shadow position/gripper only')
    if len(joints_mdeg)!=6 or not 0<=apply_cycle<expire_cycle<2**64: raise ValueError('record bounds')
    b=bytearray(128)
    struct.pack_into('<IHHIIQQQBBH6iihHHHQII',b,0,MAGIC,1,128,epoch,seq,
                     trace_id,apply_cycle,expire_cycle,channel,kind,0,*joints_mdeg,
                     gripper_um,torque_mnm,1,1,0,ps_mono_ns,transform_revision,0)
    struct.pack_into('<I',b,92,crc32c(b[:92]+b[96:]))
    return bytes(b)

def decode_event(data):
    if len(data)!=64: raise ValueError('event size')
    schema,length,flags,build,boot,domain,ch,kind,res0,seq,aux,trace,cycle,n,res1=struct.unpack_from('<HHIIIHHHHIIQQHH',data)
    if schema!=1 or length!=64 or build!=BUILD or n>8 or res0 or res1 or any(data[60:]): raise ValueError('ABI mismatch')
    return dict(flags=flags,build=build,boot_cookie=boot,domain=domain,channel=ch,kind=kind,
                seq=seq if flags&1 else None,trace_id=trace if flags&1 else None,
                cycle=cycle,aux=aux,data=data[52:52+n].hex())

if __name__=='__main__':
    assert crc32c(b'123456789')==0xe3069283
    b=encode_command(epoch=1,seq=0xffffffff,trace_id=123,apply_cycle=1,expire_cycle=10000000,
                     channel=0,kind=1,joints_mdeg=(-1,-2147483648,1,2147483647,-149999,123456))
    assert len(b)==128 and struct.unpack_from('<6i',b,44)==(-1,-2147483648,1,2147483647,-149999,123456)
    assert struct.unpack_from('<I',b,92)[0]==crc32c(b[:92]+b[96:])
    print('ABI_SELFTEST_PASS')

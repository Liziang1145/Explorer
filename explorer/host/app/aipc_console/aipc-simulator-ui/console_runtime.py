"""Software stop interlock and read-only chassis feedback helpers."""
import json
import math
import socket
import struct
import subprocess
import threading
import time
import uuid


class StopInterlock:
    def __init__(self):
        self.lock = threading.RLock()
        self.epoch = uuid.uuid4().hex
        self.stopped = False
        self.pending = False
        self.results = {}

    def status(self):
        with self.lock:
            return dict(epoch=self.epoch, stopped=self.stopped,
                        pending=self.pending, results=dict(self.results))

    def require(self, data):
        with self.lock:
            if self.stopped:
                raise ValueError('软件停止已锁定，请先解除停止并重新开始操作')
            if data.get('safety_epoch') != self.epoch:
                raise ValueError('控制状态已变化，请刷新状态后重新开始操作')

    def stop(self):
        with self.lock:
            self.epoch = uuid.uuid4().hex
            self.stopped = self.pending = True
            self.results = {'base': '正在提交零速断使能', 'arms': '正在撤销双臂和 VR 会话'}
            return self.epoch

    def result(self, epoch, channel, text):
        with self.lock:
            if epoch == self.epoch:
                self.results[channel] = text

    def complete(self, epoch):
        with self.lock:
            if epoch == self.epoch:
                self.pending = False

    def resume(self, data):
        with self.lock:
            if data.get('safety_epoch') != self.epoch or self.pending:
                raise ValueError('停止仍在处理或状态已变化，请刷新后重试')
            self.epoch = uuid.uuid4().hex
            self.stopped = False
            return self.status()


def decode_base_feedback(data):
    if len(data) != 8 or data[7] != _xor(data[:7]):
        raise ValueError('底盘反馈长度或校验错误')
    def signed(n):
        return n - 65536 if n & 0x8000 else n
    vx = signed((data[2] & 15) << 12 | data[1] << 4 | data[0] >> 4) / 1000
    wz = signed((data[4] & 15) << 12 | data[3] << 4 | data[2] >> 4) / 100
    vy = signed((data[6] & 15) << 12 | data[5] << 4 | data[4] >> 4) / 1000
    # Preserve the driver's /100 angular field without guessing its unit.
    return dict(gear=data[0] & 15, vx=vx, vy=vy, angular_raw=wz,
                angular_unit='协议单位待核对')


def _xor(values):
    out = 0
    for value in values:
        out ^= value
    return out


# Receive only: no CAN send(), link changes, service restarts or enables.
BASE_READ_PY = """import socket,struct,time,json
s=socket.socket(socket.PF_CAN,socket.SOCK_RAW,socket.CAN_RAW)
s.bind(('can0',));s.settimeout(0.35)
end=time.monotonic()+0.5
while time.monotonic()<end:
    try: frame=s.recv(16)
    except socket.timeout: break
    cid,dlc,data=struct.unpack('=IB3x8s',frame)
    if cid==0x98C4D1EF and dlc==8:
        print(json.dumps({'data':list(data),'received_at':time.time()}));break
else: pass
"""


class BaseFeedback:
    def __init__(self, host):
        self.host = host
        self.lock = threading.Lock()
        self.busy = False
        self.last_attempt = -float('inf')
        self.sample = None
        self.received = 0.0
        self.received_at = None
        self.error = '尚未收到反馈'

    def _read(self):
        started = time.monotonic()
        try:
            r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=2',
                                self.host, 'python3', '-'], input=BASE_READ_PY,
                               capture_output=True, text=True, timeout=3)
            if r.returncode != 0 or not r.stdout.strip():
                raise ValueError('未收到 can0 底盘反馈')
            raw = json.loads(r.stdout)
            sample = decode_base_feedback(bytes(raw['data']))
            with self.lock:
                self.sample = sample
                # Conservative age includes request latency (not remote clock).
                self.received = started
                self.received_at = time.time()
                self.error = None
        except Exception as e:
            with self.lock:
                self.error = str(e)
        finally:
            with self.lock:
                self.busy = False

    def status(self, refresh=True):
        now = time.monotonic()
        with self.lock:
            if refresh and not self.busy and now - self.last_attempt >= 1:
                self.busy = True
                self.last_attempt = now
                threading.Thread(target=self._read, daemon=True).start()
            age = now - self.received if self.sample is not None else None
            fresh = self.sample is not None and self.error is None and age < 2
            return dict(fresh=fresh, feedback=self.sample if fresh else None,
                        last_feedback=self.sample, age_ms=round(age*1000) if age is not None else None,
                        received_at=self.received_at, error=self.error, polling=self.busy)

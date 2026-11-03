"""Fixed-target, disabled-control VR sender. No process or robot-enable controls."""
import dataclasses,math,re,socket,threading,time
from simulator_vr_frame import make_sim_frame,encode_sim_frame,decode_frame
TARGET=('192.168.137.1',54321)
def controls(data):
 if not isinstance(data,dict) or set(data)-{'vx','vy','yaw','left','right','left_grip','right_grip'}:raise ValueError('invalid controls')
 def number(v,limit):
  if type(v) not in (int,float) or not math.isfinite(v) or abs(v)>limit:raise ValueError('out of range')
  return v
 def vector(name):
  v=data.get(name,[0,0,0])
  if not isinstance(v,list) or len(v)!=3:raise ValueError('vector required')
  return tuple(number(n,.15) for n in v)
 return dict(vx=number(data.get('vx',0),.3),vy=number(data.get('vy',0),.3),yaw=number(data.get('yaw',0),.5),left=vector('left'),right=vector('right'),left_grip=number(data.get('left_grip',0),1),right_grip=number(data.get('right_grip',0),1))
def packet(c,counter):
 f=make_sim_frame(counter,time.time_ns());f=dataclasses.replace(f,base_lin_vel=(c['vx'],c['vy'],0),base_ang_vel=(0,0,c['yaw']),left_hand_pos=c['left'],right_hand_pos=c['right'],left_grip=c['left_grip'],right_grip=c['right_grip'],right_hand_quat=(0,-.70710678,0,.70710678))
 raw=encode_sim_frame(f);assert len(raw)==78 and raw[2:4]==b'\0\0'
 return raw
class Sender:
 def __init__(self,sock=None,clock=time.monotonic,background=True):
  self.sock=sock or socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.clock=clock;self.lock=threading.RLock();self.owner=None;self.client=None;self.until=0;self.deadline=0;self.c=controls({});self.count=0;self.last=None;self.error=None;self.reason='未开始';self.seq=0
  if background:threading.Thread(target=self.loop,daemon=True).start()
 def loop(self):
  while True:
   self.tick();time.sleep(.05)
 def tick(self):
  with self.lock:
   if self.owner is None:return
   now=self.clock()
   if now>=self.until or now>=self.deadline:self.owner=None;self.reason='心跳过期或本轮60秒结束';return
   try:
    self.seq=(self.seq+1)&0xffffffff;raw=packet(self.c,self.seq);self.sock.sendto(raw,TARGET);self.last=raw;self.count+=1
   except Exception as e:self.error=type(e).__name__;self.owner=None;self.reason='发送失败，已停止'
 def status(self,owner=None,client=None):
  with self.lock:return dict(active=self.owner is not None,owned=self.owner==owner and self.client==client and self.owner is not None,sent=self.count,hz=20,target='192.168.137.1:54321',mask=0,reason=self.reason,error=self.error,remaining=max(0,round(self.deadline-self.clock(),1)) if self.owner else 0,hex=self.last.hex(' ') if self.last else None,decoded=dataclasses.asdict(decode_frame(self.last)) if self.last else None,acknowledged=False)
 def call(self,owner,action,data):
  client=data.get('client','')
  if not isinstance(client,str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}',client):raise ValueError('client required')
  if set(data)-{'client','controls'}:raise ValueError('unknown fields')
  with self.lock:
   if self.owner and (self.clock()>=self.until or self.clock()>=self.deadline):self.owner=None
   if action=='preview':
    raw=packet(controls(data.get('controls',{})),0);return dict(hex=raw.hex(' '),decoded=dataclasses.asdict(decode_frame(raw)),bytes=78,mask=0,active=False)
   if action not in ('start','update','stop'):raise ValueError('invalid action')
   if self.owner and (self.owner!=owner or self.client!=client):return {'error':'另一个页面正在联调，请等待其停止'},409
   if action=='stop':self.owner=None;self.reason='用户停止';return self.status(owner,client)
   c=controls(data.get('controls',{}))
   if action=='start':
    self.owner=owner;self.client=client;self.deadline=self.clock()+60;self.count=0;self.error=None;self.reason='无使能联调'
   if self.owner is None:return self.status(owner,client)
   self.c=c;self.until=self.clock()+1;return self.status(owner,client)
SENDER=Sender()
def get(handler,token):handler.hub_reply(SENDER.status(token))
def post(handler,token,action,data):
 result=SENDER.call(token,action,data)
 if isinstance(result,tuple):handler.hub_reply(*result)
 else:handler.hub_reply(result)

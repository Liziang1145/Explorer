"""Measured preview feedback only; never changes record configuration."""
import asyncio,math,re,time
from aiohttp import ClientError

class PreviewFeedback:
 def __init__(self,receiver):
  self.receiver=receiver;self.client=None;self.sequence=0;self.bytes=0;self.active_seconds=0;self.since=time.monotonic();self.source_rtt_ms=0;self.players={};self.last={'state':'waiting_for_preview_client_id'};self.task=None
 def begin(self,client):
  self.client=client;self.sequence=0;self.bytes=0;self.active_seconds=0;self.since=time.monotonic();self.last={'state':'measuring'if client else'upstream_has_no_feedback_client_id'}
 def observe(self,n,elapsed):
  # Header arrival waits for encoding. Only the following payload transfer is measured.
  if elapsed>=.001:self.bytes+=n;self.active_seconds+=elapsed
 def accept(self,d):
  if not isinstance(d,dict)or set(d)-{'client_id','sequence','window_ms','buffer_ms','rtt_ms','dropped_frames'}:raise ValueError('非法预览反馈字段')
  cid=d.get('client_id');seq=d.get('sequence')
  if not isinstance(cid,str)or not re.fullmatch('[a-f0-9]{32}',cid)or type(seq)is not int or seq<0:raise ValueError('反馈客户端或序号无效')
  for k,lo,hi in [('window_ms',500,5000),('buffer_ms',0,60000),('rtt_ms',0,60000),('dropped_frames',0,100000)]:
   v=d.get(k)
   if type(v)not in(int,float)or not math.isfinite(v)or not lo<=v<=hi:raise ValueError('非法'+k)
  if cid in self.players and seq<=self.players[cid]['sequence']:raise ValueError('旧预览反馈序号')
  if len(self.players)>=8 and cid not in self.players:self.players.pop(min(self.players,key=lambda k:self.players[k]['at']))
  self.players[cid]={**d,'at':time.monotonic()};return {'accepted':True,'upstream_report':self.public()}
 def public(self):return {**self.last,'active_players':sum(time.monotonic()-d['at']<6 for d in self.players.values()),'recording_affected':False}
 async def run(self):
  while True:
   await asyncio.sleep(1);now=time.monotonic()
   if not self.client or not self.receiver.source:continue
   window=int((now-self.since)*1000)
   if not 500<=window<=5000 or self.active_seconds<.02 or self.bytes<32768:
    if window>5000:self.bytes=0;self.active_seconds=0;self.since=now
    self.last={'state':'insufficient_payload_transfer_samples'};continue
   active=[d for d in self.players.values()if now-d['at']<6];self.sequence+=1
   body={'client_id':self.client,'sequence':self.sequence,'window_ms':window,'delivery_bps':int(self.bytes*8/self.active_seconds),
    'buffer_ms':round(max([d['buffer_ms']for d in active]+[0])),
    'rtt_ms':round(max([d['rtt_ms']for d in active]+[self.source_rtt_ms])),
    'dropped_frames':int(sum(d['dropped_frames']for d in active))}
   self.bytes=0;self.active_seconds=0;self.since=now
   try:
    await self.receiver.call('POST','preview/feedback',body);self.last={'state':'sent','at':time.time(),'sequence':self.sequence,'delivery_bps':body['delivery_bps'],'buffer_ms':body['buffer_ms'],'dropped_frames':body['dropped_frames']}
   except (ValueError,OSError,asyncio.TimeoutError,ClientError)as e:self.last={'state':'upstream_rejected_or_unavailable','error':type(e).__name__}

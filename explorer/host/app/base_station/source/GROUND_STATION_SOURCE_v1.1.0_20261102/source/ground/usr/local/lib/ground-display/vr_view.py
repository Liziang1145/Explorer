"""Single Quest subscriber with bounded browser fanout; never auto-starts a cancelled live session."""
import asyncio,ipaddress,json,os,time
from pathlib import Path
import aiohttp
from aiohttp import web
from tlzv_mp4 import HEADER,parse_header,Muxer
class VRView:
 def __init__(self,path='/var/lib/ground-display/vr-view.json'):
  self.path=Path(path);self.config={'host':'','token':'<PROVISION_ON_TARGET>'}
  if self.path.exists():self.config.update(json.loads(self.path.read_text()))
  self.latest={'reachable':False,'error':'尚未配置 Quest 地址','status':None};self.clients={};self.stream_task=None;self.poll_task=None;self.source=None;self.init=None;self.codec=None;self.stats={'frames':0,'reconnects':0};self.last_frame=None;self.generation=0
 def public(self):return {'host':self.config['host'],'port':8095,**self.latest,'codec':self.codec,'stats':{**self.stats,'frame_age_ms':round((time.monotonic()-self.last_frame)*1000) if self.last_frame else None},'stream_generation':self.generation}
 def url(self,path):return 'http://'+self.config['host']+':8095/v1/view/'+path
 async def call(self,method,path,body=None):
  async with self.http.request(method,self.url(path),json=body,headers={'Authorization':'Bearer '+self.config['token']},timeout=aiohttp.ClientTimeout(total=15 if method!='GET' else 3)) as r:
   chunks=[];size=0
   async for chunk in r.content.iter_chunked(16384):
    size+=len(chunk)
    if size>131072:raise ValueError('Quest 状态响应过大')
    chunks.append(chunk)
   data=json.loads(b''.join(chunks))
   if not isinstance(data,dict):raise ValueError('Quest 状态格式无效')
   if r.status!=200:raise ValueError('Quest HTTP '+str(r.status)+' · '+str(data.get('error','请求失败'))[:180])
   return data
 async def close_source(self):
  if self.source:self.source.close()
  if self.stream_task:self.stream_task.cancel();await asyncio.gather(self.stream_task,return_exceptions=True)
  self.stream_task=None;self.init=None;self.codec=None
  for queue in list(self.clients):
   while not queue.empty():queue.get_nowait()
   queue.put_nowait(None)
 async def poll(self):
  while True:
   try:
    if not self.config['host']:await asyncio.sleep(1);continue
    status=await self.call('GET','status');self.latest={'reachable':True,'error':'','status':status,'checked_at':time.time()}
    if status.get('streaming') is True:
     if self.stream_task is None or self.stream_task.done():self.stream_task=asyncio.create_task(self.receive())
    else:await self.close_source()
   except asyncio.CancelledError:raise
   except (aiohttp.ClientError,asyncio.TimeoutError,ValueError) as exc:
    self.latest={**self.latest,'reachable':False,'error':str(exc)[:200] or 'Quest 连接超时','checked_at':time.time()};await self.close_source()
   await asyncio.sleep(1)
 async def receive(self):
  mux=Muxer();self.generation+=1;self.stats['reconnects']+=1
  try:
   async with self.http.get(self.url('live.tlzv'),headers={'Authorization':'Bearer '+self.config['token']},timeout=aiohttp.ClientTimeout(total=None,sock_connect=3,sock_read=5)) as r:
    self.source=r
    if r.status!=200:raise ValueError('Quest stream HTTP '+str(r.status))
    while True:
     header=await r.content.readexactly(HEADER.size);meta=parse_header(header);payload=await r.content.readexactly(meta['size']);packet=mux.push(meta,payload);self.last_frame=time.monotonic();self.stats.pop('error',None);self.stats.update(frames=self.stats['frames']+1,seq=meta['seq'],pts_us=str(meta['pts']),width=meta['width'],height=meta['height']);self.init=mux.init;self.codec=mux.codec
     if not packet:continue
     for queue,waiting in list(self.clients.items()):
      if waiting:
       if not packet['key']:continue
       self.clients[queue]=False
      if queue.full():
       while not queue.empty():queue.get_nowait()
       queue.put_nowait(None);self.clients.pop(queue,None)
      else:queue.put_nowait(packet['data'])
  except asyncio.CancelledError:raise
  except (aiohttp.ClientError,asyncio.TimeoutError,asyncio.IncompleteReadError,ValueError) as exc:self.stats['error']=str(exc)[:180] or 'VR 直播连接中断，等待状态确认后重连'
  finally:
   self.source=None;self.init=None;self.codec=None
   for queue in list(self.clients):
    while not queue.empty():queue.get_nowait()
    queue.put_nowait(None)
 async def command(self,data):
  action=data.get('action')
  if action=='configure':
   host=data.get('host','')
   try:address=ipaddress.IPv4Address(host)
   except (ValueError,ipaddress.AddressValueError):raise ValueError('请输入 Quest 的局域网 IPv4 地址')
   if not any(address in n for n in map(ipaddress.IPv4Network,['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'])):raise ValueError('只允许 Quest 局域网地址')
   token=data.get('token',self.config['token'])
   if not isinstance(token,str) or not 1<=len(token)<=256 or any(c in token for c in '\r\n'):raise ValueError('密钥格式无效')
   await self.close_source();self.config={'host':str(address),'token':token};self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.config));temp.chmod(0o600);temp.replace(self.path);self.latest={'reachable':False,'error':'正在连接 Quest','status':None}
  elif action in ('start','stop','keyframe','capture'):
   if not self.config['host']:raise ValueError('请先配置 Quest 地址')
   method='PUT' if action=='capture' else 'POST';path={'start':'live/start','stop':'live/stop','keyframe':'keyframe','capture':'config'}[action]
   body=data.get('config',{}) if action=='capture' else {}
   if not isinstance(body,dict):raise ValueError('取景配置须为 JSON 对象')
   result=await self.call(method,path,body);self.latest={'reachable':True,'error':'','status':result,'checked_at':time.time()}
   if action=='stop':await self.close_source()
  else:raise ValueError('未知 VR 直播操作')
  return self.public()
 async def stream(self,request):
  if len(self.clients)>=8:raise web.HTTPTooManyRequests(text='最多 8 个网页接收端')
  if not self.init or not self.codec:raise web.HTTPServiceUnavailable(text='VR 未直播或尚未收到同步帧')
  init=self.init;queue=asyncio.Queue(maxsize=16);self.clients[queue]=True
  try:
   first=await asyncio.wait_for(queue.get(),5)
   if first is None:raise web.HTTPServiceUnavailable()
   response=web.StreamResponse(headers={'Content-Type':'video/mp4','Cache-Control':'no-store'});await response.prepare(request);await response.write(init+first)
   while True:
    packet=await asyncio.wait_for(queue.get(),6)
    if packet is None:break
    await asyncio.wait_for(response.write(packet),3)
   return response
  except (asyncio.TimeoutError,ConnectionError):return locals().get('response',web.Response(status=503))
  finally:self.clients.pop(queue,None)
 async def start(self,app):self.http=aiohttp.ClientSession();self.poll_task=asyncio.create_task(self.poll())
 async def stop(self,app):
  self.poll_task.cancel();await asyncio.gather(self.poll_task,return_exceptions=True);await self.close_source();await self.http.close()
def install(app,session):
 service=VRView();app['vr_view']=service
 async def get(r):return web.json_response(service.public(),headers={'Cache-Control':'no-store'})
 async def command(r):
  if session(r)['role']!='admin':raise web.HTTPForbidden()
  try:return web.json_response(await service.command(await r.json()))
  except (ValueError,aiohttp.ClientError,asyncio.TimeoutError) as exc:return web.json_response({'error':str(exc)[:220] or 'Quest 请求超时，请先查询状态再决定是否重新启动'},status=400)
 app.router.add_get('/api/vr-view',get);app.router.add_post('/api/vr-view',command);app.router.add_get('/ui/vr-view.mp4',service.stream);app.on_startup.append(service.start);app.on_cleanup.append(service.stop)
 return service

import asyncio,json,tempfile,sys,subprocess
from pathlib import Path
from aiohttp import web,ClientSession
sys.path.insert(0,str(Path(__file__).parent))
from vr_receiver import VRView
from tlzv_mp4 import HEADER,nals

async def main():
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp);samples=[]
  for width,height in [(320,240),(240,320)]:
   target=root/f'{width}.h264'
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'testsrc2=size={width}x{height}:rate=24','-frames:v','25','-c:v','libx264','-profile:v','baseline','-bf','0','-g','12','-x264-params','aud=1:repeat-headers=1','-f','h264',str(target)],check=True)
   access=[];current=[]
   for nal in nals(target.read_bytes()):
    if nal[0]&31==9 and current:access.append(current);current=[]
    current.append(nal)
   if current:access.append(current)
   samples.append((width,height,access))
  state={'streaming':True,'live_default_on':True,'live_wanted':True,'live_policy_revision':2,'live_started_by':'automatic','framing_center':'optical_axis','local_recording_supported':False};calls=[];mode=0
  async def status(r):calls.append(('GET','status'));return web.json_response(state)
  async def explicit(r):
   calls.append(('POST',r.match_info['action']));state.update(streaming=r.match_info['action']=='start',live_wanted=r.match_info['action']=='start');return web.json_response(state)
  async def stream(r):
   calls.append(('GET','live'));response=web.StreamResponse();await response.prepare(r);snapshot=mode;width,height,access=samples[snapshot]
   try:
    for index in range(300):
     if not state['streaming'] or mode!=snapshot:break
     frame=access[index%24];payload=b''.join(b'\0\0\0\1'+n for n in frame);header=HEADER.pack(b'TLZV',1,int(any(n[0]&31==5 for n in frame)),32,index,index*41667,width,height,len(payload),0)
     await response.write(header[:7]);await response.write(header[7:]+payload);await asyncio.sleep(.03)
   except (ConnectionError,asyncio.CancelledError):pass
   return response
  app=web.Application();app.router.add_get('/v1/view/status',status);app.router.add_get('/v1/view/live.tlzv',stream);app.router.add_post('/v1/view/live/{action}',explicit)
  runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();port=site._server.sockets[0].getsockname()[1]
  service=VRView(root/'config.json');service.config={'host':'127.0.0.1','token':'<PROVISION_ON_TARGET>'};service.url=lambda p:f'http://127.0.0.1:{port}/v1/view/'+p
  await service.start(None)
  async def until(predicate):
   for _ in range(60):
    if predicate():return
    await asyncio.sleep(.1)
   raise AssertionError(service.public())
  try:
   await until(lambda:service.codec is not None and service.stats['frames']>5);assert not any(c[0]=='POST' for c in calls)
   generation=service.generation;mode=1
   await until(lambda:service.generation>generation and service.stats.get('height')==320 and service.codec is not None)
   assert not any(c[0]=='POST' for c in calls),'Reconfiguration must not start live'
   state.update(streaming=False,live_wanted=False);await until(lambda:service.codec is None);before=len([c for c in calls if c==('GET','live')]);await asyncio.sleep(1.2)
   assert len([c for c in calls if c==('GET','live')])==before;assert not any(c[0]=='POST' for c in calls)
   state.update(live_wanted=True,streaming=False);await asyncio.sleep(1.2);assert not any(c[0]=='POST' for c in calls)
   await service.command({'action':'start'});await until(lambda:service.codec is not None)
   assert sum(c==('POST','start') for c in calls)==1
   assert service.public()['status']['framing_center']=='optical_axis'
   assert 'token' not in service.public();assert not (root/'recordings').exists()
   print(json.dumps({'synthetic_only':True,'default_live_without_start':True,'encoding_restart_resubscribes':True,'cancel_never_auto_starts':True,'paused_never_auto_starts':True,'explicit_start_once':True,'split_TLZV_headers':True,'shared_fmp4':True,'no_recording':True}))
  finally:await service.stop(None);await runner.cleanup()
asyncio.run(main())

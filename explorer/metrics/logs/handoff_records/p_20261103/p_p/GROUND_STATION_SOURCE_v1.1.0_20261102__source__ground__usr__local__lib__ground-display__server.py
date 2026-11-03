"""Ground dashboard and physical preview: read-only subscriptions, local PAM authentication."""
import asyncio,collections,json,os,secrets,socket,subprocess,time
from pathlib import Path
import aiohttp,psutil
from aiohttp import web
from display_state import Store
import display_control_auth
ROOT=Path(__file__).resolve().parent;CONFIG=Path('/etc/ground-display/client.json')
SESSIONS={};ATTEMPTS=collections.defaultdict(list)
def session(request):
    value=SESSIONS.get(request.cookies.get('ground_session',''))
    return value if value and value['expires']>time.monotonic() else None
def response(data,status=200):return web.json_response(data,status=status,headers={'Cache-Control':'no-store'})
def new_session(role):
    token=secrets.token_urlsafe(32);SESSIONS[token]={'role':role,'expires':time.monotonic()+43200}
    for key in list(SESSIONS):
        if SESSIONS[key]['expires']<time.monotonic():SESSIONS.pop(key,None)
    return token
async def pam_verify(password):
    reader,writer=await asyncio.open_unix_connection('/run/tlz-kiosk/auth.sock')
    try:
        writer.write(json.dumps({'action':'verify','password':password}).encode()+b'\n');await writer.drain()
        return json.loads(await asyncio.wait_for(reader.readline(),10)).get('ok') is True
    finally:writer.close();await writer.wait_closed()
class JPEGFeed:
    def __init__(self,app,kind):self.app=app;self.kind=kind;self.clients=set();self.task=None;self.frame=None;self.at=0;self.frames=0;self.process=None;self.error=None
    async def run(self):
        while self.clients:
            try:
                cfg=self.app['cfg'];url=cfg['upstream']+'/observer/'+self.kind
                args=['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-nostdin','-fflags','nobuffer','-flags','low_delay','-headers','Authorization: Bearer '+cfg['token']+'\r\n','-i',url,'-an','-vf','fps=20,scale=960:-2','-threads','2','-c:v','mjpeg','-q:v','5','-f','image2pipe','pipe:1']
                self.process=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                buffer=bytearray()
                while self.clients:
                    chunk=await asyncio.wait_for(self.process.stdout.read(65536),8)
                    if not chunk:raise OSError('Video source ended')
                    buffer.extend(chunk)
                    if len(buffer)>3000000:raise OSError('JPEG framing exceeded limit')
                    while True:
                        start=buffer.find(b'\xff\xd8');end=buffer.find(b'\xff\xd9',max(0,start+2))
                        if start<0 or end<0:break
                        self.frame=bytes(buffer[start:end+2]);del buffer[:end+2];self.at=time.monotonic();self.frames+=1;self.error=None
                        for q in tuple(self.clients):
                            if q.full():q.get_nowait()
                            q.put_nowait(self.frame)
            except (OSError,asyncio.TimeoutError):self.error='AIPC video unavailable';await asyncio.sleep(1)
            finally:
                if self.process and self.process.returncode is None:
                    self.process.terminate()
                    try:await asyncio.wait_for(self.process.wait(),3)
                    except asyncio.TimeoutError:self.process.kill();await self.process.wait()
                self.process=None
        self.task=None;self.frame=None
    async def stream(self,request):
        q=asyncio.Queue(maxsize=1);self.clients.add(q)
        if self.task is None:self.task=asyncio.create_task(self.run())
        result=web.StreamResponse(headers={'Content-Type':'multipart/x-mixed-replace; boundary=frame','Cache-Control':'no-store'})
        await result.prepare(request)
        try:
            while True:
                frame=await asyncio.wait_for(q.get(),12)
                await asyncio.wait_for(result.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(frame)).encode()+b'\r\n\r\n'+frame+b'\r\n'),3)
        except (ConnectionError,asyncio.TimeoutError):pass
        finally:self.clients.discard(q)
        return result
async def upstream(app,kind):
    start=time.monotonic()
    async with app['http'].get(app['cfg']['upstream']+'/observer/'+kind,headers={'Authorization':'Bearer '+app['cfg']['token']}) as r:
        r.raise_for_status();data=await r.json()
    return data,round((time.monotonic()-start)*1000,2)
async def poll(app,kind,interval):
    while True:
        try:
            data,rtt=await upstream(app,kind);app['cache'][kind]={'data':data,'rtt_ms':rtt,'received':time.monotonic(),'last_success_at':time.time(),'checked_at':time.time(),'error':None,'error_code':None}
        except (aiohttp.ClientError,asyncio.TimeoutError,ValueError) as exc:
            if isinstance(exc,aiohttp.ClientResponseError):
                code='authentication' if exc.status in (401,403) else 'http_error'
                message='AIPC 认证失败' if code=='authentication' else 'AIPC 服务返回 HTTP '+str(exc.status)
            elif isinstance(exc,asyncio.TimeoutError):code,message='timeout','AIPC 连接超时'
            elif isinstance(exc,aiohttp.ClientConnectorError):
                refused=isinstance(exc.os_error,ConnectionRefusedError)
                code,message=('refused','AIPC 观察服务拒绝连接') if refused else ('network','无法连接 AIPC 观察服务')
            elif isinstance(exc,ValueError):code,message='invalid_data','AIPC 返回的数据格式异常'
            else:code,message='connection','AIPC 连接已中断'
            old=app['cache'].get(kind,{});app['cache'][kind]={**old,'error':message,'error_code':code,'checked_at':time.time()}
        await asyncio.sleep(interval)
def cached(app,kind):
    value=app['cache'].get(kind,{})
    from urllib.parse import urlsplit
    address=urlsplit(app['cfg']['upstream'])
    return {**value,'target':address.hostname+(':'+str(address.port) if address.port else ''),'age_ms':round((time.monotonic()-value['received'])*1000,2) if 'received' in value else None}
async def metrics(app):
    while True:
        cpu=psutil.cpu_percent(percpu=True);vm=psutil.virtual_memory();disk=psutil.disk_usage('/')
        addresses=psutil.net_if_addrs();stats=psutil.net_if_stats();net=psutil.net_io_counters(pernic=True)
        processes=[]
        for p in psutil.process_iter(['pid','name','username','cpu_percent','memory_info']):
            try:processes.append({'pid':p.pid,'name':p.info['name'],'user':p.info['username'],'cpu':p.info['cpu_percent'] or 0,'rss':p.info['memory_info'].rss if p.info['memory_info'] else 0})
            except psutil.Error:pass
        processes.sort(key=lambda p:p['rss'],reverse=True)
        app['metrics']={'hostname':socket.gethostname(),'uptime':time.time()-psutil.boot_time(),'cpu':sum(cpu)/max(1,len(cpu)),'cores':cpu,'memory':{'used':vm.total-vm.available,'total':vm.total,'percent':vm.percent},'disk':{'used':disk.used,'total':disk.total,'percent':disk.percent},'processes':processes,'interfaces':[{'name':name,'up':s.isup,'speed':s.speed,'addresses':[v.address for v in addresses.get(name,[]) if v.family==socket.AF_INET],'rx_bytes':net[name].bytes_recv if name in net else 0,'tx_bytes':net[name].bytes_sent if name in net else 0} for name,s in stats.items() if name!='lo']}
        await asyncio.sleep(1)
def make_app(cfg):
    @web.middleware
    async def guard(r,handler):
        from urllib.parse import urlsplit
        allowed={'localhost','127.0.0.1'}|{a.address for v in psutil.net_if_addrs().values() for a in v if a.family==socket.AF_INET}
        host=urlsplit('http://'+r.host)
        if host.hostname not in allowed or host.port!=8080:raise web.HTTPForbidden(text='Invalid request host')
        if r.method not in ('GET','HEAD'):
            origin=r.headers.get('Origin','')
            if r.headers.get('X-Ground-Client')!='display' or origin!=r.scheme+'://'+r.host:raise web.HTTPForbidden(text='Invalid request origin')
        if r.path.startswith(('/api/','/ui/')) and r.path not in ('/api/login','/api/health'):
            if not session(r) and not display_control_auth.authorized(r):raise web.HTTPUnauthorized()
        answer=await handler(r)
        answer.headers['X-Content-Type-Options']='nosniff';answer.headers['Referrer-Policy']='same-origin';answer.headers['X-Frame-Options']='SAMEORIGIN'
        if r.path.endswith(('.html','.js','.css')) or r.path in ('/','/local','/preview'):answer.headers['Cache-Control']='no-store'
        return answer
    app=web.Application(middlewares=[guard],client_max_size=4096);app['cfg']=cfg;app['cache']={};app['metrics']={};app['prompt']=None;app['display']=Store();app['physical']=None
    def physical():
        value=app['physical']
        return {**value,'age_ms':round((time.monotonic()-value['received'])*1000)} if value else None
    async def display_get(r):return response({'state':app['display'].value,'physical':physical()})
    async def display_set(r):
        if not (session(r) and session(r)['role']=='admin') and not display_control_auth.authorized(r):raise web.HTTPForbidden(text='Administrator required')
        try:value=app['display'].update(await r.json())
        except (ValueError,TypeError):return response({'error':'展示设置格式或范围无效'},400)
        return response({'state':value,'physical':physical()})
    async def display_heartbeat(r):
        if r.remote not in ('127.0.0.1','::1') or session(r)['role']!='observer':raise web.HTTPForbidden()
        data=await r.json()
        if not isinstance(data,dict):raise web.HTTPBadRequest()
        app['physical']={k:data.get(k) for k in ('revision','layout','video','visibility','camera','depth','vr','camera1','camera2','camera3','camera4')};app['physical']['received']=time.monotonic()
        return response({'ok':True})
    async def health(r):return response({'ok':True,'role':'read-only-ground-display','protocol':'TLZ/2.0','hotspot_enabled':False})
    async def login(r):
        now=time.monotonic();attempts=ATTEMPTS[r.remote];attempts[:]=[v for v in attempts if now-v<60]
        if len(attempts)>=5:return response({'error':'尝试过于频繁，请稍后重试'},429)
        data=await r.json();attempts.append(now)
        if data.get('username')!='apex' or not await pam_verify(data.get('password','')):return response({'error':'账户或密码错误'},401)
        attempts.clear();result=response({'ok':True});result.set_cookie('ground_session',new_session('admin'),httponly=True,samesite='Strict',max_age=43200);return result
    async def logout(r):
        SESSIONS.pop(r.cookies.get('ground_session',''),None);result=response({'ok':True});result.del_cookie('ground_session');return result
    async def local(r):
        if r.remote not in ('127.0.0.1','::1'):raise web.HTTPForbidden()
        result=web.FileResponse(ROOT/'public/preview.html');result.set_cookie('ground_session',new_session('observer'),httponly=True,samesite='Strict',max_age=43200);return result
    async def snapshot(r):
        value={k:cached(app,k) for k in ('snapshot','operator','media-status')}
        value.update(display=app['display'].value,physical=physical(),timestamp=time.time(),read_only=True,execution_authorized=False,metrics=app['metrics'],compatibility={k:{'frames':v.frames,'age_ms':round((time.monotonic()-v.at)*1000) if v.at else None,'subscribers':len(v.clients),'error':v.error} for k,v in app['jpeg'].items()})
        return response(value)
    async def cloud(r):
        value=cached(app,'cloud');data=value.get('data',{})
        if value.get('error') or value.get('age_ms') is None or value['age_ms']>1500:data={'state':'unavailable','points':[]}
        return response({**data,'link_rtt_ms':value.get('rtt_ms'),'ground_cache_age_ms':value.get('age_ms')})
    async def video(r):
        kind=r.match_info['kind']
        if kind not in ('camera','depth','camera1','camera2','camera3','camera4'):raise web.HTTPNotFound()
        if '/mjpeg/' in r.path:return await app['jpeg'][kind].stream(r)
        try:
            async with app['http'].get(cfg['upstream']+'/observer/'+kind,headers={'Authorization':'Bearer '+cfg['token']}) as source:
                if source.status!=200:raise web.HTTPServiceUnavailable()
                result=web.StreamResponse(headers={'Content-Type':source.headers.get('Content-Type','video/mp4'),'Cache-Control':'no-store'})
                await result.prepare(r)
                async for chunk in source.content.iter_any():await asyncio.wait_for(result.write(chunk),3)
                return result
        except (aiohttp.ClientError,asyncio.TimeoutError,ConnectionError):
            if 'result' in locals():return result
            raise web.HTTPServiceUnavailable()
    async def unlock(r):
        if r.remote not in ('127.0.0.1','::1'):raise web.HTTPForbidden()
        prompt=app['prompt']
        if prompt is None or prompt.poll() is not None:
            env=os.environ.copy();path=Path('/run/user')/str(os.getuid())/'tlz-kiosk-env.json'
            if not path.exists():raise web.HTTPServiceUnavailable(text='No physical preview session')
            values=json.loads(path.read_text())
            for key in ('WAYLAND_DISPLAY','DISPLAY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'):
                if key in values:env[key]=values[key]
            app['prompt']=subprocess.Popen(['/usr/bin/python3','/usr/local/lib/tlz-kiosk/dialog.py'],env=env)
        return response({'ok':True})
    async def services(r):
        proc=await asyncio.create_subprocess_exec('systemctl','show','ground-display.service','tlz-display.service','tlz-kiosk-auth.service','tlz-display-watch.service','-p','Id,ActiveState,SubState,UnitFileState',stdout=asyncio.subprocess.PIPE)
        stdout,_=await proc.communicate();return response({'services':[dict(line.split('=',1) for line in block.splitlines() if '=' in line) for block in stdout.decode().strip().split('\n\n')]})
    async def start(app):
        app['http']=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None,sock_connect=2,sock_read=7),connector=aiohttp.TCPConnector(limit=24))
        app['jpeg']={k:JPEGFeed(app,k) for k in ('camera','depth','camera1','camera2','camera3','camera4')}
        app['tasks']=[asyncio.create_task(poll(app,k,delay)) for k,delay in [('snapshot',.5),('operator',.1),('media-status',1),('cloud',.15)]]+[asyncio.create_task(metrics(app))]
    async def stop(app):
        for task in app['tasks']:task.cancel()
        for feed in app['jpeg'].values():
            feed.clients.clear()
            if feed.task:feed.task.cancel()
        await asyncio.gather(*app['tasks'],*[v.task for v in app['jpeg'].values() if v.task],return_exceptions=True);await app['http'].close()
    app.router.add_get('/api/health',health);app.router.add_post('/api/login',login);app.router.add_post('/api/logout',logout)
    app.router.add_get('/api/display',display_get);app.router.add_post('/api/display',display_set);app.router.add_post('/ui/display/heartbeat',display_heartbeat)
    app.router.add_get('/api/snapshot',snapshot);app.router.add_get('/api/services',services)
    app.router.add_get('/ui/snapshot',snapshot);app.router.add_get('/ui/source/cloud',cloud)
    app.router.add_get('/ui/hevc/{kind}',video);app.router.add_get('/ui/mjpeg/{kind}',video);app.router.add_post('/ui/unlock-request',unlock)
    app.router.add_get('/local',local);app.router.add_get('/preview',lambda r:web.FileResponse(ROOT/'public/preview.html'))
    app.router.add_get('/',lambda r:web.FileResponse(ROOT/'public/index.html'));app.router.add_static('/assets',ROOT/'public')
    from camera_channels import install_ground
    install_ground(app)
    from vr_relay_client import install
    install(app,session)
    app.on_startup.append(start);app.on_cleanup.append(stop);return app
if __name__=='__main__':web.run_app(make_app(json.loads(CONFIG.read_text())),host='0.0.0.0',port=8080,access_log=None,shutdown_timeout=5)

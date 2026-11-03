"""Versioned service registry and asynchronous lifecycle API."""
import base64, gzip, hashlib, hmac, json, secrets, socket, subprocess, threading, time, urllib.request, urllib.error
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from dsh_entry import browser_cookie, DSH_ORIGIN, COOKIE_NAME
from kr260_api import proxy as kr260_proxy
from aipc_monitor import MONITOR as AIPC_MONITOR
import hub_settings,hub_bandwidth,rdp_gateway,hub_power,ssh_gateway
ROOT=Path(__file__).resolve().parent
AUTH=ROOT/'hub-admin.json'
SESSIONS={};RDP_CREDENTIALS={};ATTEMPTS={};JOBS={};LOCK=threading.RLock();BUSY=False
REGISTRY=[
 {'id':'model','title':'千问 · 本地模型','description':'Strata 推理与对话服务','model':'qwen3.8-flash-next-iq3_s','unit':'strata-iq3_s.service','scope':'system','url':'http://192.168.137.2:8080/','health':'http://192.168.137.2:8080/health','dependencies':[],'icon':'BrainCircuit'},
 {'id':'dsh','title':'dsh · 智能体工作区','description':'任务编排、工具调用与智能体会话','unit':'deepseek-harness-web.service','scope':'system','url':'/api/v1/entry/dsh','health':'http://192.168.137.2:3080/','dependencies':[],'inference_provider':'model','icon':'Workflow'},
 {'id':'documents','title':'墨阅 · 文档中心','description':'Markdown、公式、图片与共享分类','unit':'apex-hub-web.service','scope':'system','url':'/library.html','dependencies':[],'icon':'BookOpen','managed':False},
]
def unit_state(item):
    cmd=['systemctl']+(['--user'] if item['scope']=='user' else [])+['show',item['unit'],'-p','ActiveState','-p','SubState','-p','MainPID']
    try:
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=3)
        return dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)
    except Exception:return {'ActiveState':'unknown','SubState':'unknown'}
def healthy(item):
    if item['id']=='documents':return True
    try:
        with urllib.request.urlopen(item['health'],timeout=2) as r:
            if item['id']=='model':return json.loads(r.read(4096)).get('loaded',False)
            return r.status==200
    except urllib.error.HTTPError as e:return item['id']=='dsh' and e.code==401
    except Exception:return False
def status():
    result=[]
    for item in REGISTRY:
        state=unit_state(item);is_ready=state.get('ActiveState')=='active' and healthy(item)
        result.append({k:v for k,v in item.items() if k!='health'}|{'state':state.get('ActiveState','unknown'),'substate':state.get('SubState','unknown'),'ready':is_ready,'pid':state.get('MainPID','0'),'managed':item.get('managed',True)})
    return result
def control(service,action):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.settimeout(15);s.connect('/run/apex-hub/control.sock');s.sendall(json.dumps({'service':service,'action':action}).encode()+b'\n');raw=b''
        while b'\n' not in raw:
            part=s.recv(4096)
            if not part:break
            raw+=part
        data=json.loads(raw)
        if not data.get('ok'):raise RuntimeError(data.get('error','服务操作失败'))
def wait_for(service,running,timeout=150):
    item=next(i for i in REGISTRY if i['id']==service);end=time.monotonic()+timeout
    while time.monotonic()<end:
        state=unit_state(item).get('ActiveState')
        if running and state=='active' and healthy(item):return
        if not running and state in ('inactive','failed'):return
        if running and state=='failed':raise RuntimeError('服务启动失败，请查看 systemd 日志')
        time.sleep(1)
    raise RuntimeError('服务未在期限内就绪，请检查服务日志')
def lifecycle(job,service,action):
    global BUSY
    started=[]
    def step(message):
        with LOCK:JOBS[job]['message']=message
    try:
        if action=='start':
            order=[service]
            for target in order:
                item=next(i for i in REGISTRY if i['id']==target)
                if unit_state(item).get('ActiveState')=='active' and healthy(item):continue
                step('正在启动模型并等待加载完成…' if target=='model' else '正在启动 dsh…')
                if unit_state(item).get('ActiveState')!='active':started.append(target)
                control(target,'start');wait_for(target,True)
        else:
            order=[service]
            for target in order:
                step('正在停止 '+('dsh' if target=='dsh' else '模型')+'…');control(target,'stop');wait_for(target,False,45)
        with LOCK:JOBS[job].update(state='succeeded',message='服务已就绪' if action=='start' else '服务已停止')
    except Exception as e:
        # Roll back only processes this operation started; preserve existing sessions.
        for target in reversed(started):
            try:control(target,'stop');wait_for(target,False,45)
            except Exception:pass
        with LOCK:JOBS[job].update(state='failed',message=str(e))
    finally:
        with LOCK:
            BUSY=False;JOBS[job]['finished_at']=time.time()
            with (ROOT/'hub-audit.jsonl').open('a') as f:f.write(json.dumps(JOBS[job],ensure_ascii=False)+'\n')
class HubMixin:
    def hub_reply(self,data,code=200,cookie=None):
        raw=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode();self.send_response(code)
        if 'gzip' in self.headers.get('Accept-Encoding','') and len(raw)>1024:
            raw=gzip.compress(raw,compresslevel=3);self.send_header('Content-Encoding','gzip')
        self.send_header('Vary','Accept-Encoding')
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)))
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(raw)
    def session(self):
        try:
            cookie=SimpleCookie(self.headers.get('Cookie',''));token=cookie['hub_session'].value
            with LOCK:
                expiry=SESSIONS.get(token,0)
                if expiry>time.time():return token
                SESSIONS.pop(token,None)
                RDP_CREDENTIALS.pop(token,None);rdp_gateway.close(token);ssh_gateway.close_token(token);hub_power.forget(token)
        except Exception:pass
        return None
    def hub_get(self):
        route=urlsplit(self.path).path
        if not route.startswith('/api/v1/'):return False
        if route=='/api/v1/health':self.hub_reply({'status':'ok','api_version':'1'});return True
        token=self.session()
        if not token:self.hub_reply({'error':'请先登录管理账户'},401);return True
        if route=='/api/v1/settings':self.hub_reply(hub_settings.get());return True
        if route=='/api/v1/settings/bandwidth':self.hub_reply(hub_bandwidth.estimate());return True
        if route=='/api/v1/power/status':
            try:self.hub_reply(hub_power.rpc('status'))
            except (OSError,RuntimeError):self.hub_reply({'error':'电源控制服务暂不可用'},503)
            return True
        if route=='/api/v1/ssh/hosts':self.hub_reply(ssh_gateway.hosts());return True
        if route.startswith('/api/v1/ssh/') and route.endswith('/ws'):
            def valid_ssh(t):
                with LOCK:return SESSIONS.get(t,0)>time.time()
            ssh_gateway.serve(self,token,route.split('/')[-2],valid_ssh);return True
        if route=='/api/v1/rdp/status':self.hub_reply(rdp_gateway.status());return True
        if route=='/api/v1/rdp/ws':
            def valid(t):
                with LOCK:return SESSIONS.get(t,0)>time.time()
            rdp_gateway.serve(self,token,RDP_CREDENTIALS.get(token),valid);return True
        if route.startswith('/api/v1/aipc/'):
            try:self.hub_reply(AIPC_MONITOR.get(route.rsplit('/',1)[-1]))
            except KeyError:self.hub_reply({'error':'接口不存在'},404)
            return True
        if route.startswith('/api/v1/kr260/'):
            kr260_proxy(self,self.path);return True
        if route=='/api/v1/entry/dsh':
            if urlsplit('http://'+self.headers.get('Host','')).hostname!='192.168.137.2':
                self.hub_reply({'error':'请通过 192.168.137.2 的工作台地址进入 dsh'},400);return True
            try:cookie=browser_cookie()
            except RuntimeError as e:self.hub_reply({'error':str(e)},503);return True
            except Exception:self.hub_reply({'error':'dsh 会话映射暂时不可用，请稍后重试'},503);return True
            self.send_response(303);self.send_header('Location',DSH_ORIGIN+'/')
            self.send_header('Set-Cookie',cookie);self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Length','0');self.end_headers()
        elif route=='/api/v1/services':self.hub_reply({'services':status(),'busy':BUSY})
        elif route.startswith('/api/v1/jobs/'):
            with LOCK:data=JOBS.get(route.rsplit('/',1)[-1])
            self.hub_reply(data or {'error':'任务不存在'},200 if data else 404)
        elif route=='/api/v1/session':self.hub_reply({'user':'apex'})
        else:self.hub_reply({'error':'接口不存在'},404)
        return True
    def hub_post(self):
        global BUSY
        route=urlsplit(self.path).path
        if not route.startswith('/api/v1/'):return False
        try:
            origin=self.headers.get('Origin')
            if self.headers.get('X-Hub-Client')!='console' or (origin and urlsplit(origin).netloc!=self.headers.get('Host')):self.hub_reply({'error':'无效来源'},403);return True
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=(65536 if route=='/api/v1/kr260/protocols' else 16384 if '/integrations/' in route else 4096):raise ValueError('请求大小无效')
            data=json.loads(self.rfile.read(size))
            if route=='/api/v1/login':
                peer=self.client_address[0];now=time.time()
                with LOCK:
                    attempts=[t for t in ATTEMPTS.get(peer,[]) if now-t<60];ATTEMPTS[peer]=attempts
                    if len(attempts)>=5:self.hub_reply({'error':'尝试过于频繁，请稍后再试'},429);return True
                cfg=json.loads(AUTH.read_text());digest=hashlib.pbkdf2_hmac('sha256',str(data.get('password','')).encode(),bytes.fromhex(cfg['salt']),cfg['iterations']).hex()
                if data.get('username')!='apex' or not hmac.compare_digest(digest,cfg['hash']):
                    with LOCK:ATTEMPTS[peer].append(now)
                    self.hub_reply({'error':'账户或密码错误'},401);return True
                token=secrets.token_urlsafe(32)
                with LOCK:SESSIONS[token]=now+43200;RDP_CREDENTIALS[token]=str(data['password']);ATTEMPTS.pop(peer,None)
                self.hub_reply({'ok':True,'user':'apex'},cookie='hub_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200');return True
            token=self.session()
            if not token:self.hub_reply({'error':'请先登录管理账户'},401);return True
            if route=='/api/v1/settings':self.hub_reply(hub_settings.save(data));return True
            if route=='/api/v1/power/prepare':self.hub_reply(hub_power.prepare(token,data.get('action')));return True
            if route=='/api/v1/power/commit':self.hub_reply(hub_power.commit(token,data),202);return True
            if route=='/api/v1/power/cancel':self.hub_reply(hub_power.rpc('cancel',data.get('id')));return True
            if route.startswith('/api/v1/kr260/'):
                kr260_proxy(self,route,data);return True
            if route=='/api/v1/logout':
                with LOCK:SESSIONS.pop(token,None);RDP_CREDENTIALS.pop(token,None)
                rdp_gateway.close(token);ssh_gateway.close_token(token);hub_power.forget(token)
                raw=b'{"ok":true}';self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Set-Cookie','hub_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                self.send_header('Set-Cookie',COOKIE_NAME+'=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return True
            if route.startswith('/api/v1/services/'):
                parts=route.split('/');service=parts[-2];action=parts[-1]
                if service not in ('model','dsh') or action not in ('start','stop'):raise ValueError('不支持的服务操作')
                with LOCK:
                    if BUSY:self.hub_reply({'error':'已有启停任务正在执行'},409);return True
                    BUSY=True;job=secrets.token_hex(8)
                    JOBS[job]={'id':job,'service':service,'action':action,'state':'running','message':'请求已接收','started_at':time.time()}
                    if len(JOBS)>100:
                        for old in list(JOBS)[:-50]:JOBS.pop(old,None)
                threading.Thread(target=lifecycle,args=(job,service,action),daemon=True).start()
                self.hub_reply({'job_id':job},202);return True
            self.hub_reply({'error':'接口不存在'},404)
        except hub_power.PowerError as error:self.hub_reply({'error':str(error)},error.status)
        except (ValueError,KeyError):self.hub_reply({'error':'请求内容无效'},400)
        except Exception:self.hub_reply({'error':'管理操作失败'},500)
        return True

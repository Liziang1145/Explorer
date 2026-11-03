"""Measurement engine: bounded passive observation, explicit manual trials, actual TCP payload probes."""
import base64,collections,hashlib,hmac,http.client,json,math,os,socket,statistics,struct,threading,time,urllib.request,urllib.parse,uuid
from pathlib import Path
from store import Store
from peer import snapshot

def distribution(values):
 v=sorted(x for x in values if isinstance(x,(int,float))and math.isfinite(x));n=len(v)
 return {'n':n,'p50':v[max(0,math.ceil(n*.50)-1)],'p95':v[max(0,math.ceil(n*.95)-1)],'p99':v[max(0,math.ceil(n*.99)-1)],'max':v[-1],'mean':statistics.fmean(v)}if n else {'n':0,'p50':None,'p95':None,'p99':None,'max':None,'mean':None}

class Engine:
 def __init__(self,cfg):
  self.cfg=cfg;self.store=Store(cfg['data_dir'],int(cfg.get('limit_bytes',50_000_000_000)));self.lock=threading.RLock();self.pending=[];self.latest={};self.series=collections.defaultdict(lambda:collections.deque(maxlen=3600));self.values=collections.defaultdict(lambda:collections.deque(maxlen=10000));self.status={'started':time.time(),'peer':'connecting','errors':{},'collector_drops':0};self.prev={};self.last_can={};self.cursor=0;self.peer_boot=None;self.mapping=None;self.active=None;self.trace={};self.udp={};self.pose={};self.pending_motion={};self.clock_context={};self.bulk_busy=False;self.stage_values=collections.defaultdict(lambda:collections.deque(maxlen=10000))
  Path(cfg.get('trace_socket','/run/core-metrics/events.sock')).with_name('trial.active').unlink(missing_ok=True)
  self.can_tx_recent=collections.defaultdict(lambda:collections.deque(maxlen=256))
  for task in self.store.task():
   if task['status']=='running':task.update(status='interrupted',ended=time.time(),reason='采集服务重启，未自动恢复手动任务');self.store.task(task['id'],task)
 def record(self,project,kind,node='aipc',**data):
  r={'project':project,'kind':kind,'node':node,'wall':time.time(),**data}
  with self.lock:
   if len(self.pending)>=60000:self.status['collector_drops']+=1;return
   self.pending.append(r)
 def metric(self,key,value,unit,method,**extra):
  if value is None or not math.isfinite(value):return
  point={'at':time.time(),'value':value,'unit':unit,'method':method,**extra}
  with self.lock:self.latest[key]=point;self.series[key].append(point);self.values[key].append(value)
 def peer(self,path,data=None,timeout=5):
  raw=None if data is None else json.dumps(data).encode();req=urllib.request.Request(self.cfg['peer_url']+path,data=raw,headers={'Authorization':'Bearer '+self.cfg['token'],'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=timeout)as r:return json.load(r)
 def flush_loop(self):
  while True:
   time.sleep(.5)
   with self.lock:batch=self.pending;self.pending=[]
   try:self.store.write(batch);self.status['errors'].pop('storage',None)
   except Exception as e:self.status['errors']['storage']=str(e);self.status['collector_drops']+=len(batch)
 def interval(self,node,s):
  p=self.prev.get(node);self.prev[node]=s;self.record('fpga','counters',node,raw=s)
  if not p or s['boot']!=p['boot']:return
  dt=(int(s['mono_ns'])-int(p['mono_ns']))/1e9
  if dt<=0:return
  a=list(map(int,s['cpu'].split()[1:9]));b=list(map(int,p['cpu'].split()[1:9]));d=[x-y for x,y in zip(a,b)];total=sum(d)
  if total>0:self.metric(node+'.cpu',100*(total-d[3]-d[4])/total,'%', 'CPU /proc/stat 区间总占用，跨核归一化')
  if total>0:
   if not hasattr(self,'_cpu_accum'):self._cpu_accum={}
   count,busy=self._cpu_accum.get(node,(0,0));count+=total;busy+=total-d[3]-d[4];self._cpu_accum[node]=(count,busy);self.metric(node+'.cpu_average',100*busy/count,'%','采集会话起的累计busy jiffies/累计total jiffies，按时间加权')
  if 'observer_cpu_ns'in s and'observer_cpu_ns'in p:self.metric(node+'.observer_cpu',100*(int(s['observer_cpu_ns'])-int(p['observer_cpu_ns']))/(dt*1e9),'%单核','采集进程CPU时间增量/本机单调时间；100%代表一个核')
  for iface,v in s['interfaces'].items():
   old=p['interfaces'].get(iface)
   if not old:continue
   delta={k:max(0,v[k]-old.get(k,0))for k in ['rx_bytes','tx_bytes','rx_packets','tx_packets','rx_errors','tx_errors','rx_dropped','tx_dropped']if k in v}
   self.record('fpga','interface_interval',node,interface=iface,duration_s=dt,delta=delta)
   for direction in ['rx','tx']:
    self.metric(node+'.'+iface+'.'+direction+'_mbps',delta.get(direction+'_bytes',0)*8/dt/1e6,'Mbit/s','网卡字节计数增量/本机单调时间；CAN仅为数据域有效载荷')
    self.metric(node+'.'+iface+'.'+direction+'_fps',delta.get(direction+'_packets',0)/dt,'帧/s','接口包计数增量/本机单调时间')
    packets=delta.get(direction+'_packets',0);errors=delta.get(direction+'_errors',0);drops=delta.get(direction+'_dropped',0)
    self.metric(node+'.'+iface+'.'+direction+'_errors',errors,'次/区间','驱动错误计数增量，非历史累计')
    if packets+errors:self.metric(node+'.'+iface+'.'+direction+'_error_pct',100*errors/(packets+errors),'%','驱动错误事件/(包数+错误事件)，非端到端包错误率')
    if packets+drops:self.metric(node+'.'+iface+'.'+direction+'_drop_pct',100*drops/(packets+drops),'%','接口丢弃计数/(已处理包数+丢弃计数)，不是线缆端到端丢包率')
  def tcp(raw):
   lines=raw.splitlines()
   for i,l in enumerate(lines[:-1]):
    if l.startswith('Tcp:')and 'RetransSegs'in l:return dict(zip(l.split()[1:],map(int,lines[i+1].split()[1:])))
   return {}
  a=tcp(s['tcp_snmp']);b=tcp(p['tcp_snmp']);sent=a.get('OutSegs',0)-b.get('OutSegs',0);retry=a.get('RetransSegs',0)-b.get('RetransSegs',0)
  if sent>0:self.metric(node+'.tcp_retrans_pct',100*max(0,retry)/sent,'%','整机TCP重传段增量/发送段增量；包含其他业务，非本次探针专属')
 def sample_loop(self):
  while True:
   started=time.monotonic()
   try:self.interval('aipc',snapshot());self.interval('kr260',self.peer('/snapshot'));self.status['peer']='online';self.status['last_peer']=time.time();self.status['errors'].pop('peer',None)
   except Exception as e:self.status['peer']='offline';self.status['errors']['peer']=str(e)
   try:self.status['control_tap']=json.loads(Path(self.cfg.get('trace_socket','/run/core-metrics/events.sock')).with_name('tap-status.json').read_text())
   except (OSError,ValueError):pass
   time.sleep(max(.05,1-(time.monotonic()-started)))
 def probe_loop(self):
  seq=0;failures=0;total=0;last_rtt=None
  while True:
   start=time.monotonic_ns();seq+=1;total+=1
   try:
    d=self.peer('/clock',timeout=2);end=time.monotonic_ns();t2=int(d['t2']);t3=int(d['t3']);rtt=(end-start-(t3-t2))/1e6
    if rtt<0:raise ValueError('invalid clock exchange')
    raw={'seq':seq,'t1':str(start),'t2':str(t2),'t3':str(t3),'t4':str(end),'peer_boot':d['boot'],'rtt_ms':rtt}
    self.record('communication','clock_probe',raw=raw);self.metric('link.http_rtt',rtt,'ms','AIPC↔KR260鉴权HTTP时钟探针RTT，扣除对端处理时间')
    self.status['errors'].pop('probe',None)
    if last_rtt is not None:self.metric('link.rtt_variation',abs(rtt-last_rtt),'ms','相邻RTT绝对差；不是PL转发抖动')
    last_rtt=rtt
    mapping={'offset_ns':((t2-start)+(t3-end))/2,'uncertainty_ns':rtt*1e6/2+1_000_000,'updated':time.monotonic(),'boot':d['boot'],'method':'四时间戳最小RTT软件时钟映射；未调整系统时钟，非PTP'}
    if not self.mapping or time.monotonic()-self.mapping['updated']>30 or mapping['uncertainty_ns']<self.mapping['uncertainty_ns']:self.mapping=mapping
   except Exception as e:
    failures+=1;self.record('communication','clock_probe',seq=seq,timeout=True,error=str(e));self.status['errors']['probe']=str(e)
   self.metric('link.probe_timeout_pct',failures/total*100,'%','本进程HTTP探针超时比例；不等同UDP命令丢包率',total=total,failed=failures)
   time.sleep(max(.1,1-(time.monotonic_ns()-start)/1e9))
 def event_loop(self):
  while True:
   try:
    data=self.peer('/events?after='+str(self.cursor));boot=data['boot']
    if boot!=self.peer_boot:self.cursor=0;self.peer_boot=boot;self.udp={};self.pending_motion={}
    self.status['peer_socket_errors']=data.get('socket_errors',{});self.status['collector_drops']+=data.get('overrun',0)
    health=(data.get('overrun',0),str(data.get('socket_errors',{})))
    if health!=getattr(self,'_last_observer_health',None):self.record('fpga','observer_health','kr260',overrun=data.get('overrun',0),socket_errors=data.get('socket_errors',{}),boot=boot);self._last_observer_health=health
    for event in data['events']:
     if event['event_id']<=self.cursor:continue
     self.cursor=event['event_id']
     if event['kind']=='can_binary':
      raw=base64.b64decode(event['data'])
      for iface,local,dlc,reserved,cid,mono,wall,payload in struct.iter_unpack('<BBBBIQQ8s',raw):self.process_event({'kind':'can_frame','interface':['FPGA_CAN0','FPGA_CAN1','FPGA_CAN2','can0'][iface],'can_id':cid,'payload_hex':payload[:dlc].hex(),'direction':'tx_echo'if local else'rx','mono_ns':str(mono),'kernel_wall_ns':str(wall)if wall else None,'boot':boot,'wall':event['wall']})
     elif event['kind']=='can_batch':
      for iface,cid,payload,local,mono,wall in event['frames']:self.process_event({'kind':'can_frame','interface':iface,'can_id':cid,'payload_hex':payload,'direction':'tx_echo'if local else'rx','mono_ns':mono,'kernel_wall_ns':wall,'boot':boot,'wall':event['wall']})
     else:self.process_event(event)
    self.status['errors'].pop('events',None)
   except Exception as e:self.status['errors']['events']=str(e);time.sleep(1)
   time.sleep(.1)
 def process_event(self,e):
  self.record('fpga',e['kind'],'kr260',event=e)
  now=int(e['mono_ns'])
  if e['kind']=='control_udp_rx':
   raw=bytes.fromhex(e['payload_hex'])
   if e['port']==54321 and len(raw)>=28 and raw[:2]==b'\xfc\xfc':
    seq=struct.unpack_from('<I',raw,8)[0];self.udp[seq]=e
    with self.lock:
     if self.active:self.active['stages']['kr260_udp_rx']=self.active['stages'].get('kr260_udp_rx',0)+1
     for side,pending in self.pending_motion.items():
      if pending['event']['seq']==seq and pending['can_tx']is None:
       pending['can_tx']=next((tx for tx in self.can_tx_recent[side]if int(tx['mono_ns'])>=int(e['mono_ns'])),None)
    if len(self.udp)>2000:self.udp.pop(next(iter(self.udp)))
    self.record('communication','control_rx','kr260',seq=seq,event=e)
   return
  if e['kind']!='can_frame':return
  with self.lock:
   if self.active and e['interface']in ('FPGA_CAN0','FPGA_CAN1'):
    stage='can_tx_echo'if e['direction']=='tx_echo'else'can_feedback_rx';self.active['stages'][stage]=self.active['stages'].get(stage,0)+1
  key=e['interface']+'.'+str(e['can_id'])+'.'+e['direction'];stamp=int(e['kernel_wall_ns'])if e.get('kernel_wall_ns')else now;previous=self.last_can.get(key);self.last_can[key]=stamp
  if previous:
   dt=(stamp-previous)/1e6
   if 0<dt<5000:self.metric('can.'+key+'.interval',dt,'ms','相同CAN ID同方向的内核软件接收/本地TX回显时间戳间隔；无硬件SOF时间戳')
  self.motion_event(e)
 def bulk(self,seconds=30,rate_mbps=20):
  with self.lock:
   if self.bulk_busy:raise ValueError('已有持续吞吐测试正在进行')
   self.bulk_busy=True
  ident=uuid.uuid4().hex;task={'id':ident,'kind':'throughput','created':time.time(),'status':'running','profile':'batch-v3','seconds_per_direction':seconds,'rate_limit_mbps':rate_mbps,'path':'AIPC eno1 ↔ KR260 eth0/PS（终止于KR260）；未经过PL转发路径','results':[]};self.store.task(ident,task)
  task['observer_profile']=self.prev.get('kr260',{}).get('observer_profile','unknown')
  def run():
   try:
    rate=int(rate_mbps*1e6/8);size=seconds*rate
    for direction in ['kr260_to_aipc','aipc_to_kr260']:
     start=time.monotonic_ns();interval=start;count=0;window=0;digest=hashlib.sha256();windows=[]
     if direction=='kr260_to_aipc':
      request=urllib.request.Request(self.cfg['peer_url']+f'/bulk?seconds={seconds}&rate={rate}',headers={'Authorization':'Bearer '+self.cfg['token']})
      with urllib.request.urlopen(request,timeout=10)as r:
       while True:
        chunk=r.read(32768)
        if not chunk:break
        count+=len(chunk);window+=len(chunk);digest.update(chunk);now=time.monotonic_ns()
        if now-interval>=1e9:
         point={'bytes':window,'seconds':(now-interval)/1e9};windows.append(point);self.record('communication','bulk_interval',task_id=ident,direction=direction,**point);window=0;interval=now
      remote=None
     else:
      u=urllib.parse.urlsplit(self.cfg['peer_url']);conn=http.client.HTTPConnection(u.hostname,u.port,timeout=10);conn.putrequest('POST','/bulk');conn.putheader('Authorization','Bearer '+self.cfg['token']);conn.putheader('Content-Length',str(size));conn.endheaders();block=b'METRIC01'*4096
      while count<size:
       chunk=block[:min(len(block),size-count)];conn.send(chunk);count+=len(chunk);window+=len(chunk);digest.update(chunk);now=time.monotonic_ns()
       if now-interval>=1e9:
        point={'bytes':window,'seconds':(now-interval)/1e9};windows.append(point);self.record('communication','bulk_interval',task_id=ident,direction=direction,**point);window=0;interval=now
       wait=count/rate-(time.monotonic_ns()-start)/1e9
       if wait>0:time.sleep(wait)
      response=conn.getresponse();remote=json.loads(response.read());conn.close()
      if response.status!=200 or remote['bytes']!=count or remote['sha256']!=digest.hexdigest():raise ValueError('对端字节数或SHA256不匹配')
     elapsed=(time.monotonic_ns()-start)/1e9
     if count!=size:raise ValueError('收到的有效载荷长度不匹配')
     if direction=='kr260_to_aipc':
      expected=hashlib.sha256();left=size;block=b'METRIC01'*4096
      while left:n=min(left,len(block));expected.update(block[:n]);left-=n
      if expected.hexdigest()!=digest.hexdigest():raise ValueError('下载内容校验失败')
     result={'direction':direction,'bytes':count,'seconds':elapsed,'goodput_mbps':count*8/elapsed/1e6,'sha256':digest.hexdigest(),'integrity':'verified','windows':windows,'remote':remote};task['results'].append(result);self.store.task(ident,task);self.record('communication','bulk_result',task_id=ident,result=result)
    task['status']='completed';self.status['errors'].pop('bulk',None)
   except Exception as e:task.update(status='failed',error=str(e));self.status['errors']['bulk']=str(e)
   finally:task['ended']=time.time();self.store.task(ident,task);self.bulk_busy=False
  threading.Thread(target=run,daemon=True).start();return task
 def start(self):
  for f in [self.flush_loop,self.sample_loop,self.probe_loop,self.event_loop,self.trace_loop,self.context_loop,self.udp_probe_loop]:threading.Thread(target=f,daemon=True).start()
  if not any(t.get('profile')=='batch-v3'and t['status']=='completed'for t in self.store.task()):threading.Thread(target=lambda:(time.sleep(5),self.bulk(60,20)),daemon=True).start()

 def udp_probe_loop(self):
  host=urllib.parse.urlsplit(self.cfg['peer_url']).hostname;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(.25);seq=0;missing=0;previous=None
  while True:
   seq+=1;start=time.monotonic_ns();payload=struct.pack('!QQ',seq,start)+b'probe'*20;raw=hmac.new(self.cfg['token'].encode(),payload,hashlib.sha256).digest()+payload
   try:
    s.sendto(raw,(host,18262))
    while True:
     reply,address=s.recvfrom(2048);end=time.monotonic_ns()
     if address[0]!=host or not hmac.compare_digest(reply[:32],hmac.new(self.cfg['token'].encode(),reply[32:],hashlib.sha256).digest()):continue
     rseq,t1=struct.unpack('!QQ',reply[32:48])
     if rseq!=seq:
      if time.monotonic_ns()-start>250_000_000:raise socket.timeout()
      continue
     t2,t3=struct.unpack('!QQ',reply[-16:]);break
    rtt=(end-start-(t3-t2))/1e6;self.metric('link.udp_rtt',rtt,'ms','独立鉴权UDP回显，AIPC发送至收到同序号回包，扣除对端回显处理');self.record('communication','udp_probe',seq=seq,t1=str(t1),t2=str(t2),t3=str(t3),t4=str(end),payload_bytes=len(payload),rtt_ms=rtt)
    if previous is not None:self.metric('link.udp_jitter',abs(rtt-previous),'ms','相邻UDP探针RTT绝对差，端点/调度/网络综合，不是PL内部抖动')
    previous=rtt
   except (OSError,ValueError,struct.error)as e:missing+=1;self.record('communication','udp_probe',seq=seq,timeout=True,error=str(e))
   self.metric('link.udp_loss_pct',100*missing/seq,'%','独立探针往返未成功比例；无法区分去程/回程，非业务控制包丢失',sent=seq,missing=missing)
   time.sleep(max(.01,.2-(time.monotonic_ns()-start)/1e9))

 def trace_loop(self):
  path=Path(self.cfg.get('trace_socket','/run/core-metrics/events.sock'));path.parent.mkdir(parents=True,exist_ok=True);path.unlink(missing_ok=True);s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);s.bind(str(path));os.chmod(path,0o666)
  while True:
   try:
    data=s.recv(60000);e=json.loads(data);self.trace_event(e)
   except Exception as e:self.status['errors']['trace']=str(e)
 def context_loop(self):
  while True:
   try:
    class UnixHTTP(http.client.HTTPConnection):
     def connect(self):self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(2);self.sock.connect('/run/tlz-aipc/adapter.sock')
    conn=UnixHTTP('localhost',timeout=2);conn.request('GET','/pose-context');res=conn.getresponse()
    if res.status==200:self.clock_context=json.loads(res.read())
    else:res.read()
    conn.close();conn=UnixHTTP('localhost',timeout=2);conn.request('GET','/health');res=conn.getresponse()
    if res.status==200:self.clock_context['local']=json.loads(res.read())
    else:res.read()
    conn.close()
    conn=UnixHTTP('localhost',timeout=2);conn.request('GET','/operator-input/latest');res=conn.getresponse();v=json.load(res);conn.close();ev=v.get('event')or{};self.status['vr_input']={k:v.get(k)for k in ['available','fresh','age_ms']};self.status['vr_input'].update(seq=ev.get('seq'),stream_id=ev.get('stream_id'),at=time.time())
    try:
     cfg=json.loads(Path('/home/apex/.config/tlz-v2/direct.json').read_text());host=cfg.get('bind','192.168.137.2');host='127.0.0.1'if host=='0.0.0.0'else host;req=urllib.request.Request('http://'+host+':'+str(cfg.get('port',8088))+'/v2/health',headers={'Authorization':'Bearer '+cfg['tokens']['vr']})
     with urllib.request.urlopen(req,timeout=2)as r:gateway=json.load(r)
     sessions=[s for s in gateway.get('sessions',[])if s.get('role')=='vr'];self.status['vr_gateway']={'at':time.time(),'vr_sessions':len(sessions),'control_connected':any(s.get('control')=='connected'for s in sessions),'operator_age_ms':gateway.get('source_age_ms',{}).get('operator_B_rx_ns'),'operator_forwarded':gateway.get('counts',{}).get('operator_observation_forwarded',0)}
    except Exception as ex:self.status['vr_gateway']={'at':time.time(),'error':str(ex)}
   except Exception:pass
   if self.active and time.time()-self.active['created']>self.active['duration_s']:self.stop_trial()
   time.sleep(1)

 def start_trial(self,data):
  with self.lock:
   if self.active:raise ValueError('已有端到端任务进行中')
   task={'id':uuid.uuid4().hex,'kind':'e2e','created':time.time(),'status':'running','name':str(data.get('name','VR机械臂手动实测'))[:100],'duration_s':min(3600,max(30,int(data.get('duration_s',300)))),'threshold_deg':min(5,max(.05,float(data.get('threshold_deg',.2)))),'endpoint':'同轴CAN编码器反馈相对静止基线连续3帧变化≥阈值；属于运动反馈代理，非外部物理触发器','n':0,'samples':[],'invalid':0,'timeouts':0,'unmatched':0,'notes':'只观测，不使能、不申请控制权、不发送运动；建议每次动作前静止≥0.5秒以进行唯一响应起点关联'}
   task['measurement_version']='software-v2-trace-fix';task['start_mono_ns']=str(time.monotonic_ns());task['stages']={};task['reasons']={};task['capture_drops_at_start']=self.status['collector_drops'];task['observer_errors_at_start']=dict(self.status.get('peer_socket_errors',{}));self.active=task;self.trace={};self.pending_motion={};self.udp.clear();self.can_tx_recent.clear();self.stage_values.clear();self.store.task(task['id'],task);Path(self.cfg.get('trace_socket','/run/core-metrics/events.sock')).with_name('trial.active').touch();self.record('e2e','trial_start',task={k:v for k,v in task.items()if k!='samples'});return task
 def stop_trial(self):
  with self.lock:
   if not self.active:raise ValueError('没有运行中的任务')
   task=self.active;task['status']='completed';task['ended']=time.time();task['incomplete']=len(self.pending_motion);task['capture_drops']=self.status['collector_drops']-task.get('capture_drops_at_start',0);task['capture_loss_detected']=task['capture_drops']>0 or self.status.get('peer_socket_errors',{})!=task.get('observer_errors_at_start',{});self.active=None;self.pending_motion={};Path(self.cfg.get('trace_socket','/run/core-metrics/events.sock')).with_name('trial.active').unlink(missing_ok=True)
   task['summary']=distribution([s['latency_ms']for s in task['samples']if s.get('latency_ms')is not None]);task['partial_summary']=distribution([s['post_aipc_ms']for s in task['samples']]);task['segments']={k:distribution([s['segments'].get(k)for s in task['samples']])for k in ['vr_to_aipc','aipc_queue','ik','send_wait','network','board_to_can','can_to_feedback']};task['stage_summary']={k:distribution(v)for k,v in self.stage_values.items()};self.store.task(task['id'],task);self.record('e2e','trial_stop',task_id=task['id'],summary=task['summary']);return task
 def stage_span(self,key,ms,event):
  if ms is None or not math.isfinite(ms)or ms<0:return
  self.stage_values[key].append(ms);self.record('e2e','measured_stage_span',task_id=self.active['id'],stage=key,duration_ms=ms,trace=event.get('trace'),side=event.get('side'))
 def source_delay(self,source):
  try:
   maps=self.clock_context['clock_mappings'];v=maps[str(source['source_node_id'])];a=maps[str(self.clock_context['local']['node_id'])];a_rx=int(source['a_rx_ns'])
   if int(v['epoch'])!=int(source['clock_epoch']):return None,None,'vr_epoch_changed'
   vbase=int(v['ref_B'])+(int(source['origin_ns'])-int(v['ref_X']));abase=int(a['ref_B'])+(a_rx-int(a['ref_X']));age=(abase-int(v['updated_B_ns']))/1e9
   if not 0<=age<=2:return None,None,'vr_mapping_stale'
   delay=(abase-vbase)/1e6;unc=(int(v['uncertainty_ns'])+int(a['uncertainty_ns']))/1e6
   return (delay,unc,None)if delay>=0 else(None,unc,'vr_mapping_negative_estimate')
  except (KeyError,ValueError,TypeError):return None,None,'vr_mapping_missing'
 def reason(self,name):
  self.active['reasons'][name]=self.active['reasons'].get(name,0)+1
 def trace_event(self,e):
  with self.lock:
   if not self.active:return
   trace=e.get('trace');stage=e.get('stage')
   if not isinstance(trace,str)or len(trace)>200:return
   self.active['stages'][stage]=self.active['stages'].get(stage,0)+1
   self.record('e2e','stage',task_id=self.active['id'],event=e)
   key=(trace,e.get('side',''));state=self.trace.setdefault(key,{})
   state[stage]=e
   if len(self.trace)>10000:self.trace.pop(next(iter(self.trace)))
   source=e.get('source',{});now=int(e.get('mono_ns',0))
   if stage=='input_consumed':
    self.stage_span('input_to_consume',(now-int(source.get('a_rx_ns',now)))/1e6,e);delay,unc,why=self.source_delay(source)
    if delay is not None:self.stage_span('vr_to_aipc',delay,e)
    else:self.reason(why)
   if stage=='ik_submitted':self.stage_span('aipc_queue',(now-int(source.get('a_rx_ns',now)))/1e6,e)
   if stage=='ik_accepted':self.stage_span('ik',(now-int(e.get('ik_submit_ns',now)))/1e6,e)
   if stage=='udp_sent':
    self.stage_span('send_wait',(now-int(e.get('ik_accept_ns',now)))/1e6,e);self.stage_span('aipc_to_send',(now-int(source.get('a_rx_ns',now)))/1e6,e)
    if int(e.get('source',{}).get('a_rx_ns','0'))<int(self.active['start_mono_ns']):self.active['unmatched']+=1;return
    side=e['side'];pending=self.pending_motion.get(side)
    # Only isolated onset trials are eligible; do not invent per-packet causality during continuous motion.
    last=self.pose.get(side)
    if pending:self.active['unmatched']+=1;self.reason('previous_response_pending');return
    if not last or time.monotonic()-last['received']>1:self.active['unmatched']+=1;self.reason('no_fresh_feedback_baseline');return
    if time.monotonic()-last.get('moving_at',0)<.5:self.active['unmatched']+=1;self.reason('feedback_not_quiet');return
    self.pending_motion[side]={'event':e,'trace':state,'baseline':list(last['axes']),'received':time.monotonic(),'can_tx':None,'axis_crossings':{}}
 def motion_event(self,e):
  side='left'if e['interface']=='FPGA_CAN0'else'right'if e['interface']=='FPGA_CAN1'else None
  if not side:return
  cid=e['can_id']&0x1fffffff;data=bytes.fromhex(e['payload_hex']);now=time.monotonic()
  with self.lock:
   pose=self.pose.setdefault(side,{'axes':[None]*6,'received':now,'moving_at':0});pending=self.pending_motion.get(side)
   if pending and now-pending['received']>2:
    if self.active:self.active['timeouts']+=1
    self.pending_motion.pop(side,None);pending=None
   if e['direction']=='tx_echo'and (0x155<=cid<=0x157 or 0x15A<=cid<=0x15F):
    self.can_tx_recent[side].append(e)
    if pending and pending['can_tx']is None:
     udp=self.udp.get(pending['event']['seq'])
     if udp and int(e['mono_ns'])>=int(udp['mono_ns']):pending['can_tx']=e
    return
   values=[]
   if e['direction']!='rx' or len(data)!=8:return
   if 0x251<=cid<=0x256:values=[(cid-0x251,struct.unpack('>i',data[4:])[0]/1000*180/math.pi)]
   else:return
   for axis,value in values:
    old=pose['axes'][axis]
    if old is not None and abs(value-old)>max(.1,(self.active or{}).get('threshold_deg',.2)*.5):pose['moving_at']=now
    pose['axes'][axis]=value
   pose['received']=now
   if not pending or not self.active or not pending['can_tx']:return
   if int(e['mono_ns'])<int(pending['can_tx']['mono_ns']):return
   if any(v is None for v in pending['baseline']):return
   for axis,_ in values:
    if abs(pose['axes'][axis]-pending['baseline'][axis])<self.active['threshold_deg']:pending['axis_crossings'].pop(axis,None);continue
    count,first=pending['axis_crossings'].get(axis,(0,e));pending['axis_crossings'][axis]=(count+1,first)
    if count+1>=3:self.complete_motion(side,pending,first);self.pending_motion.pop(side,None);break
 def complete_motion(self,side,pending,feedback):
  task=self.active;sent=pending['event'];trace=pending['trace'];udp=self.udp.get(sent['seq']);consume=sent.get('source',{});mapping=self.mapping
  if not udp or not mapping or mapping['boot']!=feedback['boot']or time.monotonic()-mapping['updated']>35:
   task['invalid']+=1;self.reason('udp_seq_not_observed'if not udp else'board_clock_mapping_unavailable');return
  # KR260 durations are differences on KR260; only transport span uses a bounded cross-clock mapping.
  send_ns=int(sent['mono_ns']);rx_ns=int(udp['mono_ns']);can_ns=int(pending['can_tx']['mono_ns']);fb_ns=int(feedback['mono_ns']);a_rx=int(consume.get('a_rx_ns',send_ns));offset=mapping['offset_ns'];network=(rx_ns-offset-send_ns)/1e6
  if network<0 or not a_rx<=send_ns or not rx_ns<=can_ns<=fb_ns:
   task['invalid']+=1;self.reason('negative_network_estimate'if network<0 else'invalid_stage_order');self.record('e2e','unmatched_response',task_id=task['id'],side=side,raw={'sent':sent,'udp':udp,'can_tx':pending['can_tx'],'feedback':feedback,'mapping':mapping});return
  segments={'aipc_queue':(int(sent.get('ik_submit_ns',send_ns))-a_rx)/1e6,'ik':(int(sent.get('ik_accept_ns',send_ns))-int(sent.get('ik_submit_ns',send_ns)))/1e6,'send_wait':(send_ns-int(sent.get('ik_accept_ns',send_ns)))/1e6,'network':network,'board_to_can':(can_ns-rx_ns)/1e6,'can_to_feedback':(fb_ns-can_ns)/1e6};vr_delay=None;vr_uncertainty=None
  try:
   maps=self.clock_context['clock_mappings'];v=maps[str(consume['source_node_id'])];a=maps[str(self.clock_context['local']['node_id'])]
   if int(v['epoch'])!=int(consume['clock_epoch']):raise ValueError('VR epoch changed')
   vbase=int(v['ref_B'])+(int(consume['origin_ns'])-int(v['ref_X']));abase=int(a['ref_B'])+(a_rx-int(a['ref_X']));age=(abase-int(v['updated_B_ns']))/1e9
   if not 0<=age<=2:raise ValueError('mapping stale')
   vr_delay=(abase-vbase)/1e6;vr_uncertainty=(int(v['uncertainty_ns'])+int(a['uncertainty_ns']))/1e6
   if vr_delay<0:vr_delay=None
  except (KeyError,ValueError,StopIteration,TypeError):pass
  segments['vr_to_aipc']=vr_delay;post=sum(v for k,v in segments.items()if k!='vr_to_aipc');sample={'trace':sent['trace'],'side':side,'seq':sent['seq'],'latency_ms':post+vr_delay if vr_delay is not None else None,'post_aipc_ms':post,'segments':segments,'network_uncertainty_ms':mapping['uncertainty_ns']/1e6,'vr_uncertainty_ms':vr_uncertainty,'endpoint_proxy':True,'correlation':'静止后响应起点时序关联；CAN首帧关联不是执行端逐命令确认','raw':{'sent':sent,'udp':udp,'can_tx':pending['can_tx'],'feedback':feedback,'mapping':mapping,'baseline':pending['baseline']}}
  task['n']+=1;task['samples'].append(sample);self.record('e2e','response_sample',task_id=task['id'],sample=sample);self.store.task(task['id'],task)
  if len(task['samples'])>=10000:self.stop_trial()
 def report(self):
  with self.lock:
   current=dict(self.active)if self.active else None
   if current:
    current['stage_summary']={k:distribution(v)for k,v in self.stage_values.items()}
    current['summary']=distribution([s['latency_ms']for s in current['samples']if s['latency_ms']is not None]);current['partial_summary']=distribution([s['post_aipc_ms']for s in current['samples']]);current['segments']={k:distribution([s['segments'].get(k)for s in current['samples']])for k in ['vr_to_aipc','aipc_queue','ik','send_wait','network','board_to_can','can_to_feedback']};current['samples']=current['samples'][-10:]
   tasks=self.store.task()
   for task in tasks:
    if 'samples'in task:task['samples']=task['samples'][-10:]
   jitter={}
   for k,v in self.values.items():
    if not k.startswith('can.')or len(v)<2:continue
    median=statistics.median(v);jitter[k]={'std_ms':statistics.pstdev(v),'p95_absolute_deviation_ms':distribution([abs(x-median)for x in v])['p95'],'n':len(v)}
   return {'status':dict(self.status),'interfaces':self.prev.get('kr260',{}).get('interfaces',{}),'metrics':dict(self.latest),'distributions':{k:distribution(v)for k,v in self.values.items()},'can_jitter':jitter,'series':{k:list(v)[-120:]for k,v in self.series.items()},'storage':self.store.usage(),'clock_mapping':self.mapping,'trial':current,'tasks':tasks,'bulk_busy':self.bulk_busy,'capabilities':{'can0_can1':'PS Xilinx CAN，经PL映射到J20；不是PL CAN加速','can2':'PL CTU CAN，当前DOWN，不自动启用','bridge':'Linux软件bridge，PL Ethernet MAC接入；未启用PL硬件交换offload','pure_pl_latency':'需要PL同计数器入口/出口计数或ILA，当前无可用逐包时间戳','physical_onset':'CAN编码器变化是代理终点，严格物理起点需要同步外部传感器','one_way':'软件四时间戳映射，给出不确定度；无PTP时不声称精确单向延迟'}}

"""Verified VR discovery and last-success memory; no live start/stop side effects."""
import asyncio,ipaddress,json,re,time
from pathlib import Path
import aiohttp

def private_host(host):
    try:address=ipaddress.IPv4Address(host)
    except (ValueError,TypeError):return False
    return any(address in ipaddress.IPv4Network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))

def valid_status(data):
    return (isinstance(data,dict) and type(data.get('streaming')) is bool
            and isinstance(data.get('config'),dict)
            and all(type(data['config'].get(k)) is int and 1<=data['config'][k]<=8192 for k in ('width','height'))
            and ('live_policy_revision' in data or 'encoder' in data))

class VRDirectory:
    def __init__(self,receiver,path='/home/apex/.config/aipc-vr-devices.json'):
        self.receiver=receiver;self.path=Path(path);self.history={'version':1,'last_successful_host':'','last_successful_mac':'','devices':{}}
        try:
            stored=json.loads(self.path.read_text())
            if isinstance(stored,dict) and isinstance(stored.get('devices'),dict):self.history.update(stored)
        except (OSError,ValueError):pass
        self.rows={};self.macs={};self.self_ips=set();self.networks=[];self.scanning=False;self.checked_at=None;self.error='';self.last_flush=0;self.last_full=0;self.lock=asyncio.Lock();self.task=None
        previous=self.history.get('last_successful_host')
        if private_host(previous):receiver.config['host']=previous

    def remember(self,host,status):
        now=time.time();old=self.history['devices'].get(host,{});mac=self.macs.get(host) or old.get('mac','')
        changed=self.history.get('last_successful_host')!=host or host not in self.history['devices']
        entry={**old,'last_success_at':now,'mac':mac,'first_success_at':old.get('first_success_at',now)}
        self.history['devices'][host]=entry;self.history['last_successful_host']=host
        if mac:self.history['last_successful_mac']=mac
        self.rows[host]={'host':host,'online':True,'verified':True,'checked_at':now,'streaming':status.get('streaming'), 'width':status['config']['width'],'height':status['config']['height'],'fps':status['config'].get('fps')}
        if changed or now-self.last_flush>=30:
            self.history['devices']=dict(sorted(self.history['devices'].items(),key=lambda item:item[1].get('last_success_at',0),reverse=True)[:32])
            try:
                self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.history));temp.chmod(0o600);temp.replace(self.path)
            except OSError:self.error='当前连接正常，但无法保存 VR 连接历史'
            self.last_flush=now

    async def command_json(self,*args):
        try:
            process=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            try:raw,_=await asyncio.wait_for(process.communicate(),2)
            except asyncio.TimeoutError:process.kill();await process.communicate();return []
            return json.loads(raw)
        except (OSError,ValueError):return []

    async def candidates(self,full=False):
        addresses,neighbors=await asyncio.gather(self.command_json('ip','-j','-4','addr'),self.command_json('ip','-j','neigh'))
        own=set();networks=[]
        for interface in addresses:
            if interface.get('ifname')=='lo':continue
            for address in interface.get('addr_info',[]):
                host=address.get('local');prefix=address.get('prefixlen',0)
                if private_host(host):
                    own.add(host)
                    if 24<=prefix<=30:networks.append(ipaddress.IPv4Network(str(host)+'/'+str(prefix),strict=False))
        self.self_ips=own;self.networks=networks
        candidates=set(self.history['devices'])|{self.receiver.config.get('host','')}
        for n in neighbors:
            host=n.get('dst')
            if private_host(host):
                candidates.add(host)
                if n.get('lladdr'):self.macs[host]=n['lladdr'].lower()
        try:
            process=await asyncio.create_subprocess_exec('ss','-ntH','state','established','sport = :8088',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            try:raw,_=await asyncio.wait_for(process.communicate(),2)
            except asyncio.TimeoutError:process.kill();await process.communicate();raw=b''
            candidates.update(re.findall(r'(\d+\.\d+\.\d+\.\d+):\d+',raw.decode(errors='replace')))
        except OSError:pass
        for folder in ('/var/lib/NetworkManager','/var/lib/misc'):
            for file in Path(folder).glob('*leases*'):
                try:candidates.update(re.findall(r'\b(?:10|172|192)\.\d+\.\d+\.\d+\b',file.read_text()[:262144]))
                except (OSError,UnicodeError):pass
        priority=sorted(h for h in candidates if private_host(h) and h not in own)
        if full:
            for network in sorted(set(networks),key=lambda n:0 if str(n).startswith('192.168.137.') else 1)[:2]:
                priority.extend(str(ip) for ip in network.hosts() if str(ip) not in own)
        return list(dict.fromkeys(priority))[:512 if full else 64]

    async def probe(self,host,token=None,timeout=1):
        if not private_host(host) or host in self.self_ips:return None
        try:
            async with self.receiver.http.get('http://'+host+':8095/v1/view/status',headers={'Authorization':'Bearer '+(token or self.receiver.config['token'])},allow_redirects=False,timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status!=200:return None
                chunks=[];size=0
                async for part in response.content.iter_chunked(16384):
                    size+=len(part)
                    if size>131072:return None
                    chunks.append(part)
                result=json.loads(b''.join(chunks))
                return result if valid_status(result) else None
        except (aiohttp.ClientError,asyncio.TimeoutError,ValueError):return None

    async def scan(self,full=True):
        if self.lock.locked():return []
        async with self.lock:
            self.scanning=True;self.error=''
            try:
                hosts=await self.candidates(full);gate=asyncio.Semaphore(32)
                async def check(host):
                    async with gate:
                        status=await self.probe(host,timeout=.75 if full else 1)
                    if status:
                        self.rows[host]={'host':host,'online':True,'verified':True,'checked_at':time.time(),'streaming':status['streaming'],'width':status['config']['width'],'height':status['config']['height'],'fps':status['config'].get('fps')}
                    elif host in self.rows:self.rows[host].update(online=False,checked_at=time.time())
                    return (host,status) if status else None
                found=[v for v in await asyncio.gather(*(check(host) for host in hosts)) if v]
                for neighbor in await self.command_json('ip','-j','neigh'):
                    if neighbor.get('lladdr'):self.macs[neighbor.get('dst')]=neighbor['lladdr'].lower()
                self.checked_at=time.time()
                if full:self.last_full=time.monotonic()
                return found
            except (OSError,ValueError) as error:self.error='地址识别暂不可用';return []
            finally:self.scanning=False

    def public(self):
        now=time.time();hosts=set(self.history['devices'])|set(self.rows)
        if self.receiver.config.get('host'):hosts.add(self.receiver.config['host'])
        devices=[]
        for host in hosts:
            row=self.rows.get(host,{});past=self.history['devices'].get(host,{})
            devices.append({**row,'host':host,'online':bool(row.get('online') and now-row.get('checked_at',0)<40),'verified':bool(row.get('verified') or past),'last_success_at':past.get('last_success_at'),'selected':host==self.receiver.config.get('host'),'last_successful':host==self.history.get('last_successful_host')})
        devices.sort(key=lambda d:(not d['selected'],not d['online'],not d['last_successful'],d['host']))
        return {'devices':devices,'scanning':self.scanning,'checked_at':self.checked_at,'last_successful_host':self.history.get('last_successful_host',''),'error':self.error,'multiple_online':sum(d['online'] for d in devices)>1}

    async def watch(self):
        await asyncio.sleep(2)
        while True:
            try:
                if not self.receiver.latest.get('reachable'):
                    full=time.monotonic()-self.last_full>120
                    found=await self.scan(full)
                    current=self.receiver.config.get('host')
                    if any(host==current for host,_ in found):pass
                    else:
                        last=self.history.get('last_successful_host');mac=self.history.get('last_successful_mac')
                        exact=[host for host,_ in found if host==last or (mac and self.macs.get(host)==mac)]
                        host=exact[0] if len(exact)==1 else found[0][0] if len(found)==1 else None
                        if host:await self.receiver.command({'action':'configure','host':host})
                await asyncio.sleep(15)
            except asyncio.CancelledError:raise
            except (OSError,ValueError,aiohttp.ClientError):await asyncio.sleep(15)

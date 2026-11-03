"""Shared unprivileged Linux resources and services collector."""
import json,os,pwd,socket,subprocess,threading,time
from pathlib import Path
def read(path,default=''):
    try:return Path(path).read_text().strip()
    except OSError:return default
def command(args,timeout=4):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=True)
    return json.loads(result.stdout)
def cadence(interval,task):
    deadline=time.monotonic()
    while True:
        task();deadline+=interval;now=time.monotonic()
        if deadline<now:deadline=now+interval
        time.sleep(max(0,deadline-now))
class Resources:
    def __init__(self,address='192.168.137.224'):self.address=address;self.previous={};self.proc={};self.at=None;self.hz=os.sysconf('SC_CLK_TCK');self.pages=os.sysconf('SC_PAGE_SIZE');self.users={}
    def sample(self):
        now=time.monotonic();elapsed=now-self.at if self.at else None;self.at=now;cpus=[]
        for row in read('/proc/stat').splitlines():
            cols=row.split()
            if not cols or not cols[0].startswith('cpu'):continue
            vals=list(map(int,cols[1:9]));total=sum(vals);idle=vals[3]+vals[4];prev=self.previous.get(cols[0]);usage=None
            if prev and total>prev[0]:usage=round(100*(1-(idle-prev[1])/(total-prev[0])),1)
            self.previous[cols[0]]=(total,idle);cpus.append({'id':cols[0],'percent':usage})
        mem={k:int(v.split()[0])*1024 for k,v in (row.split(':',1) for row in read('/proc/meminfo').splitlines())};total=mem.get('MemTotal',0);avail=mem.get('MemAvailable',0)
        processes=[];seen={};uptime=float(read('/proc/uptime','0').split()[0])
        for p in Path('/proc').iterdir():
            if not p.name.isdigit():continue
            try:
                stat=(p/'stat').read_text();end=stat.rfind(')');name=stat[stat.index('(')+1:end];s=stat[end+2:].split();pid=int(p.name);ticks=int(s[11])+int(s[12]);start=int(s[19]);prev=self.proc.get((pid,start));cpu=round(max(0,(ticks-prev)/self.hz/elapsed*100),1) if prev is not None and elapsed else None;seen[(pid,start)]=ticks
                uid=p.stat().st_uid
                if uid not in self.users:
                    try:self.users[uid]=pwd.getpwuid(uid).pw_name
                    except KeyError:self.users[uid]=str(uid)
                processes.append({'pid':pid,'name':name,'ppid':int(s[1]),'state':s[0],'user':self.users[uid],'uid':uid,'cpu_percent':cpu,'rss':int(s[21])*self.pages,'memory_percent':round(int(s[21])*self.pages/total*100,2) if total else 0,'threads':int(s[17]),'nice':int(s[16]),'age_seconds':max(0,round(uptime-start/self.hz))})
            except (OSError,ValueError,IndexError):continue
        self.proc=seen;disks=[];mounts=set();devices=set()
        for line in read('/proc/mounts').splitlines():
            cols=line.split()
            if len(cols)<3 or cols[2] not in ('ext4','ext3','ext2','xfs','btrfs','vfat','exfat','f2fs','zfs','ntfs3'):continue
            mount=cols[1].replace('\\040',' ')
            if mount in mounts:continue
            mounts.add(mount)
            try:
                device_id=os.stat(mount).st_dev
                if device_id in devices:continue
                devices.add(device_id)
                st=os.statvfs(mount);capacity=st.f_blocks*st.f_frsize;used=(st.f_blocks-st.f_bfree)*st.f_frsize;free=st.f_bavail*st.f_frsize
                disks.append({'mount':mount,'device':cols[0],'filesystem':cols[2],'total':capacity,'used':used,'available':free,'percent':round(used/capacity*100,1) if capacity else 0})
            except OSError:pass
        return {'cpu':{'percent':cpus[0]['percent'] if cpus else None,'cores':cpus[1:],'load':read('/proc/loadavg').split()[:3]},'memory':{'total':total,'used':total-avail,'available':avail,'percent':round((total-avail)/total*100,1) if total else 0,'swap_total':mem.get('SwapTotal',0),'swap_used':mem.get('SwapTotal',0)-mem.get('SwapFree',0)},'disks':disks,'processes':processes,'host':{'hostname':socket.gethostname(),'kernel':os.uname().release,'uptime':float(read('/proc/uptime','0').split()[0]),'address':self.address},'sampled_at':time.time(),'cpu_process_basis':'进程 100% 为一个 CPU 核心；整机按全部核心归一化'}
_SERVICE_FILES=[];_SERVICE_FILES_AT=0;_SERVICE_FILES_BUSY=False;_SERVICE_LOCK=threading.RLock()
def refresh_service_files():
    global _SERVICE_FILES,_SERVICE_FILES_AT,_SERVICE_FILES_BUSY
    try:
        data=command(['systemctl','list-unit-files','--type=service','--output=json','--no-pager'],timeout=20)
        with _SERVICE_LOCK:_SERVICE_FILES=data
    except Exception:pass
    finally:
        with _SERVICE_LOCK:_SERVICE_FILES_AT=time.monotonic();_SERVICE_FILES_BUSY=False
def service_list():
    global _SERVICE_FILES_BUSY
    units=command(['systemctl','list-units','--type=service','--all','--output=json','--no-pager'])
    with _SERVICE_LOCK:
        if time.monotonic()-_SERVICE_FILES_AT>30 and not _SERVICE_FILES_BUSY:
            _SERVICE_FILES_BUSY=True;threading.Thread(target=refresh_service_files,daemon=True).start()
        files=list(_SERVICE_FILES)
    enabled={u['unit_file']:u.get('state','unknown') for u in files}
    names={u['unit'] for u in units}
    for u in files:
        if u['unit_file'] not in names:units.append({'unit':u['unit_file'],'active':'unloaded','sub':'unloaded','load':'unloaded','description':''})
    for u in units:u['enabled']=enabled.get(u['unit'],'unknown')
    return units

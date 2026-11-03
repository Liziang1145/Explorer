"""Bounded raw measurement store. Whole SQLite shards are FIFO-retained, never partial records."""
import json,os,sqlite3,threading,time,uuid,zlib,shutil
from pathlib import Path

LEGACY_PROJECTS=('e2e','fpga','communication')
PROJECTS={'e2e':2048,'fpga':1024,'communication':512,'vla':1024}
VLA_EXTRA_BYTES=5_000_000_000
def owner(record):
 return record.get('task_id') or (record.get('task',{}).get('id') if record.get('kind')=='trial_start' else None)
class Store:
 def __init__(self,root,limit=50_000_000_000,shard_limit=16*1024**2):
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.limit=limit;self.total_limit=limit+VLA_EXTRA_BYTES;self.shard_limit=shard_limit;self.lock=threading.RLock();self.active={};self.sizes=dict(PROJECTS);self.evicted=0
  self.catalog=sqlite3.connect(self.root/'catalog.sqlite3',check_same_thread=False);self.catalog.row_factory=sqlite3.Row
  self.catalog.executescript('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,created REAL,status TEXT,data TEXT);CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);')
  self.catalog.execute('PRAGMA journal_mode=TRUNCATE');self.catalog.commit()
  self.catalog.execute('CREATE TABLE IF NOT EXISTS deleted_tasks(id TEXT PRIMARY KEY,deleted REAL)');self.catalog.commit()
  self.deleted={r[0] for r in self.catalog.execute('SELECT id FROM deleted_tasks')}
  for k in PROJECTS:
   r=self.catalog.execute('SELECT value FROM settings WHERE key=?',('weight:'+k,)).fetchone()
   if r:self.sizes[k]=float(r[0])
 def _files(self):return sorted(self.root.glob('*-*.sqlite3'),key=lambda p:p.name.split('-',1)[1])
 def usage(self):
  totals={k:0 for k in PROJECTS};physical=sum(p.stat().st_size for p in self.root.iterdir()if p.is_file())
  for p in self._files():totals[p.name.split('-',1)[0]]+=p.stat().st_size
  weight=sum(self.sizes[k] for k in LEGACY_PROJECTS)
  quotas={k:int(self.limit*.98*self.sizes[k]/weight) for k in LEGACY_PROJECTS}
  quotas['vla']=int(VLA_EXTRA_BYTES*.98)
  return {'limit_bytes':self.total_limit,'legacy_limit_bytes':self.limit,'vla_extra_limit_bytes':VLA_EXTRA_BYTES,'physical_bytes':physical,'projects':{k:{'bytes':totals[k],'quota_bytes':quotas[k],'mean_record_bytes':round(self.sizes[k],2)}for k in PROJECTS},'evicted_shards':self.evicted,'policy':'原三类维持原50GB加权份额；VLA独立新增5GB；超额项目优先FIFO，最后全局FIFO','disk_free_bytes':shutil.disk_usage(self.root).free}
 def _rotate(self,project):
  item=self.active.pop(project,None)
  if item:item[1].close()
 def _make_room(self,extra):
  info=self.usage();reserve=min(2*1024**3,max(0,self.total_limit//10));need=max(info['physical_bytes']+extra-self.total_limit,reserve+extra-info['disk_free_bytes'])
  if need<=0:return
  for key in list(self.active):self._rotate(key)
  paths=self._files();over={k for k,v in info['projects'].items()if v['bytes']>v['quota_bytes']}
  paths.sort(key=lambda p:(p.name.split('-',1)[0]not in over,p.name.split('-',1)[1]))
  for p in paths:
   size=p.stat().st_size;p.unlink();self.evicted+=1;need-=size
   if need<=0:return
  if need>0:raise OSError('测量磁盘空间不足，已停止写入；业务控制不受影响')
 def write(self,records):
  if not records:return
  with self.lock:
   groups={k:[]for k in PROJECTS}
   for r in records:
    if owner(r) in self.deleted:continue
    project=r['project'];raw=json.dumps(r,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();packed=zlib.compress(raw,1)if len(raw)>512 else raw;compressed=len(packed)<len(raw);encoded=packed if compressed else raw
    groups[project].append((r.get('wall',time.time()),r.get('kind','sample'),r.get('node','aipc'),encoded,int(compressed)))
    self.sizes[project]=self.sizes[project]*.999+(len(encoded)+96)*.001
   self._make_room(sum(len(r[3])+256 for rows in groups.values()for r in rows)+65536)
   for project,rows in groups.items():
    if not rows:continue
    item=self.active.get(project)
    if item and(item[0].stat().st_size>=self.shard_limit or time.time()-item[2]>1800):self._rotate(project);item=None
    if not item:
     path=self.root/(project+'-'+str(time.time_ns())+'-'+uuid.uuid4().hex[:8]+'.sqlite3');db=sqlite3.connect(path,check_same_thread=False);db.execute('PRAGMA journal_mode=TRUNCATE');db.execute('CREATE TABLE samples(id INTEGER PRIMARY KEY,wall REAL,kind TEXT,node TEXT,payload BLOB,compressed INTEGER)');db.execute('CREATE INDEX sample_kind ON samples(kind,wall)');item=(path,db,time.time());self.active[project]=item
    item[1].executemany('INSERT INTO samples(wall,kind,node,payload,compressed) VALUES(?,?,?,?,?)',rows);item[1].commit()
   for k,v in self.sizes.items():self.catalog.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('weight:'+k,str(v)))
   self.catalog.commit();self._make_room(0)
 def recent(self,project=None,kind=None,limit=300,since=0):
  result=[]
  with self.lock:
   for p in reversed(self._files()):
    if project and not p.name.startswith(project+'-'):continue
    with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True)as db:
     sql='SELECT payload,compressed FROM samples WHERE wall>=?';args=[since]
     if kind:sql+=' AND kind=?';args.append(kind)
     sql+=' ORDER BY id DESC LIMIT ?';args.append(limit-len(result))
     for payload,compressed in db.execute(sql,args):result.append(json.loads(zlib.decompress(payload)if compressed else payload))
    if len(result)>=limit:break
  return result
 def task(self,ident=None,data=None):
  with self.lock:
   if data is not None:
    if ident in self.deleted:return None
    compact=dict(data)
    if 'samples'in compact:compact['samples']=compact['samples'][-10:]
    self.catalog.execute('INSERT OR REPLACE INTO tasks VALUES(?,?,?,?)',(ident,data['created'],data['status'],json.dumps(compact,ensure_ascii=False)));self.catalog.commit();return data
   if ident:
    r=self.catalog.execute('SELECT data FROM tasks WHERE id=?',(ident,)).fetchone();return json.loads(r[0])if r else None
   return [json.loads(r[0])for r in self.catalog.execute('SELECT data FROM tasks ORDER BY created DESC LIMIT 100')]
 def task_records(self,ident):
  # Task-owned events live in e2e/communication/vla. Shared CAN monitoring is not owned by a round.
  for p in self._files():
   if not p.name.startswith(('e2e-','communication-','vla-')):continue
   with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True,timeout=10) as db:
    for payload,compressed in db.execute('SELECT payload,compressed FROM samples ORDER BY id'):
     raw=zlib.decompress(payload) if compressed else payload
     record=json.loads(raw)
     if owner(record)==ident:yield record
 def delete_task(self,ident):
  with self.lock:
   task=self.task(ident)
   if not task:raise KeyError('任务不存在')
   if task['status']=='running':raise ValueError('请先结束本轮测量')
   self.deleted.add(ident)
   self.catalog.execute('INSERT OR REPLACE INTO deleted_tasks VALUES(?,?)',(ident,time.time()));self.catalog.commit()
   count=0
   for project in ['e2e','communication','vla']:self._rotate(project)
   for p in self._files():
    if not p.name.startswith(('e2e-','communication-','vla-')):continue
    with sqlite3.connect(p,timeout=10) as db:
     ids=[]
     for rowid,payload,compressed in db.execute('SELECT id,payload,compressed FROM samples'):
      if owner(json.loads(zlib.decompress(payload) if compressed else payload))==ident:ids.append((rowid,))
     if ids:
      db.execute('PRAGMA secure_delete=ON');db.executemany('DELETE FROM samples WHERE id=?',ids);db.commit();db.execute('VACUUM');count+=len(ids)
   self.catalog.execute('PRAGMA secure_delete=ON');self.catalog.execute('DELETE FROM tasks WHERE id=?',(ident,));self.catalog.commit();self.catalog.execute('VACUUM')
   return {'id':ident,'deleted_records':count,'shared_monitoring_retained':True}
 def close(self):
  with self.lock:
   for project in list(self.active):self._rotate(project)
   self.catalog.close()

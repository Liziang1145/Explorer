import json,os,time,urllib.parse
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from metrics import Engine
from rounds import Rounds,report
ROOT=Path(__file__).resolve().parent
CFG=json.loads(Path(os.environ.get('CORE_METRICS_CONFIG','/home/apex/.config/core-metrics.json')).read_text())
ENGINE=Engine(CFG)
ROUNDS=Rounds(ENGINE)
class Handler(BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def reply(self,data,code=200):
  raw=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  u=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(u.query)
  try:
   if u.path=='/status':self.reply(ENGINE.report());return
   if u.path=='/vla/history':
    self.reply({'tasks':[t for t in ENGINE.store.task() if t.get('kind')=='vla']});return
   if u.path=='/vla/task':
    ident=q.get('id',[''])[0];task=ENGINE.store.task(ident)
    self.reply({'task':task if task and task.get('kind')=='vla' else None});return
   if u.path=='/vla/records':
    ident=q.get('id',[''])[0];task=ENGINE.store.task(ident)
    if not task or task.get('kind')!='vla':self.reply({'error':'task not found'},404);return
    rows=[]
    for item in ENGINE.store.task_records(ident):
     if item.get('kind') in ('vla_sample','vla_legacy_trial'):
      rows.append(item)
     if len(rows)>=1000:break
    self.reply({'items':rows});return
   if u.path=='/raw':
    project=q.get('project',[None])[0];kind=q.get('kind',[None])[0];limit=min(2000,max(1,int(q.get('limit',['100'])[0])));self.reply({'items':ENGINE.store.recent(project,kind,limit,float(q.get('since',['0'])[0]))});return
   if u.path=='/report':
    task=ENGINE.store.task(q.get('id',[''])[0])
    if not task:self.reply({'error':'task not found'},404);return
    lines=report(task).splitlines()
    raw='\n'.join(lines).encode();self.send_response(200);self.send_header('Content-Type','text/markdown; charset=utf-8');self.send_header('Content-Disposition','attachment; filename=core-metrics-report.md');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
   if u.path=='/round/archive/status':self.reply(ROUNDS.get(q.get('job',[''])[0]));return
   if u.path=='/round/archive/download':
    path,job=ROUNDS.download(q.get('job',[''])[0]);self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Disposition','attachment; filename=VR-arm-'+job['task_id']+'.zip');self.send_header('Content-Length',str(path.stat().st_size));self.send_header('Cache-Control','no-store');self.end_headers()
    with path.open('rb') as f:
     while True:
      chunk=f.read(65536)
      if not chunk:break
      self.wfile.write(chunk)
    return
   if u.path=='/export':
    project=q.get('project',[None])[0];task_id=q.get('task_id',[None])[0]
    if project and project not in ['e2e','fpga','communication','vla']:raise ValueError('invalid project')
    self.send_response(200);self.send_header('Content-Type','application/x-ndjson');self.send_header('Content-Disposition','attachment; filename=core-metrics-raw.ndjson');self.send_header('Connection','close');self.end_headers();self.close_connection=True
    # SQLite snapshots per shard. Exports never keep the writer lock during a browser download.
    import sqlite3,zlib
    for p in ENGINE.store._files():
     if project and not p.name.startswith(project+'-'):continue
     try:
      with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True,timeout=1)as db:
       for raw,compressed in db.execute('SELECT payload,compressed FROM samples ORDER BY id'):
        raw=zlib.decompress(raw)if compressed else raw
        if task_id and json.loads(raw).get('task_id')!=task_id:continue
        self.wfile.write(raw+b'\n')
     except sqlite3.Error:continue
    return
   self.reply({'error':'not found'},404)
  except (BrokenPipeError,ConnectionResetError):self.close_connection=True
  except KeyError as e:self.reply({'error':str(e)},404)
  except Exception as e:self.reply({'error':str(e)},400)
 def do_POST(self):
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=(131072 if self.path=='/vla/ingest' else 8192):raise ValueError('invalid size')
   data=json.loads(self.rfile.read(size))
   if self.path=='/vla/ingest':
    task=data.get('task');records=data.get('records',[])
    if task is not None:
     ident=task.get('id','')
     if (not isinstance(ident,str) or not ident.startswith('vla-') or len(ident)>70
         or task.get('kind')!='vla' or task.get('status') not in ('running','completed','stopped','error','interrupted')):
      raise ValueError('invalid VLA task')
     ENGINE.store.task(ident,task)
    if not isinstance(records,list) or len(records)>20:raise ValueError('invalid record batch')
    for record in records:
     ident=record.get('task_id','')
     if (not isinstance(ident,str) or not ident.startswith('vla-') or len(ident)>70
         or record.get('kind') not in ('vla_start','vla_sample','vla_legacy_trial','vla_end')
         or not ENGINE.store.task(ident)):
      raise ValueError('invalid VLA record')
     ENGINE.record('vla',record['kind'],task_id=ident,payload=record)
    self.reply({'ok':True,'records':len(records),'storage_project':'vla'})
   elif self.path=='/trial/start':self.reply(ENGINE.start_trial(data),201)
   elif self.path=='/trial/stop':self.reply(ENGINE.stop_trial())
   elif self.path=='/round/archive':self.reply(ROUNDS.start(data.get('id','')),202)
   elif self.path=='/round/delete':self.reply(ROUNDS.delete(data.get('id',''),data.get('confirm','')))
   elif self.path=='/throughput/start':self.reply(ENGINE.bulk(min(120,max(10,int(data.get('seconds',30)))),min(50,max(1,float(data.get('rate_mbps',20))))),201)
   else:self.reply({'error':'not found'},404)
  except KeyError as e:self.reply({'error':str(e)},404)
  except Exception as e:self.reply({'error':str(e)},409)
 def log_message(self,*args):pass
if __name__=='__main__':ENGINE.start();ThreadingHTTPServer(('127.0.0.1',18261),Handler).serve_forever()

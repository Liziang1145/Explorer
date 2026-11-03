"""Round reports and bounded, asynchronous raw-data archives. No control actions."""
import csv,hashlib,io,json,shutil,threading,time,uuid,zipfile
from pathlib import Path
from store import owner

def report(task):
 if task.get('kind')=='vla':
  legacy=bool(task.get('legacy'))
  lines=['# 自然语言—机械臂只读测量' if not legacy else '# 杯子目标定位＋规划只读历史基线',
   '',f"任务：{task.get('name','未命名')}",f"ID：`{task['id']}`",f"状态：{task.get('status','未知')}",
   f"模型／设备：{task.get('vision_model','未记录')} / {task.get('device','未记录')}",
   f"边界：{task.get('measurement_boundary','未记录')}",
   f"完成预检：{task.get('successful_trials',0)} / {task.get('trials_done',0)}",'',
   '| 阶段 | N | 均值 ms | P50 ms | P95 ms | P99 ms | 最大 ms |',
   '|---|---:|---:|---:|---:|---:|---:|']
  for name,d in task.get('summary',{}).items():
   if name=='planned_duration_s':continue # output trajectory duration, not measurement latency
   if not isinstance(d,dict) or d.get('unit','ms')!='ms':continue
   def f(k):return '未测' if d.get(k) is None else f"{d[k]:.3f}"
   lines.append('|'+name+'|'+str(d.get('n',d.get('count',0)))+'|'+'|'.join(f(k) for k in ('mean','p50','p95','p99','max'))+'|')
  lines+=['','百分位采用 nearest-rank；失败样本保留在原始数据库。',
   'GPU 推理耗时嵌套在等待检测帧中，不能把各段百分位相加。',
   '本轮没有调用任何运动执行接口；这不是物理端到端时延或抓取成功率。']
  if legacy:lines.append('旧数据使用 CPU，且没有自然语言输入；不能与新 GPU 结果计算严格加速比。')
  return '\n'.join(lines)
 if task.get('kind')!='e2e':return '# 持续通信测量报告\n\n```json\n'+json.dumps(task,ensure_ascii=False,indent=2)+'\n```'
 lines=['# VR→机械臂测量结果', '', '任务：'+task.get('name','未命名'), '任务 ID：`'+task['id']+'`','状态：'+task['status'],'',
 '起点：VR origin_ns 控制采样软件时间戳，经有效时钟映射关联到 AIPC。',
 '终点：同轴编码器相对静止基线首次越运动阈值，随后连续 3 帧确认。它是运动反馈代理，包含反馈周期，不是外部传感器测得的严格物理起动。','',
 '| 统计范围 | 有效样本 N | 平均 ms | P50 ms | P95 ms | P99 ms | 最大 ms |','|---|---:|---:|---:|---:|---:|---:|']
 def row(label,d):
  return '|'+label+'|'+'|'.join(str(d.get(k,0)) if k=='n' else ('未测' if d.get(k) is None else f'{d[k]:.6f}') for k in ['n','mean','p50','p95','p99','max'])+'|'
 lines.extend([row('VR采样→编码器反馈（完整链路代理）',task.get('summary',{})),row('AIPC接收→编码器反馈（部分链路，单独统计）',task.get('partial_summary',{}))])
 lines+=['','平均值为有效样本算术平均；P50/P95/P99 使用 nearest-rank。小样本时 P95/P99 可能与最大值相同，不能据此推断稳定尾延迟。',
 '只有完整时钟映射有效的响应进入第一行；部分样本不补零，不混入完整结果。分段的百分位不能相加。',
 '仅对静止后的可关联动作采样；连续重叠输入不代表每包都能测得运动响应。CAN 使用时序关联，并非机械臂逐命令执行 ACK。','',
 '## 已关联响应的分段', '', '| 分段 | N | 平均 ms | P50 ms | P95 ms | P99 ms | 最大 ms |','|---|---:|---:|---:|---:|---:|---:|']
 lines += [row(k,v) for k,v in task.get('segments',{}).items()]
 lines+=['','## 独立分段（与响应样本集合不同，最多最近10000个样本）','','| 分段 | N | 平均 ms | P50 ms | P95 ms | P99 ms | 最大 ms |','|---|---:|---:|---:|---:|---:|---:|']
 lines += [row(k,v) for k,v in task.get('stage_summary',{}).items()]
 lines+=['','## 采集质量与元数据','','```json',json.dumps({k:v for k,v in task.items() if k not in ['samples','segments','stage_summary']},ensure_ascii=False,indent=2),'```','',
 'ZIP 仅含当前数据库中仍保留的本轮专属事件。共享 CAN 帧、网络和 CPU 后台监测属于独立持续采集，不在整轮删除范围，也不打包冒充本轮专属数据。FIFO 已到期的数据不能恢复。']
 return '\n'.join(lines)

class Rounds:
 def __init__(self,engine):
  self.engine=engine;self.lock=threading.RLock();self.jobs={}
  self.root=Path(engine.cfg.get('export_dir',str(Path(engine.cfg['data_dir']).parent/(Path(engine.cfg['data_dir']).name+'-exports'))));self.root.mkdir(parents=True,exist_ok=True)
  for p in self.root.glob('*.zip'):p.unlink(missing_ok=True) # caches only; never raw DB
 def cleanup(self):
  now=time.time()
  for key,job in list(self.jobs.items()):
   if job['state']!='building' and now-job['created']>3600:
    (self.root/(key+'.zip')).unlink(missing_ok=True);del self.jobs[key]
 def start(self,ident):
  with self.lock:
   self.cleanup()
   task=self.engine.store.task(ident)
   if not task:raise KeyError('任务不存在')
   if task['status']=='running':raise ValueError('请先结束测量，再下载完整轮次')
   for job in self.jobs.values():
    if job['task_id']==ident and job['state'] in ['building','ready']:return dict(job)
   if any(j['state']=='building' for j in self.jobs.values()):raise ValueError('正在打包另一轮，请稍后重试')
   key=uuid.uuid4().hex;job={'id':key,'task_id':ident,'state':'building','created':time.time(),'records':0};self.jobs[key]=job
   threading.Thread(target=self.build,args=(job,task),daemon=True).start();return dict(job)
 def build(self,job,task):
  key=job['id'];path=self.root/(key+'.zip');counts={};samples=[];digest=hashlib.sha256();raw_bytes=0
  try:
   if shutil.disk_usage(self.root).free<512*1024**2:raise ValueError('磁盘剩余不足512MiB，停止打包')
   # Flush queued raw records first. Tombstones also protect detached writer batches.
   with self.engine.lock:
    self.engine.store.write(self.engine.pending);self.engine.pending=[]
   with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    with z.open('raw-events.ndjson','w') as out:
     for record in self.engine.store.task_records(task['id']):
      raw=(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n').encode();out.write(raw);digest.update(raw);raw_bytes+=len(raw)
      kind=record.get('kind','unknown');counts[kind]=counts.get(kind,0)+1;job['records']+=1
      if kind=='response_sample':samples.append(record['sample'])
      if raw_bytes>1024**3:raise ValueError('单轮导出超过1GiB，请使用项目原始导出')
    z.writestr('report.md',report(task));z.writestr('result.json',json.dumps(task,ensure_ascii=False,indent=2))
    f=io.StringIO(newline='');fields=['side','seq','trace','latency_ms','post_aipc_ms','network_uncertainty_ms']
    columns=sorted({k for s in samples for k in s.get('segments',{})});writer=csv.writer(f);writer.writerow(fields+['segment.'+k for k in columns])
    for s in samples:writer.writerow([s.get(k) for k in fields]+[s.get('segments',{}).get(k) for k in columns])
    z.writestr('response-samples.csv','\ufeff'+f.getvalue())
    expected=int(task.get('n',0));manifest={'task_id':task['id'],'exported_at':time.time(),'record_counts':counts,'response_samples_found':len(samples),'response_samples_expected':expected,'response_samples_complete':len(samples)==expected,'trial_start_present':counts.get('trial_start',0)>0,'trial_stop_present':counts.get('trial_stop',0)>0,'raw_sha256':digest.hexdigest(),'scope':'本轮专属原始事件；不含共享背景CAN/CPU/网络监测','retention_note':'FIFO可能已清除原始事件；样本数一致不保证所有中间事件完整。另见结果中的采集丢弃和错误字段。','csv_note':'空值表示缺失，不是0；CSV从全部保留的response_sample重建，结果JSON的samples仅为最近10条。'}
    z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
   with self.lock:
    # Keep at most 1GiB of finished export cache, newest first.
    total=path.stat().st_size
    for old in sorted([j for j in self.jobs.values() if j['state']=='ready'],key=lambda j:j['created'],reverse=True):
     p=self.root/(old['id']+'.zip');total+=p.stat().st_size if p.exists() else 0
     if total>1024**3:p.unlink(missing_ok=True);old['state']='expired'
    job.update(state='ready',bytes=path.stat().st_size,manifest=manifest)
  except Exception as e:
   path.unlink(missing_ok=True);job.update(state='error',error=str(e))
 def get(self,key):
  with self.lock:
   self.cleanup()
   if key not in self.jobs:raise KeyError('导出任务不存在或已过期')
   return dict(self.jobs[key])
 def download(self,key):
  job=self.get(key)
  if job['state']!='ready':raise ValueError('打包尚未完成或缓存已过期')
  return self.root/(key+'.zip'),job
 def delete(self,ident,confirm):
  if confirm!=ident:raise ValueError('请明确确认本轮ID')
  with self.lock,self.engine.lock:
   if any(j['task_id']==ident and j['state']=='building' for j in self.jobs.values()):raise ValueError('本轮正在打包，请完成后删除')
   if self.engine.active and self.engine.active['id']==ident:raise ValueError('请先结束本轮测量')
   result=self.engine.store.delete_task(ident)
   self.engine.pending=[r for r in self.engine.pending if owner(r)!=ident]
   for key,job in list(self.jobs.items()):
    if job['task_id']==ident:(self.root/(key+'.zip')).unlink(missing_ok=True);del self.jobs[key]
   return result

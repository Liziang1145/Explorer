"""Offline failure injection: recorded frame + dispatcher; no hardware calls."""
import hashlib,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,'/home/apex/research/fisheye_mapping_20261030')
import dual_color as color
import run_coloring as runner

session=Path('/home/apex/long_capture/sessions/20261030T153351Z-60940b9a')
root=Path('/home/apex/research/mapping_pipeline_v3_20261103')
out=root/'fallback-validation';out.mkdir(exist_ok=True);(out/'updates').mkdir(exist_ok=True)
source=Path('/home/apex/research/fisheye_mapping_20261030/gpu-frame-validation/xyz.npy')
if not (out/'xyz.npy').exists():(out/'xyz.npy').symlink_to(source)
color.init_worker(session,out);color.CHUNK=1000000
tasks,_=color.build_tasks(session,session/'dense-color-v1/poses.jsonl')
task=next(t for t in tasks if t['kind']=='rgb' and not t.get('error'))
called=[]
def fail(*a,**k):
    called.append(True);raise RuntimeError('injected GPU projection failure')
color.project=fail;os.environ['APEX_COLOR_GPU']='1'
result=color.process(task)
assert result['accepted'] and len(called)==1 and os.environ['APEX_COLOR_GPU']=='0',result
a=np.fromfile(result['update_file'],dtype=color.UP)
b=np.fromfile(source.parent/'updates/rgb-cpu.bin',dtype=color.UP)
assert len(a)==len(b) and np.array_equal(a['id'],b['id']) and np.array_equal(a['rgb'],b['rgb']) and np.array_equal(a['source'],b['source']) and np.allclose(a['score'],b['score'])
reports=[dict(test='frame_gpu_failure_cpu_retry',accepted=True,equivalent=True,hits=len(a))]
os.environ.pop('APEX_COLOR_GPU',None)
with tempfile.TemporaryDirectory(prefix='color-policy-test-') as tmp:
    p=Path(tmp);(p/'color_gpu.py').write_text('verified kernel')
    (p/'gpu-benchmark.json').write_text(json.dumps(dict(approved=True,kernel_sha256=hashlib.sha256((p/'color_gpu.py').read_bytes()).hexdigest(),gpu='test-gpu')))
    (p/'gpu-parallel-benchmark.json').write_text(json.dumps(dict(approved=True,recommended_workers=2,speedup_vs_cpu4=1.86)))
    for low in [True,False]:
        calls=[]
        def run(cmd,**kw):
            calls.append((cmd,dict(kw.get('env',{}))))
            if '-c' in cmd:return type('Result',(),dict(returncode=0,stdout=json.dumps(dict(free=8*1024**3,name='test-gpu'))))()
            return type('Result',(),dict(returncode=1 if kw.get('env',{}).get('APEX_COLOR_GPU')=='1' else 0))()
        with patch.object(runner,'ROOT',p),patch.object(runner,'resources',return_value=dict(available_memory=(6 if low else 24)*1024**3,cpu_count=32,load_1m=2)),patch.object(runner.subprocess,'run',side_effect=run):runner.main(p)
        policy=json.loads((p/'color-resource-policy.json').read_text())
        if low:assert policy['backend']=='cpu' and len(calls)==1
        else:assert policy['backend']=='cpu_fallback' and len(calls)==3 and 'APEX_COLOR_GPU' not in calls[-1][1]
        reports.append(dict(test='low_memory_cpu' if low else 'gpu_process_failure_cpu_resume',passed=True,policy=policy))
report=dict(physical_commands=0,passed=True,tests=reports)
(root/'fallback-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

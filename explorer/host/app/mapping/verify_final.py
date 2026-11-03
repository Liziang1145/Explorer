"""Read-only release audit and offline parser regression checks."""
import hashlib,importlib.util,json,subprocess,sys,time,urllib.request,tarfile
from pathlib import Path
root=Path('/home/apex/research/mapping_pipeline_v3_20261103')
s=Path('/home/apex/long_capture/sessions/20261030T153351Z-60940b9a')
v=root/'verification';v.mkdir(exist_ok=True)
def save(name,value):(v/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
def get(path):return json.load(urllib.request.urlopen('http://127.0.0.1:8130'+path,timeout=25))
manifest=json.loads((root/'release-manifest.json').read_text())
checks=[dict(path=r['path'],match=hashlib.sha256((Path('/home/apex')/r['path']).read_bytes()).hexdigest()==r['sha256']) for r in manifest]
assert all(x['match'] for x in checks);save('deployed-sha256.json',checks)
spec=importlib.util.spec_from_file_location('mapping_gateway','/home/apex/md-service/mapping_gateway.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
rev='a'*64
assert all(g.allowed('/hub/api/evidence/image/obs_'+i+'?revision='+rev,'GET') for i in ['000001','000002533','000000000001'])
assert not g.allowed('/hub/api/evidence/image/obs_1234567890123?revision='+rev,'GET')
assert not g.allowed('/hub/api/evidence/image/obs_000002533?revision=x','GET')
assert not g.allowed('/hub/api/evidence/image/obs_000002533?revision='+rev,'POST')
save('gateway-regression.json',dict(passed=True,legacy_and_long_ids=True,invalid_revision_rejected=True,post_image_rejected=True))
tasks=get('/hub/api/tasks/status');scene=get('/hub/api/scene');drive=get('/hub/api/drive/status');e=get('/hub/api/evidence?object_id=obj_000001')
assert tasks['context']['map_revision']==scene['map_revision'] and e['binding']['available'];assert not drive['busy']
save('scene-final.json',scene);save('task-context-final.json',tasks['context']);save('drive-final.json',drive)
im=urllib.request.urlopen('http://127.0.0.1:8130'+e['observations'][-1]['image_url']);b=im.read();assert im.status==200 and b[:2]==b'\xff\xd8'
save('evidence-image-final.json',dict(status=im.status,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),binding=e['binding']))
for p in [*root.glob('*verification.json'),*root.glob('qwen-*.json'),*root.glob('deploy-*.json'),root/'release-manifest.json',s/'semantic-pipeline.json',s/'navigation-pipeline.json',s/'navigation-geometry-v1/ready.json',s/'navigation/05a8461ab27c7750/offline-checks.json',s/'navigation/05a8461ab27c7750/pipeline-manifest.json',*Path('/home/apex/research/fisheye_mapping_20261030').glob('gpu-*benchmark.json')]:
 if p.is_file():(v/p.name).write_bytes(p.read_bytes())
units=['map-v3-endtoend','map-semantic-20261030t153351z-60940b9a','aipc-monitor-hub','aipc-navigation-plan']
(v/'systemd.txt').write_text(subprocess.run(['systemctl','--user','show',*[x+'.service' for x in units],'-p','Id','-p','ActiveState','-p','Result','-p','MemoryMax','-p','CPUQuotaPerSecUSec'],capture_output=True,text=True).stdout)
(v/'offline-navigation-log.txt').write_text(subprocess.run(['journalctl','--user','-u','map-v3-endtoend.service','--no-pager'],capture_output=True,text=True).stdout)
with tarfile.open(root/'verification.tar.gz','w:gz') as tar:
 for p in v.iterdir():tar.add(p,arcname='verification/'+p.name)
print(json.dumps(dict(files=len(list(v.iterdir())),deployed_files=len(checks),map_revision=scene['map_revision'],semantic_objects=len(scene['objects']),busy=drive['busy'],passed=True,physical_commands=0)))

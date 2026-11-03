import paramiko,base64
code="""
import json,collections,statistics,os
for n in (8,9,10):
 p=f'/home/apex/datasets/vla_cup_grasp/cup_{n:04d}'
 if not os.path.isdir(p):print(json.dumps({'sample':n,'missing':True}));continue
 m=json.load(open(p+'/manifest.json'));r=[json.loads(x) for x in open(p+'/records.jsonl')]
 t=[x['timestamp_unix'] for x in r];d=[b-a for a,b in zip(t,t[1:])]
 events=[json.loads(x) for x in open(p+'/events.jsonl')] if os.path.exists(p+'/events.jsonl') else []
 print(json.dumps({'sample':n,'frames':m['frames'],'result':m['result'],'confidence':m['target']['confidence'],'errors':m['errors'],'stages':collections.Counter(x['stage'] for x in r),'event_stages':[x['stage'] for x in events],'missing_files':sum(not os.path.isfile(p+'/'+x[k]) for x in r for k in ('rgb_file','depth_file')),'feedback_fail':sum(not x['actual_feedback_ok']['left'] or not x['actual_feedback_ok']['right'] for x in r),'median_ms':statistics.median(d)*1000 if d else 0,'max_ms':max(d)*1000 if d else 0,'grip':sorted(set(x['control_status']['control']['left']['grip'] for x in r))},ensure_ascii=False))
"""
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
stdin,stdout,stderr=c.exec_command('echo '+base64.b64encode(code.encode()).decode()+' | base64 -d | python3',timeout=30)
print(stdout.read().decode());print(stderr.read().decode());c.close()

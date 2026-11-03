import paramiko,base64
code="""
import json,collections,statistics,os
p='/home/apex/datasets/vla_cup_grasp/cup_0005'
m=json.load(open(p+'/manifest.json'));r=[json.loads(x) for x in open(p+'/records.jsonl')]
t=[x['timestamp_unix'] for x in r];d=[b-a for a,b in zip(t,t[1:])]
events=[json.loads(x) for x in open(p+'/events.jsonl')] if os.path.exists(p+'/events.jsonl') else []
print(json.dumps({'manifest':m,'records':len(r),'stages':collections.Counter(x['stage'] for x in r),'events':events,'missing_rgb':sum(not os.path.isfile(p+'/'+x['rgb_file']) for x in r),'missing_depth':sum(not os.path.isfile(p+'/'+x['depth_file']) for x in r),'feedback_fail':sum(not x['actual_feedback_ok']['left'] or not x['actual_feedback_ok']['right'] for x in r),'interval_ms':{'median':statistics.median(d)*1000 if d else 0,'max':max(d)*1000 if d else 0},'grip_values':sorted(set(x['control_status']['control']['left']['grip'] for x in r))},ensure_ascii=False,indent=2))
"""
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
stdin,stdout,stderr=c.exec_command('echo '+base64.b64encode(code.encode()).decode()+' | base64 -d | python3',timeout=30)
print(stdout.read().decode());print(stderr.read().decode());c.close()

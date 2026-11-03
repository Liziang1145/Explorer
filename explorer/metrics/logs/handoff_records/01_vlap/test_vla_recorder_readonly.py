import json,time,urllib.request,paramiko
URL='http://192.168.6.206:8092/api/vla_dataset'
def post(data):
 r=urllib.request.Request(URL,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(r,timeout=90) as f:return json.load(f)
name='test_readonly_'+str(int(time.time()))
print(json.dumps(post({'action':'start','sample':name}),ensure_ascii=False))
time.sleep(2)
print(json.dumps(post({'action':'stage','stage':'read_only_test'}),ensure_ascii=False))
time.sleep(1)
result=post({'action':'stop','result':'unknown','note':'只读采集验证'})
print(json.dumps(result,ensure_ascii=False))
client=paramiko.SSHClient();client.set_missing_host_key_policy(paramiko.AutoAddPolicy());client.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
stdin,stdout,stderr=client.exec_command("python3 -c \"import json; p='/home/apex/datasets/vla_cup_grasp/"+name+"/records.jsonl'; r=json.loads(open(p).readline()); print(sorted(r)); print(r['actual_feedback_ok'])\"",timeout=20)
print(stdout.read().decode());print(stderr.read().decode());client.close()

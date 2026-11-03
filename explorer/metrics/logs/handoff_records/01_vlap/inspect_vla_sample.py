import paramiko,base64
client=paramiko.SSHClient();client.set_missing_host_key_policy(paramiko.AutoAddPolicy());client.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
code=r'''
import json,collections,statistics,os
p='/home/apex/datasets/vla_cup_grasp/cup_0001'
m=json.load(open(p+'/manifest.json'))
r=[json.loads(x) for x in open(p+'/records.jsonl')]
t=[x['timestamp_unix'] for x in r]
d=[b-a for a,b in zip(t,t[1:])]
print(json.dumps({'manifest':m,'records':len(r),'stages':collections.Counter(x['stage'] for x in r),'missing_rgb':sum(not os.path.isfile(p+'/'+x['rgb_file']) for x in r),'missing_depth':sum(not os.path.isfile(p+'/'+x['depth_file']) for x in r),'left_feedback_fail':sum(not x['actual_feedback_ok']['left'] for x in r),'right_feedback_fail':sum(not x['actual_feedback_ok']['right'] for x in r),'interval_ms':{'median':statistics.median(d)*1000,'max':max(d)*1000},'grip_values':sorted(set(x['control_status']['control']['left']['grip'] for x in r)),'first_angles':r[0]['actual_left_deg'],'last_angles':r[-1]['actual_left_deg']},ensure_ascii=False,indent=2))
'''
stdin,stdout,stderr=client.exec_command("echo "+base64.b64encode(code.encode()).decode()+" | base64 -d | python3",timeout=30)
print(stdout.read().decode());print(stderr.read().decode())
sftp=client.open_sftp();sftp.get('/home/apex/datasets/vla_cup_grasp/cup_0001/frames/000000.jpg',r'C:\Users\25298\Desktop\FPGA\0000_未处理归档\cup_0001_first.jpg');sftp.close();client.close()

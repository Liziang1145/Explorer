import paramiko,base64
code="""
import os,json
for root in ['/home/apex/datasets/vla_cup_grasp','/home/apex/datasets/cup_grasp']:
 print('ROOT',root)
 if not os.path.isdir(root): continue
 for name in sorted(os.listdir(root)):
  p=os.path.join(root,name)
  if not os.path.isdir(p):continue
  mpath=os.path.join(p,'manifest.json')
  if os.path.isfile(mpath):
   m=json.load(open(mpath));print(json.dumps({'name':name,'frames':m.get('frames'),'result':m.get('result'),'started_at':m.get('started_at'),'errors':len(m.get('errors',[]))},ensure_ascii=False))
  else:
   print(json.dumps({'name':name,'manifest':False,'files':sorted(os.listdir(p))[:12]},ensure_ascii=False))
"""
client=paramiko.SSHClient();client.set_missing_host_key_policy(paramiko.AutoAddPolicy());client.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
cmd='echo '+base64.b64encode(code.encode()).decode()+' | base64 -d | python3'
stdin,stdout,stderr=client.exec_command(cmd,timeout=30);print(stdout.read().decode());print(stderr.read().decode());client.close()

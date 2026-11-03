from pathlib import Path
import json
import time
import paramiko
import urllib.request

ROOT = Path(r'C:\Users\25298\Desktop\FPGA\代码\aipc-simulator-ui')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.6.206', username='apex', password="<AIPC_PASSWORD>", timeout=15)
sftp = client.open_sftp()
for name in ('grasp_target_bridge.py', 'stone_grasp_trial.py'):
    sftp.put(str(ROOT / name), '/home/apex/' + name + '.new')
for name in ('simulator.js', 'simulator.html'):
    sftp.put(str(ROOT / name), '/home/apex/' + name + '.new')
sftp.close()
command = """echo apex | sudo -S sh -c '
cp /home/apex/grasp_target_bridge.py.new /home/apex/grasp_target_bridge.py &&
cp /home/apex/stone_grasp_trial.py.new /home/apex/stone_grasp_trial.py &&
cp /home/apex/simulator.js.new /home/apex/md-service/public/simulator.js &&
cp /home/apex/simulator.html.new /home/apex/md-service/public/simulator.html &&
systemctl restart arm-console.service'"""
stdin, stdout, stderr = client.exec_command(command, timeout=30)
if stdout.channel.recv_exit_status() != 0:
    raise RuntimeError(stderr.read().decode())
client.close()

time.sleep(3)
def post(path, data):
    request = urllib.request.Request('http://192.168.6.206:8092' + path,
        data=json.dumps(data).encode(), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)

target = post('/api/grasp_target_preview', {'side':'left'})
print(json.dumps({'target_ok':target.get('ok'), 'xyz':target.get('xyz'),
    'retreat_m':target.get('target',{}).get('pregrasp_retreat_m'),
    'reference_j7_b_m':target.get('target',{}).get('reference_j7_b_m'),
    'pregrasp_j7_b_m':target.get('target',{}).get('pregrasp_j7_b_m')}, ensure_ascii=False))
preview = post('/api/vla_motion_execute', {'stage':'preview', 'side':'left',
    'xyz':target['xyz'], 'collision_mode':'exact', 'nearest_orientation':True})
print(json.dumps({'preview_ok':preview.get('ok'), 'execution_allowed':preview.get('execution_allowed'),
    'duration_s':preview.get('duration_s'), 'error':preview.get('error')}, ensure_ascii=False))

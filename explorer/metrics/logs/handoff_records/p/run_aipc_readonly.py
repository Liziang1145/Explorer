from pathlib import Path
import sys
import paramiko

root = Path(r'C:\Users\25298\Desktop\FPGA')
trials = int(sys.argv[1]) if len(sys.argv) > 1 else 10
remote_dir = f'/home/apex/latency_readonly_20261102_{trials}'
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.6.206', username='apex', password="<AIPC_PASSWORD>", timeout=10)
stdin, stdout, stderr = client.exec_command(
    'cp -n /home/apex/cup_target_live.py /home/apex/cup_target_live.py.before_latency '
    '&& cp -n /home/apex/grasp_target_bridge.py /home/apex/grasp_target_bridge.py.before_latency')
stdout.channel.recv_exit_status()
sftp = client.open_sftp()
sftp.put(str(root/'07_实验记录'/'延迟测量'/'measure_latency.py'), '/home/apex/measure_latency.py')
sftp.put(str(root/'02_代码'/'aipc-simulator-ui'/'cup_target_live.py'), '/home/apex/cup_target_live.py.latency')
sftp.put(str(root/'02_代码'/'aipc-simulator-ui'/'grasp_target_bridge.py'), '/home/apex/grasp_target_bridge.py.latency')
sftp.close()
stdin, stdout, stderr = client.exec_command(
    'printf "%s\\n" apex | sudo -S cp /home/apex/cup_target_live.py.latency /home/apex/cup_target_live.py '
    '&& printf "%s\\n" apex | sudo -S cp /home/apex/grasp_target_bridge.py.latency /home/apex/grasp_target_bridge.py')
stdout.channel.recv_exit_status()
command = f'python3 /home/apex/measure_latency.py collect --trials {trials} --out {remote_dir}'
stdin, stdout, stderr = client.exec_command(command, timeout=280)
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
status = stdout.channel.recv_exit_status()
for name in ('trials.csv', 'summary.json', 'metrics.csv'):
    sftp = client.open_sftp()
    sftp.get(f'{remote_dir}/{name}', str(root/'07_实验记录'/'延迟测量'/name))
    sftp.close()
client.close()
raise SystemExit(status)

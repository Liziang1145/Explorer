from pathlib import Path
import paramiko

root = Path(r'C:\Users\25298\Desktop\FPGA')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.6.206', username='apex', password="<AIPC_PASSWORD>", timeout=10)
for command in ('ps -ef', 'ls -l /home/apex/latency_readonly_20261102'):
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode('utf-8', errors='replace')
    if command == 'ps -ef':
        output = '\n'.join(line for line in output.splitlines() if 'measure_latency' in line and 'grep' not in line)
    print(output)
sftp = client.open_sftp()
for name in ('trials.csv', 'summary.json', 'metrics.csv'):
    try:
        sftp.get(f'/home/apex/latency_readonly_20261102/{name}', str(root/'07_实验记录'/'延迟测量'/name))
        print('downloaded', name)
    except FileNotFoundError:
        print('not ready', name)
sftp.close()
client.close()

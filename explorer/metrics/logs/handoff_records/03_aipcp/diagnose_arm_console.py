import json
import urllib.request
import paramiko
with urllib.request.urlopen('http://192.168.6.206:8092/api/status', timeout=10) as r:
    status=json.load(r)
print(json.dumps(status.get('control',{}),ensure_ascii=False,indent=2))
client=paramiko.SSHClient();client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
for command in ("journalctl -u arm-console.service --since '2026-11-02 02:45:00' --no-pager -n 250",):
    stdin,stdout,stderr=client.exec_command(command,timeout=30)
    print(stdout.read().decode(errors='replace'))
    print(stderr.read().decode(errors='replace'))
client.close()

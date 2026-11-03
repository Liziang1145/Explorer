import base64
import os
from pathlib import Path
import sys
import paramiko

local_path, remote_path = sys.argv[1:3]
payload = base64.b64encode(Path(local_path).read_bytes()).decode("ascii")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("192.168.6.206", username="apex", password=os.environ["AIPC_PASSWORD"], timeout=15)
stdin, stdout, stderr = client.exec_command("base64 -d > " + remote_path, timeout=30)
stdin.write(payload)
stdin.channel.shutdown_write()
error = stderr.read().decode()
status = stdout.channel.recv_exit_status()
client.close()
if status:
    raise RuntimeError(error)
print(remote_path)

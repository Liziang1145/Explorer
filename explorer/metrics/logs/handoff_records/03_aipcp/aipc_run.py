import os
import sys
import paramiko

command = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("192.168.6.206", username="apex", password=os.environ["AIPC_PASSWORD"], timeout=15)
stdin, stdout, stderr = client.exec_command(command, timeout=280)
for line in iter(stdout.readline, ""):
    print(line, end="", flush=True)
error = stderr.read()
if error:
    print(error, end="", file=sys.stderr)
status = stdout.channel.recv_exit_status()
client.close()
raise SystemExit(status)

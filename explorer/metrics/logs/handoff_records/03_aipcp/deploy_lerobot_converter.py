import paramiko
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
s=c.open_sftp();s.put(r'C:\Users\25298\Desktop\FPGA\代码\aipc-simulator-ui\convert_vla_to_lerobot.py','/home/apex/convert_vla_to_lerobot.py');s.close()
for command in ("python3 -c \"import importlib.util;print({x:bool(importlib.util.find_spec(x)) for x in ['lerobot','cv2','numpy']})\"", "test -x /home/apex/.local/opt/vision-yolo-venv/bin/python && /home/apex/.local/opt/vision-yolo-venv/bin/python -c \"import importlib.util;print({x:bool(importlib.util.find_spec(x)) for x in ['lerobot','cv2','numpy']})\""):
 stdin,stdout,stderr=c.exec_command(command,timeout=30);print(stdout.read().decode());print(stderr.read().decode())
c.close()

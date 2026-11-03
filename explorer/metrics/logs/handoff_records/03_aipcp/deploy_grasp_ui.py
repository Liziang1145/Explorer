from pathlib import Path
import paramiko
root=Path(r'C:\Users\25298\Desktop\FPGA\代码\aipc-simulator-ui')
client=paramiko.SSHClient();client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
sftp=client.open_sftp()
for name in ('simulator.js','simulator.html','arm_console.py','collect_grasp_api.py','collect_grasp_sample.py','stone_grasp_trial.py','vla_dataset_recorder.py'):
    sftp.put(str(root/name),'/home/apex/'+name+'.new')
sftp.close()
stdin,stdout,stderr=client.exec_command("echo apex | sudo -S sh -c 'cp /home/apex/simulator.js.new /home/apex/md-service/public/simulator.js && cp /home/apex/simulator.html.new /home/apex/md-service/public/simulator.html && cp /home/apex/arm_console.py.new /home/apex/arm_console.py && cp /home/apex/collect_grasp_api.py.new /home/apex/collect_grasp_api.py && cp /home/apex/collect_grasp_sample.py.new /home/apex/collect_grasp_sample.py && cp /home/apex/stone_grasp_trial.py.new /home/apex/stone_grasp_trial.py && cp /home/apex/vla_dataset_recorder.py.new /home/apex/vla_dataset_recorder.py && systemctl restart arm-console.service'",timeout=30)
status=stdout.channel.recv_exit_status()
if status: raise RuntimeError(stderr.read().decode())
print('网页已部署')
client.close()

import paramiko
client=paramiko.SSHClient();client.set_missing_host_key_policy(paramiko.AutoAddPolicy());client.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
command="rm -rf -- /home/apex/datasets/vla_cup_grasp/cup_0002 /home/apex/datasets/vla_cup_grasp/test_readonly_1793561140 && ls -1 /home/apex/datasets/vla_cup_grasp"
stdin,stdout,stderr=client.exec_command(command,timeout=30)
status=stdout.channel.recv_exit_status();print(stdout.read().decode());print(stderr.read().decode())
if status:raise RuntimeError('删除失败')
client.close()

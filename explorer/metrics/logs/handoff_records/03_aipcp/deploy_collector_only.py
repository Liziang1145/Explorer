import paramiko
client=paramiko.SSHClient();client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.6.206',username='apex',password="<AIPC_PASSWORD>",timeout=15)
sftp=client.open_sftp()
sftp.put(r'C:\Users\25298\Desktop\FPGA\代码\aipc-simulator-ui\collect_grasp_sample.py','/home/apex/collect_grasp_sample.py')
sftp.close();client.close()
print('采集脚本已上传；未运行、未调用任何运动接口')

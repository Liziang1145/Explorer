import asyncio,time
from vr_receiver import VRView
from vr_directory import VRDirectory,private_host,valid_status

class ManagedVRView(VRView):
    def __init__(self,path='/home/apex/.config/aipc-vr-live.json',history='/home/apex/.config/aipc-vr-devices.json'):
        super().__init__(path);self.directory=VRDirectory(self,history)
    def public(self):return {**super().public(),'discovery':self.directory.public()}
    async def call(self,method,path,body=None):
        host=self.config['host'];data=await super().call(method,path,body)
        if method=='GET' and path=='status':
            if host!=self.config['host']:raise ValueError('VR 地址已更新，重新查询状态')
            if not valid_status(data):raise ValueError('此地址不是兼容的 VR 直播服务')
            self.directory.remember(host,data)
        return data
    async def command(self,data):
        if data.get('action')=='discover':await self.directory.scan(True);return self.public()
        if data.get('action')=='configure':
            host=data.get('host','');token=data.get('token',self.config['token'])
            if not private_host(host):raise ValueError('请输入 Quest 的局域网 IPv4 地址')
            if not isinstance(token,str) or not 1<=len(token)<=256 or any(c in token for c in '\r\n'):raise ValueError('密钥格式无效')
            status=await self.directory.probe(host,token,timeout=2)
            if not status:raise ValueError('未识别到可认证的 VR 直播服务；已保留当前连接和最近成功地址')
            if host!=self.config['host'] or token!=self.config['token']:await super().command(data)
            self.latest={'reachable':True,'status':status,'error':'','checked_at':time.time()};self.directory.remember(host,status);return self.public()
        return await super().command(data)
    async def start(self,app):
        await super().start(app);self.directory.task=asyncio.create_task(self.directory.watch())
    async def stop(self,app):
        if self.directory.task:self.directory.task.cancel();await asyncio.gather(self.directory.task,return_exceptions=True)
        await super().stop(app)

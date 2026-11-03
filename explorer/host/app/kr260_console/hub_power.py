"""Authenticated two-phase UI confirmation; root broker owns the fixed timer."""
import json,secrets,socket,threading,time
LOCK=threading.RLock();CHALLENGES={}
class PowerError(RuntimeError):
    def __init__(self,message,status=503):super().__init__(message);self.status=status
def rpc(action,identifier=None):
    message={'scope':'power','action':action}
    if identifier:message['id']=identifier
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(12);sock.connect('/run/apex-hub/control.sock');sock.sendall(json.dumps(message).encode()+b'\n');raw=b''
        while b'\n' not in raw and len(raw)<8192:
            data=sock.recv(8192)
            if not data:break
            raw+=data
    result=json.loads(raw)
    if not result.get('ok'):raise PowerError(result.get('error','电源控制不可用'),result.get('status',503))
    return result['result']
def forget(token):
    with LOCK:CHALLENGES.pop(token,None)
def prepare(token,action):
    if action not in ('reboot','poweroff'):raise ValueError('无效电源操作')
    if rpc('status')['pending']:raise ValueError('已有电源操作正在倒计时')
    now=time.time();value={'challenge':secrets.token_urlsafe(32),'action':action,'expires_at':now+60}
    with LOCK:
        for key in list(CHALLENGES):
            if CHALLENGES[key]['expires_at']<now:CHALLENGES.pop(key,None)
        if len(CHALLENGES)>=64:raise ValueError('确认请求过多')
        CHALLENGES[token]=value
    return value|{'confirmation':'AIPC','cancel_window_seconds':15}
def commit(token,data):
    with LOCK:
        value=CHALLENGES.get(token)
        if not value or value['expires_at']<time.time() or not secrets.compare_digest(str(data.get('challenge','')),value['challenge']) or data.get('confirmation')!='AIPC':raise ValueError('确认已过期或内容不匹配')
        CHALLENGES.pop(token,None)
    return rpc(value['action'])

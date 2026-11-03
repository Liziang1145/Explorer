"""Local PAM verification and fixed kiosk→desktop action. Never an HTTP API."""
import ctypes,ctypes.util,json,os,pwd,socket,struct,subprocess,time
from pathlib import Path
class Message(ctypes.Structure):_fields_=[('style',ctypes.c_int),('msg',ctypes.c_char_p)]
class Response(ctypes.Structure):_fields_=[('resp',ctypes.c_void_p),('ret',ctypes.c_int)]
CB=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.POINTER(Message)),ctypes.POINTER(ctypes.POINTER(Response)),ctypes.c_void_p)
class Conv(ctypes.Structure):_fields_=[('callback',CB),('data',ctypes.c_void_p)]
def authenticate(password):
 if not isinstance(password,str) or not password or len(password.encode())>1024:return False
 libc=ctypes.CDLL(ctypes.util.find_library('c'));libc.calloc.restype=ctypes.c_void_p;libc.calloc.argtypes=[ctypes.c_size_t,ctypes.c_size_t];libc.strdup.restype=ctypes.c_void_p;libc.strdup.argtypes=[ctypes.c_char_p]
 pam=ctypes.CDLL(ctypes.util.find_library('pam'));pam.pam_start.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.POINTER(Conv),ctypes.POINTER(ctypes.c_void_p)];pam.pam_authenticate.argtypes=[ctypes.c_void_p,ctypes.c_int];pam.pam_acct_mgmt.argtypes=[ctypes.c_void_p,ctypes.c_int];pam.pam_end.argtypes=[ctypes.c_void_p,ctypes.c_int]
 @CB
 def callback(n,messages,out,data):
  if not 1<=n<=16:return 19
  response=ctypes.cast(libc.calloc(n,ctypes.sizeof(Response)),ctypes.POINTER(Response))
  for i in range(n):
   style=messages[i].contents.style
   if style not in (1,2,3,4):return 19
   response[i].resp=libc.strdup(password.encode() if style==1 else b'apex' if style==2 else b'');response[i].ret=0
  out[0]=response;return 0
 conv=Conv(callback,None);handle=ctypes.c_void_p();code=pam.pam_start(b'tlz-preview-unlock',b'apex',ctypes.byref(conv),ctypes.byref(handle))
 if code:return False
 try:
  code=pam.pam_authenticate(handle,0)
  if code==0:code=pam.pam_acct_mgmt(handle,0)
  return code==0
 finally:pam.pam_end(handle,code)
def main():
 u=pwd.getpwnam('apex');path=Path('/run/tlz-kiosk/auth.sock');path.parent.mkdir(mode=0o755,exist_ok=True)
 if path.exists():path.unlink()
 server=socket.socket(socket.AF_UNIX);server.bind(str(path));path.chmod(0o660);os.chown(path,0,u.pw_gid);server.listen(4);attempts=[]
 while True:
  client,_=server.accept()
  with client:
   client.settimeout(8)
   try:
    _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    if uid not in (0,u.pw_uid):continue
    raw=b''
    while b'\n' not in raw and len(raw)<=4096:
     chunk=client.recv(1024)
     if not chunk:break
     raw+=chunk
    data=json.loads(raw);now=time.monotonic();attempts[:]=[t for t in attempts if now-t<60]
    action=data.get('action');valid=action in ('verify','unlock') and len(attempts)<5 and authenticate(data.get('password'))
    if not valid:attempts.append(now);time.sleep(1)
    client.sendall(json.dumps({'ok':valid}).encode()+b'\n')
    if valid and action=='unlock':
     # /run is cleared on boot, so the next power-on always returns to preview.
     Path('/run/tlz-display-unlocked').touch(mode=0o600)
     subprocess.run(['/usr/bin/systemd-run','--quiet','--collect','--unit=tlz-open-desktop-'+str(time.monotonic_ns()),'--on-active=1s','--timer-property=RemainAfterElapse=no','/usr/local/lib/tlz-kiosk/open-desktop'],check=True)
   except (OSError,ValueError,subprocess.CalledProcessError):
    try:client.sendall(b'{"ok":false}\n')
    except OSError:pass
if __name__=='__main__':main()

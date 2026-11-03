"""Root startup health monitor, independent from the display's controlling TTY."""
import subprocess,time,pwd
from pathlib import Path
uid=pwd.getpwnam('apex').pw_uid;seen=0;since=time.monotonic()
while True:
 if Path('/run/tlz-display-unlocked').exists():seen=0;time.sleep(2);continue
 try:
  main=int(subprocess.check_output(['systemctl','show','tlz-display','--property=MainPID','--value'],timeout=3).strip() or b'0')
  if main!=seen:seen=main;since=time.monotonic()
  good=False
  if main:
   try:
    pid=int((Path('/run/user')/str(uid)/'tlz-firefox-wrapper.pid').read_text());s=Path(f'/proc/{pid}/status').read_text();parent=int(next(x for x in s.splitlines() if x.startswith('PPid:')).split()[1]);s=Path(f'/proc/{parent}/status').read_text();grandparent=int(next(x for x in s.splitlines() if x.startswith('PPid:')).split()[1]);good=grandparent==main and b'/usr/local/lib/tlz-kiosk/firefox.py' in Path(f'/proc/{pid}/cmdline').read_bytes()
   except (OSError,ValueError,StopIteration):pass
   if good:since=time.monotonic()
   elif time.monotonic()-since>30:
    print('No browser launcher after 30s; retry dedicated display',flush=True);subprocess.run(['systemctl','restart','--no-block','tlz-display'],check=True);since=time.monotonic()
 except (OSError,ValueError,subprocess.SubprocessError):pass
 time.sleep(2)

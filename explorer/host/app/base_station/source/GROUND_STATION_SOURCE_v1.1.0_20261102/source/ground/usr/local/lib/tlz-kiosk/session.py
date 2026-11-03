"""Keep systemd's PAM helper parent separate from the compositor's child wait."""
import signal,subprocess,os,pwd
from pathlib import Path
signal.signal(signal.SIGHUP,signal.SIG_IGN)
log=Path.home()/'.local/state/ground-display';log.mkdir(parents=True,exist_ok=True)
output=(log/'display.log').open('ab',buffering=0)
child=subprocess.Popen(['/usr/bin/weston','--backend=drm','--renderer=gl','--shell=kiosk-shell.so','--idle-time=0','--no-config','--','/usr/bin/python3','/usr/local/lib/tlz-kiosk/firefox.py'],stdout=output,stderr=subprocess.STDOUT)
def stop(*args):
 if child.poll() is None:
  try:
   uid=pwd.getpwnam('apex').pw_uid;pid=int((Path('/run/user')/str(uid)/'tlz-firefox-wrapper.pid').read_text())
   if b'/usr/local/lib/tlz-kiosk/firefox.py' not in Path(f'/proc/{pid}/cmdline').read_bytes():raise ValueError()
   os.kill(pid,signal.SIGTERM)
  except (OSError,ValueError):child.terminate()
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
raise SystemExit(child.wait())

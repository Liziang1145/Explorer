"""One application on Cage. Closing Firefox relaunches it; PAM unlock ends seat."""
import json,os,subprocess,time,urllib.request,signal
from pathlib import Path
runtime=Path('/run/user')/str(os.getuid());os.environ.setdefault('XDG_RUNTIME_DIR',str(runtime));os.environ.setdefault('DBUS_SESSION_BUS_ADDRESS','unix:path='+str(runtime/'bus'));env={k:os.environ[k] for k in ('WAYLAND_DISPLAY','DISPLAY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS') if k in os.environ}
path=runtime/'tlz-kiosk-env.json';temp=path.with_suffix('.tmp');temp.write_text(json.dumps(env));temp.chmod(0o600);temp.replace(path)
profile=Path.home()/'.local/share/ground-display/firefox-profile';profile.mkdir(parents=True,exist_ok=True)
# Firefox's kiosk mode hides browser chrome and does not honor F11 as a kiosk exit.
prefs='user_pref("media.ffmpeg.vaapi.enabled", true);\nuser_pref("browser.shell.checkDefaultBrowser", false);\nuser_pref("browser.sessionstore.resume_from_crash", false);\nuser_pref("browser.startup.page", 0);\nuser_pref("media.autoplay.default", 0);\nuser_pref("media.autoplay.blocking_policy", 0);\nuser_pref("browser.aboutwelcome.enabled", false);\nuser_pref("datareporting.policy.dataSubmissionEnabled", false);\n'
(profile/'user.js').write_text(prefs)
with (profile/'user.js').open('a') as f:f.write('user_pref("media.peerconnection.ice.obfuscate_host_addresses", false);\nuser_pref("media.peerconnection.ice.default_address_only", false);\n')
while not Path('/run/tlz-display-unlocked').exists():
 try:
  urllib.request.urlopen('http://127.0.0.1:8080/preview',timeout=2).close();break
 except OSError:time.sleep(1)
env=os.environ.copy();env['MOZ_ENABLE_WAYLAND']='1';env['GDK_BACKEND']='wayland';env.pop('DISPLAY',None)
stopping=False;current=None
(runtime/'tlz-firefox-wrapper.pid').write_text(str(os.getpid()))
def stop(*args):
 global stopping
 stopping=True
 if current and current.poll() is None:current.terminate()
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
while not stopping and os.getppid()!=1 and not Path('/run/tlz-display-unlocked').exists():
 args=['/opt/ground-display/firefox/firefox','--kiosk','--no-remote','--profile',str(profile),'http://127.0.0.1:8080/local?release=vr-view-20261028']
 if os.environ.get('TLZ_KIOSK_PROBE')=='1':args.insert(1,'--marionette')
 current=subprocess.Popen(args,env=env);current.wait();current=None
 time.sleep(1)

import json,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PATH=ROOT/'hub-settings.json';LOCK=threading.RLock();INTERVALS=(500,1000,2000,5000,10000)
def get():
    with LOCK:
        try:data=json.loads(PATH.read_text())
        except (OSError,ValueError):data={}
        interval=data.get('refresh_interval_ms',1000)
        if type(interval)!=int or interval not in INTERVALS:interval=1000
        return {'refresh_interval_ms':interval,'min_interval_ms':500,'default_interval_ms':1000,'allowed_intervals_ms':INTERVALS,'sample_interval_ms':400,'pause_when_hidden':True}
def save(data):
    interval=data.get('refresh_interval_ms')
    if type(interval)!=int or interval not in INTERVALS:raise ValueError('刷新间隔无效')
    with LOCK:
        temp=PATH.with_suffix('.tmp');temp.write_text(json.dumps({'refresh_interval_ms':interval}));temp.replace(PATH)
    return get()

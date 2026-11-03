# -*- coding: utf-8 -*-
"""AIPC 本地 VLA 连续采集；仅读取相机、CAN 反馈与控制状态。"""
import datetime
import json
import re
import subprocess
import threading
import time
from pathlib import Path
import urllib.request

ROOT = Path('/home/apex/datasets/vla_cup_grasp')
CAM = 'http://127.0.0.1:8098'
CONSOLE = 'http://127.0.0.1:8092'
TOKEN = Path('/home/apex/md-service/kr260-agent-token').read_text().strip()
_lock = threading.Lock()
_session = None


def _get(url, token=False):
    headers = {'Authorization': 'Bearer '+TOKEN} if token else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=5) as response:
        return response.read(), dict(response.headers.items())


def _target():
    command = ['/home/apex/.local/opt/vision-yolo-venv/bin/python', '/home/apex/cup_target_live.py']
    done = subprocess.run(command, capture_output=True, text=True, timeout=45)
    return json.loads(done.stdout.strip().splitlines()[-1])


class Session:
    def __init__(self, sample, app):
        self.sample = sample
        self.app = app
        self.folder = ROOT/sample
        if self.folder.exists():
            raise ValueError('样本编号已存在，请更换编号')
        (self.folder/'frames').mkdir(parents=True)
        self.stage = 'prepared'
        self.stop_event = threading.Event()
        self.index = 0
        self.errors = []
        self.started_wall = time.time()
        self.started_mono = time.monotonic()
        self.target = _target()
        (self.folder/'target.json').write_text(json.dumps(self.target, ensure_ascii=False, indent=2), encoding='utf-8')
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        with (self.folder/'records.jsonl').open('a', encoding='utf-8') as output:
            while not self.stop_event.is_set():
                began = time.monotonic()
                try:
                    rgb, rh = _get(CAM+'/frame/camera.jpg', True)
                    depth, dh = _get(CAM+'/frame/depth.raw', True)
                    _, sh = _get(CONSOLE+'/api/status')
                    status = json.loads(_get(CONSOLE+'/api/status')[0])
                    lok, ldeg = self.app.left_read()
                    rok, rdeg = self.app.right_read()
                    name = f'{self.index:06d}'
                    (self.folder/'frames'/(name+'.jpg')).write_bytes(rgb)
                    (self.folder/'frames'/(name+'.depth.raw')).write_bytes(depth)
                    record = {'index': self.index, 'timestamp_unix': time.time(),
                        'elapsed_s': began-self.started_mono, 'stage': self.stage,
                        'rgb_file': 'frames/'+name+'.jpg', 'depth_file': 'frames/'+name+'.depth.raw',
                        'rgb_headers': rh, 'depth_headers': dh, 'status_headers': sh,
                        'actual_left_deg': self.app.angles(ldeg) if lok else None,
                        'actual_right_deg': self.app.angles(rdeg) if rok else None,
                        'actual_feedback_ok': {'left': lok, 'right': rok},
                        'control_status': status}
                    output.write(json.dumps(record, ensure_ascii=False)+'\n');output.flush()
                    self.index += 1
                except Exception as exc:
                    self.errors.append(time.strftime('%F %T')+' '+type(exc).__name__+': '+str(exc))
                self.stop_event.wait(max(0.02, 0.2-(time.monotonic()-began)))

    def finish(self, result, note):
        self.stop_event.set();self.thread.join(timeout=15)
        manifest = {'format': 'vla_cup_grasp_v1', 'sample': self.sample,
            'started_at': datetime.datetime.fromtimestamp(self.started_wall, datetime.timezone.utc).isoformat(),
            'ended_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'frames': self.index, 'nominal_rate_hz': 5, 'result': result, 'note': note,
            'target': self.target, 'errors': self.errors, 'storage': 'AIPC',
            'files': {'records':'records.jsonl', 'frames':'frames/'},
            'units': {'actual_angles':'deg', 'depth':'见每帧 depth_headers'},
            'motion_commands_sent_by_recorder': False}
        (self.folder/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return manifest


def run(data, app):
    global _session
    action = data.get('action')
    with _lock:
        if action == 'start':
            if _session is not None:
                raise ValueError('已有采集任务正在进行')
            sample = str(data.get('sample', '')).strip()
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', sample):
                raise ValueError('样本编号格式无效')
            _session = Session(sample, app);_session.thread.start()
            return {'ok': True, 'recording': True, 'sample': sample, 'directory': str(_session.folder)}
        if action == 'stage':
            if _session is None:
                return {'ok': True, 'recording': False}
            stage = str(data.get('stage', ''))[:64]
            _session.stage = stage
            with (_session.folder/'events.jsonl').open('a', encoding='utf-8') as event:
                event.write(json.dumps({'timestamp_unix': time.time(), 'frame_index': _session.index,
                    'stage': stage}, ensure_ascii=False)+'\n')
            return {'ok': True, 'recording': True, 'stage': stage}
        if action == 'stop':
            if _session is None:
                raise ValueError('当前没有进行中的采集')
            result = data.get('result', 'unknown')
            if result not in ('success', 'failure', 'unknown'):
                raise ValueError('结果标签无效')
            session = _session;_session = None
            manifest = session.finish(result, str(data.get('note', ''))[:300])
            return {'ok': True, 'recording': False, 'manifest': manifest,
                'directory': str(session.folder)}
        if action == 'status':
            return {'ok': True, 'recording': _session is not None,
                'sample': _session.sample if _session else None,
                'frames': _session.index if _session else 0}
        if action == 'summary':
            formal_success = 0
            for folder in ROOT.glob('cup_*'):
                try:
                    number = int(folder.name.rsplit('_', 1)[1])
                    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
                    if number >= 3 and manifest.get('result') == 'success' and not manifest.get('errors'):
                        formal_success += 1
                except (ValueError, OSError, json.JSONDecodeError):
                    continue
            return {'ok': True, 'formal_success': formal_success,
                'target': 50, 'remaining': max(0, 50-formal_success)}
        raise ValueError('未知采集动作')

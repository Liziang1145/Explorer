# -*- coding: utf-8 -*-
"""保存一次杯子夹取样本；只读相机、识别和控制状态，绝不发送运动命令。"""
import argparse
import datetime
import json
from pathlib import Path
import urllib.request

CAM = 'http://127.0.0.1:8098'
CONSOLE = 'http://127.0.0.1:8092'
TOKEN = Path('/home/apex/md-service/kr260-agent-token').read_text().strip()


def fetch(url, token=False):
    headers = {'Authorization': 'Bearer '+TOKEN} if token else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as response:
        return response.read(), dict(response.headers.items())


def post_readonly(path, data):
    request = urllib.request.Request(CONSOLE+path, data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sample', help='相同样本前后使用同一名称，例如 cup_0001')
    parser.add_argument('phase', choices=('before', 'after'))
    parser.add_argument('--result', choices=('unknown', 'success', 'failure'), default='unknown')
    parser.add_argument('--note', default='')
    parser.add_argument('--target', action='store_true', help='同时保存只读识别目标及坐标换算')
    parser.add_argument('--root', type=Path, default=Path('/home/apex/datasets/cup_grasp'))
    args = parser.parse_args()
    folder = args.root/args.sample
    folder.mkdir(parents=True, exist_ok=True)
    rgb, rgb_headers = fetch(CAM+'/frame/camera.jpg', True)
    depth, depth_headers = fetch(CAM+'/frame/depth.raw', True)
    _, status_headers = fetch(CONSOLE+'/api/status')
    status = json.loads(fetch(CONSOLE+'/api/status')[0])
    prefix = folder/args.phase
    prefix.with_suffix('.jpg').write_bytes(rgb)
    prefix.with_suffix('.depth.raw').write_bytes(depth)
    metadata = {'sample': args.sample, 'phase': args.phase, 'result': args.result,
        'note': args.note, 'saved_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'rgb_headers': rgb_headers, 'depth_headers': depth_headers,
        'status_headers': status_headers, 'control_status': status,
        'motion_commands_sent': False}
    if args.target:
        metadata['grasp_target_preview'] = post_readonly('/api/grasp_target_preview', {'side':'left'})
    prefix.with_suffix('.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'directory': str(folder), 'phase': args.phase,
        'motion_commands_sent': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""实时 YOLO + 深度杯子目标 → 臂基系 J5 预抓点。只读，不发送运动。"""
import json
import math
import subprocess
import time
from stone_grasp_trial import color_optical_to_body, pregrasp_target

MAX_AGE_S = 5.0


def _live_target():
    command = ['/home/apex/.local/opt/vision-yolo-venv/bin/python',
               '/home/apex/cup_target_live.py']
    completed = subprocess.run(command, capture_output=True, text=True, timeout=45)
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ValueError('实时识别进程未返回有效结果：'+completed.stderr[-300:])
    if completed.returncode or not payload.get('ok'):
        raise ValueError(payload.get('error') or '实时杯子识别失败')
    return payload


def run(data):
    side = data.get('side', 'left')
    if side not in ('left', 'right'):
        raise ValueError('side 必须为 left 或 right')
    payload = _live_target()
    stamp = payload.get('timestamp', payload.get('stamp'))
    if type(stamp) not in (int, float) or not math.isfinite(stamp):
        raise ValueError('识别目标缺少有限 Unix 时间戳 timestamp')
    age = time.time() - stamp
    if not 0 <= age <= MAX_AGE_S:
        raise ValueError(f'识别目标已过期或时间异常（age={age:.2f}s），拒绝使用')
    if 'point_b_m' in payload:
        point_b = payload['point_b_m']
        source_frame = 'B'
    elif 'point_color_m' in payload:
        point_b = color_optical_to_body(payload['point_color_m'])
        source_frame = 'color_optical'
    else:
        raise ValueError('识别目标必须提供 point_b_m 或 point_color_m（米）')
    target = pregrasp_target(point_b, side)
    return {
        'ok': True, 'read_only': True, 'execution_enabled': False,
        'side': side, 'xyz': list(target['pregrasp_j5_arm_m']),
        'target': target, 'label': payload.get('label', '未命名目标'),
        'confidence': payload.get('confidence'), 'source_frame': source_frame,
        'timestamp': stamp, 'age_s': age,
        'request_started_unix': payload.get('request_started_unix'),
        'camera_device_timestamp_us': payload.get('camera_device_timestamp_us'),
        'timing_ms': payload.get('timing_ms', {}),
        'warning': '使用候选相机外参；只填充预抓 J5，仍需规划预检，不自动执行',
    }

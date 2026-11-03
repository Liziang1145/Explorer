# -*- coding: utf-8 -*-
"""SmolVLA 实时输入→原始动作块→只读安全预检；绝不包含控制或执行调用。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import sys
import urllib.request

import numpy as np

ROOT = Path('/home/apex/outputs/smolvla_cup_v1_100steps')
MODEL = ROOT / 'checkpoints/000100/pretrained_model'
CHUNK_FILE = ROOT / 'live_action_chunk.json'
REPORT_FILE = ROOT / 'live_safety_preview.json'
TASK = 'Pick up the cup.'
FPS = 5
# 与现有关节轨迹预检的 2° 插值粒度一致；这是诊断阈值，不是执行许可。
MAX_STEP_RAD = math.radians(2.0)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def predict():
    import torch
    from PIL import Image
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    from lerobot.policies.factory import make_pre_post_processors

    # 这里只导入常量；APEX_OFFLINE 阻止 arm_console 启动反馈线程。
    import os
    os.environ['APEX_OFFLINE'] = '1'
    sys.path.insert(0, '/home/apex')
    import arm_console as app

    token = Path('/home/apex/md-service/kr260-agent-token').read_text().strip()
    request = urllib.request.Request(
        'http://127.0.0.1:8098/frame/camera.jpg',
        headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(request, timeout=10) as response:
        encoded = response.read()
    with urllib.request.urlopen('http://127.0.0.1:8092/api/vr_telemetry', timeout=10) as response:
        telemetry = json.load(response)
    left = telemetry['arms']['left']
    right = telemetry['arms']['right']
    left_deg = np.asarray(left['fb_deg'], dtype=np.float64)
    right_deg = np.asarray(right['fb_deg'], dtype=np.float64)
    if left_deg.shape != (6,) or right_deg.shape != (6,):
        raise ValueError('双臂实际反馈必须为六轴')
    if not np.isfinite(left_deg).all() or not np.isfinite(right_deg).all():
        raise ValueError('实际反馈包含非有限角度')
    grip = float(left['grip_open'])
    if not math.isfinite(grip) or not 0.0 <= grip <= 1.0:
        raise ValueError('夹爪实际开度无效')
    state = np.concatenate((np.radians(left_deg), [grip])).astype(np.float32)
    with Image.open(io.BytesIO(encoded)) as image:
        rgb = np.asarray(image.convert('RGB'), dtype=np.uint8)
    if rgb.shape != (720, 1280, 3):
        raise ValueError(f'实时彩色图尺寸异常：{rgb.shape}')
    image_tensor = torch.from_numpy(rgb.copy()).permute(2, 0, 1).unsqueeze(0).float().div_(255.0)

    policy = SmolVLAPolicy.from_pretrained(MODEL).to('cpu').eval()
    preprocessor, postprocessor = make_pre_post_processors(
        policy.config, pretrained_path=str(MODEL))
    batch = {
        'observation.images.head': image_tensor,
        'observation.state': torch.from_numpy(state).unsqueeze(0),
        'task': [TASK],
    }
    with torch.inference_mode():
        chunk = postprocessor(policy.predict_action_chunk(preprocessor(batch)))[0].cpu().numpy()
    if chunk.shape != (50, 7):
        raise ValueError(f'动作块尺寸异常：{chunk.shape}')

    finite = bool(np.isfinite(chunk).all())
    lo, hi = np.asarray(app.JOINT_LO), np.asarray(app.JOINT_HI)
    deltas = np.diff(chunk[:, :6], axis=0)
    start_delta = chunk[0, :6] - np.radians(left_deg)
    max_delta = np.abs(deltas).max(axis=0)
    gripper_ok = bool(np.all((chunk[:, 6] >= 0.0) & (chunk[:, 6] <= 1.0)))
    limit_failures = [
        {'frame': index, 'joint': joint + 1, 'value_rad': float(chunk[index, joint]),
         'lo_rad': float(lo[joint]), 'hi_rad': float(hi[joint])}
        for index in range(50) for joint in range(6)
        if not lo[joint] <= chunk[index, joint] <= hi[joint]
    ]
    jump_failures = [
        {'segment': 'actual→0', 'joint': joint + 1,
         'delta_rad': float(start_delta[joint])}
        for joint in range(6) if abs(start_delta[joint]) > MAX_STEP_RAD
    ] + [
        {'segment': f'{index}→{index + 1}', 'joint': joint + 1,
         'delta_rad': float(deltas[index, joint])}
        for index in range(49) for joint in range(6)
        if abs(deltas[index, joint]) > MAX_STEP_RAD
    ]
    result = {
        'schema': 'smolvla-live-action-chunk-v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'model_path': str(MODEL),
        'checkpoint_step': 100,
        'task': TASK,
        'fps': FPS,
        'input': {
            'image_shape': list(rgb.shape),
            'image_preprocessing': 'RGB uint8 → float CHW / 255 → checkpoint preprocessor',
            'left_actual_deg': left_deg.tolist(),
            'right_actual_deg': right_deg.tolist(),
            'left_grip_open': grip,
            'state': state.tolist(),
            'state_source': '/api/vr_telemetry arms.*.fb_deg（实际反馈，非目标值）',
        },
        'action_chunk_rad_and_grip_open': chunk.tolist(),
        'basic_checks': {
            'shape_ok': True,
            'finite': finite,
            'gripper_range_ok': gripper_ok,
            'joint_limits_ok': not limit_failures,
            'jump_ok': not jump_failures,
            'jump_threshold_rad': MAX_STEP_RAD,
            'limit_failures': limit_failures,
            'jump_failures': jump_failures,
            'initial_delta_deg': np.degrees(start_delta).tolist(),
            'max_step_delta_deg': np.degrees(max_delta).tolist(),
            'gripper_range': [float(chunk[:, 6].min()), float(chunk[:, 6].max())],
        },
        'read_only': True,
        'execution_sent': False,
    }
    write_json(CHUNK_FILE, result)
    print(json.dumps({'chunk_file': str(CHUNK_FILE), **result['basic_checks']}, ensure_ascii=False))


def check_collision():
    data = json.loads(CHUNK_FILE.read_text())
    chunk = np.asarray(data['action_chunk_rad_and_grip_open'], dtype=np.float64)
    if chunk.shape != (50, 7) or not np.isfinite(chunk).all():
        raise ValueError('动作块无效，拒绝安全预检')
    # FCL 二进制依赖留在原规划环境，不污染 LeRobot 环境。
    for packages in Path('/home/apex/vla_exact_venv/lib').glob('python*/site-packages'):
        sys.path.insert(0, str(packages))
    sys.path.insert(0, '/home/apex')
    from exact_collision import ExactMeshCollisionModel

    right = np.radians(np.asarray(data['input']['right_actual_deg'], dtype=np.float64))
    collision = ExactMeshCollisionModel(other_arm_q={'right': right}, check_gripper=False)
    poses, failures = [], []
    for index, row in enumerate(chunk):
        checked = collision.pose(row[:6], 'left')
        item = {'frame': index, 'ok': bool(checked.ok),
                'reason': checked.reason, 'margin_cm': float(checked.margin_cm)}
        poses.append(item)
        if not checked.ok:
            failures.append(item)
    basic = data['basic_checks']
    basic_ok = all((basic['shape_ok'], basic['finite'], basic['gripper_range_ok'],
                    basic['joint_limits_ok'], basic['jump_ok']))
    result = dict(data)
    result.update({
        'schema': 'smolvla-live-safety-preview-v1',
        'collision_check': {
            'ok': not failures,
            'checked_frames': len(poses),
            'failed_frames': [item['frame'] for item in failures],
            'failures': failures,
            'poses': poses,
            'minimum_clearance_cm': float(collision.minimum_clearance_cm),
            'distance_checks': collision.distance_checks,
            'model': 'ExactMeshCollisionModel',
            'check_gripper': False,
            'right_arm': '固定为输入快照中的实际反馈',
            'scope': '离散位姿：双臂连杆网格＋支架／雷达底座／完整底盘；不含夹爪、持物、动态环境，不是连续碰撞证明',
        },
        'overall_precheck_ok': basic_ok and not failures,
        'execution_sent': False,
        'control_endpoints_called': [],
        'note': '仅供软件链路验证；100 步／13 组样本模型不具有已证明的泛化或实机抓取能力。',
    })
    write_json(REPORT_FILE, result)
    print(json.dumps({
        'report_file': str(REPORT_FILE),
        'basic_ok': basic_ok,
        'collision_ok': not failures,
        'checked_frames': len(poses),
        'failed_frames': result['collision_check']['failed_frames'],
        'minimum_clearance_cm': result['collision_check']['minimum_clearance_cm'],
        'overall_precheck_ok': result['overall_precheck_ok'],
        'execution_sent': False,
    }, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('predict', 'check'))
    args = parser.parse_args()
    if args.stage == 'predict':
        predict()
    else:
        check_collision()

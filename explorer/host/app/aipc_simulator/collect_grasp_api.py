# -*- coding: utf-8 -*-
"""网页只读采集接口：校验参数后调用采集程序，不发送运动命令。"""
import json
import re
import subprocess


def run(data):
    sample = str(data.get('sample', '')).strip()
    phase = data.get('phase')
    result = data.get('result', 'unknown')
    note = str(data.get('note', ''))[:300]
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', sample):
        raise ValueError('样本编号仅允许字母、数字、下划线和短横线，最长 64 位')
    if phase not in ('before', 'after'):
        raise ValueError('phase 必须为 before 或 after')
    if result not in ('unknown', 'success', 'failure'):
        raise ValueError('采集结果无效')
    command = ['/usr/bin/python3', '/home/apex/collect_grasp_sample.py', sample, phase,
               '--result', result, '--note', note]
    if phase == 'before':
        command.append('--target')
    completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        payload = {}
    if completed.returncode or not payload.get('ok'):
        raise RuntimeError(payload.get('error') or completed.stderr[-500:] or '采集失败')
    return payload

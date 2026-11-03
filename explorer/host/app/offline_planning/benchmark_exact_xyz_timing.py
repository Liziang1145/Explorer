# -*- coding: utf-8 -*-
"""起始位到多个实际 XYZ 目标的精确网格分阶段计时；不连接设备。"""
from __future__ import annotations

import csv
import functools
import json
from pathlib import Path
import time

import numpy as np

import vla_motion_planner as planner
import arm_console as app

OUTPUT = Path(__file__).resolve().parent/'输出'/'精确XYZ规划计时_20261101'
OUTPUT.mkdir(parents=True, exist_ok=True)


timing_stack = []


def timed(function, bucket, key):
    """嵌套函数只计自身耗时，子调用时间归入父调用但不重复累计。"""
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        frame = [time.perf_counter(), 0.0]
        timing_stack.append(frame)
        try:
            return function(*args, **kwargs)
        finally:
            timing_stack.pop()
            elapsed = time.perf_counter()-frame[0]
            bucket[key] += elapsed-frame[1]
            bucket[key+'_calls'] += 1
            if timing_stack:
                timing_stack[-1][1] += elapsed
    return wrapper


records = []
targets = [('放置拾取位置1', app.Q_LEFT_POS1),
           ('放置拾取位置2', app.Q_LEFT_POS2),
           ('放置拾取位置3', app.Q_LEFT_POS3)]
for index, (name, goal) in enumerate(targets):
    timing = dict(ik_s=0.0, ik_s_calls=0, rrt_s=0.0, rrt_s_calls=0,
                  collision_pose_s=0.0, collision_pose_s_calls=0,
                  toppra_s=0.0, toppra_s_calls=0)
    patches = []
    original_ik = app.solve_layered_j5_pose_user
    original_rrt = planner.RRTConnect.solve
    original_parameterize = planner._parameterize
    app.solve_layered_j5_pose_user = timed(original_ik, timing, 'ik_s')
    planner.RRTConnect.solve = timed(original_rrt, timing, 'rrt_s')
    planner._parameterize = timed(original_parameterize, timing, 'toppra_s')
    xyz = app._fk_points(goal, 'left')[0][5]
    orientation = planner._rotation(goal, 'left')
    started = time.perf_counter()
    try:
        from exact_collision import ExactMeshCollisionModel
        original_pose = ExactMeshCollisionModel.pose
        ExactMeshCollisionModel.pose = timed(original_pose, timing, 'collision_pose_s')
        result = planner.plan_j5_xyz(
            'left', xyz, orientation=orientation, current_q=app.Q_START_LEFT,
            other_arm_q={'right': app.Q_START_RIGHT}, collision_mode='exact')
        status, error = 'ok', None
    except Exception as exc:
        result, status, error = None, 'failed', f'{type(exc).__name__}: {exc}'
    finally:
        app.solve_layered_j5_pose_user = original_ik
        planner.RRTConnect.solve = original_rrt
        planner._parameterize = original_parameterize
        if 'ExactMeshCollisionModel' in locals():
            ExactMeshCollisionModel.pose = original_pose
    total = time.perf_counter()-started
    record = {
        'target': name, 'xyz_m': list(xyz), 'status': status, 'error': error,
        'cold_or_warm': 'cold' if index == 0 else 'warm',
        'total_s': total, **timing,
        'other_s': total-timing['ik_s']-timing['rrt_s']-timing['collision_pose_s']-timing['toppra_s'],
    }
    if result is not None:
        record.update(direct=result['search']['direct'],
                      path_nodes=result['path_nodes_before_timing'],
                      duration_s=result['duration_s'],
                      mesh_pose_checks=result['mesh_pose_checks'],
                      mesh_distance_checks=result['mesh_distance_checks'],
                      minimum_mesh_clearance_cm=result['minimum_mesh_clearance_cm'])
    records.append(record)
    print(json.dumps(record, ensure_ascii=False), flush=True)

(OUTPUT/'timing.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
fields = sorted({key for record in records for key in record})
with (OUTPUT/'timing.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)
print('OUTPUT', OUTPUT)

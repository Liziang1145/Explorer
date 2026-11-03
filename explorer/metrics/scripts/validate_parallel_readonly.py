#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""串行与并行精确规划一致性回归；仅独立离线计算。"""
import json
import time
import numpy as np
import vla_motion_planner as planner

XYZ = [-0.17177560060429417, 0.3889378547341156, 0.04781156417029076]


def run(workers):
    started = time.perf_counter()
    result = planner.plan_j5_xyz(
        'left', XYZ, current_q=planner.app.Q_START_LEFT,
        collision_mode='exact', check_gripper=False, collision_workers=workers,
        nearest_orientation=True)
    result['_elapsed_ms'] = (time.perf_counter() - started) * 1000
    return result


serial = run(1)
parallel = run(4)
assert np.array_equal(serial['q'], parallel['q']), '关节轨迹不一致'
assert np.array_equal(serial['times'], parallel['times']), '时间戳不一致'
assert serial['search'] == parallel['search'], '搜索路径不一致'
assert serial['mesh_pose_checks'] == parallel['mesh_pose_checks'], '位形检查数不一致'
assert serial['mesh_distance_checks'] == parallel['mesh_distance_checks'], '距离检查数不一致'
assert serial['minimum_mesh_clearance_cm'] == parallel['minimum_mesh_clearance_cm'], '最小余量不一致'
print(json.dumps({
    'safety': 'offline_only_no_motion_interfaces',
    'serial_ms': round(serial['_elapsed_ms'], 3),
    'parallel_4_ms': round(parallel['_elapsed_ms'], 3),
    'speedup': round(serial['_elapsed_ms'] / parallel['_elapsed_ms'], 3),
    'trajectory_identical': True,
    'mesh_pose_checks': serial['mesh_pose_checks'],
    'mesh_distance_checks': serial['mesh_distance_checks'],
    'minimum_mesh_clearance_cm': serial['minimum_mesh_clearance_cm'],
}, ensure_ascii=False, indent=2))

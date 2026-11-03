# -*- coding: utf-8 -*-
"""同一组目标下比较保守粗模型与 FCL 精确双臂网格；仅离线。"""
import json
import time
from pathlib import Path
import numpy as np

import vla_motion_planner as planner
import arm_console as app

HERE = Path(__file__).resolve().parent
records = []
for label, goal in [('pos1', app.Q_LEFT_POS1), ('pos2', app.Q_LEFT_POS2), ('pos3', app.Q_LEFT_POS3)]:
    goal = np.asarray(goal)
    xyz = app._fk_points(goal, 'left')[0][5]
    orientation = planner._rotation(goal, 'left')
    pair = {}
    for mode in ('coarse', 'exact'):
        started = time.perf_counter()
        plan = planner.plan_j5_xyz(
            'left', xyz, orientation=orientation, current_q=app.Q_START_LEFT,
            other_arm_q={'right': app.Q_START_RIGHT}, seed=7,
            collision_mode=mode)
        elapsed = time.perf_counter() - started
        pair[mode] = plan
        record = {
            'target': label, 'mode': mode, 'elapsed_s': elapsed,
            'duration_s': plan['duration_s'], 'timed_poses': len(plan['q']),
            'path_nodes_before_timing': plan['path_nodes_before_timing'],
            'search': plan['search'],
        }
        if mode == 'exact':
            record.update(mesh_pose_checks=plan['mesh_pose_checks'],
                          mesh_distance_checks=plan['mesh_distance_checks'],
                          minimum_mesh_clearance_cm=plan['minimum_mesh_clearance_cm'])
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    a, b = np.asarray(pair['coarse']['q']), np.asarray(pair['exact']['q'])
    records[-1]['same_timed_trajectory_as_coarse'] = bool(
        a.shape == b.shape and np.allclose(a, b, rtol=0, atol=1e-12))

report = {
    'method': '同一左臂起始位、位置1/2/3目标、姿态与随机种子；分别运行粗模型和FCL精确网格',
    'records': records,
    'limitations': ['精确模式不含完整底盘／支架网格、持物和动态环境',
                    '离散轨迹复核不是数学意义上的连续碰撞证明',
                    '结果是本机离线测量，不代表KR260或AIPC耗时'],
}
out = HERE / '输出' / '粗模型与精确网格规划对比.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(out)

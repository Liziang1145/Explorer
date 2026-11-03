# -*- coding: utf-8 -*-
"""左臂全搬运轨迹与固定右臂的 FCL 精确网格距离审计。"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / '.deps'))
sys.path.insert(0, str(ROOT / 'aipc-simulator-ui'))
sys.path.insert(0, str(HERE))
import fcl
import numpy as np

import arm_console as app
import vla_motion_planner as planner
import exact_mesh_audit as exact


def objects(q, right=False, opening=0.0):
    frames = exact.transforms(q, opening)
    result = {}
    for link, (rotation, translation) in frames.items():
        if right:
            # 用户系 +X 的 30.51 cm 对应原生臂底座系 -Y。
            translation = translation + np.asarray([0.0, -0.3051, 0.0])
        result[link] = fcl.CollisionObject(exact.model(link), fcl.Transform(rotation, translation))
    return result


def main():
    start, goal = np.asarray(app.Q_START_LEFT), np.asarray(app.Q_LEFT_POS3)
    xyz = app._fk_points(goal, 'left')[0][5]
    plan = planner.plan_j5_xyz('left', xyz, orientation=planner._rotation(goal, 'left'),
                               current_q=start, other_arm_q={'right': app.Q_START_RIGHT})
    right_zero = np.radians([0.0, 3.21, -3.27, 0.0, -0.46, 0.0])
    results = []
    for other_label, other_q in (('right_zero', right_zero), ('right_start', app.Q_START_RIGHT)):
        other = objects(other_q, right=True)
        worst = None
        for index, q in enumerate(np.asarray(plan['q'])):
            own = objects(q)
            for a in range(1, 9):
                for b in range(1, 9):
                    request = fcl.DistanceRequest(enable_nearest_points=False)
                    result = fcl.DistanceResult()
                    distance = fcl.distance(own[a], other[b], request, result)*1000
                    if worst is None or distance < worst['distance_mm']:
                        worst = {'distance_mm': float(distance), 'left_link': a,
                                 'right_link': b, 'case': f'planned_{index:03d}'}
        results.append({'other_arm': other_label, 'checks': len(plan['q'])*64,
                        'worst': worst, 'passes_no_intersection': worst['distance_mm'] > 1e-6,
                        'passes_20mm_margin': worst['distance_mm'] >= 20.0})
    report = {'method': 'FCL三角形网格，左臂全TOPP-RA轨迹×固定右臂64组零件',
              'results': results,
              'limitations': ['右臂保持固定', '左臂每指开合0mm；另做最大开合关键点复核',
                              '不含底盘和支架精确网格']}
    # 最紧轨迹附近及位置3，补最大开合检查。
    opening_checks = []
    for index in (0, 60, 120, 140, len(plan['q'])-1):
        own = objects(plan['q'][index], opening=0.035)
        for other_label, other_q in (('right_zero', right_zero), ('right_start', app.Q_START_RIGHT)):
            other = objects(other_q, right=True, opening=0.035)
            minimum = min(fcl.distance(own[a], other[b], fcl.DistanceRequest(), fcl.DistanceResult())*1000
                          for a in range(1, 9) for b in range(1, 9))
            opening_checks.append({'case': f'planned_{index:03d}', 'other_arm': other_label,
                                   'opening_each_mm': 35.0, 'minimum_mm': float(minimum)})
    report['opening_checks'] = opening_checks
    output = HERE / '输出' / 'FCL双臂全轨迹审计.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(output)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""多进程精确碰撞复核基准；Windows 必须使用 main 保护。"""
import json
from pathlib import Path
import time


def main():
    import vla_motion_planner as planner
    import arm_console as app
    records = []
    targets = [('放置拾取位置1', app.Q_LEFT_POS1),
               ('放置拾取位置2', app.Q_LEFT_POS2),
               ('放置拾取位置3', app.Q_LEFT_POS3)]
    for name, goal in targets:
        started = time.perf_counter()
        result = planner.plan_j5_xyz(
            'left', app._fk_points(goal, 'left')[0][5],
            orientation=planner._rotation(goal, 'left'),
            current_q=app.Q_START_LEFT, other_arm_q={'right': app.Q_START_RIGHT},
            collision_mode='exact', collision_workers=6)
        summary = {'target': name, 'workers': 6, 'total_s': time.perf_counter()-started,
                   'mesh_pose_checks': result['mesh_pose_checks'],
                   'mesh_distance_checks': result['mesh_distance_checks'],
                   'minimum_mesh_clearance_cm': result['minimum_mesh_clearance_cm']}
        records.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    output = Path(__file__).resolve().parent/'输出'/'精确XYZ规划计时_20261101'/'parallel6.json'
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

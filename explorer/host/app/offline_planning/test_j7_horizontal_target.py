# -*- coding: utf-8 -*-
"""左臂起始位到指定 J7 测量点的水平姿态离线规划测试；不连接设备。"""
import json
import math
from pathlib import Path
import time

import numpy as np


def main():
    import vla_motion_planner as planner
    import arm_console as app

    p_j7 = np.array([-0.1718, 0.7798, 0.1010], dtype=float)
    # 夹爪轴水平朝车体 +Y，J5 位于 J7 后方 152.5 mm，roll=0 表示夹指沿车体 X 张开。
    p_j5 = p_j7 - np.array([0.0, app.TWO_POINT_J5_TCP, 0.0])
    rotation = app._two_point_orientation(p_j7, p_j5, 0.0, app.Q_START_LEFT, 'left')
    started = time.perf_counter()
    try:
        result = planner.plan_j5_xyz(
            'left', p_j5, orientation=rotation, current_q=app.Q_START_LEFT,
            other_arm_q={'right': app.Q_START_RIGHT}, collision_mode='exact',
            collision_workers=6)
        q = np.asarray(result['q'][-1])
        points, native_rotation = app._fk_points(q, 'left')
        achieved_j5 = np.asarray(points[5])
        axis = np.asarray(app._mv(app._FR, (native_rotation[0][2],
                                            native_rotation[1][2], native_rotation[2][2])))
        axis /= np.linalg.norm(axis)
        achieved_j7 = achieved_j5 + app.TWO_POINT_J5_TCP * axis
        result.update({
            'status': 'ok', 'planning_time_s': time.perf_counter() - started,
            'requested_j7_xyz_m': p_j7.tolist(), 'requested_j5_xyz_m': p_j5.tolist(),
            'achieved_j7_xyz_m': achieved_j7.tolist(),
            'j7_position_error_mm': float(np.linalg.norm(achieved_j7-p_j7)*1000),
            'gripper_axis_user': axis.tolist(),
            'axis_tilt_from_horizontal_deg': math.degrees(math.asin(np.clip(axis[2], -1, 1))),
            'target_joints_deg': np.degrees(q).tolist(),
        })
    except Exception as exc:
        result = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}',
                  'planning_time_s': time.perf_counter() - started,
                  'requested_j7_xyz_m': p_j7.tolist(), 'requested_j5_xyz_m': p_j5.tolist()}
    output = Path(__file__).resolve().parent/'输出'/'J7水平目标测试_20261101.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in ('q', 'times')},
                     ensure_ascii=False, indent=2))
    print('OUTPUT', output)


if __name__ == '__main__':
    main()

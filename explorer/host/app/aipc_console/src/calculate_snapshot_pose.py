# -*- coding: utf-8 -*-
"""由左臂六轴实际角度计算机型正运动学位姿，不连接设备。"""
import json
import math
from pathlib import Path

import numpy as np


def main():
    import vla_motion_planner  # 设置离线模式及 arm_console 导入路径。
    import arm_console as app

    q_deg = [0.6, 140.6, -78.8, 2.9, -60.2, -3.5]
    q = np.radians(q_deg)
    points, native_rotation = app._fk_points(q, 'left')
    rotation = np.asarray(app._mm(app._FR, native_rotation))
    j5 = np.asarray(points[5])
    flange = np.asarray(points[6])
    j7 = j5 + app.TWO_POINT_J5_TCP * rotation[:, 2]
    # 固定轴 X-Y-Z，等价 R=Rz(yaw)Ry(pitch)Rx(roll)。
    pitch = math.atan2(-rotation[2, 0], math.hypot(rotation[0, 0], rotation[1, 0]))
    roll = math.atan2(rotation[2, 1], rotation[2, 2])
    yaw = math.atan2(rotation[1, 0], rotation[0, 0])
    result = {
        'side': 'left', 'joints_deg': q_deg,
        'coordinate_frame': '底盘系：X右/Y前/Z上；本地标定为恒等',
        'joint_centers_m': {f'J{i+1}': list(map(float, p)) for i, p in enumerate(points)},
        'j5_xyz_m': j5.tolist(), 'flange_xyz_m': flange.tolist(), 'j7_gripper_center_xyz_m': j7.tolist(),
        'gripper_axis_user': rotation[:, 2].tolist(),
        'flange_opening_axis_user': rotation[:, 1].tolist(),
        'fixed_axis_rpy_deg': [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)],
        'rotation_user': rotation.tolist(),
    }
    output = Path(__file__).resolve().parent/'输出'/'实际姿态快照FK_20261101.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""FCL 三角形级分件网格审计；仅离线，不连接设备。"""
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
import trimesh

import arm_console as app
import vla_motion_planner as planner

MESH = next((path for path in (
    ROOT / 'piper_dual_arm_teleop' / 'assets' / 'meshes',
    ROOT / 'robot_ws' / 'piper_dual_arm_teleop' / 'assets' / 'meshes',
    HERE / 'robot_ws' / 'piper_dual_arm_teleop' / 'assets' / 'meshes',
) if path.is_dir()), None)
if MESH is None:
    raise FileNotFoundError('找不到机械臂网格目录：本机工程或 AIPC robot_ws')
PAIRS = (tuple((0, b) for b in range(3, 9)) +
         tuple((a, b) for a in range(1, 9) for b in range(a+1, 9)
               if b-a > 1 and (a, b) not in ((6, 8), (7, 8))))
_MODELS = {}
_BOUNDS = {}


def bounds(link):
    """机械臂分件局部网格包围盒，用于世界系粗筛；不替代精确距离。"""
    if link not in _BOUNDS:
        name = 'arm_base.STL' if link == 0 else ('gripper_base.STL' if link == 6 else f'link{link}.STL')
        mesh = trimesh.load(MESH / name, process=False)
        _BOUNDS[link] = np.asarray(mesh.bounds, dtype=float)
    return _BOUNDS[link]


def model(link):
    if link not in _MODELS:
        name = 'arm_base.STL' if link == 0 else ('gripper_base.STL' if link == 6 else f'link{link}.STL')
        mesh = trimesh.load(MESH / name, process=False)
        bvh = fcl.BVHModel()
        bvh.beginModel(len(mesh.vertices), len(mesh.faces))
        bvh.addSubModel(np.asarray(mesh.vertices, dtype=np.float64),
                        np.asarray(mesh.faces, dtype=np.int32))
        bvh.endModel()
        _MODELS[link] = bvh
    return _MODELS[link]


def transforms(q, opening_m=0.0):
    rotation = np.eye(3)
    translation = np.zeros(3)
    result = {0: (np.eye(3), np.zeros(3))}  # J1 下方固定底座，z=0～123mm
    for index in range(6):
        fixed_r, fixed_t = app._DTF[index]
        translation = translation + rotation @ np.asarray(fixed_t)
        rotation = rotation @ np.asarray(fixed_r) @ np.asarray(app._rt(0, 0, 0, 0, 0, q[index])[0])
        result[index+1] = rotation.copy(), translation.copy()
    # joint7/8 工具轴 135.8 mm；opening_m 为每指 0–35 mm 行程，轴向相反。
    gripper_r, gripper_t = result[6]
    for link, yaw, sign in ((7, 0.0, -1.0), (8, np.pi, 1.0)):
        fixed_r, fixed_t = app._rt(0, 0, 0.1358, np.pi/2, 0, yaw)
        opening = np.asarray([0.0, sign*opening_m, 0.0])
        result[link] = (gripper_r @ np.asarray(fixed_r),
                        gripper_t + gripper_r @ (np.asarray(fixed_t)+opening))
    return result


def audit_pose(label, q, opening_m=0.0):
    frames = transforms(q, opening_m)
    objects = {link: fcl.CollisionObject(model(link), fcl.Transform(frames[link][0], frames[link][1]))
               for link in range(0, 9)}
    pairs = []
    for a, b in PAIRS:
        request = fcl.DistanceRequest(enable_nearest_points=False)
        result = fcl.DistanceResult()
        distance = fcl.distance(objects[a], objects[b], request, result)
        pairs.append({'pair': f'{a}-{b}', 'distance_mm': float(distance*1000)})
    return {'case': label, 'pairs': pairs,
            'minimum_mm': min(item['distance_mm'] for item in pairs)}


def main():
    zero = np.radians([0.0, 3.21, -3.27, -0.17, -0.46, 0.0])
    start, goal = np.asarray(app.Q_START_LEFT), np.asarray(app.Q_LEFT_POS3)
    xyz = app._fk_points(goal, 'left')[0][5]
    plan = planner.plan_j5_xyz('left', xyz, orientation=planner._rotation(goal, 'left'),
                               current_q=start, other_arm_q={'right': app.Q_START_RIGHT})
    timed = np.asarray(plan['q'])
    poses = [('zero', zero), ('start', start), ('pos3', goal)]
    poses += [(f'planned_{index:03d}', q) for index, q in enumerate(timed)]
    results = [audit_pose(label, q) for label, q in poses]
    opening_results = []
    critical = [('zero', zero), ('start', start), ('pos3', goal), ('planned_140', timed[140])]
    for label, q in critical:
        for opening in np.linspace(0.0, 0.035, 8):
            opening_results.append(audit_pose(f'{label}_opening_{opening*1000:.0f}mm', q, opening))
    all_results = results + opening_results
    worst = {}
    for pose in all_results:
        for item in pose['pairs']:
            if item['pair'] not in worst or item['distance_mm'] < worst[item['pair']]['distance_mm']:
                worst[item['pair']] = dict(item, case=pose['case'])
    below = [item for item in worst.values() if item['distance_mm'] < 20.0]
    report = {
        'method': 'FCL BVH 三角形网格精确最短距离（离散姿态）',
        'pose_count': len(all_results), 'pair_count_per_pose': len(PAIRS),
        'total_pair_checks': len(all_results)*len(PAIRS),
        'includes': 'link1-link5＋gripper_base＋link7/link8每指0–35mm开合扫描',
        'limitations': ['相邻连杆及夹爪底座×两指按运动学连接排除',
                        '不包含持物、另一臂、底盘和支架精确网格', '离散采样不是连续碰撞证明'],
        'worst_by_pair': worst,
        'below_20mm': below,
        'zero_or_intersection': [item for item in worst.values() if item['distance_mm'] <= 1e-6],
        'minimum_mm': min(item['distance_mm'] for item in worst.values()),
        'poses': all_results,
    }
    output = HERE / '输出' / 'FCL全轨迹分件审计.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'poses'},
                     ensure_ascii=False, indent=2))
    print(output)


if __name__ == '__main__':
    main()

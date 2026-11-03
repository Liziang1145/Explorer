# -*- coding: utf-8 -*-
"""分件 STL 离线审计：变换一致性、非相邻件顶点距离与关键路径扫描。

顶点最近距离不是三角形级连续碰撞证明；负值或很小值必须进一步用网格碰撞复核。
"""
import json
import struct
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'aipc-simulator-ui'))
sys.path.insert(0, str(HERE))
import arm_console as app
import vla_motion_planner as planner

MESH = ROOT / 'piper_dual_arm_teleop' / 'assets' / 'meshes'
PAIRS = ((1, 3), (1, 4), (1, 5), (1, 6), (2, 4), (2, 5), (2, 6), (3, 5), (3, 6), (4, 6))
_CACHE = {}


def vertices(link):
    if link not in _CACHE:
        name = 'gripper_base.STL' if link == 6 else f'link{link}.STL'
        data = (MESH / name).read_bytes()
        count = struct.unpack_from('<I', data, 80)[0]
        dtype = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3, 3)), ('attr', '<u2')])
        triangles = np.frombuffer(data, offset=84, dtype=dtype, count=count)
        _CACHE[link] = np.unique(triangles['vertices'].reshape(-1, 3), axis=0)
    return _CACHE[link]


def transforms(q):
    rotation = np.eye(3)
    translation = np.zeros(3)
    result = {}
    for index in range(6):
        fixed_r, fixed_t = app._DTF[index]
        translation = translation + rotation @ np.asarray(fixed_t)
        rotation = rotation @ np.asarray(fixed_r) @ np.asarray(app._rt(0, 0, 0, 0, 0, q[index])[0])
        result[index+1] = rotation.copy(), translation.copy()
    return result


def audit_pose(label, q):
    frames = transforms(q)
    world = {link: vertices(link) @ frames[link][0].T + frames[link][1] for link in range(1, 7)}
    pairs = []
    for a, b in PAIRS:
        distance = float(cKDTree(world[a]).query(world[b])[0].min())
        pairs.append({'pair': f'link{a}-' + ('gripper_base' if b == 6 else f'link{b}'),
                      'vertex_min_mm': distance*1000})
    return {'case': label, 'q_deg': np.degrees(q).tolist(), 'pairs': pairs,
            'min_vertex_distance_mm': min(item['vertex_min_mm'] for item in pairs)}


def main():
    zero = np.radians([0.0, 3.21, -3.27, -0.17, -0.46, 0.0])
    start = np.asarray(app.Q_START_LEFT)
    goal = np.asarray(app.Q_LEFT_POS3)
    xyz = app._fk_points(goal, 'left')[0][5]
    plan = planner.plan_j5_xyz('left', xyz, orientation=planner._rotation(goal, 'left'),
                               current_q=start, other_arm_q={'right': app.Q_START_RIGHT})
    timed = np.asarray(plan['q'])
    poses = [('zero', zero), ('start', start), ('pos3', goal)]
    poses += [(f'planned_{index:02d}', timed[index])
              for index in np.linspace(0, len(timed)-1, 21).round().astype(int)]
    results = [audit_pose(label, q) for label, q in poses]
    worst = {}
    for result in results:
        for item in result['pairs']:
            pair = item['pair']
            if pair not in worst or item['vertex_min_mm'] < worst[pair]['vertex_min_mm']:
                worst[pair] = {'vertex_min_mm': item['vertex_min_mm'], 'case': result['case']}
    report = {
        'method': 'URDF同源FK＋二进制STL唯一顶点＋cKDTree最近顶点距离',
        'limitation': '非三角形级精确距离、非连续碰撞证明；未包含两指与持物',
        'pose_count': len(results), 'pairs_per_pose': len(PAIRS),
        'worst_by_pair': worst,
        'minimum_vertex_distance_mm': min(item['vertex_min_mm'] for item in worst.values()),
        'poses': results,
    }
    output = HERE / '输出' / '分件STL离线审计.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'poses'},
                     ensure_ascii=False, indent=2))
    print(output)


if __name__ == '__main__':
    main()

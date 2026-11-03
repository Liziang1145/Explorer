# -*- coding: utf-8 -*-
"""通用左臂 J5 XYZ 受控规划：真实反馈→精确预检→20%限速→既有会话执行。"""
import math
from pathlib import Path
import sys

VELOCITY_LIMIT = 0.50
DURATION_LIMIT = 30.0
ACCELERATION_LIMIT = 0.4
TIME_SCALE = 5.0
# 仅并行执行相互独立的相同精度碰撞复核，不减少位形或降低安全阈值。
COLLISION_WORKERS = 4


def _plan(data, app):
    side = data.get('side', 'left')
    if side not in ('left', 'right'):
        raise ValueError('side 必须为 left 或 right')
    xyz = data.get('xyz')
    if (not isinstance(xyz, list) or len(xyz) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in xyz)):
        raise ValueError('xyz 必须为三个有限坐标（米）')
    if data.get('collision_mode', 'exact') != 'exact':
        raise ValueError('通用受控执行当前仅允许 exact 精确网格预检')
    ok, left_deg = app.left_read()
    other_ok, right_deg = app.right_read()
    if not ok or not other_ok:
        raise ValueError('无法读取双臂完整反馈')
    current = [math.radians(v) for v in app.angles(left_deg if side == 'left' else right_deg)]
    other_side = 'right' if side == 'left' else 'left'
    other = [math.radians(v) for v in app.angles(right_deg if side == 'left' else left_deg)]
    start = app._fk_points(current, side)[0][5]
    displacement = [target-value for target, value in zip(xyz, start)]
    distance = math.sqrt(sum(value*value for value in displacement))
    # 不再按固定位移拒绝目标；可达性由解析 IK、精确碰撞和限速时长共同判定。
    for packages in Path('/home/apex/vla_exact_venv/lib').glob('python*/site-packages'):
        if str(packages) not in sys.path:
            sys.path.insert(0, str(packages))
    import vla_motion_planner
    result = vla_motion_planner.plan_j5_xyz(
        side, xyz, current_q=current,
        other_arm_q={other_side: other}, collision_mode='exact', check_gripper=False,
        collision_workers=COLLISION_WORKERS,
        nearest_orientation=data.get('nearest_orientation') is True)
    # 只读可视化几何：J5 全轨迹，以及起点／终点的关节骨架。
    result['preview_geometry'] = {
        'start_links_m': app._fk_points(result['q'][0], side)[0],
        'goal_links_m': app._fk_points(result['q'][-1], side)[0],
        'j5_path_m': [app._fk_points(q, side)[0][5] for q in result['q']],
    }
    result['times'] = [value*TIME_SCALE for value in result['times']]
    result['duration_s'] *= TIME_SCALE
    max_velocity = max(
        (max(abs(a-b) for a, b in zip(qa, qb))/(tb-ta)
         for ta, tb, qa, qb in zip(result['times'], result['times'][1:],
                                   result['q'], result['q'][1:]) if tb > ta),
        default=0.0)
    result.update(start_xyz_m=start, displacement_m=displacement,
                  displacement_norm_m=distance,
                  velocity_limit_rad_s=VELOCITY_LIMIT,
                  max_joint_velocity_rad_s=max_velocity,
                  acceleration_limit_rad_s2=ACCELERATION_LIMIT,
                  execution_allowed=(result['duration_s'] <= DURATION_LIMIT and
                                     max_velocity <= VELOCITY_LIMIT+1e-6))
    return result


def run(data, app):
    if not isinstance(data, dict):
        raise ValueError('请求必须为对象')
    stage = data.get('stage', 'preview')
    if stage not in ('preview', 'execute'):
        raise ValueError('stage 必须为 preview 或 execute')
    result = _plan(data, app)
    if stage == 'preview':
        result.update(ok=True, read_only=True, execution_enabled=False)
        return result, 200
    if not result['execution_allowed']:
        raise ValueError('轨迹超过 30 秒或 0.50 rad/s 执行上限，仅供预览，拒绝执行')
    body, code = app.SENDER.start_planned_test(data, result)
    if code == 200:
        body.update(collision_mode='exact',
                    mesh_distance_checks=result['mesh_distance_checks'],
                    minimum_mesh_clearance_cm=result['minimum_mesh_clearance_cm'],
                    start_xyz_m=result['start_xyz_m'], target_xyz_m=result['target_xyz_m'],
                    displacement_norm_m=result['displacement_norm_m'])
    return body, code

# -*- coding: utf-8 -*-
"""一次性左臂 J5 上升50mm、保持、原路下降；20% 限速，不开放通用执行。"""
import math
from pathlib import Path
import sys

TEST_CONFIRM = 'LEFT_ROUNDTRIP_50MM_20_PERCENT'
TEST_DISTANCE_M = 0.05
HOLD_S = 1.0


def _plan(app):
    ok, left_deg = app.left_read()
    other_ok, right_deg = app.right_read()
    if not ok or not other_ok:
        raise ValueError('无法读取双臂完整反馈')
    current = [math.radians(v) for v in app.angles(left_deg)]
    other = [math.radians(v) for v in app.angles(right_deg)]
    for packages in Path('/home/apex/vla_exact_venv/lib').glob('python*/site-packages'):
        if str(packages) not in sys.path:
            sys.path.insert(0, str(packages))
    import vla_motion_planner
    start = app._fk_points(current, 'left')[0][5]
    target = [start[0], start[1], start[2] + TEST_DISTANCE_M]
    result = vla_motion_planner.plan_j5_xyz(
        'left', target, current_q=current, other_arm_q={'right': other},
        collision_mode='exact')
    up_times = [value * 5.0 for value in result['times']]
    up_q = result['q']
    up_duration = up_times[-1]
    # 返程严格复用已逐点、逐段验证的轨迹，不在收拢限位附近另求新 IK。
    times = up_times + [up_duration + HOLD_S]
    points = up_q + [up_q[-1]]
    for index in range(len(up_times) - 2, -1, -1):
        times.append(up_duration + HOLD_S + up_duration - up_times[index])
        points.append(up_q[index])
    result['times'] = times
    result['q'] = points
    result['duration_s'] = times[-1]
    if result['duration_s'] > 15.0:
        raise ValueError('测试轨迹异常：20% 限速往返超过 15 秒')
    for ta, tb, qa, qb in zip(times, times[1:], points, points[1:]):
        if max(abs(a-b) for a, b in zip(qa, qb)) / (tb-ta) > 0.150001:
            raise ValueError('轨迹重定时校验失败：超过 0.15rad/s')
    result.update(start_xyz_m=start, apex_xyz_m=target, return_xyz_m=start,
                  displacement_m=[0.0, 0.0, TEST_DISTANCE_M], hold_s=HOLD_S,
                  velocity_limit_rad_s=0.15, acceleration_limit_rad_s2=0.4,
                  test_confirm=TEST_CONFIRM)
    return result


def run(data, app):
    if not isinstance(data, dict) or data.get('confirm') != TEST_CONFIRM:
        raise ValueError('必须提供一次性测试确认字段')
    stage = data.get('stage', 'preview')
    if stage not in ('preview', 'execute'):
        raise ValueError('stage 必须为 preview 或 execute')
    trajectory = _plan(app)
    if stage == 'preview':
        trajectory.update(ok=True, read_only=True, execution_enabled=False)
        return trajectory, 200
    body, code = app.SENDER.start_planned_test(data, trajectory)
    if code == 200:
        body.update(collision_mode='exact',
                    mesh_distance_checks=trajectory['mesh_distance_checks'],
                    minimum_mesh_clearance_cm=trajectory['minimum_mesh_clearance_cm'],
                    start_xyz_m=trajectory['start_xyz_m'], target_xyz_m=trajectory['target_xyz_m'])
    return body, code

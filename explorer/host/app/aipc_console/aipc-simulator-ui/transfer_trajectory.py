# -*- coding: utf-8 -*-
"""X／VLA 左臂搬运共用的任务空间路径与 TOPP-RA 时间参数化。

只在搬运段启动前规划，不影响 20 Hz VR 跟随。去程缓存几何路径，回程严格反向
复用；没有可用缓存时先按反方向构造去程再反转。规划在锁外执行，失败即拒绝运动。
"""
from __future__ import annotations

import math
import threading


def _activate_exact_environment():
    """在导入 exact_collision 前加载 AIPC 的 FCL 独立环境。"""
    import sys
    from pathlib import Path
    for packages in Path('/home/apex/vla_exact_venv/lib').glob('python*/site-packages'):
        if str(packages) not in sys.path:
            sys.path.insert(0, str(packages))
    local_offline = Path(__file__).resolve().parents[1] / '离线规划'
    if local_offline.is_dir() and str(local_offline) not in sys.path:
        sys.path.insert(0, str(local_offline))


VELOCITY_LIMIT = 0.80       # 恢复 KR260 原有限速：约 45.8°/s
ACCELERATION_LIMIT = 0.8 * (0.8 / 0.3)  # 相对上一验证版等比例放大：2.1333 rad/s²
PATH_SAMPLES = 161
OUTPUT_DT = 0.02            # AIPC 以 20 Hz 下发轨迹参考点
_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _user_position(app, q):
    return tuple(app._fk_points(q, 'left')[0][5])


def _user_rotation(app, q):
    return app._mm(app._FR, app._fk(q)[1])


def _joint_path(q0, q1):
    import numpy as np
    s = np.linspace(0.0, 1.0, PATH_SAMPLES)
    a, b = np.asarray(q0, dtype=float), np.asarray(q1, dtype=float)
    return a[None, :] + s[:, None] * (b-a)[None, :]


def _home_pos3_path(app, geometry, q0, q1):
    """离线评选的 projection_x100_z050：保留参考姿态/Y，修正全部 X 与一半 Z。"""
    import numpy as np
    a, b = np.asarray(q0, dtype=float), np.asarray(q1, dtype=float)
    grid = np.linspace(0.0, 1.0, 1001)
    reference_q = a[None, :] + grid[:, None] * (b-a)[None, :]
    reference_xyz = np.asarray([_user_position(app, q) for q in reference_q])
    p0, p1 = reference_xyz[0], reference_xyz[-1]
    result = []
    seed = tuple(q0)
    for index, s in enumerate(np.linspace(0.0, 1.0, PATH_SAMPLES)):
        reference = np.asarray([np.interp(s, grid, reference_xyz[:, axis]) for axis in range(3)])
        reference[0] += p0[0] + s*(p1[0]-p0[0]) - reference[0]
        reference[2] += 0.5*(p0[2] + s*(p1[2]-p0[2]) - reference[2])
        reference_q_at_s = a + s*(b-a)
        rotation = _user_rotation(app, reference_q_at_s)
        q, error = app.solve_layered_j5_pose_user(tuple(reference), rotation, seed, side='left')
        if q is None:
            raise ValueError(f'起始位—位置3路径第 {index} 点解析 IK 失败：{error}')
        if not all(app.JOINT_LO[j] <= q[j] <= app.JOINT_HI[j] for j in range(6)):
            raise ValueError(f'起始位—位置3路径第 {index} 点超过执行端关节限位')
        margin = geometry.pose_margin(q, 'left')[0]
        if margin < geometry.MIN_MARGIN_CM:
            raise ValueError(f'起始位—位置3路径第 {index} 点支架余量不足：{margin:.2f} cm')
        result.append(q)
        seed = tuple(q)
    result[0], result[-1] = list(q0), list(q1)
    return np.asarray(result)


def _validate_path(app, geometry, path):
    for index in range(len(path)-1):
        checked = geometry.check_path(path[index].tolist(), path[index+1].tolist(),
                                      'left', vmax=VELOCITY_LIMIT, dt=0.01, stride=1)
        if not checked['ok']:
            raise ValueError(f'规划路径第 {index} 段连续几何检查失败：{checked}')


def _parameterize(path):
    import numpy as np
    from toppra_retiming import parameterize
    path = np.asarray(path, dtype=float)
    scale = float(np.max(np.abs(np.diff(path, axis=0))))
    if scale < 1e-10:
        return np.asarray([0.0, OUTPUT_DT]), np.asarray([path[0], path[0]]), {'duration_s': OUTPUT_DT}
    if scale < 0.05:
        # 小位移 LP 会出现内部零速区间并退化出非物理的巨大时长。
        # 五次平滑仅用于小位移；时长按最大速度/加速度约束取保守上限。
        travel = float(np.max(np.abs(path[-1]-path[0])))
        duration = max(OUTPUT_DT, 1.875*travel/VELOCITY_LIMIT,
                       float(np.sqrt(5.773502691896258*travel/ACCELERATION_LIMIT)))
        times = np.arange(0.0, duration, OUTPUT_DT)
        if len(times) == 0 or times[-1] < duration-1e-10:
            times = np.concatenate((times, [duration]))
        u = np.clip(times/duration, 0.0, 1.0)
        smooth = 10*u**3-15*u**4+6*u**5
        q = path[0][None, :]+smooth[:, None]*(path[-1]-path[0])[None, :]
        return times, q, {'duration_s': duration, 'small_displacement_quintic': True}
    times, q, info = parameterize(path, VELOCITY_LIMIT, ACCELERATION_LIMIT, output_dt=OUTPUT_DT)
    return times, q, info


def _validate_vehicle(path, label):
    """搬运执行前强制检查支架、雷达底座和完整底盘网格。"""
    import sys
    from pathlib import Path
    for packages in Path('/home/apex/vla_exact_venv/lib').glob('python*/site-packages'):
        if str(packages) not in sys.path:
            sys.path.insert(0, str(packages))
    local_offline = Path(__file__).resolve().parents[1] / '离线规划'
    if local_offline.is_dir() and str(local_offline) not in sys.path:
        sys.path.insert(0, str(local_offline))
    from exact_collision import ExactMeshCollisionModel
    import arm_console as app
    collision = ExactMeshCollisionModel(other_arm_q={'right': app.Q_START_RIGHT})
    for index, row in enumerate(path):
        result = collision.pose(row, 'left')
        if not result.ok:
            raise ValueError(f'{label} 第 {index} 点整车碰撞预检失败：{result.reason}')
    return collision.minimum_clearance_cm


def _cached_home_pos3(app, q0, q1):
    """读取已全程离线验证的固定 X 路径；环境哈希或端点不符即回退在线规划。"""
    import hashlib
    from pathlib import Path
    import numpy as np
    if max(abs(a-b) for a, b in zip(q0, app.Q_START_LEFT)) > math.radians(1.5):
        return None
    if max(abs(a-b) for a, b in zip(q1, app.Q_LEFT_POS3)) > math.radians(0.01):
        return None
    local = Path(__file__).resolve().parents[1] / '离线规划'
    cache = Path('/home/apex/v3_x_home_pos3_cache.npz')
    environment = Path('/home/apex/环境网格/v3_vehicle_top_center_convex.npz')
    if not cache.is_file():
        cache = local / '输出/v3_x_home_pos3_cache.npz'
        environment = local / '环境网格/v3_vehicle_top_center_convex.npz'
    if not cache.is_file() or not environment.is_file():
        return None
    with np.load(cache) as data:
        if str(data['environment_sha256']) != hashlib.sha256(environment.read_bytes()).hexdigest():
            raise ValueError('固定 X 缓存与当前整车环境哈希不一致，已拒绝使用')
        times = np.asarray(data['times'], dtype=float)
        q = np.asarray(data['q'], dtype=float).copy()
        clearance = float(data['minimum_clearance_cm'])
    if (len(times) != len(q) or len(q) < 2 or q.shape[1] != 6 or
            not np.all(np.isfinite(times)) or not np.all(np.isfinite(q)) or
            not np.all(np.diff(times) > 0)):
        raise ValueError('固定 X 缓存结构无效')
    if not np.allclose(q[0], app.Q_START_LEFT, atol=1e-8) or not np.allclose(q[-1], app.Q_LEFT_POS3, atol=1e-8):
        raise ValueError('固定 X 缓存端点与当前标定不一致')
    if not np.all(q >= np.asarray(app.JOINT_LO)) or not np.all(q <= np.asarray(app.JOINT_HI)):
        raise ValueError('固定 X 缓存包含关节限位越界')
    # 只允许 1.5° 内的真实静态反馈偏差；新鲜反馈另行做精确整车检查。
    q[0] = q0
    _validate_vehicle([q0], '固定 X 缓存真实起点')
    return {'times': times.tolist(), 'q': q.tolist(), 'duration_s': float(times[-1]),
            'planner': '离线缓存 RRT-Connect＋TOPP-RA',
            'geometry': '最终 v3 整车精确碰撞（全程离线验证）',
            'vehicle_collision_scope': '支架＋雷达／底座＋完整底盘网格',
            'minimum_vehicle_clearance_cm': clearance,
            'velocity_limit_rad_s': VELOCITY_LIMIT, 'acceleration_limit_rad_s2': ACCELERATION_LIMIT,
            'forward_leg': 'home_pos3', 'persistent_cache': True}


def _build(app, geometry, current, target, forward_leg):
    _activate_exact_environment()
    import numpy as np
    q0 = np.asarray(current, dtype=float)
    q1 = np.asarray(target, dtype=float)
    if forward_leg == 'original_home':
        # 完整恢复接入整车网格前的第一版：不做 RRT 和整车 FCL 逐点复核。
        path = _joint_path(q0, q1)
        _validate_path(app, geometry, path)
        times, q, info = _parameterize(path)
        if not np.all(np.isfinite(q)):
            raise ValueError('TOPP-RA 输出包含非有限关节值')
        if not all(np.all(row >= np.asarray(app.JOINT_LO)) and np.all(row <= np.asarray(app.JOINT_HI))
                   for row in q):
            raise ValueError('TOPP-RA 时间采样后出现关节限位越界，已拒绝执行')
        for index, row in enumerate(q):
            margin = geometry.pose_margin(row.tolist(), 'left')[0]
            if margin < geometry.MIN_MARGIN_CM:
                raise ValueError(f'TOPP-RA 输出第 {index} 点支架余量不足：{margin:.2f} cm')
        return {
            'times': (times-times[0]).tolist(), 'q': q.tolist(),
            'duration_s': float(times[-1]-times[0]),
            'planner': '五次平滑（小位移）' if info.get('small_displacement_quintic') else 'TOPP-RA',
            'geometry': '六轴关节空间直线路径',
            'velocity_limit_rad_s': VELOCITY_LIMIT,
            'acceleration_limit_rad_s2': ACCELERATION_LIMIT,
            'forward_leg': forward_leg}
    elif forward_leg == 'home_pos3':
        cached = _cached_home_pos3(app, q0, q1)
        if cached is not None:
            return cached
        # 缓存缺失、标定或环境变化时回退最终 v3 环境的全程在线规划。
        import vla_motion_planner as vehicle_planner
        planned = vehicle_planner.plan_j5_xyz(
            'left', _user_position(app, q1), orientation=_user_rotation(app, q1),
            current_q=q0, other_arm_q={'right': app.Q_START_RIGHT}, collision_mode='exact')
        path = np.asarray(planned['q'])
        geometry_name = '完整整车精确碰撞＋RRT-Connect＋连续解析 IK'
    else:
        raise ValueError(f'未知搬运规划段：{forward_leg}')
    _validate_path(app, geometry, path)
    times, q, info = _parameterize(path)
    if not np.all(np.isfinite(q)):
        raise ValueError('TOPP-RA 输出包含非有限关节值')
    if not all(np.all(row >= np.asarray(app.JOINT_LO)) and np.all(row <= np.asarray(app.JOINT_HI))
               for row in q):
        raise ValueError('TOPP-RA 时间采样后出现关节限位越界，已拒绝执行')
    for index, row in enumerate(q):
        margin = geometry.pose_margin(row.tolist(), 'left')[0]
        if margin < geometry.MIN_MARGIN_CM:
            raise ValueError(f'TOPP-RA 输出第 {index} 点支架余量不足：{margin:.2f} cm')
    vehicle_clearance = _validate_vehicle(q, 'TOPP-RA 整车复核')
    return {
        'times': (times-times[0]).tolist(),
        'q': q.tolist(),
        'duration_s': float(times[-1]-times[0]),
        'planner': '五次平滑（小位移）' if info.get('small_displacement_quintic') else 'TOPP-RA',
        'geometry': geometry_name,
        'vehicle_collision_scope': '支架＋雷达／底座＋完整底盘网格',
        'minimum_vehicle_clearance_cm': vehicle_clearance,
        'velocity_limit_rad_s': VELOCITY_LIMIT,
        'acceleration_limit_rad_s2': ACCELERATION_LIMIT,
        'forward_leg': forward_leg,
    }


def _reverse(plan, current, target):
    q = list(reversed(plan['q']))
    # 使用本段启动时的真实反馈作为首点，消除静态偏置造成的微小跳变。
    q[0] = list(current)
    q[-1] = list(target)
    return dict(plan, q=q, reversed=True)


def plan(current, target, leg):
    """生成四段之一：original_home/home_pos3/pos3_home/home_original。"""
    import arm_console as app
    import arm_geometry as geometry

    forward = {'original_home': 'original_home', 'home_original': 'original_home',
               'home_pos3': 'home_pos3', 'pos3_home': 'home_pos3'}.get(leg)
    if forward is None:
        raise ValueError(f'未知搬运轨迹段：{leg}')
    reverse = leg in ('home_original', 'pos3_home')
    with _CACHE_LOCK:
        cached = _CACHE.get(forward)
    if reverse and cached is not None:
        # 缓存必须对应本次目标；否则重新规划，不能沿用上一次 X 的原位。
        expected_start = cached['q'][-1]
        if max(abs(a-b) for a, b in zip(expected_start, current)) <= math.radians(1.5):
            return _reverse(cached, current, target)

    if reverse:
        built = _build(app, geometry, target, current, forward)
        with _CACHE_LOCK:
            _CACHE[forward] = built
        return _reverse(built, current, target)
    built = _build(app, geometry, current, target, forward)
    with _CACHE_LOCK:
        _CACHE[forward] = built
    return built


def clear_cache():
    """仅用于离线测试或重新标定后显式失效；搬运中不得调用。"""
    with _CACHE_LOCK:
        _CACHE.clear()

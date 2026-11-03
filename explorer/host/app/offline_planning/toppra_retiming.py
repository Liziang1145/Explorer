# -*- coding: utf-8 -*-
"""TOPP-RA：基于可达性分析的固定路径时间最优参数化。

后向递推可控集 K_i，前向递推时间最优速度平方 x_i；每个阶段调用 LP。
实现速度/加速度约束，不包含 jerk 约束。
参考：Pham & Pham, IEEE Transactions on Robotics, 2018, DOI:10.1109/TRO.2018.2819195。
"""
from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import linprog


def _acceleration_rows(qs, qss, accel_limits):
    """q_s*u + q_ss*x <= a_max 的线性不等式行，变量顺序 [x,u,y]。"""
    rows = []
    for a, b, limit in zip(qs, qss, accel_limits):
        rows.append(([b, a, 0.0], limit))
        rows.append(([-b, -a, 0.0], limit))
    return rows


def _backward_stage(i, ds, qs, qss, speed_max, next_set, accel_limits):
    """对 x_i 分别求最小/最大值，变量 [x_i,u_i,x_{i+1}]。"""
    solutions = []
    rows = _acceleration_rows(qs, qss, accel_limits)
    a_ub = np.asarray([row for row, _ in rows])
    b_ub = np.asarray([bound for _, bound in rows])
    a_eq = np.asarray([[1.0, 2*ds, -1.0]])
    for sign in (1.0, -1.0):
        result = linprog(np.asarray([sign, 0.0, 0.0]), A_ub=a_ub, b_ub=b_ub,
                         A_eq=a_eq, b_eq=np.asarray([0.0]),
                         bounds=[(0.0, speed_max), (None, None), next_set], method='highs')
        if not result.success:
            raise RuntimeError(f'TOPP-RA 后向 LP 在索引 {i} 失败：{result.message}')
        solutions.append(float(result.x[0]))
    return solutions[0], solutions[1]


def _forward_stage(i, ds, qs, qss, x_i, speed_next, next_set, accel_limits):
    """固定 x_i，通过 LP 最大化下一阶段速度 x_{i+1}。"""
    rows = _acceleration_rows(qs, qss, accel_limits)
    # 当前变量仍是 [x,u,y]，x 用等式固定。
    a_ub = np.asarray([row for row, _ in rows])
    b_ub = np.asarray([bound for _, bound in rows])
    a_eq = np.asarray([[1.0, 0.0, 0.0], [1.0, 2*ds, -1.0]])
    b_eq = np.asarray([x_i, 0.0])
    upper_y = min(speed_next, next_set[1])
    result = linprog(np.asarray([0.0, 0.0, -1.0]), A_ub=a_ub, b_ub=b_ub,
                     A_eq=a_eq, b_eq=b_eq,
                     bounds=[(x_i, x_i), (None, None), (max(0.0, next_set[0]), upper_y)],
                     method='highs')
    if not result.success:
        raise RuntimeError(f'TOPP-RA 前向 LP 在索引 {i} 失败：{result.message}')
    return float(result.x[2])


def parameterize(path_q, velocity_limits, acceleration_limits, output_dt=0.001,
                 speed_scale=None):
    """返回 times, q, diagnostics；轨迹端点速度均为零。

    speed_scale 是路径采样点的局部速度比例，不改变原生 TOPP-RA 的 LP 形式。
    """
    path_q = np.asarray(path_q, dtype=float)
    count = len(path_q)
    s = np.linspace(0.0, 1.0, count)
    ds = s[1]-s[0]
    spline = CubicSpline(s, path_q, axis=0)
    qs, qss = spline(s, 1), spline(s, 2)
    joints = path_q.shape[1]
    velocity_limits = np.broadcast_to(np.asarray(velocity_limits, dtype=float), (joints,))
    acceleration_limits = np.broadcast_to(np.asarray(acceleration_limits, dtype=float), (joints,))
    if speed_scale is None:
        speed_scale = np.ones(count)
    speed_scale = np.asarray(speed_scale, dtype=float)
    if speed_scale.shape != (count,) or not np.all(np.isfinite(speed_scale)) \
            or np.any(speed_scale <= 0.0) or np.any(speed_scale > 1.0):
        raise ValueError('speed_scale 必须是每个路径采样点对应的 (0, 1] 有限数')
    with np.errstate(divide='ignore', invalid='ignore'):
        speed_ceiling = np.min((velocity_limits[None, :]/np.abs(qs))**2, axis=1)
    speed_ceiling[~np.isfinite(speed_ceiling)] = 1e12
    speed_ceiling *= speed_scale**2

    controllable = np.full((count, 2), np.nan)
    controllable[-1] = (0.0, 0.0)
    for i in range(count-2, -1, -1):
        controllable[i] = _backward_stage(i, ds, qs[i], qss[i], speed_ceiling[i],
                                          controllable[i+1], acceleration_limits)

    profile = np.full(count, np.nan)
    profile[0] = 0.0
    for i in range(count-1):
        profile[i+1] = _forward_stage(i, ds, qs[i], qss[i], profile[i], speed_ceiling[i+1],
                                      controllable[i+1], acceleration_limits)
    profile[-1] = 0.0

    roots = np.sqrt(np.maximum(profile, 0.0))
    segment_dt = 2*ds / np.maximum(roots[:-1]+roots[1:], 1e-12)
    if not np.all(np.isfinite(segment_dt)):
        raise RuntimeError('TOPP-RA 速度剖面包含无法通过的零速区间')
    path_times = np.concatenate(([0.0], np.cumsum(segment_dt)))
    duration = float(path_times[-1])
    times = np.arange(0.0, duration, output_dt)
    if len(times) == 0 or times[-1] < duration-1e-10:
        times = np.concatenate((times, [duration]))
    segment = np.clip(np.searchsorted(path_times, times, side='right')-1, 0, count-2)
    path_acceleration = (profile[segment+1]-profile[segment])/(2*ds)
    tau = times-path_times[segment]
    # 段内 sddot 恒定，使用精确积分而非时间线性插值。
    sample_s = s[segment] + roots[segment]*tau + 0.5*path_acceleration*tau*tau
    sample_s[-1] = 1.0
    q = spline(sample_s)
    q[0], q[-1] = path_q[0], path_q[-1]
    squared_speed = np.maximum(0.0, profile[segment]+2*path_acceleration*(sample_s-s[segment]))
    analytic_velocity = spline(sample_s, 1)*np.sqrt(squared_speed)[:, None]
    analytic_acceleration = (spline(sample_s, 2)*squared_speed[:, None]
                             + spline(sample_s, 1)*path_acceleration[:, None])
    diagnostics = {
        'duration_s': duration, 'path_samples': count, 'backward_lp_count': 2*(count-1),
        'forward_lp_count': count-1, 'path_times': path_times, 's': s,
        'squared_speed': profile, 'controllable_sets': controllable,
        'speed_ceiling': speed_ceiling, 'analytic_velocity': analytic_velocity,
        'analytic_acceleration': analytic_acceleration,
        'analytic_max_speed_rad_s': float(np.max(np.abs(analytic_velocity))),
        'analytic_max_acceleration_rad_s2': float(np.max(np.abs(analytic_acceleration))),
    }
    return times, q, diagnostics

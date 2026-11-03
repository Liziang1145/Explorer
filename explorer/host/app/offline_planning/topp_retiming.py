# -*- coding: utf-8 -*-
"""数值前向–后向 TOPP：固定关节路径的速度/加速度约束时间参数化。

方法对应 Bobrow 等经典相平面思想和 Pham & Pham 的可达性分析框架。
本模块不宣称实现三阶 jerk 约束；jerk 仅作为输出指标另行计算。
"""
from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline


def _bounds(qs: np.ndarray, qss: np.ndarray, x: float, accel: np.ndarray):
    lo, hi = -np.inf, np.inf
    for a, b, limit in zip(qs, qss, accel):
        curvature = b*x
        if abs(a) < 1e-12:
            if abs(curvature) > limit + 1e-9:
                return None
            continue
        bound1, bound2 = (-limit-curvature)/a, (limit-curvature)/a
        lo, hi = max(lo, min(bound1, bound2)), min(hi, max(bound1, bound2))
    if lo > hi + 1e-9:
        return None
    return lo, hi


def parameterize(path_q: np.ndarray, velocity_limits, acceleration_limits,
                 output_dt=0.01):
    """返回 (times, q, path_times, s_grid, squared_speed_profile)。"""
    path_q = np.asarray(path_q, dtype=float)
    count = len(path_q)
    s = np.linspace(0.0, 1.0, count)
    spline = CubicSpline(s, path_q, axis=0)
    ds = s[1]-s[0]
    qs = spline(s, 1)
    qss = spline(s, 2)
    velocity_limits = np.broadcast_to(np.asarray(velocity_limits, dtype=float), (6,))
    acceleration_limits = np.broadcast_to(np.asarray(acceleration_limits, dtype=float), (6,))
    with np.errstate(divide='ignore', invalid='ignore'):
        speed_ceiling = np.min((velocity_limits[None, :]/np.abs(qs))**2, axis=1)
    speed_ceiling[~np.isfinite(speed_ceiling)] = 1e12

    # 后向可达剖面：从终点零速，以最负可行加速度反向传播。
    backward = np.full(count, np.nan)
    backward[-1] = 0.0
    for i in range(count-2, -1, -1):
        bounds = _bounds(qs[i], qss[i], min(backward[i+1], speed_ceiling[i]), acceleration_limits)
        if bounds is None:
            raise RuntimeError(f'TOPP 后向传播在路径索引 {i} 不可行')
        backward[i] = max(0.0, min(speed_ceiling[i], backward[i+1]-2*ds*bounds[0]))

    # 前向最大加速，遇到后向剖面后切换为制动分支。
    forward = np.full(count, np.nan)
    forward[0] = 0.0
    switch = count-1
    for i in range(count-1):
        bounds = _bounds(qs[i], qss[i], forward[i], acceleration_limits)
        if bounds is None:
            raise RuntimeError(f'TOPP 前向传播在路径索引 {i} 不可行')
        nxt = forward[i] + 2*ds*bounds[1]
        if nxt >= backward[i+1]:
            switch = i
            break
        forward[i+1] = max(0.0, min(speed_ceiling[i+1], nxt))
    profile = backward.copy()
    for i in range(switch+1):
        if np.isfinite(forward[i]):
            profile[i] = min(backward[i], forward[i])
    profile = np.maximum(profile, 0.0)
    profile[0] = profile[-1] = 0.0

    roots = np.sqrt(profile)
    segment_dt = 2*ds / np.maximum(roots[:-1]+roots[1:], 1e-12)
    if not np.all(np.isfinite(segment_dt)):
        raise RuntimeError('TOPP 路径中出现无法通过的连续零速区间')
    path_times = np.concatenate(([0.0], np.cumsum(segment_dt)))
    duration = path_times[-1]
    times = np.arange(0.0, duration, output_dt)
    times = np.concatenate((times, [duration])) if times[-1] < duration-1e-10 else times
    sample_s = np.interp(times, path_times, s)
    q = spline(sample_s)
    q[0], q[-1] = path_q[0], path_q[-1]
    return times, q, path_times, s, profile

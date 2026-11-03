# -*- coding: utf-8 -*-
"""固定几何轨迹的局部时间重参数化；仅处理离线数组。"""
from __future__ import annotations

import numpy as np


def dynamics(q: np.ndarray, h: np.ndarray):
    velocity = np.diff(q, axis=0) / h[:, None]
    acceleration = np.diff(velocity, axis=0) / h[:-1, None]
    jerk = np.diff(acceleration, axis=0) / h[:-2, None]
    return velocity, acceleration, jerk


def peaks(q: np.ndarray, h: np.ndarray):
    velocity, acceleration, jerk = dynamics(q, h)
    return (float(np.max(np.abs(velocity))),
            float(np.max(np.abs(acceleration))),
            float(np.max(np.abs(jerk))))


def _repair(q: np.ndarray, proposed: np.ndarray, limits, max_steps=100):
    """只在违反约束的时间区间及其邻域增加时长。"""
    h = proposed.copy()
    speed_limit, accel_limit, jerk_limit = limits
    for _ in range(max_steps):
        velocity, acceleration, jerk = dynamics(q, h)
        speed_ratio = np.max(np.abs(velocity), axis=1) / speed_limit
        accel_ratio = np.max(np.abs(acceleration), axis=1) / accel_limit
        jerk_ratio = np.max(np.abs(jerk), axis=1) / jerk_limit
        if max(speed_ratio.max(), accel_ratio.max(), jerk_ratio.max()) <= 1.00001:
            return h, True
        # 留 0.1% 数值余量，避免浮点误差造成边界反复。
        h *= np.maximum(1.0, speed_ratio * 1.001)
        factor = np.sqrt(np.maximum(1.0, accel_ratio * 1.001))
        h[:-1] *= factor
        h[1:] *= factor
        factor = np.cbrt(np.maximum(1.0, jerk_ratio * 1.001))
        h[:-2] *= factor
        h[1:-1] *= factor
        h[2:] *= factor
    return h, False


def retime(q: np.ndarray, times: np.ndarray, speed_limit=0.75,
           accel_limit=2.0, jerk_limit=12.0, compression=0.985,
           max_iterations=600):
    """在固定 q 序列上压缩非敏感区间，返回最短的完全可行时间序列。

    每一轮先全局小幅压缩，再仅修复超限区间；只有全部约束通过的解才更新最优值。
    """
    q = np.asarray(q, dtype=float)
    initial_h = np.diff(np.asarray(times, dtype=float))
    limits = (speed_limit, accel_limit, jerk_limit)
    best_h, ok = _repair(q, initial_h, limits)
    if not ok:
        raise RuntimeError('初始时间序列无法修复到规划约束内')
    h = best_h.copy()
    for _ in range(max_iterations):
        candidate, ok = _repair(q, h * compression, limits)
        if ok and candidate.sum() < best_h.sum() - 1e-9:
            best_h = candidate.copy()
        h = candidate
    best_times = np.concatenate(([0.0], np.cumsum(best_h)))
    return best_times, peaks(q, best_h)

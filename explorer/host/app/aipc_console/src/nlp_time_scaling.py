# -*- coding: utf-8 -*-
"""直接时间离散的非线性轨迹重定时：最短总时长 + 速度/加速度/jerk 约束。"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize


def derivatives(q, h):
    velocity = np.diff(q, axis=0) / h[:, None]
    acceleration = np.diff(velocity, axis=0) / h[:-1, None]
    jerk = np.diff(acceleration, axis=0) / h[:-2, None]
    return velocity, acceleration, jerk


def optimize(q, initial_times, speed_limit=.75, accel_limit=2.0, jerk_limit=12.0,
             max_iterations=250):
    q = np.asarray(q, dtype=float)
    h0 = np.diff(initial_times)
    n = len(h0)

    def objective(y):
        return float(np.sum(h0*y))

    def jacobian(y):
        return h0

    def constraints(y):
        v, a, j = derivatives(q, h0*y)
        return np.concatenate((1-(v*v).ravel()/speed_limit**2,
                               1-(a*a).ravel()/accel_limit**2,
                               1-(j*j).ravel()/jerk_limit**2))

    result = minimize(objective, np.ones(n), jac=jacobian, method='SLSQP',
                      bounds=[(0.02, 5.0)]*n,
                      constraints=[{'type': 'ineq', 'fun': constraints}],
                      options={'maxiter': max_iterations, 'ftol': 1e-9, 'disp': False})
    h = h0*result.x
    times = np.concatenate(([0.0], np.cumsum(h)))
    v, a, j = derivatives(q, h)
    report = {
        'success': bool(result.success), 'message': str(result.message),
        'iterations': int(result.nit), 'duration_s': float(times[-1]),
        'max_speed_rad_s': float(np.max(np.abs(v))),
        'max_acceleration_rad_s2': float(np.max(np.abs(a))),
        'max_jerk_rad_s3': float(np.max(np.abs(j))),
        'min_constraint_margin': float(constraints(result.x).min()),
    }
    return times, report

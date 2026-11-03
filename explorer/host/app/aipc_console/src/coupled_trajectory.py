# -*- coding: utf-8 -*-
"""双臂耦合、J5 平移奇异感知与冲击受限的离线轨迹规划器。

边界：
- 双臂耦合采用联合位形逐点复核；同时运动冲突时退化为左臂优先的顺序协调，
  不是十二维最优联合 RRT，也不保证全局最短路径。
- 奇异指标采用 J5 平移雅可比最小奇异值，不能代替完整六维腕部奇异分析。
- jerk 通过本地 Ruckig 多关节同步分段轨迹约束，不是原生 TOPP-RA 的 LP 约束；
  不使用 Ruckig 的云端中间路径点接口，最终输出仍需重新做联合碰撞复核。
- 离线模块，不连接设备；跟踪误差必须用实机反馈另行测量。
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import CubicSpline

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APP = ROOT / 'aipc-simulator-ui'
for directory in (APP, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import arm_console as app
import arm_geometry as geometry
from toppra_retiming import parameterize
from vla_motion_planner import StaticCollisionModel, RRTConnect, shortcut, resample


def j5_translation_jacobian(q, epsilon=1e-5):
    """J5 平移雅可比（3×6），中央差分；side 的固定基座平移不影响结果。"""
    q = np.asarray(q, dtype=float)
    if q.shape != (6,) or not np.all(np.isfinite(q)):
        raise ValueError('q 必须为有限六轴向量')
    jacobian = np.empty((3, 6))
    for joint in range(6):
        delta = np.zeros(6)
        delta[joint] = epsilon
        plus = np.asarray(geometry.fk_chain(q+delta)[5])
        minus = np.asarray(geometry.fk_chain(q-delta)[5])
        jacobian[:, joint] = (plus-minus)/(2*epsilon)
    return jacobian


def singularity_metrics(q):
    """返回 J5 平移最小奇异值与可操作度，单位分别为 m 和 m³。"""
    singular_values = np.linalg.svd(j5_translation_jacobian(q), compute_uv=False)
    return {'min_singular_value': float(singular_values[-1]),
            'manipulability': float(np.prod(singular_values))}


def singularity_speed_scale(q, sigma_floor=0.035, min_scale=0.25):
    """奇异区域平滑限速；远离阈值时比例连续恢复到 1。"""
    if not 0 < min_scale <= 1 or not math.isfinite(sigma_floor) or sigma_floor <= 0:
        raise ValueError('奇异限速参数无效')
    sigma = singularity_metrics(q)['min_singular_value']
    ratio = min(1.0, sigma/sigma_floor)
    return float(min_scale+(1.0-min_scale)*ratio*ratio)


class DualArmCoupling:
    """以联合位形 (q_left, q_right) 检查动态另一臂及各自环境。"""

    def __init__(self, collision_factory=StaticCollisionModel):
        self.collision_factory = collision_factory
        self._models = {}
        self.pose_checks = 0
        self.minimum_margin_cm = math.inf

    def _model(self, moving_side, other_q):
        # 每次另一臂位形变化都更新固定臂缓存；粗模型开销小，精确模型工厂也可复用接口。
        model = self.collision_factory(other_arm_q={
            'right' if moving_side == 'left' else 'left': np.asarray(other_q, dtype=float)})
        return model

    def pose(self, left_q, right_q):
        self.pose_checks += 1
        left = self._model('left', right_q).pose(left_q, 'left')
        right = self._model('right', left_q).pose(right_q, 'right')
        margin = min(left.margin_cm, right.margin_cm)
        self.minimum_margin_cm = min(self.minimum_margin_cm, margin)
        if not left.ok:
            return False, '左臂：'+left.reason, margin
        if not right.ok:
            return False, '右臂：'+right.reason, margin
        return True, '双臂联合位形检查通过', margin

    def path(self, combined_path, label='联合轨迹'):
        for index, row in enumerate(combined_path):
            ok, reason, _margin = self.pose(row[:6], row[6:])
            if not ok:
                raise ValueError(f'{label} 第 {index} 点失败：{reason}')
        return True


def _uniform_path(path, samples):
    path = np.asarray(path, dtype=float)
    grid = np.linspace(0.0, 1.0, len(path))
    target = np.linspace(0.0, 1.0, samples)
    return np.asarray([np.interp(target, grid, path[:, joint])
                       for joint in range(path.shape[1])]).T


def coordinate_paths(left_path, right_path, coupling, samples=81,
                     allow_simultaneous=True):
    """生成 12 维协调路径；冲突时左臂先走、右臂后走，两臂均含等待段。"""
    left = _uniform_path(left_path, samples)
    right = _uniform_path(right_path, samples)
    simultaneous = np.hstack((left, right))
    if allow_simultaneous:
        try:
            coupling.path(simultaneous, '同时运动候选')
            return simultaneous, {'mode': 'simultaneous_validated', 'wait_segments': 0}
        except ValueError:
            pass
    # 顺序协调：每一时刻仍做联合检查，不能因另一臂等待而省略检查。
    left_then_hold = np.hstack((left, np.repeat(right[:1], samples, axis=0)))
    hold_then_right = np.hstack((np.repeat(left[-1:], samples, axis=0), right))
    coordinated = np.vstack((left_then_hold, hold_then_right[1:]))
    coupling.path(coordinated, '左臂优先顺序协调')
    return coordinated, {'mode': 'left_then_right', 'wait_segments': 2}


def _search_path(side, start, goal, other_q, collision_factory, seed):
    collision = collision_factory(other_arm_q={
        'right' if side == 'left' else 'left': np.asarray(other_q, dtype=float)})
    for label, q in (('起点', start), ('终点', goal)):
        result = collision.pose(q, side)
        if not result.ok:
            raise ValueError(f'{side} {label}无效：{result.reason}')
    path, search = RRTConnect(collision, side, seed=seed).solve(start, goal)
    if not search['direct']:
        path = shortcut(path, collision, side, np.random.default_rng(seed+1))
    return resample(path), search


def limit_jerk(times, q, jerk_limit=20.0, output_dt=0.02, max_passes=12):
    """本地多关节同步分段轨迹；中间路径点不刹停，不调用云端接口。"""
    times = np.asarray(times, dtype=float)
    q = np.asarray(q, dtype=float)
    if len(times) != len(q) or len(times) < 4 or np.any(np.diff(times) <= 0):
        raise ValueError('轨迹时间和采样结构无效')
    if not math.isfinite(jerk_limit) or jerk_limit <= 0:
        raise ValueError('jerk_limit 必须为有限正数')
    sys.path.insert(0, str(HERE/'.deps'))
    from ruckig import Ruckig, InputParameter, OutputParameter, Result
    original = trajectory_metrics(times-times[0], q)
    dofs = q.shape[1]
    velocity = max(original['max_velocity_rad_s'], 1e-4)
    acceleration = max(original['max_acceleration_rad_s2'], 1e-4)
    # 直线路径不做无意义分段；非直线路径保留几何转折点。
    delta = q[-1]-q[0]
    denominator = float(np.dot(delta, delta))
    if denominator > 1e-16:
        u = np.clip(((q-q[0])@delta)/denominator, 0.0, 1.0)
        deviation = np.max(np.linalg.norm(q-(q[0]+u[:, None]*delta), axis=1))
    else:
        deviation = 0.0
    if deviation < 1e-6:
        indices = [0, len(q)-1]
    else:
        stride = max(1, (len(q)-1)//24)
        indices = sorted(set(list(range(0, len(q)-1, stride))+[len(q)-1]))
    all_times, all_q = [], []
    current_q = q[0].copy()
    current_v = np.zeros(dofs)
    current_a = np.zeros(dofs)
    elapsed = 0.0
    for segment, (a, b) in enumerate(zip(indices, indices[1:])):
        otg = Ruckig(dofs, output_dt)
        inp = InputParameter(dofs)
        inp.current_position = current_q.tolist()
        inp.current_velocity = current_v.tolist()
        inp.current_acceleration = current_a.tolist()
        inp.target_position = q[b].tolist()
        if b == indices[-1]:
            target_v = np.zeros(dofs)
        else:
            nxt = indices[indices.index(b)+1]
            direction = q[nxt]-q[b]
            scale = float(np.max(np.abs(direction)))
            target_v = 0.25*velocity*direction/max(scale, 1e-9)
        inp.target_velocity = target_v.tolist()
        inp.target_acceleration = np.zeros(dofs).tolist()
        inp.max_velocity = np.full(dofs, velocity).tolist()
        inp.max_acceleration = np.full(dofs, acceleration).tolist()
        inp.max_jerk = np.full(dofs, 0.92*jerk_limit).tolist()
        out = OutputParameter(dofs)
        result = Result.Working
        first = True
        while result == Result.Working:
            result = otg.update(inp, out)
            if result != Result.Working and result != Result.Finished:
                raise RuntimeError(f'Ruckig 第 {segment} 段失败：{result}')
            if not first:
                all_times.append(elapsed+float(out.time))
                all_q.append(np.asarray(out.new_position))
            first = False
            out.pass_to_input(inp)
        elapsed += float(out.time)
        current_q = np.asarray(out.new_position)
        current_v = np.asarray(out.new_velocity)
        current_a = np.asarray(out.new_acceleration)
    result_times = np.asarray([0.0]+all_times)
    result_q = np.asarray([q[0]]+all_q)
    result_q[-1] = q[-1]
    metrics = trajectory_metrics(result_times, result_q)
    if metrics['max_jerk_rad_s3'] > jerk_limit*1.05:
        raise RuntimeError('Ruckig 输出的数值 jerk 超过 5% 采样容差')
    return result_times, result_q, {
        'jerk_limited': True, 'method': 'local_ruckig_synchronized_segments',
        'cloud_api': False, 'segments': len(indices)-1,
        'duration_s': float(result_times[-1]),
        'max_jerk_rad_s3': metrics['max_jerk_rad_s3']}


def trajectory_metrics(times, q):
    times, q = np.asarray(times, dtype=float), np.asarray(q, dtype=float)
    velocity = np.gradient(q, times, axis=0, edge_order=2)
    acceleration = np.gradient(velocity, times, axis=0, edge_order=2)
    jerk = np.gradient(acceleration, times, axis=0, edge_order=2)
    return {'duration_s': float(times[-1]-times[0]),
            'max_velocity_rad_s': float(np.max(np.abs(velocity))),
            'max_acceleration_rad_s2': float(np.max(np.abs(acceleration))),
            'max_jerk_rad_s3': float(np.max(np.abs(jerk))),
            'rms_jerk_rad_s3': float(np.sqrt(np.mean(jerk**2)))}


def plan_dual_arm(start_left, goal_left, start_right, goal_right,
                  collision_factory=StaticCollisionModel, velocity_limit=0.8,
                  acceleration_limit=2.1333333333333333, jerk_limit=20.0,
                  sigma_floor=0.035, min_singularity_scale=0.25,
                  output_dt=0.02, coordination_samples=61,
                  allow_simultaneous=True, seed=7):
    """生成同一路径上的原生 TOPP-RA 基线和增强轨迹，确保对照公平。"""
    vectors = [np.asarray(value, dtype=float) for value in
               (start_left, goal_left, start_right, goal_right)]
    if any(value.shape != (6,) or not np.all(np.isfinite(value)) for value in vectors):
        raise ValueError('双臂起终点必须是四个有限六轴向量')
    start_left, goal_left, start_right, goal_right = vectors
    coupling = DualArmCoupling(collision_factory)
    coupling.pose(start_left, start_right)
    coupling.pose(goal_left, goal_right)
    left_path, left_search = _search_path(
        'left', start_left, goal_left, start_right, collision_factory, seed)
    # 顺序协调时右臂看到的是左臂终点，必须据此规划，不能仍按左臂起点。
    right_reference = goal_left
    right_path, right_search = _search_path(
        'right', start_right, goal_right, right_reference, collision_factory, seed+10)
    combined, coordination = coordinate_paths(
        left_path, right_path, coupling, samples=coordination_samples,
        allow_simultaneous=allow_simultaneous)
    limits = np.full(12, float(velocity_limit))
    accel = np.full(12, float(acceleration_limit))
    baseline_t, baseline_q, baseline_info = parameterize(
        combined, limits, accel, output_dt=output_dt)
    scales = np.asarray([min(singularity_speed_scale(row[:6], sigma_floor, min_singularity_scale),
                             singularity_speed_scale(row[6:], sigma_floor, min_singularity_scale))
                         for row in combined])
    enhanced_t, enhanced_q, enhanced_info = parameterize(
        combined, limits, accel, output_dt=output_dt, speed_scale=scales)
    enhanced_t, enhanced_q, jerk_info = limit_jerk(
        enhanced_t, enhanced_q, jerk_limit=jerk_limit, output_dt=output_dt)
    coupling.path(baseline_q, '原生 TOPP-RA 输出')
    coupling.path(enhanced_q, '增强轨迹输出')
    sigma = [min(singularity_metrics(row[:6])['min_singular_value'],
                 singularity_metrics(row[6:])['min_singular_value']) for row in combined]
    return {
        'baseline': {'times': baseline_t.tolist(), 'q': baseline_q.tolist(),
                     'metrics': trajectory_metrics(baseline_t, baseline_q),
                     'planner': 'coupled path + native TOPP-RA'},
        'enhanced': {'times': enhanced_t.tolist(), 'q': enhanced_q.tolist(),
                     'metrics': trajectory_metrics(enhanced_t, enhanced_q),
                     'planner': 'coupled path + singularity-aware TOPP-RA + jerk retiming'},
        'coordination': coordination,
        'search': {'left': left_search, 'right': right_search},
        'constraints': {'velocity_limit_rad_s': velocity_limit,
                        'acceleration_limit_rad_s2': acceleration_limit,
                        'jerk_limit_rad_s3': jerk_limit,
                        'sigma_floor_m': sigma_floor,
                        'minimum_path_sigma_m': float(min(sigma)),
                        'minimum_speed_scale': float(np.min(scales))},
        'collision': {'pose_checks': coupling.pose_checks,
                      'minimum_margin_cm': coupling.minimum_margin_cm,
                      'model': collision_factory.__name__},
        'scope': '离线联合位形检查；J5 平移奇异；数值 jerk；不含实机跟踪误差结论',
        'toppra': {'baseline_duration_s': baseline_info['duration_s'],
                   'enhanced_before_jerk_s': enhanced_info['duration_s'],
                   'jerk_retiming': jerk_info},
    }

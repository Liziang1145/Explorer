# -*- coding: utf-8 -*-
"""X 左臂搬运：任务空间路径 + 连续解析 IK 的离线规划与评估。

只读取 aipc-simulator-ui 中的运动学、限位和几何模型；不连接硬件、不修改在线控制。
运行：python transfer_path_planner.py --output-dir ./输出
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

WORKSPACE = Path(__file__).resolve().parents[1]
APP_DIR = WORKSPACE / 'aipc-simulator-ui'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import arm_console as app  # noqa: E402
import arm_geometry as geometry  # noqa: E402
from nlp_time_scaling import optimize as optimize_time  # noqa: E402

Vec3 = tuple[float, float, float]
PathFunction = Callable[[float], Vec3]


@dataclass(frozen=True)
class Candidate:
    name: str
    family: str
    description: str
    path: PathFunction
    orientation_law: str = 'minimum_jerk'


@dataclass
class Evaluation:
    candidate: Candidate
    feasible: bool
    reason: str
    q: np.ndarray | None = None
    xyz: np.ndarray | None = None
    margins: np.ndarray | None = None
    metrics: dict | None = None
    times: np.ndarray | None = None
    duration_s: float | None = None


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def smooth5(s):
    """五次 minimum-jerk 标量规律：端点一阶、二阶导数均为零；兼容数组。"""
    s = np.clip(s, 0.0, 1.0)
    return s ** 3 * (10.0 - 15.0 * s + 6.0 * s * s)


def user_position(q: Sequence[float]) -> Vec3:
    return tuple(app._fk_points(q, 'left')[0][5])


def user_rotation(q: Sequence[float]):
    return app._mm(app._FR, app._fk(q)[1])


def orientation_error_deg(ra, rb) -> float:
    return math.degrees(math.sqrt(sum(v * v for v in app._rot_err(app._mm(rb, app._mt(ra))))))


def make_candidates(p0: Vec3, p1: Vec3) -> list[Candidate]:
    """构造显式候选族；所有候选均严格锚定实测两端点。"""
    a, b = np.asarray(p0), np.asarray(p1)
    chord = b - a
    horizontal = np.array((chord[0], chord[1]))
    normal = np.array((-horizontal[1], horizontal[0]))
    normal /= max(np.linalg.norm(normal), 1e-12)
    midpoint = (a + b) * 0.5
    candidates = [Candidate(
        'cartesian_linear', '直线', 'J5 直线，Z 线性下降，姿态 SO(3) 同步插值',
        lambda s: tuple(a + clamp(s) * chord))]

    # 二次 Bezier：中间控制点只改变水平绕行形状，高度规律独立、可审计。
    for offset_cm in (5.0, 10.0, 15.0, 20.0):
        # 起点在左前方、终点在左后方；向 -normal 一侧绕行，避免从底座附近穿过。
        control = midpoint.copy()
        control[:2] -= normal * (offset_cm / 100.0)
        for height_mode in ('linear', 'hold_then_drop'):
            def bezier(s, c=control.copy(), mode=height_mode):
                s = clamp(s)
                xy = (1-s)**2 * a[:2] + 2*(1-s)*s*c[:2] + s*s*b[:2]
                if mode == 'linear':
                    z = a[2] + s * chord[2]
                else:
                    z = a[2] + smooth5((s - 0.35) / 0.65) * chord[2]
                return (float(xy[0]), float(xy[1]), float(z))
            candidates.append(Candidate(
                f'bezier_out_{int(offset_cm):02d}cm_{height_mode}', '中间点曲线',
                f'二次 Bezier，水平外绕 {offset_cm:.0f} cm，高度={height_mode}', bezier))

    # 圆柱坐标短圆弧：XY 半径平滑过渡，选取角度差不超过 pi 的方向。
    theta0 = math.atan2(a[1], a[0])
    theta1 = theta0 + math.atan2(math.sin(math.atan2(b[1], b[0]) - theta0),
                                 math.cos(math.atan2(b[1], b[0]) - theta0))
    r0, r1 = np.linalg.norm(a[:2]), np.linalg.norm(b[:2])
    for radius_scale in (1.0, 1.15):
        for height_mode in ('linear', 'hold_then_drop'):
            def arc(s, scale=radius_scale, mode=height_mode):
                s = clamp(s)
                theta = theta0 + (theta1 - theta0) * s
                radius = (r0 + (r1-r0)*s) * (1.0 + (scale-1.0)*4.0*s*(1.0-s))
                if mode == 'linear':
                    z = a[2] + s * chord[2]
                else:
                    z = a[2] + smooth5((s - 0.35) / 0.65) * chord[2]
                return (float(radius*math.cos(theta)), float(radius*math.sin(theta)), float(z))
            candidates.append(Candidate(
                f'arc_short_r{int(radius_scale*100):03d}_{height_mode}', '绕基座弧线',
                f'圆柱短圆弧，中部半径系数={radius_scale:.2f}，高度={height_mode}', arc))
    # 姿态进程是独立决策变量：线性进程可抵消腰转造成的腕角增长；
    # 最终时间轴仍统一采用 minimum-jerk，不在线切换或放宽限位。
    expanded = []
    for item in candidates:
        for law in ('minimum_jerk', 'linear', 'sqrt', 'early'):
            expanded.append(Candidate(
                f'{item.name}_ori_{law}', item.family,
                f'{item.description}，姿态进程={law}', item.path, law))
    return expanded


def make_reference_projection_candidates(q0: Sequence[float], q1: Sequence[float]) -> list[Candidate]:
    """以关节参考轨迹的姿态/Y 为先验，在任务空间投影修正 X/Z。

    这是独立候选族而非失败后的降级：参考轨迹、投影权重和姿态来源全部显式记录。
    """
    grid = np.linspace(0.0, 1.0, 1001)
    reference_q = np.asarray(q0)[None, :] + grid[:, None] * (np.asarray(q1)-np.asarray(q0))[None, :]
    reference_xyz = np.asarray([user_position(q) for q in reference_q])
    candidates = []
    p0, p1 = user_position(q0), user_position(q1)
    for x_weight in (0.25, 0.5, 0.75, 1.0):
        for z_weight in (0.0, 0.5, 1.0):
            def projected(s, xw=x_weight, zw=z_weight):
                reference = np.asarray([np.interp(s, grid, reference_xyz[:, axis]) for axis in range(3)])
                reference[0] += xw * (p0[0] + s*(p1[0]-p0[0]) - reference[0])
                reference[2] += zw * (p0[2] + s*(p1[2]-p0[2]) - reference[2])
                return tuple(reference)
            candidates.append(Candidate(
                f'projection_x{int(x_weight*100):03d}_z{int(z_weight*100):03d}',
                '任务空间投影', f'参考姿态/Y，X 修正权重={x_weight:.2f}，Z 修正权重={z_weight:.2f}',
                projected, 'reference'))
    return candidates


def solve_candidate(candidate: Candidate, q0: Sequence[float], q1: Sequence[float],
                    samples: int = 161) -> Evaluation:
    ss = np.linspace(0.0, 1.0, samples)
    r0, r1 = user_rotation(q0), user_rotation(q1)
    qs, points, margins = [], [], []
    seed = tuple(q0)
    for index, s in enumerate(ss):
        p = candidate.path(float(s))
        if candidate.orientation_law == 'reference':
            reference_q = np.asarray(q0) + float(s) * (np.asarray(q1)-np.asarray(q0))
            rotation = user_rotation(reference_q)
        else:
            if candidate.orientation_law == 'minimum_jerk':
                orientation_s = smooth5(float(s))
            elif candidate.orientation_law == 'linear':
                orientation_s = float(s)
            elif candidate.orientation_law == 'sqrt':
                orientation_s = math.sqrt(float(s))
            else:
                orientation_s = smooth5(clamp(float(s) / 0.65))
            rotation = app._scale_rotation(r0, r1, orientation_s)
        q, error = app.solve_layered_j5_pose_user(p, rotation, seed, side='left')
        if q is None:
            return Evaluation(candidate, False, f'第 {index}/{samples-1} 点 IK 失败：{error}')
        if not all(app.JOINT_LO[j] - 1e-9 <= q[j] <= app.JOINT_HI[j] + 1e-9 for j in range(6)):
            degrees = ', '.join(f'J{j+1}={math.degrees(q[j]):.2f}°' for j in range(6))
            return Evaluation(candidate, False, f'第 {index}/{samples-1} 点超执行端关节限位：{degrees}')
        margin = geometry.pose_margin(q, 'left')[0]
        if margin < geometry.MIN_MARGIN_CM:
            return Evaluation(candidate, False,
                              f'第 {index}/{samples-1} 点支架余量 {margin:.2f} cm < {geometry.MIN_MARGIN_CM:.2f} cm')
        qs.append(q)
        points.append(p)
        margins.append(margin)
        seed = tuple(q)
    q_array = np.asarray(qs)
    # 保留精确实测端点；解析 IK 的端点复现误差由独立测试检查。
    q_array[0] = q0
    q_array[-1] = q1
    return Evaluation(candidate, True, '离散 IK、执行端限位和单臂支架余量通过',
                      q=q_array, xyz=np.asarray(points), margins=np.asarray(margins))


def derivative_metrics(q: np.ndarray, times: np.ndarray) -> dict:
    velocity = np.diff(q, axis=0) / np.diff(times)[:, None]
    acceleration = np.diff(velocity, axis=0) / np.diff(times[:-1])[:, None]
    jerk = np.diff(acceleration, axis=0) / np.diff(times[:-2])[:, None]
    return {
        'max_joint_speed_rad_s': float(np.max(np.abs(velocity))),
        'max_joint_accel_rad_s2': float(np.max(np.abs(acceleration))),
        'max_joint_jerk_rad_s3': float(np.max(np.abs(jerk))),
        'max_joint_step_deg': float(np.max(np.abs(np.diff(q, axis=0))) * 180/math.pi),
    }


def spatial_metrics(xyz: np.ndarray) -> dict:
    delta = np.diff(xyz, axis=0)
    travel = np.abs(delta).sum(axis=0)
    net = xyz[-1] - xyz[0]
    # 本段任务 Z 应单调下降；正向增量即回弹量。
    z_rebound = float(np.maximum(delta[:, 2], 0.0).sum())
    return {
        'path_length_mm': float(np.linalg.norm(delta, axis=1).sum() * 1000),
        'x_travel_mm': float(travel[0] * 1000),
        'y_travel_mm': float(travel[1] * 1000),
        'z_travel_mm': float(travel[2] * 1000),
        'x_backtrack_mm': float((travel[0] - abs(net[0])) * 1000),
        'y_backtrack_mm': float((travel[1] - abs(net[1])) * 1000),
        'z_rebound_mm': z_rebound * 1000,
        'z_net_drop_mm': float(-net[2] * 1000),
    }


def timed_trajectory(evaluation: Evaluation, base_duration=4.0, dt=0.02,
                     speed_limit=0.75, accel_limit=2.0, jerk_limit=12.0) -> None:
    """minimum-jerk 时间标度；阈值为规划目标，不宣称为驱动器硬限值。"""
    duration = base_duration
    for _ in range(30):
        count = max(5, int(math.ceil(duration / dt)) + 1)
        times = np.linspace(0.0, duration, count)
        source = np.linspace(0.0, 1.0, len(evaluation.q))
        u = smooth5(times / duration)
        q = np.column_stack([np.interp(u, source, evaluation.q[:, j]) for j in range(6)])
        dynamic = derivative_metrics(q, times)
        scale = max(1.0,
                    dynamic['max_joint_speed_rad_s'] / speed_limit,
                    math.sqrt(dynamic['max_joint_accel_rad_s2'] / accel_limit),
                    (dynamic['max_joint_jerk_rad_s3'] / jerk_limit) ** (1/3))
        if scale <= 1.0001:
            break
        duration *= scale * 1.001
    else:
        raise RuntimeError(f"{evaluation.candidate.name} 时间标度未收敛")
    global_duration = duration
    indices = np.unique(np.r_[np.arange(0, len(q), 6), len(q)-1])
    q, times = q[indices], times[indices]
    times, solver_report = optimize_time(q, times, speed_limit, accel_limit, jerk_limit)
    if not solver_report['success'] or solver_report['min_constraint_margin'] < -1e-6:
        raise RuntimeError(f"{evaluation.candidate.name} 非线性时间优化失败：{solver_report}")
    duration = float(times[-1])
    dynamic = derivative_metrics(q, times)
    evaluation.times = times
    evaluation.q = q
    evaluation.xyz = np.asarray([user_position(row) for row in q])
    evaluation.margins = np.asarray([geometry.pose_margin(row, 'left')[0] for row in q])
    evaluation.duration_s = duration
    evaluation.metrics = spatial_metrics(evaluation.xyz) | dynamic | {
        'min_bracket_margin_cm': float(evaluation.margins.min()),
        'duration_s': float(duration),
        'global_time_scaling_s': float(global_duration),
        'local_time_compression_percent': float(100*(1-duration/global_duration)),
        'time_solver_iterations': solver_report['iterations'],
        'time_solver_min_constraint_margin': solver_report['min_constraint_margin'],
        'samples': len(q),
    }


def baseline(q0: Sequence[float], q1: Sequence[float], vmax=0.8, dt=0.01) -> Evaluation:
    """复现当前六轴独立限速：每拍各轴以相同 vmax 向目标靠近。"""
    path = geometry._rate_limited(q0, q1, vmax, dt)
    q = np.asarray(path)
    times = np.arange(len(q)) * dt
    xyz = np.asarray([user_position(row) for row in q])
    margins = np.asarray([geometry.pose_margin(row, 'left')[0] for row in q])
    candidate = Candidate('joint_rate_baseline', '现有基线', '六轴独立 0.8 rad/s 限速', lambda s: ())
    metrics = spatial_metrics(xyz) | derivative_metrics(q, times) | {
        'min_bracket_margin_cm': float(margins.min()),
        'duration_s': float(times[-1]),
        'samples': len(q),
    }
    return Evaluation(candidate, True, '现有在线算法的离线复现', q=q, xyz=xyz,
                      margins=margins, metrics=metrics, times=times, duration_s=float(times[-1]))


def verify_dense_geometry(evaluation: Evaluation) -> None:
    """补查相邻构型之间，避免只检查离散姿态漏掉局部低余量。"""
    assert evaluation.q is not None
    for index in range(len(evaluation.q)-1):
        result = geometry.check_path(evaluation.q[index].tolist(), evaluation.q[index+1].tolist(),
                                     'left', vmax=0.8, dt=0.01, stride=1)
        if not result['ok']:
            evaluation.feasible = False
            evaluation.reason = f'第 {index} 段连续补查失败：{result}'
            return
    evaluation.reason += '；相邻构型连续补查通过'


def plan(samples=161) -> tuple[Evaluation, list[Evaluation], Evaluation]:
    q0, q1 = app.Q_START_LEFT, app.Q_LEFT_POS3
    base = baseline(q0, q1)
    evaluations = []
    candidates = make_candidates(user_position(q0), user_position(q1))
    candidates += make_reference_projection_candidates(q0, q1)
    for candidate in candidates:
        result = solve_candidate(candidate, q0, q1, samples=samples)
        if result.feasible:
            try:
                timed_trajectory(result)
            except RuntimeError as error:
                result.feasible = False
                result.reason = str(error)
        if result.feasible:
            verify_dense_geometry(result)
        evaluations.append(result)
    feasible = [result for result in evaluations if result.feasible]
    if not feasible:
        details = '\n'.join(f'{r.candidate.name}: {r.reason}' for r in evaluations)
        raise RuntimeError('没有满足全部约束的候选：\n' + details)

    def score(result: Evaluation) -> float:
        m = result.metrics
        # 先过硬约束，再优先消除折返；长度、动态峰值仅作次级代价。
        return (m['x_backtrack_mm'] + m['y_backtrack_mm'] + 2.0*m['z_rebound_mm']
                + 0.03*m['path_length_mm'] + 2.0*m['max_joint_speed_rad_s'])

    best = min(feasible, key=score)
    return best, evaluations, base


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict]) -> None:
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def trajectory_rows(evaluation: Evaluation):
    r0 = user_rotation(app.Q_START_LEFT)
    for index, (t, q, xyz, margin) in enumerate(zip(
            evaluation.times, evaluation.q, evaluation.xyz, evaluation.margins)):
        rotation = user_rotation(q)
        yield {
            'index': index, 'time_s': f'{t:.12f}',
            **{f'q_J{j+1}_rad': f'{q[j]:.15f}' for j in range(6)},
            **{f'q_J{j+1}_deg': f'{math.degrees(q[j]):.10f}' for j in range(6)},
            'J5_x_mm': f'{xyz[0]*1000:.5f}', 'J5_y_mm': f'{xyz[1]*1000:.5f}',
            'J5_z_mm': f'{xyz[2]*1000:.5f}',
            'orientation_change_from_start_deg': f'{orientation_error_deg(r0, rotation):.7f}',
            'bracket_margin_cm': f'{margin:.5f}',
        }


def make_plots(best: Evaluation, baseline_result: Evaluation, output: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    ax = axes[0, 0]
    for result, label, style in ((baseline_result, '现有六轴独立限速', '--'),
                                 (best, '离线规划最优候选', '-')):
        ax.plot(result.xyz[:, 0]*1000, result.xyz[:, 1]*1000, style, linewidth=2, label=label)
        ax.scatter(result.xyz[[0, -1], 0]*1000, result.xyz[[0, -1], 1]*1000, s=35)
    ax.set(xlabel='X / mm', ylabel='Y / mm', title='J5 水平路径')
    ax.axis('equal'); ax.grid(alpha=.25); ax.legend()

    ax = axes[0, 1]
    for result, label, style in ((baseline_result, '现有', '--'), (best, '规划', '-')):
        ax.plot(result.times, result.xyz[:, 0]*1000, style, label=f'{label} X')
        ax.plot(result.times, result.xyz[:, 2]*1000, style, label=f'{label} Z', alpha=.75)
    ax.set(xlabel='时间 / s', ylabel='坐标 / mm', title='X、Z 时间历程')
    ax.grid(alpha=.25); ax.legend(ncol=2)

    ax = axes[1, 0]
    for j in range(6):
        ax.plot(best.times, np.degrees(best.q[:, j]), label=f'J{j+1}')
    ax.set(xlabel='时间 / s', ylabel='关节角 / °', title='最优候选六轴轨迹')
    ax.grid(alpha=.25); ax.legend(ncol=3)

    ax = axes[1, 1]
    for result, label, style in ((baseline_result, '现有', '--'), (best, '规划', '-')):
        ax.plot(result.times, result.margins, style, label=label)
    ax.axhline(geometry.MIN_MARGIN_CM, color='r', linestyle=':', label='最低允许余量')
    ax.set(xlabel='时间 / s', ylabel='支架余量 / cm', title='单臂支架几何余量')
    ax.grid(alpha=.25); ax.legend()
    fig.suptitle(f'X 左臂起始位 → 位置 3：{best.candidate.description}', fontsize=15)
    fig.savefig(output / '基线与最优轨迹对比.png', dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
    ax.plot(best.xyz[:, 0]*1000, best.xyz[:, 1]*1000, '-o', markevery=max(1, len(best.q)//25),
            markersize=3, label='J5 路径')
    ax.scatter(best.xyz[0, 0]*1000, best.xyz[0, 1]*1000, color='green', s=80, label='起始位')
    ax.scatter(best.xyz[-1, 0]*1000, best.xyz[-1, 1]*1000, color='red', s=80, label='位置 3')
    ax.set(xlabel='X / mm', ylabel='Y / mm', title='最优候选离散复核点')
    ax.axis('equal'); ax.grid(alpha=.25); ax.legend()
    fig.savefig(output / '最优轨迹离散复核.png', dpi=180)
    plt.close(fig)


def export(best: Evaluation, evaluations: list[Evaluation], base: Evaluation, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fields = ['name', 'family', 'description', 'feasible', 'reason', 'duration_s',
              'path_length_mm', 'x_travel_mm', 'y_travel_mm', 'z_travel_mm',
              'x_backtrack_mm', 'y_backtrack_mm', 'z_rebound_mm', 'z_net_drop_mm',
              'max_joint_speed_rad_s', 'max_joint_accel_rad_s2', 'max_joint_jerk_rad_s3',
              'max_joint_step_deg', 'min_bracket_margin_cm', 'global_time_scaling_s',
              'local_time_compression_percent', 'time_solver_iterations',
              'time_solver_min_constraint_margin', 'samples']
    rows = []
    for result in [base] + evaluations:
        rows.append({'name': result.candidate.name, 'family': result.candidate.family,
                     'description': result.candidate.description, 'feasible': result.feasible,
                     'reason': result.reason, **(result.metrics or {})})
    write_csv(output / '候选路径比较.csv', fields, rows)
    for name, result in (('最优六轴轨迹.csv', best), ('现有基线轨迹.csv', base)):
        result_rows = list(trajectory_rows(result))
        write_csv(output / name, list(result_rows[0]), result_rows)

    summary = {
        'scope': '纯离线规划；未连接硬件，未修改或部署在线控制',
        'selected': best.candidate.name,
        'selected_description': best.candidate.description,
        'selected_metrics': best.metrics,
        'baseline_metrics': base.metrics,
        'improvement_percent': {
            'path_length': 100.0 * (base.metrics['path_length_mm']-best.metrics['path_length_mm'])
                           / base.metrics['path_length_mm'],
            'x_backtrack': 100.0 * (base.metrics['x_backtrack_mm']-best.metrics['x_backtrack_mm'])
                           / base.metrics['x_backtrack_mm'],
        },
        'planning_targets_not_actuator_limits': {
            'max_joint_speed_rad_s': 0.75, 'max_joint_accel_rad_s2': 2.0,
            'max_joint_jerk_rad_s3': 12.0,
        },
        'constraints': {
            'ik_samples': 161,
            'joint_limits_rad': {'lo': app.JOINT_LO, 'hi': app.JOINT_HI},
            'min_bracket_margin_cm': geometry.MIN_MARGIN_CM,
            'orientation': '通用候选采用 SO(3) 插值；最优候选采用关节参考轨迹的姿态场',
            'time_law': 'minimum-jerk 初始轨迹 + 直接时间离散非线性约束优化（最短总时长）',
        },
        'limitations': [
            '仅验证左臂与支架模型，不包含双臂互撞、夹爪、物体和环境碰撞',
            '几何模型来自现有包络假设，离线通过不等于真机安全',
            '时间参数尚未接入在线执行器；实测延迟、跟踪误差需另行低速验证',
        ],
    }
    (output / '规划结果摘要.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                              encoding='utf-8')
    make_plots(best, base, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent / '输出')
    parser.add_argument('--samples', type=int, default=161)
    args = parser.parse_args()
    best, evaluations, base = plan(samples=args.samples)
    export(best, evaluations, base, args.output_dir)
    print(f'最优候选：{best.candidate.name} — {best.candidate.description}')
    print('指标：' + json.dumps(best.metrics, ensure_ascii=False, indent=2))
    print(f'输出目录：{args.output_dir.resolve()}')


if __name__ == '__main__':
    main()

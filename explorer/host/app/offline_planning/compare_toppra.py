# -*- coding: utf-8 -*-
"""同一解析 IK 几何路径上的 TOPP-RA 与直接时间离散 NLP 对比。"""
import csv
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline

import transfer_path_planner as planner
from toppra_retiming import parameterize

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / '输出'
data = np.genfromtxt(OUTPUT/'最优六轴轨迹.csv', delimiter=',', names=True, encoding='utf-8-sig')
q_nlp = np.column_stack([data[f'q_J{j}_rad'] for j in range(1, 7)])
t_nlp = data['time_s']

# 细化同一三次样条几何路径，降低标准 TOPP-RA 的网格间离散误差。
path_spline = CubicSpline(np.linspace(0, 1, len(q_nlp)), q_nlp, axis=0)
path_grid = np.linspace(0, 1, 851)
q_path = path_spline(path_grid)
t_ra, q_ra, info = parameterize(q_path, 0.75, 2.0, output_dt=0.001)

# 网格点解析约束：这是 TOPP-RA 线性规划直接保证的量。
x = info['squared_speed']
ds = path_grid[1]-path_grid[0]
u = np.diff(x)/(2*ds)
grid_velocity = path_spline(path_grid[:-1], 1)*np.sqrt(x[:-1])[:, None]
grid_acceleration = (path_spline(path_grid[:-1], 2)*x[:-1, None]
                     + path_spline(path_grid[:-1], 1)*u[:, None])
grid_max_speed = float(np.max(np.abs(grid_velocity)))
grid_max_acceleration = float(np.max(np.abs(grid_acceleration)))

xyz_ra = np.asarray([planner.user_position(q) for q in q_ra])
margins_ra = np.asarray([planner.geometry.pose_margin(q, 'left')[0] for q in q_ra])
metrics_ra = planner.spatial_metrics(xyz_ra) | planner.derivative_metrics(q_ra, t_ra) | {
    'duration_s': float(t_ra[-1]), 'samples': len(q_ra),
    'min_bracket_margin_cm': float(margins_ra.min()),
    'grid_max_speed_rad_s': grid_max_speed,
    'grid_max_acceleration_rad_s2': grid_max_acceleration,
    'lp_count': info['backward_lp_count']+info['forward_lp_count'],
}
metrics_nlp = planner.spatial_metrics(np.asarray([planner.user_position(q) for q in q_nlp])) \
    | planner.derivative_metrics(q_nlp, t_nlp) | {
        'duration_s': float(t_nlp[-1]), 'samples': len(q_nlp),
        'min_bracket_margin_cm': float(min(planner.geometry.pose_margin(q, 'left')[0] for q in q_nlp)),
    }

candidate = planner.Candidate('toppra_ra', 'TOPP-RA', '后向可控集 + 前向最优速度剖面，LP 求解', lambda s: ())
evaluation = planner.Evaluation(candidate, True, '离线 TOPP-RA', q=q_ra, xyz=xyz_ra,
                                margins=margins_ra, metrics=metrics_ra, times=t_ra,
                                duration_s=float(t_ra[-1]))
rows = list(planner.trajectory_rows(evaluation))
planner.write_csv(OUTPUT/'TOPPRA六轴轨迹.csv', list(rows[0]), rows)

comparison = {
    'scope': '同一解析 IK 几何路径；纯离线比较，不代表真机结果',
    'NLP': metrics_nlp,
    'TOPP_RA': metrics_ra,
    'duration_difference_s': float(t_nlp[-1]-t_ra[-1]),
    'toppra_time_reduction_percent': float(100*(t_nlp[-1]-t_ra[-1])/t_nlp[-1]),
    'interpretation': [
        'TOPP-RA 使用 851 路径点、1700 个后向 LP 和 850 个前向 LP。',
        'TOPP-RA 网格点速度/加速度满足 0.75 rad/s 和 2.0 rad/s²。',
        'TOPP-RA 不含 jerk 约束；输出轨迹的有限差分峰值包含加速度切换与网格间效应。',
        'NLP 在导出采样点上同时满足速度、加速度和 jerk 约束。',
    ],
}
(OUTPUT/'TOPPRA与NLP对比.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')
fields = ['metric', 'NLP', 'TOPP_RA']
with (OUTPUT/'TOPPRA与NLP对比.csv').open('w', newline='', encoding='utf-8-sig') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for key in metrics_nlp:
        writer.writerow({'metric': key, 'NLP': metrics_nlp.get(key), 'TOPP_RA': metrics_ra.get(key)})
    for key in ('grid_max_speed_rad_s', 'grid_max_acceleration_rad_s2', 'lp_count'):
        writer.writerow({'metric': key, 'NLP': None, 'TOPP_RA': metrics_ra[key]})

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
for j in range(6):
    axes[0, 0].plot(t_nlp, np.degrees(q_nlp[:, j]), label=f'J{j+1}')
axes[0, 0].set(title='NLP 六轴轨迹', xlabel='时间 / s', ylabel='角度 / °')
axes[0, 0].legend(ncol=3); axes[0, 0].grid(alpha=.25)
for j in range(6):
    axes[0, 1].plot(t_ra, np.degrees(q_ra[:, j]), label=f'J{j+1}')
axes[0, 1].set(title='TOPP-RA 六轴轨迹', xlabel='时间 / s', ylabel='角度 / °')
axes[0, 1].legend(ncol=3); axes[0, 1].grid(alpha=.25)

from nlp_time_scaling import derivatives
v_n, a_n, j_n = derivatives(q_nlp, np.diff(t_nlp))
v_r, a_r, j_r = derivatives(q_ra, np.diff(t_ra))
axes[1, 0].plot(t_nlp[:-1], np.max(np.abs(v_n), axis=1), label='NLP 速度')
axes[1, 0].plot(t_nlp[:-2], np.max(np.abs(a_n), axis=1), label='NLP 加速度')
axes[1, 0].plot(t_ra[:-1], np.max(np.abs(v_r), axis=1), '--', label='TOPP-RA 速度')
axes[1, 0].plot(t_ra[:-2], np.max(np.abs(a_r), axis=1), '--', label='TOPP-RA 加速度')
axes[1, 0].set(title='有限差分动态峰值', xlabel='时间 / s', ylabel='峰值（混合单位）', yscale='log')
axes[1, 0].legend(); axes[1, 0].grid(alpha=.25)
labels = ['时长 / s', '最大加速度\n(rad/s²)', '最大 jerk\n(rad/s³)']
nlp_values = [metrics_nlp['duration_s'], metrics_nlp['max_joint_accel_rad_s2'], metrics_nlp['max_joint_jerk_rad_s3']]
ra_values = [metrics_ra['duration_s'], metrics_ra['max_joint_accel_rad_s2'], metrics_ra['max_joint_jerk_rad_s3']]
pos = np.arange(3); width = .36
axes[1, 1].bar(pos-width/2, nlp_values, width, label='NLP')
axes[1, 1].bar(pos+width/2, ra_values, width, label='TOPP-RA')
axes[1, 1].set_xticks(pos, labels); axes[1, 1].set_yscale('log'); axes[1, 1].set_title('关键指标对比（对数坐标）')
axes[1, 1].legend(); axes[1, 1].grid(alpha=.25, axis='y')
fig.savefig(OUTPUT/'TOPPRA与NLP动态对比.png', dpi=180)
print(json.dumps(comparison, ensure_ascii=False, indent=2))

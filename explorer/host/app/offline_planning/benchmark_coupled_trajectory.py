# -*- coding: utf-8 -*-
"""真实构型的双臂增强规划离线对照实验；不连接设备。"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import time

import numpy as np

import coupled_trajectory as planner
import arm_console as app

OUTPUT = Path(__file__).resolve().parent / '输出' / '双臂耦合增强实验_20261101'
OUTPUT.mkdir(parents=True, exist_ok=True)

started = time.perf_counter()
result = planner.plan_dual_arm(
    app.Q_START_LEFT, app.Q_LEFT_POS3,
    app.Q_START_RIGHT, app.Q_START_RIGHT,
    jerk_limit=20.0, coordination_samples=41)
result['experiment'] = {
    'date': '2026-11-01',
    'case': '左臂起始位→位置3；右臂保持起始位',
    'collision_model': '现有粗碰撞域（非最终整车 FCL 验收）',
    'fair_comparison': '基线和增强方法使用完全相同的双臂联合几何路径',
    'wall_clock_planning_s': time.perf_counter()-started,
    'tracking_error': '未测量；需要实机反馈，离线结果不作跟踪误差结论',
}
(OUTPUT/'result.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

rows = []
for method in ('baseline', 'enhanced'):
    metrics = result[method]['metrics']
    rows.append({'method': method, **metrics})
with (OUTPUT/'metrics.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

for method in ('baseline', 'enhanced'):
    data = result[method]
    times = np.asarray(data['times'])
    q = np.asarray(data['q'])
    velocity = np.gradient(q, times, axis=0, edge_order=2)
    acceleration = np.gradient(velocity, times, axis=0, edge_order=2)
    jerk = np.gradient(acceleration, times, axis=0, edge_order=2)
    np.savez_compressed(OUTPUT/f'{method}.npz', times=times, q=q,
                        velocity=velocity, acceleration=acceleration, jerk=jerk)

base = result['baseline']['metrics']
new = result['enhanced']['metrics']
reduction = lambda key: 100.0*(base[key]-new[key])/base[key]
report = f"""# 双臂耦合、奇异感知与冲击受限规划：离线对照实验

日期：2026-11-01

## 实验条件

- 工况：左臂由起始位运动到位置 3，右臂保持起始位。
- 几何路径：两种方法使用完全相同的 12 维联合路径，避免路径差异干扰时间参数化对照。
- 联合碰撞：每个采样点均以动态另一臂位形复核，而非将另一臂永久固定在起点。
- 基线：原生 TOPP-RA，速度上限 0.8 rad/s，加速度上限 2.1333 rad/s²。
- 增强：J5 平移奇异区域局部限速＋TOPP-RA＋jerk 后处理，jerk 上限 20 rad/s³。
- 碰撞模型：现有粗碰撞域，不能替代最终整车 FCL 精确网格验收。
- 规划耗时：{result['experiment']['wall_clock_planning_s']:.3f} s（本机本次运行）。

## 结果

| 指标 | 原生 TOPP-RA | 增强轨迹 | 变化 |
| --- | ---: | ---: | ---: |
| 运动时间（s） | {base['duration_s']:.3f} | {new['duration_s']:.3f} | {100*(new['duration_s']/base['duration_s']-1):+.1f}% |
| 最大关节速度（rad/s） | {base['max_velocity_rad_s']:.3f} | {new['max_velocity_rad_s']:.3f} | {reduction('max_velocity_rad_s'):.1f}% 降低 |
| 最大关节加速度（rad/s²） | {base['max_acceleration_rad_s2']:.3f} | {new['max_acceleration_rad_s2']:.3f} | {reduction('max_acceleration_rad_s2'):.1f}% 降低 |
| 最大 jerk（rad/s³） | {base['max_jerk_rad_s3']:.3f} | {new['max_jerk_rad_s3']:.3f} | {reduction('max_jerk_rad_s3'):.1f}% 降低 |
| RMS jerk（rad/s³） | {base['rms_jerk_rad_s3']:.3f} | {new['rms_jerk_rad_s3']:.3f} | {reduction('rms_jerk_rad_s3'):.1f}% 降低 |

## 其他检查

- 协调方式：{result['coordination']['mode']}。
- 联合位形检查次数：{result['collision']['pose_checks']}。
- 本例粗模型最小余量：{result['collision']['minimum_margin_cm']:.3f} cm。
- 本例路径最小 J5 平移奇异值：{result['constraints']['minimum_path_sigma_m']:.4f} m。
- 本例最小奇异限速比例：{result['constraints']['minimum_speed_scale']:.3f}；因此本例冲击改善来自 jerk 重定时，不应归功于奇异限速。
- jerk 处理方式：{result['toppra']['jerk_retiming']['method']}。

## 结论边界

本实验只证明：**在该离线与粗碰撞模型工况下，增强方法降低了命令轨迹的数值 jerk，但增加了运动时间。**

它尚不证明实机跟踪误差更低，也不证明所有路径、所有奇异位形或精确整车模型下均有相同收益。后续应使用相同速度和加速度上限完成实机重复实验，测量关节反馈跟踪 RMSE、最大误差和到位残余波动，并补做奇异邻域专门工况。
"""
(OUTPUT/'实验报告.md').write_text(report, encoding='utf-8')
print(json.dumps({'output': str(OUTPUT), 'baseline': base, 'enhanced': new,
                  'planning_s': result['experiment']['wall_clock_planning_s']},
                 ensure_ascii=False, indent=2))

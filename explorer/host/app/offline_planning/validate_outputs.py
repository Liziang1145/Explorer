# -*- coding: utf-8 -*-
"""独立复核导出的 CSV，而不是只检查内存中的规划结果。"""
import hashlib
import json
from pathlib import Path

import numpy as np

import transfer_path_planner as planner

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / '输出'
path = OUTPUT / '最优六轴轨迹.csv'
data = np.genfromtxt(path, delimiter=',', names=True, encoding='utf-8-sig')
q = np.column_stack([data[f'q_J{j}_rad'] for j in range(1, 7)])
times = data['time_s']
xyz_saved = np.column_stack([data[f'J5_{axis}_mm'] for axis in ('x', 'y', 'z')])
xyz_fk = np.asarray([planner.user_position(row) for row in q]) * 1000
margins = np.asarray([planner.geometry.pose_margin(row, 'left')[0] for row in q])
dynamic = planner.derivative_metrics(q, times)
position_error = np.linalg.norm(xyz_saved-xyz_fk, axis=1)
checks = {
    'csv_rows_ge_100': bool(len(q) >= 100),
    'time_strictly_increasing': bool(np.all(np.diff(times) > 0)),
    'all_values_finite': bool(np.all(np.isfinite(q)) and np.all(np.isfinite(xyz_saved))),
    'exact_joint_endpoints': bool(np.allclose(q[0], planner.app.Q_START_LEFT, atol=5e-10)
                                  and np.allclose(q[-1], planner.app.Q_LEFT_POS3, atol=5e-10)),
    'saved_xyz_matches_independent_fk': bool(position_error.max() < 0.001),
    'execution_joint_limits': bool(np.all(q >= planner.app.JOINT_LO)
                                   and np.all(q <= planner.app.JOINT_HI)),
    'bracket_margin': bool(margins.min() >= planner.geometry.MIN_MARGIN_CM),
    'x_monotonic_within_1um': bool(np.all(np.diff(xyz_saved[:, 0]) >= -0.001)),
    'z_monotonic_down_within_1um': bool(np.all(np.diff(xyz_saved[:, 2]) <= 0.001)),
    'speed_planning_target': bool(dynamic['max_joint_speed_rad_s'] <= 0.7501),
    'acceleration_planning_target': bool(dynamic['max_joint_accel_rad_s2'] <= 2.0001),
    'jerk_planning_target': bool(dynamic['max_joint_jerk_rad_s3'] <= 12.0001),
}
sources = [ROOT/'transfer_path_planner.py', ROOT/'nlp_time_scaling.py',
           planner.APP_DIR/'arm_console.py', planner.APP_DIR/'arm_geometry.py']
report = {
    'scope': '仅复核离线导出文件；不代表真机验证',
    'all_passed': all(checks.values()),
    'checks': checks,
    'rows': len(q),
    'duration_s': float(times[-1]),
    'max_saved_vs_fk_position_error_mm': float(position_error.max()),
    'min_bracket_margin_cm': float(margins.min()),
    'dynamic_metrics_from_exported_csv': dynamic,
    'source_sha256': {str(file): hashlib.sha256(file.read_bytes()).hexdigest() for file in sources},
}
(OUTPUT/'独立验证报告.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
if not report['all_passed']:
    raise SystemExit(1)

# -*- coding: utf-8 -*-
"""石头目标 → 底盘 B 系 → 臂基系 → 后方预夹点 → 只读轨迹预览。

本模块没有电机、CAN、HTTP intent 或执行入口。输入点定义为 J7 夹爪中心参考点，
不是 J5 中心。默认把目标沿水平夹取反方向后退 100 mm，夹爪朝车体 +Y。
相机候选外参仅用于离线试验，状态保持 candidate_not_activated。
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

J5_TO_J7_M = 0.1525
DEFAULT_PREGRASP_RETREAT_M = 0.100
ARM_BASE_B_M = {
    'left': (-0.15255, 0.18375, 0.00500),
    'right': (0.15255, 0.18375, 0.00500),
}

# 2026-11-01 队友交接候选；输入 color optical/m，输出 B/m。
CAMERA_CANDIDATE_SHA256 = '856529b4d9170682f8c26732383a68a08ec5ce5d66752ce3e63c105ca67f6053'
T_B_FROM_COLOR_OPTICAL = (
    (0.999653806, 0.003395338, 0.026090992, -0.028135471),
    (-0.021072039, -0.490497785, 0.871187633, 0.291114746),
    (0.015755550, -0.871435824, -0.490256431, 0.540246415),
    (0.0, 0.0, 0.0, 1.0),
)


def _vector(value, name='坐标'):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f'{name}必须为三个数值')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError(f'{name}必须为三个有限数值')
    return tuple(float(v) for v in value)


def _unit(value):
    vector = _vector(value, '夹爪方向')
    length = math.sqrt(sum(v*v for v in vector))
    if length < 1e-9:
        raise ValueError('夹爪方向不能为零向量')
    return tuple(v/length for v in vector)


def color_optical_to_body(point_color_m):
    """彩色光学三维点（米）→ B 系（米）；不接受原始 depth optical 点。"""
    point = _vector(point_color_m, 'color optical 点')
    homogeneous = (*point, 1.0)
    return tuple(sum(row[i]*homogeneous[i] for i in range(4)) for row in T_B_FROM_COLOR_OPTICAL[:3])


def pregrasp_target(point_b_m, side='left', retreat_m=DEFAULT_PREGRASP_RETREAT_M,
                    direction=(0.0, 1.0, 0.0), roll_rad=0.0):
    """B 系 J7 参考点 → 水平后方预夹点及对应臂基系 J5/J7。"""
    if side not in ARM_BASE_B_M:
        raise ValueError('side 必须为 left 或 right')
    point = _vector(point_b_m, 'B 系参考点')
    if type(retreat_m) not in (int, float) or not math.isfinite(retreat_m) or not 0.0 <= retreat_m <= 0.3:
        raise ValueError('预夹后退距离必须为 0～0.3 m 的有限数值')
    if type(roll_rad) not in (int, float) or not math.isfinite(roll_rad):
        raise ValueError('roll_rad 必须为有限数值')
    d = _unit(direction)
    j7_b = tuple(point[i]-float(retreat_m)*d[i] for i in range(3))
    j7_b = (j7_b[0]-0.01, j7_b[1], j7_b[2])  # 车体 X 右为正：预抓点向左 10 mm
    j5_b = tuple(j7_b[i]-J5_TO_J7_M*d[i] for i in range(3))
    base = ARM_BASE_B_M[side]
    j7_local = tuple(j7_b[i]-base[i] for i in range(3))
    j5_local = tuple(j5_b[i]-base[i] for i in range(3))
    return {
        'input_frame': 'B: X右/Y前/Z上，底盘顶面中心，m；参考点为J7夹爪中心',
        'reference_j7_b_m': point,
        'pregrasp_retreat_m': float(retreat_m),
        'pregrasp_j7_b_m': j7_b,
        'pregrasp_j5_b_m': j5_b,
        'arm_base_b_m': base,
        'pregrasp_j7_arm_m': j7_local,
        'pregrasp_j5_arm_m': j5_local,
        'direction_b': d,
        'roll_rad': float(roll_rad),
        'side': side,
    }


def read_only_intent(target):
    """生成供人工核对的接口载荷；本函数只返回字典，绝不发送 HTTP。"""
    return {
        'intent': 'tcp_dir_abs',
        'side': target['side'],
        'p1': [v*100.0 for v in target['pregrasp_j7_arm_m']],
        'direction': list(target['direction_b']),
        'theta': math.degrees(target['roll_rad']),
        'client': 'stone-grasp-trial-preview-only',
        'safety_epoch': 'NOT_PROVIDED_PREVIEW_ONLY',
    }


def plan_preview(point_b_m, side='left', retreat_m=DEFAULT_PREGRASP_RETREAT_M,
                 direction=(0.0, 1.0, 0.0), roll_rad=0.0, current_q=None,
                 other_arm_q=None, collision_mode='exact', collision_workers=1):
    """调用现有离线规划器；没有设备反馈时必须由调用方显式提供关节角。"""
    if current_q is None:
        raise ValueError('只读规划必须提供 current_q；禁止用虚构当前姿态替代真机反馈')
    target = pregrasp_target(point_b_m, side, retreat_m, direction, roll_rad)
    import os
    os.environ['APEX_OFFLINE'] = '1'
    import arm_console as app
    import vla_motion_planner
    orientation = app._two_point_orientation(
        target['pregrasp_j7_arm_m'], target['pregrasp_j5_arm_m'],
        target['roll_rad'], current_q, side)
    trajectory = vla_motion_planner.plan_j5_xyz(
        side, target['pregrasp_j5_arm_m'], orientation=orientation,
        current_q=current_q, other_arm_q=other_arm_q,
        collision_mode=collision_mode, collision_workers=collision_workers)
    trajectory.update({
        'ok': True,
        'read_only': True,
        'execution_enabled': False,
        'message': '仅生成石头后方预夹点轨迹；未发送且不会发送电机命令',
        'target': target,
        'intent_preview_not_sent': read_only_intent(target),
        'environment_warning': '原碰撞模型不包含石头和桌面；规划通过不等于实抓安全',
    })
    return trajectory


def main():
    parser = argparse.ArgumentParser(description='石头 B 系参考点 → 水平后方10cm预夹点（只读）')
    parser.add_argument('xyz', nargs=3, type=float, help='B 系 J7 参考点 X Y Z，单位 m')
    parser.add_argument('--side', choices=('left', 'right'), default='left')
    parser.add_argument('--retreat', type=float, default=DEFAULT_PREGRASP_RETREAT_M)
    parser.add_argument('--direction', nargs=3, type=float, default=(0.0, 1.0, 0.0))
    parser.add_argument('--roll', type=float, default=0.0, help='绕夹爪轴 roll，rad')
    parser.add_argument('--output', type=Path, help='可选：保存转换结果 JSON')
    args = parser.parse_args()
    target = pregrasp_target(args.xyz, args.side, args.retreat, args.direction, args.roll)
    result = {
        'ok': True, 'read_only': True, 'execution_enabled': False,
        'target': target, 'intent_preview_not_sent': read_only_intent(target),
        'warning': '仅坐标换算；尚未进行IK、碰撞检查或实机验收',
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""VLA 运动规划只读预检：只消费关节反馈并返回轨迹，不具备执行入口。"""
import math


def preview(data, app):
    """data: {side, xyz:[x,y,z]}；XYZ 单位为米，姿态保持当前反馈姿态。"""
    if not isinstance(data, dict):
        raise ValueError('请求必须是对象')
    side = data.get('side', 'left')
    if side not in ('left', 'right'):
        raise ValueError('side 必须为 left 或 right')
    xyz = data.get('xyz')
    if not isinstance(xyz, list) or len(xyz) != 3 or any(
            type(value) not in (int, float) or not math.isfinite(value) for value in xyz):
        raise ValueError('xyz 必须为三个有限坐标（米）')
    own_read = app.left_read if side == 'left' else app.right_read
    other_read = app.right_read if side == 'left' else app.left_read
    ok, own_deg = own_read()
    other_ok, other_deg = other_read()
    if not ok or not isinstance(own_deg, list) or len(own_deg) != 6:
        raise ValueError(f'无法读取{side}臂六轴反馈：{own_deg}')
    if not other_ok or not isinstance(other_deg, list) or len(other_deg) != 6:
        raise ValueError(f'无法读取另一臂六轴反馈：{other_deg}')
    current = [math.radians(value) for value in own_deg]
    other = [math.radians(value) for value in other_deg]
    if not all(math.isfinite(value) for value in current + other):
        raise ValueError('关节反馈包含非有限值')
    collision_mode = data.get('collision_mode', 'coarse')
    if collision_mode not in ('coarse', 'exact'):
        raise ValueError('collision_mode 必须为 coarse 或 exact')
    # 延迟导入，避免 SciPy/RRT/FCL 影响现有 VR 与控制服务的启动。
    if collision_mode == 'exact':
        import sys
        from pathlib import Path
        for packages in Path('/home/apex/vla_exact_venv/lib').glob('python*/site-packages'):
            if str(packages) not in sys.path:
                sys.path.insert(0, str(packages))
    import vla_motion_planner
    result = vla_motion_planner.plan_j5_xyz(
        side, xyz, current_q=current, collision_mode=collision_mode,
        other_arm_q={'right' if side == 'left' else 'left': other})
    result.update({
        'ok': True,
        'read_only': True,
        'execution_enabled': False,
        'side': side,
        'current_q_rad': current,
        'other_arm_q_rad': other,
        'message': '仅规划预览；未发送且不会发送电机命令',
    })
    return result

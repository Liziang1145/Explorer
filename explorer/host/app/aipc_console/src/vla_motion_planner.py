# -*- coding: utf-8 -*-
"""VLA 大范围 J5 移动：可达性、静态碰撞、RRT-Connect 与 TOPP-RA 离线首版。

默认碰撞域：现有连杆保守包络、支架、双臂以及底座基准平面。
collision_mode='exact' 时增加 FCL 双臂分件网格和最终 v3 整车环境网格。
持物与动态环境尚未接入，本模块不直接连接在线控制。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
import os
import sys

import numpy as np

# 必须在导入 arm_console 前设置，阻止离线规划启动 SSH 反馈刷新线程。
os.environ['APEX_OFFLINE'] = '1'

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'aipc-simulator-ui'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import arm_console as app
import arm_geometry as geometry
from transfer_trajectory import _parameterize


@dataclass
class CollisionResult:
    ok: bool
    reason: str
    margin_cm: float


class StaticCollisionModel:
    """保守运动学碰撞域；单位换算统一由 arm_geometry.links_cm 完成。"""

    def __init__(self, other_arm_q=None, min_margin_cm=None,
                 gripper_radius_cm=7.25, gripper_length_cm=13.58,
                 check_gripper=True):
        self.check_gripper = bool(check_gripper)
        self.other_arm_q = {'left': app.Q_START_RIGHT, 'right': app.Q_START_LEFT}
        if other_arm_q:
            self.other_arm_q.update({key: list(value) for key, value in other_arm_q.items()})
        self.min_margin = geometry.MIN_MARGIN_CM if min_margin_cm is None else float(min_margin_cm)
        # CAD／实测定值：外伸 13.58 cm、最大张开根部半跨 7.25 cm。
        # 等半径胶囊是保守下界，不是精确夹爪网格，仍不据此开放实机执行。
        self.gripper_radius = float(gripper_radius_cm)
        self.gripper_length = float(gripper_length_cm)
        if not all(math.isfinite(value) and value > 0
                   for value in (self.gripper_radius, self.gripper_length)):
            raise ValueError('夹爪包络半径和长度必须为有限正数')

    @staticmethod
    def _plane_margin(links):
        best = math.inf
        for name, a, b, _r0, _r1 in links:
            # 底座立柱从安装基准面 z=0 起，不能按可动连杆要求高于安全余量。
            if name == '底座立柱':
                continue
            for s in np.linspace(0.0, 1.0, 7):
                # 底座基准面以下的空间视为底盘禁入域；不是完整 STEP 底盘网格。
                best = min(best, a[2] + s*(b[2]-a[2]))
        return best

    def _gripper_capsule(self, q, side):
        points = geometry.fk_chain(q)
        base = geometry.ARM_BASE_CM[side]
        p5, p6 = [np.asarray([point[0]*100+base[0], point[1]*100+base[1],
                              point[2]*100+base[2]]) for point in points[-2:]]
        direction = p6-p5
        length = float(np.linalg.norm(direction))
        if length < 1e-9:
            raise ValueError('腕部轴线退化，无法构造夹爪包络')
        return p6, p6+direction/length*self.gripper_length

    def _gripper_link_margin(self, q, side, links, coarse_self=False):
        a, b = self._gripper_capsule(q, side)
        best = math.inf
        for index, (name, c, d, _r0, _r1) in enumerate(links):
            # 零位 STL 顶点核对：夹爪本体距前臂约 12.7 cm，等半径圆柱却产生误报。
            # 前臂／腕部与夹爪的精确自碰撞仍待分件网格，不在粗模型里虚假判撞。
            if coarse_self and index >= len(links)-2:
                continue
            distance, s, _t = geometry.seg_seg_st(a, b, c, d)
            best = min(best, distance-self.gripper_radius-geometry._local_r(name, _t))
        return best

    def pose(self, q, side):
        q = np.asarray(q, dtype=float)
        if not np.all(np.isfinite(q)) or not np.all(q >= app.JOINT_LO) or not np.all(q <= app.JOINT_HI):
            return CollisionResult(False, '关节角非有限或超过执行端限位', -math.inf)
        margin = geometry.pose_margin(q.tolist(), side)[0]
        if margin < self.min_margin:
            return CollisionResult(False, f'支架余量 {margin:.2f} cm 不足', margin)
        own = geometry.links_cm(q.tolist(), side)
        plane = self._plane_margin(own)
        if self.check_gripper:
            gripper_a, gripper_b = self._gripper_capsule(q, side)
            plane = min(plane, gripper_a[2]-self.gripper_radius,
                        gripper_b[2]-self.gripper_radius)
        if plane < self.min_margin:
            return CollisionResult(False, f'底座／底盘禁入域余量 {plane:.2f} cm 不足', plane)
        self_margin = math.inf
        # 粗模型仅保留底座×前臂。底座／上臂×合并腕部在零位均会假碰撞；
        # 分件 STL 顶点间隙约 4.3–4.6 cm，需分件模型后再恢复这些检查。
        name, a, b, _r0, _r1 = own[0]
        other_name, c, d, _s0, _s1 = own[2]
        distance, s, t = geometry.seg_seg_st(a, b, c, d)
        self_margin = distance-(geometry._local_r(name, s)+geometry._local_r(other_name, t))
        if self_margin < self.min_margin:
            return CollisionResult(False, f'单臂自碰撞余量 {self_margin:.2f} cm 不足', self_margin)
        if self.check_gripper:
            for rod_name, c, d in geometry.BRACKET:
                distance, _s, _t = geometry.seg_seg_st(gripper_a, gripper_b, c, d)
                gripper_bracket = distance-self.gripper_radius-geometry.ROD_R_CM
                margin = min(margin, gripper_bracket)
                if gripper_bracket < self.min_margin:
                    return CollisionResult(False, f'夹爪与支架 {rod_name} 余量 {gripper_bracket:.2f} cm 不足', gripper_bracket)
        other_side = 'right' if side == 'left' else 'left'
        other_q = self.other_arm_q[other_side]
        other = geometry.links_cm(other_q, other_side)
        best = math.inf
        if self.check_gripper:
            best = self._gripper_link_margin(q, side, other)
            best = min(best, self._gripper_link_margin(other_q, other_side, own))
            other_a, other_b = self._gripper_capsule(other_q, other_side)
            distance, _s, _t = geometry.seg_seg_st(gripper_a, gripper_b, other_a, other_b)
            best = min(best, distance-2*self.gripper_radius)
        for name, a, b, _r0, _r1 in own:
            for other_name, c, d, _s0, _s1 in other:
                distance, s, t = geometry.seg_seg_st(a, b, c, d)
                clearance = distance - (geometry._local_r(name, s) + geometry._local_r(other_name, t))
                best = min(best, clearance)
        if not all(math.isfinite(value) for value in (margin, plane, self_margin, best)):
            return CollisionResult(False, '碰撞几何计算产生非有限余量', -math.inf)
        if best < self.min_margin:
            return CollisionResult(False, f'双臂连杆余量 {best:.2f} cm 不足', best)
        return CollisionResult(True, '静态碰撞检查通过（不含夹爪）' if not self.check_gripper else '静态碰撞检查通过',
                               min(margin, plane, self_margin, best))

    def segment(self, q0, q1, side, max_step_rad=math.radians(2.0)):
        a, b = np.asarray(q0), np.asarray(q1)
        count = max(1, int(math.ceil(float(np.max(np.abs(b-a))) / max_step_rad)))
        worst = math.inf
        for s in np.linspace(0.0, 1.0, count+1):
            result = self.pose(a+s*(b-a), side)
            worst = min(worst, result.margin_cm)
            if not result.ok:
                return CollisionResult(False, result.reason, worst)
        return CollisionResult(True, '连续段检查通过', worst)


class RRTConnect:
    def __init__(self, collision, side, seed=7, step_rad=0.12, max_iterations=4000):
        self.collision = collision
        self.side = side
        self.rng = np.random.default_rng(seed)
        self.step = step_rad
        self.max_iterations = max_iterations
        self.lo = np.asarray(app.JOINT_LO)
        self.hi = np.asarray(app.JOINT_HI)

    def _extend(self, nodes, parents, target):
        distances = np.linalg.norm(nodes-target, axis=1)
        nearest = int(np.argmin(distances))
        delta = target-nodes[nearest]
        length = float(np.linalg.norm(delta))
        if length < 1e-12:
            return nearest, nodes, parents, True
        q = target if length <= self.step else nodes[nearest] + delta/length*self.step
        if not self.collision.segment(nodes[nearest], q, self.side).ok:
            return nearest, nodes, parents, False
        nodes = np.vstack((nodes, q))
        parents = np.append(parents, nearest)
        return len(nodes)-1, nodes, parents, True

    def _connect(self, nodes, parents, target):
        index, nodes, parents, valid = self._extend(nodes, parents, target)
        if not valid:
            return nodes, parents, False
        while np.linalg.norm(nodes[index]-target) > 1e-10:
            new_index, nodes, parents, valid = self._extend(nodes, parents, target)
            if not valid:
                return nodes, parents, False
            index = new_index
        return nodes, parents, True

    @staticmethod
    def _branch(nodes, parents, index):
        result = []
        while index >= 0:
            result.append(nodes[index].copy())
            index = int(parents[index])
        return result

    def solve(self, q0, q1):
        start, goal = np.asarray(q0, dtype=float), np.asarray(q1, dtype=float)
        if self.collision.segment(start, goal, self.side).ok:
            return [start, goal], {'direct': True, 'iterations': 0}
        trees = [[np.asarray([start]), np.asarray([-1])],
                 [np.asarray([goal]), np.asarray([-1])]]
        swapped = False
        for iteration in range(1, self.max_iterations+1):
            random = goal if self.rng.random() < 0.1 else self.rng.uniform(self.lo, self.hi)
            a, b = (0, 1) if not swapped else (1, 0)
            index, trees[a][0], trees[a][1], valid = self._extend(*trees[a], random)
            if valid:
                target = trees[a][0][index]
                trees[b][0], trees[b][1], connected = self._connect(*trees[b], target)
                if connected:
                    other = int(np.argmin(np.linalg.norm(trees[b][0]-target, axis=1)))
                    pa = self._branch(*trees[a], index)
                    pb = self._branch(*trees[b], other)
                    if swapped:
                        pa, pb = pb, pa
                    path = list(reversed(pa))+pb
                    return path, {'direct': False, 'iterations': iteration, 'rrt_nodes': len(path)}
            swapped = not swapped
        raise RuntimeError(f'RRT-Connect 在 {self.max_iterations} 次迭代内未找到无碰撞路径')


def shortcut(path, collision, side, rng, attempts=300):
    if len(path) <= 2:
        return [np.asarray(q) for q in path]
    result = [np.asarray(q) for q in path]
    for _ in range(attempts):
        if len(result) <= 2:
            break
        i, j = sorted(rng.choice(len(result), size=2, replace=False).tolist())
        if j-i <= 1:
            continue
        if collision.segment(result[i], result[j], side).ok:
            result = result[:i+1]+result[j:]
    return result


def resample(path, max_step_rad=math.radians(1.0)):
    result = [np.asarray(path[0], dtype=float)]
    for a, b in zip(path, path[1:]):
        count = max(1, int(math.ceil(float(np.max(np.abs(np.asarray(b)-a))) / max_step_rad)))
        result.extend(np.asarray(a)+(np.asarray(b)-a)*s for s in np.linspace(0, 1, count+1)[1:])
    return np.asarray(result)


def _rotation(q, side):
    # solve_layered_j5_pose_user 接受原生机械臂姿态经 _FR 变换后的用户系矩阵。
    return app._mm(app._FR, app._fk(q)[1])


def plan_j5_xyz(side, xyz, orientation=None, current_q=None, other_arm_q=None,
                seed=7, max_iterations=4000, collision_mode='coarse', mesh_margin_cm=0.0,
                collision_workers=1, check_gripper=True, nearest_orientation=False):
    """离线通用入口；orientation=None 时保持当前姿态。

    collision_mode='coarse' 保持原行为；'exact' 使用 FCL 双臂分件网格。
    mesh_margin_cm 是精确网格额外余量，默认 0 表示只排除相交；已知合法起始
    姿态的最小自碰撞间隙约 1.14 cm，不应在不知情时强制设为 2 cm。
    """
    if side not in ('left', 'right'):
        raise ValueError('side 必须为 left 或 right')
    if isinstance(collision_workers, bool) or not isinstance(collision_workers, (int, np.integer)) or collision_workers < 1:
        raise ValueError('collision_workers 必须为大于等于 1 的整数')
    collision_workers = int(collision_workers)
    point = tuple(float(v) for v in xyz)
    if len(point) != 3 or not all(math.isfinite(v) for v in point):
        raise ValueError('J5 XYZ 必须为三个有限坐标（米）')
    if current_q is None:
        current_q = app.Q_START_LEFT if side == 'left' else app.Q_START_RIGHT
    current = np.asarray(current_q, dtype=float)
    rotation = _rotation(current, side) if orientation is None else orientation
    target, error = app.solve_layered_j5_pose_user(point, rotation, tuple(current), side=side)
    orientation_adjustment_deg = 0.0
    # 夹取试验专用：严格姿态无解时，在当前姿态附近搜索最小合法修正。
    # 不放宽关节限位，不改变目标 XYZ，也不用于普通坐标规划。
    if target is None and nearest_orientation and orientation is None:
        from itertools import product
        best = None
        for degrees in range(1, 13):
            for roll, pitch, yaw in product((-degrees, 0.0, degrees), repeat=3):
                if max(abs(roll), abs(pitch), abs(yaw)) != degrees:
                    continue
                offset = app._rt(0, 0, 0, math.radians(roll),
                                 math.radians(pitch), math.radians(yaw))[0]
                candidate_rotation = app._mm(offset, rotation)
                candidate, _ = app.solve_layered_j5_pose_user(
                    point, candidate_rotation, tuple(current), side=side)
                if candidate is None:
                    continue
                score = (degrees*degrees*20.0 +
                         sum((candidate[i]-current[i])**2 for i in range(3, 6)))
                if best is None or score < best[0]:
                    best = (score, candidate, candidate_rotation, degrees)
            if best is not None:
                break
        if best is not None:
            _score, target, rotation, orientation_adjustment_deg = best
    if target is None:
        raise ValueError(f'目标不可达：解析 IK 失败：{error}')
    target = np.asarray(target, dtype=float)
    if collision_mode == 'coarse':
        collision = StaticCollisionModel(other_arm_q=other_arm_q, check_gripper=check_gripper)
        scope = '连杆包络＋底座×前臂自检＋底座禁入平面；不含夹爪／动态环境'
    elif collision_mode == 'exact':
        from exact_collision import ExactMeshCollisionModel
        collision = ExactMeshCollisionModel(other_arm_q=other_arm_q, mesh_margin_cm=mesh_margin_cm,
                                            check_gripper=check_gripper)
        scope = ('FCL双臂连杆网格＋v3安装板／支架／雷达底座／完整底盘网格；'
                 '不含夹爪／持物／动态环境') if not check_gripper else (
                 'FCL双臂9分件网格（含固定底座与夹爪）＋v3安装板／支架／雷达底座／完整底盘网格；不含持物／动态环境')
    else:
        raise ValueError("collision_mode 必须为 'coarse' 或 'exact'")
    for label, q in (('当前位置', current), ('目标位置', target)):
        checked = collision.pose(q, side)
        if not checked.ok:
            raise ValueError(f'{label}不满足约束：{checked.reason}')
    if collision_mode == 'exact' and collision_workers > 1:
        from exact_collision import check_poses_parallel
        count = max(1, int(math.ceil(float(np.max(np.abs(target-current)))/math.radians(2.0))))
        candidates = [current+s*(target-current) for s in np.linspace(0.0, 1.0, count+1)]
        direct_checks = check_poses_parallel(collision, candidates, side, collision_workers)
        if all(item.ok for item in direct_checks):
            path, search = [current, target], {'direct': True, 'iterations': 0}
        else:
            path, search = RRTConnect(collision, side, seed=seed,
                                      max_iterations=max_iterations).solve(current, target)
    else:
        path, search = RRTConnect(collision, side, seed=seed,
                                  max_iterations=max_iterations).solve(current, target)
    if not search['direct']:
        path = shortcut(path, collision, side, np.random.default_rng(seed+1))
    dense = resample(path)
    if collision_mode == 'coarse':
        for a, b in zip(dense, dense[1:]):
            checked = collision.segment(a, b, side)
            if not checked.ok:
                raise RuntimeError('重采样路径连续碰撞复核失败：'+checked.reason)
    # exact：dense 点仅位于已检查 RRT／shortcut 直线段内部，不新增几何边；
    # 保留这些边上的原始精确采样与下方 TOPP-RA 输出逐点精确复核，避免第三次全扫。
    times, timed, info = _parameterize(dense)
    if collision_mode == 'exact' and collision_workers > 1:
        from exact_collision import check_poses_parallel
        checked_poses = check_poses_parallel(collision, timed, side, collision_workers)
    else:
        checked_poses = [collision.pose(q, side) for q in timed]
    for checked in checked_poses:
        if not checked.ok:
            raise RuntimeError('TOPP-RA 输出碰撞复核失败：'+checked.reason)
    result = {
        'times': (times-times[0]).tolist(), 'q': timed.tolist(),
        'duration_s': float(times[-1]-times[0]), 'planner': 'RRT-Connect + shortcut + TOPP-RA',
        'search': search, 'path_nodes_before_timing': len(dense),
        'collision_mode': collision_mode, 'collision_scope': scope,
        'target_xyz_m': point,
        'orientation_adjustment_deg': orientation_adjustment_deg,
    }
    if collision_mode == 'exact':
        result['mesh_margin_cm'] = float(mesh_margin_cm)
        result['mesh_pose_checks'] = collision.pose_checks
        result['mesh_distance_checks'] = collision.distance_checks
        result['minimum_mesh_clearance_cm'] = collision.minimum_clearance_cm
    return result

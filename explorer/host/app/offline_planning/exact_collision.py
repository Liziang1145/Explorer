# -*- coding: utf-8 -*-
"""可接入离线规划器的 FCL 双臂分件网格碰撞模型。

精确范围：单臂非相邻连杆、夹爪、固定另一臂的 9×9 零件距离，
以及最终全车装配体 v3 的安装板、支架、雷达底座、雷达和完整底盘网格。
保守范围：沿用 StaticCollisionModel 的额外支架约束和关节限位。
不包含：持物、动态环境和连续碰撞证明。
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / '.deps'))
import fcl

import exact_mesh_audit as exact
import vehicle_collision
from vla_motion_planner import CollisionResult, StaticCollisionModel


class ExactMeshCollisionModel(StaticCollisionModel):
    """与 RRT-Connect 兼容的精确机械臂＋保守环境组合模型。"""

    def __init__(self, other_arm_q=None, min_margin_cm=None, mesh_margin_cm=0.0,
                 environment_margin_cm=0.5, opening_m=0.0, **kwargs):
        super().__init__(other_arm_q=other_arm_q, min_margin_cm=min_margin_cm, **kwargs)
        self.mesh_margin = float(mesh_margin_cm)
        self.environment_margin = float(environment_margin_cm)
        self.opening = float(opening_m)
        if not math.isfinite(self.mesh_margin) or self.mesh_margin < 0:
            raise ValueError('网格安全余量必须为有限非负数')
        if not math.isfinite(self.environment_margin) or self.environment_margin < 0:
            raise ValueError('整车环境安全余量必须为有限非负数')
        if not math.isfinite(self.opening) or not 0 <= self.opening <= 0.035:
            raise ValueError('每指开口必须在 0–35 mm 内')
        self.link_ids = tuple(range(9)) if self.check_gripper else tuple(range(6))
        self.mesh_pairs = tuple(pair for pair in exact.PAIRS
                                if pair[0] in self.link_ids and pair[1] in self.link_ids)
        self.pose_checks = 0
        self.distance_checks = 0
        self.broadphase_skips = 0
        self.minimum_clearance_cm = math.inf
        # 另一臂在一次规划中固定；仅构造本次实际需要的另一侧缓存，
        # 避免每个规划及每个并行工作进程都重复构造左右两套对象。
        self._other_cache = {}

    def _objects_and_aabbs(self, q, side):
        frames = exact.transforms(np.asarray(q, dtype=float), self.opening)
        objects, aabbs = {}, {}
        corners = np.asarray([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)])
        for link, (rotation, translation) in frames.items():
            if side == 'right':
                translation = translation + np.asarray([0.0, -0.3051, 0.0])
            objects[link] = fcl.CollisionObject(
                exact.model(link), fcl.Transform(rotation, translation))
            bounds = exact.bounds(link)
            local = bounds[0]+corners*(bounds[1]-bounds[0])
            world = local @ np.asarray(rotation).T + translation
            aabbs[link] = np.asarray([world.min(axis=0), world.max(axis=0)])
        return objects, aabbs

    @staticmethod
    def _aabb_distance(a, b):
        delta = np.maximum(np.maximum(a[0]-b[1], b[0]-a[1]), 0.0)
        return float(np.linalg.norm(delta))

    @staticmethod
    def _distance(a, b):
        return float(fcl.distance(a, b, fcl.DistanceRequest(enable_nearest_points=False),
                                  fcl.DistanceResult()))

    def pose(self, q, side):
        # 粗模型先提供关节限位和环境保守排除；其拒绝结果对精确网格仍保守。
        coarse = super().pose(q, side)
        if not coarse.ok:
            return coarse
        other_side = 'right' if side == 'left' else 'left'
        own, own_aabb = self._objects_and_aabbs(q, side)
        if other_side not in self._other_cache:
            self._other_cache[other_side] = self._objects_and_aabbs(
                self.other_arm_q[other_side], other_side)
        other, other_aabb = self._other_cache[other_side]
        best = math.inf
        worst_pair = None
        own_bounds = np.asarray([own_aabb[index] for index in range(9)])
        other_bounds = np.asarray([other_aabb[index] for index in range(9)])
        pairs = np.asarray(self.mesh_pairs)
        # 批量计算 AABB 安全下界，精查顺序与标量版本完全一致。
        a, b = own_bounds[pairs[:, 0]], own_bounds[pairs[:, 1]]
        delta = np.maximum(np.maximum(a[:, 0]-b[:, 1], b[:, 0]-a[:, 1]), 0.0)
        lower = np.linalg.norm(delta, axis=1)
        for pair_index, (a, b) in enumerate(self.mesh_pairs):
            if lower[pair_index] >= best:
                self.broadphase_skips += 1
                continue
            distance = self._distance(own[a], own[b])
            self.distance_checks += 1
            if distance < best:
                best, worst_pair = distance, f'自身 link{a}–link{b}'
        if self.mesh_margin > self.min_margin:
            count = len(self.link_ids)
            own_checked = np.asarray([own_aabb[index] for index in self.link_ids])
            other_checked = np.asarray([other_aabb[index] for index in self.link_ids])
            a = np.repeat(own_checked, count, axis=0)
            b = np.tile(other_checked, (count, 1, 1))
            delta = np.maximum(np.maximum(a[:, 0]-b[:, 1], b[:, 0]-a[:, 1]), 0.0)
            lower = np.linalg.norm(delta, axis=1)
            for ai, a in enumerate(self.link_ids):
                for bi, b in enumerate(self.link_ids):
                    if lower[ai*count+bi] >= best:
                        self.broadphase_skips += 1
                        continue
                    distance = self._distance(own[a], other[b])
                    self.distance_checks += 1
                    if distance < best:
                        best, worst_pair = distance, f'双臂 {side} link{a}–{other_side} link{b}'
        else:
            self.broadphase_skips += len(self.link_ids)**2
        body_best, body_pair = math.inf, None
        lidar_best, lidar_pair = math.inf, None
        for link in self.link_ids:
            # body 已包含雷达、底座、支架与完整底盘，正常姿态不重复检查雷达。
            distance = vehicle_collision.distance(own[link], 'body')
            self.distance_checks += 1
            # 固定 arm_base 与 v3 安装板为设计装配贴合，不参与运动余量判定。
            if link > 0 and distance < body_best:
                body_best, body_pair = distance, f'完整车身–link{link}'
            # 仅车身余量不足时追加雷达距离，用于给出明确的危险位置诊断。
            if distance < self.environment_margin / 100.0:
                lidar_distance = vehicle_collision.distance(own[link], 'lidar')
                self.distance_checks += 1
                if lidar_distance < lidar_best:
                    lidar_best, lidar_pair = lidar_distance, f'雷达／底座–link{link}'
        if lidar_best <= body_best + 1e-12 and lidar_best < self.environment_margin / 100.0:
            environment_best, environment_pair = lidar_best, lidar_pair
        else:
            environment_best, environment_pair = body_best, body_pair
        self.pose_checks += 1
        margin_cm = best * 100.0
        environment_cm = environment_best * 100.0
        self.minimum_clearance_cm = min(self.minimum_clearance_cm, margin_cm, environment_cm)
        if not math.isfinite(margin_cm) or not math.isfinite(environment_cm):
            return CollisionResult(False, 'FCL 网格距离计算产生非有限余量', -math.inf)
        if margin_cm < self.mesh_margin:
            return CollisionResult(
                False, f'{worst_pair} 网格余量 {margin_cm:.3f} cm 不足', margin_cm)
        if environment_cm < self.environment_margin:
            return CollisionResult(
                False, f'{environment_pair} 余量 {environment_cm:.3f} cm 不足', environment_cm)
        return CollisionResult(True, '双臂分件＋支架／雷达底座／完整底盘网格检查通过',
                               min(coarse.margin_cm, margin_cm, environment_cm))


_WORKER_MODEL = None


def _init_pose_worker(other_arm_q, min_margin_cm, mesh_margin_cm, environment_margin_cm,
                      check_gripper, opening_m):
    global _WORKER_MODEL
    _WORKER_MODEL = ExactMeshCollisionModel(
        other_arm_q=other_arm_q, min_margin_cm=min_margin_cm,
        mesh_margin_cm=mesh_margin_cm, environment_margin_cm=environment_margin_cm,
        check_gripper=check_gripper, opening_m=opening_m)


def _pose_worker(task):
    side, q = task
    before = _WORKER_MODEL.distance_checks
    result = _WORKER_MODEL.pose(q, side)
    return result, _WORKER_MODEL.distance_checks-before


def check_poses_parallel(collision, poses, side, workers):
    """并行复核相互独立的位形；进程内复用 FCL 环境，顺序与串行结果一致。"""
    from concurrent.futures import ProcessPoolExecutor
    poses = list(poses)
    if workers <= 1 or len(poses) <= 1:
        return [collision.pose(q, side) for q in poses]
    with ProcessPoolExecutor(
            max_workers=workers, initializer=_init_pose_worker,
            initargs=(collision.other_arm_q, collision.min_margin,
                      collision.mesh_margin, collision.environment_margin,
                      collision.check_gripper, collision.opening)) as pool:
        results = list(pool.map(_pose_worker, [(side, q) for q in poses], chunksize=1))
    collision.pose_checks += len(results)
    collision.distance_checks += sum(item[1] for item in results)
    collision.minimum_clearance_cm = min(
        collision.minimum_clearance_cm,
        min(item[0].margin_cm for item in results))
    return [item[0] for item in results]

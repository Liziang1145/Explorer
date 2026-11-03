# -*- coding: utf-8 -*-
"""最终全车装配体 v3 的静态三角形网格碰撞环境。

环境网格以车顶部平面中心为原点，X 右、Y 前、Z 上；机械臂 FCL 对象
位于左臂原生局部系。这里只做一次坐标变换，右臂基座间距由
ExactMeshCollisionModel 统一施加。安装板、支架、雷达、雷达底座和完整
底盘均保留，不删除安装区域，也不随机抽面。
"""
from pathlib import Path
import os
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / '.deps'))
import fcl

# 默认采用逐 CAD 分件的保守凸包；需要原始网格审计时设 VEHICLE_MESH_MODE=exact。
MESH_MODE = os.environ.get('VEHICLE_MESH_MODE', 'convex').strip().lower()
if MESH_MODE not in ('convex', 'exact'):
    raise ValueError('VEHICLE_MESH_MODE 必须为 convex 或 exact')
CACHE = HERE / '环境网格' / ('v3_vehicle_top_center.npz' if MESH_MODE == 'exact'
                              else 'v3_vehicle_top_center_convex.npz')
LEFT_BASE_B = np.array([-0.15255, 0.18375, 0.005], dtype=float)
# arm_console._FR：原生臂系 -> 项目 B 系。
ARM_TO_B = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
B_TO_ARM = ARM_TO_B.T
ENV_TRANSLATION = -B_TO_ARM @ LEFT_BASE_B
_MODELS = {}
_OBJECTS = {}


def _load(scope='body'):
    if scope in _OBJECTS:
        return _OBJECTS[scope]
    if not CACHE.is_file():
        raise FileNotFoundError(f'找不到最终 v3 环境网格：{CACHE}')
    with np.load(CACHE) as data:
        vertices_b = np.asarray(data['vertices'], dtype=np.float64)
        faces = np.asarray(data['faces'], dtype=np.int32)
    # B 系环境 -> 左臂原生局部系。右侧另一臂沿原生 -Y 偏移 0.3051 m。
    vertices = vertices_b @ B_TO_ARM.T + ENV_TRANSLATION
    centers_b = vertices_b[faces].mean(axis=1)
    if scope == 'lidar':
        # v3 雷达、头平台及其高位支架区域；body 始终检查全部环境，
        # 此 scope 仅用于给危险姿态提供明确的雷达／底座诊断。
        selected = ((centers_b[:, 2] > 0.30) &
                    (centers_b[:, 0] > -0.22) & (centers_b[:, 0] < 0.16) &
                    (centers_b[:, 1] > -0.08) & (centers_b[:, 1] < 0.28))
        faces = faces[selected]
    elif scope != 'body':
        raise ValueError('未知车身碰撞范围')
    if len(faces) == 0:
        raise RuntimeError(f'v3 环境碰撞范围 {scope} 为空')
    model = fcl.BVHModel()
    model.beginModel(len(vertices), len(faces))
    model.addSubModel(vertices, faces)
    model.endModel()
    _MODELS[scope] = model
    _OBJECTS[scope] = fcl.CollisionObject(model, fcl.Transform())
    return _OBJECTS[scope]


def distance(link_object, scope='body'):
    """机械臂单个分件到指定 v3 环境网格的最短距离，米；相交返回负值。"""
    return float(fcl.distance(link_object, _load(scope), fcl.DistanceRequest(
        enable_nearest_points=False), fcl.DistanceResult()))

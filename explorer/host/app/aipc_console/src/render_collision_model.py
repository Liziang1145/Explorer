"""直接渲染 FCL 使用的整车与机械臂网格；不连接设备。"""
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / 'aipc-simulator-ui'), str(HERE / '.deps')]
import trimesh
import arm_console as app
import exact_mesh_audit as exact

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
vehicle = np.load(HERE / '环境网格' / 'v3_vehicle_top_center.npz')
vv, vf = vehicle['vertices'], vehicle['faces']
LEFT_BASE = np.array([-0.15255, 0.18375, 0.005])
FR = np.asarray(app._FR)


def add_mesh(ax, vertices, faces, color, alpha=1.0, stride=1):
    triangles = vertices[faces[::stride]]
    collection = Poly3DCollection(triangles, facecolors=color, edgecolors='none', alpha=alpha)
    ax.add_collection3d(collection)


def draw(ax, q, title, zero=False):
    add_mesh(ax, vv, vf, '#8295a5', 0.28, 10)
    centers = vv[vf].mean(axis=1)
    lidar_faces = vf[(np.abs(centers[:, 0]) < .12) &
                     (centers[:, 1] > .10) & (centers[:, 1] < .40) & (centers[:, 2] > .25)]
    add_mesh(ax, vv, lidar_faces, '#d64b45', 0.65)
    for side, joints in [('left', q), ('right', app.Q_START_RIGHT)]:
        frames = exact.transforms(np.asarray(joints))
        for link, (rotation, translation) in frames.items():
            if side == 'right':
                translation = translation + np.array([0, -.31, 0])
            # 机械臂原生系 → 车顶中心用户系，左右臂沿 X 相隔 30.51 cm。
            rotation = FR @ rotation
            translation = FR @ translation + LEFT_BASE
            name = 'arm_base.STL' if link == 0 else ('gripper_base.STL' if link == 6 else f'link{link}.STL')
            mesh = trimesh.load(exact.MESH / name, process=False)
            vertices = mesh.vertices @ rotation.T + translation
            color = '#e44b3c' if zero and side == 'left' and link == 2 else ('#e89235' if side == 'left' else '#357fc1')
            add_mesh(ax, vertices, mesh.faces, color, 0.95, 2)
    ax.scatter([0], [0], [0], c='#222222', s=24)
    ax.text(0, 0, -.03, '车顶平面中心 (0,0,0)', fontsize=9)
    ax.set_title(title, fontsize=14, weight='bold')
    ax.set_xlabel('X（m）'); ax.set_ylabel('Y（m）'); ax.set_zlabel('Z（m）')
    ax.set_xlim(-.38, .38); ax.set_ylim(-.45, .55); ax.set_zlim(-.48, .62)
    ax.set_box_aspect((.76, 1.0, 1.10))
    ax.view_init(elev=20, azim=-55)
    ax.grid(True, alpha=.18)


fig = plt.figure(figsize=(16, 9), facecolor='#f5f7fa')
ax1 = fig.add_subplot(1, 2, 1, projection='3d')
draw(ax1, [np.radians(v) for v in [0, 3.21, -3.27, .06, -.46, 0]],
     '当前零位｜v3 正向模型', True)
ax2 = fig.add_subplot(1, 2, 2, projection='3d')
draw(ax2, app.Q_START_LEFT, '左臂起始位｜v3 正向模型')
fig.suptitle('最终 v3 环境网格与机械臂对齐预览（尚未恢复执行）', fontsize=18, weight='bold')
fig.text(.5, .025, '灰色：完整车身　红色区域：雷达／底座／立柱　橙色：左臂　蓝色：右臂',
         ha='center', fontsize=12)
fig.tight_layout(rect=(0, .05, 1, .94))
out = HERE / '输出' / 'v3正向整车与机械臂对齐预览.png'
fig.savefig(out, dpi=170, bbox_inches='tight')
print(out)

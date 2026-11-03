# -*- coding: utf-8 -*-
"""生成底盘—支架—双臂坐标约定预览，不连接设备。"""
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'aipc-simulator-ui'))
import arm_console as app
import arm_geometry as geometry

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def cuboid(ax, center, size, color, alpha=0.35):
    c = np.asarray(center)
    s = np.asarray(size)/2
    vertices = np.asarray([[x, y, z] for x in (-s[0], s[0])
                           for y in (-s[1], s[1]) for z in (-s[2], s[2])]) + c
    faces = [[0,1,3,2],[4,5,7,6],[0,1,5,4],[2,3,7,6],[0,2,6,4],[1,3,7,5]]
    ax.add_collection3d(Poly3DCollection(vertices[faces], facecolors=color,
                                        edgecolors='#4c6272', linewidths=0.5, alpha=alpha))


def draw(ax, elev, azim, title):
    # 主坐标系 cm：顶面 Z=44，臂基座 Z=44.5；X/Y 按 V3 CAD 复核值。
    cuboid(ax, (0,0,22), (54.2,68,44), '#7795aa', 0.30)
    ax.plot([-3,3],[-3,3],[44,44], color='#225577', lw=2)
    # arm_geometry 以左臂为局部原点；全车系左臂在 (-15.255,18.375,44.5)。
    # 连杆坐标已经包含左右臂 30.51 cm 间距，只允许整体平移一次。
    offset=np.asarray([-15.255,18.375,44.5])
    for side in ('left','right'):
        base = np.asarray(geometry.ARM_BASE_CM[side]) + offset
        q = app.Q_START_LEFT if side == 'left' else app.Q_START_RIGHT
        for name,a,b,_r0,_r1 in geometry.links_cm(q,side):
            a,b=np.asarray(a)+offset,np.asarray(b)+offset
            ax.plot(*zip(a,b), color='#d66b35' if side=='left' else '#2476b9', lw=7,
                    solid_capstyle='round', alpha=0.88)
        ax.text(*base, '左臂基座' if side=='left' else '右臂基座', fontsize=9)
    for name,a,b in geometry.BRACKET:
        a,b=np.asarray(a)+offset,np.asarray(b)+offset
        ax.plot(*zip(a,b),color='#666666',lw=4)
    # 坐标箭头从顶面中心出发。
    origin=np.asarray([0,0,44.5])
    ax.quiver(*origin,25,0,0,color='#d43d3d',arrow_length_ratio=0.18,lw=2)
    ax.text(27,0,44.5,'+X 右',color='#d43d3d',fontsize=11,weight='bold')
    ax.quiver(*origin,0,32,0,color='#29934a',arrow_length_ratio=0.18,lw=2)
    ax.text(0,34,44.5,'+Y 前／车头',color='#19773a',fontsize=11,weight='bold')
    ax.quiver(*origin,0,0,24,color='#7c43bd',arrow_length_ratio=0.18,lw=2)
    ax.text(0,0,71,'+Z 上',color='#7c43bd',fontsize=11,weight='bold')
    ax.text(0,-36,44,'顶面 Z=44 cm',fontsize=10,ha='center')
    ax.text(0,-36,49,'臂基座 Z=44.5 cm',fontsize=10,ha='center')
    ax.set_title(title,fontsize=14,weight='bold')
    ax.set_xlabel('X 右（cm）');ax.set_ylabel('Y 前（cm）');ax.set_zlabel('Z 上（cm）')
    ax.set_xlim(-60,60);ax.set_ylim(-60,60);ax.set_zlim(0,90)
    ax.set_box_aspect((120,120,90));ax.view_init(elev=elev,azim=azim)
    ax.grid(True,alpha=0.25)


fig=plt.figure(figsize=(17,10),facecolor='#f5f7fa')
for index,(elev,azim,title) in enumerate(((24,-58,'斜视图｜图片右侧为 +Y 车头'),(90,-90,'俯视图｜核对前后与左右'),(0,-90,'正视图｜核对高度基准')),1):
    ax=fig.add_subplot(1,3,index,projection='3d')
    draw(ax,elev,azim,title)
fig.suptitle('全车碰撞模型坐标约定预览（结构示意，非精确STEP渲染）',fontsize=18,weight='bold',y=0.98)
fig.text(0.5,0.025,'底盘顶面 44 cm｜双臂运动学基座 46 cm｜+X 右、+Y 前、+Z 上',
         ha='center',fontsize=12,color='#263d4d')
fig.tight_layout(rect=(0,0.05,1,0.94))
output=HERE/'输出'/'全车坐标约定预览.png'
fig.savefig(output,dpi=170,bbox_inches='tight')
print(output)

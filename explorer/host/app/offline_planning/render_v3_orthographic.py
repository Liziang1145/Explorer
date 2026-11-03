"""最终 v3 车顶中心模型的正／左／俯三视图；与实机装配图核对。"""
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT/'aipc-simulator-ui'), str(HERE/'.deps')]
import trimesh
import arm_console as app
import exact_mesh_audit as exact

vehicle = np.load(HERE/'环境网格'/'v3_vehicle_top_center.npz')
V_ENV, F_ENV = vehicle['vertices'], vehicle['faces'][::6]
LEFT_BASE = np.array([-.15255, .18375, .005])
FR = np.asarray(app._FR)
meshes = [(V_ENV, F_ENV, np.array([155, 174, 190]))]
for side, q, color in [('left', app.Q_START_LEFT, np.array([232, 143, 51])),
                       ('right', app.Q_START_RIGHT, np.array([55, 126, 190]))]:
    frames = exact.transforms(np.asarray(q))
    for link, (r, t) in frames.items():
        if side == 'right':
            t = t + np.array([0, -.31, 0])
        r = FR @ r
        t = FR @ t + LEFT_BASE
        name = 'arm_base.STL' if link == 0 else ('gripper_base.STL' if link == 6 else f'link{link}.STL')
        mesh = trimesh.load(exact.MESH/name, process=False)
        meshes.append((mesh.vertices @ r.T + t, mesh.faces[::2], color))

VIEWS = [
    ('正视｜从车头看向车尾', np.array([1.,0,0]), np.array([0.,0,1]), np.array([0.,1,0])),
    ('左视｜从左侧看向右侧', np.array([0.,1,0]), np.array([0.,0,1]), np.array([-1.,0,0])),
    ('俯视｜车顶中心为原点', np.array([1.,0,0]), np.array([0.,1,0]), np.array([0.,0,1])),
]
W, H = 850, 850
font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 25)
small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
canvas = Image.new('RGB', (W*3, H+70), '#f5f7fa')
for index, (title, ux, uy, depth) in enumerate(VIEWS):
    triangles = []
    colors = []
    depths = []
    for vertices, faces, color in meshes:
        tri = vertices[faces]
        triangles.append(tri)
        colors.extend([color]*len(faces))
        depths.extend(tri.mean(axis=1) @ depth)
    triangles = np.concatenate(triangles)
    depths = np.asarray(depths)
    pu = triangles @ ux
    pv = triangles @ uy
    allv = np.concatenate([m[0] for m in meshes])
    u0,u1 = (allv@ux).min(),(allv@ux).max()
    v0,v1 = (allv@uy).min(),(allv@uy).max()
    scale = min(W*.84/(u1-u0), H*.80/(v1-v0))
    ox,oy = W/2-scale*(u0+u1)/2, H/2+scale*(v0+v1)/2
    image = Image.new('RGB',(W,H),'#f5f7fa')
    draw = ImageDraw.Draw(image)
    for t in np.argsort(depths):
        points = [(pu[t,j]*scale+ox, -pv[t,j]*scale+oy) for j in range(3)]
        a,b,c = triangles[t]
        normal = np.cross(b-a,c-a)
        norm = np.linalg.norm(normal)
        shade = .72 if norm < 1e-12 else .58+.42*abs(float(normal@depth)/norm)
        color = tuple(np.clip(colors[t]*shade,0,255).astype(int))
        draw.polygon(points, fill=color)
    draw.text((22,18),title,font=font,fill='#1d3448')
    draw.text((22,H-42),'橙：左臂　蓝：右臂　灰：v3 环境',font=small,fill='#344d60')
    canvas.paste(image,(index*W,70))
head = ImageDraw.Draw(canvas)
title_font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',31)
head.text((30,15),'最终 v3 碰撞环境三视图｜X 右／Y 车头／Z 上',font=title_font,fill='#172b3c')
out = HERE/'输出'/'v3正左俯对齐核对.png'
canvas.save(out)
print(out)

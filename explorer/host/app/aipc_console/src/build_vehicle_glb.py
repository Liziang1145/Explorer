"""将既有 APEX 示例中的车身、URDF 网格与关节矩阵装配成静态 GLB。"""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / '离线规划' / '.deps'
sys.path.insert(0, str(DEPS))
import trimesh

SOURCE = ROOT / '02_参考资料' / 'APEX_showcase_02_bundle' / 'app' / 'assets'
OUTPUT = ROOT / 'vehicle-assembly-preview' / 'public' / 'models'
OUTPUT.mkdir(parents=True, exist_ok=True)
rig = json.loads((SOURCE / 'rig.json').read_text(encoding='utf-8'))
scene = trimesh.Scene()
materials = {
    '车身原始配色': trimesh.visual.material.PBRMaterial(
        name='车身 · 原始配色', metallicFactor=0.28, roughnessFactor=0.5),
    '机械臂浅灰': trimesh.visual.material.PBRMaterial(
        name='机械臂 · 浅灰结构', baseColorFactor=[0.66, 0.72, 0.75, 1],
        metallicFactor=0.45, roughnessFactor=0.4),
    '机械臂深灰': trimesh.visual.material.PBRMaterial(
        name='机械臂 · 深灰关节', baseColorFactor=[0.16, 0.22, 0.26, 1],
        metallicFactor=0.5, roughnessFactor=0.4),
}

def vertex_array(name):
    return np.fromfile(SOURCE / name, dtype='<f4').reshape(-1, 3).astype(np.float64)

def matrix(values):
    return np.asarray(values, dtype=float).reshape(4, 4).T

# 车身：示例注明 STEP 的 -X 为车头，转到本项目 B 系的 +Y。
pos = vertex_array('data/car-positions.bin')
colors = np.fromfile(SOURCE / 'data/car-colors.bin', dtype=np.uint8).reshape(-1, 3)
indices = np.fromfile(SOURCE / 'data/car-index.bin', dtype='<u4').reshape(-1, 3)
pos -= [(pos[:, i].min() + pos[:, i].max()) / 2 for i in range(3)]
pos[:, 1] -= pos[:, 1].min()
# 车身二进制已按 Three.js 的 Y 向上组织；原 -X 为车头。
# 转成 B 系：B.x=-原z、B.y=-原x、B.z=原y，保持右手系。
rot = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=float)
pos = pos @ rot.T
car = trimesh.Trimesh(vertices=pos, faces=indices, process=False)
car.visual = trimesh.visual.ColorVisuals(car, vertex_colors=colors)
car.visual.material = materials['车身原始配色']
scene.add_geometry(car, node_name='vehicle_body', geom_name='完整车身')

world = {'base_link': np.eye(4)}
for joint in rig['joints']:
    transform = matrix(joint['origin'])
    angle = float(joint.get('q', 0))
    axis = np.asarray(joint.get('axis', [0, 0, 1]), dtype=float)
    world[joint['child']] = world[joint['parent']] @ transform @ trimesh.transformations.rotation_matrix(angle, axis)

for link in rig['links']:
    vertices = vertex_array(link['file'])
    mesh = trimesh.Trimesh(vertices=vertices, faces=np.arange(len(vertices)).reshape(-1, 3), process=False)
    material = materials['机械臂深灰'] if ('base' in link['name'] or 'link6' in link['name'] or 'link7' in link['name'] or 'link8' in link['name']) else materials['机械臂浅灰']
    mesh.visual = trimesh.visual.TextureVisuals(material=material)
    scene.add_geometry(mesh, node_name=link['name'], geom_name=link['name'], transform=world[link['name']] @ matrix(link['visual']))

# 将 B 系 (X右/Y前/Z上) 永久烘焙为 GLB 常用的 Y 向上坐标，
# 使模型脱离展示场景、单独打开时仍然平放。
b_to_glb = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
scene.apply_transform(b_to_glb)
output = OUTPUT / 'apex-complete-vehicle.glb'
output.write_bytes(scene.export(file_type='glb'))
print(f'已导出 {output}，{output.stat().st_size / 1024 / 1024:.1f} MiB，{len(scene.geometry)} 个部件')
print('左臂基座 B 系坐标:', world['left_arm_base'][:3, 3].tolist())
print('右臂基座 B 系坐标:', world['right_arm_base'][:3, 3].tolist())

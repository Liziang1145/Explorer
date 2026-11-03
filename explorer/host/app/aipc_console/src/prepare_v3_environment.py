"""从最终 v3 提取唯一车体环境并旋转到左臂基座系；不连接设备。"""
from pathlib import Path
import json
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / '.deps'))
import trimesh

SOURCE = ROOT / '06_CAD检查_20261030' / '整车装配体v3.glb'
scene = trimesh.load(SOURCE, force='scene', process=False)
arm_geometries = {'1','2','3','4','5','6','7','1_1','2_1','3_1','4_1','5_1','6_1','7_1'}
parts = []
report = []
for node in scene.graph.nodes_geometry:
    transform, geometry_name = scene.graph[node]
    if geometry_name in arm_geometries:
        continue
    mesh = scene.geometry[geometry_name].copy()
    mesh.apply_transform(transform)
    parts.append(mesh)
    report.append({'node': node, 'geometry': geometry_name, 'bounds': mesh.bounds.tolist()})
environment = trimesh.util.concatenate(parts)
# 原始 Z 为左右臂方向，原始 Y 为向上，原始 -X 为车头。
rotation = np.array([[0., 0., 1.], [-1., 0., 0.], [0., 1., 0.]])
# 车顶平面中心：车身上表面原始 Y=0.31365；X/Z 取车身包围盒中心。
top_center_original = np.array([-0.02085, 0.31365, 0.16832])
# link1 的 Y 中心 0.36165 不是基座；运动学基座位于安装面 Y=0.31865。
left_base_original = np.array([-0.20460, 0.31865, 0.01577])
vertices = environment.vertices @ rotation.T - rotation @ top_center_original
out = HERE / '环境网格' / 'v3_vehicle_top_center.npz'
out.parent.mkdir(exist_ok=True)
np.savez_compressed(out, vertices=vertices, faces=environment.faces)
metadata = {'source': str(SOURCE), 'rotation': rotation.tolist(),
            'top_center_original_m': top_center_original.tolist(),
            'left_base_original_m': left_base_original.tolist(),
            'left_base_in_vehicle_m': (rotation @ (left_base_original-top_center_original)).tolist(),
            'bounds_m': [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()],
            'parts': report, 'vertices': len(vertices), 'faces': len(environment.faces)}
(HERE / '输出' / 'v3环境坐标与部件.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in metadata.items() if k != 'parts'}, ensure_ascii=False, indent=2))
print('环境部件数', len(parts), out)

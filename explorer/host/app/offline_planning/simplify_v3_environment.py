"""将最终 v3 车体按 CAD 分件替换为保守凸包；仅离线，不连接设备。

凸包完整包含原分件，不会随机删除碰撞区域。对凹形底盘会额外占据部分
空腔，因此模型更保守，可能拒绝部分实际可行路径，但不会因抽面漏掉障碍。
"""
from pathlib import Path
import json
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / '.deps'))
import trimesh

SOURCE = ROOT / '06_CAD检查_20261030' / '整车装配体v3.glb'
ARM_GEOMETRIES = {'1', '2', '3', '4', '5', '6', '7',
                  '1_1', '2_1', '3_1', '4_1', '5_1', '6_1', '7_1'}
ROTATION = np.array([[0., 0., 1.], [-1., 0., 0.], [0., 1., 0.]])
TOP_CENTER_ORIGINAL = np.array([-0.02085, 0.31365, 0.16832])

scene = trimesh.load(SOURCE, force='scene', process=False)
hulls = []
report = []
for node in scene.graph.nodes_geometry:
    transform, geometry_name = scene.graph[node]
    if geometry_name in ARM_GEOMETRIES:
        continue
    mesh = scene.geometry[geometry_name].copy()
    mesh.apply_transform(transform)
    hull = mesh.convex_hull
    hull.apply_transform(np.vstack((np.hstack((ROTATION, -(ROTATION @ TOP_CENTER_ORIGINAL)[:, None])),
                                    np.array([[0., 0., 0., 1.]]))))
    hulls.append(hull)
    report.append({'node': node, 'geometry': geometry_name,
                   'source_vertices': len(mesh.vertices), 'source_faces': len(mesh.faces),
                   'hull_vertices': len(hull.vertices), 'hull_faces': len(hull.faces),
                   'bounds_m': hull.bounds.tolist()})
environment = trimesh.util.concatenate(hulls)
face_offsets = np.concatenate(([0], np.cumsum([len(hull.faces) for hull in hulls])))
out = HERE / '环境网格' / 'v3_vehicle_top_center_convex.npz'
np.savez_compressed(out, vertices=np.asarray(environment.vertices, dtype=np.float64),
                    faces=np.asarray(environment.faces, dtype=np.int32),
                    face_offsets=np.asarray(face_offsets, dtype=np.int32))
metadata = {'source': str(SOURCE), 'method': '每个独立 CAD 分件的完整三维凸包',
            'conservative': True, 'parts': report,
            'source_faces': sum(item['source_faces'] for item in report),
            'hull_faces': len(environment.faces), 'vertices': len(environment.vertices),
            'bounds_m': [environment.vertices.min(axis=0).tolist(),
                         environment.vertices.max(axis=0).tolist()]}
(HERE / '输出' / 'v3分件凸包简化报告.json').write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in metadata.items() if key != 'parts'},
                 ensure_ascii=False, indent=2))
print(out)

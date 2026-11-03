"""将完整车身按三角面连通域分件，输出尺寸供支架／雷达／底盘核对。"""
from pathlib import Path
import json
import sys
import numpy as np
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / '.deps'))
import trimesh
SOURCE = ROOT / '02_参考资料' / 'APEX_showcase_02_bundle' / 'app' / 'assets'
pos = np.fromfile(SOURCE / 'data/car-positions.bin', dtype='<f4').reshape(-1, 3).astype(np.float64)
faces = np.fromfile(SOURCE / 'data/car-index.bin', dtype='<u4').reshape(-1, 3).astype(np.int32)
pos -= [(pos[:, i].min() + pos[:, i].max()) / 2 for i in range(3)]
pos[:, 1] -= pos[:, 1].min()
rot = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=float)
pos = pos @ rot.T - np.array([0.185, 0.155, 0.446])
mesh = trimesh.Trimesh(vertices=pos, faces=faces, process=False)
components = mesh.split(only_watertight=False)
rows = []
outdir = HERE / '环境网格'
outdir.mkdir(exist_ok=True)
for index, part in enumerate(sorted(components, key=lambda p: len(p.faces), reverse=True)):
    name = f'part_{index:03d}.npz'
    np.savez_compressed(outdir / name, vertices=part.vertices, faces=part.faces)
    rows.append({'index': index, 'file': name, 'vertices': len(part.vertices), 'faces': len(part.faces),
                 'bounds_m': part.bounds.tolist(), 'centroid_m': part.vertices.mean(axis=0).tolist()})
report = HERE / '输出' / '车身连通域分件.json'
report.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
print('分件数量', len(rows))
print(json.dumps(rows[:100], ensure_ascii=False, indent=2))

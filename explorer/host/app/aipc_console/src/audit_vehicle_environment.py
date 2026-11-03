"""核对完整车身网格与双臂的坐标对齐和距离；不连接设备。"""
from pathlib import Path
import json
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / '.deps'))
sys.path.insert(0, str(ROOT / 'aipc-simulator-ui'))
import fcl
import arm_console as app
import exact_mesh_audit as exact

SOURCE = ROOT / '02_参考资料' / 'APEX_showcase_02_bundle' / 'app' / 'assets'
pos = np.fromfile(SOURCE / 'data/car-positions.bin', dtype='<f4').reshape(-1, 3).astype(np.float64)
faces = np.fromfile(SOURCE / 'data/car-index.bin', dtype='<u4').reshape(-1, 3).astype(np.int32)
pos -= [(pos[:, i].min() + pos[:, i].max()) / 2 for i in range(3)]
pos[:, 1] -= pos[:, 1].min()
rot = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=float)
pos = pos @ rot.T
pos -= np.array([0.185, 0.155, 0.446])
model = fcl.BVHModel()
model.beginModel(len(pos), len(faces))
model.addSubModel(pos, faces)
model.endModel()
env = fcl.CollisionObject(model, fcl.Transform())
result = {'bounds_m': [pos.min(axis=0).tolist(), pos.max(axis=0).tolist()], 'cases': []}
for label, q in [('left_start', app.Q_START_LEFT), ('left_pos3', app.Q_LEFT_POS3),
                 ('right_start', app.Q_START_RIGHT), ('zero', [0.0]*6)]:
    for side in (['left'] if label.startswith('left') or label == 'zero' else ['right']):
        frames = exact.transforms(np.asarray(q))
        row = {'case': label, 'side': side, 'links': {}}
        for link, (r, t) in frames.items():
            if side == 'right':
                t = t + np.array([0, -0.3051, 0])
            obj = fcl.CollisionObject(exact.model(link), fcl.Transform(r, t))
            distance = fcl.distance(obj, env, fcl.DistanceRequest(), fcl.DistanceResult())
            row['links'][str(link)] = distance*100
        row['minimum_cm'] = min(row['links'].values())
        result['cases'].append(row)
out = HERE / '输出' / '完整车身网格对齐审计.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))

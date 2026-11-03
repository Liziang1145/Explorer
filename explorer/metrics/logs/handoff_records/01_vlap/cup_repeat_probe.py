import json
import time
import urllib.request

import cv2
import numpy as np
import torch
from ultralytics import YOLO

CAM = 'http://127.0.0.1:8098'
TOKEN = open('/home/apex/md-service/kr260-agent-token').read().strip()
HDR = {'Authorization': 'Bearer ' + TOKEN}
T_B_C = np.array([
    [0.999653806, 0.003395338, 0.026090992, -0.028135471],
    [-0.021072039, -0.490497785, 0.871187633, 0.291114746],
    [0.015755550, -0.871435824, -0.490256431, 0.540246415],
    [0.0, 0.0, 0.0, 1.0],
])


def get(path):
    request = urllib.request.Request(CAM + path, headers=HDR)
    with urllib.request.urlopen(request, timeout=6) as response:
        return response.read(), {k.lower(): v for k, v in response.headers.items()}


fac = json.load(open('/home/apex/semantic_mapping/config/calibration/factory-camera-parameters.json'))
dk, ck = fac['depth_intrinsic'], fac['color_intrinsic']
Kd = np.array([[dk['fx'], 0, dk['cx']], [0, dk['fy'], dk['cy']], [0, 0, 1]], float)
Kc = np.array([[ck['fx'], 0, ck['cx']], [0, ck['fy'], ck['cy']], [0, 0, 1]], float)
Dd = np.array(fac['depth_distortion_opencv'], float)
Dc = np.array(fac['color_distortion_opencv'], float)
R = np.array(fac['depth_to_color_rotation_flat'], float).reshape(3, 3)
t = np.array(fac['depth_to_color_translation_mm'], float) / 1000.0

torch.set_num_threads(4)
torch.set_num_interop_threads(1)
cv2.setNumThreads(1)
model = YOLO('/home/apex/vision_yolo/models/yolo26m-seg.pt', task='segment')
records = []
for index in range(10):
    rgb, hc = get('/frame/camera.jpg')
    dep, hd = get('/frame/depth.raw')
    dw, dh = int(hd['x-frame-width']), int(hd['x-frame-height'])
    scale = float(hd['x-frame-scale-mm'])
    image = cv2.imdecode(np.frombuffer(rgb, np.uint8), cv2.IMREAD_COLOR)
    depth = np.frombuffer(dep, dtype='<u2').reshape(dh, dw)
    result = model.predict(image, device='cpu', imgsz=640, conf=0.25, verbose=False,
                           retina_masks=True, max_det=30)[0]
    cups = [j for j, box in enumerate(result.boxes)
            if result.names[int(box.cls.item())] == 'cup']
    if not cups:
        records.append({'index': index, 'error': 'cup_not_detected'})
        print(json.dumps(records[-1]), flush=True)
        continue
    pick = max(cups, key=lambda j: float(result.boxes[j].conf.item()))
    yy, xx = np.indices((dh, dw))
    pix = np.column_stack((xx.ravel(), yy.ravel())).astype(np.float32).reshape(-1, 1, 2)
    und = cv2.undistortPoints(pix, Kd, Dd).reshape(-1, 2)
    z = depth.astype(np.float64).ravel() * scale / 1000.0
    valid = (depth.ravel() != 0) & (z > 0.15) & (z < 3.0)
    xyz_d = np.column_stack((und, np.ones(len(und)))) * z[:, None]
    xyz_c = xyz_d @ R.T + t
    projected, _ = cv2.projectPoints(xyz_c, np.zeros(3), np.zeros(3), Kc, Dc)
    uv = projected.reshape(-1, 2)
    mask = (result.masks.data[pick].cpu().numpy() > 0.5).astype(np.uint8)
    mask = cv2.erode(mask, np.ones((5, 5), np.uint8)).astype(bool)
    u = np.round(uv[:, 0]).astype(int)
    v = np.round(uv[:, 1]).astype(int)
    inside = np.zeros(len(uv), bool)
    ok = (u >= 0) & (u < mask.shape[1]) & (v >= 0) & (v < mask.shape[0])
    inside[ok] = mask[v[ok], u[ok]]
    points = xyz_c[valid & inside]
    if len(points) < 30:
        records.append({'index': index, 'error': 'insufficient_depth', 'depth_points': len(points)})
        print(json.dumps(records[-1]), flush=True)
        continue
    center_c = np.median(points, axis=0)
    center_b = (T_B_C @ np.append(center_c, 1.0))[:3]
    record = {
        'index': index,
        'confidence': float(result.boxes[pick].conf.item()),
        'depth_points': len(points),
        'color_depth_timestamp_delta_ms': abs(int(hc['x-frame-device-timestamp-us']) - int(hd['x-frame-device-timestamp-us'])) / 1000.0,
        'center_color_optical_m': center_c.tolist(),
        'center_B_m': center_b.tolist(),
        'center_B_mm': (center_b * 1000).tolist(),
    }
    records.append(record)
    print(json.dumps(record), flush=True)
    time.sleep(0.3)

valid_records = [r for r in records if 'center_B_m' in r]
summary = {'requested': 10, 'valid': len(valid_records), 'records': records}
if valid_records:
    values = np.array([r['center_B_mm'] for r in valid_records])
    summary['mean_B_mm'] = values.mean(axis=0).tolist()
    summary['std_B_mm'] = values.std(axis=0, ddof=1).tolist() if len(values) > 1 else [0.0] * 3
    summary['range_B_mm'] = np.ptp(values, axis=0).tolist()
    summary['max_distance_from_mean_mm'] = float(np.linalg.norm(values - values.mean(axis=0), axis=1).max())
    summary['min_depth_points'] = min(r['depth_points'] for r in valid_records)
print('SUMMARY ' + json.dumps(summary), flush=True)

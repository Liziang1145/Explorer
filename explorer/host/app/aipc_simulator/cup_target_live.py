# -*- coding: utf-8 -*-
"""实时彩色图 + YOLO 杯子掩膜 + 原始深度 → B 系三维点。仅 stdout JSON。"""
import json
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

CAM = 'http://127.0.0.1:8098'
TOKEN = Path('/home/apex/md-service/kr260-agent-token').read_text().strip()
HEADERS = {'Authorization': 'Bearer ' + TOKEN}
MODEL = '/home/apex/vision_yolo/models/yolo26m-seg.pt'
FACTORY = '/home/apex/semantic_mapping/config/calibration/factory-camera-parameters.json'
T_B_C = np.array([
    [0.999653806, 0.003395338, 0.026090992, -0.028135471],
    [-0.021072039, -0.490497785, 0.871187633, 0.291114746],
    [0.015755550, -0.871435824, -0.490256431, 0.540246415],
    [0.0, 0.0, 0.0, 1.0],
])
_model = None


def get(path):
    request = urllib.request.Request(CAM + path, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=8) as response:
        return response.read(), {k.lower(): v for k, v in response.headers.items()}


def locate():
    global _model
    started = time.perf_counter()
    request_started_unix = time.time()
    rgb, hc = get('/frame/camera.jpg')
    rgb_received = time.perf_counter()
    raw, hd = get('/frame/depth.raw')
    depth_received = time.perf_counter()
    delta_ms = abs(int(hc['x-frame-device-timestamp-us'])-int(hd['x-frame-device-timestamp-us']))/1000
    if delta_ms > 100:
        raise ValueError(f'彩色与深度帧不同步：{delta_ms:.1f} ms')
    image = cv2.imdecode(np.frombuffer(rgb, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('彩色图像解码失败')
    dw, dh = int(hd['x-frame-width']), int(hd['x-frame-height'])
    scale = float(hd['x-frame-scale-mm'])
    depth = np.frombuffer(raw, dtype='<u2')
    if depth.size != dw*dh:
        raise ValueError('原始深度尺寸与帧头不一致')
    depth = depth.reshape(dh, dw)
    model_prepare_started = time.perf_counter()
    if _model is None:
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        cv2.setNumThreads(1)
        _model = YOLO(MODEL, task='segment')
    inference_started = time.perf_counter()
    result = _model.predict(image, device='cpu', imgsz=640, conf=0.25,
                            verbose=False, retina_masks=True, max_det=30)[0]
    inference_done = time.perf_counter()
    cups = [j for j, box in enumerate(result.boxes)
            if result.names[int(box.cls.item())] == 'cup']
    if not cups:
        raise ValueError('当前彩色帧未识别到杯子')
    pick = max(cups, key=lambda j: float(result.boxes[j].conf.item()))
    factory = json.loads(Path(FACTORY).read_text())
    dk, ck = factory['depth_intrinsic'], factory['color_intrinsic']
    kd = np.array([[dk['fx'], 0, dk['cx']], [0, dk['fy'], dk['cy']], [0, 0, 1]], float)
    kc = np.array([[ck['fx'], 0, ck['cx']], [0, ck['fy'], ck['cy']], [0, 0, 1]], float)
    dd = np.array(factory['depth_distortion_opencv'], float)
    dc = np.array(factory['color_distortion_opencv'], float)
    rotation = np.array(factory['depth_to_color_rotation_flat'], float).reshape(3, 3)
    translation = np.array(factory['depth_to_color_translation_mm'], float)/1000
    yy, xx = np.indices((dh, dw))
    pixels = np.column_stack((xx.ravel(), yy.ravel())).astype(np.float32).reshape(-1, 1, 2)
    undistorted = cv2.undistortPoints(pixels, kd, dd).reshape(-1, 2)
    z = depth.astype(np.float64).ravel()*scale/1000
    valid = (depth.ravel() != 0) & (z > 0.15) & (z < 3.0)
    xyz_d = np.column_stack((undistorted, np.ones(len(undistorted))))*z[:, None]
    xyz_c = xyz_d@rotation.T+translation
    projected, _ = cv2.projectPoints(xyz_c, np.zeros(3), np.zeros(3), kc, dc)
    uv = projected.reshape(-1, 2)
    mask = (result.masks.data[pick].cpu().numpy() > 0.5).astype(np.uint8)
    mask = cv2.erode(mask, np.ones((5, 5), np.uint8)).astype(bool)
    u, v = np.round(uv[:, 0]).astype(int), np.round(uv[:, 1]).astype(int)
    inside = np.zeros(len(uv), bool)
    ok = (u >= 0) & (u < mask.shape[1]) & (v >= 0) & (v < mask.shape[0])
    inside[ok] = mask[v[ok], u[ok]]
    points = xyz_c[valid & inside]
    if len(points) < 30:
        raise ValueError(f'杯子掩膜内有效深度不足：{len(points)} 点')
    center_c = np.median(points, axis=0)
    center_b = (T_B_C@np.append(center_c, 1.0))[:3]
    target_ready = time.perf_counter()
    return {
        'label': 'cup', 'point_b_m': center_b.tolist(),
        'point_color_m': center_c.tolist(), 'timestamp': time.time(),
        'request_started_unix': request_started_unix,
        'camera_device_timestamp_us': int(hc['x-frame-device-timestamp-us']),
        'timing_ms': {
            'rgb_fetch': (rgb_received-started)*1000,
            'depth_fetch': (depth_received-rgb_received)*1000,
            'decode_and_depth_prepare': (model_prepare_started-depth_received)*1000,
            'model_prepare': (inference_started-model_prepare_started)*1000,
            'yolo_inference': (inference_done-inference_started)*1000,
            'coordinate_transform': (target_ready-inference_done)*1000,
            'locate_total': (target_ready-started)*1000,
        },
        'confidence': float(result.boxes[pick].conf.item()),
        'depth_points': len(points), 'color_depth_timestamp_delta_ms': delta_ms,
        'source': 'live_yolo_depth', 'calibration_status': 'candidate_not_activated',
    }


if __name__ == '__main__':
    try:
        print(json.dumps({'ok': True, **locate()}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(2)

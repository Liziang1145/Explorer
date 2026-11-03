# Model provenance and configuration

Weights are **not** bundled. This file declares origin, version, precision and
backend so the deployment can be rebuilt.

## 1. Local language model

| Item | Value |
|---|---|
| Family | Qwen (local deployment) |
| Version used in the reported runs | `qwen3.8-flash-next-iq3_s` |
| Precision | IQ3_S quantisation (GGUF) |
| Runtime | local, no network egress |
| Role | parse a Chinese request into a restricted task JSON |
| Constraints | strict schema; extra fields, unknown actions, non-cup targets and non-left-arm requests are rejected; `temperature=0` |

> The local task-bridge default (`qwen3.6:35b`) is registered separately from the
> model actually used in the measured runs. The deployment build and the measured
> build are **not** the same checkpoint; this is stated rather than smoothed over.

## 2. Segmentation / detection

| Item | Value |
|---|---|
| Model | `yolo26m-seg.pt` |
| Framework | Ultralytics 8.4.x |
| Backend | ROCm GPU (primary), CPU (baseline) |
| Input | 640, batch=1 |
| Reported inference latency | GPU P50 **20.01 ms**; CPU P50 693.93 ms |
| Effect metric | **not yet measured** (mAP / mIoU pending) |

The GPU path is what makes the chain usable: preprocessing, inference and
post-processing are all on the AIPC's integrated GPU, and the CPU baseline is
reported only to quantify that contribution.

## 3. Action-chunk model

| Item | Value |
|---|---|
| Model | SmolVLA (`lerobot`) |
| Input | 1280x720 RGB + 6 joint angles + gripper opening |
| Output | 50 x 7 action chunk (6 joints + gripper) |
| Wiring | **pre-check only** — discrete grid collision check, never executed |
| Status | not connected to physical execution |

## 4. Colour mapping (point cloud)

| Item | Value |
|---|---|
| Backend | ROCm GPU, 2 processes (primary), CPU 4 processes (baseline) |
| Speed-up | **1.864087x** (CPU4 3.860674 s -> ROCM2 2.071080 s) |
| Input | 8 real image tasks, 5 million points each |
| Failure path | falls back to CPU workers on GPU error |

## 5. Licences

| Model | Licence |
|---|---|
| Qwen | per model card |
| YOLO26m-seg | AGPL-3.0 (Ultralytics) |
| SmolVLA / lerobot | Apache-2.0 |

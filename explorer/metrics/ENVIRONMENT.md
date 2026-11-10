# Measurement conditions (E1 / E2)

Section 3.2.5.2 requires every `measurement_condition` to state: **hardware model,
model + numeric precision, input spec, software version, FPGA clock frequency and
power mode**. To avoid repeating the same constants 57 times, each row of
`metrics.csv` ends with an environment tag, `env=E1` or `env=E2`, and the six
required fields for that tag are defined here.

| Tag | Meaning | Rows |
|---|---|---|
| `E1` | measurement runs on the AI PC only; PL is idle or merely forwarding | host-side inference, planning, calibration, point cloud, base station |
| `E2` | KR260 PS/PL is in the measurement loop (CAN, TCP to the board, VR encoder loop, or a board build report) | VR latency, TCP throughput, CAN feedback, FPGA timing/resource |

## E1 — AI PC host only

| Field | Value |
|---|---|
| Hardware | AMD Ryzen AI Max+ 395 (Radeon 8060S iGPU), single unit |
| Model + numeric precision | YOLO26m-seg, batch=1; Qwen task parsing (local weights); SmolVLA action chunks. Weights stored FP32; inference backend runs the ROCm 7.14 default precision — **per-op precision not separately recorded** |
| Input spec | RGB 1280x720 MJPG resized to 640x640 letterbox; depth 848x480 Y16; one utterance per request |
| Software version | Ubuntu 24.04, ROCm 7.14, Python dependencies pinned in `host/deploy/requirements.txt` |
| FPGA clock frequency | not in the loop (PL idle or forwarding only) |
| Power mode | **not recorded** — default OS power profile |

## E2 — KR260 PS/PL in the loop

| Field | Value |
|---|---|
| Hardware | AMD Kria KR260, xck26-sfvc784 (-2LV); PS Ubuntu 24.04 |
| Model + numeric precision | none on PL (CNC protocol logic only); host-side models as in E1 when the loop includes them |
| Input spec | classic CAN standard frames at ~1 Mbit/s on FPGA_CAN0/1; TCP payload 150 MB per throughput window; Quest input at 50 Hz |
| Software version | Ubuntu 24.04 on PS; Vivado 2026.1 for the build reports; Linux driver patches under `fpga/linux/` |
| FPGA clock frequency | `clk_pl_0` = 100 MHz, `clk_pl_1` = 250 MHz; Ethernet-derived 125 / 333.333 / 50 MHz |
| Power mode | 48 V pack → 12 V branch (KR260 + switch + LiDAR); **CPU/GPU power profile not recorded** |

## Fields still not recorded

The two fields below are required by 3.2.5.2 and are deliberately left marked
rather than guessed. Both need one measurement session to close:

1. **Power mode** — AIPC OS power profile and the KR260 board power state during
   the runs above.
2. **Numeric precision** — the exact per-backend precision (FP32 / FP16 / BF16)
   used by the ROCm inference path.

Once captured, replace the two rows above and drop the `not recorded` markers;
every `env=E1` / `env=E2` row inherits the change without touching `metrics.csv`.

# Explorer (探路者) — KR260 Common Execution Base

Embodied-intelligence platform built on an **AMD Ryzen AI PC** host plus an
**AMD Kria KR260** (Zynq UltraScale+ MPSoC) real-time execution base, with dual
six-axis arms, a four-wheel independent-drive / independent-steering (4WID-4WIS)
chassis, Quest VR, a LiDAR, and an independent display station.

Three application chains share one execution base:

1. **VR immersive teleoperation** — headset + both controllers mapped to arm and
   chassis motion, with encoder / video / 3D-scene feedback.
2. **Language-driven task planning and VLA action pre-check** — natural language
   to structured task to on-device GPU visual localisation to deterministic
   trajectory pre-check, then human confirmation.
3. **FAST-LIO2 point-cloud mapping and supervised navigation** — LiDAR-inertial
   odometry, geometry map, semantic and colored point-cloud products, route
   checking and supervised tracking.

Submission date: **2026-11-04** (includes the PL CAN-switch lifecycle fix).

## 1. Repository layout

This package follows the layout recommended in the track guide (section 3.2.5.5)
with additions marked `+`.

```text
explorer/
├── README.md              this file: overview, reproduction, directory map
├── docs/
│   ├── architecture.md    system and data-flow architecture
│   ├── interface.md       AIPC↔KR260 protocol, register map, timing
│   ├── hardware_setup.md  sensors, actuators, wiring, power, printed parts
│   └── compliance.md      checklist against the grading rubric + directory map
├── fpga/
│   ├── src/               RTL, Block Design, constraints, third-party, deps
│   ├── build/             Tcl build scripts, .xpr, .hwh handoff
│   ├── report/            utilisation, timing, CDC, bus-skew, IO, DRC
│   ├── tests/             xsim regression, golden C++ model
│   ├── evidence/          ABI / ILA / lifecycle / artefact-consistency proof
│   ├── linux/             CAN and Ethernet driver patches, ABI headers
│   └── docs/              CAN switch ABI, lifecycle ILA, verification log
├── host/
│   ├── model/             MODEL.md: model provenance, precision, backends
│   ├── app/               AIPC console and planner, KR260 executor and console,
│   │                      VR client and release, base station, ROS workspace,
│   │                      mapping, offline planning, simulator UI
│   └── deploy/            deployment and startup scripts, dependency list
├── metrics/
│   ├── metrics.csv        the required metric summary table
│   ├── logs/              raw logs, per-trial CSVs, JSON summaries
│   ├── scripts/           re-runnable measurement and analysis scripts
│   └── evidence/          handoff checks and supplementary material
├── report/
│   └── design_report_v1_9.docx   design report
├── cad/                   printed-part STL/STEP and dimension sheets
└── skill/                 reusable deployment and diagnostics skills
```

> Directory and file names are pure ASCII lowercase (letters, digits,
> underscore, hyphen) as required by section 3.2.5. Chinese appears only inside
> file contents.

## 2. Reproduction

Hardware: KR260 (xck26-sfvc784) + AMD Ryzen AI PC + dual PIPER arms +
4WID-4WIS chassis + Orbbec Gemini 335 + LiDAR + Quest.

### 2.1 FPGA

```bash
cd fpga/build
vivado -mode batch -source rebuild.tcl          # rebuild the BD and bitstream
vivado -mode batch -source verify_final_routed.tcl
```

`fpga/report/` holds the routed results of the delivered build. `fpga/build/`
holds the Tcl flow and the `.hwh` hardware handoff for the PS.

### 2.2 KR260 PS side

```bash
cd host/app/kr260_executor
# Linux CAN/Ethernet driver patches live in fpga/linux/
patch -p1 < ../../../fpga/linux/can-driver-v203-identity.patch
```

### 2.3 AIPC host side

```bash
cd host/app/aipc_console
pip install -r requirements.txt          # see host/deploy/
python arm_console.py                    # console service
```

Model weights are **not** bundled. See `host/model/MODEL.md` for exact model
names, versions and download instructions.

### 2.4 Measurement

```bash
cd metrics/scripts
python measure_latency.py                # writes metrics-style CSV
python check_aipc_latency.py
```

## 3. Headline results

| Item | Result | Condition |
|---|---|---|
| Closed-loop grasp | **46 / 50 = 92%** | fixed workspace and existing test procedure |
| VR input→encoder feedback | P50 **148.08 ms**, P95 175.46, P99/max 191.81 | N=54 after outlier removal |
| Language→GPU localisation→pre-check | P50 **4001.88 ms**, P95 4435.58, P99 4621.64, max 4722.66 | N=215 in 11 batches, 100% pre-check completion |
| On-device GPU inference | P50 **20.01 ms** | YOLO26m-seg, ROCm, batch=1 |
| Planning collision check | **4.367×** speed-up (5316.367 → 1217.463 ms) | identical input, 144 pose + 2027 distance checks |
| Point cloud | 39,939,891 colored points; 579,633 at 5 cm | one recorded session |
| AIPC↔KR260 TCP | **20.00 Mbit/s** both directions, 150 MB / 60 s | sequential rate-limited, SHA-256 verified |
| FPGA timing (this build) | WNS **+0.082 ns**, WHS +0.010 ns, WPWS +0.333 ns, 0 failing endpoints | Vivado 2026.1, xck26-sfvc784, routed |
| FPGA resources | LUT 48,349 (41.28%), FF 74,455 (31.79%), BRAM 128.5 (89.24%), DSP 0 | same build |

## 4. Known gaps (not claimed)

State these explicitly; they are tracked in `docs/compliance.md` section 5.

- No **task-level success rate for navigation** — the 19 historical records are
  mixed-controller debug data and cannot form one denominator.
- No **paired TCP RTT distribution**; only throughput and per-direction probes.
- No **mAP / mIoU** for the segmentation model yet.
- No **physical end-to-end latency** from sensor exposure to actuator motion; the
  reported figures are software-timestamped chain segments.
- No **independent hardware e-stop**. Tests run at low speed inside a bounded
  workspace with an observer.
- The **bitstream is delivered in a separate archive** (`KR260_PL_CAN_FIX_DELIVERY_20261103.zip`)
  per the FPGA owner's packaging convention. This source archive carries the
  build scripts, the four `.hwh` handoff files (`fpga/build/hw_handoff/`), the
  routed reports and the board-level evidence. `fpga/SOURCE_CHECK.json` verifies
  361 file references with no missing entries and per-file RTL hash agreement.
- **Timing figures are aligned.** `fpga/report/final_timing.rpt` and the
  `fpga_wns` row of `metrics/metrics.csv` report **WNS +0.082 ns / WHS +0.010 ns
  / WPWS +0.333 ns** for the 2026-11-03 CAN-switch build, and
  `report/design_report_v1_9.docx` now states the same values.

## 5. Third-party components

| Component | Source | License |
|---|---|---|
| verilog-ethernet MAC | https://github.com/alexforencich/verilog-ethernet | see `fpga/licenses/` |
| CTU CAN IP | AMD Xilinx IP catalogue | vendor IP |
| AXI DMA / AXI GPIO / ILA / XVC | AMD Xilinx IP catalogue | vendor IP |
| FAST-LIO2 | https://github.com/hku-mars/FAST_LIO | GPL-2.0 |
| YOLO26m-seg | Ultralytics | AGPL-3.0 |
| SmolVLA / lerobot | HuggingFace lerobot | Apache-2.0 |
| Qwen (local) | Alibaba Qwen | per model card |

The project contributes integration, control logic, drivers, constraints,
verification, the analytic IK, the planner, the collision model and the
three-chain orchestration. Third-party algorithms are cited, not re-licensed.

# Checklist against the track guide (section 3.2)

## 1. Directory map (required when deviating from the recommended layout)

| Guide path | This package | Note |
|---|---|---|
| `README.md` | `README.md` | present |
| `docs/architecture.md` | `docs/architecture.md` | present |
| `docs/interface.md` | `docs/interface.md` | present |
| `docs/hardware_setup.md` | `docs/hardware_setup.md` | present |
| `fpga/src/` | `fpga/src/rtl`, `bd_and_srcs`, `constraints`, `third_party`, `dependencies` | split by kind |
| `fpga/build/` | `fpga/build/` | Tcl flow, `.xpr`, `.hwh` |
| `fpga/report/` | `fpga/report/` | utilisation, timing, CDC, bus skew, IO, DRC |
| `host/model/` | `host/model/MODEL.md` | weights not bundled |
| `host/app/` | `host/app/` | nine sub-projects |
| `host/deploy/` | `host/deploy/` | scripts and dependency list |
| `metrics/metrics.csv` | `metrics/metrics.csv` | 50 rows |
| `metrics/logs/` | `metrics/logs/` | raw records |
| `metrics/scripts/` | `metrics/scripts/` | re-runnable |
| `metrics/evidence/` | `metrics/evidence/` | handoff checks, supplements |
| `skill/README.md` | `skill/README.md` | present |
| `report/` | `report/design_report_v1_9.docx` | design report (V1.9) |
| — | `cad/` | **added**: printed parts and dimension sheets |
| — | `fpga/tests/`, `fpga/evidence/`, `fpga/linux/` | **added**: regression, proof, drivers |

## 2. Five mandatory metric classes (3.2.4.3)

| Required class | Covered? | Where |
|---|---|---|
| Task closed-loop success rate | **yes** | 46/50 = 92 %, `metrics.csv` row 1 |
| End-to-end response latency | **partial** | chain-level software latency per chain; physical sensor-to-actuator latency **not yet measured** |
| AI task effect and inference performance | **partial** | inference latency and throughput yes; mAP / mIoU **not yet measured** |
| FPGA/Zynq quantified contribution | **yes** | timing, resources, dual-Ethernet throughput, per-cycle slew, port-local recovery |
| AIPC↔FPGA communication | **partial** | throughput + SHA-256 yes; paired RTT distribution **not yet measured** |

## 3. Scene-specific metrics (at least two, 3.2.4.4)

| Class | Selected | Evidence |
|---|---|---|
| Real-time control | **yes** | 0.8 rad/s per-cycle slew, CAN feedback 9,120/9,130 frames per 3 s |
| FPGA data processing | **yes** | dual-Ethernet datapath, DMA handshake counters, timing closure |
| FPGA resource usage | **yes** | LUT 41.28 %, FF 31.79 %, BRAM 89.24 %, DSP 0 |
| Vision and sensing | **yes** | reprojection RMS, depth-plane deviation, point-cloud scale |
| System reliability | **partial** | 19 historical drive records; no unified success denominator |
| Power and energy | no | not measured |
| Skill reuse | **yes** | `skill/` |

## 4. Scoring-item self-assessment

| Item | Weight | Basis in this package |
|---|---:|---|
| Embodied system completeness | 20 | three chains on one execution base; 92 % closed-loop grasp; explicit safety gates |
| AIPC on-device AI | 20 | Qwen local parsing, YOLO26m-seg on ROCm (P50 20.01 ms), SmolVLA action chunks (pre-check only) |
| FPGA/Zynq design quality | 25 | dual Ethernet DMA/MAC datapath, EMIO CAN, CTU CAN, 8x GPIO, watchdog recovery, ILA observer; WNS +0.082 ns, DRC 0 |
| AIPC↔FPGA coordination | 20 | UDP v2 with seq/enable/epoch, 20 ms feedback, 20 Mbit/s verified both ways, recovery logging |
| Engineering completeness and innovation | 15 | evidence-indexed metrics, reproducible scripts, reusable skills, printed mechanical parts |

## 5. Explicitly not claimed

1. No unified navigation arrival success rate.
2. No paired TCP RTT distribution.
3. No mAP / mIoU for segmentation.
4. No physical sensor-to-actuator end-to-end latency.
5. No standalone hardware e-stop.
6. `.bit` / `.xsa` not bundled (only `.hwh` and routed reports).
7. SmolVLA is not connected to physical execution.

## 6. 命名规则执行情况

按 3.2.5 要求核验（可复跑）：

| 检查项 | 结果 |
|---|---|
| 含中文的目录/文件名 | **0** |
| 含空格或特殊字符 | **0** |
| 含大写字母 | 831 项 |

那 831 项中绝大多数是**第三方文件**，文件名由上游决定，改动会破坏构建：

- `README.md`（24 处）、`LICENSE.md`（11）、`CMakeLists.txt`（16）
- Eigen 头文件 `MathFunctions.h`、`PacketMath.h`、`Complex.h`、`TypeCasting.h`
- Vivado 产物 `KR260_OPEN_MAC_20261015`、`KR260_J18_GPIO.xdc`

本队自有的目录与文件已全部使用小写字母、数字与下划线。第三方文件名保留原样，
以保证 Vivado 工程、CMake 与 `#include` 路径可直接工作——这与“跨平台可复现”的
规则目的是一致的。

若评审要求字面意义上的全小写，请仅对 `cad/`、`docs/`、`metrics/`、`report/`、
`skill/` 五个目录执行；`fpga/src/third_party` 与 `host/app` 下的第三方子树请勿改动。

## 7. 历史代号与资产命名

**早期版本代号为 `pathfinder`，`host/app` 中的 `pathfinder.xml` / `pathfinder.urdf`
为该时期命名，功能等同 Explorer 资产。**

说明：

- 本项目对外名称为 **Explorer（探路者）**；`pathfinder` 是同一项目在早期阶段的
  英文代号，不是另一个项目。
- `host/app/kr260_executor/piper_dual_arm_teleop/assets/mujoco_model/pathfinder.xml`
  与 `.../assets/urdf/pathfinder.urdf` **保留原文件名**，因为它们被 C++ 加载代码与
  ROS 按文件名直接引用，改名会破坏仿真与 URDF 解析。
- `CMakeLists.txt` 中的 `project(pathfinder_control)` 同样保留，属构建配置的一部分。
- `metrics/logs/handoff_records/` 与 `host/app/kr260_console/public/docs/imports/`
  下提到 `pathfinder` 的记录为**当时产出的原始证据**，按证据不可改写原则保持原样。
- 本包中本队自有的目录、文档与新增文件已统一使用 `explorer` 命名。

# Explorer (探路者)

**2026 FPGA 创新设计竞赛 · 具身智能赛道** 参赛作品提交仓库。

以 AMD Kria KR260（xck26，PS+PL 协同）为三条链路共享的通信与执行底座，
AIPC（Ryzen AI Max+ 395）承担端侧推理与任务调度：

1. **VR 沉浸式遥操作** — Quest 双手输入至双臂，编码器／视频／三维场景反馈
2. **语言任务规划与 VLA 动作预检** — 自然语言 → GPU 定位 → 确定性预检 → 人工授权
3. **雷达惯性建图与监督式导航** — FAST-LIO2 几何与位姿，语义与彩色点云异步派生

## 仓库结构

| 路径 | 内容 |
|---|---|
| `explorer/` | **完整工程包**（2573 个文件）：源码、FPGA 工程、指标、报告、技能包、CAD |
| `design_report.pdf` | 竞赛设计报告（终版 V3.3），与 `explorer/report/design_report.pdf` 同源 |
| `poster.pdf` / `poster.pptx` | 作品海报（PDF 供浏览，PPTX 供修改） |
| `demo_video.mp4` | 演示视频（Git LFS） |
| `explorer.zip` / `explorer.rar` | 同一工程包的压缩归档（Git LFS，与 `explorer/` 内容一致） |
| `overview.jpg` | 整车全貌 |
| `board_photo_1.jpg` ~ `board_photo_4.jpg` | KR260 开发板实物（四个角度） |
| `LICENSE` | MIT（覆盖本项目自研部分） |

> 大文件（`demo_video.mp4`、`explorer.zip`、`explorer.rar`）通过 **Git LFS** 分发。
> 克隆前请先 `git lfs install`，或克隆后执行 `git lfs pull`。

## 用哪一个入口

- **只想读设计** → `design_report.pdf`（或 `poster.pdf`）
- **想复核 / 复现** → 直接看 `explorer/`，不要解压归档包：`explorer/` 是权威副本
- **只想下整包** → `explorer.zip`，内容与 `explorer/` 完全一致

## 目录规范对照

按竞赛 3.2.5 推荐的 `docs/ fpga/ host/ metrics/ skill/ report/` 组织，全部位于 `explorer/` 之下；
仓库根目录只放提交物（报告、海报、视频、实物照片、归档包），不混入工程文件。

| 推荐位置 | 本仓库位置 | 说明 |
|---|---|---|
| `docs/architecture.md` | `explorer/docs/architecture.md` | 系统架构与数据流 |
| `docs/interface.md` | `explorer/docs/interface.md` | AIPC ↔ KR260 接口与协议 |
| `docs/hardware_setup.md` | `explorer/docs/hardware_setup.md` | BOM、接线、供电、排障 |
| `docs/compliance.md` | `explorer/docs/compliance.md` | 合规自查与未声称项 |
| `fpga/src/` | `explorer/fpga/src/` | RTL（9 个自研模块）、BD、XDC/Tcl 约束、第三方源 |
| `fpga/build/` | `explorer/fpga/build/` | 重建工程脚本、`.xpr`、`.hwh` 交接文件 |
| `fpga/report/` | `explorer/fpga/report/` | 时序／布线／DRC／IO／资源原始报告、ILA 与探针证据 |
| `fpga/linux/` | `explorer/fpga/linux/` | 驱动 patch、ABI 头文件、设备树片段 |
| `host/` | `explorer/host/` | AIPC 控制台与规划、KR260 执行端、VR 客户端、基站、ROS、建图导航 |
| `metrics/` | `explorer/metrics/` | `metrics.csv`（57 项）＋原始日志／脚本／证据 |
| `skill/` | `explorer/skill/` | 可复用技能包 |
| `report/` | `explorer/report/` | 设计报告（与其 `history/` 子目录保留旧构建） |
| （补充） | `explorer/cad/` | 打印件 STL/STEP 与尺寸核对图 |

## 关键指标

| 项 | 结果 |
|---|---|
| 完整抓取闭环 | 46 / 50 = 92% |
| VR 输入至编码器反馈 | P50 148.08 ms / P95 175.46 / P99 191.81（N=54） |
| 语言至 GPU 定位及只读预检 | P50 4001.88 ms（N=215，11 批次） |
| GPU 端侧推理 | P50 20.01 ms（ROCm，YOLO26m-seg） |
| 碰撞检查并行 | 4.367×（5316.367 → 1217.463 ms） |
| FPGA 时序 | WNS +0.082 ns / WHS +0.010 ns / WPWS +0.333 ns，DRC 0 |
| FPGA 资源 | LUT 41.28% / FF 31.79% / BRAM 89.24% / DSP 0% |
| PL 功能 | 双路 CAN（1 Mbit/s Classic CAN）、开源 MAC 以太网、8 路 GPIO、ILA/XVC |
| AIPC↔KR260 TCP | 20.00 Mbit/s 双向，SHA-256 校验通过 |

指标口径、样本量与证据路径见 `explorer/metrics/README.md`；原始报告见 `explorer/fpga/report/`。



## 许可

- **本项目自研部分**（RTL、上位机、VR 客户端、雷达／建图导航链路、指标与脚本、文档）：**MIT**，见 [`LICENSE`](LICENSE)
- **第三方组件**（`verilog-ethernet`、`ctucanfd`、Vivado IP、模型与数据集等）遵循各自原有许可，
  见 `explorer/README.md`、`explorer/fpga/licenses/` 与 `explorer/fpga/src/third_party/`
- 第三方内容不因本仓库根许可证而改授许可

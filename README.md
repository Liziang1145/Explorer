# Explorer (探路者)

**FPGA 创新设计竞赛 · 具身智能赛道** 参赛作品提交仓库。

以 AMD Kria KR260 为共同通信与执行底座，AIPC 承担端侧推理与任务调度，
构建三条共享同一执行底座的应用链路：

1. **VR 沉浸式遥操作** — Quest 双手输入至双臂，编码器／视频／三维场景反馈
2. **语言任务规划与 VLA 动作预检** — 自然语言 → GPU 定位 → 确定性预检 → 人工授权
3. **雷达惯性建图与监督式导航** — FAST-LIO2 几何与位姿，语义与彩色点云异步派生

## 仓库结构

| 路径 | 内容 |
|---|---|
| `explorer/` | 完整工程包（源码、FPGA、指标、报告、技能包） |
| `explorer_archive.rar` | 同一工程包的压缩归档 |
| `design_report_v2_0.docx` / `.pdf` | 竞赛技术文档 V2.0 |
| `poster.pptx` | 作品海报 |
| `demo_video.mp4` | 演示视频 |
| `overview.jpg` | 整车全貌 |
| `board_photo_1.jpg` ~ `board_photo_3.jpg` | 开发板实物 |
| `commitment_and_authorization.pdf` | 参赛作品承诺及使用授权书 |

## 快速导航

工程包内：

- `README.md` — 项目概览、复现步骤、目录对照
- `docs/` — 架构、接口、硬件与外设、合规自查
- `fpga/` — RTL、Block Design、约束、构建脚本、时序与资源报告、板级证据
- `host/` — AIPC 控制台与规划、KR260 执行端、VR 客户端、基站、ROS、建图导航
- `metrics/` — `metrics.csv`（57 行指标）与全部原始日志、脚本、证据
- `report/` — 设计报告
- `skill/` — 可复用技能包
- `cad/` — 打印件 STL/STEP 与尺寸核对图

## 关键指标

| 项 | 结果 |
|---|---|
| 完整抓取闭环 | 46 / 50 = 92% |
| VR 输入至编码器反馈 | P50 148.08 ms / P95 175.46 / P99 191.81（N=54） |
| 语言至 GPU 定位及只读预检 | P50 4001.88 ms（N=215，11 批次） |
| GPU 端侧推理 | P50 20.01 ms（ROCm，YOLO26m-seg） |
| 碰撞检查并行 | 4.367×（5316.367 → 1217.463 ms） |
| FPGA 时序 | WNS +0.082 ns / WHS +0.010 ns，DRC 0 |
| FPGA 资源 | LUT 41.28% / FF 31.79% / BRAM 89.24% / DSP 0% |
| AIPC↔KR260 TCP | 20.00 Mbit/s 双向，SHA-256 校验通过 |

## 未声称项

导航无统一成功率；无成对 TCP RTT 分布；无 mAP/mIoU；无物理端到端延迟；
独立硬件急停未接入。详见 `explorer/docs/compliance.md`。

## 许可

第三方组件许可见 `explorer/README.md` 与 `explorer/fpga/licenses/`。

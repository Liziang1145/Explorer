# 自然语言—机械臂控制（VLA）只读链路测量

版本：2026-11-03。工作台入口：**核心指标测量 → 自然语言 → 机械臂（VLA）**。

## 1. 测量对象与安全边界

本页针对一句“用左机械臂抓取镜头前的杯子”，顺序测量：

```text
自然语言原话
  → AI PC 本地千问解析为 {action=grasp, side, target_label=cup}
  → 生产中的 AMD ROCm YOLO26m-seg 进程输出下一帧杯子轮廓
  → 深度相机原始深度帧 + 标定参数 → 相机光学系三维中心
  → 候选相机到车体外参 + 现有 pregrasp_target() → 臂基系 J5 预抓点
  → arm-console /api/vla_motion_execute(stage=preview) 只读轨迹预检
```

测量程序**不调用** `execute`、`intent`、关节发送、夹爪、底盘或 CAN 接口；页面启动只读测试不会让车动。预检成功只表示规划器接受该候选轨迹，不代表机械臂已移动或抓取成功。候选手眼外参尚未完成抓取验收。需要物理端到端结果时，须另行同步记录 KR260/CAN 和实际关节首次运动，并与本页软件链路分开报告。

## 2. 旧数据与新数据

提供的 `pathfinder_latency_readonly_100_20261102` 被导入为**历史 CPU 基线**，原始 100 条 CSV 逐条保存于核心指标数据库新增 `vla` 项目，单独标记 `legacy-cpu-20261102`。其中 87 条通过预检，13 条因 J4～J6 限位的 IK 拒绝。旧测试从目标获取程序开始，不含自然语言；`cup_target_live.py` 明确使用 `device='cpu'`、`conf=.25`、`retina_masks=True`，且每次启动独立进程。旧 `planned_duration_s` 是规划出的运动时长，**不是计算延迟**。

新测量读取正在运行的 `/home/apex/rocm-services-20261102/yolo/gpu_worker.py` 的 `orbbec-rgb` 结果，严格要求 `device=rocm`、`model=YOLO26m-seg`、新帧序号和新鲜时间戳。该生产支路使用 `device=0`、FP16、`imgsz=640`、`conf=.35`、轮廓近似和 `retina_masks=False`。新旧输入、阈值、掩膜表示、进程模型及包含的阶段不同；不能把两批 P50 相除称为 GPU 加速比。

## 3. 指标定义

所有程序内阶段用 AI PC 的 `time.perf_counter()` 计时，单位 ms，百分位采用 **nearest-rank**，同时展示 N、均值、P50/P95/P99、最大值。失败样本仍保存；某阶段未到达时保留缺失，不补零。

| 指标 | 起点 → 终点 | 说明 |
|---|---|---|
| `natural_language_ms` | 向本地千问提交 JSON → 收到响应 | 包括本机 HTTP/模型排队与生成；严格校验 `grasp/left|right/cup` |
| `vision_wait_ms` | 解析完成 → 读到新鲜 GPU 检测帧 | 含生产流水线等待；不是纯网络前向 |
| `gpu_inference_ms` | ROCm worker 的 `model.predict()` | 由生产 GPU 进程报告；**嵌套于**等待段 |
| `gpu_processing_ms` | GPU worker 接到 JPEG → 形成结果 | 同样嵌套于等待段 |
| `depth_fetch_ms` | 请求原始深度 → 获取设备时间戳匹配帧 | RGB 与深度设备戳差 ≤100 ms，否则失败 |
| `geometry_ms` | 杯子轮廓＋深度 → 臂基系 J5 预抓点 | 包括畸变校正、投影、深度筛选、候选外参 |
| `planning_preview_ms` | `stage=preview` 请求 → 预检返回 | 不执行运动；IK 拒绝作为失败保留 |
| `total_ms` | 本轮自然语言调用前 → 预检完成或失败 | 失败时表示失败前已耗时，不混入成功端到端结论 |
| `total_success_ms` | 同上，仅预检成功样本 | 成功链路统计；失败率另报，失败样本不丢弃 |

**不能相加分段的百分位**；GPU 的两项耗时嵌套于 `vision_wait_ms`。YOLO 是异步持续运行的生产进程，采样等待时长还受其调度和相机帧率影响。`source_stamp` 与 `generated_at` 是 AI PC 同主机墙钟；RGB/D 用相机设备时间戳检验配对，未宣称多设备硬件同步。P99 在少量样本时不稳定，验收建议不少于 100 个可比有效样本并保留所有失败。

## 4. 使用步骤与完成标准

1. 确认深度相机供电、画面中有一个可辨认杯子，AI PC 工作台已登录；本地千问与 ROCm YOLO 正在运行。车辆可保持静止。
2. 打开“核心指标测量 → 自然语言 → 机械臂（VLA）”，输入明确的左右臂抓杯原话，先选 1 次冒烟测试，再选 10～100 次。页面不使能机械臂。
3. 运行后看 **GPU** 列是否为 `ROCm`，检查 `depth_fetch_ms`、`geometry_ms` 与预检结果。若 YOLO 只在 CPU 上运行，当前程序直接判失败，不静默降级。
4. 导出本轮 NDJSON 与报告，核对记录数、失败原因、模型和设备。完成标准是逐次记录可追溯、所有成功样本 `gpu_verified=true`、无执行调用，且原三类数据库配额计算未变。

失败类别包括：千问解析不合规、生产 GPU 检测过期或无杯子、RGB-D 不同步、轮廓深度不足、候选外参目标超工作空间、IK 预检拒绝，以及测量后台/数据库不可用。失败不应被删除或算作 0 ms。

## 5. 数据库与程序位置

- 旧与新样本都写入现有 `core-metrics-data` 下新增的 **`vla` 项目**。原三类 `e2e`、`fpga`、`communication` 的权重、50 GB 总预算和相互配额公式保持不变。VLA 单独增加 5 GB，总上限为 55 GB，继续使用相同的 SQLite 分片、FIFO 回收与磁盘余量策略。VLA 记录不会参与旧三类的平均记录大小计算。
- 轮次摘要在 `catalog.sqlite3/tasks`；逐次原始事件为 `vla_legacy_trial` 或 `vla_sample`，原始字段和失败原因均保存。数据库到期可能按原规则回收旧分片；验收时立即导出。
- 新程序：`/home/apex/vla-metrics/vla_service.py`，独立 systemd 服务 `vla-latency.service`，仅监听 `127.0.0.1:18262`。独立进程处理 OpenCV/Numpy，不挤占 `core-metrics.service` 的 768 MiB 内存限制。
- 工作台仍复用 `/api/v1/core-metrics` 同源登录代理；`/vla/start` 和 `/vla/stop` 仅控制只读测量。原始数据写入内部 `127.0.0.1:18261/vla/ingest`，不暴露给工作台页面。
- 算法复用现有 `metrics.distribution()`、`Store`、`stone_grasp_trial.pregrasp_target()` 和 `arm-console` 只读预检接口。

## 6. 复现与版本记录

页面“导出本轮原始 NDJSON”与“下载本轮报告”可直接获取证据。命令行只读检查：

```bash
systemctl status core-metrics vla-latency --no-pager
curl -s http://127.0.0.1:18262/health
curl -s http://127.0.0.1:18262/status
```

复现实验时应记录 AI PC 整机/处理器/内存、ROCm/PyTorch/Ultralytics 版本、千问模型 ID、YOLO 权重哈希、相机内参和候选外参版本、相机输入分辨率、杯子位置/光照、并发服务、样本数与失败率。现有 2026-11-02 CPU 基线的详细条件与原始数据见本工程 `baseline/`。除非后续补齐运动执行和外部物理时间戳，本页不得标成“自然语言到实际抓取”的物理端到端延迟。

## 7. 上线只读冒烟结果（2026-11-03）

实机完成两次单轮只读调用，原始记录已存于 `vla` 分区，ID 分别为 `vla-dff94088fec74977a92431cfded1b453` 和 `vla-7c549e9968374e6494c018aad2cee259`。两次均返回本地千问的 `grasp/left/cup` 草案，取得 `device=rocm` 的 `YOLO26m-seg` 新帧，RGB-D 设备戳差约 33.5 ms，深度轮廓内分别有 1070 和 975 个有效点。第二次测得千问解析 385.32 ms、GPU 推理 18.05 ms、规划预检 3.86 ms、请求到返回总耗时 684.59 ms。两个候选 J5 目标均被现有 IK 工作空间检查拒绝，因此 **成功预检数为 0/2**，也没有实际抓取；这些失败总耗时不得当成成功链路延迟。这里证实了 ROCm 分支和逐段原始记录可工作，后续正式测量需把杯子放在机械臂可达范围，再采不少于 100 次并保留失败率。

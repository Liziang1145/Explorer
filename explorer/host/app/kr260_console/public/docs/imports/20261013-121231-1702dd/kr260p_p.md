# KR260 侧任务卡：AI PC 消息的机械臂执行

> 记录日期：2026-10-13
> 负责人：本人（KR260 / 机械臂侧）；队友（AI PC / 通信侧）

## 任务分工

| 侧 | 负责人 | 任务 |
|---|---|---|
| AI PC | 队友 | 运行通信程序，将 VR 侧数据（或测试数据）打包为 `whole_body_msg`，经 UDP 发往 KR260 |
| KR260 | 本人 | **接收 AI PC 消息 → 解析 → 驱动机械臂执行对应动作**，并回传关节状态 `nav_state_msg` |

## 本人任务的技术链路

```text
UDP 收包（0.0.0.0:6001）
  → whole_body_msg 解析（78 字节，CRC-16 校验）
  → mask 使能位检查
  → 位姿映射（×1.1 放大 + 头显坐标系换算）
  → DLS 逆运动学解算（≤200 次迭代）
  → ArmPlanner 轨迹规划（20Hz）
  → ArmController 控制环（200Hz）
  → SocketCAN 下发 Piper 协议帧（can2，1Mbps）
  → 电机执行
同时：以 50Hz 向 AI PC（192.168.1.5:6000）回传 nav_state_msg（12 关节角 + 底盘位姿）
```

## 接口约定（与队友对齐）

| 参数 | 值 | 说明 |
|---|---|---|
| KR260 接收端口 | UDP 6001 | deploy 绑定 0.0.0.0:6001 收 whole_body_msg |
| AI PC 接收端口 | UDP 6000 | KR260 回传 nav_state_msg 的目标端口 |
| AI PC 地址 | 192.168.1.5（正式）/ 192.168.137.1（直连调试） | teleop_task_runner.cpp 顶部常量可改 |
| 报文格式 | 原自研协议二进制帧（含 CRC-16） | whole_body_msg 78B / nav_state_msg 54B |

## 当前状态（2026-10-13）

- [x] 通信通道从 Unix socket 改为 UDP（teleop_task_runner.h/.cpp）
- [x] 单臂降级补丁：can1（左臂）不在线时 deploy 照常运行右臂
- [ ] 代码上传 KR260 并重新编译（`make deploy -j2`）
- [ ] 与队友联调：确认对方发包的 IP/端口/格式与本表一致
- [ ] 联调通过后接入左臂适配器（udev 加一行绑定 can1 即可）

## 备注

- 队友程序未就绪时，可用伪造数据脚本自行验证"收包→动作"链路（待开发）
- 左臂接入为热插拔式扩展，代码零改动

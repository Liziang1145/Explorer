# Linux 对接与部署验收

本工程提供 FPGA 硬件接口和对接规范。当前电脑不能连接板卡，且没有目标 Ubuntu 24 的完整内核源码及配置，因此本包不宣称新驱动已编译或实机运行。不得把影子测试通过替代这次真实发送通路验收。

## 设备资源

|逻辑设备|控制寄存器|原生 CTU 寄存器|原生IRQ / 管理IRQ|
|---|---|---|---|
|PL_CAN0|80310000/4000|80314000/1000|pl_ps_irq0[3]/[4]，GIC124/125，DT SPI92/93|
|PL_CAN1|80320000/4000|80324000/1000|pl_ps_irq0[5]/[6]，GIC126/127，DT SPI94/95|

32位地址以上均为十六进制。实际驱动可由单一父设备管理每通道64KiB，再把原生窗交给CTU子设备，避免重叠 request_mem_region。两路管理IRQ建议由同一仲裁驱动处理；原生IRQ仅在PL_GENERIC/RUN有效。管理IRQ为高电平，ACTION非零时不可仅写W1C消除，必须完成或取消策略。

IRQ编号依据本工程system_irqs追加In3..In6和AMD映射。来源：[PG201 PL时钟与中断](https://docs.amd.com/r/en-US/pg201-zynq-ultrascale-plus-processing-system/Programmable-Logic-Clocks-and-Interrupts)、[AMD Linux GIC说明](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842191/Linux%20GIC%20Driver)。原有In0 VCU、In1 CAN2、In2 GPIO不移动；以随包XSA/HWH最终检查为准。原网口IRQ组不变。

时钟使用真实PL0时钟99999001 Hz，不要写死125MHz。新增控制器接同一时钟，独立局部复位；原PS与CAN2不复位。引脚：CAN0 J20 pin1 AC12 TX、pin3 AD12 RX；CAN1 J20 pin5 AE10 TX、pin7 AF10 RX。GPIO仍J19，CAN2仍原接口。没有新增占用外部IO。

## SocketCAN 与驱动所有权

复用当前工程CTU 2.2寄存器布局，不要按最新CTU 2.6文档直接修改寄存器。内核参考：[CTU CAN驱动说明](https://docs.kernel.org/networking/device_drivers/can/ctu/ctucanfd-driver.html)。该页面解释平台设备、寄存器和TX echo时序；它不能证明目标内核无需修改即可匹配本项目的受保护窗口。

在现有ctucanfd驱动外增加每通道仲裁胶合层：

1. probe可在PS模式只读识别ID，不能依靠probe期间原生写重置。硬件ID必须0202cafd，ABI/build必须严格匹配。
2. `ndo_open`先申请PL_GENERIC，PREPARE/清队列/CONFIRM，到READY后完成CTU位时序与中断配置，再COMMIT，最后开放netdev队列。
3. 清除`CAN_CTRLMODE_FD`能力，仅公布Classic CAN；配置MODE不得置FDE。硬件拒绝FD缓冲区和无效READY，不能静默把FD降为Classic。经典标准/扩展/RTR按验收表提供。
4. TX echo只有CTU TXOK及对应中断后完成；入队/AXI写成功不等于发出。ERROR/ABORTED/bus-off需要清echo、上报错误，不能伪造成功。
5. 进入PL_ARM前停止SocketCAN TX并清硬件缓冲区/echo；机械臂独占核心时，通用设备应明确DOWN或不可发送，不能让用户以为两种通路可同时输出。
6. 准备返回PS时真正停止PS硬件、清FIFO、清应用/SocketCAN积压，再确认generation。驱动必须实现这一点；仅停用户进程或仅`ip link down`不是硬件清理证据。
7. ARM心跳建议10ms，默认租约100ms；只能在确认控制任务健康且generation一致时续租，不能用脱离任务状态的后台线程掩盖任务失效。
8. 关闭驱动、解绑、重载、全局PL重配置前先关闭AUTO、停止新目标、执行确认式回退PS；所有CAN输出须静止。全局PL复位默认PS，不会替Linux清旧PS FIFO。

建议固定名称PL_CAN0/PL_CAN1，保留原FPGA_CAN0/1/2、USB can0映射。使用设备树路径/硬件身份命名，不依据枚举先后猜名字。原测量驱动仍使用旧ABI，不把新控制区映射到旧驱动。

## 自动策略工作线程

该功能需要部署端实现策略代理，硬件已提供AUTO/RETRY/ACTION/token/IRQ接口。

- AUTO=0：只记录FAULT并保持隔离，等待人工选择PS或PL。
- AUTO=1且ACTION=FALLBACK_PS：锁定通道，停止新目标，PREPARE PS，清旧PS/PL队列，CONFIRM当前generation，等READY并COMMIT PS，重新开放新的PS命令。
- AUTO=1且ACTION=RETRY_PL：停止新PS提交，PREPARE优先PL模式，清PS队列并确认，检查核心初始化；通用模式配置驱动，ARM模式等硬件初始化，COMMIT后只允许新generation新目标。
- 任一步超时/代际变化，读取实际STATE重新决定；不得盲目继续旧步骤。检测到AUTO关闭后停止发起自动切换，已PREPARE的事务由受控取消/人工流程结束。
- 重试只检查链路与控制器，不自动生成机械臂测试动作，不自动发471或失能。优先PL是通路策略，恢复运动由上层状态机授权新目标。
- RETRY_LIMIT=0不限长期次数，RETRY_MS至少1000；次数达到上限停在PS并报告。失败计数/日志和FAULT快照用于现场诊断。

## 部署前和现场验收

先按随包SHA256验证bit/bin/ltx/XSA同版；只烧录经README标明构建通过的文件。更新现有以太网驱动firmware allowlist，不能因改固件名绕过检查。沿用原网络/看门狗/GPIO覆盖，不用新简化设备树覆盖整个PL。

先断开机械臂执行器，使用独立USB-CAN节点，逐路执行：PS旧功能回归、PL_GENERIC标准/扩展/RTR双向、1Mbps时序、RX FIFO与TX echo、无ACK/短暂断线/位错误/bus-off、PS<->PL每种方向切换、旧队列不重放、AUTO开关/优先PL/重试上限及不限次数、Linux策略停止时保持隔离。用示波器/逻辑分析仪验证J20真实引脚，不能仅看内部回环。

随后双路并发+原CAN2+以太网双口持续负载+GPIO，至少1小时，记录bus-off、TEC/REC、所有权generation、事件丢失、应用deadline、网络包计数。200Hz两路各完整位置+夹爪组六帧，必须以USB-CAN物理接收记录对齐seq/trace，不能以候选事件代替。

只有上述通过后，按部署端机械安全流程依次做单臂静止目标、双臂低幅、原应用任务；每一步保留证据。若通路切换仍有旧目标或额外脉冲，立即停止动作并回报状态/事件/波形。通信故障处理不等价于机械急停。

## 本次生命周期修复

新ABI=00020001、BUILD=26110303、CAPS=1ff。现有部署驱动请应用随包身份匹配补丁并实际编译。初始化、停核资格、探针与现场验收按CAN_LIFECYCLE_ILA.md执行。新RTL为两个输出IRQ补齐LEVEL_HIGH元数据；最终HWH检查结果以本次交付报告为准，DT仍核对上述显式IRQ表。

新控制generation在全局PL复位后重新开始，不是跨重启唯一boot_id。Linux必须把自身boot_id/固件重配置代次与generation一起管理，重启/重配置时丢弃持久化和应用旧目标、重新PREPARE确认。硬件不承诺单独识别跨重启重放；旧测量ABI的cookie/快照流程保持原定义。

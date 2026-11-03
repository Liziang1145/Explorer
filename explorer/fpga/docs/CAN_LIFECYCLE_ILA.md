# CAN 生命周期 ILA 与 Linux 对接

对应 ABI=0x00020001 / BUILD=0x26110303 / CAPS=0x1ff。实际验证结果见最终报告，本文件不是现场通过证明。

## 探针

新增 ila_can_lifecycle0/1，每路一个512位probe0、深度1024，PL0=99,999,001Hz，连续窗口约10.24微秒。沿用原XVC，保留旧网口和CAN/GPIO ILA。必须使用与新bit配套LTX。100ms配置窗口由软件日志记录，ILA定位关键跳变前后。

probe0每32位一字，word0=[31:0]，word15=[511:480]。

|字|内容|
|---|---|
|0|标记0x43414e33|
|1|周期低32位，约42.95秒回绕|
|2|generation|
|3|所有权层faults|
|4|核心服务fault_bits|
|5|ERR_STAT采样；16=active，17=passive，18=BOF|
|6|CTU原始REC/TEC寄存器0x030|
|7|MODE缓存，22=ENA|
|8/9/10|APB地址/写数据/读数据|
|11|TX_STATUS|
|12|quiet_count|
|13|所有权、引脚、握手，见下|
|14|服务/APB状态，见下|
|15|队列与编码状态，见下|

word13：target[1:0]，phase[4:2]，owner[6:5]，core_stopped[7]，backend_idle[8]，物理TX[9]，PL_TX[10]，PS_TX[11]，原始RX[12]，core_resetn[13]，initialized[14]，core_operational[15]，stop_core[16]，heartbeat[17]，COMMIT[18]，CONFIRM[19]，PREPARE[20]，host_complete[21]，host_sent[22]，host_pending[23]。

word14：PSEL[0]，PENABLE[1]，bus_state[4:2]，job[7:5]，expired[8]，launched[9]，active[10]，stop_sent[11]，stopped[12]，initialized[13]，enabled[14]，core_operational[15]，poll_pending[16]，counter_pending[17]，PREADY[18]，PSLVERR[19]。完成=PSEL&PENABLE&PREADY。job6为ERR_STAT轮询，7为错误计数，1为主机事务，0为初始化。

word15：queue_count[6:0]，validating[7]，engine_busy[8]，frame_valid[9]，frame_ready[10]，frame_done[11]，frame_result[14:12]，frame_index[17:15]。上述未定义高位保留0。

触发建议：word3 bit1上升；word13 phase进入5/6；word14 job6且APB完成；word7 ENA跳变。触发点放窗口中部。保存bit SHA、boot_id、channel、generation及Linux操作时间。

## 生命周期 ABI

新增只读0xd0 MODE_SHADOW、0xd4 ERR_STAT_SAMPLE、0xd8 CORE_LIFECYCLE（同word14）。0xdc LIFECYCLE_TIMEOUT_MS默认1000，只能在PS/RUN写100..5000，否则拒绝。原128B命令和64B事件布局不变。

新增FAULT bit6=PL接管INIT/READY配置超时、bit7=RUN禁用超时、bit8=RUN启用但未就绪超时。原bit1保留真实运行bus-off隔离。毫秒计时允许一个粒度及APB响应延迟，不能当作纳秒定时。

initialized仅为APB配置完成。core_operational为已启用且采样到非BOF active/passive；隔离期间RX为隐性，因此它不证明外部节点ACK。COMMIT仍检查资格、总线空闲、后端空闲和当前generation确认，RESULT3应等待重试。

成功的MODE disable/reset写先撤销运行资格，后续轮询不会将预期禁用BOF误报；仍须执行停止、清队列及所有权握手，不能长期留在禁用RUN。EVENT_MASK默认0，消费者就绪后再开启，并记录EVENT_LOST和ENGINE_EVENT_LOST基线/增量。

## Linux 部署与验收

1. linux/can-driver-v203-identity.patch基于输入包implementation/driver/can_switch.c；目标6.8.0-1036-xilinx需部署端实际编译。未提供未经编译的伪成品ko。
2. loader路径/SHA按最终新交付更新，不能直接运行硬编码旧bit的load_driver.py。DT地址/IRQ/J20/J19映射保持；IRQ为高电平，新HWH补齐元数据。
3. 保持PS/AUTO0及资格阻塞；按既有停止/加载/回退流程更新，核对新ABI/build/caps。只换bit会被旧驱动严格检查拒绝。
4. 独立CAN测试节点上验证两路冷启动、延迟配置、软件复位、关闭回PS、generic→ARM→PS；记录首错、generation、MODE、ERR_STAT、REC/TEC及两个LOST，不清故障掩盖证据。
5. 真发真收标准/扩展/RTR，核对物理内容与TXOK；测no-ACK、真实bus-off、异常退出、旧队列不重放，再做双路与网络并发长测。
6. 不删除qualification文件绕过验收；通过后由维护者更新资格。原deploy可能自动使能，不用于无运动握手验收。当前没有新板端实测。

AUTO仍需Linux清PS硬件/SocketCAN/应用积压并确认，FPGA不能代替。limit0允许无限长期重试，间隔至少1秒，不重放旧运动目标。

## 现有状态接口的兼容提醒

输入驱动的kcs_state.regs[52]只覆盖0x000..0x0cc，KCS_STATE总长608B；当前status JSON没有0xd0..0xdc。身份补丁不会自动新增这些诊断字段。部署端可在父驱动锁内添加只读sysfs生命周期字段，或定义独立版本化诊断ioctl；不要直接把regs[52]扩大成56而不升级用户态ABI。可先用新ILA定位，避免在驱动运行时以裸MMIO并发操作窗口。

已确认现驱动probe/release显式写EVENT_MASK=0，ARM进入时写0x17，因此上电默认0兼容其事件开启流程。

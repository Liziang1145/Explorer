# KR260 双路 PL CAN / 机械臂通路 ABI v2

实现中；最终固件验收结果以 delivery/README.md 为准。此文档用于 Linux 对接，不能据此假定已实机验证。

## 地址与模式

通道 0 控制窗 0x80310000，通道 1 控制窗 0x80320000，各 64 KiB。0x4000..0x4fff 是该通道 CTU CAN 2.2 的原生寄存器窗口，物理地址分别 0x80314000、0x80324000。原影子测量块 0x80300000、ABI 1.0 保留。

每通道 OWNER：0=PS_GENERIC，1=PL_GENERIC（SocketCAN），2=PL_ARM（硬件队列），3=ISOLATED。同一引脚只有一个控制器可以输出，非所有者 RX 强制隐性。CAN2 不参与此切换，原连接保持。

PHASE：0 RUN，1 DRAIN，2 RESET，3 INIT，4 READY，5 FAULT_DRAIN，6 FAULT。上电 PS_GENERIC、AUTO=0。机械臂模式为经典 CAN 标准帧，约 1 Mbps（99,999,001 Hz /100，约 999,990 bit/s）、75%采样点、SJW=2；PL_GENERIC 可配置底层 Classic CAN 位时序，反馈解码器只适用于约1 Mbps。公开接口禁止 CAN FD。

所有寄存器为 little-endian 32 位，控制写必须完整四字节且对齐。AXI 错误不触发 CPU abort，软件必须读取 RESULT / DENIED；原生窗口非法状态读返回 0xffffffff。控制面需要每通道内核互斥锁，不能同时由多个进程写。

## 寄存器表（通道基址偏移）

|偏移|名称|约定|
|---|---|---|
|000|MAGIC|0x4b434132|
|004|ABI|0x00020001|
|008|BUILD|0x26110303；发布时检查是否变化|
|00c|CAPS|0x1ff：bit0 PS复用，1 PL通用，2 ARM队列，3组合命令，4软件协同自动策略，5完整反馈，6事件，7仅Classic，8生命周期资格/诊断；不代表实机验收|
|010|CLOCK_HZ|99999001|
|014|CHANNEL|0或1|
|018/01c|CYCLE_LO/HI|64位本通道周期；HI-LO-HI重读防翻转；不要与旧测量域相减|
|020|STATE|owner[1:0]，phase[4:2]，target[6:5]，core_resetn[7]，initialized[8]|
|024|GENERATION|每次准备/故障递增；所有确认和命令必须匹配|
|028|FAULTS|粘滞：bit0心跳，1 bus-off，3 APB错误/超时，4核心ID不匹配，5组失败，6配置超时，7受控停核超时，8启动超时，31非法状态|
|02c|OWNER_RESULT|0成功，1非法目标，2过期token，3未空闲/未取得运行资格，4忙/阶段错误，5故障|
|030|TOKEN|写当前generation供确认、提交、心跳使用|
|034|PREPARE|写目标0/1/2；递增generation并暂停后续组|
|038|CONFIRM_QUIESCED|写1；必须已清PS和通用发送队列，再确认TOKEN|
|03c|COMMIT|READY且空闲时写1，再回读STATE；不能省略|
|040|HEARTBEAT|写1；仅RUN ARM且TOKEN匹配时刷新|
|044|FAULT_CLEAR|写1清相应粘滞位；不能使活跃故障消失或自动接通|
|048|AUTO_POLICY|bit0自动开关，bits9:8优先目标1或2；0表示不重试PL；默认0x200|
|04c|LEASE_MS|10..60000，默认100，仅ARM启用|
|050|RETRY_MS|至少1000毫秒，默认1000，长期重试间隔|
|054|RETRY_LIMIT|默认0=不限次数；正数限制自动PL重试请求被接受次数|
|058|RETRY_COUNT/CLEAR|读计数，写1清计数并重新开始间隔|
|05c|ACTION|0无，1需自动回退PS，2需自动重新申请优先PL模式|
|060|QUIET_CYCLES|RX、PS TX、PL TX同时隐性的连续周期数|
|064|FORCED_ISOLATIONS|故障停止2ms仍不完成而强制断开次数|
|068|CORE_ID|要求0x0202cafd；不同CTU版本不能混用|
|06c|ERROR_COUNTERS|CTU原始REC低9位、TEC[24:16]，周期采样；复位后清零|
|070|TX_STATUS|CTU四buffer nibble状态快照|
|074/078/07c|IRQ_STATUS/MASK/W1C|bit0故障，bit1事件；ACTION非零也拉高中断，不受MASK屏蔽|
|080|QUEUE_COUNT|0..64，不含已取出的活动组|
|084|CMD_RESULT|0通过，1模式/忙，2格式，3代际，4通道/kind，5单位/保留字，6CRC，7时间，8序号，9队列满；ffffffff校验中|
|088/08c/090|ACCEPTED/REJECTED/EXPIRED|计数|
|094|ENGINE_STATE|bit0组在执行，bit1正在校验|
|098/09c|FB_VALID/SNAPSHOT_SEQ|20槽快照有效位、序号|
|0a0|SNAPSHOT|写1，原子复制20槽；回读09c确认|
|0a4|EVENT_STATE|count[8:0]、head_ready[9]|
|0a8|EVENT_POP|读取完整事件后写1弹出；空或未就绪无操作|
|0ac|EVENT_LOST|环满及同周期事件来源冲突累计|
|0b0|DENIED_COUNT|原生窗口拒绝/超时数|
|0b4|EVENT_MASK|bit0命令/组，1发送完成，2专用SOF，3接收EOF，4切换/故障；默认0，消费者就绪后显式开启|
|0b8|CONTROL_RESULT|0正常，1写宽度/对齐错误，2参数越界；写任意值清零|
|0bc|ENGINE_EVENT_LOST|队列事件同周期冲突数；总丢失=此值+0ac|
|0c0/0c4/0c8/0cc|FAULT_SNAPSHOT|故障前最后采样REC/TEC、TX_STATUS、故障周期低/高；核心复位不清，下一次故障覆盖|
|0d0/0d4/0d8|MODE_SHADOW/ERR_STAT/CORE_LIFECYCLE|见CAN_LIFECYCLE_ILA.md，资格与APB状态|
|0dc|LIFECYCLE_TIMEOUT_MS|默认1000；仅PS/RUN可写100..5000|
|100..23f|FEEDBACK_SNAPSHOT|20槽，每槽16B：原始wire数据64位，然后PL EOF周期64位|
|800..83f|EVENT_HEAD|64B，只在count>0且ready=1时有效；读后显式POP|
|1000..107f|COMMAND_STAGING|128B记录；校验期间禁止写，必须等完成|
|1080|SUBMIT|写0x41524d32；轮询094校验结束，再读084|
|4000..4fff|CTU_NATIVE|只允许PL_GENERIC访问；PS模式仅识别/状态读取，ARM/切换/复位拒绝|

反馈槽顺序：251..256（0..5）、261..266（6..11）、2a1..2a8（12..19）。原始64位按首字节在最高位表示，例如总线12 34 56 78 90 ab cd ef，低32位读90abcdef、高32位读12345678。反馈没有命令因果seq，不能用最近命令伪造。

## 切换流程

1. 驱动停止接收新目标、停止PS/PL通用提交。PREPARE目标；读取新GENERATION。
2. 清PS硬件TX FIFO、SocketCAN队列、echo skb、应用积压；这是Linux驱动职责，不能只做`ip link down`就假定完成。停止旧PL通用队列；硬件会终止PL CTU待发/重试。
3. TOKEN=新generation，CONFIRM_QUIESCED=1。硬件等待三条信号连续隐性不少于11 bit、APB空闲、所有PL TX buffer无待发/发送，进入隔离、复位、初始化。
4. 等READY。PL_GENERIC可以在READY配置原生位时序/中断，但禁止READY发送命令；PL_ARM已固定初始化。PL核心须先取得core_operational；禁用/复位BOF不计运行故障，但配置超时会隔离。
5. TOKEN匹配后COMMIT=1。确认OWNER/PHASE；RESULT=3时等待空闲及运行资格后重试COMMIT。只在成功后恢复当前模式的新命令。

返回PS同样执行完整流程。不能用MMIO写一个mux选择位绕过队列清理。PS TX仍为低会阻止正常切换；须修复PS侧未停发问题，不能放宽检查。

## 自动开关与用户确认策略

AUTO关闭：故障停止接受后续目标，取消待发，记录故障，隔离；人工可按上述流程选PS或PL。

AUTO开启：FAULT产生ACTION=1/IRQ，由Linux策略代理自动清旧队列、确认并提交PS；PS运行达到RETRY_MS后产生ACTION=2，代理自动准备优先PL、检查初始化并提交。RETRY_LIMIT=0长期不限，但不得突破至少1秒间隔；正值达到上限后留在PS。用户可以随时关闭自动控制，之后只接受人工切换。重试不发送旧目标、无自动失能/0x471帧。

**硬件无法清除PS CAN控制器FIFO，自动回退必须有Linux策略代理。代理没有运行/内核失去调度时保持隔离，不能宣称纯FPGA完成自动回退。** FALLBACK优先于RETRY；代理必须保存审计记录、处理generation变化、停止过期请求。设备掉线时恢复通路不代表机械运动安全恢复，需要上层状态机决定是否提交新目标。

## 128字节命令

沿用旧128B字段布局，magic改4b434132，schema=2、length=128，epoch字段为generation。CRC32C初值ffffffff、反射多项式82f63b78、最终取反，覆盖除92..95的其余124字节。channel为0/1，kind=1位置、2夹爪、3位置+夹爪；flags与reserved必须0，unit_profile=coordinate_profile=1。序号采用32位半空间递增。apply/expire使用本通道周期，apply<expire。

每路64条队列，最多200Hz启动一组。kind1发151、151、155、156、157；kind2发159；kind3六帧组合。151=0101640000000000；155/156/157为两两有符号32位大端mdeg，159为有符号32位大端微米、有符号16位大端mNm、0100。不重复做PS的限位、符号、坐标转换。

入队是原子的，CAN多帧上总线不是可回滚事务。过期未开始则丢弃整组；开始后每帧等待CTU TXOK，遇错/到期停止后续，报告已完成数量并故障隔离。不能把已完成的前几帧撤销。PREPARE和故障清空队列，generation不匹配永不发送。

## 64字节事件

offset0 schema/length=00400002；4 build；8 generation；12 kind(u16)；14 channel(u16)；16 seq；20 aux；24 trace64；32 cycle64；40 data64；48..63保留。

kind0100接受、0101拒绝（aux原因）、0200组开始、0202组成功（aux已完成帧数）、0203到期（aux已完成）、0204组失败（aux[10:8]底层结果，[2:0]已完成）、0301专用实际SOF尝试、0302CTU终态、0402接收EOF、0500切换、0501故障。0302 aux[15:13]结果0TXOK/1ERROR/2ABORTED/3EXPIRED/4APB超时，aux[12:10]帧索引。SOF可能多次重试，不等于TXOK；EOF无因果seq/trace。0402 aux id[10:0]、dlc[15:12]、ACK[16]、local[17]。故障/切换事件优先；任何丢失都读两个LOST计数。

CTU统计在核心复位后归零，软件必须在处理故障/切换时保留前后统计。故障原因与强制隔离累计保留到显式清除或全局PL复位。

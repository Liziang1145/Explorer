# 给部署端 AI 的交接

## 任务与边界

本包修复CAN冷启动/停核误报bus-off，新增生命周期诊断，不改变机械臂编码、网口、CAN2、GPIO、旧测量ABI、J20/J19引脚。已做离线仿真；最终构建结果和固件SHA以包根README、MANIFEST.json为准。没有新板端/机械臂验收，不能把离线通过写成现场通过。不要删除qualification文件绕过阻塞。

## 身份与必须同步的文件

- 新控制ABI 0x00020001、BUILD 0x26110303、CAPS 0x1ff；CLOCK99999001、CTU_ID0202cafd。
- 对输入包implementation/driver/can_switch.c应用linux/can-driver-v203-identity.patch，再用目标内核源码和配置编译、更新模块校验表；包内没有编译好的新ko。
- 对implementation/load_driver.py按随包加载补丁更新firmware-name和SHA；实际dtbo、固件加载服务和现有网口校验表也必须一致。不要删断言、放宽版本检查或直接运行旧脚本。
- 固件、LTX和XSA必须同包，先核对SHA。既有回退文件保留。

## 驱动兼容语义

沿用PREPARE→清旧队列→TOKEN/CONFIRM→READY→配置并启用→COMMIT→回读STATE。RESULT3表示未空闲或尚未取得运行资格，等待后重试；不能只发一次COMMIT或跳过确认。MODE ENA是bit22，初始化APB完成不等于CAN可运行。正常MODE disable/reset撤销资格，仍需后续退出握手。

EVENT_MASK默认0，消费者就绪后再开启所需事件，采集两个LOST基线与增量。0xd0/d4/d8/dc及新超时故障码按CAN_LIFECYCLE_ILA.md处理。原命令128B、事件64B、命令schema2不变。

AUTO继续由Linux协同：先清PS硬件/SocketCAN/应用积压再确认回退，重试间隔至少1秒，limit0无限长期次数；不恢复旧目标。默认PS、AUTO0。现有父驱动的实际AUTO能力需按源码/测试确认，不能因硬件有开关就声称策略代理已实现。

## 现场验收顺序

1. 停止原控制程序，按既有加载和恢复流程更新；先只读核对新身份、两路PS/RUN、AUTO0、初始化与故障。
2. 独立CAN测试节点逐路验证冷启动generic、10us..100ms配置延迟、软件reset、native关闭回PS、generic→ARM→PS；保存首错前后状态与两路ILA。不得先清故障再截图。
3. 真发真收标准/扩展/RTR，核对线上内容与TXOK；测试no-ACK、真实bus-off、异常退出与旧队列不重放，再做双路/网络/CAN2/GPIO回归及至少1小时并发。
4. 通过后由维护者更新qualification和固定版本记录；随后才按既有流程做受控机械臂测试。原deploy可能自动使能，不用它代替无运动握手测试。

本机实际构建工程：D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/KR260_PL_CAN_SWITCH.xpr。压缩包rtl_delta与tests仅供审查，不是完整可搬迁工程或工具环境。不要修改interaction-end或覆盖旧交付。

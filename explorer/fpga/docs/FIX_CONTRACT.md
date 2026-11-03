# CAN 生命周期修复约定（实施中）

输入：KR260_PL_ARM_INTEGRATION_RESULT_20261103，182项SHA通过。原RTL冷启动READY等待约300us、不发任何帧，稳定误入FAULT=2、REC/TEC=0；证据cold_reproduction.txt及baseline_repro波形。根因是CTU 2.2禁用/复位本来就维持s_fc_bus_off，服务层未区分运行资格。

新控制ABI 00020001，BUILD26110303，CAPS1ff（新增bit8生命周期资格/诊断）。命令schema2与64B事件布局不变；旧影子ABI完全不变。设计默认PS、AUTO=0不变；EVENT_MASK默认0，消费者准备好后显式开启。

- APB initialized仅代表内部配置序列完成。
- MODE.ENA为bit22（不是bit7）；按成功APB写和WSTRB跟踪。SW reset清资格，ENA清零先撤销运行资格。
- core_operational要求已启用、读取ERR_STAT为非BOF且error-active/passive。PS/禁用/配置窗口BOF不锁存为运行故障。
- COMMIT到PL要求core_operational、完整空闲窗口及后端空闲；未就绪返回RESULT3，按原ABI等待重试。不能跳过PREPARE/CONFIRM。
- 只有运行中的已就绪PL发生BOF才锁存FAULT bit1，仍执行故障排空/隔离和既有AUTO策略。不能把清故障或轮询抢跑作为修复。
- PL接管INIT/READY超过生命周期超时记FAULT bit6；RUN中受控禁用过久记bit7；RUN中启用但未就绪过久记bit8。默认1000ms，0xdc在PS/RUN可配置100..5000ms。真实bus-off与这些超时分开。
- MODE软件复位/disable作为明确的受控停核事务，因此部署驱动当前stop→release顺序可兼容；仍需真正清队列，MODE写不能替代所有权握手。
- 0xd0为按成功写跟踪的MODE，0xd4为最近ERR_STAT采样，0xd8为生命周期/事务状态，不是跨重启日志。原生窗口可读取真实MODE。

Linux补丁仅更新严格身份匹配，未在目标内核编译。load_driver.py及部署配置的固件路径/SHA必须使用最终新包；不要直接运行旧硬编码脚本，也不要删除资格阻塞文件。先无执行器冷启动/退出和真实TXOK验收，再由部署端更新资格。

本次不处理无因果证据的eth2软件drop，不重写原网络/GPIO/CAN2/编码协议。保留旧交付与interaction-end。

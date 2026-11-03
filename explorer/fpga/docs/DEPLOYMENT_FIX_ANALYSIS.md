# 2026-11-03 部署问题分析与修复

## 结论及证据边界

已复现 FPGA 服务层把 CTU 复位/禁用状态误判成运行期 bus-off。它能够解释现场 CAN0 打开失败、CAN1 偶尔成功但关闭时报错、REC/TEC=0且无发送的组合现象。根因在本次控制层设计；不应以更换收发器、缩短Linux配置延迟或反复清故障来掩盖。

输入包182项SHA核验通过。现场最新事实来自主交接文档第9节及handover-diagnosis.json：两路最后回PS/RUN、AUTO0、无ARM提交；不能把较早只读监测结果当成真实输出验证。

CTU2.2的fault_confinement_fsm.vhd复位进入s_fc_bus_off，禁用时保持该状态。旧can_core_service.v在J_FAULT无资格条件地将ERR_STAT bit18锁存为fault bit1，owner又在INIT/READY立即隔离。旧RTL配合真实CTU模型，在READY不发送、延迟约300us时稳定复现FAULT2、REC/TEC0（314606ns），波形及日志保存在evidence/baseline_repro_*。

以上是源码与离线真实核心仿真证据；没有本次现场ILA，不声称获得了现场逐周期波形证明，也不声称新板端已经通过。

## 修复

- 分离APB初始化完成与核心运行资格。启用且采样到active/passive、非BOF后才允许PL COMMIT。
- MODE disable/reset成功事务撤销资格，受控启停不再把预期BOF报为运行故障。RUN真实BOF仍隔离。
- 配置/禁用/启用未就绪超时采用独立原因码，默认1000ms，PS/RUN可配100..5000ms。
- EVENT_MASK默认关闭，避免消费者启动前诊断环已满。原LOST数属于诊断丢失，不是线上CAN掉包。
- 新增两路生命周期ILA、补齐IRQ高电平元数据；更新ABI/build/caps和Linux严格版本补丁。

新旧BD仅17个字段路径变化：新增两路debug_bus、两个ILA、其时钟和探针连接、两路IRQ元数据。原网络/GPIO/CAN2、地址、J20/J19引脚映射不变。原18个RTL/约束文件哈希已复核保持；未操作interaction-end。

## 交付与现场责任

本次新源代码位于KR260_PL_CAN_FIX_20261103；实际综合布线副本为build_project/KR260_PL_CAN_SWITCH.xpr，根目录同名工程用于长时间仿真，不能误认成带新ILA的最终构建工程。旧KR260_PL_CAN_SWITCH_20261103保留可回退。

最终bit、SHA、资源/时序及各项测试结果以交付README为准。Linux必须同步新的严格身份检查及loader SHA；旧驱动不能直接匹配新bit。接口及探针详见CAN_SWITCH_ABI_V2.md、CAN_LIFECYCLE_ILA.md。

现场仍需先完成无执行器冷启动/关闭/互切、真TXOK与反馈、真实故障退出、双路及网络长测，再更新qualification。不要删除阻塞文件或启动会自动使能的deploy来代替握手验收。当前eth2少量软件drop缺少新因果证据，本次未宣称解决。

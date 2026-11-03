# 本次测试材料说明

- tb_can_lifecycle：真实CTU双节点，冷启动配置延迟10us/100us/1ms/10ms/100ms、软件复位、关闭、generic→ARM→PS、配置超时。通过296项。
- tb_can_service_lifecycle：服务层APB模型定向测试，MODE字节掩码、运行资格、真实BOF、两种RUN超时、停核。通过19项；不能替代真实CTU测试。
- tb_can_actual：真实CTU双节点，六帧ACK、标准/扩展/RTR、RX、仲裁、no-ACK、35次数据位错误诱发bus-off、回PS。通过3007项。
- tb_can_owner/arm_queue/can_axil/shadow：分别68/533/11/49391项通过。
- tb_can_cold_repro：仅用于旧RTL错误复现，期望看到旧版FAULT2；它不是修复版的通过门槛，不能将修复后不再复现误判为失败。原始结果见baseline_repro日志。

仿真通过依据test_pass和断言，不依据进程退出码。这里保留源片段用于审查，压缩包不包含完整Vivado环境/CTU源工程；实际构建工程保存在本机build_project。现场仍须Linux和物理接口验收。

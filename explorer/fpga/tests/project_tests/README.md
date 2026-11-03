# 仿真与黄金参考复核

本目录测试均不访问板卡。CAN仲裁、ACK和注错是CTU RTL双节点的有线与总线模型，不等同实机验证。

在原工程中打开 KR260_PL_CAN_SWITCH.xpr，使用 Vivado 2026.1 XSim：

- sim_can_owner / tb_can_owner：运行1ms，期望test_pass=1、checks=68。
- sim_arm_queue / tb_arm_queue：运行10ms，期望test_pass=1、checks=533。
- sim_shadow_regression / tb_shadow：运行20ms，期望test_pass=1、checks=49391。
- sim_can_actual / tb_can_actual：运行20ms，期望test_pass=1、checks=2979、injected=35。
- tb_can_axil：独立Verilog测试，使用can_axil_endpoint.v，运行1ms，期望test_pass=1、checks=11。补充测试工程保存在原工作目录tests/actual_arbitration_project，归档不依赖该工程。

每项先launch_simulation -simset对应集合 -mode behavioral，再run对应时长，读取get_value -radix unsigned /顶层/test_pass 和 /顶层/checks；必须检查test_pass=1，不能只依据模拟器进程退出码。之后close_sim。final_regression.tcl为前四项串行入口；最终补充结果见evidence中的三个单项result文件。所有测试是确定性的，无随机种子；未宣称覆盖所有协议状态或完成形式证明。

golden_cpp.cpp包含交接冻结的四个编码函数，来源SHA见golden_provenance.json。可在Linux用g++ -std=c++17 -O2 -pthread golden_cpp.cpp -o golden_cpp编译，执行输出与golden_frames.txt核对。golden_vectors.json给出输入。没有板卡/socket真实发送操作。tb_arm_queue嵌入相同黄金帧，验证字节序、负数和边界。

工程归档可以恢复设计文件。Tcl中原工作目录为D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project，迁移其他目录时须同步替换辅助脚本中的根路径；不得误指向旧影子工程。不要把未验证的路径迁移宣称为新环境重建通过。

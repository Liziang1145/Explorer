# 构建与验证记录

日期2026-11-03，Vivado2026.1，器件xck26-sfvc784-2LV-c。只创建新KR260_PL_CAN_FIX_20261103目录，原交付保留。

## 已完成

- 输入包182项SHA核验；旧RTL冷启动300us无发送稳定复现FAULT2、REC/TEC0。
- 修改can_core_service/can_path_owner/can_path_control；ABI20001/BUILD26110303/CAPS1ff；默认事件关闭、生命周期资格/独立超时、IRQ元数据、512位调试总线。
- 新增两路Native ILA，深度1024、宽512，最终BD读回511:0与连线全部正确。每路OOC综合15BRAM。旧ILA不降深度。
- 全部功能回归通过，详见evidence/regression_summary.txt；最终实际核心PASS3007含35次真实位错误注入。
- C11 ABI静态断言通过；未编译目标Linux模块。
- 新旧BD差异17项，仅新探针/连接和IRQ元数据；原本地RTL/约束18个哈希保持。仿真/构建8个本地RTL哈希一致。
- 最终综合synth_design Complete，NEEDS_REFRESH=0；开始impl_1至route_design。

## 已处理的过程问题

1. 初次固定RTL冷测试假定COMMIT一次成功，但后端APB忙时合法返回RESULT3。测试改为按Linux现有约定等待重试，未绕过硬件资格门槛。
2. 新仿真文件集需要显式CTU VHDL library=ctu_can_fd_rtl，已修正。
3. 新ILA默认AXI模式，切换Native后probe宽度被默认回1；重新设置宽512/深1024并读回、验证，无宽度截断后才启动综合。每个IP共3次配置尝试。
4. 首次并行子任务有三个在create_project/tclapp启动阶段报Common17-354 Could not open C for writing，未进入RTL综合。日志在evidence/build_attempt1；串行重试及受影响XVC依赖通过，没有修改工具环境。
5. 补充探针保留位16..19后，两路CAN检查点被标过期，顶层拒绝缺失DCP。仅重置两路CAN及顶层并重建，最终综合通过，无过期依赖。不复制旧DCP冒充新结果。
6. 真实bus-off旧测试在主动重启MODE后过早发送，DENIED增1且injected0。补充等待运行资格后重跑，PASS3007、injected35。没有改弱真实bus-off断言。
7. 精简Model Composer GCC缺标准头；换用现有完整MinGW8.3的gcc -std=c11 -fsyntax-only，ABI断言通过。未安装新环境。

## 待最终报告记录

布局布线、时序、CDC差异、DRC、引脚/复位/ILA连接、bit/bin/XSA一致性及压缩包SHA以最终delivery/README.md和reports为准；本记录中已完成综合不等于位流已交付。

## 实现重试补充

首次4线程place_design在Phase1.2产生hs_err_pid78600.dmp（0字节），日志停止，CPU多次保持571.40625秒不变。确认PID/命令属于本构建后，仅停止该失效子进程。优化检查点kr260_j18_top_opt.dcp已保留，证据在evidence/implementation_attempt1。使用reset_runs impl_1 -from_step place_design，以implementation_threads_stable.tcl设置2线程从布局重试；这不是设计功能改动，最终结果仍需后续签核。


## Final routed checks (2026-11-03)
WNS +0.082 ns, WHS +0.010 ns, WPWS +0.333 ns; TNS/THS/TPWS 0. Fully routed 111276 nets, routing errors 0. LUT 48349/117120 (41.28%), FF 74455/234240 (31.79%), BRAM 128.5/144 (89.24%), DSP 0/1248, IOB 45/189. DRC: 12 ordinary warnings, no errors or critical warnings. All connection, pin migration, functional isolation, probe, Ethernet reset and timing gates passed. CDC: original 95 critical entries unchanged; one added CDC-10 inside encrypted lifecycle ILA1 debug logic. Both ILA output fanouts checked: 17 outputs/17 sinks, debug-only. This specific debug crossing is reviewed and retained unwaived; see reports/cdc_review.json and full CDC report. No board qualification claimed.

Bitgen and XSA export succeeded. Bootgen bin payload matches bit (32-bit byte swap); XSA embedded bit matches exactly; CAN addresses and IRQ metadata verified. Driver identity and loader patches pass git apply --check. Final bin SHA256: 88d72ec35d084acaecfd5ad562f3004b15767273dad42d48de6fbd9452f3cb00. Offline release only; board qualification remains false.

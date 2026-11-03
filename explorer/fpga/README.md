# 最新 FPGA 源码归档（2026-11-04）

对应 2026-11-03 CAN 冷启动/停核误报修复版，ABI 0x00020001、BUILD 0x26110303。实际来源为 KR260_PL_CAN_FIX_20261103/build_project，不是其上级仿真工程。未改变设计逻辑。

## 使用
使用 Vivado 2026.1，安装 xck26 器件支持及 xilinx.com:kr260_som:part0:2.0 板卡定义。将完整包解压到短路径。
在 Vivado Tcl 控制台执行：
```
source C:/your_path/project/open_source.tcl
```
此入口打开工程、设置包内 CTU IP 仓库和实现前置脚本。若需要完整重编译，另执行：
```
source C:/your_path/project/rebuild.tcl
```
重编脚本会重置本副本 synth_1 及下游结果，再综合、实现及生成 bit。请在独立副本中运行。需要后处理/导出时参考 docs 和 project/verify_release.tcl；其中历史比较脚本含原机证据路径，属于审查辅助，不是编译依赖。不要运行历史 integrate_*.tcl 重复叠加设计。

## 内容
project：XPR、完整本地RTL、导入RTL、BD/IP配置、约束、第三方CTU源及许可证、必要生成支持文件、外部引用迁入dependencies。
docs：ABI、Linux对接、根因、ILA与交付指导。文档中D盘路径是原机证据位置，本包入口以本README为准。
linux：头文件与部署端补丁。tests：回归源。reports/evidence：已完成构建的签核和测试证据。
licenses：以太网开源许可证，CTU许可证保留在project/third_party。

## 验证和边界
自动archive_project在历史源导入阶段失败，因此本包使用独立快照及路径迁移。361个XPR显式文件引用存在，18个外部引用迁入包内；已用Vivado重新打开副本并更新编译顺序，所有get_files -all文件存在且均位于包内，见VIVADO_SOURCE_CHECK.txt。
本次未重新综合/布局布线；reports是2026-11-03已交付设计结果，不声称新目录重编已通过或位级可复现。源快照与实际构建本地RTL逐文件哈希一致。原设计时序WNS +0.082ns，WHS +0.010ns；LUT41.28%、FF31.79%、BRAM89.24%、DSP0%。CDC审查例外详见reports/cdc_review.json。
没有打包Vivado工具环境、许可证密钥或本次运行结果目录；生成支持文件保留用于源码完整性，历史baseline_routed.dcp是工程显式引用资料。打开时缺少GeneratedRun或ip_user_files的警告与排除编译结果有关，重新生成即可。原工程及interaction-end未修改。
现场验收状态仍为未完成；固件部署包另见KR260_PL_CAN_FIX_DELIVERY_20261103.zip。

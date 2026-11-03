# 2026-10-13 两端只读检查记录

本文件记录 SSH 实际读取结果，区别于源码模板。没有修改主机配置，没有执行 CAN 启动、发送、控制或业务服务重启。仅在 /tmp 生成源码读取快照并复制到本机。会话中获取的登录凭据不存入文件。

## KR260

- 主机 kria，192.168.137.224，内核6.8.0-1015-xilinx，aarch64。
- 当前 lsusb 没有 1d50:606f，只有根控制器、Microchip Hub/存储等。
- lsmod 已有 can、can_raw、can_dev、xilinx_can、ctucanfd、ctucanfd_platform；没有 gs_usb。
- modinfo gs_usb 指向当前内核内置路径，intree=Y，depends=can-dev，匹配1d50:606f。
- /boot/config 当前 CAN_GS_USB/CAN_RAW/CAN_DEV/CAN_BCM/CAN_ISOTP/CAN_J1939 均为 m。
- can0/can1/can2 没有枚举；fpga_can0、fpga_can1、fpga_can2 为板载接口。
- 监听未见37001/54321；没有发现 udp_link、vr_sim、piper 业务进程。
- TCP5006 的 PID1787 是 snap kria-dashboard 的 bokeh serve，不是 CAN 或 AIPC 协议。

实际 `/etc/udev/rules.d/99-usb-can.rules`：

```udev
ACTION=="add", SUBSYSTEM=="net", ATTRS{serial}=="003900435746570F20383839", NAME="can2"
```

实际 `/etc/udev/rules.d/70-kr260-fpga-can.rules`：

```udev
ACTION=="add", SUBSYSTEM=="net", KERNELS=="ff060000.can", NAME="fpga_can0"
ACTION=="add", SUBSYSTEM=="net", KERNELS=="ff070000.can", NAME="fpga_can1"
ACTION=="add", SUBSYSTEM=="net", KERNELS=="80160000.can", NAME="fpga_can2"
```

检查 /etc/systemd/system、/etc/rc.local、/home/ubuntu/.config/systemd、/etc/network、/etc/netplan 中相关脚本引用未发现匹配。该范围不构成所有可能启动来源的穷举。

## AIPC

- 用户确认192.168.137.2属于AIPC，并授权检查其代码。
- 主机apex，Ubuntu24.04.4，内核7.0.0-38-generic，x86_64；eno1=192.168.137.2/24，Wi-Fi=192.168.6.206。
- 到KR260路由：192.168.137.224 dev eno1 src 192.168.137.2。
- lsusb筛选无1d50或CAN匹配；无CAN接口。modinfo gs_usb 指向7.0.0-38-generic自带模块。
- 当前未发现ROS/arm_station/udp_link/vr_sim控制进程；docker ps无运行容器输出。
- 本次监听检查无37000/54321业务监听；8091为文档服务。
- 用户服务及指定系统启动目录中未发现相关业务脚本引用。

实际 `/etc/udev/rules.d/99-usb-can.rules` 与工程副本一致：

```udev
SUBSYSTEM=="net", ACTION=="add", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="606f", ATTRS{serial}=="003900435746570F20383839", NAME="can0"
SUBSYSTEM=="net", ACTION=="add", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="606f", ATTRS{serial}=="0034004A5746570A20383839", NAME="can1"
```

关键源码 SHA256 与本地复制一致：

```text
785e036cd5bd6af5752da520650bff739c2450e5d79fb63ee9131e4aac10ba14 kr260_link/udp_link.py
fc34e0700ef95f8900241673afdbafb6bca93375d4f40ac35b3a24e0a56f5578 src/robot/inter-process-comm/comm_channel.hpp
753a40337fb406756d3665301d03d817f4e88af6991f0c67436aa0c279d03101 src/robot/inter-process-comm/msgs/whole_body_msg/whole_body_sender.hpp
```

状态是本次观察时刻的快照，设备插拔或服务启动后可能变化。

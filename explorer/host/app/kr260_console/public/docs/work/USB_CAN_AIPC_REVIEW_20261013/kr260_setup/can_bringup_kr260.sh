#!/bin/bash
# KR260 CAN 总线启动脚本
# 用法: sudo bash can_bringup_kr260.sh

set -e

echo "== 1. 检查 gs_usb 驱动 =="
if ! lsmod | grep -q gs_usb; then
    echo "gs_usb 未加载，尝试加载..."
    modprobe gs_usb || { echo "错误: 内核没有 gs_usb 模块，需要编译工程自带驱动"; exit 1; }
fi
lsmod | grep gs_usb

echo "== 2. 当前 CAN 接口 =="
ip -br link show type can || echo "(尚未发现 CAN 接口，请检查适配器是否插好)"

echo "== 3. 配置波特率并启用 =="
# can0 = 底盘 500 kbps
if ip link show can0 &>/dev/null; then
    ip link set can0 down 2>/dev/null || true
    ip link set can0 type can bitrate 500000
    ip link set can0 up
    echo "can0 (底盘, 500k) 已启用"
else
    echo "can0 不存在，跳过（未插底盘适配器时正常）"
fi

# can1/can2 = 左右臂 1 Mbps
for iface in can1 can2; do
    if ip link show $iface &>/dev/null; then
        ip link set $iface down 2>/dev/null || true
        ip link set $iface type can bitrate 1000000
        ip link set $iface up
        echo "$iface (机械臂, 1M) 已启用"
    else
        echo "$iface 不存在，跳过"
    fi
done

echo "== 4. 最终状态 =="
ip -details link show type can
echo "完成。"

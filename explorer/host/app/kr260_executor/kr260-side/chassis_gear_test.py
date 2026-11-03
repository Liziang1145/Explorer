# -*- coding: utf-8 -*-
"""底盘固件档位实测脚本（2026-10-24，一次性诊断用）。

目的：RC 子模式（gear6 同帧 vx+wz）实测"直行时不能转向"，逐档位验证固件行为：
  P1 gear6 vx=0.15 wz=0.0  —— 基线：纯直行（已知正常）
  P2 gear6 vx=0.15 wz=0.3  —— 复现问题：预期直行不转弯
  P3 gear2 vx=0.15 wz=0.3  —— 自由模式候选：观察是否走弧线
  P4 gear8 vx=0.15 vy=0.15 —— 蟹行对角平移（已知正常的对照）
  P5 gear1                 —— 停车
每段 2.5s、段间停车 0.8s，全程约 15s，最高速度 0.15m/s（每段位移 <40cm）。

运行前必须：sudo systemctl stop chassis-relay（避免两个发送方打架）。
运行后记得：sudo systemctl start chassis-relay。
"""
import socket
import struct
import time

CAN_IF = "can0"
VEL_ID = 0x98C4D1D0
IO_ID = 0x98C4D7D0
CAN_EFF_FLAG = 0x80000000

_count = 0
_io_count = 0


def pack_vel(gear, vx, vy, wz):
    global _count
    x = int(vx * 1000) & 0xFFFF
    z = int(wz * 100) & 0xFFFF
    y = int(vy * 1000) & 0xFFFF
    d = bytearray(8)
    d[0] = (gear & 0x0F) | ((x & 0x0F) << 4)
    d[1] = (x >> 4) & 0xFF
    d[2] = ((x >> 12) & 0x0F) | ((z & 0x0F) << 4)
    d[3] = (z >> 4) & 0xFF
    d[4] = ((z >> 12) & 0x0F) | ((y & 0x0F) << 4)
    d[5] = (y >> 4) & 0xFF
    d[6] = ((y >> 12) & 0x0F) | (_count << 4)
    _count = (_count + 1) % 16
    d[7] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[6]
    return bytes(d)


def pack_io_unlock():
    global _io_count
    d = bytearray(8)
    d[0] = 0xFF
    d[0] &= 0xFE
    d[1] = 0xFF
    d[1] &= 0xFE
    d[1] &= 0xFD
    d[1] &= 0xF3
    d[1] &= 0xEF
    d[1] &= 0xDF
    d[1] &= 0xBF
    d[2] = 0
    _io_count = (_io_count + 1) % 16
    d[6] = _io_count << 4
    d[7] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[6]
    return bytes(d)


sock = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
sock.bind((CAN_IF,))


def send(can_id, data):
    sock.send(struct.pack("=IB3x8s", can_id | CAN_EFF_FLAG, 8, data))


def run_phase(label, gear, vx, vy, wz, seconds):
    print(">>> %s  gear=%d vx=%.2f vy=%.2f wz=%.2f  %.1fs" %
          (label, gear, vx, vy, wz, seconds), flush=True)
    t0 = time.monotonic()
    last_io = 0.0
    while time.monotonic() - t0 < seconds:
        now = time.monotonic()
        send(VEL_ID, pack_vel(gear, vx, vy, wz))
        if now - last_io > 1.0:
            send(IO_ID, pack_io_unlock())
            last_io = now
        time.sleep(0.02)


def stop(seconds):
    run_phase("停车", 1, 0.0, 0.0, 0.0, seconds)


try:
    send(IO_ID, pack_io_unlock())
    stop(1.0)
    run_phase("P1 基线直行(gear6 只带vx)", 6, 0.15, 0.0, 0.0, 2.5)
    stop(0.8)
    run_phase("P2 复现问题(gear6 vx+wz)", 6, 0.15, 0.0, 0.3, 2.5)
    stop(0.8)
    run_phase("P3 自由模式(gear2 vx+wz)", 2, 0.15, 0.0, 0.3, 2.5)
    stop(0.8)
    run_phase("P4 蟹行对照(gear8 vx+vy)", 8, 0.15, 0.15, 0.0, 2.5)
    stop(0.8)
    run_phase("P5 纯自旋对照(gear6 只带wz)", 6, 0.0, 0.0, 0.3, 2.5)
    stop(1.0)
finally:
    for _ in range(25):                      # 0.5s 连续停车帧兜底
        send(VEL_ID, pack_vel(1, 0.0, 0.0, 0.0))
        time.sleep(0.02)
    print(">>> 测试结束，已发送停车帧", flush=True)

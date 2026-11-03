#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR260 底盘中继：UDP(54322) → can0 (YHS 帧格式)
- 速度帧 0x98C4D1D0（扩展帧）：vx*1000 / wz(0.01°/s) / vy*1000，三轴拼接 + 滚动计数 + XOR
- IO 帧  0x98C4D7D0：unlock=True（上电解锁，周期性补发防锁回）
- 看门狗：>200ms 无新指令则发零速；>1s 停止发帧
协议（UDP，JSON 文本）：
  {"vx": m/s, "vy": m/s, "wz": rad/s, "enable": true/false}

C22 修复（2026-10-23）：
  1. 整包校验后再原子提交 —— 原来逐字段写入，后面的字段失败会留下"半新半旧"的速度；
  2. 严格类型：只接受 int/float（且非 bool）、必须有限；enable 必须是真 bool
     （原实现 bool('false') 为真，非法 enable 可能被当成使能）；
  3. clamp() 遇 NaN 会返回正的最大限值，现在在进入 clamp 前就拒绝 NaN/Inf；
  4. 看门狗改用 time.monotonic() —— 系统时间回拨不再延长命令有效期；
  5. 错误包进入明确的零速策略（而不是"忽略该包、旧命令继续生效"）；
  6. CAN 发送失败不再让进程崩溃（此前 ENOBUFS 导致 systemd 反复重启）。
"""
import json
import math
import socket
import struct
import threading
import time

CAN_IF = "can0"
UDP_PORT = 54322
VEL_ID = 0x98C4D1D0
IO_ID = 0x98C4D7D0
# 转向控制帧（FW-mid 手册 §4.4 / 原车 yhs_can_control.cpp）：阿克曼转向轮角度通道。
# 档位编码与速度帧不同：05=4T4D / 07=横移。角度精度 0.01°，轮速 0.001m/s。
# 2026-10-25 起仅作备用参考：wz 单位 bug 修正后，速度帧档位 6 同帧 vx+wz 即为
# 手册标准的 4T4D 行进转向方式，RC 子模式已改回单帧方案，不再发转向帧。
STEER_ID = 0x98C4D2D0
WATCHDOG_MS = 200
MAX_VX = 0.8   # m/s 限速
MAX_VY = 0.8
MAX_WZ = 1.0   # rad/s

# wz 打包系数：rad/s → 0.01°/s（手册 §4.4 明确单位为 0.01°/s/bit，且仅在档位 6 有效。
# 曾误用 ×100（0.01 rad/s 假设），比固件期望值小 57.3 倍，表现为"轮子摆好姿势但不转"）
WZ_SCALE = 180.0 / math.pi * 100.0

CAN_EFF_FLAG = 0x80000000

sock_can = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
sock_can.bind((CAN_IF,))

# vx/vy/wz/enable 为经过校验的命令；mono 为该命令接收时刻（单调时钟）
state = {"vx": 0.0, "vy": 0.0, "wz": 0.0, "enable": False, "mono": 0.0, "rc": False}
lock = threading.Lock()
_count = 0
_io_count = 0
_last_send_err = 0.0


def clamp(v, m):
    """限幅。调用前已保证 v 为有限数；这里仍显式拒绝非有限值以防回归。"""
    if not math.isfinite(v):
        return 0.0
    return max(-m, min(m, v))


def _num(msg, key, limit):
    """严格取一个有限数字字段。bool 是 int 的子类，必须排除。"""
    v = msg.get(key, 0)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("%s 必须是数字（收到 %r）" % (key, v))
    v = float(v)
    if not math.isfinite(v):
        raise ValueError("%s 必须是有限值（收到 %r）" % (key, v))
    return clamp(v, limit)


def _bool(msg, key):
    """严格布尔：只接受 JSON true/false，拒绝 'false'、0、'0' 等。"""
    v = msg.get(key, False)
    if type(v) is not bool:
        raise ValueError("%s 必须是布尔值（收到 %r）" % (key, v))
    return v


def parse_command(raw):
    """整包解析 + 校验，返回完整命令字典；任何字段不合法都抛异常（调用方转入零速）。"""
    msg = json.loads(raw.decode())
    if not isinstance(msg, dict):
        raise ValueError("报文必须是 JSON 对象")
    return {"vx": _num(msg, "vx", MAX_VX),
            "vy": _num(msg, "vy", MAX_VY),
            "wz": _num(msg, "wz", MAX_WZ),
            "enable": _bool(msg, "enable"),
            "rc": _bool(msg, "rc"),        # 2026-10-24 RC 遥控车子模式：允许 vx+wz 同时下发
            "mono": time.monotonic()}


def pack_vel(gear, vx, vy, wz):
    global _count
    x = int(vx * 1000) & 0xFFFF
    z = int(wz * WZ_SCALE) & 0xFFFF      # 0.01°/s/bit，仅档位 6 有效
    y = int(vy * 1000) & 0xFFFF
    d = bytearray(8)
    d[0] = (gear & 0x0F) | ((x & 0x0F) << 4)          # gear: 8=横移 6=4T4D 1=驻车
    d[1] = (x >> 4) & 0xFF
    d[2] = ((x >> 12) & 0x0F) | ((z & 0x0F) << 4)
    d[3] = (z >> 4) & 0xFF
    d[4] = ((z >> 12) & 0x0F) | ((y & 0x0F) << 4)
    d[5] = (y >> 4) & 0xFF
    d[6] = ((y >> 12) & 0x0F) | (_count << 4)
    _count = (_count + 1) % 16
    d[7] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[6]
    return bytes(d)


_steer_count = 0
_last_steer_deg = 0.0          # 最近一帧发出的转向轮角度（回正窗口用）
_steer_straighten_until = 0.0  # 回正补发截止时间（单调时钟）


def pack_steer(gear, vel, angle_deg):
    """转向控制帧 0x98C4D2D0：与 yhs_can_control.cpp steering_ctrl_cmdCallBack 逐字节一致。
    vel 单位 m/s（×1000），angle_deg 单位度（×100，0.01°/bit），档位 05=4T4D / 07=横移。"""
    global _steer_count
    v = int(vel * 1000) & 0xFFFF
    a = int(angle_deg * 100) & 0xFFFF
    d = bytearray(8)
    d[0] = (gear & 0x0F) | ((v & 0x0F) << 4)
    d[1] = (v >> 4) & 0xFF
    d[2] = ((v >> 12) & 0x0F) | ((a & 0x0F) << 4)
    d[3] = (a >> 4) & 0xFF
    d[4] = (a >> 12) & 0x0F
    _steer_count = (_steer_count + 1) % 16
    d[6] = _steer_count << 4
    d[7] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[6]
    return bytes(d)


def pack_io_unlock():
    """io_cmd 全 False 仅 unlock=True（灯光全关）"""
    global _io_count
    d = bytearray(8)
    d[0] = 0xFF
    d[0] &= 0xFE          # lamp_ctrl False
    # unlock True → 保持
    d[1] = 0xFF
    d[1] &= 0xFE          # lower_beam False
    d[1] &= 0xFD          # upper_beam False
    d[1] &= 0xF3          # turn_lamp 0
    d[1] &= 0xEF          # braking False
    d[1] &= 0xDF          # clearance False
    d[1] &= 0xBF          # fog False
    d[2] = 0              # speaker 0
    _io_count = (_io_count + 1) % 16
    d[6] = _io_count << 4
    d[7] = d[0] ^ d[1] ^ d[2] ^ d[3] ^ d[4] ^ d[5] ^ d[6]
    return bytes(d)


def send_can(can_id, data):
    """发送一帧。失败只记录、不抛出 —— 否则总线异常会让整个中继退出并反复重启。"""
    global _last_send_err
    frame = struct.pack("=IB3x8s", can_id | CAN_EFF_FLAG, 8, data)
    try:
        sock_can.send(frame)
        return True
    except OSError as exc:
        now = time.monotonic()
        if now - _last_send_err > 2.0:      # 限流打印，避免刷爆日志
            print("[chassis_relay] CAN 发送失败：%s" % exc, flush=True)
            _last_send_err = now
        return False


def udp_loop():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", UDP_PORT))
    print("[chassis_relay] UDP :%d → %s" % (UDP_PORT, CAN_IF), flush=True)
    while True:
        data, _ = s.recvfrom(512)
        try:
            cmd = parse_command(data)
        except Exception as exc:                        # noqa: BLE001
            # 明确零速策略：不保留旧指令，免得一个坏包把上一帧速度"续命"
            print("bad pkt → 零速：", exc, flush=True)
            with lock:
                state.update(vx=0.0, vy=0.0, wz=0.0, enable=False, mono=time.monotonic())
            continue
        with lock:
            state.update(cmd)                            # 校验通过后原子替换整组字段


def can_loop():
    last_io = 0.0
    while True:
        now = time.monotonic()
        with lock:
            vx, vy, wz = state["vx"], state["vy"], state["wz"]
            en, mono = state["enable"], state["mono"]
            rc = state.get("rc", False)
        age_ms = (now - mono) * 1000.0 if mono > 0 else 1e9
        if not en or age_ms > WATCHDOG_MS:
            vx = vy = wz = 0.0
        # 档位（手册 §4.4）：横移=8（vx/vy 有效、wz 无效），4T4D=6（vx/wz 有效、
        # vy 无效），全零=驻车 1。
        # 2026-10-25 重大修正：此前认定"档位 6 同帧 vx+wz 固件忽略 wz"是误判——
        # 真相是 wz 单位错（应为 0.01°/s，误用 0.01 rad/s，小了 57.3 倍）。
        # 单位修正后 RC 子模式回归手册标准方案：档位 6 同帧 vx+wz，固件按
        # 双阿克曼自算四轮转角，行进中即可转向；静止纯 wz = 原地自旋。
        if rc:
            vy = 0.0
            gear = 6 if (vx != 0.0 or wz != 0.0) else 1
        elif vx != 0.0 or vy != 0.0:
            gear, wz = 8, 0.0
        elif wz != 0.0:
            gear, vx, vy = 6, 0.0, 0.0
        else:
            gear = 1
        if mono > 0 and age_ms <= 1000:
            send_can(VEL_ID, pack_vel(gear, vx, vy, wz))
        if now - last_io > 1.0:      # 1Hz 补发解锁
            send_can(IO_ID, pack_io_unlock())
            last_io = now
        time.sleep(0.02)             # 50Hz 发送节拍


threading.Thread(target=udp_loop, daemon=True).start()
can_loop()

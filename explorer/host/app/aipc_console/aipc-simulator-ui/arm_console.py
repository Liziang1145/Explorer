#!/usr/bin/env python3
"""AIPC 机械臂控制台服务（独立适配器，端口 8092）。

职责：
1. 管理通道：通过 SSH 调用 KR260 上的 /usr/local/sbin/arm_console.sh，
   完成 can2 拉起、tool 使能/回预备位、deploy 启停与状态/日志读取。
2. 数据通道：以 20 Hz 向 KR260:54321 发送 v2 teleop_setpoint 帧
   （0xFCFC，142 字节，CRC16-Kermit，位定义 bit0 总使能 / bit2 左臂 / bit3 右臂 /
   bit4 左夹爪 / bit5 右夹爪；只置当前会话涉及的位），
   心跳 1 秒、单轮最长 120 秒、单持有者互斥。
   2026-10-19 起从旧 78 字节 0xFBFB 帧切换到 v2；位置缩放/偏置与姿态
   变换改由本端「只应用一次」，KR260 deploy 不再做任何变换。

不修改 8091 现有任何业务；仅读取同目录 simulator_vr_frame.py 的编码器。
前置条件：apex 用户到 ubuntu@192.168.137.1 的免密 SSH（ssh-copy-id），
KR260 已安装 arm_console.sh 及 sudoers 白名单。
"""

from __future__ import annotations

import base64
import csv
import dataclasses
import hashlib
from collections import deque
import json
import math
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from arm_entry import EntrySequence, angles, plan_phases, slew_command
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from vr_sticks import decode_stick, preview as stick_preview
from console_runtime import StopInterlock, BaseFeedback
import arm_buttons
import vr_stick_buttons
import base_drive
import arm_geometry
import transfer_trajectory
from one_euro import OneEuroFilter3

# VR 位置滤波：One Euro 根据目标速度自适应调节截止频率。
# 需要回退时只改成 'ema'，即可恢复原来的固定系数 0.25 低通。
VR_POSITION_FILTER = 'one_euro'
VR_ONE_EURO_MIN_CUTOFF = 1.5   # Hz：降低静止／精细操作的基础滤波强度
VR_ONE_EURO_BETA = 6.0         # s/m：1× 为 6；0.5×／0.25× 按倍率补偿为 12／24
VR_ONE_EURO_D_CUTOFF = 1.0     # Hz：速度估计低通截止频率

KR260_HOST = "ubuntu@192.168.137.1"
KR260_SCRIPT = "/usr/local/sbin/arm_console.sh"
UDP_TARGET = ("192.168.137.1", 54321)
BASE_UDP_TARGET = ("192.168.137.1", 54322)  # chassis_relay.py（底盘 can0）
BASE_UDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
BASE_UDP.settimeout(0.10)  # Bound the serialized send/stop critical section.
# 底盘子模式文案（VR Y 键与网页 /api/base_sub 共用同一口径）
BASE_SUB_TEXT = {'a': '全向平移+自旋', 'b': 'RC 遥控车（左油门/右转向）'}
SAFETY = StopInterlock()
if os.environ.get('CONSOLE_START_STOPPED') == '1':
    # Used during coordinated deployment to preserve an existing stop latch.
    _startup_epoch = SAFETY.stop()
    SAFETY.complete(_startup_epoch)
ACTION_LOCK = threading.Lock()
BASE_FEEDBACK = BaseFeedback(KR260_HOST)
BASE_COMMAND = {'submitted_at': None, 'enable': False, 'error': None}

# 入口动作逐帧诊断：只记录反馈与已经生成的指令，不参与控制，也绝不因磁盘异常中止动作。
ENTRY_LOG_DIR = os.environ.get('ARM_ENTRY_LOG_DIR',
                               os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'))
ENTRY_LOGS = {'left': None, 'right': None}


def entry_log(event, side, entry, feedback=None, note=''):
    """feedback 使用读取接口的度；entry 内部指令与参考值使用弧度。"""
    path = getattr(entry, 'log_path', None)
    if not path:
        return
    try:
        feedback = list(feedback) if feedback is not None else [None] * 6
        href = entry._hold_ref()
        row = [f'{time.time():.6f}', event, side, entry.phase,
               *[round(math.degrees(v), 5) for v in entry.command],
               round(math.degrees(href[0]), 5),
               *[round(float(v), 5) if v is not None else '' for v in feedback], note]
        with open(path, 'a', newline='', encoding='utf-8') as stream:
            csv.writer(stream).writerow(row)
    except Exception:
        pass


def entry_log_start(side, entry):
    try:
        os.makedirs(ENTRY_LOG_DIR, exist_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S') + f'_{int(time.time() * 1000) % 1000:03d}'
        entry.log_path = os.path.join(ENTRY_LOG_DIR, f'entry_{side}_{stamp}.csv')
        ENTRY_LOGS[side] = entry.log_path
        with open(entry.log_path, 'w', newline='', encoding='utf-8') as stream:
            csv.writer(stream).writerow(
                ['unix_time', 'event', 'side', 'phase',
                 *[f'cmd_J{i}_deg' for i in range(1, 7)], 'hold_ref_J1_deg',
                 *[f'feedback_J{i}_deg' for i in range(1, 7)], 'note'])
        entry_log('start', side, entry,
                  note='initial=' + ','.join(f'{math.degrees(v):.5f}' for v in entry.initial))
    except Exception:
        entry.log_path = None


# ---- v2 teleop_setpoint（0xFCFC, 142B, CRC16-Kermit；格式见 KR260 侧
# ---- piper_dual_arm_teleop/third_party/.../teleop_setpoint_msg.h 头注释）----
# enable_mask: bit0 总使能 + bit3 右臂 + bit5 右夹爪（v2 新位定义，不再是旧 0x9000）
ENABLE_RIGHT = 0x0001 | 0x0008 | 0x0020
ENABLE_LEFT = 0x0001 | 0x0004 | 0x0010   # 总使能 + 左臂 + 左夹爪


def crc16_kermit(data: bytes) -> int:
    """CRC-16/KERMIT（poly 反射 0x8408, init 0, xorout 0）。check: b'123456789'→0x2189。
    binascii.crc_hqx 是 CCITT-FALSE，不能用。"""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def encode_v2(seq: int, joints, gripper_open: float,
              left_joints=None, left_grip_open: float = 1.0,
              left_grip_on: bool = False) -> bytes:
    """v2 mode=2 关节直达帧（绕过 deploy IK 与世界系，AIPC 已解好关节角，
    deploy 只限速执行）。joints 为物理/tool 约定六轴 rad，gripper_open 为
    归一化开口 [0,1]，1=全开。left_joints 为 None 时左臂保持（mode=0）。
    left_grip_on=True 时即使左臂保持也带左夹爪使能位（deploy 的夹爪位
    独立于臂使能位处理，2026-10-21 修：VR 左臂未定位时夹爪无响应）。
    帧布局见 deploy third_party/.../teleop_setpoint_msg.h。"""
    left_on = left_joints is not None
    mask = (ENABLE_RIGHT if joints is not None else 0x0001)
    if left_on:
        mask |= ENABLE_LEFT
    elif left_grip_on:
        mask |= 0x0010      # 仅左夹爪使能（左臂 mode=0 保持）
    right_mode = 2 if joints is not None else 0
    buf = struct.pack('<HBBBBHIIIQ', 0xFCFC, 2, 0,
                      2 if left_on else 0, right_mode,
                      mask, seq & 0xFFFFFFFF, 0, 0,
                      time.monotonic_ns())
    buf += struct.pack('<7f', 0, 0, 0, 0, 0, 0, 1)      # left_target（mode=2 不用）
    buf += struct.pack('<7f', 0, 0, 0, 0, 0, 0, 1)      # right_target（mode=2 不用）
    # 左臂 J1 预取反（2026-10-21 真机实测定稿）：deploy mode=2 对收到的 J1
    # 统一取反；实测左臂物理转角 = deploy 执行值（与右臂镜像相反），故发送端
    # 预取反一次抵消。其余五轴与右臂完全一致，勿动。
    # 注意：tool 直驱（joint_set_left/set_left）不经过 deploy 取反，无需此处理。
    lj = list(left_joints or (0,) * 6)
    if left_on:
        lj[0] = -lj[0]
    buf += struct.pack('<6f', *[float(v) for v in lj])
    buf += struct.pack('<6f', *[float(v) for v in (joints or (0,)*6)])
    buf += struct.pack('<ff', float(left_grip_open), float(gripper_open))
    return buf + struct.pack('<H', crc16_kermit(buf))


# ===== 坐标系与 IK 标准（2026-10-19 定稿，与 03_工具/joint_fk_viewer.html 完全同源）=====
# 架构：AIPC 负责全部解算（底盘系 FK/IK），v2 mode=2 关节直达，deploy 不做任何
# 坐标变换——base_transform_ / 世界系 / J1 镜像问题整体绕开。
# 底盘系：X 右 / Y 前 / Z 上，原点 = 车底盘中心（OFF=底盘中心在机械臂底座系下坐标）。
OFF = (0.0, 0.0, 0.0)

# ===== 标定刚体修正（2026-10-24 新增，/api/calibrate 最小二乘标定的结果）=====
# 每臂一组修正：实测末端位置 ≈ Rz(yaw)·FK模型位置 + t（底盘用户系内，米/弧度）。
# 恒等修正时一切行为与之前完全一致；IK 入口做逆变换、FK 显示出口做正变换，
# deploy 侧零改动。结果持久化到 calib_offsets.json（与本文件同目录），重启保留。
# 2026-10-25 升级 5 参数：新增 s = 测量点（两指根转轴连线中点）到法兰中心
# 沿法兰轴的距离（米）。s 不进 IK/控制链路（语义仍是法兰），只随标定结果
# 持久化，供显示与后续 TCP 偏移使用。
CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calib_offsets.json')
CALIB = {'right': {'t': [0.0, 0.0, 0.0], 'yaw': 0.0, 's': 0.0},
         'left': {'t': [0.0, 0.0, 0.0], 'yaw': 0.0, 's': 0.0}}


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def _calib_load():
    try:
        with open(CALIB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for side in ('right', 'left'):
            c = data.get(side) or {}
            t = c.get('t', [0.0, 0.0, 0.0])
            yaw = float(c.get('yaw', 0.0))
            s = float(c.get('s', 0.0))     # 旧 4 参数文件无 s 字段，按 0 兼容
            if (isinstance(t, list) and len(t) == 3
                    and all(math.isfinite(float(v)) for v in t)
                    and math.isfinite(yaw) and math.isfinite(s)):
                CALIB[side] = {'t': [float(v) for v in t], 'yaw': yaw, 's': s}
    except FileNotFoundError:
        pass
    except Exception:                     # noqa: BLE001  标定文件损坏不致命：按无修正运行
        pass


def _calib_save():
    tmp = CALIB_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(CALIB, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CALIB_PATH)


def _calib_to_arm(p, side):
    """用户/底盘系目标点 → IK 模型点（修正的逆变换）。"""
    c = CALIB[side]
    t, yaw = c['t'], c['yaw']
    d = (p[0] - t[0], p[1] - t[1], p[2] - t[2])
    cw, sw = math.cos(yaw), math.sin(yaw)     # 逆旋转 = Rz(-yaw)
    return (cw * d[0] + sw * d[1], -sw * d[0] + cw * d[1], d[2])


def _calib_to_chassis(p, side):
    """FK 模型点 → 修正后位置（正变换，用于显示与意图层）。"""
    c = CALIB[side]
    t, yaw = c['t'], c['yaw']
    cw, sw = math.cos(yaw), math.sin(yaw)
    return (cw * p[0] - sw * p[1] + t[0], sw * p[0] + cw * p[1] + t[1], p[2] + t[2])


def _calib_tcp_from_fk(f_user, R_native, side):
    """模型 FK（用户系法兰位置 + 原生法兰姿态）→ 修正后**测量点**位置（底盘系，米）。
    2026-10-25 TCP 语义：对外输入/显示的位置一律是测量点（两指根转轴连线中点）
    = 修正法兰位置 + Rz(yaw)·(s·法兰轴用户系)。s=0 时与法兰逐字同值（向后兼容）。"""
    base = _calib_to_chassis(f_user, side)
    s = CALIB[side].get('s', 0.0)
    if not s:
        return base
    a = _mv(_FR, (R_native[0][2], R_native[1][2], R_native[2][2]))
    da = _mv(_rz(CALIB[side]['yaw']), (s * a[0], s * a[1], s * a[2]))
    return (base[0] + da[0], base[1] + da[1], base[2] + da[2])


_calib_load()

# 标定会话状态（每臂独立）：plan 生成点位，goto/record/measure 逐点推进，
# solve/apply 收尾。点位目标为底盘用户系坐标（米），q 为对应关节角（弧度）。
CALIB_SESSION = {'right': {'points': [], 'pending': None},
                 'left': {'points': [], 'pending': None}}
CALIB_SESSION_PATH = os.path.join(os.path.dirname(CALIB_PATH), 'calib_session.json')
CALIB_CLIENT = 'calib-20261024'
CALIB_MIN_MARGIN = 3.0          # 标定点支架余量下限（cm），比跟随下限 2.0 更保守


def _calib_session_save():
    """会话持久化：标定是慢速人工流程，服务重启不应丢记录（2026-10-24 教训）。"""
    try:
        tmp = CALIB_SESSION_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(CALIB_SESSION, f, ensure_ascii=False)
        os.replace(tmp, CALIB_SESSION_PATH)
    except Exception:                     # noqa: BLE001  持久化失败不影响主流程
        pass


def _calib_session_load():
    try:
        with open(CALIB_SESSION_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for side in ('right', 'left'):
            s = data.get(side) or {}
            pts = s.get('points')
            if isinstance(pts, list):
                CALIB_SESSION[side] = {'points': pts, 'pending': s.get('pending')}
    except FileNotFoundError:
        pass
    except Exception:                     # noqa: BLE001
        pass


_calib_session_load()

def _rt(x, y, z, roll, pitch, yaw):
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cw, sw = math.cos(yaw), math.sin(yaw)
    Rx = ((1, 0, 0), (0, cr, -sr), (0, sr, cr))
    Ry = ((cp, 0, sp), (0, 1, 0), (-sp, 0, cp))
    Rz = ((cw, -sw, 0), (sw, cw, 0), (0, 0, 1))
    return _mm(_mm(Rz, Ry), Rx), (x, y, z)

def _mm(a, b):
    return tuple(tuple(a[i][0]*b[0][j] + a[i][1]*b[1][j] + a[i][2]*b[2][j]
                       for j in range(3)) for i in range(3))

def _mv(a, v):
    return (a[0][0]*v[0] + a[0][1]*v[1] + a[0][2]*v[2],
            a[1][0]*v[0] + a[1][1]*v[1] + a[1][2]*v[2],
            a[2][0]*v[0] + a[2][1]*v[1] + a[2][2]*v[2])

def _mt(a):
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))

def _quat_to_R(q):
    """四元数 [x,y,z,w] → 旋转矩阵。"""
    x, y, z, w = q
    n = math.sqrt(x*x + y*y + z*z + w*w) or 1.0
    x, y, z, w = x/n, y/n, z/n, w/n
    return ((1-2*(y*y+z*z), 2*(x*y-z*w),   2*(x*z+y*w)),
            (2*(x*y+z*w),   1-2*(x*x+z*z), 2*(y*z-x*w)),
            (2*(x*z-y*w),   2*(y*z+x*w),   1-2*(x*x+y*y)))

# 与 arm_model.cpp default_transform_ 同源（前 6 个旋转连杆）
_DTF = (_rt(0, 0, 0.123, 0, 0, 0),
        _rt(0, 0, 0, math.pi/2, -0.1359, -math.pi),
        _rt(0.28503, 0, 0, 0, 0, -1.7939),
        _rt(-0.021984, -0.25075, 0, math.pi/2, 0, 0),
        _rt(0, 0, 0, -math.pi/2, 0, 0),
        _rt(0, -0.091, 0, math.pi/2, 0, 0))
# 用户系(X右/Y前/Z上) = FR · 原生底座系
_FR = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
_FRT = ((0, 1, 0), (-1, 0, 0), (0, 0, 1))
# 关节限位与 deploy arm_model.cpp 一致
# C11：两套范围，职责分明
#   _QLO/_QHI      机械硬限位（与 deploy arm_model.cpp 一致）—— 用来判断"能不能到"
#   JOINT_LO/HI    执行端 mode=2 的接受范围 —— 用来在下发前钳制，保证不出现静默裁剪
_QLO = (-2.618, 0.0, -2.967, -1.745, -1.22, -2.0944)
_QHI = (2.618, math.pi, 0.0, 1.745, 1.22, 2.0944)

# 关节直驱/滑块等入口的合法性判定改用硬限位
JOINT_HARD_LO = _QLO
JOINT_HARD_HI = _QHI
# 水平构型（夹爪朝前水平，真机已验证）与其用户系姿态 = 固定目标姿态
QLEVEL = tuple(v * math.pi / 180 for v in (-40, 92, -49, -63, -59, 40))

# ===== 两个可执行定点位姿（2026-10-22 新增「移动到起始 / 移动到零位」）=====
# 起始位姿以真机实测为准。右臂保留 5° 朝前补偿；左臂采用 03:16 实际姿态快照，
# 不再强制与右臂 J5 镜像。X 搬运的位置 1/2 会随左臂起始位自动重算。
Q_START_RIGHT = (-0.6981317007977319, 1.6057029118347828, -0.8552113334772216,
                 -1.024274566614689, -0.9696918456934094, 0.6583213836503105)
Q_START_LEFT = tuple(math.radians(v) for v in (38.8, 93.8, -43.2, 57.2, -60.4, -35.8))
# 网页 RPY=0 表示各臂实测起始姿态；内部基准包含完整滚转/俯仰/偏航，而非只补偏航。
LEVEL_RPY_DEG = {'right': (0.0, 0.0, -5.0),
                 'left': (-1.557848039521263, 4.631148426416149, -18.119814266007882)}
# X 键搬运流程：位置 3 来自 2026-10-29 左臂实际姿态快照。
# 位置 1/2 固定使用位置 3 的 J1/J2，J3～J6 从起始位到位置 3 等分过渡。
Q_LEFT_POS3 = tuple(math.radians(v) for v in (149.0, 100.6, -34.3, -50.6, -61.4, 31.3))
Q_LEFT_POS1 = Q_LEFT_POS3[:2] + tuple(
    Q_START_LEFT[i] + (Q_LEFT_POS3[i] - Q_START_LEFT[i]) / 3.0 for i in range(2, 6))
Q_LEFT_POS2 = Q_LEFT_POS3[:2] + tuple(
    Q_START_LEFT[i] + (Q_LEFT_POS3[i] - Q_START_LEFT[i]) * 2.0 / 3.0 for i in range(2, 6))
VR_RELEASE_WAIT_S = 5.0
# 零位：六轴 0°，但 J2/J3 取 deploy mode=2 的限位内缩值 ±0.05 rad。
# 直接下发 0 会被 deploy 钳到该值，反馈差 2.86° 会让到位判定永远不成立并触发超时停止。
Q_ZERO = (0.0, 0.05, -0.05, 0.0, 0.0, 0.0)
# 停车式移动的到位容差：覆盖实测关节零点偏置（左臂 J4 约 -4.5°）与重力垂度。
# 收紧前需实测核对；J1 归零判定另用 EntrySequence.ZERO_TOL（3°），不受此影响。
MOVE_TOL = math.radians(6.0)
MOVE_TARGETS = {('right', 'start'): list(Q_START_RIGHT),
                ('right', 'zero'): list(Q_ZERO),
                ('left', 'start'): list(Q_START_LEFT),
                ('left', 'zero'): list(Q_ZERO),
                ('left', 'pos1'): list(Q_LEFT_POS1),
                ('left', 'pos2'): list(Q_LEFT_POS2),
                ('left', 'pos3'): list(Q_LEFT_POS3)}
MOVE_LABELS = {('right', 'start'): '移动到起始位姿', ('right', 'zero'): '移动到零位',
               ('left', 'start'): '移动到起始位姿', ('left', 'zero'): '移动到零位',
               ('left', 'pos1'): 'X 流程：位置 1', ('left', 'pos2'): 'X 流程：位置 2',
               ('left', 'pos3'): 'X 流程：位置 3'}


def _fk(q):
    """返回 (法兰位置[原生系], 法兰姿态[原生系])。"""
    R = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    t = (0.0, 0.0, 0.0)
    for i in range(6):
        dt = _mv(R, _DTF[i][1])
        t = (t[0] + dt[0], t[1] + dt[1], t[2] + dt[2])
        R = _mm(_mm(R, _DTF[i][0]), _rt(0, 0, 0, 0, 0, q[i])[0])
    return t, R


def _fk_points(q, side):
    """逐关节 FK（2026-10-24，VR 遥测用）：返回 (7 个关节点[臂底座系·米], 法兰姿态[原生系])。
    pts[0]=底座，pts[6]=法兰（与 _fk(q)[0] 逐字同值，含标定修正）。
    VR 端不需要再解 FK：相邻点连线即为连杆，末点姿态用 ee_quat。"""
    R = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    t = (0.0, 0.0, 0.0)
    pts = [_calib_to_chassis(_mv(_FR, t), side)]
    for i in range(6):
        dt = _mv(R, _DTF[i][1])
        t = (t[0] + dt[0], t[1] + dt[1], t[2] + dt[2])
        R = _mm(_mm(R, _DTF[i][0]), _rt(0, 0, 0, 0, 0, q[i])[0])
        pts.append(_calib_to_chassis(_mv(_FR, t), side))
    return pts, R


def _mat_to_quat(R):
    """旋转矩阵 → 四元数 [x, y, z, w]。标准 Shepperd 法，数值稳定分支。"""
    m00, m01, m02 = R[0]
    m10, m11, m12 = R[1]
    m20, m21, m22 = R[2]
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return ((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s)
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        return (0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s)
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        return ((m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s)
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2
    return ((m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s)


_RTGT_NATIVE = None  # 惰性计算：FR^T · fkR(QLEVEL) · ...（用户系水平姿态→原生）


def _target_ori_native():
    global _RTGT_NATIVE
    if _RTGT_NATIVE is None:
        _, Rq = _fk(QLEVEL)               # R_user = FR·R_native → R_native(QLEVEL)
        _RTGT_NATIVE = Rq                 # 直接在原生系求解，目标姿态即此
    return _RTGT_NATIVE


def _ori_vee(Re):
    return (0.5 * (Re[2][1] - Re[1][2]),
            0.5 * (Re[0][2] - Re[2][0]),
            0.5 * (Re[1][0] - Re[0][1]))


def _rot_err(Rerr):
    """SO(3) 对数映射：把 Rerr 变成"转回单位阵所需的旋转向量"，长度即真实夹角（弧度）。

    C08 修复：原实现用反对称部分 _ori_vee 当姿态误差，它在夹角 θ=π 时恒为零，
    于是一个差 180° 的姿态会被判成"已收敛"。这里按 θ = acos((tr-1)/2) 取角度：
      θ 小   → 旋转向量 = θ/(2 sinθ) · vee(Rerr)
      θ≈π    → sinθ→0，改用 (Rerr+I)/2 = a·aᵀ 取轴，误差 = π·a
    这样 0°、小角度、接近 π、恰好 π 都能给出正确的误差量级。
    """
    tr = Rerr[0][0] + Rerr[1][1] + Rerr[2][2]
    c = max(-1.0, min(1.0, (tr - 1.0) * 0.5))
    th = math.acos(c)
    if th < 1e-9:
        return (0.0, 0.0, 0.0)
    if th < math.pi - 1e-3:
        k = th / (2.0 * math.sin(th))
        return (k * (Rerr[2][1] - Rerr[1][2]),
                k * (Rerr[0][2] - Rerr[2][0]),
                k * (Rerr[1][0] - Rerr[0][1]))
    # θ ≈ π：a 为特征值 1 的轴（(Rerr+I)/2 ≈ a·aᵀ）
    A = [[(Rerr[i][j] + (1.0 if i == j else 0.0)) * 0.5 for j in range(3)]
         for i in range(3)]
    k = max(range(3), key=lambda i: A[i][i])
    col = (A[0][k], A[1][k], A[2][k])
    n = math.sqrt(sum(v * v for v in col)) or 1.0
    return tuple(math.pi * v / n for v in col)


def _scale_rotation(anchor, target, scale):
    """将 target 相对 anchor 的旋转角按 scale 缩放，旋转轴保持不变。"""
    if scale >= 1.0:
        return target
    delta = _mm(target, _mt(anchor))
    vec = _rot_err(delta)
    angle = math.sqrt(sum(v * v for v in vec))
    if angle < 1e-12 or scale <= 0.0:
        return anchor
    axis = tuple(v / angle for v in vec)
    x, y, z = axis
    cross = ((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0))
    theta = angle * scale
    c, s = math.cos(theta), math.sin(theta)
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    cross2 = _mm(cross, cross)
    step = tuple(tuple(identity[i][j] + s * cross[i][j] + (1.0 - c) * cross2[i][j]
                       for j in range(3)) for i in range(3))
    return _mm(step, anchor)


def _dir_err(R, Rtgt):
    """仅夹爪指向（法兰 Z 轴）的姿态误差：把当前指向转到目标指向所需的旋转向量。
    绕指向轴的翻滚角不参与（腕部翻滚放开）。用于降级解算第二级。"""
    a = (R[0][2], R[1][2], R[2][2])
    b = (Rtgt[0][2], Rtgt[1][2], Rtgt[2][2])
    cx = (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])
    s = math.sqrt(sum(v*v for v in cx))
    d = max(-1.0, min(1.0, a[0]*b[0] + a[1]*b[1] + a[2]*b[2]))
    th = math.atan2(s, d)
    if s < 1e-9:
        return (0.0, 0.0, 0.0) if d > 0 else (math.pi, 0.0, 0.0)
    return (th * cx[0] / s, th * cx[1] / s, th * cx[2] / s)


def _ik_residual(t, R, tgt, Rtgt, ori_mode):
    """返回 (位置误差范数, 姿态误差范数[rad])。ori_mode: full/dir/pos。"""
    pe = math.sqrt(sum((tgt[i] - t[i]) ** 2 for i in range(3)))
    if ori_mode == 'pos':
        return pe, 0.0
    if ori_mode == 'dir':
        oe = _dir_err(R, Rtgt)
    else:
        oe = _rot_err(_mm(Rtgt, tuple(tuple(R[j][i] for j in range(3)) for i in range(3))))
    return pe, math.sqrt(sum(v*v for v in oe))


def _ik_core(tgt, Rtgt, q0, ori_mode, iters):
    """单种子阻尼最小二乘（LM 自适应阻尼 + 回溯步长，2026-10-25 强化版）。

    相对旧版的改动：λ 不再恒定（被拒×3、接受÷2）；每步在 1/2/4/8 折半中接受
    第一个让加权误差下降的结果，四次都不行才纯加阻尼——旧版是"步长超限直接
    钳死、误差增大也照走"，在限位/奇异附近会卡死或发散。
    收敛返回 q，未收敛返回 None。"""
    W = (50.0, 50.0, 50.0, 20.0, 20.0, 20.0)
    if ori_mode == 'pos':
        W = (50.0, 50.0, 50.0, 0.0, 0.0, 0.0)
    lam = 0.1
    q = list(q0)

    def err_vec(qv):
        t, R = _fk(qv)
        pe = tuple(tgt[i] - t[i] for i in range(3))
        if ori_mode == 'pos':
            oe = (0.0, 0.0, 0.0)
        elif ori_mode == 'dir':
            # 迭代用弦向误差（a 指向 b），收敛判据在 _ik_residual 用真实夹角
            oe = tuple(Rtgt[i][2] - R[i][2] for i in range(3))
        else:
            oe = _rot_err(_mm(Rtgt, tuple(tuple(R[j][i] for j in range(3)) for i in range(3))))
        return [pe[0]*W[0], pe[1]*W[1], pe[2]*W[2], oe[0]*W[3], oe[1]*W[4], oe[2]*W[5]], t, R

    e, t, R = err_vec(q)
    prev = math.sqrt(sum(v*v for v in e))
    for _ in range(iters):
        pe_n, oe_n = _ik_residual(t, R, tgt, Rtgt, ori_mode)
        if pe_n < 1e-4 and (ori_mode == 'pos' or oe_n < 2e-3):
            return q
        # 数值雅可比（与旧版同：h=1e-6 前向差分）
        J = [[0.0]*6 for _ in range(6)]
        for j in range(6):
            h = 1e-6
            s = q[j]; q[j] = s + h
            t2, R2 = _fk(q)
            q[j] = s
            if ori_mode == 'full':
                oe2 = _ori_vee(_mm(R2, tuple(tuple(R[jj][i] for jj in range(3)) for i in range(3))))
            elif ori_mode == 'dir':
                oe2 = tuple((R2[i][2] - R[i][2]) for i in range(3))
            else:
                oe2 = (0.0, 0.0, 0.0)
            for i in range(3):
                J[i][j] = (t2[i] - t[i]) / h * W[i]
                J[3+i][j] = oe2[i] / h * W[3+i]
        # dq = Jᵀ(JJᵀ+λ²I)⁻¹ e（6x6 高斯消元，同旧版）
        JJT = [[sum(J[i][k]*J[j][k] for k in range(6)) + (lam*lam if i == j else 0)
                for j in range(6)] for i in range(6)]
        M = [row[:] for row in JJT]
        I = [[1.0 if i == j else 0.0 for j in range(6)] for i in range(6)]
        for c in range(6):
            p = max(range(c, 6), key=lambda r: abs(M[r][c]))
            M[c], M[p] = M[p], M[c]; I[c], I[p] = I[p], I[c]
            dd = M[c][c] or 1e-12
            M[c] = [v/dd for v in M[c]]; I[c] = [v/dd for v in I[c]]
            for r in range(6):
                if r == c:
                    continue
                f = M[r][c]
                M[r] = [a - f*b for a, b in zip(M[r], M[c])]
                I[r] = [a - f*b for a, b in zip(I[r], I[c])]
        dq = [sum(J[k][j] * sum(I[k][i] * e[i] for i in range(6)) for k in range(6))
              for j in range(6)]
        n = math.sqrt(sum(v*v for v in dq))
        sc = 0.15 / n if n > 0.15 else 1.0
        # 回溯：接受第一个让误差下降的折半步；都不行则只加阻尼不进了一步
        accepted = False
        for scale in (1.0, 0.5, 0.25, 0.125):
            qn = [max(_QLO[j], min(_QHI[j], q[j] + dq[j]*sc*scale)) for j in range(6)]
            en, tn, Rn = err_vec(qn)
            nn = math.sqrt(sum(v*v for v in en))
            if nn < prev:
                q, e, t, R, prev = qn, en, tn, Rn, nn
                lam = max(lam * 0.5, 0.02)
                accepted = True
                break
        if not accepted:
            lam = min(lam * 3.0, 1.0)
    return None


def _ik_seeds(q_seed):
    """多种子集（2026-10-25）：覆盖常见分支——当前解、水平构型、零位、
    J1 左右偏 90°、J4 肘部翻转、中位构型。全部钳进硬限位；确定性顺序，不引入随机。"""
    def cl(v):
        return [max(_QLO[j], min(_QHI[j], v[j])) for j in range(6)]
    out = [list(q_seed), list(QLEVEL), list(Q_ZERO)]
    for j, d in ((0, math.pi/2), (0, -math.pi/2), (3, None)):
        v = list(q_seed)
        v[j] = -v[j] if d is None else v[j] + d
        out.append(cl(v))
    out.append([0.0, math.pi/2, -math.pi/2, 0.0, 0.0, 0.0])
    # 去重（避免与前三粒重复浪费预算）
    seen, uniq = set(), []
    for v in out:
        key = tuple(round(x, 3) for x in v)
        if key not in seen:
            seen.add(key)
            uniq.append(v)
    return uniq


def solve_ik_user(p_chassis, q_seed, Rtgt_native=None, side='right', budget_s=0.65,
                  tcp_s=None):
    """底盘系目标位置 + 目标姿态 → 六轴关节角（2026-10-25 强化版）。

    目标位置语义（2026-10-25 起）：p_chassis 是**测量点**（两指根转轴连线中点）
    的期望位置，函数内部自动扣除 s·目标法兰轴换算成法兰目标（s=0 时等价法兰语义）。

    返回约定（全部调用点按 `q is None` 判失败，向后兼容）：
      (q, None)   完全收敛（位置+全姿态）
      (q, warn)   降级收敛：warn 注明降级级别（位置+夹爪朝向 / 仅位置）
      (None, err) 失败，err 含最近残差

    相对旧版（单种子 + 固定 λ + 步长钳死 + 仅全姿态）的强化：
      1. 多种子重启：分支覆盖（肘上/肘下、J1 偏置、中位构型），种子间取
         级别最高、离 q_seed 最近的解，跟随不产生跳变；
      2. 姿态降级：全姿态无解 → 位置+夹爪指向（放开腕部翻滚）→ 仅位置，
         逐级尝试并如实标注——"演示模式摆得出但调不出"的绝大多数落在第二级；
      3. LM 自适应阻尼 + 回溯步长：治限位边界卡死与奇异附近发散；
      4. 时间预算：首粒种子（热启动）全参数 200 迭代与旧版一致；
         救援阶段（多种子×降级）总预算 budget_s，到期返回当时最好结果。
    side 决定使用哪条臂的标定修正。"""
    t0 = time.monotonic()
    Rtgt = Rtgt_native if Rtgt_native is not None else _target_ori_native()
    yaw = CALIB[side]['yaw']
    if yaw:
        # 底座偏航同样作用于姿态：模型系目标姿态 = Rz(-yaw)·目标姿态。
        # FRT 与 Rz 同为绕 Z 旋转、可交换，直接左乘即可。
        Rtgt = _mm(_rz(-yaw), Rtgt)
    p_model = _calib_to_arm(p_chassis, side)
    # TCP 语义（2026-10-25）：用户目标点 = 测量点（两指根转轴连线中点），
    # 法兰目标 = 标定逆变换结果 − s·目标姿态法兰轴（用户系，Rtgt 已过 yaw 调整，
    # 与 IK 实际达成的模型姿态一致）。s=0 时逐字等价旧行为。
    # 注意：降级到"仅位置"模式时实际姿态 ≠ Rtgt，s 偏移为近似（二阶小量）。
    s_tcp = CALIB[side].get('s', 0.0) if tcp_s is None else float(tcp_s)
    if s_tcp:
        a_u = _mv(_FR, (Rtgt[0][2], Rtgt[1][2], Rtgt[2][2]))
        p_model = (p_model[0] - s_tcp * a_u[0],
                   p_model[1] - s_tcp * a_u[1],
                   p_model[2] - s_tcp * a_u[2])
    u = (p_model[0] + OFF[0], p_model[1] + OFF[1], p_model[2] + OFF[2])
    tgt = _mv(_FRT, u)                    # 原生系目标位置

    seeds = _ik_seeds(q_seed)
    # 快路径：第一粒种子（调用方热启动）+ 全姿态。正常情形 1~2ms 收敛；
    # 失败情形 120 迭代 ≈ 90ms 即止损（旧版 200 迭代 ≈ 165ms 会把救援预算吃光），
    # 剩余交给多种子+降级——那里才是"摆得出调不出"的主战场
    q = _ik_core(tgt, Rtgt, seeds[0], 'full', 120)
    if q is not None:
        return tuple(q), None
    # 救援阶段：级别优先（full > dir > pos），每级内按种子顺序扫；
    # 快路径已试过 seeds[0]@full（200 迭代），full 轮跳过它；
    # dir/pos 轮从 seeds[0]（热种子）开始，跟随连续性最好。
    # 迭代数按"便宜筛查 → 认真求解"递增：full 只做分支筛查（45），
    # pos 给足 140——实测 pos 从好种子收敛需约百次迭代，给少了永远轮不到它。
    best = None          # (level_rank, dist_to_seed, q)
    warns = {0: None,     # 备用种子全姿态收敛仍是完全解，不算降级
             1: '降级：位置+夹爪朝向（腕部翻滚放开）', 2: '降级：仅位置（姿态放开）'}
    rounds = ((0, 'full', 45, seeds[1:4]),   # 3 粒备用种子分支筛查
              (1, 'dir', 60, seeds[:3]),     # 放开腕部翻滚（热种子优先）
              (2, 'pos', 150, seeds[:2]))    # 只保位置：可达时十几次迭代收敛；150 封顶防不可达空转
    for rank, mode, iters, seed_list in rounds:
        for sd in seed_list:
            if time.monotonic() - t0 > budget_s:
                break
            q = _ik_core(tgt, Rtgt, sd, mode, iters)
            if q is not None:
                dist = math.sqrt(sum((q[j] - q_seed[j]) ** 2 for j in range(6)))
                if best is None or dist < best[1]:
                    best = (rank, dist, q)
        if best is not None:
            break          # 本级别已有解，不再降下一级
        if time.monotonic() - t0 > budget_s:
            break
    if best is not None:
        return tuple(best[2]), warns[best[0]]
    # 失败：用最后一粒种子报残差量级，帮助判断"真不可达"还是"差一点"
    t, R = _fk(list(q_seed))
    pe, oe = _ik_residual(t, R, tgt, Rtgt, 'full')
    return None, ('IK 未收敛（多种子+三级降级均未达标；种子位残差 位置 %.1f cm / 姿态 %.1f°）'
                  % (pe * 100, math.degrees(oe)))


# 两点式 VLA 动作接口（2026-10-28 真机核实）：P1=J7 测量点，P2=J5 中心。
# 实测 J5→J7 总距离 152.5mm；官方模型 J5→法兰为 91mm，与法兰→J7 同轴。
TWO_POINT_J5_TCP = 0.1525
TWO_POINT_TCP_S = TWO_POINT_J5_TCP - 0.091
TWO_POINT_LEN_TOL = 0.025       # 感知/模型输出允许的 J5—J7 距离误差（米）


def _two_point_orientation(p_j7, p_j5, roll, q_seed, side, expected_len=TWO_POINT_J5_TCP):
    """J7/J5 两点 + 翻滚角 → 用户系完整姿态。

    法兰 Z 轴从 J5 指向 J7；法兰 Y 轴是夹指张开轴。roll=0 时张开轴取
    车体 X 在垂直于指向轴平面上的投影；roll 按右手定则绕法兰 Z 轴旋转。
    指向轴接近车体 X 时零位投影退化，改用当前关节姿态的张开轴，避免跳变。
    """
    try:
        p1 = [float(v) for v in p_j7]
        p2 = [float(v) for v in p_j5]
        psi = float(roll)
    except (TypeError, ValueError) as exc:
        raise ValueError('两点坐标和翻滚角必须是数值') from exc
    if len(p1) != 3 or len(p2) != 3 or not all(math.isfinite(v) for v in p1 + p2 + [psi]):
        raise ValueError('两点必须为有限 XYZ，翻滚角必须有限')
    v = [p1[i] - p2[i] for i in range(3)]
    length = math.sqrt(sum(x * x for x in v))
    if length < 1e-6:
        raise ValueError('J5 与 J7 不能重合')
    if abs(length - expected_len) > TWO_POINT_LEN_TOL:
        raise ValueError('J5—J7 距离 %.1f cm 与工具长度 %.1f cm 不符'
                         % (length * 100, expected_len * 100))
    z = [x / length for x in v]
    # 零位张开轴 = 车体 X 去掉沿夹爪指向的分量。
    opening = [1.0 - z[0] * z[0], -z[0] * z[1], -z[0] * z[2]]
    n = math.sqrt(sum(x * x for x in opening))
    if n < 1e-6:
        # 退化时继承当前目标姿态的法兰 Y 轴，仍投影到目标指向的法平面。
        Rcur = _mm(_rz(CALIB[side]['yaw']), _mm(_FR, _fk(q_seed)[1]))
        a = [Rcur[0][1], Rcur[1][1], Rcur[2][1]]
        dot = sum(a[i] * z[i] for i in range(3))
        opening = [a[i] - dot * z[i] for i in range(3)]
        n = math.sqrt(sum(x * x for x in opening))
        if n < 1e-6:
            raise ValueError('当前姿态也无法确定夹指张开轴')
    y0 = [x / n for x in opening]
    x0 = (y0[1] * z[2] - y0[2] * z[1],
          y0[2] * z[0] - y0[0] * z[2],
          y0[0] * z[1] - y0[1] * z[0])
    c, s = math.cos(psi), math.sin(psi)
    # R = R0·Rz(roll)：局部 X/Y 绕指向轴旋转，Z 保持不变。
    x = [c * x0[i] + s * y0[i] for i in range(3)]
    y = [-s * x0[i] + c * y0[i] for i in range(3)]
    return ((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2]))


def solve_two_point_user(p_j7, p_j5, roll, q_seed, side='right', budget_s=0.65,
                         tcp_s=None):
    """两点式目标 → 六轴关节角。单位：米、弧度；坐标：底盘用户系。

    P1(p_j7) 是末端测量点，P2(p_j5) 是 J5 中心；roll=0 时夹指左右张开。
    tcp_s=None 使用实测 61.5mm；VR 适配器显式传各臂标定值以保持原有几何。
    返回约定与 solve_ik_user 相同。几何输入不合法抛出 ValueError，IK 不可达
    仍返回 (None, err)，不输出未收敛关节角。
    """
    s_tcp = TWO_POINT_TCP_S if tcp_s is None else float(tcp_s)
    R_user = _two_point_orientation(p_j7, p_j5, roll, q_seed, side,
                                    expected_len=0.091 + s_tcp)
    # V3.0：VR/VLA 与网页统一使用 J1～J3 几何定位 + J4～J6 解析调姿。
    # budget_s 仅为旧调用签名兼容保留；解析解不需要迭代时间预算，也绝不降级。
    return solve_layered_j5_pose_user(p_j5, R_user, q_seed, side=side)


def solve_vr_pose_two_point_user(p_chassis, R_user, q_seed, side='right', budget_s=0.65):
    """VR 的 J5 目标位置+四元数矩阵 → P1/P2/θ → 两点式 IK。

    p_chassis 直接指定 P2（J5 中心）；目标姿态 Z 轴给出 J5→J7 方向，按该臂
    工具长度正算 P1（J7），再从完整姿态恢复绕轴翻滚角。VLA 的 P1=J7 语义不变。
    """
    p2 = [float(v) for v in p_chassis]
    d = [R_user[0][2], R_user[1][2], R_user[2][2]]
    n = math.sqrt(sum(v * v for v in d))
    if not math.isfinite(n) or n < 1e-9:
        raise ValueError('VR 目标姿态指向无效')
    d = [v / n for v in d]
    j5_j7 = 0.091 + CALIB[side].get('s', 0.0)
    p1 = [p2[i] + j5_j7 * d[i] for i in range(3)]
    R0 = _two_point_orientation(p1, p2, 0.0, q_seed, side, expected_len=j5_j7)
    xt = [R_user[i][0] for i in range(3)]
    x0 = [R0[i][0] for i in range(3)]
    y0 = [R0[i][1] for i in range(3)]
    roll = math.atan2(sum(xt[i] * y0[i] for i in range(3)),
                      sum(xt[i] * x0[i] for i in range(3)))
    return solve_two_point_user(p1, p2, roll, q_seed, side=side,
                                budget_s=budget_s, tcp_s=CALIB[side].get('s', 0.0))


# ===== 网页右臂试验：J1～J3 定位，J4～J6 调姿（2026-10-28）=====
def _fk_j5_native(q):
    """原生系 J5 中心。第五个平移为零，因此结果只取决于 J1～J3。"""
    R = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    t = (0.0, 0.0, 0.0)
    for i in range(5):
        dt = _mv(R, _DTF[i][1])
        t = (t[0] + dt[0], t[1] + dt[1], t[2] + dt[2])
        R = _mm(_mm(R, _DTF[i][0]), _rt(0, 0, 0, 0, 0, q[i])[0])
    return t


def _wrap_pi(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _web_j5_position(tgt, q_seed):
    """J1～J3 几何解析定位 J5：腰转分支 × 平面两连杆肘部分支。

    松灵模型在消去固定旋转后，J2/J3 可写成标准平面 2R：
      连杆角之差 = -(J3 + elbow_offset)，首连杆角 = pi - J2 + shoulder_offset。
    第三连杆的横向固定偏距并入其长度与零位角，不丢弃、不另加修正项。
    所有几何分支都做硬限位与原生 FK 复核，选择离当前前三轴最近者。
    """
    l1 = abs(_DTF[2][1][0])
    v3 = _DTF[3][1]
    l2 = math.hypot(v3[0], v3[1])
    base_z = _DTF[0][1][2]
    shoulder_offset = -0.1359
    elbow_offset = -1.7939 + math.atan2(v3[1], v3[0])
    radius = math.hypot(tgt[0], tgt[1])
    alpha = math.atan2(tgt[1], tgt[0]) if radius > 1e-10 else q_seed[0]
    base_candidates = (_wrap_pi(alpha),) if radius <= 1e-10 else (
        _wrap_pi(alpha), _wrap_pi(alpha + math.pi))
    candidates = []
    geometric = False
    best = None
    for q0 in base_candidates:
        # 目标在腰转平面内的有符号水平距离；反腰转分支对应负距离。
        r = math.cos(q0) * tgt[0] + math.sin(q0) * tgt[1]
        h = tgt[2] - base_z
        ce = (r * r + h * h - l1 * l1 - l2 * l2) / (2.0 * l1 * l2)
        if not -1.0 - 1e-10 <= ce <= 1.0 + 1e-10:
            continue
        ce = max(-1.0, min(1.0, ce))
        se_abs = math.sqrt(max(0.0, 1.0 - ce * ce))
        for sign in (1.0, -1.0):
            geometric = True
            elbow = math.atan2(sign * se_abs, ce)
            q2 = _wrap_pi(-elbow - elbow_offset)
            phi1 = math.atan2(h, r) - math.atan2(l2 * math.sin(elbow),
                                                   l1 + l2 * ce)
            q1 = _wrap_pi(math.pi + shoulder_offset - phi1)
            qpos = [q0, q1, q2]
            pe = math.dist(tgt, _fk_j5_native(qpos + list(q_seed[3:6])))
            if best is None or pe < best:
                best = pe
            if pe > 1e-7:
                continue                    # 固定模型若变化，绝不接受错误解析式
            if not all(_QLO[j] - 1e-9 <= qpos[j] <= _QHI[j] + 1e-9 for j in range(3)):
                continue
            dist = sum((qpos[j] - q_seed[j]) ** 2 for j in range(3))
            candidates.append((dist, qpos))
    if candidates:
        return min(candidates, key=lambda item: item[0])[1], None
    if geometric:
        return None, 'J5 位置的几何解超出 J1～J3 限位'
    return None, 'J5 位置超出 J1～J3 工作空间'


def _web_wrist_orientation(Rtgt, qpos, q_seed):
    """固定 J1～J3，用 ZYZ 解析式求 J4～J6，不用位置关节补偿姿态。

    R3ᵀ·Rtgt·(后续固定旋转) 可写成 Rz(J4)·Ry(J5)·Rz(J6)。
    两个解析分支都检查机械限位，并选择离当前腕部最近的解。
    """
    R3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    for i in range(3):
        R3 = _mm(_mm(R3, _DTF[i][0]), _rt(0, 0, 0, 0, 0, qpos[i])[0])
    B = _mm(_mt(_DTF[3][0]), _mm(_mt(R3), Rtgt))
    candidates = []
    cb = max(-1.0, min(1.0, B[2][2]))
    sb = math.sqrt(max(0.0, 1.0 - cb * cb))
    if sb > 1e-8:
        b0 = math.acos(cb)
        for sign in (1.0, -1.0):
            candidates.append((math.atan2(sign * B[1][2], sign * B[0][2]),
                               sign * b0,
                               math.atan2(sign * B[2][1], -sign * B[2][0])))
    elif cb > 0.0:
        total = math.atan2(B[1][0], B[0][0])
        candidates.append((total - q_seed[5], 0.0, q_seed[5]))
        candidates.append((q_seed[3], 0.0, total - q_seed[3]))
    valid = []
    for wrist in candidates:
        if all(_QLO[j + 3] - 1e-9 <= wrist[j] <= _QHI[j + 3] + 1e-9
               for j in range(3)):
            dist = sum((wrist[j] - q_seed[j + 3]) ** 2 for j in range(3))
            valid.append((dist, wrist))
    if not valid:
        return None, '当前 J5 位置下目标姿态超出 J4～J6 限位（分层解算不补偿前三轴）'
    wrist = min(valid, key=lambda item: item[0])[1]
    return qpos[:] + list(wrist), None


def solve_layered_j5_pose_user(p_chassis, R_user, q_seed, side='right'):
    """V3.0 全解析核心：J1～J3 几何定位 J5，J4～J6 ZYZ 解析调姿。

    网页、VR、VLA 共用；不调用六轴数值 IK，不降级，不用前三轴补偿腕部限位。
    """
    p_model = _calib_to_arm(p_chassis, side)
    u = (p_model[0] + OFF[0], p_model[1] + OFF[1], p_model[2] + OFF[2])
    tgt = _mv(_FRT, u)
    qpos, err = _web_j5_position(tgt, q_seed)
    if qpos is None:
        return None, err
    Rtgt = _mm(_FRT, R_user)
    yaw = CALIB[side]['yaw']
    if yaw:
        Rtgt = _mm(_rz(-yaw), Rtgt)
    return _web_wrist_orientation(Rtgt, qpos, q_seed)


def solve_web_j5_rpy_side(p_chassis, rpy_deg, q_seed, side):
    """J5 位置 + 相对本臂实测起始姿态的 RPY；零输入精确复现起始姿态。"""
    base = LEVEL_RPY_DEG[side]
    roll, pitch, yaw = [math.radians(v + base[i]) for i, v in enumerate(rpy_deg)]
    R_level = _mm(_rz(CALIB[side]['yaw']), _mm(_FR, _target_ori_native()))
    R_offset = _rt(0, 0, 0, roll, pitch, yaw)[0]  # Rz(yaw)·Ry(pitch)·Rx(roll)
    return solve_layered_j5_pose_user(p_chassis, _mm(R_offset, R_level), q_seed, side=side)


def solve_level_j5_pose_user(p_chassis, q_seed, side='right'):
    """J5 位置 + 标准水平姿态，供 VR 启动/位置模式使用 V3.0 解析解。"""
    return solve_web_j5_rpy_side(p_chassis, (0.0, 0.0, 0.0), q_seed, side)


def solve_web_j5_rpy_user(p_chassis, R_user, q_seed):
    """旧网页入口兼容包装；实际解算与 VR/VLA 共用 V3.0 全解析核心。"""
    return solve_layered_j5_pose_user(p_chassis, R_user, q_seed, side='right')


# ===== 坐标系标准（2026-10-19 定稿，与 03_工具/joint_fk_viewer.html 完全一致）=====
# 对用户/UI 暴露的是「底盘系」：X 右 / Y 前 / Z 上，原点 = 车底盘中心。
# 变换链（本端只应用一次，KR260 deploy 不做任何变换）：
#   底盘系 p_c → 机械臂底座用户系 p_u = p_c + OFF（OFF=底盘中心在底座系下坐标，尺量）
#   → deploy 世界系 p_w = (p_u.z, p_u.y, -p_u.x) + WORLD_ARM_BASE
# 推导：原生底座系 p_b = (p_u.y, -p_u.x, p_u.z)（用户系 = Rz90·原生）；
#   世界系 p_w = R_wb·p_b + t_wb，R_wb=[[0,0,1],[1,0,0],[0,1,0]]，
#   见 teleop_task_runner.cpp right_arm_base_transform_（已数值校验，
#   与 arm_model.cpp FK 直算结果一致，误差 < 0.1mm）。
# 底盘系法兰目标安全盒（与 HTML 滑块范围一致，米）
TARGET_LO = (-0.50, -0.10, -0.25)
TARGET_HI = ( 0.50,  0.55,  0.60)
# 默认目标 = 水平构型（夹爪朝前水平，QLEVEL）法兰：用户系 (0.1514, 0.2885, 0.2659) 减 OFF。
# 选它而非零位法兰：零位法兰点配水平姿态近乎不可达（IK 需 J4 转 62° 仍残差 2.4°），
# 开始跟随时臂会乱动；水平构型位姿自洽、可达、真机已验证。
DEFAULT_TARGET = (0.1514 - OFF[0], 0.2885 - OFF[1], 0.2659 - OFF[2])

HEARTBEAT_S = 1.0
# 定点移动期间由 _entry_feedback 线程续租；租期必须长于一次 SSH 反馈读取的最长耗时
# （LEFT/RIGHT_READ_PY 内部最多 1.5s，subprocess 3s 超时），否则 _tick 会把“读取慢”
# 误判成“页面心跳过期”并触发全局软件停止。
MOVE_LEASE_S = 8.0
# 判定“臂是否真的动过”的门限。入口/移动中止时若六轴偏离起始值都小于此值，
# 说明是前置条件失败（deploy 未运行、臂未使能、反馈读不到、页面心跳断了），
# 没有需要紧急停止的运动对象，只撤销会话而不锁存全局软件停止。
NO_MOTION_TOL = math.radians(0.5)
# “机械臂无响应”快筛：指令需要移动超过 STALL_NEED，但 STALL_S 秒内实际位移仍小于
# STALL_DEV，就判定为未使能/未上电/不在 CAN 模式，立即中止（不锁存），不白等 45s 超时。
STALL_S = 6.0
STALL_NEED = math.radians(10.0)
STALL_DEV = math.radians(3.0)
ROUND_S = 600.0        # 2026-10-23：原 120s 到点硬停，演示时每 2 分钟断一次
SSH_TIMEOUT_S = 20

# ===== VR 跟随（2026-10-20）=====
# 数据源：本机 TLZ 代理 unix socket /operator-input/latest（只读快照，50 Hz）。
# 映射（三点标定实测定稿，见 03_工具 采集分析）：
#   底盘 X(右) = −VR.y   底盘 Y(前) = +VR.x   底盘 Z(上) = +VR.z   比例 1:1
# 离合：input_state bit3（按住控制）按下期间跟随手部位移增量，松开保持；
#   每次按下以当前手部位姿为参考零位、以当前机械臂目标为锚点，无跳变。
#   bit2（右手跟踪有效）丢失或数据不新鲜（>0.5s）时保持，心跳自然过期停发。
TLZ_SOCK = "/run/tlz-aipc/adapter.sock"
# 2026-10-24：0.3s → 0.5s。头显→AIPC 走 WiFi，300ms 抖动在无线链路上很常见，
# 0.3 时正常网络波动就会触发「目标停止更新」，表现为无故顿挫。0.5s 仍在
# deploy 100ms 看门狗 + 5s 会话心跳的安全包络内（这两条不受影响）。
VR_FRESH_S = 0.5


def _cbor_decode(buf, pos=0):
    """最小 CBOR 解码（够解析 OPERATOR_STATE 包体）。"""
    ib = buf[pos]; pos += 1
    major, info = ib >> 5, ib & 31
    if info < 24:
        val = info
    elif info == 24:
        val = buf[pos]; pos += 1
    elif info == 25:
        val = struct.unpack('>H', buf[pos:pos+2])[0]; pos += 2
    elif info == 26:
        val = struct.unpack('>I', buf[pos:pos+4])[0]; pos += 4
    elif info == 27:
        val = struct.unpack('>Q', buf[pos:pos+8])[0]; pos += 8
    else:
        raise ValueError('bad cbor info')
    if major == 0:
        return val, pos
    if major == 1:
        return -1 - val, pos
    if major in (2, 3):
        out = bytes(buf[pos:pos+val]); pos += val
        return (out.decode('utf-8') if major == 3 else out), pos
    if major == 4:
        arr = []
        for _ in range(val):
            v, pos = _cbor_decode(buf, pos); arr.append(v)
        return arr, pos
    if major == 5:
        d = {}
        for _ in range(val):
            k, pos = _cbor_decode(buf, pos)
            v, pos = _cbor_decode(buf, pos)
            d[k] = v
        return d, pos
    if major == 7:
        if info == 20:
            return False, pos
        if info == 21:
            return True, pos
        if info in (22, 23):
            return None, pos
        if info == 26:
            return struct.unpack('>f', buf[pos-4:pos])[0], pos
        if info == 27:
            return struct.unpack('>d', buf[pos-8:pos])[0], pos
    raise ValueError(f'cbor major {major}')


def parse_operator_packet(raw: bytes):
    """TLZ2 OPERATOR_STATE → (input_state, 右手pos, 右手quat, 右扳机, 右侧键,
    左手pos, 左手quat, 左扳机, 左侧键, 左摇杆候选, 右摇杆候选, A/B/X/Y, 摇杆按下)。
    key4=左手柄位姿 key5=右手柄位姿（协议 v2.0 §OPERATOR_STATE）；
    key11 共用模拟量：k1/k2 左右侧键，k3/k4 左右扳机；
    k5/k6 为二维摇杆，暂按左右顺序预览，待当前 APK 确认；
    key13=A/B/X/Y（arm_buttons）；key15=左右摇杆按下 L3/R3（vr_stick_buttons）。"""
    if len(raw) < 64 or raw[:4] != b'TLZ2':
        return (None,) * 13
    if struct.unpack('>H', raw[6:8])[0] != 0x0104:
        return (None,) * 13
    if struct.unpack('>I', raw[12:16])[0] != len(raw) - 64:
        raise ValueError('OPERATOR_STATE payload length mismatch')
    body, _ = _cbor_decode(raw, 64)
    istate = body.get(2) or 0
    pose = body.get(5)
    if isinstance(pose, dict) and 1 in pose:
        pos = tuple(float(v) for v in pose[1])
        quat = tuple(float(v) for v in pose[2]) if 2 in pose else None
    else:
        pos, quat = None, None
    lpose = body.get(4)
    if isinstance(lpose, dict) and 1 in lpose:
        lpos = tuple(float(v) for v in lpose[1])
        lquat = tuple(float(v) for v in lpose[2]) if 2 in lpose else None
    else:
        lpos, lquat = None, None
    # key11 手柄模拟量（2026-10-21 采集终裁：左右手共用 key11，对称布局）：
    #   k1=左侧键  k2=右侧键（按住时 istate bit3/0x08 同时置位）
    #   k3=左扳机  k4=右扳机（纯模拟量，无数字位）
    # key12 不存在，勿再用。
    trig = body.get(11)
    if isinstance(trig, dict):
        trigger = float(trig.get(4) or 0.0)
        sidegrip = float(trig.get(2) or 0.0)
    else:
        trigger, sidegrip = 0.0, 0.0
    if isinstance(trig, dict):
        ltrigger = float(trig.get(3) or 0.0)
        lsidegrip = float(trig.get(1) or 0.0)
    else:
        ltrigger, lsidegrip = 0.0, 0.0
    lstick = decode_stick(trig.get(5)) if isinstance(trig, dict) else None
    rstick = decode_stick(trig.get(6)) if isinstance(trig, dict) else None
    # A/B/X/Y（key13）：实采 2026-10-22 确认 bit0=A bit1=B bit2=X bit3=Y，
    # 校验规则与直连网关 tlz2/face_buttons.py 一致；缺失或不合规一律 None。
    buttons = arm_buttons.parse(body)
    # key15=左右摇杆按下 L3/R3（2026-10-31 增补 revision 1）：缺失或不合规为 None。
    stick_buttons = vr_stick_buttons.parse(body)
    return (istate, pos, quat, trigger, sidegrip, lpos, lquat, ltrigger, lsidegrip,
            lstick, rstick, buttons, stick_buttons)


class VrFeed:
    """轮询 TLZ 代理最新 OPERATOR_STATE（25 ms），供 VR 跟随读取。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.version = None
        self.recv_mono = 0.0      # 本机收到该版本的时刻
        self.istate = 0
        self.pos = None
        self.quat = None
        self.trigger = 0.0
        self.sidegrip = 0.0
        self.lpos = None
        self.lquat = None
        self.ltrigger = 0.0
        self.lsidegrip = 0.0
        self.lstick = None
        self.rstick = None
        self.face = None          # key13：{'revision','valid','pressed','touched','touched_valid'}
        self.stick_buttons = None # key15：{'revision','valid','pressed'}（L3/R3 摇杆按下）
        self.stick_source_fresh = False
        self.stick_recv_mono = 0.0
        self.error = None
        threading.Thread(target=self._loop, daemon=True).start()

    def _fetch(self):
        import base64
        import http.client

        class UnixHTTP(http.client.HTTPConnection):
            def connect(self2):
                self2.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self2.sock.settimeout(self2.timeout)
                self2.sock.connect(TLZ_SOCK)

        conn = UnixHTTP('localhost', timeout=1.5)
        try:
            conn.request('GET', '/operator-input/latest')
            r = conn.getresponse()
            if r.status != 200:
                return None
            return json.loads(r.read())
        finally:
            conn.close()

    def _loop(self):
        while True:
            try:
                d = self._fetch()
                with self.lock:
                    self.stick_source_fresh = bool(d and d.get('fresh') is True)
                if d:
                    ev = d.get('event')
                    if ev and ev.get('version') != self.version:
                        istate, pos, quat, trigger, sidegrip, lpos, lquat, ltrigger, lsidegrip, lstick, rstick, buttons, stick_buttons = parse_operator_packet(base64.b64decode(ev['packet_base64']))
                        with self.lock:
                            self.version = ev['version']
                            self.recv_mono = time.monotonic()
                            self.istate = istate or 0
                            self.pos = pos
                            self.quat = quat
                            self.trigger = trigger
                            self.sidegrip = sidegrip
                            self.lpos = lpos
                            self.lquat = lquat
                            self.ltrigger = ltrigger
                            self.lsidegrip = lsidegrip
                            self.lstick, self.rstick = lstick, rstick
                            self.face = buttons
                            self.stick_buttons = stick_buttons
                            age_ms = d.get('age_ms')
                            if type(age_ms) in (int, float) and math.isfinite(age_ms) and age_ms >= 0:
                                self.stick_recv_mono = self.recv_mono - age_ms / 1000.0
                            else:
                                self.stick_source_fresh = False
                                self.stick_recv_mono = 0.0
                            self.error = None
            except Exception as e:  # noqa: BLE001
                with self.lock:
                    self.error = type(e).__name__
                    self.stick_source_fresh = False
            time.sleep(0.025)

    def latest(self):
        with self.lock:
            return (self.version, self.recv_mono, self.istate, self.pos,
                    self.quat, self.trigger, self.sidegrip, self.error,
                    self.lpos, self.lquat, self.ltrigger, self.lsidegrip,
                    self.stick_buttons)

    def buttons(self, now=None):
        """A/B/X/Y 只读快照（含新鲜度）。不授予任何控制权。"""
        now = time.monotonic() if now is None else now
        with self.lock:
            fresh = (self.version is not None and self.error is None
                     and 0 <= now - self.recv_mono < VR_FRESH_S)
            snap = arm_buttons.summary(self.face)
            snap['fresh'] = fresh
            snap['age_ms'] = max(0, round((now - self.recv_mono) * 1000)) \
                if self.version is not None else None
            snap['revision'] = (self.face or {}).get('revision')
            return snap

    def stick_buttons_snapshot(self, now=None):
        """L3/R3 摇杆按下只读快照（含新鲜度）。与 buttons() 同风格，供遥测用。"""
        now = time.monotonic() if now is None else now
        with self.lock:
            fresh = (self.version is not None and self.error is None
                     and 0 <= now - self.recv_mono < VR_FRESH_S)
            snap = vr_stick_buttons.summary(self.stick_buttons)
            snap['fresh'] = fresh
            snap['age_ms'] = max(0, round((now - self.recv_mono) * 1000)) \
                if self.version is not None else None
            return snap

    def raw_snapshot(self, now=None):
        """内部用：经时效校验的摇杆/侧键快照（不对外发 UDP、不授予控制权）。

        与 sticks() 的分工（C03 修复）：
          - raw_snapshot() 给底盘驱动循环用，字段与"是否新鲜"绑定在一起，
            避免调用方拿到裸值却自己猜时效；
          - sticks() 只给页面看，返回带推导模式的只读摘要。
        两者曾同名，后者覆盖前者，导致 _base_loop 解包失败（VR 底盘从未生效）。
        """
        now = time.monotonic() if now is None else now
        with self.lock:
            age = now - self.stick_recv_mono
            fresh = (self.version is not None and self.stick_source_fresh
                     and self.error is None and 0 <= age < VR_FRESH_S)
            return dict(lstick=self.lstick, rstick=self.rstick,
                        lsidegrip=self.lsidegrip, rsidegrip=self.sidegrip,
                        fresh=fresh, error=self.error,
                        age_ms=(max(0, round(age * 1000))
                                if self.version is not None else None))

    def sticks(self, now=None):
        """Read-only endpoint; never grants control ownership or emits UDP."""
        now = time.monotonic() if now is None else now
        with self.lock:
            age = now - self.stick_recv_mono
            fresh = (self.version is not None and self.stick_source_fresh
                     and self.error is None and 0 <= age < VR_FRESH_S)
            result = stick_preview(self.lstick, self.rstick, fresh=fresh,
                                   input_state=self.istate)
            result['age_ms'] = max(0, round(age * 1000)) if self.version is not None else None
            return result


VR = VrFeed()


def kr260(*args: str, timeout: float = SSH_TIMEOUT_S) -> tuple[int, str]:
    """在 KR260 上执行控制台助手，返回 (返回码, 输出)。

    timeout 可按调用覆盖：deploy_start 的脚本会把 deploy 放到后台，而该后台进程
    会占住 SSH 的 stdout 管道，导致 ssh 直到超时才返回（实测 >25 s，但远端脚本
    早已打印完 deploy-running）。因此这类调用要短超时 + 以状态查询为准。
    """
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
             KR260_HOST, "sudo", KR260_SCRIPT, *args],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "SSH 执行超时（KR260 不在线？）"
    except Exception as e:  # noqa: BLE001
        return 1, f"SSH 调用失败: {type(e).__name__}: {e}"


def deploy_running() -> bool:
    rc, out = kr260("status")
    if rc != 0:
        return False
    m = re.search(r"deploy:\s*(\d+)", out)
    return bool(m)


# deploy 状态缓存（2026-10-21）：左臂控制每拍都查会高频 SSH 打爆 KR260 sshd，
# 导致控制链路时断时续。5s TTL 足够安全（deploy 崩溃后最多晚 5s 发现）。
_deploy_cache = [0.0, False]


def deploy_running_cached(ttl: float = 5.0) -> bool:
    now = time.monotonic()
    if now - _deploy_cache[0] < ttl:
        return _deploy_cache[1]
    ok = deploy_running()
    _deploy_cache[0] = now
    _deploy_cache[1] = ok
    return ok


LEFT_CAN_IF = 'FPGA_CAN0'   # 左臂板载 CAN；网页/API 中仍称 left/can1 别名
RIGHT_CAN_IF = 'FPGA_CAN1'  # 右臂板载 CAN；网页/API 中仍称 right/can2 别名


def exit_teach_script(interface: str) -> str:
    """结束普通示教并切 CAN/MOVE J；必须收到 0x2A1 模式反馈才算成功。"""
    if interface not in (LEFT_CAN_IF, RIGHT_CAN_IF):
        raise ValueError('无效 CAN 接口')
    return (
        "import socket,struct,time\n"
        f"s=socket.socket(socket.PF_CAN,socket.SOCK_RAW,socket.CAN_RAW)\n"
        f"s.bind(('{interface}',));s.settimeout(0.15)\n"
        "def send(cid,data):\n"
        "    s.send(struct.pack('=IB3x8s',cid,len(data),bytes(data)))\n"
        "send(0x150,[0,0,0x02,0,0,0,0,0])\n"
        "time.sleep(0.1)\n"
        "send(0x151,[0x01,0x01,0,0,0,0,0,0])\n"
        "end=time.monotonic()+2.0\n"
        "while time.monotonic()<end:\n"
        "    try:frame,_=s.recvfrom(16)\n"
        "    except socket.timeout:continue\n"
        "    cid,dlc,data=struct.unpack('=IB3x8s',frame)\n"
        "    if cid==0x2A1 and dlc>=1:\n"
        "        if data[0]==0x01:\n"
        f"            print('OK mode=CAN move=MOVE_J interface={interface}')\n"
        "            raise SystemExit(0)\n"
        "        print('Unexpected mode: 0x%02X'%data[0])\n"
        "        raise SystemExit(2)\n"
        "print('No 0x2A1 CAN-mode confirmation within 2 seconds')\n"
        "raise SystemExit(3)\n"
    )


def exit_teach_can(side: str) -> tuple[int, str]:
    """只改变控制模式，不发送关节目标、不自动运动。"""
    interface = {'left': LEFT_CAN_IF, 'right': RIGHT_CAN_IF}.get(side)
    if interface is None:
        return 1, '无效机械臂侧别'
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
             KR260_HOST, "python3", "-"],
            input=exit_teach_script(interface), capture_output=True, text=True,
            timeout=8)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, 'SSH 执行超时，未确认 CAN 模式'
    except Exception as e:  # noqa: BLE001
        return 1, f'SSH 调用失败: {type(e).__name__}: {e}'


LEFT_READ_PY = (
    "import socket,struct,time,math\n"
    "s=socket.socket(socket.PF_CAN,socket.SOCK_RAW,socket.CAN_RAW)\n"
    "s.bind(('" + LEFT_CAN_IF + "',));s.settimeout(0.3)\n"
    "j={}\n"
    "t0=time.time()\n"
    # 关节高速反馈 0x251-0x256（与 deploy arm_hardware_interface.cpp 一致）：
    # data[4:8] 大端 int32，/1000 = rad；左臂无 J1 取反（取反是右臂专用配对）
    "while time.time()-t0<1.5 and len(j)<6:\n"
    "    try:f,_=s.recvfrom(16)\n"
    "    except socket.timeout:continue\n"
    "    cid,dlc,data=struct.unpack('=IB3x8s',f)\n"
    "    if 0x251<=cid<=0x256:\n"
    "        j[cid-0x251]=math.degrees(struct.unpack('>i',data[4:8])[0]/1000.0)\n"
    "print(' '.join(f'{j.get(i,float(\"nan\")):.2f}' for i in range(6)))\n"
)


def left_read_raw() -> tuple[bool, list]:
    """在 KR260 上监听左臂 CAN 关节反馈，返回六轴角度（度）。"""
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
             KR260_HOST, "python3", "-"],
            input=LEFT_READ_PY,
            capture_output=True, text=True, timeout=6)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout).strip()
        vals = [float(v) for v in r.stdout.split()]
        if len(vals) != 6 or any(math.isnan(v) for v in vals):
            return False, LEFT_CAN_IF + " 反馈不完整（左臂未通电或未使能？）"
        return True, vals
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# 右臂 J1 反馈符号（2026-10-22 现场核对后改为不取反）。
# 历史：deploy 的 mode=2 分支曾对两臂 J1 统一取反，故读回侧给右臂再取反一次抵消。
# 现场证据表明这一口径已经对不上——J2–J6 与目标精确吻合、唯独 J1 呈镜像
# （实测 +40 vs 目标 −40），并直接导致进入流程的 J1 相位恒差 80°、45 s 超时。
# 判断方法：点「读取当前角度」，看「实际姿态预览」的 J1 是否与真机同侧。
# 若哪天又镜像了，只把下面这一个常量改回 True 并重启 arm-console，不要改别处。
RIGHT_J1_FLIP = False
_RIGHT_J1_STMT = ("j[cid-0x251]=-d if cid==0x251 else d" if RIGHT_J1_FLIP
                  else "j[cid-0x251]=d")
RIGHT_READ_PY = LEFT_READ_PY.replace(LEFT_CAN_IF, RIGHT_CAN_IF) \
    .replace("j[cid-0x251]=math.degrees(struct.unpack('>i',data[4:8])[0]/1000.0)",
             "d=math.degrees(struct.unpack('>i',data[4:8])[0]/1000.0)\n"
             "        " + _RIGHT_J1_STMT)


def right_read_raw() -> tuple[bool, list]:
    """在 KR260 上监听 can2 关节反馈（0x251-0x256，data[4:8] 大端 int32 /1000=rad）。
    J1 是否取反由 RIGHT_J1_FLIP 决定；当前为不取反（与左臂一致），
    依据见该常量处的说明。"""
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
             KR260_HOST, "python3", "-"],
            input=RIGHT_READ_PY,
            capture_output=True, text=True, timeout=6)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout).strip()
        vals = [float(v) for v in r.stdout.split()]
        if len(vals) != 6 or any(math.isnan(v) for v in vals):
            return False, "can2 反馈不完整（右臂未通电或未使能？）"
        return True, vals
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# ===== 反馈缓存（2026-10-23）=====
# 每次读六轴反馈都要在 KR260 上起一个 python 去监听 CAN，实测 230~370ms。
# 页面按 5Hz 轮询，控制循环就每 200ms 被抢走 300ms —— 20Hz 发帧被拖出 >100ms 空档，
# deploy 看门狗随即触发冻结。表现：跟随顿挫、"跟随自己退出"、会话被判超时。
# 这里用两个后台线程各自持续刷新一臂，所有读取方都只读缓存（微秒级）。
_FB_CACHE = {'right': (0.0, False, []), 'left': (0.0, False, [])}
_FB_STALE_S = 3.0


def _fb_cached(side: str) -> tuple[bool, list]:
    """读缓存；缓存过期（刷新线程刚起/异常）时才同步读一次兜底。"""
    ts, ok, vals = _FB_CACHE[side]
    if time.monotonic() - ts > _FB_STALE_S:
        ok2, vals2 = (left_read_raw if side == 'left' else right_read_raw)()
        _FB_CACHE[side] = (time.monotonic(), ok2, vals2)
        return ok2, vals2
    return ok, vals


# 两次远端读取之间的最小间隔（秒）。
# 2026-10-23：原实现没有间隔、还开了两个线程 —— 等于满速轰炸 KR260（实测 load 11.5，
# python3 占满核，deploy 被饿到 70% CPU，收帧迟到，看门狗反复冻结 → 手臂一顿一顿）。
_FB_MIN_INTERVAL = 0.35


def _fb_refresher() -> None:
    """单线程轮流刷新两臂，**带节流**。约每臂 1.4 次/秒，够页面显示用。"""
    while True:
        for side in ('right', 'left'):
            fn = left_read_raw if side == 'left' else right_read_raw
            try:
                ok, vals = fn()
            except Exception as e:  # noqa: BLE001
                ok, vals = False, f"{type(e).__name__}: {e}"
            _FB_CACHE[side] = (time.monotonic(), ok, vals)
            time.sleep(_FB_MIN_INTERVAL)


# 离线运动学／碰撞规划不需要、也不允许后台 SSH 实机反馈。
if os.environ.get('APEX_OFFLINE') != '1':
    threading.Thread(target=_fb_refresher, daemon=True, name='fb-refresher').start()


def left_read() -> tuple[bool, list]:
    """左臂六轴角度（读后台缓存，微秒级；实现见 _FB_CACHE）。"""
    return _fb_cached('left')


def right_read() -> tuple[bool, list]:
    """右臂六轴角度（读后台缓存，微秒级；实现见 _FB_CACHE）。"""
    return _fb_cached('right')


def clamp_hand(v) -> tuple[float, float, float]:
    """底盘系法兰目标：三元素数组，逐轴钳到安全盒。"""
    if not isinstance(v, list) or len(v) != 3:
        raise ValueError("right 需为三元素数组")
    out = []
    for n, lo, hi in zip(v, TARGET_LO, TARGET_HI):
        if type(n) not in (int, float) or not math.isfinite(n):
            raise ValueError("非法数值")
        out.append(max(lo, min(hi, float(n))))
    return tuple(out)


def clamp_grip(v) -> float:
    if type(v) not in (int, float) or not math.isfinite(v):
        raise ValueError("非法夹爪值")
    return max(0.0, min(1.0, float(v)))


def rpy_degrees(v, field='rpy_deg') -> tuple[float, float, float]:
    """左右臂共用：滚转/俯仰/偏航，单位度，绕底盘固定轴依次旋转。"""
    if not isinstance(v, list) or len(v) != 3:
        raise ValueError(field + ' 需为滚转/俯仰/偏航三个角度（度）')
    if any(type(n) not in (int, float) or not math.isfinite(n) or not -180.0 <= n <= 180.0
           for n in v):
        raise ValueError(field + ' 各角须为 -180～180 度内的有限数值')
    return tuple(float(n) for n in v)


def right_rpy_degrees(v) -> tuple[float, float, float]:
    """旧右臂调用兼容包装。"""
    return rpy_degrees(v, 'right_rpy_deg')


class ControlSender:
    """带使能位的实时跟随发送器（右臂）。
    链路：底盘系 XYZ 目标 → AIPC 端 DLS IK（查看器同款）→ v2 mode=2 关节直达。"""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.lock = threading.RLock()
        self.entries = {'right': None, 'left': None}
        self.entry_generation = {'right': 0, 'left': 0}
        self.entry_pending = {'right': False, 'left': False}
        # 定点移动会话：值为 'start'/'zero'，None 表示当前不是定点移动
        self.move_side = {'right': None, 'left': None}
        self.owner = None
        self.until = 0.0
        self.deadline = 0.0
        self.right = list(DEFAULT_TARGET)
        self.right_target_point = 'j5'  # 网页 EE/VR/关节直驱共享目标统一为 J5
        self.right_rpy_deg = [0.0, 0.0, 0.0]
        self.grip = 0.0
        self.joints = Q_START_RIGHT   # 当前关节目标（5° 朝前补偿，与默认 J5/RPY 自洽）
        self.ik_err = None
        self.count = 0
        # 时间种子保证左臂单独启动时，AIPC 重启后的首帧也不会被 deploy 去重。
        self.seq = int(time.time()) & 0x7FFFFFFF
        self.reason = "未开始"
        self.error = None
        # VR 跟随状态
        self.vr_on = False
        self.vr_pressing = False      # 上一拍离合是否按住
        self.vr_ref = None            # 本次按下手柄的 VR 系参考位
        self.vr_anchor = None         # 对应的底盘系目标锚点
        self.vr_info = ""
        self.vr_smooth = None         # 位置滤波后的目标（默认 One Euro）
        self.vr_position_filters = {'right': None, 'left': None}
        # 腕部姿态跟随状态（2026-10-20）：与位置同款离合增量方案
        self.vr_qref = None           # 按下沿手柄姿态矩阵（VR 系）
        self.vr_ori_anchor = None     # 按下沿的目标姿态（用户系）
        self.vr_ori_user = None       # 当前目标姿态（用户系），None=水平构型姿态
        # 2026-10-31：夹爪改纯模拟量（扳机）+ L3/R3 按住强制闭合，不再有扳机"重新武装"状态。
        # 左臂关节直达（2026-10-21）：独立于右臂的属主与心跳，滑块直接给六轴角度
        self.owner_left = None
        self.left_until = 0.0
        self.left_joints = None       # rad 六轴；None=左臂不发送（deploy 保持）
        self.left_grip = 0.0          # 闭合量 [0,1]，与右臂 grip 同约定
        self.left_reason = "未开始"
        # 左臂唯一起始位：网页归位、X 搬运与首次 VR 均使用 Q_START_LEFT。
        # J5 锚点由同一组关节角正解得到，不再从另一组默认 XYZ 反解出第二起始位。
        self.left_target = list(_fk_points(Q_START_LEFT, 'left')[0][5])
        self.left_rpy_deg = [0.0, 0.0, 0.0]
        # 左臂 VR 跟随状态（2026-10-21）：镜像右臂 VR 方案，数据源=左手柄
        self.vr_left_on = False
        self._vr_was = (False, False)  # 切离双臂模式时记住两臂是否在跟随，B 键回来时恢复
        self._preset_resume = {'right': False, 'left': False}  # A/X 抢占了跟随 → 归位完成后自动恢复
        self._web_active_at = {'right': 0.0, 'left': 0.0}      # 网页会话最后操作时刻（空闲释放用）
        self.vr_left_pressing = False
        self.vr_left_ref = None
        self.vr_left_anchor = None
        self.vr_left_qref = None
        self.vr_left_ori_anchor = None
        self.vr_left_ori_user = None
        self.vr_left_smooth = None
        self.vr_left_info = ""
        self.vr_left_trigger_armed = True
        # ===== A/B/X/Y 与模式（2026-10-22）=====
        # 位映射实采确认：A=bit0(右) B=bit1(右) X=bit2(左) Y=bit3(左)
        self.mode = 'arms'                    # 'arms' 双臂跟随 / 'base' 底盘
        # 定点移动的完成结果：前后端靠 seq 对齐，前端据此"等前一步真到位再走下一步"
        self.move_seq = 0
        self.move_result = {'right': None, 'left': None}
        self.btn_latch = arm_buttons.Latch()
        # B 短按仍切回双臂；长按 2 秒循环切换双臂 VR 平移倍率。
        self.vr_motion_scale = 1.0
        self._b_down_since = None
        self._b_long_fired = False
        self._vr_task_id = 0             # 撤销旧 X/A 流程，防止停止后继续下一段
        self._vr_route_running = False
        # 固定左臂搬运任务的机读状态：网页/VR/VLA 共用，VLA 可独立轮询，无需 SSH 状态查询。
        self._transfer = {'task_id': None, 'state': 'idle', 'stage': 'idle',
                          'source': None, 'message': '尚未执行左臂搬运',
                          'resume_vr': False, 'updated_at': time.time()}
        # C06：定点动作串行闸门。左右臂、网页/VR/多客户端都经 _call_move 这一道，
        # 同一时刻只允许一路，避免两臂同时走未做联合预检的轨迹。
        self._move_gate = threading.Lock()
        self.base_state = {'vx': 0.0, 'vy': 0.0, 'wz': 0.0, 'active': False,
                           'reason': '未在底盘模式', 'sent': 0}
        # 底盘子模式（2026-10-24）：'a'=全向平移+自旋（互斥，现状）；
        # 'b'=RC 遥控车（左摇杆油门/右摇杆转向，vx+wz 同帧）。底盘模式下按 Y 循环。
        self.base_sub = 'a'
        # ===== 2026-10-28 第一批修复（顿挫 P0-A/P1-A）=====
        # IK 异步工作器：VR 跟随的求解从发送循环剥离。发送循环只把最新目标提交到
        # 容量 1 的邮箱（新覆盖旧）；每臂一个工作线程求解，结果经版本/会话/停止
        # 复核后才提交。困难求解（实测 181~324ms）不再挡住 20Hz 发包。
        self._ik_version = {'right': 0, 'left': 0}
        self._ik_job = {'right': None, 'left': None}
        self._ik_cv = threading.Condition()
        # VR 死区滞回状态（P1-A）：quiet=静止压噪态（大门限），动过之后改小门限
        self.vr_quiet = True
        self._vr_still = 0
        self.vr_left_quiet = True
        self._vr_left_still = 0
        # 发送节拍统计（验收口径：近 400 帧的间隔分位数与超期拍数）
        self._send_prev = None
        self._send_intervals = deque(maxlen=400)
        self._tick_late = 0
        threading.Thread(target=self._loop, daemon=True).start()
        threading.Thread(target=self._base_loop, daemon=True).start()
        threading.Thread(target=self._ik_worker, args=('right',), daemon=True).start()
        threading.Thread(target=self._ik_worker, args=('left',), daemon=True).start()

    def _loop(self):
        # 2026-10-28（P0-A）：绝对截止时间调度。原来“处理完再 sleep(0.05)”，真实周期
        # = 计算耗时 + 50ms，IK 一慢发包就断档（KR260 100ms 看门狗冻结 → 顿挫）。
        # 现在每拍对齐 50ms 网格；超期不追补（不连发一串旧包），记录后重新对齐。
        period = 0.05
        next_t = time.monotonic() + period
        while True:
            self._tick()
            now = time.monotonic()
            if next_t > now:
                time.sleep(next_t - now)
            else:
                self._tick_late += 1
                next_t = now
            next_t += period

    def set_base_sub(self, sub):
        """网页 /api/base_sub 切换底盘子模式（与 VR 端 Y 键循环同一份状态）。
        切换时零速断使能一拍，避免带着旧速度换手感。"""
        if sub not in BASE_SUB_TEXT:
            raise ValueError('sub 必须为 a（全向平移+自旋）或 b（RC 遥控车）')
        with self.lock:
            self.base_sub = sub
        self._send_base_udp(0.0, 0.0, 0.0, enable=False)
        return sub

    # ==================== A/B/X/Y 与底盘模式 ====================
    # 语义（2026-10-22 与队友对齐）：
    #   Y(bit3,左手柄) 按一下 → 切底盘模式      B(bit1,右手柄) 按一下 → 切双臂模式
    #   X(bit2,左手柄) 按一下 → 左臂回起始位姿  A(bit0,右手柄) 按一下 → 右臂回起始位姿
    #   "按一下"用 arm_buttons.Latch：只在 valid 位为 1 的键上判上升沿，且必须见到
    #   "valid=1 且 pressed=0" 才重新武装（valid=0 不推断为松开）。
    MODE_BY_BIT = {3: 'base'}         # B 单独做短按/长按计时，不走上升沿立即触发
    PRESET_BY_BIT = {2: 'left', 0: 'right'}
    PRESET_TARGET = 'start'          # X/A 的"预备位"= 跟随起始位姿
    VR_SCALE_LEVELS = (1.0, 0.5, 0.25)
    VR_SCALE_NAMES = {1.0: '普通', 0.5: '精细', 0.25: '微调'}
    B_LONG_PRESS_S = 2.0

    def _activate_mode(self, mode):
        if mode != self.mode:
            self._set_mode(mode)
        elif mode == 'base':
            # 已在底盘模式时再按 Y = 循环底盘子模式（全向 ↔ RC 遥控车）。
            self.base_sub = 'b' if self.base_sub == 'a' else 'a'
            self._send_base_udp(0.0, 0.0, 0.0, enable=False)
            self.base_state.update(
                vx=0.0, vy=0.0, wz=0.0, active=False,
                reason='子模式：' + ('RC 遥控车（左摇杆油门/右摇杆转向）'
                               if self.base_sub == 'b' else '全向平移+自旋（平移优先）'))

    def _cycle_vr_scale(self):
        """B 长按入口。只在离合释放、双臂模式且无定点任务时改变配置。"""
        if self.mode != 'arms':
            self.error = 'B 长按倍率切换仅在双臂模式可用'
            return False
        if self.vr_pressing or self.vr_left_pressing:
            self.error = '请先松开两侧离合，再长按 B 切换 VR 倍率'
            return False
        if self._vr_route_running or any(self.entries.values()):
            self.error = '定点/搬运任务进行中，暂不能切换 VR 倍率'
            return False
        levels = self.VR_SCALE_LEVELS
        current = getattr(self, 'vr_motion_scale', 1.0)
        index = levels.index(current) if current in levels else 0
        self.vr_motion_scale = levels[(index + 1) % len(levels)]
        # 下一次离合按下沿会重建参考；旧滤波值不得跨倍率沿用。
        self.vr_smooth = self.vr_left_smooth = None
        name = self.VR_SCALE_NAMES[self.vr_motion_scale]
        message = f'{name}模式：VR 平移倍率 {self.vr_motion_scale:g}×'
        self.vr_info = message
        self.vr_left_info = message
        return True

    def _handle_b_button(self, snap, now):
        """B 松开且未长按=切回双臂；持续 2 秒=只切倍率。无效位不推断松开。"""
        if not ((snap['valid'] >> 1) & 1):
            return
        pressed = bool((snap['pressed'] >> 1) & 1)
        if pressed:
            if getattr(self, '_b_down_since', None) is None:
                self._b_down_since = now
                self._b_long_fired = False
            if (not self._b_long_fired
                    and now - self._b_down_since >= self.B_LONG_PRESS_S):
                self._b_long_fired = True
                if not SAFETY.status()['stopped']:
                    self._cycle_vr_scale()
            return
        if getattr(self, '_b_down_since', None) is None:
            return
        long_fired = self._b_long_fired
        self._b_down_since = None
        self._b_long_fired = False
        if not long_fired and not SAFETY.status()['stopped']:
            self._activate_mode('arms')

    def _handle_buttons(self, now):
        """处理 A/B/X/Y。B 短按在释放时执行，长按只触发一次。"""
        snap = VR.buttons(now)
        if not snap.get('fresh'):
            self.btn_latch.disarm()
            self._b_down_since = None
            self._b_long_fired = False
            return
        fired = self.btn_latch.update(snap)
        self._handle_b_button(snap, now)
        if SAFETY.status()['stopped']:
            return                    # 软件停止锁存时忽略所有按键触发
        for bit in sorted(fired):
            if bit == 1:
                continue               # B 已由上面的时长状态机处理
            mode = self.MODE_BY_BIT.get(bit)
            if mode is not None:
                self._activate_mode(mode)
                continue
            side = self.PRESET_BY_BIT.get(bit)
            if side is not None:
                if self.mode != 'arms':
                    self.error = '底盘模式下不接受臂动作：请先短按 B 切回双臂'
                    continue
                self._request_preset(side)

    def _set_mode(self, mode):
        """切模式：先撤掉所有会话并让底盘归零，避免"手指同时控制两样东西"。
        2026-10-24：切回双臂时自动恢复切走前的 VR 跟随（此前只能回网页重开，
        手柄没有重建会话的途径 —— "按 Y 出去后 VR 连不上"的根因）。"""
        # 2026-10-24 二次修：便签必须在【切离双臂】时记（按 Y），而不是切回时读
        # —— 切回时 vr_on 早已被上次切换清零，读到恒为 False（二轮实测复现）。
        if mode == 'arms':
            resume_r, resume_l = self._vr_was      # 读上次切走时的便签
            self._vr_was = (False, False)
        else:
            self._vr_was = (self.vr_on, self.vr_left_on)   # 切走前记下跟随状态
            resume_r = resume_l = False
        self._cancel_sessions('模式切换：会话已撤销')
        self._reset_vr_anchors()
        self.mode = mode
        self.base_state.update(vx=0.0, vy=0.0, wz=0.0, active=False,
                               reason='模式已切换：' + ('底盘' if mode == 'base' else '双臂'))
        self._send_base_udp(0.0, 0.0, 0.0, enable=False)
        if mode == 'arms' and (resume_r or resume_l):
            # deploy 检查要走 SSH，绝不能在本方法（持锁）里阻塞 20Hz 循环（C19 教训）
            threading.Thread(target=self._resume_vr_follow,
                             args=(resume_r, resume_l), daemon=True).start()

    def _resume_vr_follow(self, right, left):
        """B 键切回双臂后自动恢复 VR 跟随。与网页「VR 跟随」启动同语义：
        deploy 不在跑则不恢复；排队期间模式又被切走则放弃（同 C06）。"""
        if not deploy_running_cached():
            with self.lock:
                self.error = '已切回双臂，但 deploy 未运行，VR 跟随未自动恢复'
            return
        with self.lock:
            if self.mode != 'arms':
                return
            now = time.monotonic()
            self.seq = int(time.time()) & 0x7FFFFFFF  # 防 deploy seq 去重丢帧（同启动路径）
            if right:
                self.owner = 'vr-button'
                self.vr_on = True
                self.vr_pressing = False
                self.vr_smooth = None
                self.right = list(_fk_points(self.joints, 'right')[0][5])
                self.right_target_point = 'j5'
                self.vr_anchor = tuple(self.right)
                self.until = now + HEARTBEAT_S * 3
                self.reason = 'VR 跟随已自动恢复（按住侧键移动，松开保持）'
            if left:
                if self.left_joints is None:
                    self.left_joints = list(Q_START_LEFT)
                    self.left_target = list(_fk_points(self.left_joints, 'left')[0][5])
                self.owner_left = 'vr-button'
                self.vr_left_on = True
                self.vr_left_pressing = False
                self.vr_left_smooth = None
                self.vr_left_anchor = tuple(self.left_target)
                self.left_until = now + HEARTBEAT_S * 3
                self.left_reason = '左臂 VR 跟随已自动恢复（按住左侧键移动，松开保持）'

    def _vr_task_valid(self, task_id):
        with self.lock:
            return (task_id == self._vr_task_id and self.mode == 'arms'
                    and not SAFETY.status()['stopped'])

    def _move_and_wait(self, side, which, task_id, target=None):
        """启动一次定点运动并等待真实到位；返回 False 时流程不得继续。"""
        if not self._vr_task_valid(task_id):
            return False
        if target is not None:
            MOVE_TARGETS[(side, which)] = list(target)
        data = {'client': 'vr-button', 'safety_epoch': SAFETY.status()['epoch'],
                'controls': {'mode': 'left_joints' if side == 'left' else 'right_joints',
                             'move': which}}
        result, code = self._call_move(side, data)
        if code != 200:
            with self.lock:
                self.error = 'VR 流程「%s」启动失败：%s' % (which, result.get('error'))
            return False
        seq = result.get('move_seq')
        while self._vr_task_valid(task_id):
            with self.lock:
                state = dict(self.move_result.get(side) or {})
            if state.get('seq') == seq and state.get('state') in ('done', 'failed'):
                return state['state'] == 'done'
            time.sleep(0.05)
        return False

    def _slow_move_left(self, target, task_id):
        """X／VLA 共用 TOPP-RA 段；规划失败直接中止，不回退到关节直冲。"""
        leg = getattr(self, '_transfer_leg', None)
        if leg not in ('original_home', 'home_pos3', 'pos3_home', 'home_original'):
            with self.lock:
                self.error = '搬运段缺少 TOPP-RA 路径标识，已拒绝启动'
            return False
        return self._move_and_wait('left', 'toppra_' + leg, task_id, target)

    def transfer_status(self):
        """左臂固定搬运流程的轻量只读状态，不触发 KR260/SSH 查询。"""
        with self.lock:
            return dict(self._transfer)

    def _transfer_update(self, task_id, state, stage, message):
        # 调用方可已持有 self.lock（RLock）；旧任务不得覆盖新任务状态。
        with self.lock:
            if self._transfer.get('task_id') == task_id:
                self._transfer.update(state=state, stage=stage, message=message,
                                      updated_at=time.time())

    def _request_preset(self, side, source='vr', resume_vr=True):
        """X/VLA：左臂记录→搬运→释放→返回；A：双臂依次回起始位。

        VLA 默认 resume_vr=False，避免流程结束后 VR 与规划器同时抢左臂。
        返回左臂 task_id；重复触发返回 None。网页/VR 旧调用语义保持不变。
        """
        mode_at_request = self.mode
        task_id = None
        if side == 'left':
            with self.lock:
                if self._vr_route_running:
                    self.left_reason = '左臂搬运流程正在运行，请勿重复触发'
                    return None
                self._vr_route_running = True
                self._vr_task_id += 1
                task_id = self._vr_task_id
                self._transfer = {'task_id': task_id, 'state': 'accepted', 'stage': 'accepted',
                                  'source': source, 'message': '左臂搬运流程已受理',
                                  'resume_vr': bool(resume_vr), 'updated_at': time.time()}

        def run():
            if self.mode != mode_at_request:
                if task_id is not None:
                    self._transfer_update(task_id, 'cancelled', 'cancelled', '模式已变化，搬运流程取消')
                    with self.lock:
                        if task_id == self._vr_task_id:
                            self._vr_route_running = False
                return
            if side == 'left':
                label = 'VLA' if source == 'vla' else 'X'
                try:
                    with self.lock:
                        self.owner_left = None
                        self.vr_left_on = False
                        self._preset_resume['left'] = False
                        self._reset_vr_anchors('left', note=label + ' 流程：VR 跟随已结束')
                        saved_grip = self.left_grip
                    self._transfer_update(task_id, 'running', 'recording', '正在读取左臂原位与夹爪状态')
                    ok, values = left_read()
                    if not ok:
                        with self.lock:
                            self.error = label + ' 流程无法记录当前位置：' + str(values)
                            message = self.error
                        self._transfer_update(task_id, 'failed', 'recording', message)
                        return
                    original = [math.radians(v) for v in angles(values)]
                    self._transfer_update(task_id, 'running', 'recording',
                                          label + ' 已记录左臂位置与夹爪状态')
                    # 四段共用 TOPP-RA；回程反向复用去程几何路径，VLA 与 X 完全同路。
                    outbound = ((Q_START_LEFT, 'to_home', '前往起始位', 'original_home'),
                                (Q_LEFT_POS3, 'to_pos3', '前往位置 3', 'home_pos3'))
                    for target, stage, message, leg in outbound:
                        self._transfer_update(task_id, 'running', stage, message + '（TOPP-RA）')
                        self._transfer_leg = leg
                        if not self._slow_move_left(target, task_id):
                            self._transfer_update(task_id, 'failed', stage, message + '失败或已中止')
                            return
                    if not self._vr_task_valid(task_id):
                        return
                    with self.lock:
                        self.left_grip = 0.0       # 只在位置 3 松爪，六轴保持不动
                        self.owner_left = 'vla-transfer' if source == 'vla' else 'vr-button'
                        self.left_joints = list(Q_LEFT_POS3)
                        self.left_until = time.monotonic() + VR_RELEASE_WAIT_S + 1.0
                        self.left_reason = '已到位置 3：夹爪松开，等待 5 秒'
                    self._transfer_update(task_id, 'running', 'releasing', self.left_reason)
                    deadline = time.monotonic() + VR_RELEASE_WAIT_S
                    while time.monotonic() < deadline:
                        if not self._vr_task_valid(task_id):
                            return
                        time.sleep(0.05)
                    returned = ((Q_START_LEFT, 'return_home', '返回起始位', 'pos3_home'),
                                (original, 'return_original', '返回原夹取位置', 'home_original'))
                    for target, stage, message, leg in returned:
                        self._transfer_update(task_id, 'running', stage, message + '（TOPP-RA）')
                        self._transfer_leg = leg
                        if not self._slow_move_left(target, task_id):
                            self._transfer_update(task_id, 'failed', stage, message + '失败或已中止')
                            return
                    with self.lock:
                        self.left_grip = saved_grip
                        self.owner_left = 'vla-transfer' if source == 'vla' else 'vr-button'
                        self.left_joints = list(original)
                        # 以返回后的实际六轴目标重建 J5 与 VR 锚点，不能沿用手柄旧参考系。
                        self.left_target = list(_fk_points(original, 'left')[0][5])
                        self.vr_left_anchor = tuple(self.left_target)
                        self.vr_left_ref = None
                        self.vr_left_qref = None
                        self.vr_left_ori_anchor = None
                        self.vr_left_ori_user = None
                        self.vr_left_smooth = None
                        self.vr_left_pressing = False
                        self.vr_left_on = bool(resume_vr)
                        self.left_until = time.monotonic() + HEARTBEAT_S * 3
                        self.left_reason = (label + ' 流程完成：已返回原位并恢复夹持' +
                                            ('，VR 跟随已自动恢复' if resume_vr else '，VR 保持关闭'))
                        message = self.left_reason
                    self._transfer_update(task_id, 'done', 'done', message)
                except Exception as exc:  # 状态接口必须如实反映 worker 异常，不能永远卡在 running。
                    self._transfer_update(task_id, 'failed', 'exception',
                                          '左臂搬运内部异常：%s' % exc)
                    raise
                finally:
                    with self.lock:
                        if task_id == self._vr_task_id:
                            self._vr_route_running = False
            else:
                # 双臂尚未做联合轨迹碰撞预检，沿用串行闸门依次归位。
                with self.lock:
                    # A 只保存 VR 状态：普通网页跟随归位后仍保持停止。
                    resume_home_vr = (self.vr_on, self.vr_left_on)
                    self._vr_task_id += 1
                    self._vr_route_running = False
                    self._cancel_sessions('A 键：停止当前任务，双臂依次回起始位')
                    home_task_id = self._vr_task_id
                for arm in ('right', 'left'):
                    if not self._move_and_wait(arm, 'start', home_task_id):
                        return
                if any(resume_home_vr):
                    # 两臂均真实到位后，复用模式切换的恢复路径重建离合锚点。
                    self._resume_vr_follow(*resume_home_vr)

        threading.Thread(target=run, daemon=True).start()
        return task_id

    def _send_base_udp(self, vx, vy, wz, enable, rc=False):
        """底盘指令下发（VR 驱动用，不走网页的 safety_epoch 校验）。
        rc=True 时 relay 走 RC 子模式（档位 6 同帧 vx+wz，4T4D 行进转向）。"""
        if SAFETY.stopped:
            vx = vy = wz = 0.0
            enable = False
        pkt = dict(vx=round(vx, 4), vy=round(vy, 4), wz=round(wz, 4), enable=bool(enable),
                   rc=bool(rc))
        try:
            BASE_UDP.sendto(json.dumps(pkt).encode(), BASE_UDP_TARGET)
            with self.lock:
                self.base_state['sent'] += 1
            return True
        except Exception:             # noqa: BLE001
            return False

    def _base_loop(self):
        """底盘模式下的 20Hz 摇杆驱动。只在 mode=='base' 时发送，避免与网页抢底盘。"""
        was_base = False
        while True:
            try:
                with self.lock:
                    mode = self.mode
                if mode != 'base':
                    if was_base:
                        self._send_base_udp(0.0, 0.0, 0.0, enable=False)
                        was_base = False
                    with self.lock:
                        self.base_state.update(vx=0.0, vy=0.0, wz=0.0, active=False,
                                               reason='未在底盘模式（按 Y 切换）')
                else:
                    was_base = True
                    now = time.monotonic()
                    ver, recv, istate = VR.latest()[:3]
                    snap = VR.raw_snapshot(now)          # C03：带时效的内部快照
                    lstick, rstick = snap['lstick'], snap['rstick']
                    held = (snap['lsidegrip'] > 0.5) or (snap['rsidegrip'] > 0.5)   # 任一侧键
                    rc = self.base_sub == 'b'
                    cmd = base_drive.command(lstick, rstick, held=held,
                                             fresh=snap['fresh'], input_state=istate,
                                             rc=rc)
                    self._send_base_udp(cmd['vx'], cmd['vy'], cmd['wz'],
                                        enable=cmd['active'] or held, rc=rc)
                    with self.lock:
                        self.base_state.update(vx=cmd['vx'], vy=cmd['vy'], wz=cmd['wz'],
                                               active=cmd['active'], reason=cmd['reason'])
            except Exception as exc:      # noqa: BLE001
                with self.lock:
                    self.base_state.update(vx=0.0, vy=0.0, wz=0.0, active=False,
                                           reason='底盘驱动异常：' + type(exc).__name__)
            time.sleep(0.05)

    @staticmethod
    def _vr_pose_ok(pos, quat):
        """C07：位姿结构校验。长度/类型/有限性/四元数范数任一不合格即为"本拍无有效位姿"。

        原来直接 pos[0] 与 _quat_to_R(quat)，一个长度错误的四元数就会让工作线程
        以未捕获异常退出——HTTP 服务还在，但没人再发帧，页面看不出区别。
        """
        if not isinstance(pos, (tuple, list)) or len(pos) != 3:
            return False
        if not isinstance(quat, (tuple, list)) or len(quat) != 4:
            return False
        try:
            vals = [float(v) for v in list(pos) + list(quat)]
        except (TypeError, ValueError):
            return False
        if any(not math.isfinite(v) for v in vals):
            return False
        norm = math.sqrt(sum(float(v) * float(v) for v in quat))
        return norm > 1e-6

    # ==================== IK 异步工作器（2026-10-28，P0-A）====================
    def _ik_submit(self, side, tgt, Rtgt_native, seed, ori_new, ctx):
        """提交最新 IK 目标（调用方须持有 self.lock）。容量 1 邮箱：新目标覆盖未处理的旧目标，
        版本号 +1 使晚到的旧结果自动作废。求解本身在 _ik_worker 线程、不持发送锁。"""
        self._ik_version[side] += 1
        job = (self._ik_version[side], list(tgt), Rtgt_native, list(seed), ori_new, ctx)
        with self._ik_cv:
            self._ik_job[side] = job
            self._ik_cv.notify_all()

    def _ik_worker(self, side):
        """IK 工作线程（每臂一个）。求解不持锁；提交前复核版本、会话存活、进入序列
        与全局停止——任一失效都丢弃结果，绝不让旧目标在停止/切换后复活。"""
        while True:
            with self._ik_cv:
                while self._ik_job[side] is None:
                    self._ik_cv.wait()
                job = self._ik_job[side]
                self._ik_job[side] = None
            ver, tgt, Rtgt_native, seed, ori_new, ctx = job
            try:
                q, err = solve_vr_pose_two_point_user(list(tgt), ori_new, list(seed), side=side)
            except Exception as exc:            # noqa: BLE001
                q, err = None, 'IK 工作器异常：' + type(exc).__name__
            with self.lock:
                if ver != self._ik_version[side]:
                    continue                    # 已有更新目标，旧结果作废
                alive = ((self.vr_on and self.owner is not None and self.vr_pressing)
                         if side == 'right' else
                         (self.vr_left_on and self.owner_left is not None and self.vr_left_pressing))
                if not alive or self.entries[side] is not None:
                    continue                    # 会话结束/进入序列接管：不得复活旧目标
                if SAFETY.status()['stopped']:
                    continue
                delta, ang_deg = ctx
                if side == 'right':
                    if q is not None:
                        self.joints = q
                        self.right = list(tgt)
                        self.vr_ori_user = ori_new
                        self.ik_err = None
                        self.vr_info = (f"跟随中 目标=({tgt[0]:+.3f},{tgt[1]:+.3f},{tgt[2]:+.3f}) "
                                        f"ΔVR=({delta[0]:+.3f},{delta[1]:+.3f},{delta[2]:+.3f}) "
                                        f"转腕={ang_deg:.1f}°" + (f"（{err}）" if err else ""))
                    else:
                        self.ik_err = err
                        self.vr_info = f"目标不可达，保持原位（{err}）"
                else:
                    if q is not None:
                        self.left_joints = q
                        self.left_target = list(tgt)
                        self.vr_left_ori_user = ori_new
                        self.vr_left_info = (f"左臂跟随中 目标=({tgt[0]:+.3f},{tgt[1]:+.3f},{tgt[2]:+.3f}) "
                                             f"ΔVR=({delta[0]:+.3f},{delta[1]:+.3f},{delta[2]:+.3f}) "
                                             f"转腕={ang_deg:.1f}°" + (f"（{err}）" if err else ""))
                    else:
                        self.vr_left_info = f"左臂目标不可达，保持原位（{err}）"

    def _send_stats(self):
        """发送节拍统计（P0-A 验收口径）。须在 self.lock 内调用。单位 ms。"""
        iv = sorted(self._send_intervals)
        if len(iv) < 10:
            return {'n': len(iv), 'late_ticks': self._tick_late}
        def pct(p):
            return round(iv[min(len(iv) - 1, int(p * len(iv)))] * 1000, 1)
        return {'n': len(iv), 'p50_ms': pct(0.50), 'p95_ms': pct(0.95),
                'p99_ms': pct(0.99), 'max_ms': round(iv[-1] * 1000, 1),
                'late_ticks': self._tick_late}

    def _vr_filter_position(self, side, raw, current, now):
        """滤波左右臂共享；vr_smooth=None 时重新初始化，避免跨离合沿用旧状态。"""
        smooth_attr = 'vr_smooth' if side == 'right' else 'vr_left_smooth'
        previous = getattr(self, smooth_attr, None)
        filters = getattr(self, 'vr_position_filters', None)
        if filters is None:
            filters = self.vr_position_filters = {'right': None, 'left': None}
        if previous is None:
            previous = tuple(current)
            setattr(self, smooth_attr, previous)
            filters[side] = None
        if VR_POSITION_FILTER == 'ema':
            return tuple(previous[i] + 0.25 * (raw[i] - previous[i]) for i in range(3))
        filt = filters[side]
        if filt is None:
            scale = max(0.01, float(getattr(self, 'vr_motion_scale', 1.0)))
            filt = filters[side] = OneEuroFilter3(
                previous, min_cutoff=VR_ONE_EURO_MIN_CUTOFF,
                beta=VR_ONE_EURO_BETA / scale, d_cutoff=VR_ONE_EURO_D_CUTOFF)
        return filt(raw, now)

    def _vr_update_grip(self, side, trigger, stick, bit):
        """夹爪 = 扳机模拟量；该侧摇杆按下（L3/R3）按一次切换"闭合锁存"。

        2026-11-01 实测定案（用户要求：按一次闭合到上限，再按一次松开）：
          * 扳机是纯模拟量：grip = clamp(trigger)，0=开、1=闭合，连续可调；
          * L3/R3 是"按一下切换"的边沿锁存：每次检测到该 bit 从未按下→按下的
            上升沿，闭合锁存取反——锁存成立时 grip=1（闭合到上限），
            锁存释放后 grip 回到当前扳机值（扳机 0 则夹爪自然打开）；
          * 边沿只在 key15 合规且该 bit valid=1 的帧上判定；key15 缺失/不合规或
            该 bit valid=0 时**完全不动**边沿状态与锁存（本帧读不到 ≠ 松开）——
            恢复后若上次记忆是"未按下"，下一次按下即构成新边沿；若用户在整个
            数据缺口期间一直按着，记忆仍是"已按下"，必须见到一次松键才会把
            下一次按下当成新的切换，防止缺口恢复那帧连切两次；
          * VR 数据整体过期时不调用本函数（调用方先行返回），保持最后夹爪开度。
        """
        try:
            close = float(trigger)
        except (TypeError, ValueError):
            close = 0.0
        if not math.isfinite(close):
            close = 0.0
        close = min(1.0, max(0.0, close))
        sfx = 'r' if side == 'right' else 'l'
        lat_attr = 'vr_grip_latched_' + sfx
        prev_attr = 'vr_grip_sb_prev_' + sfx
        latched = getattr(self, lat_attr, False)
        # 初始按"已知松开"处理：上电后的第一次按下即构成释放→按下边沿。
        prev = getattr(self, prev_attr, False)
        if stick is not None and (stick['valid'] >> bit) & 1:
            now_pressed = bool((stick['pressed'] >> bit) & 1)
            if prev is False and now_pressed:
                latched = not latched
                setattr(self, lat_attr, latched)
            setattr(self, prev_attr, now_pressed)
        setattr(self, 'grip' if side == 'right' else 'left_grip',
                1.0 if latched else close)

    def _vr_step(self, now):
        """VR：位置按离合增量，姿态按本会话固定参考的绝对朝向，扳机模拟量控夹爪、R3 按一下切换闭合锁存。"""
        ver, recv, istate, pos, quat, trigger, sidegrip, verr, _lp, _lq, _lt, _ls, sb = VR.latest()
        fresh = ver is not None and (now - recv) < VR_FRESH_S
        if not fresh:
            self.vr_pressing = False
            self.vr_info = f"等待 VR 数据（{verr or '无新包'}）"
            return False
        if not self._vr_pose_ok(pos, quat):
            # C07：链路是新鲜的，但位姿本身不可用。保持心跳、保持不动，
            # 不要因为一个坏包把会话踢掉（那会让人误以为"VR 掉线"）。
            self.vr_pressing = False
            self.vr_info = 'VR 位姿无效（长度/NaN/零四元数）：本拍保持不动'
            return True
        self._vr_update_grip('right', trigger, sb, 1)
        if self.vr_ori_user is None:
            self.vr_ori_user = _mm(_rz(CALIB['right']['yaw']), _mm(_FR, _fk(self.joints)[1]))
        if self.vr_qref is None:
            # 绝对朝向：整个 VR 会话只在第一帧有效手姿建立一次参考；
            # 后续松开/重按侧键只改变位置锚点，不再重置姿态参考。
            self.vr_qref = _quat_to_R(quat)
            self.vr_ori_anchor = self.vr_ori_user
        # 离合 = 侧键(k2) 模拟量过半；位置仍为增量，姿态为会话绝对量。
        pressing = (sidegrip > 0.5 and bool(istate & 0x04)
                    and pos is not None and quat is not None)
        if pressing:
            if not self.vr_pressing:
                self.vr_ref = pos
                self.vr_anchor = tuple(self.right)
                self.vr_pressing = True
                self.vr_quiet = True         # P1-A：新一段离合从压噪态开始
                self._vr_still = 0
            delta = (pos[0] - self.vr_ref[0], pos[1] - self.vr_ref[1], pos[2] - self.vr_ref[2])
            # 位置映射：X右=-ΔVR.y  Y前=+ΔVR.x  Z上=+ΔVR.z；精细档同时缩放平移与姿态。
            scale = getattr(self, 'vr_motion_scale', 1.0)
            raw = (self.vr_anchor[0] - delta[1] * scale,
                   self.vr_anchor[1] + delta[0] * scale,
                   self.vr_anchor[2] + delta[2] * scale)
            # 姿态增量：VR 系增量 RΔ=Rc·Rrefᵀ，共轭变换到底盘用户系（同一 FR 映射），
            # 左乘到按下沿锚定姿态上——与位置增量同一套离合语义。
            Rc = _quat_to_R(quat)
            Rd_vr = _mm(Rc, _mt(self.vr_qref))
            Rd = _mm(_mm(_FR, Rd_vr), _FRT)
            ori_new = _scale_rotation(self.vr_ori_anchor, _mm(Rd, self.vr_ori_anchor), scale)
            # 2026-10-31：固定 EMA 升级为 One Euro。静止时保留较强压噪，
            # 快速运动时提高截止频率以降低拖尾；原有死区滞回保持不变。
            if self.vr_smooth is None:
                self.vr_smooth = tuple(self.right)
            sm = self._vr_filter_position('right', raw, self.right, now)
            Re = _mm(ori_new, _mt(self.vr_ori_user))
            tr = Re[0][0] + Re[1][1] + Re[2][2]
            ang = math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0)))
            d_pos = max(abs(sm[i] - self.right[i]) for i in range(3))
            accept = (d_pos >= 0.002 * scale or ang >= 0.03 * scale) if self.vr_quiet \
                else (d_pos >= 0.0004 * scale or ang >= 0.006 * scale)
            if not accept:
                self.vr_smooth = sm
                self._vr_still += 1
                if self._vr_still >= 15:
                    self.vr_quiet = True
                self.vr_info = (f"跟随中（静止·滤波保持）目标=({self.right[0]:+.3f},"
                                f"{self.right[1]:+.3f},{self.right[2]:+.3f})")
                return True
            self._vr_still = 0
            self.vr_quiet = False
            self.vr_smooth = sm
            right = tuple(max(lo, min(hi, v)) for v, lo, hi in zip(sm, TARGET_LO, TARGET_HI))
            Rtgt_native = _mm(_FRT, ori_new)   # 用户系 = FR·原生 → 原生 = FRᵀ·用户
            # 2026-10-28（P0-A）：IK 移出发送循环——提交到异步工作器（容量 1 邮箱），
            # 结果由工作器经版本/会话复核后提交；困难求解不再阻塞 20Hz 发包。
            self._ik_submit('right', right, Rtgt_native, self.joints, ori_new,
                            (delta, math.degrees(ang)))
            self.vr_info = (f"跟随中 目标=({right[0]:+.3f},{right[1]:+.3f},{right[2]:+.3f}) "
                            f"ΔVR=({delta[0]:+.3f},{delta[1]:+.3f},{delta[2]:+.3f}) "
                            f"转腕={math.degrees(ang):.1f}°")
        else:
            self.vr_pressing = False
            self.vr_smooth = None     # 松开离合后下次按压重新初始化滤波器
            hand = "右手跟踪中" if istate & 0x04 else "右手未跟踪"
            self.vr_info = f"{hand}，按住侧键开始跟随（目标保持）"
        return True

    def _vr_step_left(self, now):
        """左臂 VR 跟随一拍：镜像右臂方案，数据源=左手柄（bit1 跟踪有效）。
        映射与右臂同一套：X右=-ΔVR.y  Y前=+ΔVR.x  Z上=+ΔVR.z，离合=左侧键 k2。"""
        ver, recv, istate, _p, _q, _t, _s, verr, pos, quat, trigger, sidegrip, sb = VR.latest()
        fresh = ver is not None and (now - recv) < VR_FRESH_S
        if not fresh:
            self.vr_left_pressing = False
            self.vr_left_info = f"等待 VR 数据（{verr or '无新包'}）"
            return False
        if not self._vr_pose_ok(pos, quat):
            # 与右臂 C07 一致：坏位姿只保持本拍，不撤销会话、不提交 IK。
            self.vr_left_pressing = False
            self.vr_left_info = '左臂 VR 位姿无效（长度/NaN/零四元数）：本拍保持不动'
            return True
        self._vr_update_grip('left', trigger, sb, 0)
        if self.vr_left_ori_user is None:
            seed = self.left_joints if self.left_joints else QLEVEL
            self.vr_left_ori_user = _mm(_rz(CALIB['left']['yaw']), _mm(_FR, _fk(seed)[1]))
        if self.vr_left_qref is None:
            self.vr_left_qref = _quat_to_R(quat)
            self.vr_left_ori_anchor = self.vr_left_ori_user
        pressing = (sidegrip > 0.5 and bool(istate & 0x02)
                    and pos is not None and quat is not None)
        if pressing:
            if not self.vr_left_pressing:
                self.vr_left_ref = pos
                self.vr_left_anchor = tuple(self.left_target)
                self.vr_left_pressing = True
                self.vr_left_quiet = True      # P1-A：新一段离合从压噪态开始
                self._vr_left_still = 0
            delta = (pos[0] - self.vr_left_ref[0], pos[1] - self.vr_left_ref[1],
                     pos[2] - self.vr_left_ref[2])
            scale = getattr(self, 'vr_motion_scale', 1.0)
            raw = (self.vr_left_anchor[0] - delta[1] * scale,
                   self.vr_left_anchor[1] + delta[0] * scale,
                   self.vr_left_anchor[2] + delta[2] * scale)
            Rc = _quat_to_R(quat)
            Rd_vr = _mm(Rc, _mt(self.vr_left_qref))
            Rd = _mm(_mm(_FR, Rd_vr), _FRT)
            ori_new = _scale_rotation(self.vr_left_ori_anchor,
                                      _mm(Rd, self.vr_left_ori_anchor), scale)
            if self.vr_left_smooth is None:
                self.vr_left_smooth = tuple(self.left_target)
            sm = self._vr_filter_position('left', raw, self.left_target, now)
            Re = _mm(ori_new, _mt(self.vr_left_ori_user))
            tr = Re[0][0] + Re[1][1] + Re[2][2]
            ang = math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0)))
            # 滞回门限随倍率缩小，与右臂一致，避免精细档小动作被过滤。
            d_pos = max(abs(sm[i] - self.left_target[i]) for i in range(3))
            accept = (d_pos >= 0.002 * scale or ang >= 0.03 * scale) if self.vr_left_quiet \
                else (d_pos >= 0.0004 * scale or ang >= 0.006 * scale)
            if not accept:
                self.vr_left_smooth = sm
                self._vr_left_still += 1
                if self._vr_left_still >= 15:
                    self.vr_left_quiet = True
                self.vr_left_info = (f"左臂跟随中（静止·滤波保持）目标=({self.left_target[0]:+.3f},"
                                     f"{self.left_target[1]:+.3f},{self.left_target[2]:+.3f})")
                return True
            self._vr_left_still = 0
            self.vr_left_quiet = False
            self.vr_left_smooth = sm
            tgt = tuple(max(lo, min(hi, v)) for v, lo, hi in zip(sm, TARGET_LO, TARGET_HI))
            Rtgt_native = _mm(_FRT, ori_new)
            seed = self.left_joints if self.left_joints else QLEVEL
            # 2026-10-28（P0-A）：IK 提交异步工作器，不再阻塞发送循环
            self._ik_submit('left', tgt, Rtgt_native, seed, ori_new,
                            (delta, math.degrees(ang)))
            self.vr_left_info = (f"左臂跟随中 目标=({tgt[0]:+.3f},{tgt[1]:+.3f},{tgt[2]:+.3f}) "
                                 f"ΔVR=({delta[0]:+.3f},{delta[1]:+.3f},{delta[2]:+.3f}) "
                                 f"转腕={math.degrees(ang):.1f}°")
        else:
            self.vr_left_pressing = False
            self.vr_left_smooth = None
            hand = "左手跟踪中" if istate & 0x02 else "左手未跟踪"
            self.vr_left_info = f"{hand}，按住左侧键开始跟随（目标保持）"
        return True

    def _tick(self):
        """工作循环入口（C07）：任何未预期异常都不得让发送线程静默退出。

        线程死了而 HTTP 服务还在，是最难发现的分裂状态：页面一切正常，
        实际没有任何帧在发，执行端可能还在逼近旧目标。这里把异常转成
        故障态 + 全局停止锁存，然后继续下一拍（锁存后 _tick_body 会直接返回）。
        """
        try:
            self._tick_body()
        except Exception as exc:      # noqa: BLE001
            self.error = '控制循环异常：%s: %s（已锁存软件停止）' % (type(exc).__name__, exc)
            try:
                stop_all()
            except Exception:         # noqa: BLE001
                pass

    def _tick_body(self):
        with self.lock:
            if SAFETY.status()['stopped']:
                return
            now = time.monotonic()
            self._handle_buttons(now)     # A/B/X/Y：切模式、回起始位姿
            for side, entry in self.entries.items():
                if entry is None:
                    continue
                try:
                    entry.check(now)
                    is_vr = self.vr_on if side == 'right' else self.vr_left_on
                    # 2026-10-24：VR 会话不再受 120s 轮次期限限制（用户要求取消；
                    # VR 的存活由输入新鲜度 + 5s 心跳 + deploy 看门狗保证）。
                    if side == 'right' and not is_vr and now >= self.deadline:
                        raise ValueError('进入跟随中止：本轮期限已到')
                    if is_vr:
                        snap = VR.latest()
                        if snap[0] is None or now-snap[1] >= VR_FRESH_S or snap[7]:
                            raise ValueError('进入跟随中止：VR 输入失效')
                    # 2026-10-23 修：非 VR 进入序列不再被"页面心跳"秒级掐断。
                    # 采集器实锤（err='进入跟随中止：页面心跳过期'，phL=body_to_...）：
                    # 会话租约只有 3 秒，而一次进入要几秒，页面又只在拖滑块时发包，
                    # 于是进入必被掐断 → 停了又重开 → "一卡一卡"。
                    # 存活改由 deadline(120s)、显式停止和 deploy 的 100ms 看门狗兜底；
                    # VR 模式的输入新鲜度检查保留（那才是真正的安全信号）。
                    if side == 'right':
                        self.joints = entry.command
                        if is_vr: self.until = now + HEARTBEAT_S
                    else:
                        self.left_joints = entry.command
                        if is_vr: self.left_until = now + HEARTBEAT_S
                    self._follow_geo_guard(side, self.count)     # C09
                except ValueError as exc:
                    self._abort(side, entry, exc)
                    return
            # 左臂属主心跳：VR 模式数据新鲜即续拍；过期停发（右臂逻辑不受影响）
            if self.owner_left is not None:
                if self.entries['left'] is None:
                    try:
                        self._follow_geo_guard('left', self.count)      # C09
                    except ValueError as exc:
                        self.error = str(exc)
                        self.left_reason = str(exc)
                        stop_all()
                        return
                if self.vr_left_on and self.entries['left'] is None:
                    if self._vr_step_left(now):
                        self.left_until = now + HEARTBEAT_S
                if (self.entries['left'] is None and self.owner_left is not None
                        and self.owner_left != 'stationary-gripper'):
                    # 普通跟随持续续期；静止夹爪短会话必须按原截止时间释放。
                    self.left_until = now + 5.0
                if now >= self.left_until:
                    self.owner_left = None
                    self.left_joints = None
                    self.vr_left_on = False
                    self.move_side['left'] = None
                    self.left_reason = "左臂心跳过期，已停发"
            # 网页会话空闲自动释放（2026-10-24）：非 VR 的网页会话 60s 无任何操作即让位。
            # 背景：一轮实测中残留网页会话挡住 VR 按键约 1 分钟（741 条「另一页面正在控制」）。
            # VR 会话由手柄数据流维持（vr_on），不适用；归位/进入动作期间（entry 在）不适用。
            if (self.owner is not None and not self.vr_on
                    and self.entries['right'] is None
                    and now - self._web_active_at['right'] > 60.0):
                self.owner = None
                self.reason = '网页会话空闲超时，已自动释放'
            if (self.owner_left is not None and not self.vr_left_on
                    and self.entries['left'] is None and not self._vr_route_running
                    and now - self._web_active_at['left'] > 60.0):
                self.owner_left = None
                self.left_joints = None
                self.left_reason = '网页会话空闲超时，已自动释放'
            if self.owner is None and self.owner_left is None:
                return
            if self.owner is not None:
                if self.entries['right'] is None:
                    # C09：跟随期持续检查。此刻手臂确实在动，余量不足按故障处理（锁停）。
                    try:
                        self._follow_geo_guard('right', self.count)
                    except ValueError as exc:
                        self.error = str(exc)
                        self.reason = str(exc)
                        stop_all()
                        return
                if self.vr_on and self.entries['right'] is None:
                    # VR 模式：数据新鲜即续心跳；不新鲜则心跳自然过期停发（安全）
                    if self._vr_step(now):
                        self.until = now + HEARTBEAT_S
                if self.entries['right'] is None and self.owner is not None:
                    # 2026-10-23 修：**跟随态不能靠 1 秒心跳活着**。
                    # 页面的 rightPush() 只在拖动滑块/关节时才发，没有定时器，
                    # 所以非 VR 的纯跟随根本没有心跳源 —— 1 秒后租约到期，会话被撤销，
                    # deploy 随后收不到帧，手臂停住。表现就是"跟随自己退出"。
                    # 现在跟随态由 deadline（120s）管存活；目标更新仍然要求新鲜输入
                    # （_vr_step 不新鲜就不更新目标，臂保持），deploy 的 100ms 看门狗
                    # 仍然会在真的没有帧时立即冻结。安全属性不变，只是会话不再被误杀。
                    # 2026-10-23 二次修：余量从 1 秒加到 5 秒。采集器实测：
                    # 跟随 21 秒时 active 由 True 变 False 且 reason 不变 —— 就是这条
                    # 租约在循环被慢调用卡住 >1s 时静默过期。真正的安全网是 deploy 的看门狗。
                    # 2026-10-24：VR 会话不再受 deadline 限制（存活 = 输入新鲜 + 5s 心跳 +
                    # deploy 看门狗）；deadline 只对非 VR 的网页会话生效。
                    self.until = now + 5.0
                # 2026-10-24：VR 会话豁免 120s deadline（非 VR 的网页会话仍由它兜底）。
                if now >= self.until or (not self.vr_on and now >= self.deadline):
                    self.owner = None
                    self.vr_on = False
                    self.move_side['right'] = None
                    self.reason = "心跳过期或本轮结束，已停发"
            try:
                self.seq = (self.seq + 1) & 0x7FFFFFFF
                # v2 mode=2 关节直达：deploy 不做坐标变换，只限速执行。
                # J1 反号修正已下沉到 deploy 内部（teleop_task_runner.cpp mode=2
                # 分支，2026-10-19），发送方直接使用查看器/物理约定角度。
                # C11：发送边界统一钳制到执行端接受范围。
                # 这样无论目标来自 IK、VR 还是关节直驱，"我们发的" 恒等于 "执行端接受的"，
                # 执行端那句 clipped 告警应当永不触发（触发了就说明这里被绕过）。
                if self.owner is not None:
                    right_joints = tuple(min(hi, max(lo, v)) for v, lo, hi
                                         in zip(self.joints, JOINT_LO, JOINT_HI))
                else:
                    right_joints = None
                left_joints = (None if self.left_joints is None else
                               tuple(min(hi, max(lo, v)) for v, lo, hi
                                     in zip(self.left_joints, JOINT_LO, JOINT_HI)))
                frame = encode_v2(self.seq, right_joints, 1.0 - self.grip,
                                  left_joints, 1.0 - self.left_grip,
                                  self.owner_left is not None)
                with SAFETY.lock:
                    if SAFETY.stopped:
                        return
                    self.sock.sendto(frame, UDP_TARGET)
                self.count += 1
                # P0-A 验收埋点：记录真实发送间隔（只有实际发帧才计，空闲不算）
                t_sent = time.monotonic()
                if self._send_prev is not None:
                    self._send_intervals.append(t_sent - self._send_prev)
                self._send_prev = t_sent
                # C02：这一帧确实发出去了；对应臂此后若失败，"是否动过"才有据可查。
                for _side, _entry in self.entries.items():
                    if _entry is not None:
                        _entry.sent_any = True
            except Exception as e:  # noqa: BLE001
                self.error = type(e).__name__
                self.owner = None
                self.owner_left = None
                self.reason = "发送失败，已停止"
                if any(self.entries.values()): stop_all()

    def _mask(self) -> int:
        """当前帧将要携带的 enable_mask（供状态显示，与实际下发保持同一表达式）。"""
        mask = ENABLE_RIGHT if self.owner is not None else 0x0001
        if self.left_joints is not None:
            mask |= ENABLE_LEFT
        elif self.owner_left is not None:
            mask |= 0x0010      # 仅左夹爪使能
        return mask

    def _reset_vr_anchors(self, side=None, note='锚点已清空'):
        """统一重建 VR 离合锚点（C17）。

        离合是"增量"语义：按下沿记录参考位，之后的位移叠加到**错点时的目标**上。
        只要目标被别的路径改过（定点动作、关节直驱、模式切换、会话结束），
        旧锚点就过期了；不清掉的话，下一次握侧键会以旧目标解释新手柄增量，
        出现"手没动、臂却跳一下"。清成 None 后，按下沿会按**当前状态**重建。
        """
        sides = (side,) if side else ('right', 'left')
        for _s in sides:
            # P0-A：锚点失效 = 跟随目标被外部路径改写，挂起的异步 IK 结果一并作废
            self._ik_version[_s] += 1
            if _s == 'right':
                self.vr_ref = None
                self.vr_anchor = None
                self.vr_qref = None
                self.vr_ori_anchor = None
                self.vr_ori_user = None
                self.vr_smooth = None
                self.vr_pressing = False
            else:
                self.vr_left_ref = None
                self.vr_left_anchor = None
                self.vr_left_qref = None
                self.vr_left_ori_anchor = None
                self.vr_left_ori_user = None
                self.vr_left_smooth = None
                self.vr_left_pressing = False
        if note:
            if side in (None, 'right'):
                self.vr_info = note
            if side in (None, 'left'):
                self.vr_left_info = note

    def _send_side_hold(self, side):
        """撤销本侧前发一帧 mode=0；另一臂若活动则原目标随帧保持不变。"""
        if side not in ('right', 'left'):
            raise ValueError('未知机械臂侧别')
        with self.lock:
            right_joints = None
            left_joints = None
            if side == 'left' and self.owner is not None:
                right_joints = tuple(min(hi, max(lo, v)) for v, lo, hi
                                     in zip(self.joints, JOINT_LO, JOINT_HI))
            if side == 'right' and self.owner_left is not None and self.left_joints is not None:
                left_joints = tuple(min(hi, max(lo, v)) for v, lo, hi
                                    in zip(self.left_joints, JOINT_LO, JOINT_HI))
            self.seq = (self.seq + 1) & 0x7FFFFFFF
            frame = encode_v2(self.seq, right_joints, 1.0 - self.grip,
                              left_joints, 1.0 - self.left_grip,
                              self.owner_left is not None)
            try:
                with SAFETY.lock:
                    self.sock.sendto(frame, UDP_TARGET)
                return None
            except Exception as exc:  # 停发失败必须可见，不能伪称执行端已保持。
                self.error = '单臂保持帧发送失败：%s' % exc
                return self.error

    def _cancel_side_session(self, side, note='本侧会话已撤销'):
        """只撤销指定臂；另一臂的跟随、定点移动和搬运任务保持有效。"""
        if side not in ('right', 'left'):
            raise ValueError('未知机械臂侧别')
        with self.lock:
            if side == 'left':
                transfer = getattr(self, '_transfer', None)
                if transfer and transfer.get('state') in ('accepted', 'running'):
                    transfer.update(state='cancelled', stage='cancelled',
                                    message=note, updated_at=time.time())
                self._vr_task_id = getattr(self, '_vr_task_id', 0) + 1
                self._vr_route_running = False
            self.entries[side] = None
            self.entry_generation[side] += 1
            self.entry_pending[side] = False
            self.move_side[side] = None
            self._preset_resume[side] = False
            if side == 'right':
                self.owner = None
                self.vr_on = False
                self.reason = note
            else:
                self.owner_left = None
                self.left_joints = None
                self.vr_left_on = False
                self.left_reason = note
            self._reset_vr_anchors(side, note='本侧会话已撤销：离合锚点清空')

    def _cancel_sessions(self, note='会话已撤销'):
        """撤掉双臂/VR 会话与定点移动状态（不锁存、不等 SSH）。调用方可已持有 self.lock。"""
        with self.lock:
            transfer = getattr(self, '_transfer', None)
            if transfer and transfer.get('state') in ('accepted', 'running'):
                transfer.update(state='cancelled', stage='cancelled',
                                message=note, updated_at=time.time())
            self._vr_task_id = getattr(self, '_vr_task_id', 0) + 1
            self._vr_route_running = False
            for _side in ('right', 'left'):
                self.entries[_side] = None
                self.entry_generation[_side] += 1
                self.entry_pending[_side] = False
                self.move_side[_side] = None
            self.owner = self.owner_left = None
            self.left_joints = None
            self.vr_on = self.vr_left_on = False
            self.vr_pressing = self.vr_left_pressing = False
            # 2026-10-24 三轮实测补：归位被模式切换中途打断时，_preset_resume 会悬空，
            # 之后任何一次无关归位完成都会意外自动恢复跟随。会话撤销即意图失效，一并清掉。
            self._preset_resume = {'right': False, 'left': False}
            self._reset_vr_anchors(note='会话已撤销：离合锚点清空')
            self.reason = self.left_reason = note

    def status(self) -> dict:
        with self.lock:
            return dict(entry={side: entry.status() if entry else None for side,entry in self.entries.items()},
                        active=self.owner is not None, sent=self.count,
                        hz=20, mask=f"0x{self._mask():04X}",
                        send_stats=self._send_stats(),
                        mode=self.mode,
                        vr_motion_scale=getattr(self, 'vr_motion_scale', 1.0),
                        vr_motion_scale_text=self.VR_SCALE_NAMES[getattr(self, 'vr_motion_scale', 1.0)],
                        b_long_press_s=self.B_LONG_PRESS_S,
                        vr_buttons=VR.buttons(),
                        base=dict(self.base_state),
                        target=f"{UDP_TARGET[0]}:{UDP_TARGET[1]}",
                        reason=self.entries['right'].status()['message'] if self.entries['right'] else self.reason, error=self.error,
                        ik=self.ik_err,
                        vr=self.vr_on, vr_info=self.vr_info,
                        move=self.move_side['right'],
                        move_seq=self.move_seq,
                        move_result=dict(self.move_result),
                        transfer=dict(getattr(self, '_transfer', {})),
                        right=[round(v, 4) for v in self.right],
                        right_target_point=self.right_target_point,
                        right_rpy_deg=list(self.right_rpy_deg),
                        joints=[round(v, 4) for v in self.joints],
                        # 标定修正原值（米/弧度）：浏览器预览解算 TCP 用（2026-10-25）
                        calib={sd: {'t': list(CALIB[sd]['t']), 'yaw': CALIB[sd]['yaw'],
                                    's': CALIB[sd].get('s', 0.0)}
                               for sd in ('right', 'left')},
                        remaining=round(max(0.0, self.deadline - time.monotonic()), 1)
                        if self.owner else 0,
                        left=dict(active=self.owner_left is not None,
                                  joints_deg=[round(math.degrees(v), 2) for v in self.left_joints]
                                  if self.left_joints else None,
                                  target=[round(v, 4) for v in self.left_target],
                                  target_point='j5',
                                  rpy_deg=list(self.left_rpy_deg),
                                  grip=round(self.left_grip, 3),
                                  vr=self.vr_left_on, vr_info=self.vr_left_info,
                                  move=self.move_side['left'],
                                  reason=self.entries['left'].status()['message'] if self.entries['left'] else self.left_reason))

    def _entry_feedback(self, side, entry):
        reader = right_read if side == 'right' else left_read
        t0 = time.monotonic()
        while True:
            with self.lock:
                if self.entries[side] is not entry or SAFETY.stopped:
                    return
                # 定点移动没有页面心跳，由本线程续租。必须在阻塞式 SSH 读取“之前”续，
                # 且租期覆盖一次慢读取，否则读取期间 _tick 会判心跳过期并触发全局停止。
                if self.move_side[side] is not None:
                    until = time.monotonic() + MOVE_LEASE_S
                    if side == 'right':
                        self.until = until
                    else:
                        self.left_until = until
            sampled = time.monotonic()
            ok, values = reader()
            entry_log('sample' if ok else 'feedback_error', side, entry,
                      feedback=values if ok else None, note='' if ok else str(values))
            with self.lock:
                if self.entries[side] is not entry or SAFETY.stopped:
                    return
                try:
                    if not ok:
                        raise ValueError(entry.label + '中止：无法读取六轴反馈：' + str(values))
                    entry.observe([math.radians(v) for v in angles(values)], sampled, time.monotonic())
                    # 臂完全没有响应：未使能（0x2A1 状态 0x40）、未上电或不在 CAN 模式时，
                    # deploy 仍会照常启动并接收指令，但关节一动不动。以前要白等 45s 超时，
                    # 再按“动过”处理去锁存——白等又难查。这里 6s 内位移仍小于门限就快速失败。
                    need = max(abs(a - b) for a, b in zip(entry.target, entry.initial))
                    if (need > STALL_NEED and time.monotonic() - t0 > STALL_S
                            and entry.max_deviation < STALL_DEV):
                        entry.stalled = True
                        raise ValueError(entry.label + '中止：机械臂无响应（未使能/未上电/不在 CAN 模式？）')
                    if entry.phase == 'done':
                        self.entries[side] = None
                        moving = self.move_side[side] is not None
                        self.move_side[side] = None
                        if side == 'right':
                            self.joints = entry.target[:]
                            if moving:
                                self.owner = None
                                self.vr_on = False
                                self._reset_vr_anchors('right', note='定点动作完成：锚点清空')
                                self.reason = entry.label + '已完成（已到位并释放）'
                                self._mark_move('right', 'done', self.reason)
                                # 2026-10-24 方案乙：A 键抢占过跟随 → 归位完成后原地恢复 VR 跟随。
                                # 此刻臂刚动过，deploy 必然在跑，无需 SSH 检查；纯内存操作，持锁安全。
                                if self._preset_resume['right']:
                                    self._preset_resume['right'] = False
                                    self.owner = 'vr-button'
                                    self.vr_on = True
                                    self.vr_pressing = False
                                    self.vr_smooth = None
                                    self.right = list(_fk_points(self.joints, 'right')[0][5])
                                    self.right_target_point = 'j5'
                                    self.vr_anchor = tuple(self.right)
                                    self.until = time.monotonic() + HEARTBEAT_S * 3
                                    self.reason = entry.label + '已完成，VR 跟随已恢复（按住侧键继续）'
                            else:
                                self.reason = '起始位姿已到位，跟随中'
                        else:
                            self.left_joints = entry.target[:]
                            if moving:
                                # X 搬运的各段到位只结束运动，不释放夹爪发送权。
                                # 否则位置 3 到位与 releasing 之间存在无 UDP 帧的空窗，
                                # 松爪可能延迟到返回阶段重新建立会话时才真正执行。
                                if not self._vr_route_running:
                                    self.owner_left = None
                                self.vr_left_on = False
                                self._reset_vr_anchors('left', note='定点动作完成：锚点清空')
                                self.left_reason = entry.label + ('已完成（搬运会话保持）'
                                    if self._vr_route_running else '已完成（已到位并释放）')
                                self._mark_move('left', 'done', self.left_reason)
                                # 同右臂方案乙：X 键抢占过跟随 → 归位完成后恢复
                                if self._preset_resume['left']:
                                    self._preset_resume['left'] = False
                                    self.owner_left = 'vr-button'
                                    self.vr_left_on = True
                                    self.vr_left_pressing = False
                                    self.vr_left_smooth = None
                                    self.vr_left_anchor = tuple(self.left_target)
                                    self.left_until = time.monotonic() + HEARTBEAT_S * 3
                                    self.left_reason = entry.label + '已完成，VR 跟随已恢复（按住侧键继续）'
                            else:
                                self.left_reason = '起始位姿已到位，跟随中'
                        entry_log('done', side, entry, feedback=values)
                        return
                except ValueError as exc:
                    entry_log('abort', side, entry, feedback=values if ok else None, note=str(exc))
                    self._abort(side, entry, exc)
                    return
            time.sleep(1.0 / 20)   # 20Hz；原来是 0.15s=6.7Hz，帧间隔超过 deploy 的 100ms 看门狗导致反复冻结


    def _abort(self, side, entry, exc):
        """入口/定点移动中止时的分级处理（调用方必须已持有 self.lock）。

        六轴偏离起始值都小于 NO_MOTION_TOL ⇒ 臂根本没动，属于前置条件失败
        （deploy 未运行、臂未使能、反馈读不到、页面心跳断了）。此时没有需要
        紧急停止的运动对象，只撤销本会话，deploy 留给另一条臂继续用，不锁存。
        真的动过才按原策略 stop_all 锁存全局软件停止。
        """
        self.error = str(exc)
        was_move = self.move_side[side] is not None
        sent = bool(getattr(entry, 'sent_any', False))
        have_fb = bool(getattr(entry, 'have_feedback', False))
        # C02：只有"确实发过目标"且"有有效反馈证明六轴偏离都很小"时，
        # 才能下"臂没动"的结论。发了目标却没有反馈 = 反馈未知，必须锁停。
        # max_deviation 只可能由 observe()（通过校验的反馈）累积，所以它本身
        # 就蕴含有过有效反馈，不必再叠加 have_fb。
        # stalled 是有反馈证明它根本不响应的**已知**状态（未使能/未上电），
        # 不属于未知，因此不锁存。
        evidence_of_motion = entry.max_deviation > NO_MOTION_TOL and not entry.stalled
        feedback_unknown = sent and not have_fb
        if evidence_of_motion or feedback_unknown:
            reason = ('位移超过容差' if evidence_of_motion else '反馈未知，无法确认是否在动')
            note = str(exc) + '（已发出目标且' + reason + '，已锁存软件停止）'
            self.error = note
            if was_move:
                self._mark_move(side, 'failed', note)
            stop_all()
            return
        self.entries[side] = None
        self.move_side[side] = None
        if not sent:
            note = str(exc) + '（尚未发出目标帧，仅撤销本会话；未锁存软件停止）'
        else:
            note = str(exc) + '（反馈显示六轴偏离均小于容差，判定未产生运动；仅撤销本会话）'
        if was_move:
            self._mark_move(side, 'failed', note)
        if side == 'right':
            self.owner = None
            self.vr_on = False
            self.reason = note
        else:
            self.owner_left = None
            self.left_joints = None
            self.vr_left_on = False
            self.left_reason = note

    def _mark_move(self, side, state, message):
        """登记定点移动的终态（调用方已持有 self.lock）。"""
        cur = self.move_result.get(side) or {}
        self.move_result[side] = dict(cur, seq=cur.get('seq', self.move_seq),
                                      state=state, message=message,
                                      finished_at=time.time())

    # C09：跟随期的几何检查频率与阈值
    # 原来取 5 拍（4Hz）是拍的数：4Hz 下每拍末端走 60.6 mm，而警戒壳只有 20 mm，
    # 可能一步跨过 → 漏检。按"每拍位移 < 阈值"反解，临界约 12.1 Hz，所以取每拍（20Hz）。
    # 单次 pose_margin 实测 119.7 µs，20Hz 只占单核 0.2%。
    FOLLOW_GEO_EVERY = 1
    # 跟随期阈值单独放大：实测 stop_all 后还冲出 3.56°（力臂 0.5 m ≈ 30~40 mm），
    # 20 mm 的壳"发现得到但停不下"。50 mm 对正常路径（实测 6.5/6.9 cm）不会误报。
    FOLLOW_MARGIN_CM = 5.0

    def _follow_geo_guard(self, side, tick_no):
        """C09：入口通过 ≠ 全程安全。

        入口预检只覆盖"进入时的那条分段路径"；之后手柄会把人带到任何地方。
        这里按固定节拍对**当前目标姿态**重查支架余量，不足就抛 ValueError。
        单点检查是微秒级，4Hz 对 20Hz 发送没有影响。
        """
        if tick_no % self.FOLLOW_GEO_EVERY != 0:
            return
        q = self.joints if side == 'right' else self.left_joints
        if q is None:
            return
        # pose_margin 返回 (margin, 中心线距离, 连杆名, 杆名)，不是单个浮点数。
        # 之前直接和浮点比大小 -> TypeError '<' not supported -> 每拍都抛。
        # pose_margin 返回 (margin, 中心线距离, 连杆名, 杆名)
        margin, _dist, link, rod = arm_geometry.pose_margin(list(q), side)
        limit = max(arm_geometry.MIN_MARGIN_CM, self.FOLLOW_MARGIN_CM)
        # 2026-10-23 降级：只记日志，**不再中止**。
        # 原实现 raise ValueError → _abort → stop_all()，即"几何检查一旦误报就锁停整个程序"。
        # 而阈值用的是未实测模型（线上 ROD_R_CM=2.0 vs 分析用 1.513），误报风险不可忽略。
        # 入口预检（_geo_check）保持不变 —— 那是原来就有的、经过验证的那道。
        if margin < limit:
            self.geo_warn = ('跟随中 %s 与 %s 余量 %.1f cm < %.1f cm（仅告警，未中止）'
                             % (link, rod, margin, limit))

    def _geo_check(self, side, current, target, j1_order=None):
        """支架几何预检：把将要下发的**相位顺序路径**抽样，算与支架的最小余量。

        这是目前唯一能自动拦住"把臂送进支架"的检查。参数（杆半径、最小余量）
        集中在 arm_geometry 顶部，实测后改那里；失败时返回可直接展示的原因。
        """
        try:
            r = arm_geometry.check_entry(list(current), list(target), side, j1_order=j1_order)
        except Exception as exc:                     # noqa: BLE001
            return {'ok': False, 'message': '几何预检异常（%s），已拒绝' % type(exc).__name__}
        if r.get('ok'):
            r['message'] = '几何预检通过：最小余量 %.1f cm' % r['margin_cm']
            return r
        r['message'] = ('支架几何预检未通过：最小余量 %.1f cm（要求 ≥%.1f cm），'
                        '最近处 %s × %s' % (r.get('margin_cm') or 0,
                                            arm_geometry.MIN_MARGIN_CM,
                                            r.get('link'), r.get('rod')))
        return r

    def start_planned_test(self, data, trajectory):
        """左臂受控规划执行：复用反馈门控与20Hz会话，仅由精确规划端点调用。"""
        if not self._move_gate.acquire(blocking=False):
            return {'error': '另一路定点动作正在进行'}, 409
        try:
            side = data.get('side', 'left')
            if side not in ('left', 'right'):
                return {'error': '未知机械臂侧'}, 400
            client = 'vla-exact-test'
            other = 'right' if side == 'left' else 'left'
            if self.mode != 'arms':
                return {'error': '当前不是双臂模式'}, 409
            with self.lock:
                try:
                    SAFETY.require(data)
                except ValueError as exc:
                    return {'error': str(exc)}, 409
                if (self.owner_left if side == 'left' else self.owner) or self.entries[side] or self.entry_pending[side]:
                    return {'error': ('左臂' if side == 'left' else '右臂')+'已有控制会话或动作'}, 409
                if (self.owner if other == 'right' else self.owner_left) or self.entries[other] or self.entry_pending[other]:
                    return {'error': '精确规划要求另一臂保持固定，请先停止另一臂会话'}, 409
                self.entry_pending[side] = True
                self.entry_generation[side] += 1
                generation = self.entry_generation[side]
            if not deploy_running():
                with self.lock:
                    if generation == self.entry_generation[side]:
                        self.entry_pending[side] = False
                return {'error': 'KR260 deploy 未运行'}, 409
            sampled = time.monotonic()
            ok, values = left_read() if side == 'left' else right_read()
            with self.lock:
                if generation != self.entry_generation[side]:
                    return {'error': '测试已取消'}, 409
                self.entry_pending[side] = False
                try:
                    SAFETY.require(data)
                    if not ok:
                        raise ValueError('无法读取本臂反馈：' + str(values))
                    current = [math.radians(v) for v in angles(values)]
                    if time.monotonic() - sampled > EntrySequence.FRESH:
                        raise ValueError('关节反馈过期')
                    target = trajectory['q'][-1]
                    if any(not lo <= q <= hi for q, lo, hi in zip(target, JOINT_LO, JOINT_HI)):
                        raise ValueError('目标超出关节限位')
                    entry = EntrySequence(current, target, sampled, arrive_tol=MOVE_TOL,
                                          label=('左臂' if side == 'left' else '右臂')+'精确网格受控运动', trajectory=trajectory)
                    entry.started = time.monotonic()
                    entry.check(time.monotonic())
                except (ValueError, KeyError) as exc:
                    return {'error': str(exc)}, 409
                self.entries[side] = entry
                self.move_side[side] = 'vla_exact_test'
                self.move_seq += 1
                self.move_result[side] = {'seq': self.move_seq, 'which': 'vla_exact_test',
                                            'state': 'running', 'message': entry.status()['message'],
                                            'sent_at': time.time()}
                if side == 'left':
                    self.owner_left = client
                    self.left_joints = entry.command
                    self.left_until = time.monotonic() + HEARTBEAT_S * 3
                    self.left_reason = entry.status()['message']
                else:
                    self.owner = client
                    self.right_joints = entry.command
                    self.right_until = time.monotonic() + HEARTBEAT_S * 3
                    self.right_reason = entry.status()['message']
                self._web_active_at[side] = time.monotonic()
                entry_log_start(side, entry)
                threading.Thread(target=self._entry_feedback, args=(side, entry), daemon=True).start()
                return {'ok': True, 'side': side, 'move_seq': self.move_seq,
                        'duration_s': trajectory['duration_s'],
                        'velocity_limit_rad_s': 0.15,
                        'acceleration_limit_rad_s2': 0.4}, 200
        finally:
            self._move_gate.release()

    def _call_move(self, side, data):
        """定点动作串行闸门（C06）。

        左右臂的定点动作必须串行：单臂的支架预检并不能证明两条轨迹互不干涉。
        闸门是非阻塞的 —— 拿不到就明确拒绝，而不是排队（排队会引入"停止后旧任务又跑"）。
        """
        if not self._move_gate.acquire(blocking=False):
            return {'error': '另一路定点动作正在进行：左右臂定点动作必须串行，请等它完成或先停止'}, 409
        try:
            return self._call_move_body(side, data)
        finally:
            self._move_gate.release()

    def _call_move_body(self, side, data):
        """定点移动：读起始反馈 → EntrySequence 分阶段 → 原 UDP mode=2 通道下发。

        起始位姿→零位：先归零 J1（J2–J6 保持）再收拢；
        零位→起始位姿：先展开 J2–J6（此时 J1=0）再偏航 J1。
        与「开始跟随」共用同一套进入门控、软件停止联锁与数据通道。
        """
        # C05：模式准入。底盘模式下禁止任何臂动作（不能只靠按钮禁用）。
        if self.mode != 'arms':
            return {'error': '当前是底盘模式：臂动作被禁用，请先按 B 切回双臂模式'}, 409
        controls = data.get('controls', {})
        which = controls.get('move')
        target = MOVE_TARGETS.get((side, which))
        if target is None:
            return {'error': '无效的移动目标（需 start 或 zero）'}, 400
        client = data.get('client', '')
        label = MOVE_LABELS.get((side, which), '移动到目标')
        with self.lock:
            try:
                SAFETY.require(data)
            except ValueError as exc:
                return {'error': str(exc)}, 409
            owner = self.owner_left if side == 'left' else self.owner
            lease = self.left_until if side == 'left' else self.until
            if owner and owner != client and time.monotonic() < lease:
                return {'error': '另一页面正在控制此臂'}, 409
            if self.entries[side] is not None:
                return {'error': '正在进入跟随或移动中，请先停止'}, 409
            if self.entry_pending[side]:
                return {'error': '正在读取起始反馈，请稍候'}, 409
            self.entry_pending[side] = True
            self.entry_generation[side] += 1
            generation = self.entry_generation[side]
        # 锁外做所有 SSH 类阻塞调用：deploy 状态查询在缓存过期时会走 SSH（最长 20s），
        # 持锁会把 _tick 一起挡住，导致 deploy 100ms 看门狗落到保持。
        # 注意必须用不带缓存的 deploy_running()：5s 缓存会让「deploy 刚停」时仍放行，
        # 启动一个没人执行的运动会话 → 反馈不动 → 中止并锁存全局停止（2026-10-22 实锤）。
        if not deploy_running():
            with self.lock:
                if generation == self.entry_generation[side]:
                    self.entry_pending[side] = False
            return {'error': 'KR260 上 deploy 未运行，请先按 ①②③ 完成启动'}, 409
        # 起始反馈读取不持锁，停止按钮保持可用。
        sampled = time.monotonic()
        ok, values = (left_read if side == 'left' else right_read)()
        trajectory = None
        if ok and which.startswith('toppra_'):
            try:
                current = [math.radians(v) for v in angles(values)]
                # LP／IK 规划必须在锁外：规划期间另一臂的 20 Hz 会话和停止按钮仍须工作。
                trajectory = transfer_trajectory.plan(current, target, which[len('toppra_'):])
                # 精确整车规划可能耗时数分钟，不能拿规划前的过期反馈直接执行。
                # 规划后重新读取；静态反馈偏差≤1.5° 时替换首点并重新做整车检查，
                # 其余已验证路径不变。偏差较大仍拒绝，不自动追踪移动中的机械臂。
                fresh_sampled = time.monotonic()
                fresh_ok, fresh_values = (left_read if side == 'left' else right_read)()
                if not fresh_ok:
                    raise ValueError('规划后无法刷新起始反馈：' + str(fresh_values))
                fresh_current = [math.radians(v) for v in angles(fresh_values)]
                drift = max(abs(a-b) for a, b in zip(fresh_current, trajectory['q'][0]))
                if drift > math.radians(1.5):
                    raise ValueError(f'规划期间起始姿态变化 {math.degrees(drift):.3f}°，拒绝沿用轨迹')
                transfer_trajectory._validate_vehicle([fresh_current], '规划后新鲜反馈')
                trajectory['q'][0] = fresh_current
                sampled, ok, values, current = fresh_sampled, fresh_ok, fresh_values, fresh_current
            except (ValueError, RuntimeError) as exc:
                with self.lock:
                    if generation == self.entry_generation[side]:
                        self.entry_pending[side] = False
                return {'error': 'TOPP-RA 规划失败，未发送运动指令：' + str(exc)}, 409
        with self.lock:
            if generation != self.entry_generation[side]:
                return {'error': '移动已被取消'}, 409
            self.entry_pending[side] = False
            try:
                SAFETY.require(data)
                if not ok:
                    raise ValueError('无法读取起始六轴反馈：' + str(values))
                current = [math.radians(v) for v in angles(values)]
                if time.monotonic() - sampled > EntrySequence.FRESH:
                    raise ValueError('起始反馈过期，请重新读取')
                if any(not lo <= q <= hi for q, lo, hi in zip(target, JOINT_LO, JOINT_HI)):
                    raise ValueError('移动目标超出关节限位')
                # 双臂 start/zero 均用 J1/J4 分阶段；VR 入口仍用半展开三段式。
                j1_order = (('first' if which == 'zero' else 'last')
                            if which in ('start', 'zero') else None)
                # TOPP-RA 模块已逐点及逐段检查真实路径；不能再只检查两端点直线。
                geo = ({'ok': True} if trajectory is not None else
                       self._geo_check(side, current, target, j1_order=j1_order))
                if not geo['ok']:
                    raise ValueError(geo['message'])
                entry = EntrySequence(current, target, sampled,
                                      arrive_tol=MOVE_TOL, label=label, j1_order=j1_order,
                                      trajectory=trajectory)
                # 规划耗时不是运动时间：轨迹从零时刻开始，首帧必须是实测起点而非中间点。
                if trajectory is not None:
                    entry.started = time.monotonic()
                entry.check(time.monotonic())
            except ValueError as exc:
                return {'error': str(exc)}, 409
            self.entries[side] = entry
            self.move_side[side] = which
            self.move_seq += 1
            self.move_result[side] = {'seq': self.move_seq, 'which': which,
                                      'state': 'running',
                                      'message': entry.status()['message'],
                                      'sent_at': time.time()}
            if side == 'right':
                self.owner = client
                self.deadline = time.monotonic() + ROUND_S
                self.joints = entry.command
                self.until = time.monotonic() + HEARTBEAT_S * 3
                self.reason = entry.status()['message']
            else:
                self.owner_left = client
                self.left_joints = entry.command
                self.left_until = time.monotonic() + HEARTBEAT_S * 3
                self.left_reason = entry.status()['message']
            entry_log_start(side, entry)
            threading.Thread(target=self._entry_feedback,
                             args=(side, entry), daemon=True).start()
            payload = self.status()
            payload['move_seq'] = self.move_seq
            return payload, 200

    def call(self, action: str, data: dict) -> tuple[dict, int]:
        controls = data.get('controls', {})
        if not isinstance(controls, dict):
            return {'error':'controls 必须为对象'}, 400
        side = 'left' if controls.get('mode') in ('vr_left','left_ee','left_joints') else 'right'
        client = data.get('client', '')
        if not isinstance(client,str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}',client):
            return {'error':'client required'},400
        if action in ('start', 'update', 'move'):
            # 网页会话活跃打点（空闲自动释放的依据；status 轮询不走这里，不会误刷）
            self._web_active_at[side] = time.monotonic()
        if action == 'move':
            return self._call_move(side, data)
        follow_deferred = False
        with self.lock:
            if action == 'stop':
                # 先让执行端原子冻结本侧平滑目标，再撤销本侧会话；另一臂目标原样保留。
                # 不停止 deploy、不锁存全局停止。保持帧失败会写入 error，不能伪称已保持。
                hold_error = self._send_side_hold(side)
                note = '用户停止：本侧会话已撤销（deploy 保持运行）'
                if hold_error:
                    note += '；' + hold_error
                self._cancel_side_session(side, note)
                return self.status(), 200
            else:
                try:
                    SAFETY.require(data)
                except ValueError as exc:
                    return {'error':str(exc)},409
                owner = self.owner_left if side == 'left' else self.owner
                if owner and owner != client:
                    return {'error':'另一页面正在控制此臂'},409
                if self.entries[side] is not None:
                    # Only refresh the existing owner's lease; freeze all target changes.
                    if action == 'update':
                        if side == 'left': self.left_until = time.monotonic()+HEARTBEAT_S*2
                        else: self.until = time.monotonic()+HEARTBEAT_S
                    return self.status(),200
                if self.entry_pending[side]:
                    return {'error':'正在读取跟随起始反馈，请稍候'},409
                lease = self.left_until if side == 'left' else min(self.until,self.deadline)
                if owner is not None and time.monotonic() < lease:
                    follow_deferred = True
                else:
                    if side == 'left': self.owner_left = None; self.left_joints = None
                    else: self.owner = None
                    if action not in ('start','update'):
                        return {'error':'invalid action'},400
                    if side == 'right' and action != 'start':
                        return self.status(),200
                    self.entry_pending[side] = True
                    self.entry_generation[side] += 1
                    generation = self.entry_generation[side]
        if follow_deferred:
            # P0-B（2026-10-28 真修）：此前上面两条路径在**锁内**调 _call_follow，
            # 而它第一句 deploy_running() 缓存过期会走 SSH（最长 20s）——外层 RLock
            # 可重入但不会自动释放，网页 200ms update 反复触发时发送循环被 SSH 顶住，
            # deploy 100ms 看门狗冻结 → “操作一下就保持”。现在锁内只做决定，
            # 锁外再进 _call_follow（其内部会重新拿锁复核属主/租约，语义不变）。
            return self._call_follow(action, data)
        # Never hold the sender lock across initial feedback I/O: stop stays responsive.
        sampled = time.monotonic()
        ok, values = (left_read if side == 'left' else right_read)()
        with self.lock:
            if generation != self.entry_generation[side]:
                return {'error':'启动已被取消'},409
            self.entry_pending[side] = False
            try:
                SAFETY.require(data)
                if not ok: raise ValueError('无法读取起始六轴反馈：'+str(values))
                current = [math.radians(v) for v in angles(values)]
                if time.monotonic()-sampled > EntrySequence.FRESH:
                    raise ValueError('起始反馈过期，请重新读取')
            except ValueError as exc:
                return {'error':str(exc)},409
            result, code = self._call_follow(action,data)
            if code != 200:
                if side == 'right': self.owner = None
                else: self.owner_left = None; self.left_joints = None
                return result,code
            target = self.left_joints if side == 'left' else self.joints
            if self.ik_err and side == 'right':
                self.owner = None
                return {'error':'起始目标 IK 未收敛'},409
            try:
                target = angles(target)
                if any(not lo <= q <= hi for q,lo,hi in zip(target,JOINT_LO,JOINT_HI)):
                    raise ValueError('起始目标关节超限')
                geo = self._geo_check(side, current, target)
                if not geo['ok']:
                    raise ValueError(geo['message'])
                entry = EntrySequence(current,target,sampled)
                entry.check(time.monotonic())
            except ValueError as exc:
                if side == 'right': self.owner = None; self.vr_on = False
                else: self.owner_left = None; self.left_joints = None; self.vr_left_on = False
                return {'error':str(exc)},409
            self.entries[side] = entry
            self.move_side[side] = None   # 跟随进入不走定点移动分支
            if side == 'right': self.joints = entry.command
            else: self.left_joints = entry.command
            entry_log_start(side, entry)
            threading.Thread(target=self._entry_feedback,args=(side,entry),daemon=True).start()
            return self.status(),200

    # ==================== AI / 语音命令层（2026-10-23）====================
    INTENT_MAX_DELTA_M = 0.05          # 单次相对移动上限 5 cm
    INTENT_MAX_JOINT_STEP = math.radians(45.0)   # 单次关节变更上限 45°
    # 底盘意图限值（2026-10-25 收敛为单一数据源：校验与 intent_schema 的
    # limits_machine 都取这里——调用方启动时 GET /api/intent 读机读限值，不要硬编码）
    INTENT_BASE_MAX_VX = 0.3           # m/s
    INTENT_BASE_MAX_VY = 0.3           # m/s
    INTENT_BASE_MAX_WZ = 0.5           # rad/s
    INTENT_BASE_MAX_DUR = 2.0          # s

    @staticmethod
    def intent_schema():
        """GET /api/intent 的自描述，模型可先读这个再决定怎么调。"""
        return {
            'ok': True,
            # 契约版本（2026-10-29）：日期式版本号。演进纪律=只增不删不改——
            # 新增 intent/字段直接出现；既有字段语义永不变更；必须变更时先加新版
            # 字段并保留旧版一个过渡期。调用方启动时核对 api_version 即可。
            'api_version': '2026-10-29',
            'base_contract': {'version': 'serialized-base-20261025-1',
                              'units': {'vx': 'm/s', 'vy': 'm/s', 'wz': 'rad/s'},
                              'rc_combined_twist': True,
                              'optional_drive_precondition': 'base_generation',
                              'stop_scope': 'base_only',
                              'stop_cancels_timed_drive': True},
            'usage': 'POST /api/intent，body 必须带 safety_epoch（从 GET /api/safety 取）',
            'units': '位置一律 cm，关节角一律度，夹爪 open ∈ [0,1]（1=全开）',
            'frame': '位置相对该臂底座的运动学原点；+X 右 / +Y 前 / +Z 上',
            # 全部枚举值机读化：调用方不要硬编码模式名/子模式名/intent 名清单
            'enums': {'mode': ['arms', 'base'],
                      'base_sub': ['a', 'b'],
                      'side': ['right', 'left'],
                      'which': ['start', 'zero']},
            'error_semantics': {'400': '参数/取值非法（修正后重试）',
                                '409': '状态冲突：软件停止锁存 / epoch 过期 / 控制权被占用',
                                '202': '已受理（动作异步执行，需读遥测确认实际结果）'},
            'limits': {'单次相对移动': '≤ 5 cm（超出直接拒绝）',
                       '单次关节变更': '≤ 45°',
                       '其余': '硬限位、几何预检、双臂串行闸门、软件停止联锁全部照常生效'},
            # 机读限值（2026-10-25）：与强制校验同一数据源。客户端启动时读这里，
            # 不要把数字硬编码进自己代码——限值调整后这里会跟着变。
            'limits_machine': {
                'ee_delta_max_cm': ControlSender.INTENT_MAX_DELTA_M * 100.0,
                'joint_step_max_deg': round(math.degrees(ControlSender.INTENT_MAX_JOINT_STEP), 3),
                'base_max_vx_mps': ControlSender.INTENT_BASE_MAX_VX,
                'base_max_vy_mps': ControlSender.INTENT_BASE_MAX_VY,
                'base_max_wz_rads': ControlSender.INTENT_BASE_MAX_WZ,
                'base_max_duration_s': ControlSender.INTENT_BASE_MAX_DUR,
            },
            'intents': [
                {'intent': 'preset', 'params': {'side': 'right|left', 'which': 'start|zero'},
                 '说明': '回到跟随起始位姿或零位（等同网页「移动到起始/零位」）'},
                {'intent': 'ee_delta', 'params': {'side': 'right|left', 'd': '[dx,dy,dz] cm'},
                 '说明': '在当前末端位置基础上相对移动，单次 ≤5 cm'},
                {'intent': 'ee_abs', 'params': {'side': 'right|left', 'p': '[x,y,z] cm'},
                 '说明': '末端移动到绝对位置（臂底座系）'},
                {'intent': 'two_point_abs',
                 'params': {'side': 'right|left', 'p1': 'J7 [x,y,z] cm',
                            'p2': 'J5 [x,y,z] cm', 'theta': '翻滚角，度'},
                 '说明': 'J5/J7 两点+翻滚角定点运动；仅完整姿态 IK 收敛才接受，J5—J7 距离 15.25±2.5cm'},
                {'intent': 'tcp_dir_abs',
                 'params': {'side': 'right|left', 'p1': 'J7 [x,y,z] cm',
                            'direction': 'J5→J7 方向 [dx,dy,dz]', 'theta': '翻滚角，度'},
                 '说明': 'J7+朝向+翻滚角定点运动；方向自动归一化并反算 J5，仅完整姿态 IK 收敛才接受'},
                {'intent': 'joints_abs', 'params': {'side': 'right|left', 'deg': '[6 个角度]'},
                 '说明': '六轴绝对角度（度）；单轴变更 ≤45°'},
                {'intent': 'gripper', 'params': {'side': 'right|left', 'open': '0..1'},
                 '说明': '夹爪开口；需要已有动作会话在续租，否则拒绝'},
                {'intent': 'left_transfer',
                 'params': {'side': 'left', 'resume_vr': 'boolean，可选，默认 false'},
                 '说明': '固定安全轨迹：记录左臂原位和夹持→起始位→位置3→松爪5秒→起始位→返回原位并恢复夹持；'
                         '202 仅表示受理，轮询 GET /api/transfer/status 直到 done/failed/cancelled'},
                {'intent': 'base_drive', 'params': {'vx': 'm/s ±0.3', 'vy': 'm/s ±0.3',
                                                    'wz': 'rad/s ±0.5', 'duration_s': '(0,2.0]', 'rc': 'boolean, default false'},
                 '说明': '底盘定时速度指令（车体系：+vx 前 / +vy 左 / +wz 逆时针）；到点自动停车断使能；'
                         'rc=false 平移与转向互斥；rc=true 走 4T4D 同时前进转向，vy 必须为 0；KR260 侧 200ms 看门狗兜底'},
                {'intent': 'base_stop', 'params': {},
                 '说明': '底盘专用停止：作废进行中的 base_drive 定时指令并立即零速断使能；'
                         '不触碰双臂、不锁存全局停止、无需 safety_epoch，任何状态下可调用'},
                {'intent': 'stop', 'params': {},
                 '说明': '等价于「停止全部运动」：撤会话 + 锁存软件停止（影响双臂和底盘）'},
            ],
            'examples': [
                {'intent': 'ee_delta', 'side': 'right', 'd': [0, 0, -3], 'safety_epoch': '<epoch>',
                 '含义': '右臂末端下降 3 cm'},
                {'intent': 'preset', 'side': 'right', 'which': 'zero', 'safety_epoch': '<epoch>'},
                {'intent': 'gripper', 'side': 'right', 'open': 0.0, 'safety_epoch': '<epoch>',
                 '含义': '右夹爪闭合'},
                {'intent': 'base_drive', 'vx': 0.2, 'duration_s': 1.0, 'safety_epoch': '<epoch>',
                 '含义': '底盘以 0.2 m/s 前进 1 秒'},
            ],
        }

    def intent(self, data):
        """把"意图"翻译成已有的受控路径。返回 (body, http_code)。"""
        if not isinstance(data, dict):
            return {'ok': False, 'error': 'body 必须是 JSON 对象'}, 400
        name = str(data.get('intent', '')).strip()
        side = data.get('side', 'right')
        if side not in ('right', 'left'):
            return {'ok': False, 'error': 'side 必须是 right 或 left'}, 400

        if name == 'stop':
            return {'ok': True, 'intent': name, 'result': stop_all()}, 202

        if name == 'base_stop':
            """底盘专用停止（2026-10-25，P0-A）：作废进行中的 base_drive 定时指令
            （代次令牌 +1 使旧线程退出循环），立即发零速断使能。
            不触碰双臂、不锁存全局软件停止——停止指令任何状态下都必须可执行，
            故不做 SAFETY.require / epoch 校验（与全局 stop 同一原则）。"""
            with self.lock:
                self._base_gen = getattr(self, '_base_gen', 0) + 1
                stopped_gen = self._base_gen
                mode = self.mode
                # Admission, generation check and the actual datagram share this
                # lock. A cancelled worker can never send after this zero packet.
                sent = self._send_base_udp(0.0, 0.0, 0.0, False)
                self._base_intent = dict(generation=self._base_gen, active=False,
                                        state='stop_submitted' if sent else 'stop_send_failed')
                self.base_state.update(vx=0.0, vy=0.0, wz=0.0, active=False,
                                       reason='base_stop：底盘专用停止')
            note = '已作废进行中的底盘定时指令并零速断使能（双臂不受影响）'
            if mode == 'base':
                note += '；注意当前为 VR 底盘模式，摇杆下一拍会继续占用底盘'
            return {'ok': sent, 'intent': name, 'note': note,
                    'generation': stopped_gen, 'actual_stop_confirmed': False}, 202 if sent else 503

        if name == 'base_drive':
            """底盘定时速度指令（感知/大模型语义入口，不依赖 VR 模式）。
            vx/vy m/s、wz rad/s；duration_s ≤ 2.0，到点自动零速断使能；
            KR260 侧 200ms 看门狗兜底。限速与网页一致：±0.3 m/s、±0.5 rad/s。
            2026-10-24 审计修正：N1 补 SAFETY.require（epoch+停止联锁）；
            N2 代次令牌：新调用抢占旧线程；N3 与 VR 底盘摇杆模式互斥。"""
            SAFETY.require(data)          # ValueError → 409（停止锁存 / epoch 过期）
            rc = data.get('rc', False)
            if type(rc) is not bool:
                return {'ok': False, 'error': 'rc 必须为 JSON 布尔值'}, 400
            try:
                if any(isinstance(data.get(k, 0), bool) for k in ('vx','vy','wz','duration_s')):
                    raise ValueError('Boolean speed/duration')
                vx = float(data.get('vx', 0.0))
                vy = float(data.get('vy', 0.0))
                wz = float(data.get('wz', 0.0))
                dur = float(data.get('duration_s', 0.5))
                if not all(math.isfinite(x) for x in (vx,vy,wz,dur)):
                    raise ValueError('Nonfinite speed/duration')
            except (TypeError, ValueError):
                return {'ok': False, 'error': 'vx/vy/wz/duration_s 必须是数值'}, 400
            if max(abs(vx), abs(vy)) > self.INTENT_BASE_MAX_VX + 1e-9:
                return {'ok': False, 'error': '线速度超过 ±%.2f m/s 限制' % self.INTENT_BASE_MAX_VX}, 400
            if rc and abs(vy)>1e-9:
                return {'ok': False, 'error': 'RC 模式不支持横移，vy 必须为 0'}, 400
            if abs(wz) > self.INTENT_BASE_MAX_WZ + 1e-9:
                return {'ok': False, 'error': '角速度超过 ±%.2f rad/s 限制' % self.INTENT_BASE_MAX_WZ}, 400
            if not (0.0 < dur <= self.INTENT_BASE_MAX_DUR):
                return {'ok': False, 'error': 'duration_s 必须在 (0, %.1f] 秒' % self.INTENT_BASE_MAX_DUR}, 400

            with self.lock:
                SAFETY.require(data)
                if self.mode == 'base':
                    return {'ok': False,
                            'error': '当前为 VR 底盘模式（摇杆占用底盘），请先按 B 切回双臂模式'}, 409
                previous = getattr(self, '_base_gen', 0)
                expected = data.get('base_generation', previous)
                if type(expected) is not int or expected != previous:
                    return {'ok': False, 'error': '底盘代次已变化；禁止重试旧运动请求'}, 409
                self._base_gen = previous + 1
                gen = self._base_gen
                epoch = data.get('safety_epoch')
                end = time.monotonic() + dur  # Include scheduling delay in the deadline.
                self._base_intent = dict(generation=gen, active=True, state='accepted',
                                        deadline_monotonic=end)

            def _run():
                try:
                    while True:
                        with self.lock, SAFETY.lock:
                            if (self._base_gen != gen or self.mode == 'base' or
                                SAFETY.stopped or SAFETY.epoch != epoch or time.monotonic() >= end):
                                break
                            if not self._send_base_udp(vx, vy, wz, True, rc=rc):
                                self._base_intent['state'] = 'drive_send_failed'
                                break
                        time.sleep(min(.05, max(0, end-time.monotonic())))
                finally:
                    with self.lock:
                        # A superseded worker must not stop its replacement (or VR).
                        if self._base_gen == gen and self.mode != 'base':
                            sent = self._send_base_udp(0.0, 0.0, 0.0, False)
                            self._base_intent.update(active=False,
                                state='window_ended' if sent else 'stop_send_failed')

            threading.Thread(target=_run, daemon=True).start()
            return {'ok': True, 'intent': name,
                    'generation': gen,
                    'cmd': {'vx': vx, 'vy': vy, 'wz': wz, 'duration_s': dur, **({'rc': rc} if 'rc' in data else {})},
                    'note': ('RC 同时前进转向' if rc else '平移与转向互斥（平移优先）')+'；新 base_drive 会抢占未完成的旧指令'}, 202

        if name == 'left_transfer':
            # 已验证的固定轨迹只作为整体能力开放；VLA 不可注入路径点或提高速度。
            if side != 'left':
                return {'ok': False, 'error': 'left_transfer 仅支持 side=left'}, 400
            resume_vr = data.get('resume_vr', False)
            if type(resume_vr) is not bool:
                return {'ok': False, 'error': 'resume_vr 必须为 JSON 布尔值'}, 400
            SAFETY.require(data)
            with self.lock:
                if self.mode != 'arms':
                    return {'ok': False, 'error': '底盘模式下不能启动左臂搬运'}, 409
                if self._vr_route_running:
                    return {'ok': False, 'error': '左臂搬运流程正在运行'}, 409
            task_id = self._request_preset('left', source='vla', resume_vr=resume_vr)
            if task_id is None:
                return {'ok': False, 'error': '左臂搬运流程未能受理'}, 409
            return {'ok': True, 'intent': name, 'side': 'left', 'task_id': task_id,
                    'state': 'accepted', 'status_url': '/api/transfer/status',
                    'note': '202 仅表示已受理；轮询状态直到 done/failed/cancelled'}, 202

        if name == 'preset':
            which = str(data.get('which', '')).strip()
            if which not in ('start', 'zero'):
                return {'ok': False, 'error': "which 必须是 start 或 zero"}, 400
            payload = {'client': str(data.get('client') or 'ai-intent-preset'),
                       'safety_epoch': data.get('safety_epoch'),
                       'controls': {'mode': 'left_joints' if side == 'left' else 'right_joints',
                                    'move': which}}
            body, code = self._call_move(side, payload)
            return ({'ok': code == 200, 'intent': name, 'side': side, 'which': which,
                     'result': body} if code != 200 else
                    {'ok': True, 'intent': name, 'side': side, 'which': which,
                     'result': body}), code

        if name == 'joints_abs':
            deg = data.get('deg')
            try:
                vals = [float(v) for v in deg]
            except (TypeError, ValueError):
                return {'ok': False, 'error': 'deg 必须是 6 个数值（度）'}, 400
            if len(vals) != 6:
                return {'ok': False, 'error': 'deg 必须是 6 个数值（度）'}, 400
            cur = self._intent_current_joints(side)
            if cur is None:
                return {'ok': False, 'error': '读不到 %s 臂当前角度，先确认使能与 CAN' % side}, 409
            if max(abs(math.radians(vals[i]) - cur[i]) for i in range(6)) > self.INTENT_MAX_JOINT_STEP:
                return {'ok': False, 'error': '单次关节变更超过 45°，请分几步'}, 400
            return self._intent_send_joints(side, vals, data, name)

        if name in ('ee_abs', 'ee_delta'):
            key = 'p' if name == 'ee_abs' else 'd'
            raw = data.get(key)
            try:
                vec = [float(v) for v in raw]
            except (TypeError, ValueError):
                return {'ok': False, 'error': '%s 必须是 3 个数值（cm）' % key}, 400
            if len(vec) != 3:
                return {'ok': False, 'error': '%s 必须是 3 个数值（cm）' % key}, 400
            if name == 'ee_delta':
                if max(abs(v) for v in vec) > self.INTENT_MAX_DELTA_M * 100.0 + 1e-9:
                    return {'ok': False,
                            'error': '单次相对移动超过 %.0f cm，请分几步' % (self.INTENT_MAX_DELTA_M * 100)}, 400
            cur = self._intent_current_joints(side)
            if cur is None:
                return {'ok': False, 'error': '读不到 %s 臂当前角度' % side}, 409
            cur_f, cur_R = _fk(list(cur))
            here = _calib_tcp_from_fk(_mv(_FR, cur_f), cur_R, side)  # 当前测量点（修正后，m）
            tgt = (here[0] + vec[0] / 100.0,
                   here[1] + vec[1] / 100.0,
                   here[2] + vec[2] / 100.0) if name == 'ee_delta' else \
                  (vec[0] / 100.0, vec[1] / 100.0, vec[2] / 100.0)
            if not (TARGET_LO[0] <= tgt[0] <= TARGET_HI[0]
                    and TARGET_LO[1] <= tgt[1] <= TARGET_HI[1]
                    and TARGET_LO[2] <= tgt[2] <= TARGET_HI[2]):
                return {'ok': False,
                        'error': '目标超出可达框 %s..%s cm，请换个方向或分步'
                                 % (tuple(round(v * 100) for v in TARGET_LO),
                                    tuple(round(v * 100) for v in TARGET_HI))}, 400
            # 2026-10-25：多种子+降级解算内含 QLEVEL 种子，原二次调用已取消；
            # 降级成功（err 为降级说明）照常下发并如实告知调用方
            q, err = solve_ik_user(list(tgt), list(cur), side=side)
            if q is None:
                return {'ok': False, 'error': 'IK 无解（%s），目标未接受' % err,
                        'from_cm': [round(v * 100, 1) for v in here],
                        'to_cm': [round(v * 100, 1) for v in tgt]}, 409
            extra = {'from_cm': [round(v * 100, 1) for v in here],
                     'to_cm': [round(v * 100, 1) for v in tgt]}
            if err:
                extra['note'] = err        # 降级级别说明（位置+朝向 / 仅位置）
            return self._intent_send_joints(side, [math.degrees(v) for v in q], data, name,
                                            extra=extra)

        if name in ('two_point_abs', 'tcp_dir_abs'):
            # VLA 位姿定点运动：外部统一 cm/deg，内部解算 m/rad。
            # 两种输入共用同一完整姿态构造；只接受完整位姿解，不下发降级结果。
            try:
                raw1 = data.get('p1')
                raw2 = data.get('p2') if name == 'two_point_abs' else data.get('direction')
                if any(isinstance(v, bool) for v in list(raw1) + list(raw2) + [data.get('theta')]):
                    raise ValueError('boolean coordinate')
                p1 = [float(v) for v in raw1]
                p2 = [float(v) for v in raw2]
                theta = float(data.get('theta'))
                if (len(p1) != 3 or len(p2) != 3
                        or not all(math.isfinite(v) for v in p1 + p2 + [theta])):
                    raise ValueError('nonfinite coordinate')
            except (TypeError, ValueError):
                second = 'p2' if name == 'two_point_abs' else 'direction'
                return {'ok': False,
                        'error': 'p1/%s 必须是有限三维数值，theta 必须是有限角度（度）' % second}, 400
            if not all(TARGET_LO[i] <= p1[i] / 100.0 <= TARGET_HI[i] for i in range(3)):
                return {'ok': False,
                        'error': 'P1 超出可达框 %s..%s cm'
                                 % (tuple(round(v * 100) for v in TARGET_LO),
                                    tuple(round(v * 100) for v in TARGET_HI))}, 400
            direction = None
            if name == 'tcp_dir_abs':
                norm = math.sqrt(sum(v * v for v in p2))
                if norm < 1e-9:
                    return {'ok': False, 'error': 'direction 不能是零向量'}, 400
                direction = [v / norm for v in p2]
                # direction 表示 J5→J7；已知 P1 和固定工具长度，反算 J5（cm）。
                p2 = [p1[i] - TWO_POINT_J5_TCP * 100.0 * direction[i] for i in range(3)]
            cur = self._intent_current_joints(side)
            if cur is None:
                return {'ok': False, 'error': '读不到 %s 臂当前角度，先确认使能与 CAN' % side}, 409
            p1_m = [v / 100.0 for v in p1]
            p2_m = [v / 100.0 for v in p2]
            try:
                q, err = solve_two_point_user(p1_m, p2_m, math.radians(theta), cur, side=side)
            except ValueError as exc:
                return {'ok': False, 'error': '目标几何不合法：%s' % exc}, 400
            if q is None:
                return {'ok': False, 'error': '目标 IK 无解（%s），目标未接受' % err,
                        'p1_cm': p1, 'p2_cm': p2, 'theta_deg': theta}, 409
            if err is not None:
                return {'ok': False,
                        'error': '完整位姿不可达（%s）；位姿接口不下发降级解' % err,
                        'p1_cm': p1, 'p2_cm': p2, 'theta_deg': theta}, 409
            extra = {'p1_cm': p1, 'p2_cm': p2, 'theta_deg': theta,
                     'j5_j7_cm': TWO_POINT_J5_TCP * 100.0,
                     'note': '位置+完整姿态收敛'}
            if direction is not None:
                extra['direction'] = direction
            return self._intent_send_joints(side, [math.degrees(v) for v in q], data, name,
                                            extra=extra)

        if name == 'gripper':
            try:
                opening = float(data.get('open'))
            except (TypeError, ValueError):
                return {'ok': False, 'error': 'open 必须是 0..1 的数值'}, 400
            if not 0.0 <= opening <= 1.0:
                return {'ok': False, 'error': 'open 超出 [0,1]'}, 400
            # 静止夹取也需要夹爪命令：建立一个仅保持当前关节的短会话，
            # 不伪造零位移动作。1.5 秒后自动释放，夹爪物理状态保持不变。
            current = None
            with self.lock:
                owner = self.owner_left if side == 'left' else self.owner
                if owner is None:
                    if self.entries[side] or self.entry_pending[side]:
                        return {'ok': False, 'error': '上一动作尚未完全结束，请稍后重试'}, 409
                    current = self._intent_current_joints(side)
                    if current is None:
                        return {'ok': False, 'error': '读不到当前关节反馈，拒绝静止夹爪控制'}, 409
            with self.lock:
                owner = self.owner_left if side == 'left' else self.owner
                if owner is None:
                    if current is None:
                        return {'ok': False, 'error': '静止夹爪会话未建立'}, 409
                    if side == 'left':
                        self.owner_left = 'stationary-gripper'
                        self.left_joints = None  # 仅左夹爪使能，关节由 deploy 原地保持
                        self.left_until = time.monotonic() + 1.5
                        self.left_reason = '静止夹爪保持（1.5 秒）'
                    else:
                        self.owner = 'stationary-gripper'
                        self.right_joints = current
                        self.right_until = time.monotonic() + 1.5
                        self.reason = '静止夹爪保持（1.5 秒）'
                    self._web_active_at[side] = time.monotonic()
                if side == 'left':
                    self.left_grip = 1.0 - opening
                else:
                    self.grip = 1.0 - opening
            return {'ok': True, 'intent': name, 'side': side, 'open': opening}, 200

        return {'ok': False,
                'error': "未知 intent：%s（GET /api/intent 查可用意图）" % (name or '(空)')}, 400

    @staticmethod
    def _intent_current_joints(side):
        ok, vals = (left_read if side == 'left' else right_read)()
        if not ok:
            return None
        try:
            return [math.radians(v) for v in angles(vals)]
        except Exception:                     # noqa: BLE001
            return None

    def _intent_send_joints(self, side, deg, data, name, extra=None):
        """把算好的绝对角度走关节直驱那条受控路径（含硬限位、钳制、进入序列、串行闸门）。"""
        # 2026-10-25 修：意图层会话必须打点活跃——_call_follow 绕过了 /api/control 的
        # 打点（2074 行），网页空闲 60s 自动释放会在创建后的第一拍就撤销 API 会话，
        # 实测表现为 ee_abs 返回 ok 但臂纹丝不动（sent=0、owner 同拍被清）。
        # 打点后续约语义与网页一致：60s 内没有新的意图调用即自动让位。
        self._web_active_at[side] = time.monotonic()
        payload = {'client': str(data.get('client') or ('ai-intent-%s' % side)),
                   'safety_epoch': data.get('safety_epoch'),
                   'controls': {'mode': 'left_joints' if side == 'left' else 'right_joints',
                                '_keep_target': True,  # VLA 绝对目标不是网页“开始跟随回起始位”
                                ('left_joints_deg' if side == 'left' else 'right_joints_deg'):
                                    [round(v, 3) for v in deg]}}
        body, code = self._call_follow('start', payload)
        out = {'ok': code == 200, 'intent': name, 'side': side,
               'deg': [round(v, 2) for v in deg], 'result': body}
        if extra:
            out.update(extra)
        if code != 200:
            out['error'] = (body or {}).get('error', '动作未被接受')
        return out, code

    def _call_follow(self, action: str, data: dict) -> tuple[dict, int]:
        client = data.get("client", "")
        if not isinstance(data.get('controls', {}), dict):
            return {'error': 'controls 必须为对象'}, 400
        if not isinstance(client, str) or not re.fullmatch(r"[a-zA-Z0-9-]{8,80}", client):
            return {"error": "client required"}, 400
        # C19：deploy_running() 在缓存过期时会走 SSH（最长 20s）。它必须放在**锁外**——
        # 共享锁同时被 _tick（20Hz 发送）和状态请求使用，锁内 SSH 会把发帧拖到
        # deploy 的 100ms 看门狗之外，表现就是"操作一下机械臂就掉到保持"。
        # 2026-10-28（P0-B）：准入预查——只有**接管属主/启动**才需要 deploy 状态，
        # 在拿锁之前按廉价条件决定是否查询；属主已在的 200ms 网页 update 不再触发 SSH。
        # 锁内的准入分支只读预算好的结果，绝不在锁内发起 SSH。
        left_mode = data.get('controls', {}).get('mode') in ('vr_left', 'left_ee', 'left_joints')
        need_deploy = (action == 'start'
                       or (left_mode and action != 'stop' and self.owner_left is None))
        deploy_up = deploy_running() if need_deploy else None
        with self.lock:
            if data.get('action') != 'stop':
                try:
                    SAFETY.require(data)
                except ValueError as e:
                    return {'error': str(e)}, 409
            if self.owner and time.monotonic() >= self.until:
                self.owner = None
            if self.owner_left and time.monotonic() >= self.left_until:
                self.owner_left = None
                self.left_joints = None
            controls = data.get("controls", {})
            # 新跟随会话会走统一起始位入口，必须立即撤销同侧旧定点标记；
            # 否则入口完成后会被误判为“定点移动完成”而释放会话，或下一次更新重回起始位。
            if action == 'start' and not controls.get('_keep_target'):
                if left_mode:
                    self.move_side['left'] = None
                elif controls.get('mode') in ('vr', 'right_joints', 'right_ee'):
                    self.move_side['right'] = None
            # ===== 左臂 VR 跟随（左手柄，镜像右臂 VR 方案，可与右臂同时进行）=====
            if controls.get("mode") == "vr_left":
                if action == "stop":
                    self.owner_left = None
                    self.left_joints = None
                    self.vr_left_on = False
                    self.left_reason = "用户停止"
                    return self.status(), 200
                if self.owner_left and self.owner_left != client:
                    return {"error": "另一个页面正在控制左臂，请先停止"}, 409
                if self.owner_left is None:
                    if deploy_up is None:
                        return {"error": "会话状态变化，请重试"}, 409
                    if not deploy_up:
                        return {"error": "KR260 上 deploy 未运行，请先启动"}, 409
                # 新 VR 会话与定点归位、普通开始跟随共用同一六轴起始位。
                if self.owner_left is None:
                    self.left_joints = list(Q_START_LEFT)
                    self.left_rpy_deg = [0.0, 0.0, 0.0]
                self.owner_left = client
                self.vr_left_on = True
                self.vr_left_pressing = False
                self.vr_left_smooth = None
                # VR 的 target_cm 从本刻起表示 J5；锚点与当前关节目标严格一致。
                self.left_target = list(_fk_points(self.left_joints, 'left')[0][5])
                self.vr_left_anchor = tuple(self.left_target)
                self.left_until = time.monotonic() + HEARTBEAT_S * 3
                self.left_reason = "左臂 VR 跟随中（按住左手柄侧键移动，松开保持）"
                return self.status(), 200
            # ===== 左臂末端跟随（与右臂同款：底盘系 XYZ → AIPC 端 IK → mode=2 关节直达）=====
            if controls.get("mode") == "left_ee":
                if action == "stop":
                    self.owner_left = None
                    self.left_joints = None
                    self.vr_left_on = False
                    self.left_reason = "用户停止"
                    return self.status(), 200
                if self.owner_left and self.owner_left != client:
                    return {"error": "另一个页面正在控制左臂，请先停止"}, 409
                # 仅接管属主时查一次 deploy（带 5s 缓存）；每拍都直连 SSH 会打爆 KR260
                if self.owner_left is None:
                    if deploy_up is None:
                        return {"error": "会话状态变化，请重试"}, 409
                    if not deploy_up:
                        return {"error": "KR260 上 deploy 未运行，请先启动"}, 409
                # 网页、VR 与关节直驱共享目标统一为 J5，不再切换成 J7/TCP 口径。
                self.vr_left_on = False
                if self.owner_left is None and not controls.get('_keep_target'):
                    self.left_joints = list(Q_START_LEFT)
                    self.left_target = list(_fk_points(Q_START_LEFT, 'left')[0][5])
                    self.left_rpy_deg = [0.0, 0.0, 0.0]
                    self.owner_left = client
                    self.left_until = time.monotonic() + HEARTBEAT_S * 2
                    self.left_reason = '左臂末端跟随中（统一起始位）'
                    return self.status(), 200
                try:
                    tgt = clamp_hand(controls.get("left", list(self.left_target)))
                    rpy_deg = rpy_degrees(controls.get('left_rpy_deg', self.left_rpy_deg),
                                          'left_rpy_deg')
                    self.left_grip = clamp_grip(controls.get("left_grip", self.left_grip))
                except ValueError as e:
                    return {"error": str(e)}, 400
                # 与右臂共用 J5+RPY 的 V3.0 解析入口，种子保持腕部分支连续。
                seed = self.left_joints if self.left_joints else QLEVEL
                q, err = solve_web_j5_rpy_side(list(tgt), rpy_deg, seed, side='left')
                if q is None:
                    self.left_reason = f"IK 未收敛：{err}"
                    return {"error": f"左臂 IK 未收敛（{err}），目标保持不动"}, 409
                self.left_target = list(tgt)
                self.left_rpy_deg = list(rpy_deg)
                self.left_joints = q
                self.owner_left = client
                self.left_until = time.monotonic() + HEARTBEAT_S * 2
                self.left_reason = "左臂末端跟随中" + (f"（{err}）" if err else "")
                return self.status(), 200
            # ===== 左臂关节直达（独立属主，与右臂/VR 互不干扰）=====
            if controls.get("mode") == "left_joints":
                if action == "stop":
                    self.owner_left = None
                    self.left_joints = None
                    self.vr_left_on = False
                    self.left_reason = "用户停止"
                    return self.status(), 200
                if self.owner_left and self.owner_left != client:
                    return {"error": "另一个页面正在控制左臂，请先停止"}, 409
                # 仅接管属主时查一次 deploy（带 5s 缓存）；每拍都直连 SSH 会打爆 KR260
                if self.owner_left is None:
                    if deploy_up is None:
                        return {"error": "会话状态变化，请重试"}, 409
                    if not deploy_up:
                        return {"error": "KR260 上 deploy 未运行，请先启动"}, 409
                self.vr_left_on = False
                if self.owner_left is None and not controls.get('_keep_target'):
                    self.left_joints = list(Q_START_LEFT)
                    self.left_target = list(_fk_points(Q_START_LEFT, 'left')[0][5])
                    self.left_rpy_deg = [0.0, 0.0, 0.0]
                    self.owner_left = client
                    self.left_until = time.monotonic() + HEARTBEAT_S * 2
                    self.left_reason = '左臂关节跟随中（统一起始位）'
                    self._reset_vr_anchors('left', note='统一起始位已建立')
                    return self.status(), 200
                joints_deg = controls.get("left_joints_deg")
                if joints_deg is not None:
                    if (not isinstance(joints_deg, list) or len(joints_deg) != 6
                            or any(type(j) not in (int, float) or not math.isfinite(j)
                                   for j in joints_deg)):
                        return {"error": "left_joints_deg 需为 6 个数值（度）"}, 400
                    rad = [math.radians(j) for j in joints_deg]
                    if any(not (lo <= r <= hi)
                           for r, lo, hi in zip(rad, JOINT_HARD_LO, JOINT_HARD_HI)):
                        return {"error": "左臂关节超出机械硬限位（各轴范围见页面标注）"}, 400
                    rad = [min(hi, max(lo, r)) for r, lo, hi in zip(rad, JOINT_LO, JOINT_HI)]
                    self.left_joints = rad
                    self.left_target = list(_fk_points(rad, 'left')[0][5])
                    self._reset_vr_anchors('left', note='左臂关节直驱后需重新建立锚点')
                try:
                    self.left_grip = clamp_grip(controls.get("left_grip", self.left_grip))
                except ValueError as e:
                    return {"error": str(e)}, 400
                self.owner_left = client
                self.left_until = time.monotonic() + HEARTBEAT_S * 2
                self.left_reason = "左臂关节跟随中"
                return self.status(), 200
            if action == "stop":
                self.owner = None
                self.vr_on = False
                self.reason = "用户停止"
                return self.status(), 200
            if self.owner and self.owner != client:
                return {"error": "另一个页面正在控制，请先停止"}, 409
            controls = data.get("controls", {})
            joint_mode = controls.get('mode') == 'right_joints'
            joint_target = None
            if joint_mode:
                try:
                    joint_target = [math.radians(v) for v in angles(controls.get('right_joints_deg'))]
                    if any(not lo <= q <= hi
                           for q,lo,hi in zip(joint_target, JOINT_HARD_LO, JOINT_HARD_HI)):
                        raise ValueError('右臂关节超出机械硬限位')
                    joint_target = [min(hi, max(lo, q))
                                    for q,lo,hi in zip(joint_target, JOINT_LO, JOINT_HI)]
                except ValueError as exc:
                    return {'error':str(exc)},400
            vr_mode = controls.get("mode") == "vr"
            if action == 'start' and self.vr_on and joint_mode:
                # 只有切到关节/旧 J7 路径才还原共享目标；网页 EE 与 VR 均为 J5。
                fk_r = _fk(self.joints)
                self.right = list(_calib_tcp_from_fk(_mv(_FR, fk_r[0]), fk_r[1], 'right'))
            try:
                right = clamp_hand(controls.get("right", list(self.right)))
                grip = clamp_grip(controls.get("right_grip", self.grip))
            except ValueError as e:
                return {"error": str(e)}, 400
            if action == "start":
                if not deploy_up:
                    return {"error": "KR260 上 deploy 未运行，请先按 ①②③ 完成启动"}, 409
                self.owner = client
                self.deadline = time.monotonic() + ROUND_S
                self.count = 0
                # v2 deploy 按 seq 去重（seq<=last_seen 丢弃）：用时间种子保证
                # 服务重启后 seq 仍大于 KR260 侧已见值，避免开场静默丢帧
                self.seq = int(time.time()) & 0x7FFFFFFF
                self.error = None
                self.vr_on = vr_mode
                self.vr_pressing = False
                if not controls.get('_keep_target'):
                    self.joints = list(Q_START_RIGHT)
                    self.right = list(_fk_points(Q_START_RIGHT, 'right')[0][5])
                    self.right_rpy_deg = [0.0, 0.0, 0.0]
                    self.right_target_point = 'j5'
                    self.ik_err = None
                if vr_mode:
                    # VR 启动沿用当前关节目标，本分支不做 IK；清掉此前网页/VR 更新
                    # 留下的失败状态，避免旧 ik_err 被进入流程误报成“起始目标 IK 未收敛”。
                    self.ik_err = None
                    # VR 的 target_cm 从本刻起表示 J5；锚点与当前关节目标严格一致。
                    self.right = list(_fk_points(self.joints, 'right')[0][5])
                    self.right_target_point = 'j5'
                    self.vr_anchor = tuple(self.right)
                    self.until = time.monotonic() + HEARTBEAT_S * 3
                    self.reason = "VR 跟随中（按住手柄侧键移动，松开保持）"
                    return self.status(), 200
                self.reason = "实机跟随中（v2 · 0xFCFC · mode=2 关节直达 · 底盘系）"
                if not controls.get('_keep_target'):
                    self.until = time.monotonic() + HEARTBEAT_S * 2
                    return self.status(), 200
            elif action != "update":
                return {"error": "invalid action"}, 400
            if self.owner is None:
                return self.status(), 200
            if self.vr_on:
                # VR 模式下网页只保留夹爪/停止，位置由手柄驱动
                self.grip = grip
                return self.status(), 200
            if joint_mode:
                self.joints = joint_target
                self.ik_err = None
                self.right = list(_fk_points(joint_target, 'right')[0][5])
                self.right_target_point = 'j5'
                self._reset_vr_anchors('right', note='关节直驱后需重新建立锚点')
                self.grip = grip
                self.until = time.monotonic()+HEARTBEAT_S
                self.reason = '右臂关节跟随中'
                return self.status(),200
            try:
                rpy_deg = rpy_degrees(controls.get('right_rpy_deg',
                                      getattr(self, 'right_rpy_deg', [0.0, 0.0, 0.0])),
                                      'right_rpy_deg')
            except ValueError as exc:
                return {'error': str(exc)}, 400
            # 与左臂共用 J5+RPY 的 V3.0 解析入口，种子保持腕部分支连续。
            try:
                q, err = solve_web_j5_rpy_side(right, rpy_deg, self.joints, side='right')
            except ValueError as exc:
                return {'error': '右臂目标位姿不合法：%s' % exc}, 400
            if q is None:
                # C18：IK 失败不得更新目标、不得续租，也不得报成功 —— 与左臂分支一致返回 409。
                # 页面显示的"请求点"与"已接受目标"必须分开，避免看起来像接受了一个不可达点。
                self.ik_err = err
                return {'error': '右臂 IK 无解，目标未被接受：%s' % err}, 409
            self.joints = q
            self.ik_err = None      # 成功（含降级）；降级说明放 reason，ik_err 只表示失败
            # 2026-10-23 修：跟随接管会话时必须清掉 move_side。
            # 否则「移动到起始」与「开始跟随」撞在同一个进入序列上时，进入完成会走
            # "定点移动完成"分支把 owner 释放掉 —— 跟随刚显示"已到位"就自己退出。
            self.move_side['right'] = None
            self.right = list(right)
            self.right_target_point = 'j5'
            self.right_rpy_deg = list(rpy_deg)
            self.grip = grip
            self.until = time.monotonic() + HEARTBEAT_S
            if err:
                self.reason = '右臂跟随中（%s）' % err     # 降级说明可见
            return self.status(), 200

    # ==================== VR 侧遥测（2026-10-24，GET /api/vr_telemetry）====================
    def telemetry(self):
        """给 VR APK 的只读状态回报：当前模式、两臂状态/末端位置/夹爪、底盘状态、按键。
        位置 = 反馈关节 FK + 标定修正（底盘系 cm，与尺量坐标一致）；
        反馈读 _FB_CACHE 内存缓存（微秒级），绝不在锁内走 SSH（C19 教训）。"""
        now = time.monotonic()
        with self.lock:
            arms = {}
            for side in ('right', 'left'):
                owner = self.owner if side == 'right' else self.owner_left
                vr = self.vr_on if side == 'right' else self.vr_left_on
                pressing = self.vr_pressing if side == 'right' else self.vr_left_pressing
                joints = self.joints if side == 'right' else self.left_joints
                reason = self.reason if side == 'right' else self.left_reason
                info = (self.vr_info if side == 'right' else self.vr_left_info) or ''
                grip = self.grip if side == 'right' else self.left_grip
                tgt = self.right if side == 'right' else self.left_target
                if self.entries[side] is not None:
                    state = 'moving'          # 进入序列/定点移动中
                elif owner is None:
                    state = 'idle'            # 无控制会话（deploy 看门狗冻结保持）
                elif vr:
                    state = 'vr_follow'       # VR 跟随中（pressing=离合按下）
                else:
                    state = 'manual'          # 网页/AI 会话
                ts, ok, vals = _FB_CACHE[side]
                fb_fresh = ok and (now - ts) < _FB_STALE_S
                q = None
                src = None
                if fb_fresh:
                    q = [math.radians(v) for v in angles(vals)]
                    src = 'feedback'
                elif joints is not None:
                    q = list(joints)
                    src = 'target'
                ee_cm = None
                tcp_cm = None
                j5_cm = None
                link_cm = None
                ee_quat = None
                if q is not None:
                    pts, R_native = _fk_points(q, side)
                    ee_cm = pts[-1]       # 与原 _fk 路径逐字同值（法兰，VR 骨架契约不变）
                    tcp_cm = _calib_tcp_from_fk(_mv(_FR, _fk(q)[0]), R_native, side)
                    j5_cm = [round(v * 100, 1) for v in pts[5]]
                    link_cm = [[round(v * 100, 1) for v in p] for p in pts]
                    ee_quat = [round(v, 4) for v in _mat_to_quat(
                        _mm(_rz(CALIB[side]['yaw']), _mm(_FR, R_native)))]
                arms[side] = {
                    'state': state,
                    'vr_pressing': bool(vr and pressing),
                    'ee_cm': [round(v * 100, 1) for v in ee_cm] if ee_cm else None,
                    'tcp_cm': [round(v * 100, 1) for v in tcp_cm] if tcp_cm else None,
                    'j5_cm': j5_cm,       # 实际/目标关节推算的 J5 中心，供 VR 新 XYZ 语义核对
                    'ee_quat': ee_quat,   # 末端姿态四元数 [x,y,z,w]（臂底座系·用户朝向）
                    'link_cm': link_cm,   # 底座→法兰 7 个关节点（cm），VR 相邻连线即可显示
                    'ee_src': src,            # feedback=真实反馈；target=目标推算（无反馈时）
                    'target_point': (getattr(self, 'right_target_point', 'j5')
                                     if side == 'right' else 'j5'),
                    'target_cm': [round(v * 100, 1) for v in tgt] if tgt else None,
                    'joints_deg': ([round(math.degrees(v), 1) for v in joints]
                                   if joints else None),
                    'fb_deg': ([round(v, 1) for v in vals] if fb_fresh else None),
                    'grip_open': round(1.0 - grip, 2),   # 1=全开 0=闭合
                    'reason': reason or '',
                    'info': info,
                }
            base = dict(self.base_state)
            base['sub'] = self.base_sub
            base['sub_text'] = BASE_SUB_TEXT[self.base_sub]
            if self.mode == 'base':
                mode_text = '底盘模式 · ' + base['sub_text']
            else:
                mode_text = '双臂模式（VR 控臂）'
            scale = getattr(self, 'vr_motion_scale', 1.0)
            return {'ok': True,
                    'mode': self.mode,
                    'mode_text': mode_text,
                    'vr_motion_scale': scale,
                    'vr_motion_scale_text': self.VR_SCALE_NAMES[scale],
                    # 2026-10-31：VR 2.12 对接要求——模式细节结构化回传，
                    # VR 侧不必从多个顶层字段拼装（倍率由 AIPC 唯一缩放，VR 只显示）。
                    'mode_detail': {
                        'mode': self.mode,
                        'mode_text': mode_text,
                        'arm_mode': self.mode == 'arms',
                        'base_mode': self.mode == 'base',
                        'base_sub': self.base_sub,
                        'base_sub_text': BASE_SUB_TEXT[self.base_sub],
                        'vr_motion_scale': scale,
                        'vr_motion_scale_text': self.VR_SCALE_NAMES[scale],
                    },
                    'stopped': SAFETY.status()['stopped'],
                    'error': self.error,
                    'arms': arms,
                    'base': base,
                    'buttons': VR.buttons(now),
                    # key15 增补：左右摇杆按下 L3/R3 的合规性与瞬时状态
                    'stick_buttons': VR.stick_buttons_snapshot(now)}

    # ==================== 标定模式（2026-10-24，/api/calibrate）====================
    # 目的：解算坐标与真机末端位置存在系统性偏差（10-19 实测 X 偏 ~8cm、Y 偏 ~5cm），
    # 根因是底座相对底盘中心的安装偏移/偏航从未建模（OFF 恒零）。
    # 流程：plan 生成外偏 8 点（避开中间铁支架）→ 逐点 goto（关节直驱，固定水平姿态）
    # → record（CAN 读真实反馈并做模型 FK）→ measure（尺量测量点填实测值）
    # → solve（最小二乘 4 参数：平移 t + 偏航 yaw）→ apply（生效并持久化）。
    # 测量点 = 夹爪两指根转轴连线中点（与开合无关）；全程固定姿态，
    # 法兰到测量点的固定工具偏移被吸收进平移量，无需单独测量。
    def calibrate(self, data):
        if not isinstance(data, dict):
            return {'ok': False, 'error': 'body 必须是 JSON 对象'}, 400
        act = str(data.get('do', '')).strip()
        side = data.get('side', 'right')
        if side not in ('right', 'left'):
            return {'ok': False, 'error': 'side 必须是 right 或 left'}, 400
        sess = CALIB_SESSION[side]

        if act == 'status':
            return {'ok': True, 'side': side, 'calib': CALIB[side],
                    'points': sess['points'], 'pending': sess['pending']}, 200

        if act == 'plan':
            pts = self._calib_plan_points(side)
            if not pts:
                return {'ok': False, 'error': '没有生成任何可达且支架余量足够的点'}, 409
            sess['points'] = pts
            sess['pending'] = None
            _calib_session_save()
            return {'ok': True, 'side': side, 'points': pts,
                    'note': '逐点 goto → 到位停 3 秒 → record → 尺量后 measure'}, 200

        if act == 'add':
            # 追加加测点（2026-10-24 用户要求）：which=start 用起始位姿（与标定点同为
            # 水平姿态，工具偏移一致，可直接参与解算，也适合标定后精度验证）；
            # 或给 xyz_cm 自定义点（须过可达框 + IK + 支架余量三道筛）。
            which = str(data.get('which', '')).strip()
            if which == 'start':
                q = list(Q_START_RIGHT if side == 'right' else Q_START_LEFT)
                fk = list(_mv(_FR, _fk(q)[0]))
                margin, _d, _l, _r = arm_geometry.pose_margin(q, side)
                sess['points'].append({'target_m': fk, 'q': q,
                                       'margin_cm': round(margin, 1), 'state': 'planned',
                                       'label': '起始位姿'})
                _calib_session_save()
                return {'ok': True, 'side': side, 'index': len(sess['points']) - 1,
                        'target_cm': [round(v * 100, 1) for v in fk]}, 200
            try:
                cm = [float(v) for v in data.get('xyz_cm')]
            except (TypeError, ValueError):
                return {'ok': False, 'error': 'xyz_cm 必须是 3 个数值（cm）或 which=start'}, 400
            if len(cm) != 3:
                return {'ok': False, 'error': 'xyz_cm 必须是 3 个数值（cm）或 which=start'}, 400
            p = [v / 100.0 for v in cm]
            if not all(lo <= v <= hi for v, lo, hi in zip(p, TARGET_LO, TARGET_HI)):
                return {'ok': False, 'error': '超出可达框 %s..%s cm'
                        % (tuple(round(v * 100) for v in TARGET_LO),
                           tuple(round(v * 100) for v in TARGET_HI))}, 400
            q, err = solve_ik_user(p, QLEVEL, side=side)
            if q is None:
                return {'ok': False, 'error': 'IK 无解（%s），换个点' % err}, 409
            margin, _d, _l, _r = arm_geometry.pose_margin(list(q), side)
            if margin < CALIB_MIN_MARGIN:
                return {'ok': False, 'error': '支架余量 %.1f cm < %.1f cm，换个点' % (margin, CALIB_MIN_MARGIN)}, 409
            sess['points'].append({'target_m': p, 'q': list(q),
                                   'margin_cm': round(margin, 1), 'state': 'planned',
                                   'label': '自定义'})
            _calib_session_save()
            return {'ok': True, 'side': side, 'index': len(sess['points']) - 1,
                    'margin_cm': round(margin, 1)}, 200

        if act == 'goto':
            idx = int(data.get('index', -1))
            if not (0 <= idx < len(sess['points'])):
                return {'ok': False, 'error': 'index 越界或尚未 plan'}, 400
            pt = sess['points'][idx]
            deg = [round(math.degrees(v), 3) for v in pt['q']]
            key = 'left_joints_deg' if side == 'left' else 'right_joints_deg'
            mode = 'left_joints' if side == 'left' else 'right_joints'
            payload = {'client': CALIB_CLIENT,
                       'safety_epoch': data.get('safety_epoch'),
                       'controls': {'mode': mode, key: deg}}
            body, code = self.call('start', payload)
            if code != 200:
                return {'ok': False, 'error': (body or {}).get('error', '动作未被接受'),
                        'result': body}, code
            pt['state'] = 'arrived'
            return {'ok': True, 'side': side, 'index': idx,
                    'note': '已下发；到位后等 3 秒稳定再 record'}, 200

        if act == 'record':
            idx = int(data.get('index', -1))
            if not (0 <= idx < len(sess['points'])):
                return {'ok': False, 'error': 'index 越界或尚未 plan'}, 400
            # 刻意绕开缓存读一次最新反馈：标定要的是此刻真实角度
            ok, vals = (left_read_raw if side == 'left' else right_read_raw)()
            if not ok:
                return {'ok': False, 'error': '读不到 %s 臂反馈：%s' % (side, vals)}, 409
            q = [math.radians(v) for v in angles(vals)]
            fk = _mv(_FR, _fk(q)[0])          # 模型 FK 位置（不含标定修正，解算基准）
            # 到位校验（2026-10-24 实测新增）：J2 扛重力爬升慢，等 3 秒可能远未到位
            # （实测 J2 指令 156° 反馈仅 114°）。反馈与指令偏差 >8° 时明确告警——
            # 标定数学上用反馈 FK 仍正确，但提示用户「等久一点再记录」点位更分散。
            tgt_deg = [math.degrees(v) for v in sess['points'][idx]['q']]
            dev = max(abs(a - b) for a, b in zip(vals, tgt_deg))
            warn = None
            if dev > 8.0:
                warn = ('臂尚未完全到位：反馈与指令最大偏差 %.1f°（阈值 8°）。'
                        '已按当前真实位置记录；若想点位更准，等臂停稳后再点一次「记录反馈」'
                        % dev)
            sess['points'][idx].update(state='recorded',
                                       fb_deg=[round(v, 2) for v in vals],
                                       fk_m=[round(v, 4) for v in fk])
            _calib_session_save()
            out = {'ok': True, 'side': side, 'index': idx,
                   'fb_deg': sess['points'][idx]['fb_deg'],
                   'dev_deg': round(dev, 1),
                   'fk_cm': [round(v * 100, 1) for v in fk]}
            if warn:
                out['warn'] = warn
            return out, 200

        if act == 'measure':
            idx = int(data.get('index', -1))
            if not (0 <= idx < len(sess['points'])):
                return {'ok': False, 'error': 'index 越界或尚未 plan'}, 400
            pt = sess['points'][idx]
            if not pt.get('fk_m'):
                return {'ok': False, 'error': '该点尚未 record，请先记录反馈'}, 409
            try:
                cm = [float(v) for v in data.get('xyz_cm')]
            except (TypeError, ValueError):
                return {'ok': False, 'error': 'xyz_cm 必须是 3 个数值（cm，底盘系：X右/Y前/Z上）'}, 400
            if len(cm) != 3:
                return {'ok': False, 'error': 'xyz_cm 必须是 3 个数值（cm，底盘系：X右/Y前/Z上）'}, 400
            pt['meas_m'] = [v / 100.0 for v in cm]
            pt['state'] = 'measured'
            _calib_session_save()
            return {'ok': True, 'side': side, 'index': idx}, 200

        if act == 'solve':
            res = self._calib_solve(side)
            if res is None:
                return {'ok': False, 'error': '可用实测点不足（至少 6 个 measured）或方程奇异'}, 409
            sess['pending'] = res
            _calib_session_save()
            return {'ok': True, 'side': side, 'result': res,
                    'note': '确认残差可接受后 apply 生效；不满意可 reset 清零'}, 200

        if act == 'apply':
            res = sess.get('pending')
            if not res:
                return {'ok': False, 'error': '没有待应用的解算结果，请先 solve'}, 409
            CALIB[side] = {'t': list(res['t']), 'yaw': res['yaw'],
                           's': res.get('s', 0.0)}
            _calib_save()
            return {'ok': True, 'side': side, 'calib': CALIB[side],
                    'note': '修正已生效并写入 calib_offsets.json，服务重启也会保留'}, 200

        if act == 'reset':
            CALIB[side] = {'t': [0.0, 0.0, 0.0], 'yaw': 0.0, 's': 0.0}
            _calib_save()
            return {'ok': True, 'side': side, 'calib': CALIB[side],
                    'note': '该臂修正已清零（恒等）'}, 200

        if act == 'release':
            payload = {'client': CALIB_CLIENT, 'safety_epoch': data.get('safety_epoch')}
            body, code = self.call('stop', payload)
            return {'ok': code == 200, 'side': side, 'result': body}, code

        return {'ok': False, 'error': '未知动作 do=%s（plan/goto/record/measure/solve/apply/reset/release/status）' % (act or '(空)')}, 400

    @staticmethod
    def _calib_plan_points(side):
        """生成标定点（固定水平姿态）：外偏避开中间铁支架——右臂取 +X 侧、左臂取 -X 侧。
        在候选网格上筛「IK 可达且支架余量足够」的点，再贪心挑 8 个分布最散的
        （最大化最小间距，保证偏航/平移都可观测）。固定姿态下法兰到测量点的
        工具偏移为常量，会被吸收进平移量，无需单独测量。"""
        sgn = 1.0 if side == 'right' else -1.0
        cand = []
        for ax in (0.18, 0.24, 0.30, 0.36):
            for y in (0.26, 0.32, 0.38, 0.44):
                for z in (0.12, 0.20, 0.28, 0.36):
                    p = [sgn * ax, y, z]
                    q, _err = solve_ik_user(p, QLEVEL, side=side)
                    if q is None:
                        continue
                    margin, _d, _l, _r = arm_geometry.pose_margin(list(q), side)
                    if margin < CALIB_MIN_MARGIN:
                        continue
                    cand.append({'target_m': p, 'q': list(q),
                                 'margin_cm': round(margin, 1), 'state': 'planned'})
        # 贪心 max-min 分散选 8 个：先取最外前上角，再逐个取离已选集合最远的
        picked = []
        if cand:
            first = max(cand, key=lambda c: abs(c['target_m'][0]) + c['target_m'][1] + c['target_m'][2])
            picked.append(first)
            while len(picked) < 8 and len(picked) < len(cand):
                nxt = max((c for c in cand if c not in picked),
                          key=lambda c: min(math.dist(c['target_m'], p['target_m'])
                                            for p in picked))
                picked.append(nxt)
        return picked

    @staticmethod
    def _calib_solve(side):
        """最小二乘解 5 参数刚体修正：实测 m ≈ Rz(yaw)·(模型FK f + s·a) + t。
        f = record 时存的法兰 FK（用户系、无修正）；a = 该点反馈角重算的法兰轴
        单位向量（用户系 = _FR·原生姿态第 3 列）；s = 测量点（两指根转轴连线
        中点）到法兰中心沿法兰轴的距离（2026-10-25 零位实测 ≈7.4cm——旧 4 参数
        解把这个 TCP 偏移错当基座平移吸收，旧 t_y≈+6.6cm 即源于此）。
        线性化（yaw 为小量，yaw·s 为二阶小量忽略）：
            r = m - f ≈ (dx, dy, dz) + yaw·(-f_y, f_x, 0) + s·a
        残差按完整非线性式 Rz(yaw)·(f+s·a)+t 回代。纯 Python 5x5 高斯消元。"""
        pts = [p for p in CALIB_SESSION[side]['points']
               if p.get('state') == 'measured' and p.get('fk_m') and p.get('meas_m')]
        if len(pts) < 6:
            return None
        N = 5
        ATA = [[0.0] * N for _ in range(N)]
        ATb = [0.0] * N
        axes = []
        for p in pts:
            q_deg = p.get('fb_deg') or [math.degrees(v) for v in p['q']]
            q = [math.radians(v) for v in q_deg]
            Rn = _fk(q)[1]                # 原生系法兰姿态
            a = _mv(_FR, (Rn[0][2], Rn[1][2], Rn[2][2]))   # 法兰轴 → 用户系
            axes.append(a)
            f, m = p['fk_m'], p['meas_m']
            rows = ((1.0, 0.0, 0.0, -f[1], a[0], m[0] - f[0]),
                    (0.0, 1.0, 0.0, f[0], a[1], m[1] - f[1]),
                    (0.0, 0.0, 1.0, 0.0, a[2], m[2] - f[2]))
            for row in rows:
                ar, b = row[:N], row[N]
                for i in range(N):
                    ATb[i] += ar[i] * b
                    for j in range(N):
                        ATA[i][j] += ar[i] * ar[j]
        M = [row[:] + [ATb[i]] for i, row in enumerate(ATA)]
        for c in range(N):
            pvt = max(range(c, N), key=lambda r: abs(M[r][c]))
            if abs(M[pvt][c]) < 1e-12:
                return None
            M[c], M[pvt] = M[pvt], M[c]
            d = M[c][c]
            M[c] = [v / d for v in M[c]]
            for r in range(N):
                if r == c:
                    continue
                fac = M[r][c]
                M[r] = [x - fac * y for x, y in zip(M[r], M[c])]
        dx, dy, dz, yaw, s = (M[i][N] for i in range(N))
        cw, sw = math.cos(yaw), math.sin(yaw)
        errs = []
        for p, a in zip(pts, axes):
            f, m = p['fk_m'], p['meas_m']
            fx, fy, fz = f[0] + s * a[0], f[1] + s * a[1], f[2] + s * a[2]
            errs.append(math.dist((cw * fx - sw * fy + dx,
                                   sw * fx + cw * fy + dy,
                                   fz + dz), m))
        rms = math.sqrt(sum(e * e for e in errs) / len(errs))
        return {'t': [dx, dy, dz], 'yaw': yaw, 's': s,
                't_cm': [round(v * 100, 2) for v in (dx, dy, dz)],
                'yaw_deg': round(math.degrees(yaw), 2),
                's_cm': round(s * 100, 2),
                'rms_cm': round(rms * 100, 2),
                'max_cm': round(max(errs) * 100, 2),
                'n': len(pts)}


SENDER = ControlSender()
ACTIONS = ("prepare", "enable", "zero", "deploy_start", "deploy_stop",
           "enable_left", "zero_left", "disable", "disable_left")
# 六轴限位：下限与官方机械硬限位一致，上限保留 0.05 rad 安全余量。
# KR260 执行端必须使用同一组下限，避免 AIPC 通过后目标被静默钳制。
JOINT_LO = _QLO
JOINT_HI = (2.618, 3.092, -0.05, 1.695, 1.17, 2.0444)


# ===== 任务数据采集（Episode Recorder，2026-10-25 一期）=====
# 规范见 01_文档/遥操作数据采集规范_20261025.md。设计取舍：
# - 独立 20Hz 采样线程，**只读** SENDER 状态与 _FB_CACHE，不挂钩发送循环：
#   控制链路零改动、零风险；动作真值 = SENDER 中正在下发的量（与发送同一份源）。
# - 关节反馈直接读 _FB_CACHE（约 1.4Hz 更新），不为采集额外轰炸 KR260。
# - 落盘 CSV + meta.json，零依赖（AIPC 无 h5py）；HDF5/LeRobot 由离线脚本后转。
# - 记录器任何异常只影响记录本身，绝不影响控制；磁盘不足自动停止并标注。
DATASET_ROOT = os.environ.get('ARM_DATASET_ROOT', '/home/apex/datasets')
REC_SAMPLE_S = 0.05                     # 20Hz
REC_FLUSH_ROWS = 20                     # 约 1s 落盘一次，崩溃损失可控
REC_MIN_FREE = 300 * 1024 * 1024        # 磁盘余量低于 300MB 拒绝开始/自动停止
REC_MODE_CODE = {'arms': 0, 'base': 1}
REC_SUB_CODE = {'a': 0, 'b': 1}
REC_ACTIONS_HEADER = ('t,seq,mode,base_sub,own_r,own_l,vr_r,vr_l,'
                      'rj1,rj2,rj3,rj4,rj5,rj6,rg,'
                      'lj1,lj2,lj3,lj4,lj5,lj6,lg,vx,vy,wz,base_active')
REC_FB_HEADER = 't,rok,r1,r2,r3,r4,r5,r6,lok,l1,l2,l3,l4,l5,l6'


class EpisodeRecorder:
    """一次任务 = 一个 Episode 目录：actions.csv（20Hz 动作真值）+
    joints_fb.csv（关节反馈快照）+ meta.json（开始即写、结束补全，崩溃也有元数据）。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.active = False
        self.episode_id = None
        self.dir = None
        self.meta = None
        self._fa = None                 # actions.csv 文件对象
        self._ff = None                 # joints_fb.csv 文件对象
        self._rows_a = 0
        self._rows_f = 0
        self._since_flush = 0
        self._t0 = 0.0                  # monotonic 起点
        self._err_streak = 0
        self.auto_note = ''

    # ---------- 对外 API ----------
    def start(self, task_text, operator, scene_notes):
        task_text = str(task_text or '').strip()[:200]
        operator = str(operator or '').strip()[:40]
        scene_notes = str(scene_notes or '').strip()[:400]
        if not task_text:
            raise ValueError('task_text 必填：一句话说清「做什么」')
        with self.lock:
            if self.active:
                raise ValueError('已有记录进行中：请先结束当前 Episode（%s）' % self.episode_id)
        os.makedirs(DATASET_ROOT, exist_ok=True)
        if shutil.disk_usage(DATASET_ROOT).free < REC_MIN_FREE:
            raise ValueError('磁盘余量不足 300MB，拒绝开始记录')
        episode_id = time.strftime('ep_%Y%m%d_%H%M%S')
        path = os.path.join(DATASET_ROOT, episode_id)
        os.makedirs(path, exist_ok=False)
        fa = open(os.path.join(path, 'actions.csv'), 'w', encoding='utf-8')
        fa.write(REC_ACTIONS_HEADER + '\n')
        ff = open(os.path.join(path, 'joints_fb.csv'), 'w', encoding='utf-8')
        ff.write(REC_FB_HEADER + '\n')
        meta = {
            'episode_id': episode_id,
            'task_text': task_text,
            'operator': operator,
            'scene_notes': scene_notes,
            'start_time': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'start_unix': round(time.time(), 3),
            'end_time': None, 'duration_s': None,
            'success': None, 'fail_reason': '', 'interventions': None,
            'sample_rate_hz': round(1.0 / REC_SAMPLE_S),
            'units': {'joints_cmd': 'rad', 'joints_fb': 'deg',
                      'grip': '闭合量 0=全开 1=全闭',
                      'base': 'vx,vy m/s; wz rad/s',
                      't': 'unix 秒'},
            'codes': {'mode': REC_MODE_CODE, 'base_sub': REC_SUB_CODE,
                      'own/vr/base_active': '0/1'},
            'files': ['actions.csv', 'joints_fb.csv', 'meta.json'],
            'rows': {'actions': 0, 'joints_fb': 0},
            'sw_version': {'aipc_md5': self._self_md5()},
            'note': '一期：动作=下发真值（SENDER 源）；反馈读缓存约1.4Hz；'
                    '视频/深度待二期接入',
        }
        with self.lock:
            self.episode_id, self.dir, self.meta = episode_id, path, meta
            self._fa, self._ff = fa, ff
            self._rows_a = self._rows_f = self._since_flush = 0
            self._err_streak = 0
            self.auto_note = ''
            self._t0 = time.monotonic()
            self.active = True
        self._write_meta()              # 开始即落 meta，中途崩溃也有记录
        threading.Thread(target=self._loop, daemon=True, name='episode-recorder').start()
        return {'ok': True, 'episode_id': episode_id, 'dir': path}

    def stop(self, success=None, fail_reason='', interventions=None, scene_notes=''):
        with self.lock:
            if not self.active:
                raise ValueError('当前没有进行中的记录')
            self.active = False
        time.sleep(REC_SAMPLE_S * 2)    # 让采样线程退出循环
        with self.lock:
            try:
                self._fa.close(); self._ff.close()
            except Exception:           # noqa: BLE001
                pass
            meta = self.meta
            meta['end_time'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
            meta['duration_s'] = round(time.monotonic() - self._t0, 2)
            meta['success'] = bool(success) if success is not None else None
            meta['fail_reason'] = str(fail_reason or '').strip()[:200]
            if interventions is not None:
                try:
                    meta['interventions'] = max(0, int(interventions))
                except (TypeError, ValueError):
                    pass
            extra = str(scene_notes or '').strip()[:400]
            if extra:
                meta['scene_notes'] = (meta['scene_notes'] + '；' + extra).strip('；')
            if self.auto_note:
                meta['auto_note'] = self.auto_note
            meta['rows'] = {'actions': self._rows_a, 'joints_fb': self._rows_f}
            self._write_meta()
            out = {'ok': True, 'episode_id': self.episode_id, 'dir': self.dir,
                   'duration_s': meta['duration_s'], 'rows': meta['rows']}
            if self.auto_note:
                out['auto_note'] = self.auto_note
        return out

    def status(self):
        with self.lock:
            if not self.active:
                return {'recording': False}
            return {'recording': True, 'episode_id': self.episode_id,
                    'task_text': self.meta['task_text'],
                    'elapsed_s': round(time.monotonic() - self._t0, 1),
                    'rows': {'actions': self._rows_a, 'joints_fb': self._rows_f},
                    'dir': self.dir}

    # ---------- 内部 ----------
    @staticmethod
    def _self_md5():
        try:
            with open(os.path.abspath(__file__), 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:               # noqa: BLE001
            return None

    def _write_meta(self):
        tmp = os.path.join(self.dir, 'meta.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=2)
        os.replace(tmp, os.path.join(self.dir, 'meta.json'))

    def _loop(self):
        next_t = time.monotonic()
        while True:
            with self.lock:
                if not self.active:
                    return
            try:
                self._sample()
                self._err_streak = 0
            except Exception:           # noqa: BLE001
                self._err_streak += 1
                if self._err_streak >= 5:
                    self._auto_stop('采样连续异常，已自动停止')
                    return
            if self._rows_a % 100 == 0:  # 每 5s 查一次磁盘
                try:
                    if shutil.disk_usage(self.dir).free < REC_MIN_FREE:
                        self._auto_stop('磁盘余量不足 300MB，已自动停止')
                        return
                except Exception:       # noqa: BLE001
                    pass
            next_t += REC_SAMPLE_S
            delay = next_t - time.monotonic()
            time.sleep(delay if delay > 0 else REC_SAMPLE_S)

    def _auto_stop(self, note):
        try:
            self.stop(success=None, fail_reason='')
        except Exception:               # noqa: BLE001
            pass
        with self.lock:
            self.auto_note = note
            if self.meta is not None:
                self.meta['auto_note'] = note
                try:
                    self._write_meta()
                except Exception:       # noqa: BLE001
                    pass

    def _sample(self):
        t = time.time()
        with SENDER.lock:
            mode = SENDER.mode
            sub = SENDER.base_sub
            own_r = SENDER.owner is not None
            own_l = SENDER.owner_left is not None
            vr_r = bool(SENDER.vr_on)
            vr_l = bool(SENDER.vr_left_on)
            rj = list(SENDER.joints)
            rg = SENDER.grip
            lj = list(SENDER.left_joints) if SENDER.left_joints else None
            lg = SENDER.left_grip
            bs = dict(SENDER.base_state)
            seq = SENDER.seq
        row = [f'{t:.3f}', str(seq),
               str(REC_MODE_CODE.get(mode, -1)), str(REC_SUB_CODE.get(sub, -1)),
               '1' if own_r else '0', '1' if own_l else '0',
               '1' if vr_r else '0', '1' if vr_l else '0']
        row += [f'{v:.4f}' for v in rj] + [f'{rg:.3f}']
        row += ([f'{v:.4f}' for v in lj] + [f'{lg:.3f}']) if lj else [''] * 7
        row += [f"{bs.get('vx', 0.0):.3f}", f"{bs.get('vy', 0.0):.3f}",
                f"{bs.get('wz', 0.0):.3f}", '1' if bs.get('active') else '0']
        self._fa.write(','.join(row) + '\n')
        self._rows_a += 1
        # 关节反馈：直接读缓存（不触网），失败侧留空
        frow = [f'{t:.3f}']
        for side in ('right', 'left'):
            ts, ok, vals = _FB_CACHE[side]
            if ok and isinstance(vals, list) and len(vals) == 6:
                frow += ['1'] + [f'{v:.2f}' for v in vals]
            else:
                frow += ['0'] + [''] * 6
        self._ff.write(','.join(frow) + '\n')
        self._rows_f += 1
        self._since_flush += 1
        if self._since_flush >= REC_FLUSH_ROWS:
            self._fa.flush(); self._ff.flush()
            self._since_flush = 0


RECORDER = EpisodeRecorder()


def send_base(data):
    """Send and record submission, never equate UDP submission with execution."""
    enable = data.get('enable', False)
    if type(enable) is not bool:
        raise ValueError('enable 必须为布尔值')
    rc = data.get('rc', False)
    if type(rc) is not bool:
        raise ValueError('rc 必须为布尔值')
    values = []
    for name, limit in [('vx', .8), ('vy', .8), ('wz', 1.0)]:
        value = data.get(name, 0)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('速度必须为有限数值')
        values.append(max(-limit, min(limit, value)) if enable else 0.0)
    # rc=True（RC 遥控车子模式）：relay 蟹行实现（行进转向=档位 8 方向偏转，静止转向=档位 6 自旋）
    pkt = dict(zip(('vx', 'vy', 'wz'), values), enable=enable, rc=rc)
    # C05：控制源互斥。VR 正在驱动底盘（Y 键切到 base 模式）时，网页摇杆不得同时下发，
    # 否则两边交替覆盖同一条 UDP 指令，车辆表现取决于谁后到。
    if SENDER.mode == 'base':
        raise ValueError('VR 正在控制底盘（Y 键）：请先按 B 切回双臂模式，再用网页摇杆')
    with SAFETY.lock:
        if enable:
            SAFETY.require(data)
        try:
            BASE_UDP.sendto(json.dumps(pkt).encode(), BASE_UDP_TARGET)
            BASE_COMMAND.update(submitted_at=time.time(), enable=enable, error=None)
        except Exception as e:
            BASE_COMMAND['error'] = str(e)
            raise
    return dict(ok=True, submitted=True, execution_confirmed=False)


def finish_stop_all(epoch, note='全局软件停止：会话已撤销'):
    """Wait behind any in-flight management action, then stop the shared deploy.

    epoch 为 None 表示“有序停机”：撤会话 + 停 deploy，但不回写软件停止结果
    （SAFETY.result/complete 对不匹配的 epoch 天然 no-op）。
    """
    try:
        # 与 A／模式切换共用撤销路径：使旧任务 ID 失效，并把搬运状态置为 cancelled。
        SENDER._cancel_sessions(note)
        with ACTION_LOCK:
            rc, out = kr260('deploy_stop')
            verify_rc, status = kr260('status')
            ok = rc == 0 and verify_rc == 0 and re.search(r'deploy:\s*STOPPED', status)
            SAFETY.result(epoch, 'arms', '双臂/VR 会话已撤销，控制进程已停止；实际姿态需观察'
                          if ok else '会话已封锁，控制进程停止未确认：'+out[-300:])
    except Exception as e:
        SAFETY.result(epoch, 'arms', '停止未确认：'+str(e))
    finally:
        SAFETY.complete(epoch)


def stop_all():
    epoch = SAFETY.stop()  # Immediately blocks ticks and all new motion requests.
    try:
        send_base(dict(enable=False))
        SAFETY.result(epoch, 'base', '零速断使能已提交；实际停车请查看底盘反馈')
    except Exception as e:
        SAFETY.result(epoch, 'base', '停车请求失败：'+str(e))
    threading.Thread(target=finish_stop_all, args=(epoch,), daemon=True).start()
    return SAFETY.status()


class Handler(BaseHTTPRequestHandler):
    server_version = "arm-console/1.0"
    _status_cache = (0.0, None)

    # C23：来源边界。
    # 8092 仍然监听 0.0.0.0（现场要从 VR 机/另一台电脑访问），但**不再发通配 CORS**：
    # 只有本机或受信主机的页面能跨源读到响应，别的站点既读不到也不能改状态。
    # 想加一台机器就用环境变量 CONSOLE_ALLOWED_HOSTS="192.168.1.9,foo.local"。
    DEFAULT_ALLOWED_HOSTS = ("192.168.137.2", "127.0.0.1", "localhost")
    _allowed_hosts = None

    @classmethod
    def allowed_hosts(cls):
        if cls._allowed_hosts is None:
            import os
            extra = [h.strip().lower()
                     for h in (os.environ.get("CONSOLE_ALLOWED_HOSTS") or "").split(",")
                     if h.strip()]
            cls._allowed_hosts = tuple(cls.DEFAULT_ALLOWED_HOSTS) + tuple(extra)
        return cls._allowed_hosts

    def _origin_host(self):
        """取 Origin 的主机名；无 Origin 返回 None（同源导航或命令行工具）。"""
        raw = self.headers.get("Origin")
        if not raw:
            return None
        m = re.match(r'^https?://([^/:]+)(?::\d+)?$', raw.strip(), re.I)
        return m.group(1).lower() if m else "?"

    def _origin_ok(self):
        """来源是否受信。无 Origin 视为同源/本地工具；有 Origin 必须在白名单或与 Host 同源。"""
        host = self._origin_host()
        if host is None:
            return True
        if host in self.allowed_hosts():
            return True
        host_hdr = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        return bool(host_hdr) and host == host_hdr

    def _cors(self):
        host = self._origin_host()
        if host is not None and self._origin_ok():
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin"))
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def _reply(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # 静默
        pass

    def do_OPTIONS(self):
        if not self._origin_ok():
            return self._reply({"error": "跨站来源被拒绝（C23）"}, 403)
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/safety":
            return self._reply(SAFETY.status())
        if self.path == "/api/vr_telemetry":
            # VR APK 侧只读遥测：模式/臂状态/位置/底盘/按键（CORS 已放行受信来源）
            return self._reply(SENDER.telemetry())
        if self.path == "/api/base_status":
            with SAFETY.lock:
                command = dict(BASE_COMMAND)
            with SENDER.lock:
                sub = SENDER.base_sub
                timed = dict(getattr(SENDER, '_base_intent', {}))
                generation = getattr(SENDER, '_base_gen', 0)
            return self._reply(dict(command=command, device=BASE_FEEDBACK.status(),
                                    sub=sub, sub_text=BASE_SUB_TEXT[sub],
                                    base_generation=generation, timed_intent=timed))
        if self.path == "/api/intent":
            return self._reply(SENDER.intent_schema())
        if self.path == "/api/transfer/status":
            return self._reply({'ok': True, 'transfer': SENDER.transfer_status()})
        if self.path == "/api/record/status":
            return self._reply(RECORDER.status())
        if self.path == "/api/vr_sticks":
            return self._reply(VR.sticks())
        if self.path == "/api/vr_buttons":
            # 只读：A/B/X/Y 的 valid/pressed 位图 + 当前模式 + 底盘状态。
            # 不授予任何控制权；顺带返回 mode/base 是为了让顶部指示条只轮询一个端点。
            payload = VR.buttons()
            with SENDER.lock:
                payload['mode'] = SENDER.mode
                payload['base_sub'] = SENDER.base_sub
                payload['base'] = dict(SENDER.base_state)
                payload['move_result'] = dict(SENDER.move_result)
            return self._reply(payload)
        if self.path == "/api/status":
            # KR260 状态 SSH 查询带 2s 缓存：页面有 300ms/1.5s/3s 三路轮询，
            # 不缓存会持续高频 SSH（2026-10-21 左臂无响应问题的另一半原因）
            now = time.monotonic()
            if Handler._status_cache[1] is None or now - Handler._status_cache[0] > 2.0:
                Handler._status_cache = (now, kr260("status"))
            rc, out = Handler._status_cache[1]
            can = re.search(r"can2:\s*(?:\S+\s+)?(\S+)", out)
            can1 = re.search(r"can1:\s*(?:\S+\s+)?(\S+)", out)
            dep = re.search(r"deploy:\s*(\S+)", out)
            self._reply(dict(ok=rc == 0, raw=out,
                             can2=can.group(1) if can else "UNKNOWN",
                             can1=can1.group(1) if can1 else "UNKNOWN",
                             deploy=dep.group(1) if dep else "UNKNOWN",
                             control=SENDER.status(), safety=SAFETY.status()))
        elif self.path == "/api/deploy_log":
            rc, out = kr260("deploy_log", "30")
            self._reply(dict(ok=rc == 0, log=out))
        elif self.path in ('/api/entry_log/left', '/api/entry_log/right'):
            side = self.path.rsplit('/', 1)[1]
            path = ENTRY_LOGS.get(side)
            try:
                with open(path, encoding='utf-8') as stream:
                    text = stream.read()
                self._reply({'ok': True, 'side': side,
                             'file': os.path.basename(path), 'log': text})
            except (OSError, TypeError):
                self._reply({'ok': False, 'error': '尚无本侧入口日志'}, 404)
        elif self.path == "/api/left_read":
            ok, res = left_read()
            if ok:
                self._reply(dict(ok=True, joints_deg=res))
            else:
                self._reply(dict(ok=False, error=res), 200)
        elif self.path == "/api/right_read":
            ok, res = right_read()
            if ok:
                self._reply(dict(ok=True, joints_deg=res))
            else:
                self._reply(dict(ok=False, error=res), 200)
        else:
            self._reply({"error": "not found"}, 404)

    def do_POST(self):
        # C23：跨站来源一律拒绝（状态变更是最危险的一类）。浏览器跨源 POST 必带 Origin，
        # 同源页面与命令行工具不带或与 Host 一致，所以这一条不会误伤正常用法。
        if not self._origin_ok():
            return self._reply({"error": "跨站来源被拒绝（C23）：控制接口只接受本机/受信页面的请求"}, 403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                return self._reply({"error": "body too large"}, 413)
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError('body must be an object')
        except Exception:  # noqa: BLE001
            return self._reply({"error": "bad json"}, 400)
        if self.path == '/api/vla_plan_preview':
            # 只读规划：不检查/获取控制权，不实例化运动会话，不调用任何发送接口。
            try:
                from vla_plan_preview import preview
                return self._reply(preview(data, sys.modules[__name__]), 200)
            except (ValueError, RuntimeError) as exc:
                return self._reply({'ok': False, 'read_only': True,
                                    'execution_enabled': False, 'error': str(exc)}, 409)
        if self.path == '/api/grasp_target_preview':
            # 只读取实时识别目标并换算预抓 J5，不创建运动或控制会话。
            try:
                from grasp_target_bridge import run
                return self._reply(run(data), 200)
            except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
                return self._reply({'ok': False, 'read_only': True,
                                    'execution_enabled': False, 'error': str(exc)}, 409)
        if self.path == '/api/collect_grasp_sample':
            # 只保存相机、深度、识别和控制状态；不创建运动或夹爪会话。
            try:
                from collect_grasp_api import run
                return self._reply(run(data), 200)
            except (ValueError, RuntimeError, OSError) as exc:
                return self._reply({'ok': False, 'error': str(exc)}, 409)
        if self.path == '/api/vla_dataset':
            # AIPC 连续只读采集；start/stop/stage/status 均不发送运动命令。
            try:
                from vla_dataset_recorder import run
                return self._reply(run(data, sys.modules[__name__]), 200)
            except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
                return self._reply({'ok': False, 'error': str(exc)}, 409)
        if self.path == '/api/vla_motion_execute':
            # 通用左臂 J5 XYZ：50mm 位移上限、精确网格、20% 限速、现有安全会话。
            try:
                from vla_motion_execute import run
                return self._reply(*run(data, sys.modules[__name__]))
            except (ValueError, RuntimeError) as exc:
                return self._reply({'ok': False, 'error': str(exc)}, 409)
        if self.path == '/api/vla_test_motion':
            # 固定往返回归轨迹；独立确认字段，不代替通用 VLA 接口。
            try:
                from vla_test_motion import run
                return self._reply(*run(data, sys.modules[__name__]))
            except (ValueError, RuntimeError) as exc:
                return self._reply({'ok': False, 'error': str(exc)}, 409)
        if self.path == '/api/vr_route':
            try:
                SAFETY.require(data)
                action = data.get('action')
                if action not in ('left_transfer', 'dual_home'):
                    return self._reply({'error': '未知流程'}, 400)
                with SENDER.lock:
                    if SENDER.mode != 'arms':
                        return self._reply({'error': '底盘模式下不能启动机械臂流程'}, 409)
                    if action == 'left_transfer' and SENDER._vr_route_running:
                        return self._reply({'error': '左臂搬运流程正在运行'}, 409)
                side = 'left' if action == 'left_transfer' else 'right'
                SENDER._request_preset(side)
                message = ('左臂搬运流程已启动（与手柄 X 相同）' if side == 'left'
                           else '双臂返回起始已启动（与手柄 A 相同）')
                return self._reply({'ok': True, 'message': message}, 202)
            except ValueError as exc:
                return self._reply({'error': str(exc)}, 409)
        if self.path == '/api/intent':
            try:
                return self._reply(*SENDER.intent(data))
            except ValueError as exc:
                return self._reply({'ok': False, 'error': str(exc)}, 409)
        if self.path == '/api/record/start':
            try:
                return self._reply(RECORDER.start(data.get('task_text'),
                                                  data.get('operator'),
                                                  data.get('scene_notes')))
            except ValueError as exc:
                return self._reply({'ok': False, 'error': str(exc)}, 409)
            except OSError as exc:
                return self._reply({'ok': False, 'error': '创建数据目录失败：%s' % exc}, 500)
        if self.path == '/api/record/stop':
            try:
                return self._reply(RECORDER.stop(success=data.get('success'),
                                                 fail_reason=data.get('fail_reason'),
                                                 interventions=data.get('interventions'),
                                                 scene_notes=data.get('scene_notes')))
            except ValueError as exc:
                return self._reply({'ok': False, 'error': str(exc)}, 409)
        if self.path == '/api/calibrate':
            return self._reply(*SENDER.calibrate(data))
        if self.path == '/api/stop_all':
            return self._reply(stop_all(), 202)
        if self.path == '/api/resume':
            try:
                return self._reply(SAFETY.resume(data))
            except ValueError as e:
                return self._reply({'error': str(e)}, 409)
        if self.path == '/api/action':
            # Management commands cannot overlap; stop_all latches immediately
            # and its worker runs deploy_stop AFTER an in-flight action finishes.
            with ACTION_LOCK:
                try:
                    if data.get('action') != 'deploy_stop':
                        SAFETY.require(data)
                except ValueError as e:
                    return self._reply({'error': str(e)}, 409)
                return self._dispatch_post(data)
        return self._dispatch_post(data)

    def _dispatch_post(self, data):
        if self.path == "/api/action":
            action = data.get("action", "")
            if action == 'deploy_stop':
                with SENDER.lock:
                    if any(SENDER.entries.values()) or any(SENDER.entry_pending.values()):
                        stop_all()
                        return self._reply(dict(ok=True, output='进入跟随已取消，全局软件停止已锁定'), 202)
            if action in ('zero', 'zero_left'):
                return self._reply({'error': '旧「预备位」已废弃：请改用 /api/control 的 move=start|zero（页面按钮「移动到起始」「移动到零位」）'}, 409)
            if action == "joint_set":
                joints = data.get("joints")
                if (not isinstance(joints, list) or len(joints) != 6
                        or any(type(j) not in (int, float) or not math.isfinite(j)
                               or not (lo <= j <= hi)
                               for j, lo, hi in zip(joints, JOINT_LO, JOINT_HI))):
                    return self._reply({"error": "joints 超出限位（各轴范围见页面标注）"}, 400)
                if deploy_running():
                    return self._reply({"error": "deploy 运行中禁止关节直驱，请先停止控制程序"}, 409)
                rc, out = kr260("set", *[f"{j:.4f}" for j in joints])
                return self._reply(dict(ok=rc == 0, action=action, output=out), 200 if rc == 0 else 500)
            if action == "joint_set_left":
                joints = data.get("joints")
                if (not isinstance(joints, list) or len(joints) != 6
                        or any(type(j) not in (int, float) or not math.isfinite(j)
                               or not (lo <= j <= hi)
                               for j, lo, hi in zip(joints, JOINT_LO, JOINT_HI))):
                    return self._reply({"error": "joints 超出限位（各轴范围见页面标注）"}, 400)
                if deploy_running():
                    return self._reply({"error": "deploy 运行中禁止关节直驱，请先停止控制程序"}, 409)
                rc, out = kr260("set_left", *[f"{j:.4f}" for j in joints])
                return self._reply(dict(ok=rc == 0, action=action, output=out), 200 if rc == 0 else 500)
            if action in ('exit_teach', 'exit_teach_left'):
                side = 'left' if action.endswith('_left') else 'right'
                with SENDER.lock:
                    if (any(SENDER.entries.values()) or any(SENDER.entry_pending.values())
                            or SENDER.owner is not None or SENDER.owner_left is not None):
                        return self._reply({'ok': False, 'action': action,
                                            'error': '存在活动控制或跟随会话，请先停止跟随'}, 409)
                if deploy_running():
                    return self._reply({'ok': False, 'action': action,
                                        'error': 'deploy 运行中禁止切换控制模式，请先停止双臂程序'}, 409)
                rc, out = exit_teach_can(side)
                if rc == 0:
                    out = (side == 'left' and '左臂' or '右臂') + '已确认 CAN / MOVE J；未发送运动目标\n' + out
                return self._reply(dict(ok=rc == 0, action=action, output=out),
                                   200 if rc == 0 else 500)
            if action not in ACTIONS:
                return self._reply({"error": "unknown action"}, 400)
            if action in ('disable', 'disable_left') and deploy_running():
                # 安全护栏：本机固件在状态字节 DISABLED 下仍会执行位置指令（2026-10-14 实测），
                # 所以 deploy 运行中「取消使能」既不会让手臂停下，又会让它失去保持力矩。
                # 必须先把控制程序停掉，才能断使能。
                return self._reply({
                    'ok': False, 'action': action,
                    'error': ('deploy 运行中禁止取消使能：该固件在 DISABLED 状态下仍执行位置指令，'
                              '此时断使能既不能让手臂停下，又会失去保持力矩。请先点「停止双臂程序」。')}, 409)
            if action == 'deploy_start':
                # 远端脚本把 deploy 放到后台，该后台进程占住 SSH 的 stdout 管道，
                # ssh 要等超时才返回（实测 >25 s），但脚本本身 ~1 s 就已完成。
                # 所以：短超时结束等待，再以状态查询确认是否真的起来了。
                rc, out = kr260(action, timeout=3.0)
                started = deploy_running()
                for _ in range(4):
                    if started:
                        break
                    time.sleep(0.7)
                    started = deploy_running()
                Handler._status_cache = (0.0, None)   # 让页面立刻看到新状态
                if not started:
                    return self._reply({'ok': False, 'action': action,
                                        'output': out + '\n未确认 deploy 已启动（状态查询仍为未运行）'}, 500)
                if rc == 124:
                    # 这是“我们主动提前结束等待”，不是 KR260 掉线，别把超时文案透给使用者
                    out = '远端脚本已执行（deploy 后台进程占用 SSH 管道，故按短超时提前返回）'
                _, log = kr260("deploy_log", "10")
                return self._reply({'ok': True, 'action': action,
                                    'output': (out + '\n启动已确认：状态查询显示 deploy 正在运行\n' + log).strip()}, 200)
            rc, out = kr260(action)
            if rc == 0 and action == 'prepare':
                check_rc, check = kr260('status')
                expected = {'can1': LEFT_CAN_IF, 'can2': RIGHT_CAN_IF}
                if check_rc != 0 or not all(re.search(rf'{alias}:\s*{port}\s+UP\b', check)
                                            for alias, port in expected.items()):
                    return self._reply({'ok': False, 'error': 'CAN 连接未全部成功，已终止，请检查左右臂接口', 'output': out+'\n'+check}, 409)
            if action in ("deploy_start", "deploy_stop"):
                _, log = kr260("deploy_log", "10")
                out = (out + "\n" + log).strip()
            if action == 'deploy_stop':
                Handler._status_cache = (0.0, None)
            return self._reply(dict(ok=rc == 0, action=action, output=out), 200 if rc == 0 else 500)
        if self.path == "/api/control":
            action = data.get("action", "")
            result, code = SENDER.call(action, data)
            return self._reply(result, code)
        if self.path == "/api/base_cmd":
            # 底盘遥控：网页摇杆 → UDP 转发 KR260:54322（chassis_relay.py 写 can0）
            # 限速/看门狗/解锁均在 KR260 侧执行，本端只做透明转发
            try:
                return self._reply(send_base(data))
            except Exception as e:  # noqa: BLE001
                return self._reply(dict(ok=False, error=str(e)), 400)
        if self.path == "/api/base_sub":
            # 网页切换底盘子模式（与 VR 端 Y 键循环同一份 SENDER.base_sub）
            try:
                sub = SENDER.set_base_sub(str(data.get("sub", "")))
                return self._reply(dict(ok=True, sub=sub, sub_text=BASE_SUB_TEXT[sub]))
            except ValueError as e:
                return self._reply(dict(ok=False, error=str(e)), 400)
        self._reply({"error": "not found"}, 404)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8092), Handler).serve_forever()


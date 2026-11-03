#!/usr/bin/env python3
"""Codec for the original 78-byte whole_body_msg UDP wire format.

This is a test-only companion to the C++ WholeBodySender/Receiver. It does
not access ROS, CAN, GPIO or motor controllers.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

FRAME_BYTES = 78
HEADER = b"\xfb\xfb"
QUAT_MAX = 0.70710678118
ACK_PREFIX = b"VRACK1"


class FrameError(ValueError):
    """Invalid VR datagram."""


def crc16_kermit(data: bytes, bit_count: int | None = None) -> int:
    """CRC-16/KERMIT. bit_count mirrors the C++ CalculateBits API."""
    if bit_count is None:
        bit_count = len(data) * 8
    if bit_count < 0 or bit_count > len(data) * 8:
        raise ValueError("invalid bit count")
    crc = 0
    whole_bytes, remaining_bits = divmod(bit_count, 8)
    for byte in data[:whole_bytes]:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x8408 if crc & 1 else 0)
    if remaining_bits:
        crc ^= data[whole_bytes]
        for _ in range(remaining_bits):
            crc = (crc >> 1) ^ (0x8408 if crc & 1 else 0)
    return crc


def _encode_float(value: float, bits: int, max_abs: float) -> int:
    if not math.isfinite(value) or not -max_abs <= value <= max_abs:
        raise ValueError(f"value {value} outside +/-{max_abs}")
    return int((value + max_abs) / (2.0 * max_abs) * ((1 << bits) - 1) + 0.5)


def _decode_float(value: int, bits: int, max_abs: float) -> float:
    return (value & ((1 << bits) - 1)) / ((1 << bits) - 1) * (2.0 * max_abs) - max_abs


def _encode_3d(xyz: tuple[float, float, float], max_abs: float) -> int:
    x, y, z = (_encode_float(v, 10, max_abs) for v in xyz)
    return (x << 20) | (y << 10) | z


def _decode_3d(value: int, max_abs: float) -> tuple[float, float, float]:
    return tuple(_decode_float(value >> shift, 10, max_abs) for shift in (20, 10, 0))


def _encode_quat(quat: tuple[float, float, float, float]) -> int:
    if len(quat) != 4 or not all(math.isfinite(v) for v in quat):
        raise ValueError("quaternion must contain four finite values")
    norm = math.sqrt(sum(v * v for v in quat))
    if abs(norm - 1.0) > 1e-4:
        raise ValueError("quaternion must be normalized")
    index = max(range(4), key=lambda i: abs(quat[i]))
    sign = 1.0 if quat[index] >= 0 else -1.0
    rest = tuple(sign * quat[i] for i in range(4) if i != index)
    return (index << 30) | _encode_3d(rest, QUAT_MAX)


def _decode_quat(value: int) -> tuple[float, float, float, float]:
    index = value >> 30
    rest = _decode_3d(value, QUAT_MAX)
    remaining = 1.0 - sum(v * v for v in rest)
    if remaining < -1e-5:
        raise FrameError("quaternion norm is invalid")
    largest = math.sqrt(max(0.0, remaining))
    output = []
    iterator = iter(rest)
    for i in range(4):
        output.append(largest if i == index else next(iterator))
    return tuple(output)


@dataclass(frozen=True)
class VrFrame:
    mask: int
    cnt: int
    time_ns: int
    base_pos: tuple[float, float, float]
    left_hand_pos: tuple[float, float, float]
    right_hand_pos: tuple[float, float, float]
    base_quat: tuple[float, float, float, float]
    left_hand_quat: tuple[float, float, float, float]
    right_hand_quat: tuple[float, float, float, float]
    base_lin_vel: tuple[float, float, float]
    base_ang_vel: tuple[float, float, float]
    left_hand_lin_vel: tuple[float, float, float]
    right_hand_lin_vel: tuple[float, float, float]
    left_hand_ang_vel: tuple[float, float, float]
    right_hand_ang_vel: tuple[float, float, float]
    left_grip: float
    right_grip: float


def make_sim_frame(cnt: int, time_ns: int, hand_x: float = 0.0) -> VrFrame:
    """Return a disabled-control test frame; no caller can set mask here."""
    zero = (0.0, 0.0, 0.0)
    identity = (0.0, 0.0, 0.0, 1.0)
    return VrFrame(
        mask=0, cnt=cnt, time_ns=time_ns, base_pos=zero,
        left_hand_pos=(hand_x, 0.0, 0.0),
        right_hand_pos=(-hand_x, 0.0, 0.0),
        base_quat=identity, left_hand_quat=identity, right_hand_quat=identity,
        base_lin_vel=zero, base_ang_vel=zero,
        left_hand_lin_vel=zero, right_hand_lin_vel=zero,
        left_hand_ang_vel=zero, right_hand_ang_vel=zero,
        left_grip=0.0, right_grip=0.0,
    )


def encode_sim_frame(frame: VrFrame) -> bytes:
    """Encode a test frame, refusing any nonzero control mask."""
    if frame.mask != 0:
        raise ValueError("simulation sender requires mask=0")
    if not 0 <= frame.cnt <= 0xFFFFFFFF or not 0 <= frame.time_ns <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("counter or timestamp out of range")
    packet = bytearray(FRAME_BYTES)
    packet[:2] = HEADER
    struct.pack_into("<HIQ", packet, 2, frame.mask, frame.cnt, frame.time_ns)
    struct.pack_into("<3f", packet, 16, *frame.base_pos)
    for offset, vector, limit in (
        (28, frame.left_hand_pos, 2.0),
        (32, frame.right_hand_pos, 2.0),
        (48, frame.base_lin_vel, 3.0),
        (52, frame.base_ang_vel, 3.14),
        (56, frame.left_hand_lin_vel, 5.0),
        (60, frame.right_hand_lin_vel, 5.0),
        (64, frame.left_hand_ang_vel, 6.28),
        (68, frame.right_hand_ang_vel, 6.28),
    ):
        struct.pack_into("<I", packet, offset, _encode_3d(vector, limit))
    for offset, quat in (
        (36, frame.base_quat),
        (40, frame.left_hand_quat),
        (44, frame.right_hand_quat),
    ):
        struct.pack_into("<I", packet, offset, _encode_quat(quat))
    grips = (_encode_float(frame.left_grip, 16, 1.0) << 16) | _encode_float(frame.right_grip, 16, 1.0)
    struct.pack_into("<I", packet, 72, grips)
    # Original C++ uses CalculateBits(..., 76): 76 BITS, not 76 bytes.
    struct.pack_into("<H", packet, 76, crc16_kermit(packet, 76))
    return bytes(packet)


def decode_frame(packet: bytes) -> VrFrame:
    """Strictly validate and decode one original-format datagram."""
    if len(packet) != FRAME_BYTES:
        raise FrameError(f"length={len(packet)}, expected={FRAME_BYTES}")
    if packet[:2] != HEADER:
        raise FrameError("bad header")
    expected = crc16_kermit(packet, 76)
    received = struct.unpack_from("<H", packet, 76)[0]
    if expected != received:
        raise FrameError(f"bad CRC: got 0x{received:04x}, expected 0x{expected:04x}")
    mask, cnt, time_ns = struct.unpack_from("<HIQ", packet, 2)

    def u32(offset: int) -> int:
        return struct.unpack_from("<I", packet, offset)[0]

    grips = u32(72)
    base_pos = struct.unpack_from("<3f", packet, 16)
    if not all(math.isfinite(v) for v in base_pos):
        raise FrameError("non-finite base position")
    return VrFrame(
        mask=mask, cnt=cnt, time_ns=time_ns, base_pos=base_pos,
        left_hand_pos=_decode_3d(u32(28), 2.0),
        right_hand_pos=_decode_3d(u32(32), 2.0),
        base_quat=_decode_quat(u32(36)),
        left_hand_quat=_decode_quat(u32(40)),
        right_hand_quat=_decode_quat(u32(44)),
        base_lin_vel=_decode_3d(u32(48), 3.0),
        base_ang_vel=_decode_3d(u32(52), 3.14),
        left_hand_lin_vel=_decode_3d(u32(56), 5.0),
        right_hand_lin_vel=_decode_3d(u32(60), 5.0),
        left_hand_ang_vel=_decode_3d(u32(64), 6.28),
        right_hand_ang_vel=_decode_3d(u32(68), 6.28),
        left_grip=_decode_float(grips >> 16, 16, 1.0),
        right_grip=_decode_float(grips, 16, 1.0),
    )


def make_ack(cnt: int) -> bytes:
    return ACK_PREFIX + struct.pack("<I", cnt)


def parse_ack(packet: bytes) -> int | None:
    if len(packet) != len(ACK_PREFIX) + 4 or not packet.startswith(ACK_PREFIX):
        return None
    return struct.unpack_from("<I", packet, len(ACK_PREFIX))[0]

"""Pure, read-only joystick decoding and motion preview. No robot transport.

key11[5]/[6] are treated as left/right pending confirmation by the current APK
owner. Historical captures contain two vec2 values, but do not label each hand.
"""
import math

DEADZONE = 0.1
MAX_LINEAR = 0.3
MAX_ANGULAR = 0.5


def decode_stick(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   or not -1 <= v <= 1 for v in value)):
        return None
    return tuple(float(v) for v in value)


def radial_stick(value):
    x, y = value
    radius = math.hypot(x, y)
    if radius <= DEADZONE:
        return 0.0, 0.0
    scale = (min(radius, 1.0) - DEADZONE) / (1.0 - DEADZONE) / radius
    return x * scale, y * scale


def axis(value):
    if abs(value) <= DEADZONE:
        return 0.0
    return math.copysign((abs(value) - DEADZONE) / (1 - DEADZONE), value)


def preview(left, right, *, fresh, input_state):
    """FLU command convention: vx forward, vy left, wz counterclockwise.

    Assumed input convention: x right, y forward. Does not infer any enable
    from key11[7], grip state, input_state bit3 or the presence of a packet.
    """
    valid = left is not None and right is not None
    tracked = (type(input_state) is int and input_state & 0x17 == 0x17)
    usable = bool(fresh and valid and tracked)
    vx = vy = wz = 0.0
    if usable:
        x, y = radial_stick(left)
        vx, vy = y * MAX_LINEAR, -x * MAX_LINEAR
        wz = -axis(right[0]) * MAX_ANGULAR
    reason = ('等待新鲜 VR 数据' if not fresh else
              '摇杆字段缺失或非法' if not valid else
              '头显/双手跟踪或前台状态无效' if not tracked else
              '仅预览；左右字段及轴方向待 APK 确认')
    simultaneous = bool((vx or vy) and wz)
    return {
        'left': list(left) if left is not None else None,
        'right': list(right) if right is not None else None,
        'fresh': bool(fresh), 'valid': valid, 'usable': usable,
        'mapping_confirmed': False, 'execution_enabled': False,
        'reason': reason, 'deadzone': DEADZONE,
        'intent': {'vx': vx, 'vy': vy, 'wz': wz},
        # Reflect current chassis-relay behavior, without sending anything.
        'relay_preview': {'vx': vx, 'vy': vy, 'wz': 0.0 if simultaneous else wz},
        'simultaneous': simultaneous,
    }

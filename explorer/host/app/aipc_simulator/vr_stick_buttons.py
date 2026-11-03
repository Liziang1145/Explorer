"""左右摇杆按下 L3/R3（OPERATOR_STATE 的 CBOR key15）：校验与只读快照。

协议（VR 控制传输增补：左右摇杆按下 revision 1）：
    15: {0: revision=1, 1: valid_mask, 2: pressed_mask}
    bit0 = 左摇杆按下（L3）   bit1 = 右摇杆按下（R3）

校验规则（与 arm_buttons 同一套判据风格）：
  * revision 只认 1
  * valid_mask / pressed_mask 必须是 0..3 的整数（高位必须为 0）
  * pressed_mask 必须是 valid_mask 的子集
  * 字段缺失或不合规一律返回 None —— 表示"本帧读不到摇杆按下"，
    **不能推断为松开**（调用方按该侧无此信息处理，夹爪回退到扳机模拟量）。

与 A/B/X/Y（key13）不同：L3/R3 在本系统里是"持续按住"语义（按住闭合夹爪），
不是"按一下"边沿事件，因此不提供 Latch，调用方直接读瞬时 pressed。
"""

BIT_NAME = {0: 'L3', 1: 'R3'}
_KEYS = {0, 1, 2}
REVISION = 1


def parse(body):
    """从 OPERATOR_STATE 顶层 CBOR map 取 key15。

    合规时返回 dict(revision/valid/pressed)；缺失或不合规返回 None，不抛异常。
    """
    if not isinstance(body, dict) or 15 not in body:
        return None
    v = body[15]
    if not isinstance(v, dict) or set(v) - _KEYS:
        return None
    if type(v.get(0)) is not int or v[0] != REVISION:
        return None
    for key in (1, 2):
        if type(v.get(key)) is not int or not 0 <= v[key] <= 3:
            return None
    if v[2] & ~v[1]:                       # pressed 不是 valid 的子集
        return None
    return {'revision': REVISION, 'valid': v[1], 'pressed': v[2]}


def pressed(stick, bit):
    """该 bit 当前是否按住。stick 为 None 或该 bit 本帧不可读时返回 False
    （调用方按"无此信息"回退，不推断为松开——持续按住语义下这样最安全）。"""
    if not stick:
        return False
    return bool((stick['valid'] >> bit) & 1 and (stick['pressed'] >> bit) & 1)


def names(mask):
    """把 2 位掩码翻成 ['L3','R3']，便于日志与界面显示。"""
    if not isinstance(mask, int):
        return []
    return [name for bit, name in BIT_NAME.items() if (mask >> bit) & 1]


def summary(stick):
    """给 /api/vr_telemetry 与页面用的紧凑结构（None 安全）。"""
    if not stick:
        return {'available': False, 'valid': 0, 'pressed': 0,
                'valid_names': [], 'pressed_names': [], 'bits': {}}
    return {'available': True,
            'revision': stick['revision'],
            'valid': stick['valid'], 'pressed': stick['pressed'],
            'valid_names': names(stick['valid']),
            'pressed_names': names(stick['pressed']),
            'bits': {name: {'valid': bool((stick['valid'] >> bit) & 1),
                            'pressed': bool((stick['pressed'] >> bit) & 1)}
                     for bit, name in BIT_NAME.items()}}

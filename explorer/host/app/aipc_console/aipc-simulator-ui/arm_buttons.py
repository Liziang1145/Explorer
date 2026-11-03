"""A/B/X/Y（OPERATOR_STATE 的 CBOR key13）：校验与"按一下"边沿锁存。

位映射已由 2026-10-22 实采确认（采集页 A/B/X/Y 四条样本，valid 全程 15）：
    bit0 = A（右手柄）  bit1 = B（右手柄）  bit2 = X（左手柄）  bit3 = Y（左手柄）
校验规则与 AIPC 直连网关的 tlz2/face_buttons.py 保持一致，避免两边判据分叉。

协议硬要求（来自 VR_DIRECT_AIPC_HANDOFF_20261022 §5）：
  * revision 只认 1
  * pressed_mask 必须是 valid_mask 的子集，高位必须为 0（即 0..15）
  * touched 必须与 touched_valid 同时出现，且是它的子集
  * valid=0 表示"本帧读不到按键"，**不能推断为松开**
  * 单帧快照不是可靠事件队列，短于采样周期的点击可能漏采
"""

BIT_NAME = {0: 'A', 1: 'B', 2: 'X', 3: 'Y'}
_KEYS = {0, 1, 2, 3, 4}
REVISION = 1


def parse(body):
    """从 OPERATOR_STATE 顶层 CBOR map 取 key13。

    合规时返回 dict(revision/valid/pressed/touched/touched_valid)；
    缺失或任何不合规都返回 None（调用方按"本帧无按键信息"处理），不抛异常。
    """
    if not isinstance(body, dict) or 13 not in body:
        return None
    v = body[13]
    if not isinstance(v, dict) or set(v) - _KEYS:
        return None
    if type(v.get(0)) is not int or v[0] != REVISION:
        return None
    for key in (1, 2):
        if type(v.get(key)) is not int or not 0 <= v[key] <= 15:
            return None
    if v[2] & ~v[1]:                       # pressed 不是 valid 的子集
        return None
    if (3 in v) != (4 in v):               # touched 与 touched_valid 必须成对
        return None
    out = {'revision': REVISION, 'valid': v[1], 'pressed': v[2],
           'touched': None, 'touched_valid': None}
    if 3 in v:
        for key in (3, 4):
            if type(v[key]) is not int or not 0 <= v[key] <= 15:
                return None
        if v[3] & ~v[4]:
            return None
        out['touched'] = v[3]
        out['touched_valid'] = v[4]
    return out


def names(mask):
    """把 4 位掩码翻成 ['A','B',...]，便于日志与界面显示。"""
    if not isinstance(mask, int):
        return []
    return [name for bit, name in BIT_NAME.items() if (mask >> bit) & 1]


def summary(buttons):
    """给 /api/vr_buttons 与页面用的紧凑结构（None 安全）。"""
    if not buttons:
        return {'available': False, 'valid': 0, 'pressed': 0,
                'valid_names': [], 'pressed_names': [], 'bits': {}}
    return {'available': True,
            'valid': buttons['valid'], 'pressed': buttons['pressed'],
            'valid_names': names(buttons['valid']),
            'pressed_names': names(buttons['pressed']),
            'bits': {name: {'valid': bool((buttons['valid'] >> bit) & 1),
                            'pressed': bool((buttons['pressed'] >> bit) & 1)}
                     for bit, name in BIT_NAME.items()}}


class Latch:
    """在 50Hz 快照上实现"按一下只触发一次"。

    - 只在 valid 位为 1 的键上判边沿；
    - 上升沿触发一次，之后必须看到该键 valid=1 且 pressed=0 才重新武装；
    - 该键 valid=0 时**保持**已按下状态不动（文档：不能推断按键释放），
      这样"按着的时候跟踪丢了又回来"不会被当成一次新的按下。
    """

    def __init__(self):
        self._down = 0            # 已触发且尚未见到释放的位
        self._await_release = 0   # 源数据失效后，这些位必须先看到"可读且未按下"才重新武装

    @property
    def down(self):
        return self._down

    def disarm(self):
        """源数据失效（过期/解析失败）时调用（C04）：清掉按下态，并要求先看到松键。

        过期的那段时间里用户可能一直按着键；若直接重新武装，
        恢复后的第一帧就会被当成一次新的"按一下"。强制先见到松键才符合直觉。
        """
        self._down = 0
        self._await_release = 0xF

    def update(self, buttons):
        """返回本次新触发的位集合 set[int]。buttons 为 None 时不改变内部状态。"""
        if not buttons:
            return set()
        valid, pressed = buttons['valid'], buttons['pressed']
        fired = set()
        for bit in range(4):
            if not (valid >> bit) & 1:
                continue                    # 本帧不可读：不判边沿、不改状态
            was_down = bool((self._down >> bit) & 1)     # 本帧处理前的按下态
            if (pressed >> bit) & 1:
                self._down |= 1 << bit
                if (self._await_release >> bit) & 1:
                    continue                # 恢复后仍按住：等松开，不算新的一次按下
                if not was_down:
                    fired.add(bit)
            else:
                self._down &= ~(1 << bit)
                self._await_release &= ~(1 << bit)       # 见到松键 → 该位重新武装
        return fired

"""VR 摇杆 → 底盘速度指令。只做数值决策，不发网络、不碰硬件。

2026-10-22 定下的三条约束：
  1. **平移与转向互斥，平移优先**——与 KR260 侧 `chassis_relay.py` 的档位互斥一致
     （vx/vy 非零时 relay 会强制 wz=0，档位 8 平移 / 6 自旋）。这里提前把 wz 清零，
     让页面预览与实际下发口径一致，不出现"预览有转向、实际没转向"。
  2. **速度上限 ±0.3 m/s、转向 ±0.5 rad/s**（沿用网页侧同类限幅；relay 侧虽然允许
     ±0.8，但 VR 驱动先用保守值）。
  3. **侧键按住才动**（任一侧），松开立即零速。

实现上直接复用 `vr_sticks.preview()` 的意图计算，保证"只读预览"与"实际下发"
永远是同一套死区/缩放/符号，不会各算一份而漂移。
"""
from vr_sticks import preview, axis

MAX_LINEAR = 0.3      # m/s
MAX_ANGULAR = 0.5     # rad/s


def command(left, right, *, held, fresh, input_state, rc=False):
    """返回 dict(vx, vy, wz, active, reason)。

    left/right   : 二维摇杆元组或 None
    held         : 任一（左或右）侧键是否按住
    fresh        : VR 数据是否新鲜
    input_state  : OPERATOR_STATE 的 input_state 位
    rc           : RC 遥控车子模式（2026-10-24）：左摇杆 Y=油门（前+/后-），
                   右摇杆 X=转向（逆+顺-），vx 与 wz 允许同时非零。
                   relay 侧手册标准实现：档位 6（4T4D）同帧 vx+wz，固件按双阿克曼
                   自算四轮转角，行进中即可转向，静止纯 wz = 原地自旋。
                   （2026-10-25 修正：此前"档位 6 忽略 wz"系 wz 单位 bug——
                   应为 0.01°/s 误作 0.01 rad/s，小 57.3 倍；转向帧方案已弃用）。
    """
    zero = dict(vx=0.0, vy=0.0, wz=0.0, active=False)

    if not fresh:
        return dict(zero, reason='等待新鲜 VR 数据')
    if not held:
        return dict(zero, reason='侧键未按住（松开即零速）')

    p = preview(left, right, fresh=fresh, input_state=input_state)
    if not p['usable']:
        return dict(zero, reason=p['reason'])

    if rc:
        vx = max(-MAX_LINEAR, min(MAX_LINEAR, axis(left[1]) * MAX_LINEAR))
        wz = max(-MAX_ANGULAR, min(MAX_ANGULAR, -axis(right[0]) * MAX_ANGULAR))
        active = bool(vx or wz)
        reason = ('RC ' + ('前进' if vx > 0 else '后退' if vx < 0 else '原地')
                  + ('+左转' if wz > 0 else '+右转' if wz < 0 else '')
                  + ('' if active else '（中位）'))
        return dict(vx=round(vx, 4), vy=0.0, wz=round(wz, 4),
                    active=active, reason=reason)

    # relay_preview 已按"平移优先"把同时转向清零
    r = p['relay_preview']
    vx = max(-MAX_LINEAR, min(MAX_LINEAR, float(r['vx'])))
    vy = max(-MAX_LINEAR, min(MAX_LINEAR, float(r['vy'])))
    wz = max(-MAX_ANGULAR, min(MAX_ANGULAR, float(r['wz'])))
    if vx or vy:
        wz = 0.0            # 双保险：即使上游改了口径也保证互斥
    active = bool(vx or vy or wz)
    reason = ('平移' if (vx or vy) else '转向' if wz else '摇杆在中位') + \
             ('（转向被平移优先抑制）' if p.get('simultaneous') else '')
    return dict(vx=round(vx, 4), vy=round(vy, 4), wz=round(wz, 4),
                active=active, reason=reason)

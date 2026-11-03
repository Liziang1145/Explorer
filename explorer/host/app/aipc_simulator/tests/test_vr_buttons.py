"""A/B/X/Y、模式、底盘驱动、支架几何预检的离线回归。

全部不联网、不碰设备：VR 在 test_console_safety.SafetyTests.setUp 里已被 mock。
"""
import math
import sys
import pathlib
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import arm_buttons
import base_drive
import arm_geometry
from test_console_safety import SafetyTests

D = math.radians
QL = [D(v) for v in (-40, 92, -49, -63, -59, 40)]          # 右臂起始位姿
QL_LEFT = [D(v) for v in (30.7143, 86.2514, -36.6947, 30.029, -48.0366, -25.4887)]  # 左臂起始位姿（2026-10-25 标定后镜像重算，余量与旧值同为 6.94cm）
ZERO = [0.0, 0.05, -0.05, 0.0, 0.0, 0.0]


class FaceButtonParseTests(unittest.TestCase):
    def test_valid_bitmap(self):
        b = arm_buttons.parse({13: {0: 1, 1: 15, 2: 9}})
        self.assertEqual(b['valid'], 15)
        self.assertEqual(b['pressed'], 9)
        self.assertEqual(arm_buttons.names(b['pressed']), ['A', 'Y'])

    def test_missing_key13_is_none_not_error(self):
        self.assertIsNone(arm_buttons.parse({}))          # 旧 APK 没有该功能
        self.assertIsNone(arm_buttons.parse(None))

    def test_rejects_malformed(self):
        bad = [
            {13: {0: 2, 1: 15, 2: 0}},          # revision 不是 1
            {13: {0: 1, 1: 15, 2: 16}},         # 高位越界
            {13: {0: 1, 1: 0, 2: 1}},           # pressed 不是 valid 子集
            {13: {0: 1, 1: 15, 2: 0, 3: 1}},    # touched 缺 touched_valid
            {13: {0: 1, 1: 15, 2: 0, 9: 1}},    # 未知键
            {13: 'x'},
        ]
        for b in bad:
            self.assertIsNone(arm_buttons.parse(b), b)

    def test_summary_is_none_safe(self):
        s = arm_buttons.summary(None)
        self.assertFalse(s['available'])
        self.assertEqual(s['valid_names'], [])


class LatchTests(unittest.TestCase):
    def test_fires_once_per_press(self):
        L = arm_buttons.Latch()
        for v, p, expect in [(15, 0, set()), (15, 1, {0}), (15, 1, set()),
                             (15, 0, set()), (15, 1, {0})]:
            self.assertEqual(L.update({'valid': v, 'pressed': p}), expect)

    def test_valid_zero_does_not_release(self):
        L = arm_buttons.Latch()
        L.update({'valid': 15, 'pressed': 1})
        self.assertEqual(L.update({'valid': 0, 'pressed': 1}), set())
        # valid 恢复后仍是"按着"，不能当成新的一次按下
        self.assertEqual(L.update({'valid': 15, 'pressed': 1}), set())
        # 真正松开后才重新武装
        L.update({'valid': 15, 'pressed': 0})
        self.assertEqual(L.update({'valid': 15, 'pressed': 1}), {0})

    def test_all_four_bits(self):
        L = arm_buttons.Latch()
        self.assertEqual(L.update({'valid': 15, 'pressed': 0b1111}), {0, 1, 2, 3})

    def test_none_keeps_state(self):
        L = arm_buttons.Latch()
        self.assertEqual(L.update(None), set())
        L.update({'valid': 15, 'pressed': 1})
        self.assertEqual(L.update(None), set())
        self.assertEqual(L.update({'valid': 15, 'pressed': 1}), set())


class BaseDriveTests(unittest.TestCase):
    def cmd(self, **kw):
        kw.setdefault('fresh', True)
        kw.setdefault('input_state', 0x17)
        kw.setdefault('held', True)
        return base_drive.command(kw.pop('left', None), kw.pop('right', None), **kw)

    def test_translation_priority_kills_yaw(self):
        r = self.cmd(left=(1, 1), right=(1, 0))
        self.assertNotEqual((r['vx'], r['vy']), (0.0, 0.0))
        self.assertEqual(r['wz'], 0.0)          # 平移优先

    def test_yaw_only_when_not_translating(self):
        r = self.cmd(left=(0, 0), right=(1, 0))
        self.assertEqual((r['vx'], r['vy']), (0.0, 0.0))
        self.assertNotEqual(r['wz'], 0.0)

    def test_requires_side_grip(self):
        r = self.cmd(left=(0, 1), held=False)
        self.assertFalse(r['active'])
        self.assertEqual((r['vx'], r['vy'], r['wz']), (0.0, 0.0, 0.0))

    def test_requires_fresh_data(self):
        r = self.cmd(left=(0, 1), fresh=False)
        self.assertFalse(r['active'])

    def test_requires_tracking(self):
        r = self.cmd(left=(0, 1), input_state=0x11)   # 双手跟踪丢失
        self.assertFalse(r['active'])

    def test_clamped_to_limits(self):
        r = self.cmd(left=(1, 1), right=(1, 0))
        self.assertLessEqual(abs(r['vx']), base_drive.MAX_LINEAR + 1e-9)
        self.assertLessEqual(abs(r['vy']), base_drive.MAX_LINEAR + 1e-9)
        r2 = self.cmd(left=(0, 0), right=(1, 0))
        self.assertLessEqual(abs(r2['wz']), base_drive.MAX_ANGULAR + 1e-9)


class GeometryTests(unittest.TestCase):
    def test_fk_reference_points(self):
        # 两个已知基准：q=0 与 水平构型(RIGHT QLEVEL) 的法兰位置
        p = [v * 100 for v in arm_geometry.fk_chain([0.0] * 6)[-1]]
        self.assertAlmostEqual(p[0], 0.0, places=2)
        self.assertAlmostEqual(p[1], 5.613, places=2)
        self.assertAlmostEqual(p[2], 21.328, places=2)
        p = [v * 100 for v in arm_geometry.fk_chain(QL)[-1]]
        self.assertAlmostEqual(p[0], 15.136, places=2)
        self.assertAlmostEqual(p[1], 28.851, places=2)
        self.assertAlmostEqual(p[2], 26.586, places=2)

    def test_canonical_paths_pass(self):
        # 2026-10-23：支架障碍由"⌀40 圆杆(r=20mm)"更正为"30×4mm 刀片"，
        # 按外接圆 r=15.13mm 建模（arm_geometry.ROD_R_CM=1.513），余量随之变大。
        for arm, a, b, expect in (('right', QL, ZERO, 6.51), ('left', QL_LEFT, ZERO, 6.94),
                                  ('right', ZERO, QL, 6.51), ('left', ZERO, QL_LEFT, 6.94)):
            r = arm_geometry.check_entry(a, b, arm)
            self.assertTrue(r['ok'], (arm, r))
            self.assertAlmostEqual(r['margin_cm'], expect, delta=0.3, msg=(arm, a is QL))

    def test_folding_at_start_yaw_is_rejected(self):
        # 这是 2026-10-22 之前的错误顺序：J1 冻结在起始角收拢 J2–J6
        for arm, start in (('right', QL), ('left', QL_LEFT)):
            mid = [start[0], *ZERO[1:]]
            r = arm_geometry.check_path(start, mid, arm)
            self.assertFalse(r['ok'], (arm, r))
            self.assertLess(r['margin_cm'], 0)

    def test_extended_adjust_not_phased_through_j1_zero(self):
        tweak = [D(-40), D(80), D(-44), D(-58), D(-54), D(36)]
        from arm_entry import plan_phases
        names = [n for n, _ in plan_phases(QL, tweak)]
        self.assertNotIn('j1_to_zero', names)
        self.assertTrue(arm_geometry.check_entry(QL, tweak, 'right')['ok'])

    def test_precheck_is_fast_enough(self):
        import time
        t = time.monotonic()
        arm_geometry.check_entry(QL, ZERO, 'right')
        self.assertLess(time.monotonic() - t, 0.5)


class ModeWiringTests(SafetyTests):
    def _fire(self, pressed_mask, fresh=True):
        """喂一帧"四键都有效"的 VR 快照给按键处理。

        2026-10-23（C04）起，按键必须与"源数据新鲜"绑定：快照不带 fresh=True 时
        后端一律不触发动作，所以这里显式给出 fresh（false 用于验证过期场景）。
        """
        app, s = self.app, self.app.SENDER
        with patch.object(app.VR, 'buttons',
                          return_value={'valid': 15, 'pressed': pressed_mask, 'fresh': fresh}):
            with s.lock:
                s._handle_buttons(0.0)

    def test_stale_buttons_do_not_fire(self):
        """C04：源数据过期（fresh=False）时，按下的键不得触发任何动作。"""
        app, s = self.app, self.app.SENDER
        s.mode = 'arms'
        with patch.object(s, '_request_preset') as preset:
            with patch.object(s, '_set_mode') as set_mode:
                for _ in range(5):
                    self._fire(4, fresh=False)      # X 按住但数据过期
                    self._fire(8, fresh=False)      # Y 按住但数据过期
                preset.assert_not_called()
                set_mode.assert_not_called()
        self.assertEqual(s.mode, 'arms')

    def test_needs_release_after_stale_before_firing_again(self):
        """C04：恢复后仍按着同一键，不得被当成新的一次按下。"""
        app, s = self.app, self.app.SENDER
        s.mode = 'arms'
        with patch.object(s, '_request_preset') as preset:
            self._fire(4)                    # 正常触发一次（X）
            preset.assert_called_once_with('left')
            self._fire(4, fresh=False)       # 数据过期，锁存器被 disarm
            self._fire(4)                    # 恢复但仍按着 → 不应再次触发
            preset.assert_called_once_with('left')
            self._fire(0)                    # 终于看到松键
            self._fire(4)                    # 再按 → 允许触发
            self.assertEqual(preset.call_count, 2)

    def test_y_switches_to_base_and_b_back(self):
        app, s = self.app, self.app.SENDER
        s.mode = 'arms'
        self._fire(8)                       # Y = bit3
        self.assertEqual(s.mode, 'base')
        s.btn_latch = arm_buttons.Latch()   # 松开
        self._fire(0)
        self._fire(2)                       # B = bit1：按下时先计时
        self.assertEqual(s.mode, 'base')
        self._fire(0)                       # 短按松开才切回双臂
        self.assertEqual(s.mode, 'arms')

    def test_x_and_a_request_preset_for_correct_arm(self):
        app, s = self.app, self.app.SENDER
        with patch.object(s, '_request_preset') as preset:
            self._fire(4)                   # X = bit2 → 左臂
            preset.assert_called_with('left')
            s.btn_latch = arm_buttons.Latch()
            self._fire(0)
            self._fire(1)                   # A = bit0 → 右臂
            preset.assert_called_with('right')

    def test_press_held_does_not_repeat(self):
        app, s = self.app, self.app.SENDER
        with patch.object(s, '_request_preset') as preset:
            for _ in range(5):              # 按住不放 5 帧
                self._fire(4)
            preset.assert_called_once_with('left')

    def test_latched_stop_ignores_buttons(self):
        app, s = self.app, self.app.SENDER
        app.SAFETY.stop()
        with patch.object(s, '_request_preset') as preset, \
             patch.object(s, '_set_mode') as setmode:
            self._fire(15)
            preset.assert_not_called()
            setmode.assert_not_called()
        self.assertEqual(s.mode, 'arms')

    def test_status_exposes_mode_and_buttons(self):
        app, s = self.app, self.app.SENDER
        st = s.status()
        self.assertIn('mode', st)
        self.assertIn('vr_buttons', st)
        self.assertIn('base', st)
        self.assertEqual(st['mode'], 'arms')

"""B 长按 VR 精细倍率：全部离线，不连接机械臂。"""
import math
import pathlib
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_console_safety import SafetyTests
from test_smooth_follow_20261028 import bare_sender


class PrecisionButtonTests(SafetyTests):
    def frame(self, pressed, now):
        with patch.object(self.app.VR, 'buttons',
                          return_value={'valid': 15, 'pressed': pressed, 'fresh': True}):
            with self.app.SENDER.lock:
                self.app.SENDER._handle_buttons(now)

    def test_short_b_switches_only_on_release(self):
        sender = self.app.SENDER
        sender.mode = 'base'
        with patch.object(sender, '_set_mode') as set_mode:
            self.frame(2, 0.0)
            set_mode.assert_not_called()
            self.frame(2, 1.99)
            set_mode.assert_not_called()
            self.frame(0, 1.995)
            set_mode.assert_called_once_with('arms')

    def test_long_b_cycles_once_and_never_switches_mode(self):
        sender = self.app.SENDER
        with patch.object(sender, '_set_mode') as set_mode:
            self.frame(2, 0.0)
            self.frame(2, 1.99)
            self.assertEqual(sender.vr_motion_scale, 1.0)
            self.frame(2, 2.0)
            self.assertEqual(sender.vr_motion_scale, 0.5)
            self.frame(2, 4.0)
            self.assertEqual(sender.vr_motion_scale, 0.5)
            self.frame(0, 4.1)
            set_mode.assert_not_called()
            self.frame(2, 5.0)
            self.frame(2, 7.0)
            self.assertEqual(sender.vr_motion_scale, 0.25)
            self.frame(0, 7.1)
            self.frame(2, 8.0)
            self.frame(2, 10.0)
            self.assertEqual(sender.vr_motion_scale, 1.0)

    def test_long_b_refused_while_clutch_or_task_active(self):
        sender = self.app.SENDER
        for condition in ('clutch', 'task'):
            sender.vr_motion_scale = 1.0
            sender._b_down_since = None
            sender._b_long_fired = False
            sender.vr_pressing = condition == 'clutch'
            sender._vr_route_running = condition == 'task'
            self.frame(2, 0.0)
            self.frame(2, 2.1)
            self.assertEqual(sender.vr_motion_scale, 1.0)
            self.frame(0, 2.2)
            sender.vr_pressing = False
            sender._vr_route_running = False

    def test_stale_b_cancels_long_press(self):
        sender = self.app.SENDER
        self.frame(2, 0.0)
        with patch.object(self.app.VR, 'buttons',
                          return_value={'valid': 0, 'pressed': 0, 'fresh': False}):
            with sender.lock:
                sender._handle_buttons(1.0)
        self.frame(2, 3.0)                 # 恢复后仍按着：重新计时，不沿用旧 1 秒
        self.assertEqual(sender.vr_motion_scale, 1.0)
        self.assertEqual(sender._b_down_since, 3.0)
        self.frame(2, 4.99)
        self.assertEqual(sender.vr_motion_scale, 1.0)
        self.frame(2, 5.0)
        self.assertEqual(sender.vr_motion_scale, 0.5)

    def test_status_and_telemetry_expose_scale(self):
        sender = self.app.SENDER
        self.assertEqual(sender.status()['vr_motion_scale'], 1.0)
        self.assertEqual(sender.status()['vr_motion_scale_text'], '普通')


class PrecisionMappingTests(SafetyTests):
    I = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    def run_right(self, scale, travel=0.08, quiet=False):
        sender = bare_sender()
        sender.vr_motion_scale = scale
        sender.vr_pressing = True
        sender.vr_ref = (0.0, 0.0, 0.0)
        sender.vr_anchor = tuple(sender.right)
        sender.vr_qref = self.I
        sender.vr_ori_anchor = self.I
        sender.vr_ori_user = self.I
        sender.vr_smooth = tuple(sender.right)
        sender.vr_quiet = quiet
        sender._vr_still = 0
        submitted = []
        sender._ik_submit = lambda side, target, *rest: submitted.append(target)
        now = time.monotonic()
        snap = (1, now, 0x04, (travel, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0),
                0.0, 1.0, None, None, None, None, None, None)
        with patch.object(self.app.VR, 'latest', return_value=snap):
            sender._vr_step(now)
        return sender.vr_anchor[1], submitted[-1][1]

    def run_left(self, scale):
        sender = bare_sender()
        sender.vr_motion_scale = scale
        sender.left_grip = 0.0
        sender.vr_left_pressing = True
        sender.vr_left_ref = (0.0, 0.0, 0.0)
        sender.vr_left_anchor = tuple(sender.left_target)
        sender.vr_left_qref = self.I
        sender.vr_left_ori_anchor = self.I
        sender.vr_left_ori_user = self.I
        sender.vr_left_smooth = tuple(sender.left_target)
        sender.vr_left_quiet = False
        sender._vr_left_still = 0
        submitted = []
        sender._ik_submit = lambda side, target, *rest: submitted.append(target)
        now = time.monotonic()
        snap = (1, now, 0x02, None, None, None, None, None,
                (0.08, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), 0.0, 1.0, None)
        with patch.object(self.app.VR, 'latest', return_value=snap):
            sender._vr_step_left(now)
        return sender.vr_left_anchor[1], submitted[-1][1]

    def test_both_arms_scale_translation(self):
        for runner in (self.run_right, self.run_left):
            for scale in (1.0, 0.5, 0.25):
                anchor, target = runner(scale)
                # 左右臂先乘精细倍率；beta 按倍率补偿，避免小档额外拖尾。
                filt = self.app.OneEuroFilter3(
                    (0.0, anchor, 0.0),
                    min_cutoff=self.app.VR_ONE_EURO_MIN_CUTOFF,
                    beta=self.app.VR_ONE_EURO_BETA / scale,
                    d_cutoff=self.app.VR_ONE_EURO_D_CUTOFF)
                expected = filt((0.0, anchor + 0.08 * scale, 0.0), 0.0)[1]
                self.assertAlmostEqual(target, expected, places=6)
                self.assertGreater(target - anchor, 0.0)
                self.assertLess(target - anchor, 0.08 * scale)

    def test_rotation_angle_uses_same_scale(self):
        target = self.app._rz(math.radians(40.0))
        for scale in (1.0, 0.5, 0.25):
            scaled = self.app._scale_rotation(self.I, target, scale)
            trace = scaled[0][0] + scaled[1][1] + scaled[2][2]
            angle = math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))
            self.assertAlmostEqual(angle, 40.0 * scale, places=6)

    def test_micro_mode_does_not_keep_large_deadzone(self):
        # 手柄移动 16mm、倍率 0.25：原始目标为 4mm，滤波后仍须超过 0.5mm 缩放门限。
        anchor, target = self.run_right(0.25, travel=0.016, quiet=True)
        movement = target - anchor
        self.assertGreater(movement, 0.002 * 0.25)
        self.assertLess(movement, 0.016 * 0.25)

    def test_left_bad_pose_holds_without_ik_or_exception(self):
        sender = bare_sender()
        submitted = []
        sender._ik_submit = lambda *args: submitted.append(args)
        now = time.monotonic()
        for pos, quat in [(None, None), ((0, 0, 0), (0, 0, 0)),
                          ((0, 0, float('nan')), (0, 0, 0, 1))]:
            snap = (1, now, 0x02, None, None, None, None, None,
                    pos, quat, 0.0, 1.0, None)
            with patch.object(self.app.VR, 'latest', return_value=snap):
                self.assertTrue(sender._vr_step_left(now))
            self.assertIn('位姿无效', sender.vr_left_info)
        self.assertEqual(submitted, [])

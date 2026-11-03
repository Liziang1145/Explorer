"""VR 位置 One Euro 接入与回退测试，不连接机械臂。"""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import arm_console as app
from test_smooth_follow_20261028 import bare_sender


class VRPositionFilterTests(unittest.TestCase):
    def test_clutch_reset_creates_fresh_filter(self):
        sender = bare_sender()
        sender.vr_smooth = tuple(sender.right)
        sender._vr_filter_position('right', (0.21, 0.3, 0.25), sender.right, 1.0)
        previous = sender.vr_position_filters['right']
        sender.vr_smooth = None  # 松开离合时现有逻辑清空平滑状态
        result = sender._vr_filter_position('right', (0.20, 0.3, 0.25), sender.right, 100.0)
        self.assertIsNot(sender.vr_position_filters['right'], previous)
        self.assertEqual(result, (0.2, 0.3, 0.25))

    def test_left_and_right_have_independent_states(self):
        sender = bare_sender()
        sender.vr_smooth = tuple(sender.right)
        sender.vr_left_smooth = tuple(sender.left_target)
        sender._vr_filter_position('right', (0.21, 0.3, 0.25), sender.right, 1.0)
        self.assertIsNotNone(sender.vr_position_filters['right'])
        self.assertIsNone(sender.vr_position_filters['left'])

    def test_ema_fallback_preserves_old_behavior(self):
        sender = bare_sender()
        sender.vr_smooth = tuple(sender.right)
        with mock.patch.object(app, 'VR_POSITION_FILTER', 'ema'):
            result = sender._vr_filter_position(
                'right', (0.24, 0.34, 0.29), sender.right, 1.0)
        self.assertAlmostEqual(result[0], 0.21)
        self.assertAlmostEqual(result[1], 0.31)
        self.assertAlmostEqual(result[2], 0.26)

    def test_default_filter_is_one_euro(self):
        self.assertEqual(app.VR_POSITION_FILTER, 'one_euro')

    def test_precision_scales_compensate_beta(self):
        for scale, expected_beta in ((1.0, 6.0), (0.5, 12.0), (0.25, 24.0)):
            with self.subTest(scale=scale):
                sender = bare_sender()
                sender.vr_motion_scale = scale
                sender.vr_smooth = tuple(sender.right)
                sender._vr_filter_position('right', sender.right, sender.right, 1.0)
                filt = sender.vr_position_filters['right'].filters[0]
                self.assertEqual(filt.beta, expected_beta)
                self.assertEqual(filt.min_cutoff, 1.5)


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""只读 VLA 规划预检测试；禁止网络、子进程与电机调用。"""
import math
import pathlib
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import vla_plan_preview


class VlaPlanPreviewTests(unittest.TestCase):
    def setUp(self):
        self.app = Mock()
        self.app.left_read.return_value = (True, [10.0, 80.0, -30.0, -20.0, -50.0, 5.0])
        self.app.right_read.return_value = (True, [-10.0, 80.0, -30.0, 20.0, -50.0, -5.0])
        self.plan = {'times': [0.0, 0.02], 'q': [[0.0]*6, [0.1]*6], 'duration_s': 0.02}
        self.planner = Mock()
        self.planner.plan_j5_xyz.return_value = dict(self.plan)

    def test_preview_uses_both_real_feedback_snapshots(self):
        with patch.dict(sys.modules, {'vla_motion_planner': self.planner}):
            result = vla_plan_preview.preview({'side': 'left', 'xyz': [0.1, 0.2, 0.3]}, self.app)
        self.assertTrue(result['read_only'])
        self.assertFalse(result['execution_enabled'])
        args = self.planner.plan_j5_xyz.call_args.args
        kwargs = self.planner.plan_j5_xyz.call_args.kwargs
        self.assertEqual(args[:2], ('left', [0.1, 0.2, 0.3]))
        self.assertAlmostEqual(kwargs['current_q'][0], math.radians(10.0))
        self.assertAlmostEqual(kwargs['other_arm_q']['right'][0], math.radians(-10.0))

    def test_right_arm_uses_left_arm_as_obstacle(self):
        with patch.dict(sys.modules, {'vla_motion_planner': self.planner}):
            vla_plan_preview.preview({'side': 'right', 'xyz': [0.1, 0.2, 0.3]}, self.app)
        kwargs = self.planner.plan_j5_xyz.call_args.kwargs
        self.assertIn('left', kwargs['other_arm_q'])
        self.assertNotIn('right', kwargs['other_arm_q'])

    def test_invalid_or_missing_feedback_never_enters_planner(self):
        for data in ({'side': 'left', 'xyz': [0.1, 0.2]},
                     {'side': 'left', 'xyz': [0.1, float('nan'), 0.3]},
                     {'side': 'bad', 'xyz': [0.1, 0.2, 0.3]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                vla_plan_preview.preview(data, self.app)
        self.app.left_read.return_value = (False, 'timeout')
        with self.assertRaisesRegex(ValueError, '无法读取'):
            vla_plan_preview.preview({'side': 'left', 'xyz': [0.1, 0.2, 0.3]}, self.app)
        self.planner.plan_j5_xyz.assert_not_called()

    def test_preview_module_has_no_execution_or_network_api(self):
        source = pathlib.Path(vla_plan_preview.__file__).read_text(encoding='utf-8')
        for forbidden in ('sendto(', '_request_preset(', '_call_move(', 'kr260(', 'deploy('):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()

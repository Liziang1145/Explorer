import math
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stone_grasp_trial as trial


class StoneGraspTrialTests(unittest.TestCase):
    def test_left_arm_body_to_local_and_ten_cm_pregrasp(self):
        target = trial.pregrasp_target([-0.20, 0.70, 0.05], 'left')
        for actual, wanted in zip(target['pregrasp_j7_b_m'], (-0.21, 0.60, 0.05)):
            self.assertAlmostEqual(actual, wanted)
        self.assertAlmostEqual(target['pregrasp_j5_b_m'][1], 0.4475)
        expected = (-0.05745, 0.26375, 0.045)
        for actual, wanted in zip(target['pregrasp_j5_arm_m'], expected):
            self.assertAlmostEqual(actual, wanted)

    def test_right_arm_uses_positive_base_offset(self):
        target = trial.pregrasp_target([0.20, 0.70, 0.05], 'right')
        self.assertAlmostEqual(target['pregrasp_j5_arm_m'][0], 0.2-0.01-0.15255)

    def test_direction_is_normalized_and_j5_j7_length_is_fixed(self):
        target = trial.pregrasp_target([0.0, 0.7, 0.05], direction=[0.0, 2.0, 0.0])
        self.assertEqual(target['direction_b'], (0.0, 1.0, 0.0))
        distance = math.dist(target['pregrasp_j7_arm_m'], target['pregrasp_j5_arm_m'])
        self.assertAlmostEqual(distance, 0.1525)

    def test_camera_origin_maps_to_camera_center_in_body(self):
        point = trial.color_optical_to_body([0.0, 0.0, 0.0])
        expected = (-0.028135471, 0.291114746, 0.540246415)
        for actual, wanted in zip(point, expected):
            self.assertAlmostEqual(actual, wanted)

    def test_intent_is_cm_preview_and_never_contains_real_epoch(self):
        target = trial.pregrasp_target([0.0, 0.7, 0.05])
        intent = trial.read_only_intent(target)
        self.assertEqual(intent['intent'], 'tcp_dir_abs')
        self.assertAlmostEqual(intent['p1'][2], 4.5)
        self.assertEqual(intent['safety_epoch'], 'NOT_PROVIDED_PREVIEW_ONLY')

    def test_bad_inputs_are_rejected(self):
        bad_calls = [
            lambda: trial.pregrasp_target([0.0, 0.7], 'left'),
            lambda: trial.pregrasp_target([0.0, 0.7, float('nan')], 'left'),
            lambda: trial.pregrasp_target([0.0, 0.7, 0.05], 'middle'),
            lambda: trial.pregrasp_target([0.0, 0.7, 0.05], retreat_m=0.31),
            lambda: trial.pregrasp_target([0.0, 0.7, 0.05], direction=[0.0] * 3),
        ]
        for call in bad_calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()

    def test_plan_requires_real_current_q(self):
        with self.assertRaisesRegex(ValueError, 'current_q'):
            trial.plan_preview([0.0, 0.7, 0.05])

    def test_plan_uses_local_j5_and_explicit_orientation(self):
        captured = {}
        app = types.SimpleNamespace(_two_point_orientation=lambda *args: 'orientation')
        def fake_plan(side, xyz, **kwargs):
            captured.update(side=side, xyz=xyz, **kwargs)
            return {'times': [0.0], 'q': [[0.0] * 6], 'duration_s': 0.0}
        planner = types.SimpleNamespace(plan_j5_xyz=fake_plan)
        with patch.dict(sys.modules, {'arm_console': app, 'vla_motion_planner': planner}):
            result = trial.plan_preview([0.0, 0.7, 0.05], current_q=[0.0] * 6)
        self.assertEqual(captured['orientation'], 'orientation')
        self.assertAlmostEqual(captured['xyz'][2], 0.045)
        self.assertTrue(result['read_only'])
        self.assertFalse(result['execution_enabled'])
        self.assertIn('不包含石头和桌面', result['environment_warning'])


if __name__ == '__main__':
    unittest.main()

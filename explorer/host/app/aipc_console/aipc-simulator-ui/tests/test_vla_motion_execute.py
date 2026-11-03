import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vla_motion_execute as motion


class App:
    angles = staticmethod(lambda values: list(values))
    left_read = staticmethod(lambda: (True, [0.0] * 6))
    right_read = staticmethod(lambda: (True, [0.0] * 6))
    _fk_points = staticmethod(lambda q, side: ([[0.0, 0.0, 0.22]] * 6, None))
    _two_point_orientation = staticmethod(lambda *args: [[1.0, 0.0, 0.0]] * 3)


def fake_plan(side, xyz, **kwargs):
    return {'times': [0.0, 0.1, 0.2],
            'q': [[0.0] * 6, [0.0075] + [0.0] * 5, [0.015] + [0.0] * 5],
            'duration_s': 0.2, 'target_xyz_m': xyz,
            'mesh_distance_checks': 10, 'minimum_mesh_clearance_cm': 1.2}


class GenericMotionTests(unittest.TestCase):
    def test_preview_validates_target_and_retimes(self):
        module = types.SimpleNamespace(plan_j5_xyz=fake_plan)
        with patch.dict(sys.modules, {'vla_motion_planner': module}):
            result, code = motion.run({'side': 'left', 'xyz': [0.0, 0.0, 0.23]}, App())
        self.assertEqual(code, 200)
        self.assertTrue(result['read_only'])
        self.assertFalse(result['execution_enabled'])
        self.assertEqual(result['duration_s'], 1.0)
        self.assertAlmostEqual(result['displacement_norm_m'], 0.01)

    def test_more_than_50mm_is_allowed_when_plan_is_safe(self):
        with patch.dict(sys.modules, {'vla_motion_planner': types.SimpleNamespace(plan_j5_xyz=fake_plan)}):
            result, code = motion.run({'side': 'left', 'xyz': [0.0, 0.0, 0.271]}, App())
        self.assertEqual(code, 200)
        self.assertGreater(result['displacement_norm_m'], 0.05)

    def test_long_trajectory_can_preview_but_cannot_execute(self):
        def long_plan(side, xyz, **kwargs):
            result = fake_plan(side, xyz, **kwargs)
            result['duration_s'] = 7.0
            return result
        module = types.SimpleNamespace(plan_j5_xyz=long_plan)
        with patch.dict(sys.modules, {'vla_motion_planner': module}):
            preview, code = motion.run({'side': 'left', 'xyz': [0.0, 0.0, 0.23]}, App())
            self.assertEqual(code, 200)
            self.assertFalse(preview['execution_allowed'])
            with self.assertRaisesRegex(ValueError, '仅供预览'):
                motion.run({'side': 'left', 'xyz': [0.0, 0.0, 0.23],
                            'stage': 'execute'}, App())

    def test_right_arm_preview_and_invalid_requests(self):
        with patch.dict(sys.modules, {'vla_motion_planner': types.SimpleNamespace(plan_j5_xyz=fake_plan)}):
            result, code = motion.run({'side': 'right', 'xyz': [0.0] * 3}, App())
        self.assertEqual(code, 200)
        self.assertTrue(result['read_only'])
        for request in ({'side': 'invalid', 'xyz': [0.0] * 3},
                        {'side': 'left', 'xyz': [0.0] * 3, 'collision_mode': 'coarse'}):
            with self.assertRaises(ValueError):
                motion.run(request, App())

    def test_execute_reuses_controlled_sender(self):
        class Sender:
            def start_planned_test(self, data, trajectory):
                self.duration = trajectory['duration_s']
                return {'ok': True}, 200
        app = App()
        app.SENDER = Sender()
        with patch.dict(sys.modules, {'vla_motion_planner': types.SimpleNamespace(plan_j5_xyz=fake_plan)}):
            result, code = motion.run({'side': 'left', 'xyz': [0.0, 0.0, 0.23],
                                       'stage': 'execute', 'safety_epoch': 'epoch'}, app)
        self.assertEqual(code, 200)
        self.assertEqual(app.SENDER.duration, 1.0)
        self.assertEqual(result['mesh_distance_checks'], 10)


if __name__ == '__main__':
    unittest.main()

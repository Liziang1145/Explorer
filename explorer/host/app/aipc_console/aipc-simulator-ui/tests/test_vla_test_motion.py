import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vla_test_motion as motion


class App:
    angles = staticmethod(lambda values: list(values))
    left_read = staticmethod(lambda: (True, [0.0] * 6))
    right_read = staticmethod(lambda: (True, [0.0] * 6))
    _fk_points = staticmethod(lambda q, side: ([[0.0, 0.0, 0.22]] * 6, None))


def fake_plan(side, xyz, **kwargs):
    assert side == 'left'
    assert abs(xyz[2] - 0.27) < 1e-12
    assert kwargs['collision_mode'] == 'exact'
    return {'times': [0.0, 0.1, 0.2],
            'q': [[0.0] * 6, [0.0075] + [0.0] * 5, [0.015] + [0.0] * 5],
            'duration_s': 0.2, 'target_xyz_m': xyz,
            'mesh_distance_checks': 10, 'minimum_mesh_clearance_cm': 1.2}


class MotionTests(unittest.TestCase):
    def test_preview_is_retimed_and_read_only(self):
        module = types.SimpleNamespace(plan_j5_xyz=fake_plan)
        with patch.dict(sys.modules, {'vla_motion_planner': module}):
            result, code = motion.run({'confirm': motion.TEST_CONFIRM}, App())
        self.assertEqual(code, 200)
        self.assertTrue(result['read_only'])
        self.assertFalse(result['execution_enabled'])
        self.assertEqual(result['times'], [0.0, 0.5, 1.0, 2.0, 2.5, 3.0])
        self.assertEqual(result['q'][0], result['q'][-1])
        self.assertEqual(result['velocity_limit_rad_s'], 0.15)

    def test_wrong_confirmation_never_plans(self):
        with patch.object(motion, '_plan') as plan:
            with self.assertRaises(ValueError):
                motion.run({'confirm': 'wrong', 'stage': 'execute'}, App())
        plan.assert_not_called()

    def test_execute_uses_existing_sender(self):
        class Sender:
            def start_planned_test(self, data, trajectory):
                self.trajectory = trajectory
                return {'ok': True}, 200
        app = App()
        app.SENDER = Sender()
        module = types.SimpleNamespace(plan_j5_xyz=fake_plan)
        with patch.dict(sys.modules, {'vla_motion_planner': module}):
            result, code = motion.run({'confirm': motion.TEST_CONFIRM,
                                       'stage': 'execute'}, app)
        self.assertEqual(code, 200)
        self.assertEqual(app.SENDER.trajectory['duration_s'], 3.0)


if __name__ == '__main__':
    unittest.main()

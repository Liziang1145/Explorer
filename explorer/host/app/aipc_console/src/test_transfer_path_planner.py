# -*- coding: utf-8 -*-
"""离线规划结果的独立回归测试；无网络、无硬件。"""
import math
import unittest

import numpy as np

import transfer_path_planner as planner


class TransferPlannerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.best, cls.evaluations, cls.baseline = planner.plan(samples=161)

    def test_selected_is_fully_feasible(self):
        self.assertTrue(self.best.feasible, self.best.reason)
        self.assertIn('连续补查通过', self.best.reason)
        self.assertGreaterEqual(sum(item.feasible for item in self.evaluations), 1)

    def test_exact_joint_endpoints(self):
        np.testing.assert_allclose(self.best.q[0], planner.app.Q_START_LEFT, atol=1e-12)
        np.testing.assert_allclose(self.best.q[-1], planner.app.Q_LEFT_POS3, atol=1e-12)

    def test_cartesian_and_orientation_endpoints(self):
        for q in (planner.app.Q_START_LEFT, planner.app.Q_LEFT_POS3):
            solved, error = planner.app.solve_layered_j5_pose_user(
                planner.user_position(q), planner.user_rotation(q), q, side='left')
            self.assertIsNone(error)
            np.testing.assert_allclose(solved, q, atol=1e-7)

    def test_execution_joint_limits(self):
        self.assertTrue(np.all(self.best.q >= np.asarray(planner.app.JOINT_LO)))
        self.assertTrue(np.all(self.best.q <= np.asarray(planner.app.JOINT_HI)))

    def test_selected_removes_axis_reversal(self):
        metrics = self.best.metrics
        self.assertLess(metrics['x_backtrack_mm'], 0.01)
        self.assertLess(metrics['z_rebound_mm'], 0.01)
        self.assertLess(metrics['path_length_mm'], self.baseline.metrics['path_length_mm'])

    def test_clearance_and_dynamic_targets(self):
        metrics = self.best.metrics
        self.assertGreaterEqual(metrics['min_bracket_margin_cm'], planner.geometry.MIN_MARGIN_CM)
        self.assertLessEqual(metrics['max_joint_speed_rad_s'], 0.7501)
        self.assertLessEqual(metrics['max_joint_accel_rad_s2'], 2.0001)
        self.assertLessEqual(metrics['max_joint_jerk_rad_s3'], 12.0001)

    def test_time_grid_and_finite_values(self):
        self.assertTrue(np.all(np.isfinite(self.best.q)))
        self.assertTrue(np.all(np.diff(self.best.times) > 0))
        self.assertAlmostEqual(self.best.times[0], 0.0)
        self.assertAlmostEqual(self.best.times[-1], self.best.duration_s)

    def test_minimum_jerk_scalar_boundary_derivatives(self):
        eps = 1e-5
        self.assertAlmostEqual(planner.smooth5(0.0), 0.0)
        self.assertAlmostEqual(planner.smooth5(1.0), 1.0)
        self.assertLess(abs(planner.smooth5(eps) / eps), 1e-9)
        self.assertLess(abs((1-planner.smooth5(1-eps)) / eps), 1e-9)


if __name__ == '__main__':
    unittest.main(verbosity=2)

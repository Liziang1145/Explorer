# -*- coding: utf-8 -*-
"""增强轨迹规划器离线测试，不连接任何设备。"""
import pathlib
import sys
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import coupled_trajectory as planner
import arm_console as app


class ControlledCoupling:
    """测试环境：两臂同时离开起点视为冲突，顺序运动合法。"""
    def __init__(self):
        self.pose_checks = 0
        self.minimum_margin_cm = 1.0

    def pose(self, left, right):
        self.pose_checks += 1
        if 1e-9 < left[0] < 1.0-1e-9 and 1e-9 < right[0] < 1.0-1e-9:
            return False, '测试同时运动冲突', -1.0
        return True, '通过', 1.0

    def path(self, combined, label=''):
        for row in combined:
            ok, reason, _ = self.pose(row[:6], row[6:])
            if not ok:
                raise ValueError(reason)
        return True


class CoupledTrajectoryTests(unittest.TestCase):
    def test_jacobian_shape_and_finite_difference(self):
        q = np.asarray(app.Q_START_LEFT)
        jac = planner.j5_translation_jacobian(q)
        self.assertEqual(jac.shape, (3, 6))
        self.assertTrue(np.all(np.isfinite(jac)))
        joint = 1
        epsilon = 1e-5
        expected = (np.asarray(planner.geometry.fk_chain(q+np.eye(6)[joint]*epsilon)[5]) -
                    np.asarray(planner.geometry.fk_chain(q-np.eye(6)[joint]*epsilon)[5]))/(2*epsilon)
        np.testing.assert_allclose(jac[:, joint], expected, atol=1e-10)

    def test_singularity_speed_scale_is_bounded_and_continuous(self):
        normal = planner.singularity_speed_scale(app.Q_START_LEFT, sigma_floor=0.001)
        self.assertAlmostEqual(normal, 1.0)
        with mock.patch.object(planner, 'singularity_metrics',
                               return_value={'min_singular_value': 0.0}):
            near = planner.singularity_speed_scale(app.Q_START_LEFT, min_scale=0.25)
        self.assertAlmostEqual(near, 0.25)

    def test_coupling_falls_back_to_validated_sequence(self):
        line = np.zeros((21, 6))
        line[:, 0] = np.linspace(0, 1, len(line))
        combined, info = planner.coordinate_paths(
            line, line, ControlledCoupling(), samples=21)
        self.assertEqual(info['mode'], 'left_then_right')
        self.assertEqual(combined.shape, (41, 12))
        np.testing.assert_allclose(combined[20, :6], line[-1])
        np.testing.assert_allclose(combined[20, 6:], line[0])
        np.testing.assert_allclose(combined[-1, 6:], line[-1])

    def test_jerk_limiter_preserves_endpoints_and_limit(self):
        path = np.zeros((41, 6))
        path[:, 0] = np.linspace(0, 0.2, len(path))
        times, q, _ = planner.parameterize(path, 0.8, 2.1333333333, output_dt=0.02)
        times, q, info = planner.limit_jerk(times, q, jerk_limit=20.0)
        metrics = planner.trajectory_metrics(times, q)
        self.assertLessEqual(metrics['max_jerk_rad_s3'], 21.0)
        np.testing.assert_allclose(q[0], path[0], atol=1e-9)
        np.testing.assert_allclose(q[-1], path[-1], atol=1e-9)
        self.assertTrue(info['jerk_limited'])

    def test_toppra_supports_twelve_joints_and_local_speed_scale(self):
        path = np.zeros((31, 12))
        path[:, 0] = np.linspace(0, 0.2, len(path))
        normal_t, _, _ = planner.parameterize(path, 0.8, 2.1333333333, output_dt=0.02)
        slow_t, _, _ = planner.parameterize(
            path, 0.8, 2.1333333333, output_dt=0.02,
            speed_scale=np.full(len(path), 0.5))
        self.assertGreater(slow_t[-1], normal_t[-1])


if __name__ == '__main__':
    unittest.main()

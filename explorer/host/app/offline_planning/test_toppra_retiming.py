# -*- coding: utf-8 -*-
"""TOPP-RA 后向可控集与前向 LP 速度剖面的独立测试。"""
import unittest
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline

from toppra_retiming import parameterize


class ToppraRetimingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parent/'输出'/'最优六轴轨迹.csv'
        data = np.genfromtxt(path, delimiter=',', names=True, encoding='utf-8-sig')
        cls.q_path = np.column_stack([data[f'q_J{j}_rad'] for j in range(1, 7)])
        cls.times, cls.q, cls.info = parameterize(cls.q_path, .75, 2.0, output_dt=.002)

    def test_lp_reachability_algorithm_ran(self):
        n = len(self.q_path)
        self.assertEqual(self.info['backward_lp_count'], 2*(n-1))
        self.assertEqual(self.info['forward_lp_count'], n-1)
        self.assertTrue(np.all(np.isfinite(self.info['controllable_sets'])))

    def test_grid_velocity_and_acceleration_constraints(self):
        s = self.info['s']
        spline = CubicSpline(s, self.q_path, axis=0)
        x = self.info['squared_speed']
        ds = s[1]-s[0]
        u = np.diff(x)/(2*ds)
        velocity = spline(s[:-1], 1)*np.sqrt(x[:-1])[:, None]
        acceleration = spline(s[:-1], 2)*x[:-1, None]+spline(s[:-1], 1)*u[:, None]
        self.assertLessEqual(np.max(np.abs(velocity)), .7500001)
        self.assertLessEqual(np.max(np.abs(acceleration)), 2.0000001)

    def test_zero_endpoint_speed_and_exact_endpoints(self):
        self.assertEqual(self.info['squared_speed'][0], 0.0)
        self.assertEqual(self.info['squared_speed'][-1], 0.0)
        np.testing.assert_allclose(self.q[0], self.q_path[0], atol=1e-12)
        np.testing.assert_allclose(self.q[-1], self.q_path[-1], atol=1e-12)

    def test_duration_and_time_grid(self):
        self.assertAlmostEqual(self.times[-1], self.info['duration_s'])
        self.assertTrue(np.all(np.diff(self.times) > 0))
        self.assertLess(self.info['duration_s'], 4.2)


if __name__ == '__main__':
    unittest.main(verbosity=2)

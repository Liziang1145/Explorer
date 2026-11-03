# -*- coding: utf-8 -*-
"""网页右臂 J5 中心 + RPY 姿态偏移接口专项测试（无硬件）。"""
import math
import time
import unittest
from unittest import mock

import arm_console as app


class WebJ5PoseTest(unittest.TestCase):
    def setUp(self):
        patches = [mock.patch('socket.socket'), mock.patch('threading.Thread.start')]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(patches)])
        self.s = app.ControlSender()
        self.s.owner = 'testclient1234'
        self.s.until = time.monotonic() + 60.0
        self.s.status = lambda: {'ok': True}
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(app.SAFETY, 'require', lambda _d: None).start()

    def request(self, controls, action='update'):
        return self.s._call_follow(action, {
            'client': 'testclient1234', 'action': action, 'controls': controls})

    def test_xyz_is_j5_and_zero_rpy_uses_shared_side_solver(self):
        target = list(app._fk_points(app.QLEVEL, 'right')[0][5])
        with mock.patch.object(app, 'solve_web_j5_rpy_side',
                               return_value=(list(app.QLEVEL), None)) as solve:
            body, code = self.request({'mode': 'right_ee', 'right': target,
                                       'right_rpy_deg': [0, 0, 0]})
        self.assertEqual(code, 200, body)
        p, rpy, seed = solve.call_args.args[:3]
        self.assertEqual(list(p), target)
        self.assertEqual(list(rpy), [0, 0, 0])
        self.assertEqual(seed, app.Q_START_RIGHT)
        self.assertEqual(solve.call_args.kwargs, {'side': 'right'})
        self.assertEqual(self.s.right, target)
        self.assertEqual(self.s.right_target_point, 'j5')

    def test_nonzero_rpy_passes_fixed_chassis_xyz_angles_to_shared_solver(self):
        rpy = [13.0, -24.0, 37.0]
        target = [0.12, 0.29, 0.31]
        with mock.patch.object(app, 'solve_web_j5_rpy_side',
                               return_value=(list(app.QLEVEL), None)) as solve:
            body, code = self.request({'mode': 'right_ee', 'right': target,
                                       'right_rpy_deg': rpy})
        self.assertEqual(code, 200, body)
        self.assertEqual(list(solve.call_args.args[1]), rpy)
        self.assertEqual(solve.call_args.kwargs, {'side': 'right'})
        self.assertEqual(self.s.right_rpy_deg, rpy)

    def test_bad_rpy_rejected_before_solver(self):
        bad_values = [None, [0, 0], [0, 0, float('nan')], [True, 0, 0],
                      [181, 0, 0], ['0', 0, 0]]
        with mock.patch.object(app, 'solve_web_j5_rpy_side') as solve:
            for value in bad_values:
                with self.subTest(value=value):
                    body, code = self.request({'mode': 'right_ee', 'right': [0.1, 0.3, 0.3],
                                               'right_rpy_deg': value})
                    self.assertEqual(code, 400, body)
                    self.assertIn('right_rpy_deg', body.get('error', ''))
        solve.assert_not_called()

    def test_joint_and_web_modes_share_j5_target_point(self):
        deg = [math.degrees(v) for v in app.QLEVEL]
        with mock.patch.object(self.s, '_reset_vr_anchors'):
            body, code = self.request({'mode': 'right_joints', 'right_joints_deg': deg})
        self.assertEqual(code, 200, body)
        self.assertEqual(self.s.right_target_point, 'j5')
        expected_j5 = list(app._fk_points(app.QLEVEL, 'right')[0][5])
        for got, want in zip(self.s.right, expected_j5):
            self.assertAlmostEqual(got, want)

        target = list(app._fk_points(app.QLEVEL, 'right')[0][5])
        with mock.patch.object(app, 'solve_web_j5_rpy_side',
                               return_value=(list(app.QLEVEL), None)) as solve:
            body, code = self.request({'mode': 'right_ee', 'right': target,
                                       'right_rpy_deg': [0, 0, 0]})
        self.assertEqual(code, 200, body)
        self.assertEqual(self.s.right_target_point, 'j5')
        self.assertEqual(list(solve.call_args.args[0]), target)

    def test_start_vr_from_web_does_not_convert_web_j5_to_j7(self):
        self.s.vr_on = True
        self.s.right = [0.1, 0.3, 0.3]
        target = [0.12, 0.32, 0.34]
        with mock.patch.object(app, 'deploy_running', return_value=True), \
                mock.patch.object(app, 'solve_web_j5_rpy_side',
                                  return_value=(list(app.QLEVEL), None)):
            body, code = self.request({'mode': 'right_ee', 'right': target,
                                       'right_rpy_deg': [0, 0, 0]}, action='start')
        self.assertEqual(code, 200, body)
        expected = list(app._fk_points(app.Q_START_RIGHT, 'right')[0][5])
        self.assertEqual(self.s.right, expected)
        self.assertEqual(self.s.joints, list(app.Q_START_RIGHT))
        self.assertEqual(self.s.right_target_point, 'j5')

    def test_telemetry_reports_web_j5_target_and_computed_j5(self):
        self.s.right = [0.12, 0.32, 0.34]
        self.s.right_target_point = 'j5'
        with mock.patch.object(app.VR, 'buttons', return_value={}), \
                mock.patch.dict(app._FB_CACHE, {
                    'right': (0.0, False, None), 'left': (0.0, False, None)}):
            data = self.s.telemetry()
        self.assertEqual(data['arms']['right']['target_point'], 'j5')
        self.assertEqual(data['arms']['right']['target_cm'], [12.0, 32.0, 34.0])
        expected = [round(v * 100, 1) for v in app._fk_points(app.QLEVEL, 'right')[0][5]]
        self.assertEqual(data['arms']['right']['j5_cm'], expected)
        self.assertEqual(data['arms']['left']['target_point'], 'j5')


class WebLayeredIkTest(unittest.TestCase):
    """真实数值解算：网页专用分层算法，不 mock IK，不接触硬件。"""
    @staticmethod
    def pose(q):
        p = app._fk_points(q, 'right')[0][5]
        R = app._mm(app._rz(app.CALIB['right']['yaw']),
                    app._mm(app._FR, app._fk(q)[1]))
        return p, R

    def assert_pose_close(self, got, expected):
        self.assertLess(math.dist(app._fk_points(got, 'right')[0][5],
                                  app._fk_points(expected, 'right')[0][5]), 1e-4)
        rg, re = app._fk(got)[1], app._fk(expected)[1]
        # ||RgᵀRe-I|| 是完整三维姿态残差，不只是某一个欧拉角。
        err = app._mm(app._mt(rg), re)
        angle = math.acos(max(-1.0, min(1.0, (sum(err[i][i] for i in range(3)) - 1) / 2)))
        self.assertLess(angle, 2e-3)

    def test_orientation_only_keeps_first_three_and_j5_fixed(self):
        expected = list(app.QLEVEL[:3]) + [math.radians(v) for v in (35, -45, 70)]
        p, R = self.pose(expected)
        got, err = app.solve_web_j5_rpy_user(p, R, app.QLEVEL)
        self.assertIsNone(err)
        for j in range(3):
            self.assertAlmostEqual(got[j], app.QLEVEL[j], places=12)
        self.assertLess(math.dist(app._fk_j5_native(got), app._fk_j5_native(app.QLEVEL)), 1e-4)
        self.assert_pose_close(got, expected)

    def test_position_change_preserves_target_orientation(self):
        expected = [-0.50, 1.45, -0.90] + [math.radians(v) for v in (35, -45, 70)]
        p, R = self.pose(expected)
        got, err = app.solve_web_j5_rpy_user(p, R, app.QLEVEL)
        self.assertIsNone(err)
        self.assert_pose_close(got, expected)
        self.assertNotEqual(got[:3], list(app.QLEVEL[:3]))
        # 位置由几何解析求解；只要求最终位姿精确，不要求腕部欧拉分解
        # 与 expected 逐角相同（同姿态可有不同分支）。

    def test_wrist_limit_rejects_without_compensating_first_three(self):
        impossible = list(app.QLEVEL[:3]) + [math.radians(v) for v in (35, 80, 70)]
        p, R = self.pose(impossible)
        got, err = app.solve_web_j5_rpy_user(p, R, app.QLEVEL)
        self.assertIsNone(got)
        self.assertIn('限位', err)

    def test_small_rpy_offsets_are_solvable_without_moving_first_three(self):
        p, level = self.pose(app.QLEVEL)
        for rpy in ([0, 5, 0], [0, -5, 0], [5, 0, 0], [0, 0, 5]):
            with self.subTest(rpy=rpy):
                offset = app._rt(0, 0, 0, *[math.radians(v) for v in rpy])[0]
                got, err = app.solve_web_j5_rpy_user(p, app._mm(offset, level), app.QLEVEL)
                self.assertIsNone(err)
                for j in range(3):
                    self.assertAlmostEqual(got[j], app.QLEVEL[j], places=12)
                self.assertLess(math.dist(app._fk_j5_native(got),
                                          app._fk_j5_native(app.QLEVEL)), 1e-4)

    def test_analytic_position_round_trip_over_deterministic_joint_grid(self):
        # 120 个确定性的限位内构型；允许选择与种子不同的等价几何分支。
        for i in range(120):
            expected = [-2.4 + 4.8 * ((i * 37) % 120) / 119,
                        0.08 + (math.pi - 0.16) * ((i * 53) % 120) / 119,
                        -2.85 + 2.77 * ((i * 71) % 120) / 119]
            with self.subTest(i=i):
                target = app._fk_j5_native(expected + [0.0, 0.0, 0.0])
                got, err = app._web_j5_position(target, app.QLEVEL)
                self.assertIsNotNone(got, err)
                self.assertLess(math.dist(target, app._fk_j5_native(got + [0, 0, 0])), 1e-7)
                for j in range(3):
                    self.assertGreaterEqual(got[j], app._QLO[j] - 1e-9)
                    self.assertLessEqual(got[j], app._QHI[j] + 1e-9)


if __name__ == '__main__':
    unittest.main()

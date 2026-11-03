# -*- coding: utf-8 -*-
"""2026-10-28 J5/J7 两点 + 翻滚角动作接口专项测试。"""
import math
import unittest
from unittest import mock

import arm_console as app


class TwoPointGeometryTest(unittest.TestCase):
    def test_measured_lengths(self):
        self.assertAlmostEqual(app.TWO_POINT_J5_TCP, 0.1525)
        self.assertAlmostEqual(app.TWO_POINT_TCP_S, 0.0615)

    def test_zero_roll_points_forward_and_opens_left_right(self):
        R = app._two_point_orientation(
            [0.0, app.TWO_POINT_J5_TCP, 0.0], [0.0, 0.0, 0.0], 0.0,
            app.QLEVEL, 'right')
        # 法兰 Z=指向车体前方，法兰 Y=夹指沿车体左右张开。
        for got, want in zip((R[0][2], R[1][2], R[2][2]), (0.0, 1.0, 0.0)):
            self.assertAlmostEqual(got, want)
        for got, want in zip((R[0][1], R[1][1], R[2][1]), (1.0, 0.0, 0.0)):
            self.assertAlmostEqual(got, want)

    def test_roll_changes_opening_axis_not_direction(self):
        p1 = [0.0, app.TWO_POINT_J5_TCP, 0.0]
        p2 = [0.0, 0.0, 0.0]
        R0 = app._two_point_orientation(p1, p2, 0.0, app.QLEVEL, 'right')
        R1 = app._two_point_orientation(p1, p2, math.pi / 2, app.QLEVEL, 'right')
        for i in range(3):
            self.assertAlmostEqual(R0[i][2], R1[i][2])
            self.assertAlmostEqual(R1[i][1], -R0[i][0])

    def test_arbitrary_pose_is_rotation_matrix(self):
        d = (0.3, -0.7, 0.5)
        n = math.sqrt(sum(v * v for v in d))
        p2 = (0.1, 0.2, 0.3)
        p1 = [p2[i] + app.TWO_POINT_J5_TCP * d[i] / n for i in range(3)]
        R = app._two_point_orientation(p1, p2, 0.37, app.QLEVEL, 'right')
        I = app._mm(R, app._mt(R))
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(I[i][j], 1.0 if i == j else 0.0, places=8)
        det = app._mv(R, (1, 0, 0))
        self.assertAlmostEqual(sum(det[i] * R[i][0] for i in range(3)), 1.0)

    def test_bad_distance_rejected(self):
        with self.assertRaisesRegex(ValueError, '距离'):
            app._two_point_orientation([0.0, 0.3, 0.0], [0.0, 0.0, 0.0],
                                       0.0, app.QLEVEL, 'right')

    def test_parallel_zero_reference_uses_current_orientation(self):
        R = app._two_point_orientation(
            [app.TWO_POINT_J5_TCP, 0.0, 0.0], [0.0, 0.0, 0.0], 0.0,
            app.QLEVEL, 'right')
        for got, want in zip((R[0][2], R[1][2], R[2][2]), (1.0, 0.0, 0.0)):
            self.assertAlmostEqual(got, want)
        self.assertAlmostEqual(sum(R[i][1] ** 2 for i in range(3)), 1.0)


class TwoPointSolverTest(unittest.TestCase):
    def test_solver_uses_measured_tcp_and_layered_core(self):
        p1 = [0.0, app.TWO_POINT_J5_TCP, 0.0]
        p2 = [0.0, 0.0, 0.0]
        expected_R = app._two_point_orientation(p1, p2, 0.0, app.QLEVEL, 'right')
        with mock.patch.object(app, 'solve_layered_j5_pose_user',
                               return_value=(app.QLEVEL, None)) as solve:
            q, err = app.solve_two_point_user(p1, p2, 0.0, app.QLEVEL)
            self.assertIsNone(err)
            self.assertEqual(tuple(q), app.QLEVEL)
            self.assertEqual(solve.call_args.args[0], p2)
            self.assertEqual(solve.call_args.kwargs['side'], 'right')
            got_R = solve.call_args.args[1]
            for i in range(3):
                for j in range(3):
                    self.assertAlmostEqual(got_R[i][j], expected_R[i][j], places=12)

    def test_round_trip_from_known_joint_pose(self):
        # 从已知六轴姿态生成符合实测工具长度的 J5/J7，再反解并核验 FK 位姿。
        q0 = app.QLEVEL
        pts, Rn = app._fk_points(q0, 'right')
        p5 = pts[5]
        flange = app._calib_to_chassis(app._mv(app._FR, app._fk(q0)[0]), 'right')
        R_user = app._mm(app._rz(app.CALIB['right']['yaw']), app._mm(app._FR, Rn))
        axis = [R_user[i][2] for i in range(3)]
        p7 = [flange[i] + app.TWO_POINT_TCP_S * axis[i] for i in range(3)]
        R0 = app._two_point_orientation(p7, p5, 0.0, q0, 'right')
        xt = [R_user[i][0] for i in range(3)]
        x0 = [R0[i][0] for i in range(3)]
        y0 = [R0[i][1] for i in range(3)]
        psi = math.atan2(sum(xt[i] * y0[i] for i in range(3)),
                         sum(xt[i] * x0[i] for i in range(3)))
        q, err = app.solve_two_point_user(p7, p5, psi, q0)
        self.assertIsNotNone(q, err)
        self.assertIsNone(err)
        pe, oe = app._ik_residual(app._fk(q)[0], app._fk(q)[1],
                                  app._fk(q0)[0], app._fk(q0)[1], 'full')
        self.assertLess(pe, 1e-4)
        self.assertLess(oe, 2e-3)


class VrTwoPointAdapterTest(unittest.TestCase):
    def test_xyz_is_j5_and_arbitrary_orientation_is_preserved(self):
        R = app._quat_to_R((0.13, -0.37, 0.29, 0.87))
        p5_input = [0.03, 0.29, 0.31]
        captured = {}

        def fake_solve(p7, p5, roll, seed, **kwargs):
            captured['p7'] = list(p7)
            captured['p5'] = list(p5)
            captured['R'] = app._two_point_orientation(
                p7, p5, roll, seed, kwargs['side'], expected_len=0.091 + kwargs['tcp_s'])
            return app.QLEVEL, None

        with mock.patch.object(app, 'solve_two_point_user', side_effect=fake_solve):
            q, err = app.solve_vr_pose_two_point_user(p5_input, R, app.QLEVEL)
        self.assertIsNone(err)
        self.assertEqual(tuple(q), app.QLEVEL)
        self.assertEqual(captured['p5'], p5_input, 'VR XYZ 必须原样作为 J5 目标')
        length = 0.091 + app.CALIB['right']['s']
        for i in range(3):
            self.assertAlmostEqual(captured['p7'][i], p5_input[i] + length * R[i][2])
            for j in range(3):
                self.assertAlmostEqual(captured['R'][i][j], R[i][j], places=10)

    def test_adapter_uses_existing_arm_calibration(self):
        R = app._mm(app._rz(app.CALIB['left']['yaw']),
                    app._mm(app._FR, app._fk(app.QLEVEL)[1]))
        with mock.patch.object(app, 'solve_two_point_user',
                               return_value=(app.QLEVEL, None)) as solve:
            app.solve_vr_pose_two_point_user([0.0, 0.3, 0.3], R, app.QLEVEL, side='left')
        self.assertAlmostEqual(solve.call_args.kwargs['tcp_s'], app.CALIB['left']['s'])

    def test_round_trip_from_known_joint_pose(self):
        q0 = app.QLEVEL
        pts, Rn = app._fk_points(q0, 'right')
        p5 = pts[5]
        R = app._mm(app._rz(app.CALIB['right']['yaw']), app._mm(app._FR, Rn))
        q, err = app.solve_vr_pose_two_point_user(p5, R, q0)
        self.assertIsNotNone(q, err)
        self.assertIsNone(err)
        pe, oe = app._ik_residual(app._fk(q)[0], app._fk(q)[1],
                                  app._fk(q0)[0], app._fk(q0)[1], 'full')
        self.assertLess(pe, 1e-4)
        self.assertLess(oe, 2e-3)

    def test_zero_tcp_calibration_does_not_use_http_length(self):
        R = app._mm(app._rz(app.CALIB['right']['yaw']), app._mm(app._FR, app._fk(app.QLEVEL)[1]))
        with mock.patch.dict(app.CALIB['right'], {'s': 0.0}), \
                mock.patch.object(app, 'solve_two_point_user',
                                  return_value=(app.QLEVEL, None)) as solve:
            q, err = app.solve_vr_pose_two_point_user([0.0, 0.3, 0.3], R, app.QLEVEL)
        self.assertIsNotNone(q, err)
        self.assertIsNone(err)
        self.assertEqual(solve.call_args.kwargs['tcp_s'], 0.0)


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""左右网页 J5+RPY 共性入口回归；全部 mock，不接触硬件。"""
import math
import time
import unittest
from unittest import mock

import arm_console as app


class UnifiedWebJ5Test(unittest.TestCase):
    def setUp(self):
        patches = [mock.patch('socket.socket'), mock.patch('threading.Thread.start')]
        for patch in patches:
            patch.start()
        self.addCleanup(lambda: [patch.stop() for patch in reversed(patches)])
        mock.patch.object(app.SAFETY, 'require', lambda _d: None).start()
        self.sender = app.ControlSender()
        self.sender.owner_left = 'testclient1234'
        self.sender.left_until = time.monotonic() + 60
        self.sender.status = lambda: {'ok': True}

    def request(self, controls):
        return self.sender._call_follow('update', {
            'client': 'testclient1234', 'action': 'update', 'controls': controls})

    def test_left_rpy_uses_shared_v3_solver_not_legacy_ik(self):
        target = [-0.12, 0.29, 0.31]
        rpy = [11.0, -22.0, 33.0]
        with mock.patch.object(app, 'solve_web_j5_rpy_side',
                               return_value=(list(app.Q_START_LEFT), None)) as solve, \
                mock.patch.object(app, 'solve_ik_user') as legacy:
            body, code = self.request({'mode': 'left_ee', 'left': target,
                                       'left_rpy_deg': rpy})
        self.assertEqual(code, 200, body)
        legacy.assert_not_called()
        self.assertEqual(list(solve.call_args.args[0]), target)
        self.assertEqual(list(solve.call_args.args[1]), rpy)
        self.assertEqual(solve.call_args.kwargs, {'side': 'left'})
        self.assertEqual(self.sender.left_rpy_deg, rpy)
        self.assertEqual(self.sender.left_target, target)

    def test_left_bad_rpy_rejected_before_solver(self):
        with mock.patch.object(app, 'solve_web_j5_rpy_side') as solve:
            body, code = self.request({'mode': 'left_ee', 'left': [-0.1, 0.3, 0.3],
                                       'left_rpy_deg': [0, 181, 0]})
        self.assertEqual(code, 400, body)
        self.assertIn('left_rpy_deg', body.get('error', ''))
        solve.assert_not_called()

    def test_left_joint_mode_keeps_j5_target(self):
        degrees = [math.degrees(v) for v in app.Q_START_LEFT]
        with mock.patch.object(self.sender, '_reset_vr_anchors'):
            body, code = self.request({'mode': 'left_joints',
                                       'left_joints_deg': degrees})
        self.assertEqual(code, 200, body)
        expected = app._fk_points(app.Q_START_LEFT, 'left')[0][5]
        for got, want in zip(self.sender.left_target, expected):
            self.assertAlmostEqual(got, want)

    def test_right_start_keeps_j5_and_compensates_five_degrees(self):
        base_points, _ = app._fk_points(app.QLEVEL, 'right')
        points, native_r = app._fk_points(app.Q_START_RIGHT, 'right')
        for got, want in zip(points[5], base_points[5]):
            self.assertAlmostEqual(got, want, places=7)
        level_user_r = app._mm(app._FR, app._fk(app.QLEVEL)[1])
        want_user_r = app._mm(app._rt(0, 0, 0, 0, 0, math.radians(-5))[0], level_user_r)
        want_r = app._mm(app._FRT, want_user_r)
        for got_row, want_row in zip(native_r, want_r):
            for got, want in zip(got_row, want_row):
                self.assertAlmostEqual(got, want, places=7)

    def test_left_start_uses_measured_snapshot(self):
        expected = [math.radians(v) for v in (38.8, 93.8, -43.2, 57.2, -60.4, -35.8)]
        for got, want in zip(app.Q_START_LEFT, expected):
            self.assertAlmostEqual(got, want, places=12)
        points, _ = app._fk_points(app.Q_START_LEFT, 'left')
        expected_j5 = [-0.15563879998834196, 0.19357562697099595, 0.23843720606181953]
        for got, want in zip(points[5], expected_j5):
            self.assertAlmostEqual(got, want, places=7)

    def test_zero_rpy_reproduces_each_calibrated_start_pose(self):
        for side, start in (('right', app.Q_START_RIGHT), ('left', app.Q_START_LEFT)):
            with self.subTest(side=side):
                p5 = app._fk_points(start, side)[0][5]
                got, err = app.solve_web_j5_rpy_side(p5, [0, 0, 0], start, side)
                self.assertIsNone(err)
                for actual, expected in zip(got, start):
                    self.assertAlmostEqual(actual, expected, places=7)

    def test_shared_solver_constructs_fixed_axis_rpy_for_both_sides(self):
        for side in ('right', 'left'):
            with self.subTest(side=side), \
                    mock.patch.object(app, 'solve_layered_j5_pose_user',
                                      return_value=(list(app.QLEVEL), None)) as layered:
                app.solve_web_j5_rpy_side([0.1, 0.3, 0.3], [10, 20, 30],
                                           app.QLEVEL, side)
                self.assertEqual(layered.call_args.kwargs, {'side': side})
                self.assertEqual(layered.call_args.args[2], app.QLEVEL)

    def test_new_sender_seq_is_time_seeded_for_left_only_restart(self):
        self.assertGreater(self.sender.seq, 1_000_000_000)

    def test_finish_stop_all_uses_common_cancel_and_marks_transfer(self):
        with mock.patch.object(app.SENDER, '_cancel_sessions') as cancel, \
                mock.patch.object(app, 'kr260', side_effect=[
                    (0, 'stopped'), (0, 'deploy: STOPPED')]):
            app.finish_stop_all(None)
        cancel.assert_called_once_with('全局软件停止：会话已撤销')


if __name__ == '__main__':
    unittest.main()

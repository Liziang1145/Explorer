# -*- coding: utf-8 -*-
"""two_point_abs 意图：单位换算、完整位姿准入与受控运动链路。"""
import math
import unittest
from unittest import mock

import arm_console as app


class TwoPointIntentTest(unittest.TestCase):
    def setUp(self):
        self.s = app.ControlSender.__new__(app.ControlSender)
        self.data = {'intent': 'two_point_abs', 'side': 'right',
                     'p1': [0.0, 15.25, 20.0], 'p2': [0.0, 0.0, 20.0],
                     'theta': 30.0, 'safety_epoch': 'epoch-test',
                     'client': 'vla-test'}

    def test_schema_advertises_new_intent(self):
        schema = app.ControlSender.intent_schema()
        self.assertEqual(schema['api_version'], '2026-10-29')
        item = next(v for v in schema['intents'] if v['intent'] == 'two_point_abs')
        self.assertEqual(item['params']['theta'], '翻滚角，度')

    def test_full_pose_is_forwarded_to_controlled_motion(self):
        with mock.patch.object(app.ControlSender, '_intent_current_joints', return_value=app.QLEVEL), \
             mock.patch.object(app, 'solve_two_point_user', return_value=(app.QLEVEL, None)) as solve, \
             mock.patch.object(app.ControlSender, '_intent_send_joints',
                               return_value=({'ok': True}, 200)) as send:
            body, code = self.s.intent(self.data)
            self.assertEqual(code, 200)
            self.assertTrue(body['ok'])
            args = solve.call_args.args
            self.assertEqual(args[0], [0.0, 0.1525, 0.20])
            self.assertEqual(args[1], [0.0, 0.0, 0.20])
            self.assertAlmostEqual(args[2], math.radians(30.0))
            self.assertEqual(args[3], app.QLEVEL)
            self.assertEqual(send.call_args.args[2]['safety_epoch'], 'epoch-test')
            self.assertEqual(send.call_args.args[3], 'two_point_abs')
            self.assertEqual(send.call_args.kwargs['extra']['note'], '位置+完整姿态收敛')

    def test_degraded_pose_is_not_sent(self):
        with mock.patch.object(app.ControlSender, '_intent_current_joints', return_value=app.QLEVEL), \
             mock.patch.object(app, 'solve_two_point_user',
                               return_value=(app.QLEVEL, '降级：仅位置（姿态放开）')), \
             mock.patch.object(app.ControlSender, '_intent_send_joints') as send:
            body, code = self.s.intent(self.data)
            self.assertEqual(code, 409)
            self.assertFalse(body['ok'])
            self.assertIn('不下发降级解', body['error'])
            send.assert_not_called()

    def test_unreachable_pose_is_not_sent(self):
        with mock.patch.object(app.ControlSender, '_intent_current_joints', return_value=app.QLEVEL), \
             mock.patch.object(app, 'solve_two_point_user', return_value=(None, '不可达')), \
             mock.patch.object(app.ControlSender, '_intent_send_joints') as send:
            body, code = self.s.intent(self.data)
            self.assertEqual(code, 409)
            self.assertFalse(body['ok'])
            send.assert_not_called()

    def test_bad_geometry_is_400_and_not_sent(self):
        self.data['p2'] = [0.0, -20.0, 20.0]  # J5—J7 变成 35.25cm
        with mock.patch.object(app.ControlSender, '_intent_current_joints', return_value=app.QLEVEL), \
             mock.patch.object(app.ControlSender, '_intent_send_joints') as send:
            body, code = self.s.intent(self.data)
            self.assertEqual(code, 400)
            self.assertIn('距离', body['error'])
            send.assert_not_called()

    def test_boolean_coordinate_is_rejected(self):
        self.data['theta'] = True
        body, code = self.s.intent(self.data)
        self.assertEqual(code, 400)
        self.assertFalse(body['ok'])

    def test_p1_outside_workspace_is_rejected(self):
        self.data['p1'] = [0.0, 80.0, 20.0]
        body, code = self.s.intent(self.data)
        self.assertEqual(code, 400)
        self.assertIn('超出可达框', body['error'])


class DirectionIntentTest(unittest.TestCase):
    def setUp(self):
        self.s = app.ControlSender.__new__(app.ControlSender)
        self.data = {'intent': 'tcp_dir_abs', 'side': 'right',
                     'p1': [0.0, 15.25, 20.0], 'direction': [0.0, 10.0, 0.0],
                     'theta': 30.0, 'safety_epoch': 'epoch-test', 'client': 'vla-test'}

    def test_direction_is_normalized_and_p2_derived(self):
        with mock.patch.object(app.ControlSender, '_intent_current_joints', return_value=app.QLEVEL), \
             mock.patch.object(app, 'solve_two_point_user', return_value=(app.QLEVEL, None)) as solve, \
             mock.patch.object(app.ControlSender, '_intent_send_joints',
                               return_value=({'ok': True}, 200)) as send:
            body, code = self.s.intent(self.data)
            self.assertEqual(code, 200)
            self.assertTrue(body['ok'])
            args = solve.call_args.args
            self.assertEqual(args[0], [0.0, 0.1525, 0.20])
            for got, want in zip(args[1], [0.0, 0.0, 0.20]):
                self.assertAlmostEqual(got, want)
            self.assertAlmostEqual(args[2], math.radians(30.0))
            self.assertEqual(send.call_args.kwargs['extra']['direction'], [0.0, 1.0, 0.0])
            self.assertEqual(send.call_args.args[3], 'tcp_dir_abs')

    def test_zero_direction_is_rejected_without_motion(self):
        self.data['direction'] = [0.0, 0.0, 0.0]
        with mock.patch.object(app.ControlSender, '_intent_send_joints') as send:
            body, code = self.s.intent(self.data)
            self.assertEqual(code, 400)
            self.assertIn('零向量', body['error'])
            send.assert_not_called()

    def test_direction_interface_also_rejects_degraded_pose(self):
        with mock.patch.object(app.ControlSender, '_intent_current_joints', return_value=app.QLEVEL), \
             mock.patch.object(app, 'solve_two_point_user',
                               return_value=(app.QLEVEL, '降级：仅位置（姿态放开）')), \
             mock.patch.object(app.ControlSender, '_intent_send_joints') as send:
            body, code = self.s.intent(self.data)
            self.assertEqual(code, 409)
            self.assertIn('不下发降级解', body['error'])
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()

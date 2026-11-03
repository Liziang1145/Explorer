"""X 搬运流程与 A 双臂归位：全部离线，不连接机械臂。"""
import math
import pathlib
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_console_safety import SafetyTests


class VrRouteTests(SafetyTests):
    def test_positions_one_two_three_hold_j1_j2(self):
        app = self.app
        for q in (app.Q_LEFT_POS1, app.Q_LEFT_POS2, app.Q_LEFT_POS3):
            self.assertEqual(q[:2], app.Q_LEFT_POS3[:2])
        self.assertEqual([round(math.degrees(v), 1) for v in app.Q_LEFT_POS3],
                         [149.0, 100.6, -34.3, -50.6, -61.4, 31.3])

    def test_x_releases_only_at_pos3_then_restores_original(self):
        app, sender = self.app, self.app.SENDER
        original_deg = [10.0, 80.0, -30.0, -20.0, -50.0, 5.0]
        original = [math.radians(v) for v in original_deg]
        sender.left_grip = 0.65
        calls = []
        grip_at_calls = []

        def slow_move(target, task_id):
            calls.append(tuple(target))
            grip_at_calls.append(sender.left_grip)
            return True

        with patch.object(app, 'left_read', return_value=(True, original_deg)), \
             patch.object(sender, '_slow_move_left', side_effect=slow_move), \
             patch.object(app, 'VR_RELEASE_WAIT_S', 0.0), \
             patch('threading.Thread') as thread:
            sender._request_preset('left')
            thread.call_args.kwargs['target']()
        self.assertEqual(calls, [tuple(app.Q_START_LEFT), tuple(app.Q_LEFT_POS3),
                                 tuple(app.Q_START_LEFT), tuple(original)])
        self.assertEqual(grip_at_calls[:2], [0.65] * 2)
        self.assertEqual(grip_at_calls[2:], [0.0, 0.0])
        self.assertEqual(sender.left_grip, 0.65)
        self.assertEqual(sender.left_joints, original)
        self.assertTrue(sender.vr_left_on)
        self.assertEqual(sender.vr_left_anchor, tuple(sender.left_target))
        self.assertIsNone(sender.vr_left_ref)
        self.assertIsNone(sender.vr_left_qref)
        self.assertFalse(sender._vr_route_running)

    def test_x_stage_completion_keeps_gripper_sender_active(self):
        """位置 3 到位不得留下夹爪停发空窗，否则返回时才真正松开。"""
        sender = self.app.SENDER
        target = list(self.app.Q_LEFT_POS3)
        entry = self.app.EntrySequence(target, target, self.app.time.monotonic())
        sender.entries['left'] = entry
        sender.move_side['left'] = 'to_pos3'
        sender.owner_left = 'vr-button'
        sender.left_joints = list(target)
        sender.left_grip = 0.0
        sender._vr_route_running = True
        feedback = [math.degrees(v) for v in target]
        with patch.object(self.app, 'left_read', return_value=(True, feedback)), \
             patch.object(self.app, 'entry_log'):
            sender._entry_feedback('left', entry)
        self.assertEqual(sender.owner_left, 'vr-button')
        self.assertEqual(sender.left_joints, target)
        self.assertEqual(sender.left_grip, 0.0)
        self.assertIsNone(sender.move_side['left'])
        self.assertEqual(sender.move_result['left']['state'], 'done')
        # 第二轮常见的额外条件：上次网页活动已超过 60 秒，也不能误撤搬运会话。
        sender._web_active_at['left'] = time.monotonic() - 120.0
        with patch.object(sender.sock, 'sendto') as send:
            sender._tick_body()
        self.assertEqual(sender.owner_left, 'vr-button')
        self.assertEqual(sender.left_joints, target)
        send.assert_called_once()

    def test_a_returns_right_then_left(self):
        sender = self.app.SENDER
        with patch.object(sender, '_move_and_wait', return_value=True) as move, \
             patch('threading.Thread') as thread:
            sender._request_preset('right')
            thread.call_args.kwargs['target']()
        self.assertEqual([c.args[:2] for c in move.call_args_list],
                         [('right', 'start'), ('left', 'start')])

    def test_a_restores_only_previously_active_vr_sides(self):
        sender = self.app.SENDER
        sender.vr_on = True
        sender.vr_left_on = False
        with patch.object(sender, '_move_and_wait', return_value=True), \
             patch.object(sender, '_resume_vr_follow') as resume, \
             patch('threading.Thread') as thread:
            sender._request_preset('right')
            thread.call_args.kwargs['target']()
        resume.assert_called_once_with(True, False)

    def test_a_does_not_invent_vr_or_resume_after_cancel(self):
        sender = self.app.SENDER
        with patch.object(sender, '_move_and_wait', return_value=False), \
             patch.object(sender, '_resume_vr_follow') as resume, \
             patch('threading.Thread') as thread:
            sender.vr_on = sender.vr_left_on = True
            sender._request_preset('right')
            thread.call_args.kwargs['target']()
        resume.assert_not_called()

    def test_cancel_sessions_invalidates_route(self):
        sender = self.app.SENDER
        sender._vr_task_id = 7
        sender._vr_route_running = True
        sender._cancel_sessions('test')
        self.assertFalse(sender._vr_route_running)
        self.assertFalse(sender._vr_task_valid(7))
        self.assertEqual(app_wait_seconds(self.app), 5.0)

    def test_web_route_uses_same_x_workflow_and_safety(self):
        sender = self.app.SENDER
        with patch.object(sender, '_request_preset') as route:
            body, code = self.post('/api/vr_route', {
                'action': 'left_transfer', 'safety_epoch': self.token})
            self.assertEqual(code, 202)
            route.assert_called_once_with('left')

    def test_web_dual_home_can_cancel_running_route(self):
        sender = self.app.SENDER
        sender._vr_route_running = True
        with patch.object(sender, '_request_preset') as route:
            body, code = self.post('/api/vr_route', {
                'action': 'dual_home', 'safety_epoch': self.token})
            self.assertEqual(code, 202)
            route.assert_called_once_with('right')

    def test_web_route_rejects_duplicate_and_wrong_mode(self):
        sender = self.app.SENDER
        sender._vr_route_running = True
        body, code = self.post('/api/vr_route', {
            'action': 'left_transfer', 'safety_epoch': self.token})
        self.assertEqual(code, 409)
        sender._vr_route_running = False
        sender.mode = 'base'
        body, code = self.post('/api/vr_route', {
            'action': 'left_transfer', 'safety_epoch': self.token})
        self.assertEqual(code, 409)

    def test_vla_transfer_uses_same_workflow_without_vr_resume(self):
        sender = self.app.SENDER
        with patch.object(sender, '_request_preset', return_value=42) as route:
            body, code = self.post('/api/intent', {
                'intent': 'left_transfer', 'side': 'left', 'safety_epoch': self.token})
        self.assertEqual(code, 202)
        self.assertEqual(body['task_id'], 42)
        self.assertEqual(body['status_url'], '/api/transfer/status')
        route.assert_called_once_with('left', source='vla', resume_vr=False)

    def test_vla_transfer_completion_is_machine_readable_and_keeps_vr_off(self):
        app, sender = self.app, self.app.SENDER
        original_deg = [10.0, 80.0, -30.0, -20.0, -50.0, 5.0]
        sender.left_grip = 0.65
        with patch.object(app, 'left_read', return_value=(True, original_deg)), \
             patch.object(sender, '_slow_move_left', return_value=True), \
             patch.object(app, 'VR_RELEASE_WAIT_S', 0.0), \
             patch('threading.Thread') as thread:
            task_id = sender._request_preset('left', source='vla', resume_vr=False)
            thread.call_args.kwargs['target']()
        state = sender.transfer_status()
        self.assertEqual(state['task_id'], task_id)
        self.assertEqual(state['state'], 'done')
        self.assertEqual(state['stage'], 'done')
        self.assertEqual(state['source'], 'vla')
        self.assertFalse(state['resume_vr'])
        self.assertFalse(sender.vr_left_on)
        self.assertEqual(sender.left_grip, 0.65)

    def test_vla_transfer_rejects_bad_parameters_and_duplicate(self):
        sender = self.app.SENDER
        body, code = self.post('/api/intent', {
            'intent': 'left_transfer', 'side': 'right', 'safety_epoch': self.token})
        self.assertEqual(code, 400)
        body, code = self.post('/api/intent', {
            'intent': 'left_transfer', 'side': 'left', 'resume_vr': 'false',
            'safety_epoch': self.token})
        self.assertEqual(code, 400)
        sender._vr_route_running = True
        body, code = self.post('/api/intent', {
            'intent': 'left_transfer', 'side': 'left', 'safety_epoch': self.token})
        self.assertEqual(code, 409)

    def test_cancel_updates_transfer_status(self):
        sender = self.app.SENDER
        sender._transfer.update(task_id=9, state='running', stage='to_pos2')
        sender._cancel_sessions('测试停止')
        state = sender.transfer_status()
        self.assertEqual(state['state'], 'cancelled')
        self.assertEqual(state['message'], '测试停止')

    def test_left_vr_start_uses_unique_home_without_ik(self):
        app, sender = self.app, self.app.SENDER
        data = {'client': 'offline-left-vr', 'safety_epoch': self.token,
                'controls': {'mode': 'vr_left'}}
        with patch.object(app, 'deploy_running', return_value=True), \
             patch.object(app, 'solve_level_j5_pose_user',
                          side_effect=AssertionError('统一起始位不得再经过 IK')):
            body, code = sender._call_follow('start', data)
        self.assertEqual(code, 200, body)
        self.assertTrue(sender.vr_left_on)
        self.assertEqual(sender.left_joints, list(app.Q_START_LEFT))
        actual_j5 = app._fk_points(sender.left_joints, 'left')[0][5]
        for actual, expected in zip(actual_j5, sender.left_target):
            self.assertAlmostEqual(actual, expected, places=5)

    def test_left_vr_resume_uses_same_unique_home_without_ik(self):
        app, sender = self.app, self.app.SENDER
        sender.left_joints = None
        with patch.object(app, 'deploy_running_cached', return_value=True), \
             patch.object(app, 'solve_level_j5_pose_user',
                          side_effect=AssertionError('恢复起始位不得再经过 IK')):
            sender._resume_vr_follow(False, True)
        self.assertEqual(sender.left_joints, list(app.Q_START_LEFT))
        self.assertTrue(sender.vr_left_on)
        self.assertEqual(sender.vr_left_anchor, tuple(sender.left_target))

    def test_left_stop_during_move_preserves_right_session(self):
        app, sender = self.app, self.app.SENDER
        right_entry = app.EntrySequence([0.0] * 6, list(app.Q_START_RIGHT), time.monotonic())
        left_entry = app.EntrySequence([0.0] * 6, list(app.Q_START_LEFT), time.monotonic())
        sender.entries.update(right=right_entry, left=left_entry)
        sender.owner = 'right-owner'
        sender.owner_left = 'left-owner'
        sender.vr_on = True
        sender.left_joints = list(app.Q_START_LEFT)
        with patch.object(app, 'encode_v2', return_value=b'left-hold') as encode:
            body, code = sender.call('stop', {'client': 'offline-client',
                                             'controls': {'mode': 'left_joints'}})
        self.assertEqual(code, 200, body)
        args = encode.call_args.args
        self.assertIsNotNone(args[1])       # 右臂仍以 mode=2 保持原目标
        self.assertEqual(tuple(args[1]), tuple(sender.joints))
        self.assertIsNone(args[3])          # 左臂明确 mode=0，而非简单停发
        sender.sock.sendto.assert_called_once_with(b'left-hold', app.UDP_TARGET)
        self.assertIs(sender.entries['right'], right_entry)
        self.assertEqual(sender.owner, 'right-owner')
        self.assertTrue(sender.vr_on)
        self.assertIsNone(sender.entries['left'])
        self.assertIsNone(sender.owner_left)
        self.assertIsNone(sender.left_joints)
        self.assertFalse(sender.vr_left_on)

    def test_right_stop_during_move_preserves_left_transfer(self):
        app, sender = self.app, self.app.SENDER
        left_entry = app.EntrySequence([0.0] * 6, list(app.Q_START_LEFT), time.monotonic())
        sender.entries['right'] = app.EntrySequence([0.0] * 6, list(app.Q_START_RIGHT), time.monotonic())
        sender.entries['left'] = left_entry
        sender.owner_left = 'left-owner'
        sender.left_joints = list(app.Q_START_LEFT)
        sender.vr_left_on = True
        sender._transfer.update(task_id=9, state='running', stage='to_pos2')
        with patch.object(app, 'encode_v2', return_value=b'right-hold') as encode:
            body, code = sender.call('stop', {'client': 'offline-client',
                                             'controls': {'mode': 'right_joints'}})
        self.assertEqual(code, 200, body)
        args = encode.call_args.args
        self.assertIsNone(args[1])          # 右臂明确 mode=0
        self.assertIsNotNone(args[3])       # 左臂仍以 mode=2 保持原目标
        self.assertEqual(tuple(args[3]), tuple(app.Q_START_LEFT))
        sender.sock.sendto.assert_called_once_with(b'right-hold', app.UDP_TARGET)
        self.assertIs(sender.entries['left'], left_entry)
        self.assertEqual(sender.owner_left, 'left-owner')
        self.assertTrue(sender.vr_left_on)
        self.assertEqual(sender.transfer_status()['state'], 'running')
        self.assertIsNone(sender.entries['right'])

    def test_left_default_position_has_complete_v3_solution(self):
        app = self.app
        q, err = app.solve_level_j5_pose_user(list(app.SENDER.left_target),
                                              app.QLEVEL, side='left')
        self.assertIsNotNone(q, err)
        self.assertIsNone(err)


def app_wait_seconds(app):
    return app.VR_RELEASE_WAIT_S


if __name__ == '__main__':
    unittest.main()

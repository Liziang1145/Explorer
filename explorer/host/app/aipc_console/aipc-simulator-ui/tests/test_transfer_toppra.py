"""X／VLA 四段 TOPP-RA 接入测试；不连接硬件。"""
import importlib
import math
import pathlib
import sys
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from console_runtime import StopInterlock
import transfer_trajectory


class TransferToppraTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch('socket.socket'), patch('threading.Thread.start'),
                        patch('subprocess.run', side_effect=AssertionError('real subprocess forbidden'))]
        for item in self.patches:
            item.start()
        self.app = importlib.import_module('arm_console')
        self.app.SAFETY = StopInterlock()
        self.app.SENDER = self.app.ControlSender()
        self.base = Mock()
        self.patch_base = patch.object(self.app, 'BASE_UDP', self.base)
        self.patch_base.start()
        self.patch_ssh = patch.object(self.app, 'kr260', return_value=(0, 'deploy: STOPPED'))
        self.ssh = self.patch_ssh.start()
        self.token = self.app.SAFETY.epoch
        transfer_trajectory.clear_cache()
        self.original = tuple(math.radians(v) for v in (10, 80, -30, -20, -50, 5))

    def tearDown(self):
        self.patch_ssh.stop()
        self.patch_base.stop()
        for item in reversed(self.patches):
            item.stop()

    def test_four_segments_use_toppra_and_exact_reverse_geometry(self):
        app = self.app

        def fast_plan(_app, _geometry, current, target, forward_leg):
            middle = [(a+b)/2 for a, b in zip(current, target)]
            return {'times': [0.0, 0.1, 0.2], 'q': [list(current), middle, list(target)],
                    'duration_s': 0.2, 'planner': 'TOPP-RA', 'forward_leg': forward_leg}

        with patch.object(transfer_trajectory, '_build', side_effect=fast_plan):
            forward_original = transfer_trajectory.plan(self.original, app.Q_START_LEFT, 'original_home')
            forward_pos3 = transfer_trajectory.plan(app.Q_START_LEFT, app.Q_LEFT_POS3, 'home_pos3')
            return_home = transfer_trajectory.plan(app.Q_LEFT_POS3, app.Q_START_LEFT, 'pos3_home')
            return_original = transfer_trajectory.plan(app.Q_START_LEFT, self.original, 'home_original')
        self.assertEqual(return_home['q'], list(reversed(forward_pos3['q'])))
        self.assertEqual(return_original['q'], list(reversed(forward_original['q'])))
        for result, start, target in (
                (forward_original, self.original, app.Q_START_LEFT),
                (forward_pos3, app.Q_START_LEFT, app.Q_LEFT_POS3),
                (return_home, app.Q_LEFT_POS3, app.Q_START_LEFT),
                (return_original, app.Q_START_LEFT, self.original)):
            self.assertEqual(result['planner'], 'TOPP-RA')
            self.assertEqual(len(result['times']), len(result['q']))
            self.assertGreater(result['duration_s'], 0.0)
            for a, b in zip(result['q'][0], start):
                self.assertAlmostEqual(a, b, places=8)
            for a, b in zip(result['q'][-1], target):
                self.assertAlmostEqual(a, b, places=8)

    def test_x_and_vla_route_all_four_legs_through_same_planner(self):
        for source in ('vr', 'vla'):
            with self.subTest(source=source):
                sender = self.app.SENDER
                original_deg = [math.degrees(v) for v in self.original]
                with patch.object(self.app, 'left_read', return_value=(True, original_deg)), \
                     patch.object(sender, '_move_and_wait', return_value=True) as move, \
                     patch.object(self.app, 'VR_RELEASE_WAIT_S', 0.0), \
                     patch('threading.Thread') as thread:
                    sender._request_preset('left', source=source, resume_vr=(source == 'vr'))
                    thread.call_args.kwargs['target']()
                self.assertEqual([call.args[1] for call in move.call_args_list], [
                    'toppra_original_home', 'toppra_home_pos3',
                    'toppra_pos3_home', 'toppra_home_original'])

    def test_trajectory_does_not_complete_at_an_intermediate_reference(self):
        start = [0.0] * 6
        target = [0.0, 0.2, -0.2, 0.1, -0.1, 0.1]
        middle = [(a+b)/2 for a, b in zip(start, target)]
        trajectory = {'times': [0.0, 0.1, 0.2], 'q': [start, middle, target]}
        now = time.monotonic()
        entry = self.app.EntrySequence(start, target, now, trajectory=trajectory)
        entry.observe(start, now+0.01, now+0.01)
        entry.observe(middle, now+0.06, now+0.06)
        self.assertNotEqual(entry.phase, 'done')
        entry.observe(target, now+0.21, now+0.21)
        entry.observe(target, now+0.32, now+0.32)
        entry.observe(target, now+0.75, now+0.75)
        self.assertEqual(entry.phase, 'done')

    def test_plan_failure_rejects_motion_without_fallback(self):
        sender = self.app.SENDER
        which = 'toppra_original_home'
        self.app.MOVE_TARGETS[('left', which)] = list(self.app.Q_START_LEFT)
        data = {'client': 'offline-test', 'safety_epoch': self.token,
                'controls': {'mode': 'left_joints', 'move': which}}
        with patch.object(self.app, 'deploy_running', return_value=True), \
             patch.object(self.app, 'left_read', return_value=(True, [math.degrees(v) for v in self.original])), \
             patch.object(self.app.transfer_trajectory, 'plan', side_effect=ValueError('offline infeasible')):
            body, code = sender._call_move('left', data)
        self.assertEqual(code, 409)
        self.assertIn('未发送运动指令', body['error'])
        self.assertIsNone(sender.entries['left'])
        self.assertIsNone(sender.owner_left)


if __name__ == '__main__':
    unittest.main()

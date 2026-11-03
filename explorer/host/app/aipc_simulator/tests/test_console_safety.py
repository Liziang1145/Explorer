"""No hardware: every SSH command, socket and background worker is mocked."""
import importlib
import io
import json
import pathlib
import sys
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from console_runtime import StopInterlock, BaseFeedback, decode_base_feedback


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch('socket.socket'), patch('threading.Thread.start'),
                        patch('subprocess.run', side_effect=AssertionError('real subprocess forbidden'))]
        for p in self.patches: p.start()
        self.app = importlib.import_module('arm_console')
        self.app.SAFETY = StopInterlock()
        self.app.SENDER = self.app.ControlSender()
        self.base = Mock()
        self.patch_base = patch.object(self.app, 'BASE_UDP', self.base)
        self.patch_base.start()
        self.patch_ssh = patch.object(self.app, 'kr260', return_value=(0, 'deploy: STOPPED'))
        self.ssh = self.patch_ssh.start()
        self.token = self.app.SAFETY.epoch

    def tearDown(self):
        self.patch_ssh.stop(); self.patch_base.stop()
        for p in reversed(self.patches): p.stop()

    def post(self, path, data):
        h = object.__new__(self.app.Handler)
        h.path = path
        body = json.dumps(data).encode()
        h.headers = {'Content-Length': str(len(body))}
        h.rfile = io.BytesIO(body)
        h._reply = Mock()
        h.do_POST()
        args = h._reply.call_args.args
        return args[0], args[1] if len(args) > 1 else 200

    def test_epoch_and_latch_reject_old_commands(self):
        s = self.app.SAFETY
        s.require({'safety_epoch': self.token})
        stopped = s.stop()
        with self.assertRaises(ValueError): s.require({'safety_epoch': self.token})
        with self.assertRaises(ValueError): s.resume({'safety_epoch': stopped})
        s.complete(stopped)
        new = s.resume({'safety_epoch': stopped})
        self.assertFalse(new['stopped'])
        with self.assertRaises(ValueError): s.require({'safety_epoch': self.token})
        s.require({'safety_epoch': new['epoch']})

    def test_stop_covers_base_both_arms_and_vr(self):
        sender = self.app.SENDER
        sender.owner = sender.owner_left = 'offline-owner'
        sender.vr_on = sender.vr_left_on = True
        state, code = self.post('/api/stop_all', {})
        self.assertEqual(code, 202); self.assertTrue(state['stopped'])
        pkt = json.loads(self.base.sendto.call_args.args[0])
        self.assertEqual(pkt, dict(vx=0, vy=0, wz=0, enable=False, rc=False))
        sender.sock.reset_mock(); sender._tick(); sender.sock.sendto.assert_not_called()
        self.app.finish_stop_all(state['epoch'])
        self.assertIsNone(sender.owner); self.assertIsNone(sender.owner_left)
        self.assertFalse(sender.vr_on or sender.vr_left_on)
        self.assertFalse(self.app.SAFETY.pending)
        self.assertEqual(self.ssh.call_args_list[0].args, ('deploy_stop',))
        self.assertIn('进程已停止', self.app.SAFETY.results['arms'])

    def test_failed_stop_stays_latched_and_reports_both_channels(self):
        self.base.sendto.side_effect = OSError('offline UDP failure')
        self.ssh.return_value = (1, 'SSH failed')
        s, _ = self.post('/api/stop_all', {})
        self.app.finish_stop_all(s['epoch'])
        self.assertTrue(self.app.SAFETY.stopped)
        self.assertIn('失败', self.app.SAFETY.results['base'])
        self.assertIn('未确认', self.app.SAFETY.results['arms'])

    def test_latched_post_blocks_start_and_base_but_allows_zero(self):
        self.app.SAFETY.stop()
        _, code = self.post('/api/action', {'action':'enable','safety_epoch':self.token})
        self.assertEqual(code,409); self.ssh.assert_not_called()
        _, code = self.post('/api/control', {'action':'start','client':'offline-owner','safety_epoch':self.token})
        self.assertEqual(code,409)
        _, code = self.post('/api/base_cmd', {'enable':True,'vx':.2,'safety_epoch':self.token})
        self.assertNotEqual(code,200); self.base.sendto.assert_not_called()
        _, code = self.post('/api/base_cmd', {'enable':False,'vx':.2})
        self.assertEqual(code,200)
        self.assertEqual(json.loads(self.base.sendto.call_args.args[0])['vx'],0)

    def test_ready_pose_is_blocked_on_both_sides(self):
        # 旧「预备位」动作已废弃：两条旧指令都必须拒绝，并指向新的 move=start|zero 通道
        for action in ['zero','zero_left']:
            d, code = self.post('/api/action', {'action':action,'safety_epoch':self.token})
            self.assertEqual(code,409); self.assertIn('已废弃',d['error'])
            self.assertIn('move=start|zero',d['error'])
        self.ssh.assert_not_called()

    def test_prepare_partial_failure_is_failure(self):
        self.ssh.side_effect=[(0,'can1 missing'),(0,'can1: MISSING\ncan2: can2 UP\ndeploy: STOPPED')]
        d, code = self.post('/api/action', {'action':'prepare','safety_epoch':self.token})
        self.assertEqual(code,409); self.assertFalse(d['ok'])

    def test_prepare_accepts_fpga_can_for_both_arms(self):
        self.ssh.side_effect=[(0,'can2 up (FPGA_CAN1)\ncan1 up (FPGA_CAN0)'),
                              (0,'can2: FPGA_CAN1 UP\ncan1: FPGA_CAN0 UP\ndeploy: STOPPED')]
        d, code = self.post('/api/action', {'action':'prepare','safety_epoch':self.token})
        self.assertEqual(code,200,d)
        self.assertTrue(d['ok'])
        self.assertIn('FPGA_CAN0',self.app.LEFT_READ_PY)
        self.assertIn('FPGA_CAN1',self.app.RIGHT_READ_PY)
        self.assertNotIn('FPGA_CAN0',self.app.RIGHT_READ_PY)

    def test_enable_never_sends_ready_pose(self):
        for action in ['enable','enable_left']:
            self.post('/api/action', {'action':action,'safety_epoch':self.token})
        self.assertEqual([c.args for c in self.ssh.call_args_list],[('enable',),('enable_left',)])

    def test_base_submission_not_feedback_and_invalid_numbers_rejected(self):
        d, code = self.post('/api/base_cmd', {'enable':True,'vx':.2,'safety_epoch':self.token})
        self.assertEqual(code,200);self.assertFalse(d['execution_confirmed'])
        self.base.reset_mock()
        for value in [float('nan'),float('inf'),'0.3',True]:
            _,code=self.post('/api/base_cmd',{'enable':True,'vx':value,'safety_epoch':self.token})
            self.assertEqual(code,400)
        self.base.sendto.assert_not_called()

    def test_feedback_checksum_sign_and_expiry(self):
        # Independent packed vector: vx=-.1 m/s, vy=.2 m/s, angular raw=-1.5.
        x,z,y=(-100)&65535,(-150)&65535,200
        data=bytearray([8|((x&15)<<4),(x>>4)&255,((x>>12)&15)|((z&15)<<4),(z>>4)&255,((z>>12)&15)|((y&15)<<4),(y>>4)&255,(y>>12)&15,0])
        for b in data[:7]:data[7]^=b
        d=decode_base_feedback(data)
        self.assertEqual((d['vx'],d['vy'],d['angular_raw']),(-.1,.2,-1.5))
        data[7]^=1
        with self.assertRaises(ValueError):decode_base_feedback(data)
        f=BaseFeedback('offline');f.sample=d;f.error=None;f.received=time.monotonic()
        self.assertTrue(f.status(refresh=False)['fresh'])
        f.received-=3
        self.assertIsNone(f.status(refresh=False)['feedback'])


if __name__ == '__main__': unittest.main()

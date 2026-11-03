"""退出示教 UI/API 离线测试：socket、SSH 与全部实车通道均为替身。"""
import importlib
import io
import json
import pathlib
import struct
import sys
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


class FakeSocket:
    def __init__(self, feedback):
        self.feedback = list(feedback)
        self.bound = None
        self.sent = []

    def bind(self, address):
        self.bound = address

    def settimeout(self, _timeout):
        pass

    def send(self, frame):
        self.sent.append(frame)

    def recvfrom(self, _size):
        if not self.feedback:
            raise socket_timeout
        return self.feedback.pop(0), ('ignored', 0)


socket_timeout = type('timeout', (OSError,), {})


def execute_remote(script, feedback):
    sock = FakeSocket(feedback)
    fake_socket = types.SimpleNamespace(
        PF_CAN=29, SOCK_RAW=3, CAN_RAW=1, socket=lambda *args: sock,
        timeout=socket_timeout)
    clock = [0.0]
    fake_time = types.SimpleNamespace(sleep=lambda s: clock.__setitem__(0, clock[0] + s),
                                      monotonic=lambda: clock[0])
    with patch.dict(sys.modules, {'socket': fake_socket, 'time': fake_time}), \
         patch('sys.stdout', new=io.StringIO()) as stdout:
        with unittest.TestCase().assertRaises(SystemExit) as exited:
            exec(compile(script, '<remote-exit-teach>', 'exec'), {})
    return exited.exception.code, stdout.getvalue(), sock


class ExitTeachTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [patch('socket.socket'), patch('threading.Thread.start'),
                       patch('subprocess.run', side_effect=AssertionError('real subprocess forbidden'))]
        for item in cls.patches:
            item.start()
        cls.app = importlib.import_module('arm_console')

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()

    def setUp(self):
        self.app.SAFETY = self.app.StopInterlock()
        self.app.SENDER = self.app.ControlSender()
        self.token = self.app.SAFETY.epoch

    def post(self, action):
        handler = object.__new__(self.app.Handler)
        handler.path = '/api/action'
        body = json.dumps({'action': action, 'safety_epoch': self.token}).encode()
        handler.headers = {'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler._reply = Mock()
        handler.do_POST()
        args = handler._reply.call_args.args
        return args[0], args[1] if len(args) > 1 else 200

    def test_left_and_right_frames_interfaces_and_confirmation(self):
        for side, interface in [('left', 'FPGA_CAN0'), ('right', 'FPGA_CAN1')]:
            with self.subTest(side=side):
                good = struct.pack('=IB3x8s', 0x2A1, 8, bytes([1, 1, 0, 0, 0, 0, 0, 0]))
                code, output, sock = execute_remote(self.app.exit_teach_script(interface), [good])
                self.assertEqual(code, 0)
                self.assertIn(interface, output)
                self.assertEqual(sock.bound, (interface,))
                frames = [struct.unpack('=IB3x8s', frame) for frame in sock.sent]
                self.assertEqual([frame[0] for frame in frames], [0x150, 0x151])
                self.assertEqual(list(frames[0][2]), [0, 0, 2, 0, 0, 0, 0, 0])
                self.assertEqual(list(frames[1][2]), [1, 1, 0, 0, 0, 0, 0, 0])

    def test_missing_or_wrong_feedback_is_not_success(self):
        for feedback, expected in [([], 3),
                                   ([struct.pack('=IB3x8s', 0x2A1, 8, bytes([2, 0, 0, 0, 0, 0, 0, 0]))], 2)]:
            clock = [0.0]
            sock = FakeSocket(feedback)
            fake_socket = types.SimpleNamespace(PF_CAN=29, SOCK_RAW=3, CAN_RAW=1,
                                                socket=lambda *args: sock, timeout=socket_timeout)
            fake_time = types.SimpleNamespace(sleep=lambda s: None,
                monotonic=lambda: clock.__setitem__(0, clock[0] + 0.2) or clock[0])
            with patch.dict(sys.modules, {'socket': fake_socket, 'time': fake_time}), \
                 patch('sys.stdout', new=io.StringIO()):
                with self.assertRaises(SystemExit) as exited:
                    exec(self.app.exit_teach_script('FPGA_CAN0'), {})
            self.assertEqual(exited.exception.code, expected)

    def test_invalid_side_never_invokes_subprocess(self):
        with patch.object(self.app.subprocess, 'run') as run:
            code, output = self.app.exit_teach_can('invalid')
        self.assertNotEqual(code, 0)
        self.assertIn('无效', output)
        run.assert_not_called()

    def test_api_requires_stopped_deploy_and_idle_sessions(self):
        with patch.object(self.app, 'deploy_running', return_value=True), \
             patch.object(self.app, 'exit_teach_can') as command:
            result, code = self.post('exit_teach_left')
        self.assertEqual(code, 409)
        self.assertIn('deploy', result['error'])
        command.assert_not_called()

        self.app.SENDER.owner_left = 'test-follow'
        with patch.object(self.app, 'deploy_running', return_value=False), \
             patch.object(self.app, 'exit_teach_can') as command:
            result, code = self.post('exit_teach_left')
        self.assertEqual(code, 409)
        self.assertIn('会话', result['error'])
        command.assert_not_called()

    def test_api_success_requires_confirmation_and_stop_latch_blocks(self):
        with patch.object(self.app, 'deploy_running', return_value=False), \
             patch.object(self.app, 'exit_teach_can', return_value=(3, 'no confirmation')) as command:
            result, code = self.post('exit_teach')
        self.assertEqual(code, 500)
        self.assertFalse(result['ok'])
        command.assert_called_once_with('right')

        self.app.SAFETY.stop()
        with patch.object(self.app, 'exit_teach_can') as command:
            _, code = self.post('exit_teach_left')
        self.assertEqual(code, 409)
        command.assert_not_called()

    def test_buttons_and_script_version_present(self):
        root = pathlib.Path(self.app.__file__).parent
        html = (root / 'simulator.html').read_text(encoding='utf-8')
        script = (root / 'simulator.js').read_text(encoding='utf-8')
        for button in ('con-exit-teach', 'lcon-exit-teach'):
            self.assertIn('id="' + button + '"', html)
            self.assertIn("$('" + button + "').onclick", script)
        self.assertIn('/simulator.js?v=61', html)


if __name__ == '__main__':
    unittest.main()

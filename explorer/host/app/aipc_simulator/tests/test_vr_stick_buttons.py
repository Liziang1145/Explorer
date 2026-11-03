"""key15 左右摇杆按下 L3/R3：解析校验、VrFeed 快照、遥测 mode_detail。全部离线。"""
import base64
import importlib
import pathlib
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import vr_stick_buttons


def cbor(v):
    if isinstance(v, dict):
        return bytes([0xa0 + len(v)]) + b''.join(cbor(k) + cbor(x) for k, x in v.items())
    if isinstance(v, (tuple, list)):
        return bytes([0x80 + len(v)]) + b''.join(cbor(x) for x in v)
    if type(v) is int and 0 <= v < 24:
        return bytes([v])
    return b'\xfb' + struct.pack('>d', float(v))


def packet(extra=None):
    body_map = {2: 23}
    if extra:
        body_map.update(extra)
    body = cbor(body_map)
    head = bytearray(64)
    head[:4] = b'TLZ2'
    struct.pack_into('>H', head, 6, 0x0104)
    struct.pack_into('>I', head, 12, len(body))
    return bytes(head) + body


class ParseTests(unittest.TestCase):
    def test_valid_full(self):
        s = vr_stick_buttons.parse({15: {0: 1, 1: 3, 2: 3}})
        self.assertEqual(s, {'revision': 1, 'valid': 3, 'pressed': 3})

    def test_missing_returns_none(self):
        self.assertIsNone(vr_stick_buttons.parse({}))
        self.assertIsNone(vr_stick_buttons.parse(None))
        self.assertIsNone(vr_stick_buttons.parse({15: None}))

    def test_invalid_variants(self):
        cases = [
            {0: 2, 1: 3, 2: 3},      # revision 错
            {0: 1, 1: 4, 2: 0},      # valid 高位越界
            {0: 1, 1: 3, 2: 4},      # pressed 高位越界
            {0: 1, 1: 1, 2: 2},      # pressed 非 valid 子集
            {0: 1, 1: 3},            # 缺 pressed
            {0: 1, 2: 3},            # 缺 valid
            {0: 1, 1: 3, 2: 3, 4: 0},# 未知 key
            {0: 1, 1: True, 2: 0},   # bool 不是 int
            'junk',
        ]
        for bad in cases:
            self.assertIsNone(vr_stick_buttons.parse({15: bad}), str(bad))

    def test_pressed_helper(self):
        s = vr_stick_buttons.parse({15: {0: 1, 1: 3, 2: 2}})
        self.assertFalse(vr_stick_buttons.pressed(None, 0))
        self.assertFalse(vr_stick_buttons.pressed(s, 0))   # L3 未按
        self.assertTrue(vr_stick_buttons.pressed(s, 1))    # R3 按住
        # 该 bit 本帧不可读（valid=0）时不得推断为松开以外的状态，持续语义下按 False 处理
        s2 = vr_stick_buttons.parse({15: {0: 1, 1: 2, 2: 2}})
        self.assertFalse(vr_stick_buttons.pressed(s2, 0))

    def test_summary(self):
        s = vr_stick_buttons.parse({15: {0: 1, 1: 3, 2: 1}})
        snap = vr_stick_buttons.summary(s)
        self.assertTrue(snap['available'])
        self.assertEqual(snap['pressed_names'], ['L3'])
        self.assertTrue(snap['bits']['R3']['valid'])
        self.assertFalse(snap['bits']['R3']['pressed'])
        self.assertFalse(vr_stick_buttons.summary(None)['available'])


class FeedAndTelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.net = patch('socket.socket')
        cls.sock = cls.net.start()
        cls.threads = patch('threading.Thread.start')
        cls.threads.start()
        cls.ssh = patch('subprocess.run', side_effect=AssertionError('SSH forbidden in offline tests'))
        cls.ssh.start()
        cls.app = importlib.import_module('arm_console')

    @classmethod
    def tearDownClass(cls):
        cls.sock.return_value.sendto.assert_not_called()
        cls.sock.return_value.connect.assert_not_called()
        cls.net.stop(); cls.threads.stop(); cls.ssh.stop()

    def feed_once(self, feed, response):
        with patch.object(feed, '_fetch', return_value=response), \
             patch.object(self.app.time, 'sleep', side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):
                feed._loop()

    def test_feed_carries_key15(self):
        f = self.app.VrFeed()
        raw = packet({15: {0: 1, 1: 3, 2: 3}})
        response = dict(fresh=True, age_ms=20,
                        event=dict(version=1, packet_base64=base64.b64encode(raw).decode()))
        self.feed_once(f, response)
        snap = f.stick_buttons_snapshot()
        self.assertTrue(snap['available'])
        self.assertEqual(snap['pressed_names'], ['L3', 'R3'])
        self.assertTrue(snap['fresh'])
        # latest() 第 13 项透传
        self.assertEqual(f.latest()[12], {'revision': 1, 'valid': 3, 'pressed': 3})

    def test_feed_key15_missing_is_unavailable_not_release(self):
        f = self.app.VrFeed()
        raw = packet()
        response = dict(fresh=True, age_ms=20,
                        event=dict(version=1, packet_base64=base64.b64encode(raw).decode()))
        self.feed_once(f, response)
        snap = f.stick_buttons_snapshot()
        self.assertFalse(snap['available'])
        self.assertTrue(snap['fresh'])

    def test_telemetry_mode_detail_and_stick_buttons(self):
        t = self.app.SENDER.telemetry()
        self.assertIn('mode_detail', t)
        md = t['mode_detail']
        self.assertIn(md['mode'], ('arms', 'base'))
        self.assertEqual(md['arm_mode'], md['mode'] == 'arms')
        self.assertEqual(md['base_mode'], md['mode'] == 'base')
        self.assertEqual(md['base_sub_text'],
                         self.app.BASE_SUB_TEXT[md['base_sub']])
        self.assertEqual(md['vr_motion_scale_text'],
                         self.app.SENDER.VR_SCALE_NAMES[md['vr_motion_scale']])
        # 顶层兼容字段仍在
        self.assertEqual(t['mode'], md['mode'])
        self.assertEqual(t['vr_motion_scale'], md['vr_motion_scale'])
        self.assertIn('stick_buttons', t)
        self.assertIn('available', t['stick_buttons'])


if __name__ == '__main__':
    unittest.main()

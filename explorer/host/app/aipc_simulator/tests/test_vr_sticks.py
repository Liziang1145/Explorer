"""Offline only: network sockets, SSH and background threads are intercepted."""
import base64
import importlib
import math
import pathlib
import struct
import sys
import unittest
from unittest.mock import patch, Mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vr_sticks import decode_stick, preview


def cbor(v):
    if isinstance(v, dict):
        return bytes([0xa0 + len(v)]) + b''.join(cbor(k) + cbor(x) for k, x in v.items())
    if isinstance(v, (tuple, list)):
        return bytes([0x80 + len(v)]) + b''.join(cbor(x) for x in v)
    if type(v) is int and 0 <= v < 24:
        return bytes([v])
    return b'\xfb' + struct.pack('>d', float(v))


def packet(analog, extra=None):
    body_map = {2: 23, 11: analog}
    if extra:
        body_map.update(extra)
    body = cbor(body_map)
    head = bytearray(64)
    head[:4] = b'TLZ2'
    struct.pack_into('>H', head, 6, 0x0104)
    struct.pack_into('>I', head, 12, len(body))
    return bytes(head) + body


class StickTests(unittest.TestCase):
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

    def mapped(self, left=(0., 0.), right=(0., 0.), **kwargs):
        return preview(left, right, fresh=kwargs.get('fresh', True), input_state=kwargs.get('state', 23))

    def test_analog_validation(self):
        for value in (None, [], [0], [0, 0, 0], [True, 0], ['1', 0], [math.nan, 0], [math.inf, 0], [1.01, 0]):
            self.assertIsNone(decode_stick(value))
        self.assertEqual(decode_stick([-.921, -.389]), (-.921, -.389))

    def test_cardinal_and_diagonal(self):
        self.assertAlmostEqual(self.mapped((0, 1))['intent']['vx'], .3)
        self.assertAlmostEqual(self.mapped((1, 0))['intent']['vy'], -.3)
        d = self.mapped((1, 1))['intent']
        self.assertGreater(d['vx'], 0); self.assertLess(d['vy'], 0)
        self.assertAlmostEqual(math.hypot(d['vx'], d['vy']), .3)
        self.assertLess(self.mapped((0, .5))['intent']['vx'], .3)

    def test_yaw_and_unused_vertical(self):
        self.assertAlmostEqual(self.mapped(right=(1, 0))['intent']['wz'], -.5)
        self.assertEqual(self.mapped(right=(0, 1))['intent']['wz'], 0)

    def test_deadzone_and_release(self):
        self.assertEqual(self.mapped((.03, -.04), (.08, 0))['intent'], dict(vx=0, vy=0, wz=0))
        self.assertEqual(self.mapped()['intent'], dict(vx=0, vy=0, wz=0))

    def test_stale_missing_tracking_and_fields(self):
        for d in (self.mapped((1, 1), fresh=False), self.mapped((1, 1), state=21),
                  self.mapped((1, 1), state=7), self.mapped(None)):
            self.assertFalse(d['usable'])
            self.assertEqual(d['intent'], dict(vx=0, vy=0, wz=0))
            self.assertFalse(d['execution_enabled'])

    def test_translation_priority_is_explicit(self):
        d = self.mapped((0, 1), (1, 0))
        self.assertTrue(d['simultaneous'])
        self.assertNotEqual(d['intent']['wz'], 0)
        self.assertEqual(d['relay_preview']['wz'], 0)

    def test_parser_preserves_old_fields(self):
        d = self.app.parse_operator_packet(packet({1: .8, 2: .9, 3: .2, 4: .3, 5: [.4, .5], 6: [-.6, .7], 7: 63}))
        self.assertEqual(d[:9], (23, None, None, .3, .9, None, None, .2, .8))
        self.assertEqual(d[9:11], ((.4, .5), (-.6, .7)))
        self.assertIsNone(d[11])          # key13 缺失 -> None
        self.assertIsNone(d[12])          # key15 缺失 -> None
        self.assertEqual(self.app.parse_operator_packet(packet({}))[9:11], (None, None))
        with self.assertRaises(ValueError):
            self.app.parse_operator_packet(packet({}) + b'bad')

    def test_parser_key15_stick_buttons(self):
        # 合规：L3+R3 都有效且都按住（extra 走顶层 key15，analog 留空 dict）
        d = self.app.parse_operator_packet(packet({}, {15: {0: 1, 1: 3, 2: 3}}))
        self.assertEqual(d[12], {'revision': 1, 'valid': 3, 'pressed': 3})
        # 只按住 R3
        d = self.app.parse_operator_packet(packet({}, {15: {0: 1, 1: 3, 2: 2}}))
        self.assertEqual(d[12]['pressed'], 2)
        # 合规性失败全部 -> None：revision 错 / 高位越界 / pressed 非 valid 子集
        for bad in ({0: 2, 1: 3, 2: 3}, {0: 1, 1: 4, 2: 0}, {0: 1, 1: 1, 2: 2},
                    {0: 1, 1: 3}, {0: 1, 1: 3, 2: 1.5}):
            d = self.app.parse_operator_packet(packet({}, {15: bad}))
            self.assertIsNone(d[12], f'{bad} 必须解析为 None')

    def feed_once(self, feed, response):
        with patch.object(feed, '_fetch', return_value=response), patch.object(self.app.time, 'sleep', side_effect=InterruptedError):
            with self.assertRaises(InterruptedError):
                feed._loop()

    def test_feed_staleness_and_unchanged_snapshot(self):
        f = self.app.VrFeed()
        raw = packet({5: [.4, .5], 6: [.3, 0]})
        response = dict(fresh=True, age_ms=20, event=dict(version=1, packet_base64=base64.b64encode(raw).decode()))
        self.feed_once(f, response)
        self.assertTrue(f.sticks()['usable'])
        self.assertEqual(len(f.latest()), 13, 'legacy arm feed tuple remains compatible (+stick_buttons)')
        received = f.stick_recv_mono
        self.feed_once(f, response)
        self.assertEqual(f.stick_recv_mono, received, 'duplicate snapshot must not refresh age')
        self.assertFalse(f.sticks(now=received + self.app.VR_FRESH_S + .01)['usable'])
        self.feed_once(f, dict(response, fresh=False))
        self.assertFalse(f.sticks()['usable'])

    def test_bad_age_and_fetch_failure(self):
        f = self.app.VrFeed()
        raw = base64.b64encode(packet({5: [1, 0], 6: [0, 0]})).decode()
        self.feed_once(f, dict(fresh=True, event=dict(version=1, packet_base64=raw)))
        self.assertFalse(f.sticks()['usable'])
        self.feed_once(f, None)
        self.assertFalse(f.sticks()['fresh'])

    def test_readonly_endpoint(self):
        handler = object.__new__(self.app.Handler)
        handler.path = '/api/vr_sticks'
        handler._reply = Mock()
        handler.do_GET()
        self.assertFalse(handler._reply.call_args.args[0]['execution_enabled'])

    def test_historical_recordings(self):
        total = nonzero = 0
        folder = ROOT.parent.parent / '工具' / '标定数据'
        for p in folder.glob('*.tlzraw'):
            data = p.read_bytes(); pos = 0
            while True:
                i = data.find(b'TLZ2', pos)
                if i < 0: break
                pos = i + 4
                if i < 4 or i + 64 > len(data): continue
                size = struct.unpack('>I', data[i-4:i])[0]
                length = struct.unpack('>I', data[i+12:i+16])[0]
                if size != 64 + length or i + size > len(data) or data[i+6:i+8] != b'\x01\x04': continue
                parsed = self.app.parse_operator_packet(data[i:i+size])
                left, right = parsed[9], parsed[10]
                self.assertIsNotNone(left); self.assertIsNotNone(right)
                d = self.mapped(left, right, state=parsed[0])
                self.assertFalse(d['execution_enabled'])
                self.assertLessEqual(math.hypot(d['intent']['vx'], d['intent']['vy']), .300001)
                total += 1; nonzero += bool(any(left) or any(right))
        self.assertGreater(total, 10000); self.assertGreater(nonzero, 100)
        print(f'Historical replay: {total} frames, {nonzero} with nonzero stick input; no network.')


if __name__ == '__main__':
    unittest.main()

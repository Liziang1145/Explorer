# -*- coding: utf-8 -*-
"""审计清单修复的回归测试：C03 / C08 / C18 / C22。

对应《代码遗留问题清单》的关闭条件，尽量用真实方法驱动，不把出错的方法替换成理想实现。
"""
import math
import os
import sys
import threading
import time
import types
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.dirname(HERE)
sys.path.insert(0, UI)

_saved_thread = threading.Thread


class _NoThread:
    def __init__(self, *a, **k):
        pass

    def start(self):
        pass


threading.Thread = _NoThread
import arm_console as app  # noqa: E402
threading.Thread = _saved_thread


class _Stop(BaseException):
    """在真实循环跑完一拍后中断（BaseException 不会被 except Exception 吞掉）。"""


def _rot(axis, ang):
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    x, y, z = x / n, y / n, z / n
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return ((c + x * x * C, x * y * C - z * s, x * z * C + y * s),
            (y * x * C + z * s, c + y * y * C, y * z * C - x * s),
            (z * x * C - y * s, z * y * C + x * s, c + z * z * C))


def _Rmul(A, B):
    return tuple(tuple(sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)) for i in range(3))


# ======================= C03 =======================
class C03SticksTest(unittest.TestCase):
    """sticks() 重复定义导致 VR 底盘循环解包失败。"""

    def _feed(self):
        f = app.VrFeed.__new__(app.VrFeed)
        f.lock = threading.Lock()
        f.version = 1
        f.error = None
        f.istate = 0
        f.lstick, f.rstick = (0.0, 0.5), (0.4, 0.0)
        f.lsidegrip, f.sidegrip = 1.0, 0.0
        f.stick_recv_mono = time.monotonic()
        f.stick_source_fresh = True
        return f

    def test_raw_snapshot_is_dict_with_validated_fields(self):
        snap = self._feed().raw_snapshot()
        self.assertIsInstance(snap, dict, 'raw_snapshot 必须是字典，不能再是会被覆盖的同名元组')
        self.assertTrue(snap['fresh'])
        self.assertEqual(snap['lstick'], (0.0, 0.5))
        self.assertGreaterEqual(snap['lsidegrip'], 0.5)
        self.assertIsNone(snap['error'])

    def test_stale_stick_is_not_fresh(self):
        snap = self._feed().raw_snapshot(time.monotonic() + app.VR_FRESH_S + 1.0)
        self.assertFalse(snap['fresh'], '过期摇杆必须标记为不新鲜')

    def test_sticks_and_raw_snapshot_are_two_methods(self):
        self.assertNotEqual(app.VrFeed.sticks, app.VrFeed.raw_snapshot,
                            '内部快照与对外摘要必须是两个方法，不能同名覆盖')
        self.assertIsInstance(self._feed().sticks(), dict)

    def test_base_loop_one_tick_does_not_raise(self):
        """真实 _base_loop 跑一拍：必须能解包（旧代码在这里 ValueError → '底盘驱动异常'）。"""
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s.mode = 'base'
        s.base_state = {}
        s.base_sub = 'a'
        sent = []
        s._send_base_udp = lambda vx, vy, wz, enable, rc=False: sent.append((vx, vy, wz, enable, rc))

        feed = app.VR
        with feed.lock:
            feed.version = 1
            feed.error = None
            feed.istate = 0
            feed.lstick, feed.rstick = (0.0, 0.8), (0.0, 0.0)
            feed.lsidegrip, feed.sidegrip = 1.0, 0.0
            feed.stick_recv_mono = time.monotonic()
            feed.stick_source_fresh = True
            feed.recv_mono = time.monotonic()

        orig_sleep = app.time.sleep
        app.time.sleep = lambda _s: (_ for _ in ()).throw(_Stop())
        try:
            with self.assertRaises(_Stop):
                s._base_loop()
        finally:
            app.time.sleep = orig_sleep

        self.assertEqual(len(sent), 1, '一拍应发送一帧底盘指令')
        self.assertTrue(sent[0][3], '按住侧键应带使能')
        self.assertFalse(sent[0][4], '默认子模式 a 不带 rc 标志')

    def test_base_loop_rc_submode_allows_vx_and_wz(self):
        """RC 子模式（base_sub='b'）：左手油门 + 右手转向可同时非零，且帧带 rc=True。"""
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s.mode = 'base'
        s.base_state = {}
        s.base_sub = 'b'
        sent = []
        s._send_base_udp = lambda vx, vy, wz, enable, rc=False: sent.append((vx, vy, wz, enable, rc))

        feed = app.VR
        with feed.lock:
            feed.version = 1
            feed.error = None
            feed.istate = 0x17          # 头显+双手跟踪有效
            feed.lstick, feed.rstick = (0.0, 0.8), (0.6, 0.0)
            feed.lsidegrip, feed.sidegrip = 1.0, 0.0
            feed.stick_recv_mono = time.monotonic()
            feed.stick_source_fresh = True
            feed.recv_mono = time.monotonic()

        orig_sleep = app.time.sleep
        app.time.sleep = lambda _s: (_ for _ in ()).throw(_Stop())
        try:
            with self.assertRaises(_Stop):
                s._base_loop()
        finally:
            app.time.sleep = orig_sleep

        self.assertEqual(len(sent), 1)
        vx, vy, wz, enable, rc = sent[0]
        self.assertGreater(vx, 0, '左摇杆前推 = 前进')
        self.assertLess(wz, 0, '右摇杆右推 = 顺时针')
        self.assertEqual(vy, 0.0, 'RC 模式不发横移')
        self.assertTrue(rc, 'RC 子模式帧必须带 rc=True')
        self.assertNotIn('异常', s.base_state.get('reason', ''),
                         '不应落入"底盘驱动异常"分支：%r' % s.base_state)


# ======================= C08 =======================
class C08RotationErrorTest(unittest.TestCase):
    def test_rot_err_magnitude_matches_true_angle(self):
        for ang in (0.0, 0.01, 0.5, math.pi - 0.01, math.pi):
            v = app._rot_err(_rot((0.3, -0.5, 0.8), ang))
            got = math.sqrt(sum(x * x for x in v))
            self.assertAlmostEqual(got, ang, places=2, msg='夹角 %.4f 时模长应等于夹角' % ang)

    def test_ori_vee_alone_is_zero_at_pi(self):
        R = _rot((1, 0, 0), math.pi)
        v = app._ori_vee(R)
        self.assertLess(math.sqrt(sum(x * x for x in v)), 1e-6,
                        '原实现（反对称部分）在 π 处为零 —— C08 的根因')
        v2 = app._rot_err(R)
        self.assertAlmostEqual(math.sqrt(sum(x * x for x in v2)), math.pi, places=2)

    def test_ik_does_not_accept_180_degree_pose_mismatch(self):
        p = list(app._mv(app._FR, app._fk(app.QLEVEL)[0]))
        R0 = app._fk(app.QLEVEL)[1]
        Rtgt = _Rmul(_rot((0, 0, 1), math.pi), R0)
        q, err = app.solve_ik_user(p, app.QLEVEL, Rtgt)
        if q is None:
            return
        # 2026-10-25：降级解算（放开翻滚/放开姿态）是合法结果，但必须如实标注，
        # 不得冒充完全收敛；声称完全收敛（err is None）才做真收敛校验
        if err is not None:
            self.assertTrue(err.startswith('降级'), '非完全收敛必须标注降级级别：%s' % err)
            return
        t, R = app._fk(q)
        Rerr = _Rmul(Rtgt, tuple(tuple(R[j][i] for j in range(3)) for i in range(3)))
        tr = Rerr[0][0] + Rerr[1][1] + Rerr[2][2]
        ang = math.acos(max(-1.0, min(1.0, (tr - 1.0) * 0.5)))
        self.assertLess(ang, 5e-3, '声称收敛就必须真收敛：实际夹角 %.4f rad' % ang)

    def test_ik_multiseed_finds_exact_pose_from_far_seed(self):
        """多种子（2026-10-25）：离解很远的种子也应收敛到精确可达位姿。
        构造：QLEVEL 微调 J4/J6 的关节角 → FK 得精确可达位姿 → 用 Q_ZERO 当种子求解。"""
        q0 = list(app.QLEVEL)
        q0[3] += 0.3
        q0[5] += 0.5
        q0 = tuple(max(lo, min(hi, v)) for v, lo, hi in zip(q0, app._QLO, app._QHI))
        t, R = app._fk(q0)
        # 逆变换到底盘系：p_chassis = FR·t − OFF（恒等标定下）
        p = [a - b for a, b in zip(app._mv(app._FR, t), app.OFF)]
        q, err = app.solve_ik_user(p, app.Q_ZERO, R)
        self.assertIsNotNone(q, '精确可达位姿必须有解：%s' % err)
        t2, R2 = app._fk(q)
        self.assertLess(math.sqrt(sum((t2[i]-t[i])**2 for i in range(3))), 1e-3,
                        '解的位置必须真到达')
        if err is None:   # 声称完全收敛时姿态也必须真到
            Rerr = _Rmul(R, tuple(tuple(R2[j][i] for j in range(3)) for i in range(3)))
            tr = Rerr[0][0] + Rerr[1][1] + Rerr[2][2]
            ang = math.acos(max(-1.0, min(1.0, (tr - 1.0) * 0.5)))
            self.assertLess(ang, 5e-3)

    def test_ik_unreachable_reports_residual(self):
        """真不可达目标：必须失败且带残差量级（辅助判断"真不可达"还是"差一点"）。"""
        q, err = app.solve_ik_user([0.49, 0.54, 0.59], app.QLEVEL)   # 距底座约 1m，超出臂展
        self.assertIsNone(q)
        self.assertIn('残差', err)

    def test_ik_fast_path_performance_unchanged(self):
        """跟随热路径回归：当前位附近的可达点应快速完全收敛（旧版约 1~2ms）。"""
        t0 = time.perf_counter()
        q, err = app.solve_ik_user([0.15, 0.30, 0.25], app.QLEVEL)
        dt = time.perf_counter() - t0
        self.assertIsNotNone(q)
        self.assertIsNone(err, '近距可达点不应降级')
        self.assertLess(dt, 0.5, '快路径耗时 %.1fms，疑似误入救援阶段' % (dt * 1000))


# ======================= C18 =======================
class C18RightIkFailureTest(unittest.TestCase):
    def _sender(self):
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s.owner = 'testclient1234'
        s.until = time.monotonic() + 60
        s.owner_left = None
        s.left_until = 0.0
        s.left_joints = None
        s.vr_on = False
        s.vr_left_on = False
        s.grip = 0.0
        s.left_grip = 0.0
        s.joints = [0.1, 0.2, -0.3, 0.0, 0.0, 0.0]
        s.right = [0.2, 0.3, 0.25]
        s.ik_err = None
        s.reason = ''
        s.seq = 1
        s.deadline = 0.0
        s.count = 0
        s.status = lambda: {'ok': True}
        return s

    def test_ik_failure_keeps_old_target_and_returns_409(self):
        s = self._sender()
        old_joints, old_right = list(s.joints), list(s.right)
        orig_solve, orig_require = app.solve_web_j5_rpy_side, app.SAFETY.require
        app.solve_web_j5_rpy_side = lambda *a, **k: (None, '不可达')
        app.SAFETY.require = lambda _d: None          # 跳过会话层，直测 IK 分支
        try:
            data = {'client': 'testclient1234', 'action': 'update',
                    'controls': {'right': [0.9, 0.9, 0.9]}}
            body, code = s._call_follow('update', data)
        finally:
            app.solve_web_j5_rpy_side, app.SAFETY.require = orig_solve, orig_require
        self.assertEqual(code, 409, '右臂 IK 失败必须返回 409（与左臂一致），实际 %r' % (body,))
        self.assertIn('IK', body.get('error', ''))
        self.assertEqual(s.joints, old_joints, '失败不得改写已接受目标')
        self.assertEqual(s.right, old_right, '失败不得更新页面显示目标')


# ======================= C22 =======================
class C22ChassisInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # chassis_relay.py 末尾会直接调用 can_loop()，导入即挂起；
        # 这里剥掉启动那两行后 exec，只测纯函数。
        path = os.path.join(os.path.dirname(UI), 'kr260-side', 'chassis_relay.py')
        src = open(path, encoding='utf-8').read()
        src = src.replace('threading.Thread(target=udp_loop, daemon=True).start()', '')
        src = src.replace('\ncan_loop()\n', '\n')
        src = src.replace('sock_can.bind((CAN_IF,))', 'pass  # 测试环境无 CAN')
        src = src.replace('sock_can = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)',
                          'sock_can = None')

        class _DummySock:
            def __init__(self, *a, **k):
                pass

            def bind(self, *a, **k):
                pass

            def send(self, *a, **k):
                return 8

        cls.ns = {'__name__': 'chassis_relay_test'}
        import socket as _sock
        real = (_sock.socket, getattr(_sock, 'PF_CAN', None), getattr(_sock, 'CAN_RAW', None))
        _sock.socket = _DummySock
        _sock.PF_CAN, _sock.CAN_RAW = 29, 1
        try:
            exec(compile(src, path, 'exec'), cls.ns)
        finally:
            _sock.socket = real[0]
            if real[1] is not None:
                _sock.PF_CAN = real[1]
            if real[2] is not None:
                _sock.CAN_RAW = real[2]

    def test_rejects_nan_and_inf(self):
        for tok in ('NaN', 'Infinity', '-Infinity'):
            with self.assertRaises(ValueError, msg=tok):
                self.ns['parse_command'](('{"vx": %s, "enable": false}' % tok).encode())

    def test_rejects_non_bool_enable(self):
        for body in ('{"vx":0.1,"enable":"false"}', '{"vx":0.1,"enable":0}',
                     '{"vx":0.1,"enable":1}', '{"vx":0.1,"enable":"0"}'):
            with self.assertRaises(ValueError, msg=body):
                self.ns['parse_command'](body.encode())

    def test_rejects_wrong_types_and_non_object(self):
        for body in ('{"vx":"0.5","enable":true}', '[1,2,3]', '"x"'):
            with self.assertRaises(ValueError, msg=body):
                self.ns['parse_command'](body.encode())

    def test_valid_packet_round_trip(self):
        cmd = self.ns['parse_command'](b'{"vx":0.3,"vy":-0.2,"wz":0.1,"enable":true}')
        self.assertAlmostEqual(cmd['vx'], 0.3)
        self.assertAlmostEqual(cmd['vy'], -0.2)
        self.assertAlmostEqual(cmd['wz'], 0.1)
        self.assertTrue(cmd['enable'])
        self.assertGreater(cmd['mono'], 0.0, '必须记录单调时钟用于看门狗')

    def test_clamp_nan_is_zero_not_max(self):
        self.assertEqual(self.ns['clamp'](float('nan'), 0.8), 0.0,
                         'clamp(NaN) 必须是 0，不能是正的最大限值 0.8')


# ======================= C05 =======================
class C05ModeArbitrationTest(unittest.TestCase):
    """模式与控制源缺少统一互斥：底盘模式下仍能触发臂动作 / 网页与 VR 抢底盘。"""

    def _sender(self):
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s.mode = 'base'                       # 底盘模式
        s.entries = {'right': None, 'left': None}
        s.entry_pending = {'right': False, 'left': False}
        s.entry_generation = {'right': 0, 'left': 0}
        s.owner = s.owner_left = None
        s.until = s.left_until = 0.0
        s._move_gate = threading.Lock()
        s.btn_latch = app.arm_buttons.Latch()
        s.error = None
        s.status = lambda: {'ok': True}
        return s

    def test_move_is_refused_in_base_mode(self):
        s = self._sender()
        body, code = s._call_move('right', {'client': 'testclient1234',
                                           'safety_epoch': app.SAFETY.status()['epoch'],
                                           'controls': {'move': 'start'}})
        self.assertEqual(code, 409, body)
        self.assertIn('底盘模式', body.get('error', ''))

    def _fire_A(self, s, safety_stopped=False):
        """喂一帧新鲜的 A 键快照；safety_stopped 控制软件停止联锁。"""
        with unittest.mock.patch.object(
                app.VR, 'buttons',
                return_value={'valid': 15, 'pressed': 1, 'fresh': True}), \
             unittest.mock.patch.object(
                app.SAFETY, 'status',
                return_value={'stopped': safety_stopped, 'epoch': 1}):
            with s.lock:
                s._handle_buttons(0.0)

    def test_preset_button_refused_in_base_mode(self):
        """C05：底盘模式下 A 键不得触发臂动作（含正对照）。"""
        s = self._sender()                        # mode='base'
        with unittest.mock.patch.object(s, '_request_preset') as preset:
            self._fire_A(s)
            preset.assert_not_called()            # 底盘模式：拒绝

        s.mode = 'arms'
        s.btn_latch = app.arm_buttons.Latch()     # 重新武装
        with unittest.mock.patch.object(s, '_request_preset') as preset:
            self._fire_A(s)
            preset.assert_called_once_with('right')   # 双臂模式：放行（正对照）
    def test_web_base_refused_while_vr_drives_base(self):
        old = app.SENDER.mode
        app.SENDER.mode = 'base'
        try:
            with self.assertRaises(ValueError) as cm:
                app.send_base({'enable': False})
        finally:
            app.SENDER.mode = old
        self.assertIn('VR 正在控制底盘', str(cm.exception))

    def test_send_base_rc_passthrough(self):
        """网页底盘指令：rc 字段透传进 UDP 包；非布尔 rc 拒绝；缺省为 False。"""
        sent = []
        old_mode = app.SENDER.mode
        app.SENDER.mode = 'arms'          # 避开 VR/网页底盘互斥
        fake_udp = types.SimpleNamespace(
            sendto=lambda b, addr: sent.append(b))
        try:
            with unittest.mock.patch.object(app, 'BASE_UDP', fake_udp):
                app.send_base({'vx': 0.1, 'vy': 0.0, 'wz': 0.2,
                               'enable': False, 'rc': True})
                app.send_base({'vx': 0.0, 'vy': 0.0, 'wz': 0.0, 'enable': False})
        finally:
            app.SENDER.mode = old_mode
        import json as _json
        pkt1 = _json.loads(sent[0].decode())
        pkt2 = _json.loads(sent[1].decode())
        self.assertIs(pkt1['rc'], True)   # rc=True 透传给 relay（档位 2 自由模式同帧 vx+wz）
        self.assertIs(pkt2['rc'], False)  # 缺省 False，不影响旧行为
        with self.assertRaises(ValueError):
            app.send_base({'vx': 0, 'vy': 0, 'wz': 0, 'enable': False, 'rc': 'yes'})

    def test_set_base_sub_validates_and_zero_beats(self):
        """网页 /api/base_sub 与 VR Y 键共用 set_base_sub：非法值拒绝，切换发零速断使能。"""
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s.base_sub = 'a'
        beats = []
        s._send_base_udp = lambda vx, vy, wz, enable, rc=False: beats.append((vx, vy, wz, enable)) or True
        self.assertEqual(s.set_base_sub('b'), 'b')
        self.assertEqual(s.base_sub, 'b')
        self.assertEqual(beats, [(0.0, 0.0, 0.0, False)])   # 零速断使能一拍
        with self.assertRaises(ValueError):
            s.set_base_sub('x')
        self.assertEqual(s.base_sub, 'b')                   # 非法值不改变现状

    def test_telemetry_returns_link_points_and_quat(self):
        """VR 免解算显示（2026-10-24）：遥测应带 7 个关节点 link_cm 与单位四元数 ee_quat。"""
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s.mode = 'arms'
        s.error = None
        s.base_sub = 'a'
        s.base_state = {'vx': 0.0, 'vy': 0.0, 'wz': 0.0, 'active': False,
                        'reason': '', 'sent': 0}
        s.entries = {'right': None, 'left': None}
        s.owner = s.owner_left = None
        s.vr_on = s.vr_left_on = False
        s.vr_pressing = s.vr_left_pressing = False
        s.joints = [0.0] * 6                              # 零位（Z 字停留位）
        s.left_joints = None
        s.reason = s.left_reason = ''
        s.vr_info = s.vr_left_info = ''
        s.grip = s.left_grip = 0.0
        s.right = s.left_target = None
        d = s.telemetry()
        arm = d['arms']['right']
        self.assertEqual(len(arm['link_cm']), 7, '底座→法兰共 7 个关节点')
        self.assertEqual(arm['link_cm'][-1], arm['ee_cm'], '末点必须等于 ee_cm')
        # 恒等标定 + 零位：法兰 ≈ (0, 5.6, 21.3) cm（arm_geometry 文档基准值）
        self.assertAlmostEqual(arm['ee_cm'][2], 21.3, delta=0.5)
        self.assertAlmostEqual(arm['ee_cm'][1], 5.6, delta=0.5)
        quat = arm['ee_quat']
        self.assertEqual(len(quat), 4)
        self.assertAlmostEqual(sum(v * v for v in quat), 1.0, places=3,
                               msg='ee_quat 必须是单位四元数')
        self.assertEqual(arm['ee_src'], 'target')         # 无反馈时走目标推算
        self.assertIsNone(d['arms']['left']['link_cm'])   # 无关节数据时为 None


# ======================= C06 =======================
class C06MoveSerializationTest(unittest.TestCase):
    """A/X 可同时启动两个定点动作，绕过串行约束。"""

    def _sender(self):
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s.mode = 'arms'
        s._move_gate = threading.Lock()
        s.entries = {'right': None, 'left': None}
        s.entry_pending = {'right': False, 'left': False}
        s.entry_generation = {'right': 0, 'left': 0}
        s.owner = s.owner_left = None
        s.until = s.left_until = 0.0
        s.status = lambda: {'ok': True}
        return s

    def test_second_move_rejected_while_first_holds_gate(self):
        s = self._sender()
        s._move_gate.acquire()                # 模拟第一路正在跑
        try:
            for side in ('right', 'left'):
                body, code = s._call_move(side, {'client': 'testclient1234',
                                                 'safety_epoch': app.SAFETY.status()['epoch'],
                                                 'controls': {'move': 'start'}})
                self.assertEqual(code, 409, body)
                self.assertIn('串行', body.get('error', ''))
        finally:
            s._move_gate.release()

    def test_gate_released_after_body_returns(self):
        s = self._sender()
        body, code = s._call_move('right', {'client': 'testclient1234',
                                           'safety_epoch': app.SAFETY.status()['epoch'],
                                           'controls': {'move': 'bogus'}})
        self.assertEqual(code, 400, '非法 move 应由 body 返回 400：%r' % (body,))
        self.assertTrue(s._move_gate.acquire(blocking=False), 'body 返回后闸门必须已释放')
        s._move_gate.release()


# ======================= C02 =======================
class C02FeedbackUnknownTest(unittest.TestCase):
    """"没有观察到位移"被当成"没有运动"。"""

    def _sender(self):
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s._ik_version = {'right': 0, 'left': 0}   # P0-A：锚点重置会作废旧 IK 结果
        s.entries = {'right': None, 'left': None}
        s.move_side = {'right': None, 'left': None}
        s.move_result = {'right': None, 'left': None}
        s.move_seq = 1
        s.error = None
        s.reason = ''
        s.left_reason = ''
        s.owner = 'c'
        s.owner_left = None
        s.vr_on = False
        s.vr_left_on = False
        s.left_joints = None
        return s

    def _entry(self, sent, have_fb, deviation=0.0):
        e = app.EntrySequence([0.0] * 6, [0.1] * 6, time.monotonic())
        e.sent_any = sent
        e.have_feedback = have_fb
        e.max_deviation = deviation
        return e

    def test_never_sent_does_not_lock(self):
        s = self._sender()
        e = self._entry(sent=False, have_fb=False)
        with unittest.mock.patch.object(app, 'stop_all') as stop_all:
            s._abort('right', e, ValueError('反馈读不到'))
            stop_all.assert_not_called()
        self.assertIn('尚未发出目标帧', s.reason)

    def test_sent_with_feedback_proving_still_does_not_lock(self):
        s = self._sender()
        e = self._entry(sent=True, have_fb=True, deviation=0.0)
        with unittest.mock.patch.object(app, 'stop_all') as stop_all:
            s._abort('right', e, ValueError('反馈读不到'))
            stop_all.assert_not_called()
        self.assertIn('判定未产生运动', s.reason)

    def test_sent_without_feedback_must_lock(self):
        s = self._sender()
        e = self._entry(sent=True, have_fb=False)
        with unittest.mock.patch.object(app, 'stop_all') as stop_all:
            s._abort('right', e, ValueError('反馈读不到'))
            stop_all.assert_called_once()
        self.assertIn('反馈未知', s.error)
        self.assertNotIn('未产生运动', s.error)

    def test_sent_with_deviation_must_lock(self):
        s = self._sender()
        e = self._entry(sent=True, have_fb=True, deviation=0.5)
        with unittest.mock.patch.object(app, 'stop_all') as stop_all:
            s._abort('right', e, ValueError('超时'))
            stop_all.assert_called_once()
        self.assertIn('位移超过容差', s.error)

    def test_observe_marks_have_feedback(self):
        t0 = time.monotonic()
        e = app.EntrySequence([0.0] * 6, [0.0] * 6, t0)
        self.assertFalse(e.have_feedback)
        sampled = t0 + 0.05          # 必须严格晚于构造时刻，否则 observe 会因"样本不新"早退
        e.observe([0.0] * 6, sampled, sampled)
        self.assertTrue(e.have_feedback)


# ======================= C07 =======================
class C07PoseValidationTest(unittest.TestCase):
    """畸形位姿可使控制发送线程退出。"""

    def test_pose_validator(self):
        ok = app.ControlSender._vr_pose_ok
        self.assertTrue(ok((0.1, 0.2, 0.3), (0.0, 0.0, 0.0, 1.0)))
        self.assertFalse(ok(None, (0.0, 0.0, 0.0, 1.0)))
        self.assertFalse(ok((0.1, 0.2), (0.0, 0.0, 0.0, 1.0)))
        self.assertFalse(ok((0.1, 0.2, 0.3), (0.0, 0.0, 1.0)))     # 三元素四元数
        self.assertFalse(ok((0.1, 0.2, 0.3), (0.0, 0.0, 0.0, 0.0)))  # 零范数
        self.assertFalse(ok((float('nan'), 0, 0), (0.0, 0.0, 0.0, 1.0)))
        self.assertFalse(ok((0.1, 0.2, 0.3), (0.0, 0.0, 0.0, float('inf'))))
        self.assertFalse(ok(('a', 0, 0), (0.0, 0.0, 0.0, 1.0)))

    def test_vr_step_does_not_raise_on_bad_quat(self):
        """真实 _vr_step 收到三元素四元数：不得抛异常。"""
        s = app.ControlSender.__new__(app.ControlSender)
        s.vr_pressing = False
        s.vr_info = ''
        s.grip = 0.0
        s.right = [0.2, 0.3, 0.25]
        s.vr_ori_user = None
        now = time.monotonic()
        bad = (1, now, 0x17, (0.1, 0.2, 0.3), (0.0, 0.0, 1.0),
               0.0, 1.0, None, None, None, None, None, None)
        with unittest.mock.patch.object(app.VR, 'latest', return_value=bad):
            r = s._vr_step(now)          # 不应抛异常
        self.assertTrue(r, '链路新鲜但位姿无效时应返回"仍然新鲜"，保持心跳而非踢掉会话')
        self.assertIn('位姿无效', s.vr_info)

    def test_tick_survives_unexpected_exception(self):
        s = app.ControlSender.__new__(app.ControlSender)
        s.error = None
        s._tick_body = lambda: (_ for _ in ()).throw(RuntimeError('boom'))
        with unittest.mock.patch.object(app, 'stop_all') as stop_all:
            s._tick()                     # 不得向外抛
            stop_all.assert_called_once()
        self.assertIn('控制循环异常', s.error or '')


# ======================= C23 =======================
class C23OriginBoundaryTest(unittest.TestCase):
    """控制服务没有建立身份和来源边界（通配 CORS + 无来源校验）。"""

    def _handler(self, origin=None, host='192.168.137.2:8092'):
        h = app.Handler.__new__(app.Handler)
        h.headers = {}
        if origin is not None:
            h.headers['Origin'] = origin
        if host is not None:
            h.headers['Host'] = host
        return h

    def test_no_origin_is_allowed(self):
        self.assertTrue(self._handler(None)._origin_ok(), '同源导航/命令行不带 Origin，应放行')

    def test_same_origin_is_allowed(self):
        self.assertTrue(self._handler('http://192.168.137.2:8092')._origin_ok())

    def test_localhost_is_allowed(self):
        for o in ('http://localhost:8091', 'http://127.0.0.1:8092'):
            self.assertTrue(self._handler(o)._origin_ok(), o)

    def test_foreign_origin_is_rejected(self):
        for o in ('http://evil.example.com', 'https://10.0.0.5:1234', 'file://x'):
            self.assertFalse(self._handler(o)._origin_ok(), o)

    def test_origin_matching_host_header_is_allowed(self):
        h = self._handler('http://robot.lan:8092', host='robot.lan:8092')
        self.assertTrue(h._origin_ok(), '与 Host 同源也应放行（换网段时不必改代码）')

    def test_wildcard_cors_header_no_longer_sent(self):
        """_cors 不应再写死 '*'。"""
        sent = []
        h = self._handler('http://evil.example.com')
        h.send_header = lambda k, v: sent.append((k, v))
        h._cors()
        self.assertFalse(any(k == 'Access-Control-Allow-Origin' for k, _ in sent),
                         '外来来源不得拿到 ACAO 头')

        sent.clear()
        h2 = self._handler('http://192.168.137.2:8091')
        h2.send_header = lambda k, v: sent.append((k, v))
        h2._cors()
        acao = [v for k, v in sent if k == 'Access-Control-Allow-Origin']
        self.assertEqual(acao, ['http://192.168.137.2:8091'], '受信来源应回显具体 Origin，而不是 *')


# ======================= C17 =======================
class C17AnchorRebuildTest(unittest.TestCase):
    """关节状态与 VR 锚点没有统一重建 → 首次握侧键可能回跳。"""

    def _sender(self):
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s._ik_version = {'right': 0, 'left': 0}   # P0-A：锚点重置会作废旧 IK 结果
        s.entries = {'right': None, 'left': None}
        s.entry_generation = {'right': 0, 'left': 0}
        s.entry_pending = {'right': False, 'left': False}
        s.move_side = {'right': None, 'left': None}
        s.owner = s.owner_left = None
        s.until = s.left_until = 0.0
        s.joints = list(app.QLEVEL)
        s.left_joints = None
        s.right = [0.2, 0.3, 0.25]
        s.left_target = [-0.1514, 0.2885, 0.2659]
        s.vr_on = s.vr_left_on = False
        s.vr_pressing = s.vr_left_pressing = False
        s.vr_ref = (0.1, 0.2, 0.3)
        s.vr_anchor = (0.2, 0.3, 0.25)
        s.vr_qref = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        s.vr_ori_anchor = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        s.vr_ori_user = ((0, 1, 0), (-1, 0, 0), (0, 0, 1))
        s.vr_smooth = (0.2, 0.3, 0.25)
        s.vr_left_ref = s.vr_left_anchor = s.vr_left_qref = None
        s.vr_left_ori_anchor = s.vr_left_ori_user = s.vr_left_smooth = None
        s.vr_info = ''
        s.vr_left_info = ''
        s.reason = ''
        s.left_reason = ''
        s.mode = 'arms'
        s.base_state = {}
        s.error = None
        s.status = lambda: {'ok': True}
        s._send_base_udp = lambda *a, **k: True
        return s

    def test_reset_clears_all_anchor_fields(self):
        s = self._sender()
        s._reset_vr_anchors()
        for name in ('vr_ref', 'vr_anchor', 'vr_qref', 'vr_ori_anchor', 'vr_ori_user', 'vr_smooth'):
            self.assertIsNone(getattr(s, name), name)
        self.assertFalse(s.vr_pressing)

    def test_cancel_sessions_resets_anchors(self):
        s = self._sender()
        s._cancel_sessions('测试')
        self.assertIsNone(s.vr_ori_user, '撤会话后旧姿态锚点必须清空，否则下次握侧键会回跳')
        self.assertIsNone(s.vr_anchor)

    def test_mode_switch_resets_anchors(self):
        s = self._sender()
        s._set_mode('base')
        self.assertIsNone(s.vr_ori_user)
        self.assertEqual(s.mode, 'base')

    def test_press_edge_uses_current_accepted_pose(self):
        """会话首个有效手姿以当前目标建绝对参考，不能退回固定 QLEVEL。"""
        s = self._sender()
        s.grip = 0.0
        s.left_grip = 0.0
        s.vr_ori_user = None
        s.vr_qref = None
        s.vr_ori_anchor = None
        s.joints = [app.QLEVEL[i] + 0.2 for i in range(6)]     # 被别处改过的姿态
        now = time.monotonic()
        snap = (1, now, 0x17, (0.1, 0.2, 0.3), (0.0, 0.0, 0.0, 1.0),
                0.0, 1.0, None, None, None, None, None, None)
        with unittest.mock.patch.object(app.VR, 'latest', return_value=snap):
            s._vr_step(now)
        expected = app._mm(app._FR, app._fk(s.joints)[1])
        for r_exp, r_got in zip(expected, s.vr_ori_user):
            for a, b in zip(r_exp, r_got):
                self.assertAlmostEqual(a, b, places=9)

    def test_gripper_trigger_analog_and_stick_toggle(self):
        """2026-11-01 实测定案：扳机=纯模拟量连续夹取；L3/R3 按一次闭合锁存、再按一次松开。"""
        s = self._sender()

        def sb(pressed_bit):
            return {'revision': 1, 'valid': 3, 'pressed': pressed_bit}

        for side, bit in (('right', 1), ('left', 0)):
            attr = 'grip' if side == 'right' else 'left_grip'
            s._vr_update_grip(side, 0.0, None, bit)
            self.assertEqual(getattr(s, attr), 0.0)
            s._vr_update_grip(side, 0.3, None, bit)
            self.assertAlmostEqual(getattr(s, attr), 0.3)   # 模拟量连续可调
            s._vr_update_grip(side, 0.8, None, bit)
            self.assertAlmostEqual(getattr(s, attr), 0.8)
            s._vr_update_grip(side, float('nan'), None, bit)
            self.assertEqual(getattr(s, attr), 0.0)         # 非法值归零
            s._vr_update_grip(side, 1.7, None, bit)
            self.assertEqual(getattr(s, attr), 1.0)         # 超界钳位
            # 按一次 L3/R3：闭合锁存（即使扳机为 0 也闭合到上限）
            s._vr_update_grip(side, 0.0, sb(1 << bit), bit)
            self.assertEqual(getattr(s, attr), 1.0)
            # 长按同一拍不重复切换；锁存保持
            s._vr_update_grip(side, 0.0, sb(1 << bit), bit)
            self.assertEqual(getattr(s, attr), 1.0)
            # 扳机模拟量在锁存期间不改变闭合状态
            s._vr_update_grip(side, 0.5, sb(1 << bit), bit)
            self.assertEqual(getattr(s, attr), 1.0)
            # 松开（pressed=0）后锁存仍保持
            s._vr_update_grip(side, 0.5, sb(0), bit)
            self.assertEqual(getattr(s, attr), 1.0)
            # 再按一次：锁存释放，回到当前扳机值
            s._vr_update_grip(side, 0.5, sb(1 << bit), bit)
            self.assertAlmostEqual(getattr(s, attr), 0.5)
            s._vr_update_grip(side, 0.0, sb(0), bit)
            self.assertEqual(getattr(s, attr), 0.0)         # 扳机 0 → 打开
            # key15 缺失：不动锁存、不判边沿，退回纯扳机模拟量
            s._vr_update_grip(side, 0.0, sb(1 << bit), bit)  # 先建立锁存
            self.assertEqual(getattr(s, attr), 1.0)
            s._vr_update_grip(side, 0.4, None, bit)
            self.assertEqual(getattr(s, attr), 1.0)          # 锁存保持
            # 该 bit valid=0 的帧：不动边沿状态；恢复后若上次记忆是"已按下"，
            # 必须先见到松开再按才算新切换（防缺口恢复帧连切）
            s._vr_update_grip(side, 0.4, {'revision': 1, 'valid': 3 - (1 << bit),
                                          'pressed': 0}, bit)
            s._vr_update_grip(side, 0.4, sb(1 << bit), bit)  # 恢复即按下：不算新边沿
            self.assertEqual(getattr(s, attr), 1.0)          # 仍锁存（未连切两次）
            s._vr_update_grip(side, 0.4, sb(0), bit)         # 见到松开
            s._vr_update_grip(side, 0.4, sb(1 << bit), bit)  # 新的按下 → 切换
            self.assertAlmostEqual(getattr(s, attr), 0.4)

    def test_orientation_reference_survives_clutch_repress(self):
        s = self._sender()
        reference = s.vr_qref
        anchor = s.vr_ori_anchor
        now = time.monotonic()
        snap = (1, now, 0x17, (0.1, 0.2, 0.3), (0.0, 0.0, 0.0, 1.0),
                0.0, 1.0, None, None, None, None, None, None)
        with unittest.mock.patch.object(app.VR, 'latest', return_value=snap), \
             unittest.mock.patch.object(s, '_ik_submit'):
            s._vr_step(now)
            s.vr_pressing = False
            s._vr_step(now)
        self.assertIs(s.vr_qref, reference)
        self.assertIs(s.vr_ori_anchor, anchor)


# ======================= C19 =======================
class C19LockScopeTest(unittest.TestCase):
    """共享控制锁内仍有阻塞的 deploy 状态查询。"""

    def test_deploy_query_happens_outside_lock(self):
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s._ik_version = {'right': 0, 'left': 0}   # P0-A：锚点重置会作废旧 IK 结果
        s.entries = {'right': None, 'left': None}
        s.owner = s.owner_left = None
        s.until = s.left_until = 0.0
        s.mode = 'arms'
        s.status = lambda: {'ok': True}
        s.right = [0.2, 0.3, 0.25]
        s.joints = list(app.QLEVEL)
        s.grip = 0.0
        s.vr_on = False
        s.vr_pressing = False
        s.vr_anchor = None
        s.reason = ''
        s.deadline = 0.0
        s.count = 0
        s.seq = 1
        s.error = None
        s.move_side = {'right': None, 'left': None}

        seen = []

        def fake_running():
            seen.append(s.lock.locked())      # 查询这一刻锁是否被持有
            return False                      # 让 _call_follow 直接拒绝

        with unittest.mock.patch.object(app, 'deploy_running', fake_running), \
             unittest.mock.patch.object(app.SAFETY, 'require', lambda _d: None):
            body, code = s._call_follow('start', {'client': 'testclient1234',
                                                  'controls': {'mode': 'vr'}})

        self.assertEqual(code, 409, body)
        self.assertEqual(seen, [False],
                         'deploy_running() 必须在锁外调用，否则慢 SSH 会拖住 20Hz 发帧')


# ======================= C09 =======================
class C09FollowGeoGuardTest(unittest.TestCase):
    """跟随期持续几何检查：返回值解包错误会让每一拍都抛 TypeError。"""

    def _sender(self):
        s = app.ControlSender.__new__(app.ControlSender)
        s.joints = list(app.QLEVEL)
        s.left_joints = None
        s.FOLLOW_GEO_EVERY = 1
        return s

    def test_guard_runs_without_type_error(self):
        s = self._sender()
        # 不抛异常即通过；若 pose_margin 的返回值解包错，这里会 TypeError
        try:
            s._follow_geo_guard('right', 1)
        except ValueError as exc:
            self.assertIn('余量', str(exc))          # 余量不足是合法结果
        except TypeError as exc:
            self.fail('解包类型错误（回归）：%s' % exc)

    def test_guard_skips_when_no_target(self):
        s = self._sender()
        s.left_joints = None
        s._follow_geo_guard('left', 1)               # 无目标应直接返回

    def test_guard_skips_between_checks(self):
        s = self._sender()
        s.FOLLOW_GEO_EVERY = 5
        s._follow_geo_guard('right', 3)              # 非检查拍直接返回

    def test_guard_blocks_when_margin_short(self):
        """2026-10-23 降级为告警制：余量不足不再中止（防误报锁停），但必须记录 geo_warn。"""
        s = self._sender()
        s.geo_warn = None
        old = app.arm_geometry.MIN_MARGIN_CM
        app.arm_geometry.MIN_MARGIN_CM = 999.0
        try:
            s._follow_geo_guard('right', 1)          # 不再抛 ValueError
            self.assertIsNotNone(s.geo_warn)
            self.assertIn('余量', s.geo_warn)
        finally:
            app.arm_geometry.MIN_MARGIN_CM = old


# ======================= AI 意图接口 =======================
class IntentLayerTest(unittest.TestCase):
    """AI/语音命令层：只翻译、不放宽；上限与联锁必须生效。"""

    def _sender(self, mode='arms'):
        s = app.ControlSender.__new__(app.ControlSender)
        s.lock = threading.Lock()
        s.mode = mode
        s.owner = s.owner_left = None
        s.grip = 0.0
        s.left_grip = 0.0
        s.joints = list(app.QLEVEL)
        s.left_joints = None
        s._move_gate = threading.Lock()
        s.entries = {'right': None, 'left': None}
        s.entry_pending = {'right': False, 'left': False}
        s.entry_generation = {'right': 0, 'left': 0}
        s.until = s.left_until = 0.0
        s._web_active_at = {'right': 0.0, 'left': 0.0}
        s.move_side = {'right': None, 'left': None}
        s.status = lambda: {'ok': True}
        return s

    def test_schema_is_self_describing(self):
        sc = app.ControlSender.intent_schema()
        names = {i['intent'] for i in sc['intents']}
        self.assertEqual(names, {'preset', 'ee_delta', 'ee_abs', 'two_point_abs', 'tcp_dir_abs',
                                 'joints_abs', 'gripper', 'left_transfer', 'stop',
                                 'base_drive', 'base_stop'})
        self.assertIn('safety_epoch', sc['usage'])
        self.assertIn('cm', sc['units'])

    def test_schema_limits_machine_matches_enforcement(self):
        """limits_machine 机读限值必须与强制校验同源：超出 schema 声明值的请求被拒。"""
        sc = app.ControlSender.intent_schema()
        lm = sc['limits_machine']
        self.assertEqual(lm['ee_delta_max_cm'], 5.0)
        self.assertEqual(lm['base_max_vx_mps'], 0.3)
        self.assertEqual(lm['base_max_wz_rads'], 0.5)
        self.assertEqual(lm['base_max_duration_s'], 2.0)
        # 超限拒绝与 schema 声明同源（改常量时两边一起动，此测试保证不脱节）
        s = self._sender()
        with unittest.mock.patch.object(app.SAFETY, 'require', lambda _d: None):
            body, code = s.intent({'intent': 'base_drive',
                                   'vx': lm['base_max_vx_mps'] + 0.01, 'duration_s': 0.5,
                                   'safety_epoch': 'x'})
        self.assertEqual(code, 400)
        self.assertIn('线速度', body['error'])

    def test_schema_declares_contract_version_and_enums(self):
        """契约稳定性（2026-10-25）：schema 必须带 api_version 与全枚举机读清单，
        调用方启动时据此校验兼容性而不是硬编码。"""
        sc = app.ControlSender.intent_schema()
        self.assertRegex(sc['api_version'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(sc['enums']['mode'], ['arms', 'base'])
        self.assertEqual(sc['enums']['base_sub'], ['a', 'b'])
        self.assertEqual(sc['enums']['side'], ['right', 'left'])
        self.assertIn('409', sc['error_semantics'])

    def test_base_stop_cancels_timed_without_touching_arms(self):
        """base_stop（2026-10-25，P0-A）：作废 base_drive 代次令牌 + 零速断使能；
        不需要 safety_epoch、不锁存全局停止、不触碰双臂。"""
        s = self._sender()
        s.base_state = {'vx': 0.2, 'vy': 0.0, 'wz': 0.0, 'active': True, 'reason': ''}
        s._base_gen = 7
        beats = []
        s._send_base_udp = lambda vx, vy, wz, enable, rc=False: beats.append((vx, vy, wz, enable)) or True
        old_stopped = app.SAFETY.stopped
        app.SAFETY.stopped = False
        try:
            body, code = s.intent({'intent': 'base_stop'})   # 故意不带 safety_epoch
            stopped_after = app.SAFETY.stopped               # 先取证再恢复现场
        finally:
            app.SAFETY.stopped = old_stopped
        self.assertEqual(code, 202)
        self.assertTrue(body['ok'])
        self.assertEqual(s._base_gen, 8)                     # 旧定时线程将自行退出
        self.assertEqual(beats, [(0.0, 0.0, 0.0, False)])    # 零速断使能一拍
        self.assertFalse(s.base_state['active'])
        self.assertFalse(stopped_after)                      # 不锁存全局停止
        self.assertIsNone(s.entries['right'])                # 双臂会话未被触碰

    def test_base_stop_works_even_when_globally_stopped(self):
        """停止指令必须永远可执行：全局停止锁存中 base_stop 仍放行。"""
        s = self._sender()
        s.base_state = {'vx': 0.0, 'vy': 0.0, 'wz': 0.0, 'active': False, 'reason': ''}
        s._send_base_udp = lambda *a, **k: True
        old_stopped = app.SAFETY.stopped
        app.SAFETY.stopped = True
        try:
            body, code = s.intent({'intent': 'base_stop'})
        finally:
            app.SAFETY.stopped = old_stopped
        self.assertEqual(code, 202)
        self.assertTrue(body['ok'])

    def test_unknown_intent_rejected(self):
        s = self._sender()
        body, code = s.intent({'intent': 'fly', 'safety_epoch': 'x'})
        self.assertEqual(code, 400)
        self.assertFalse(body['ok'])
        self.assertIn('未知 intent', body['error'])

    def test_bad_side_rejected(self):
        s = self._sender()
        body, code = s.intent({'intent': 'preset', 'side': 'middle', 'which': 'zero'})
        self.assertEqual(code, 400)

    def test_ee_delta_over_limit_rejected(self):
        s = self._sender()
        body, code = s.intent({'intent': 'ee_delta', 'side': 'right', 'd': [0, 10, 0],
                               'safety_epoch': 'x'})
        self.assertEqual(code, 400)
        self.assertIn('超过', body['error'])

    def test_joint_step_over_limit_rejected(self):
        s = self._sender()
        # 让"当前角度"可控
        s._intent_current_joints = lambda side: [0.0] * 6
        body, code = s.intent({'intent': 'joints_abs', 'side': 'right',
                               'deg': [0, 0, 0, 0, 0, 90], 'safety_epoch': 'x'})
        self.assertEqual(code, 400)
        self.assertIn('45', body['error'])

    def test_ee_abs_out_of_box_rejected(self):
        s = self._sender()
        s._intent_current_joints = lambda side: list(app.QLEVEL)
        body, code = s.intent({'intent': 'ee_abs', 'side': 'right', 'p': [200, 0, 0],
                               'safety_epoch': 'x'})
        self.assertEqual(code, 400)
        self.assertIn('可达框', body['error'])

    def test_gripper_without_session_refused(self):
        s = self._sender()
        body, code = s.intent({'intent': 'gripper', 'side': 'right', 'open': 0.2,
                               'safety_epoch': 'x'})
        self.assertEqual(code, 409)
        self.assertIn('已有动作', body['error'])

    def test_preset_delegates_to_guarded_move(self):
        """preset 必须走 _call_move（串行闸门 + 几何预检），不能自己发帧。"""
        s = self._sender()
        calls = []

        def fake_move(side, data):
            calls.append((side, data))
            return {'ok': True}, 200

        s._call_move = fake_move
        body, code = s.intent({'intent': 'preset', 'side': 'left', 'which': 'zero',
                               'safety_epoch': 'E'})
        self.assertEqual((code, body['ok']), (200, True))
        self.assertEqual(calls[0][0], 'left')
        self.assertEqual(calls[0][1]['controls']['move'], 'zero')
        self.assertEqual(calls[0][1]['controls']['mode'], 'left_joints')

    def test_ee_delta_delegates_to_guarded_follow(self):
        s = self._sender()
        s._intent_current_joints = lambda side: list(app.QLEVEL)
        seen = []

        def fake_follow(action, data):
            seen.append((action, data))
            return {'ok': True}, 200

        s._call_follow = fake_follow
        body, code = s.intent({'intent': 'ee_delta', 'side': 'right', 'd': [0, 0, -2],
                               'safety_epoch': 'E'})
        self.assertEqual(code, 200, body)
        self.assertTrue(body['ok'])
        self.assertEqual(seen[0][0], 'start')
        deg = seen[0][1]['controls']['right_joints_deg']
        self.assertEqual(len(deg), 6)
        # 下降 2 cm 后 J2 应比原构型更大（肩更抬），至少不能原封不动
        self.assertNotEqual([round(v, 3) for v in deg],
                            [round(math.degrees(v), 3) for v in app.QLEVEL])


if __name__ == '__main__':
    unittest.main()

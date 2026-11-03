# -*- coding: utf-8 -*-
"""2026-10-28 第一批顿挫修复专项回归：
P0-A 异步 IK 工作器（提交/作废旧结果/会话与停止复核）
P0-B 锁外准入预查（update 不再触发 SSH）
P1-A VR 死区滞回（慢速小动作连续、静止重新压噪）
"""
import threading
import time
import unittest
from unittest import mock

import arm_console as app


def bare_sender():
    s = app.ControlSender.__new__(app.ControlSender)
    s.lock = threading.RLock()
    s._ik_version = {'right': 0, 'left': 0}
    s._ik_job = {'right': None, 'left': None}
    s._ik_cv = threading.Condition()
    s.entries = {'right': None, 'left': None}
    s.owner = 'testclient1234'
    s.owner_left = None
    s.until = time.monotonic() + 100.0
    s.left_until = 0.0
    s.vr_on = True
    s.vr_left_on = False
    s.vr_pressing = True
    s.vr_left_pressing = False
    s.joints = list(app.QLEVEL)
    s.right = [0.2, 0.3, 0.25]
    s.left_joints = None
    s.left_target = [-0.1514, 0.2885, 0.2659]
    s.vr_ori_user = None
    s.vr_left_ori_user = None
    s.ik_err = None
    s.vr_info = ''
    s.vr_left_info = ''
    s.grip = 0.0
    s.status = lambda: {'ok': True}
    return s


class ControllableSolver:
    """可卡住的 IK：先报告“开始求解”，测试放开闸门后才返回。"""
    def __init__(self, result):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.result = result

    def __call__(self, *a, **k):
        self.entered.set()
        self.release.wait(2.0)
        return self.result


class AsyncIKWorkerTest(unittest.TestCase):
    def setUp(self):
        # 全套件运行时，前序测试可能把全局停止锁存留在 True——这里显式复位并恢复
        self._old_stopped = app.SAFETY.stopped
        app.SAFETY.stopped = False

    def tearDown(self):
        app.SAFETY.stopped = self._old_stopped

    def _submit(self, s, tgt):
        with s.lock:
            s._ik_submit('right', tgt, None, s.joints, None, ((0.0, 0.0, 0.0), 0.0))

    def test_worker_commits_result(self):
        s = bare_sender()
        fake_q = [v + 0.01 for v in app.QLEVEL]
        with mock.patch.object(app, 'solve_vr_pose_two_point_user', return_value=(fake_q, None)):
            threading.Thread(target=s._ik_worker, args=('right',), daemon=True).start()
            self._submit(s, [0.21, 0.3, 0.25])
            t0 = time.monotonic()
            while time.monotonic() - t0 < 1.0:
                with s.lock:
                    if s.right == [0.21, 0.3, 0.25]:
                        break
                time.sleep(0.005)
        self.assertEqual(s.right, [0.21, 0.3, 0.25])
        self.assertEqual(s.joints, fake_q)
        self.assertIsNone(s.ik_err)

    def test_worker_discards_stale_version(self):
        """求解期间来了更新目标：旧结果必须作废，只提交最新目标。"""
        s = bare_sender()
        solver = ControllableSolver(([v + 0.01 for v in app.QLEVEL], None))
        with mock.patch.object(app, 'solve_vr_pose_two_point_user', solver):
            threading.Thread(target=s._ik_worker, args=('right',), daemon=True).start()
            self._submit(s, [0.21, 0.3, 0.25])
            self.assertTrue(solver.entered.wait(1.0))
            self._submit(s, [0.22, 0.3, 0.25])       # 新版本，旧结果失效
            solver.release.set()
            time.sleep(0.15)
        with s.lock:
            self.assertNotEqual(s.right, [0.21, 0.3, 0.25], '旧版本结果被提交了')
            self.assertEqual(s.right, [0.22, 0.3, 0.25])

    def test_worker_discards_after_session_end(self):
        """会话已结束（VR 跟随撤销）：晚到的解不得复活旧目标。"""
        s = bare_sender()
        solver = ControllableSolver(([v + 0.01 for v in app.QLEVEL], None))
        with mock.patch.object(app, 'solve_vr_pose_two_point_user', solver):
            threading.Thread(target=s._ik_worker, args=('right',), daemon=True).start()
            self._submit(s, [0.21, 0.3, 0.25])
            self.assertTrue(solver.entered.wait(1.0))
            with s.lock:
                s.vr_on = False
                s.owner = None
            solver.release.set()
            time.sleep(0.15)
        with s.lock:
            self.assertEqual(s.right, [0.2, 0.3, 0.25], '会话结束后旧 IK 结果被复活')

    def test_worker_discards_after_clutch_release(self):
        """侧键松开：尚在求解的旧位置/姿态不得再写入目标。"""
        s = bare_sender()
        solver = ControllableSolver(([v + 0.01 for v in app.QLEVEL], None))
        with mock.patch.object(app, 'solve_vr_pose_two_point_user', solver):
            threading.Thread(target=s._ik_worker, args=('right',), daemon=True).start()
            self._submit(s, [0.21, 0.3, 0.25])
            self.assertTrue(solver.entered.wait(1.0))
            with s.lock:
                s.vr_pressing = False
            solver.release.set()
            time.sleep(0.15)
        with s.lock:
            self.assertEqual(s.right, [0.2, 0.3, 0.25])
            self.assertEqual(s.joints, list(app.QLEVEL))

    def test_worker_discards_when_globally_stopped(self):
        s = bare_sender()
        solver = ControllableSolver(([v + 0.01 for v in app.QLEVEL], None))
        with mock.patch.object(app, 'solve_vr_pose_two_point_user', solver), \
             mock.patch.object(app.SAFETY, 'status', return_value={'stopped': True}):
            threading.Thread(target=s._ik_worker, args=('right',), daemon=True).start()
            self._submit(s, [0.21, 0.3, 0.25])
            self.assertTrue(solver.entered.wait(1.0))
            solver.release.set()
            time.sleep(0.15)
        with s.lock:
            self.assertEqual(s.right, [0.2, 0.3, 0.25], '全局停止中旧 IK 结果被提交')


class FollowDeployQueryTest(unittest.TestCase):
    def test_update_with_owner_does_not_ssh(self):
        """属主已在的跟随 update：不再触发 deploy_running（SSH）。"""
        s = bare_sender()
        seen = []
        with mock.patch.object(app, 'deploy_running', lambda: seen.append(1) or True), \
             mock.patch.object(app.SAFETY, 'require', lambda _d: None):
            body, code = s._call_follow('update', {'client': 'testclient1234',
                                                   'controls': {'mode': 'vr'}})
        self.assertEqual(code, 200)
        self.assertEqual(seen, [], '跟随 update 仍在查 deploy（可能走 SSH 堵锁）')


class HysteresisTest(unittest.TestCase):
    def _vr_sender(self):
        s = bare_sender()
        s.vr_pressing = True
        s.vr_ref = (0.0, 0.0, 0.0)
        s.vr_anchor = tuple(s.right)
        s.vr_qref = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        s.vr_ori_anchor = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        s.vr_ori_user = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        s.vr_smooth = tuple(s.right)
        s.vr_quiet = True
        s._vr_still = 0
        return s

    def _run_ticks(self, s, positions):
        submitted = []
        def fake_submit(side, tgt, *rest):
            submitted.append((side, list(tgt)))
            # 模拟工作器提交：真实代码里接受目标由 _ik_worker 写回
            if side == 'right':
                s.right = list(tgt)
            else:
                s.left_target = list(tgt)
        s._ik_submit = fake_submit
        for pos in positions:
            now = time.monotonic()
            snap = (1, now, 0x04, pos, (0.0, 0.0, 0.0, 1.0),
                    0.0, 1.0, None, None, None, None, None, None)
            with mock.patch.object(app.VR, 'latest', return_value=snap):
                s._vr_step(now)
        return submitted

    def test_slow_motion_becomes_continuous(self):
        """1mm/拍的慢速移动：起步后应每拍都接受（不再攒 2mm 才跳）。"""
        s = self._vr_sender()
        positions = [(0.001 * i, 0.0, 0.0) for i in range(1, 13)]
        submitted = self._run_ticks(s, positions)
        self.assertGreaterEqual(len(submitted), 8,
                                f'12 拍慢速移动只接受了 {len(submitted)} 次，仍有阶梯')
        self.assertFalse(s.vr_quiet)

    def test_tiny_noise_rejected_while_quiet(self):
        """静止压噪：0.2mm/拍的微动在静止态下不得触发求解。"""
        s = self._vr_sender()
        positions = [(0.0002 * i, 0.0, 0.0) for i in range(1, 6)]
        submitted = self._run_ticks(s, positions)
        self.assertEqual(submitted, [])
        self.assertTrue(s.vr_quiet)

    def test_hysteresis_reengages_after_still(self):
        """动起来→停 15 拍以上→回静止态：微小增量重新被压住。"""
        s = self._vr_sender()
        self._run_ticks(s, [(0.001 * i, 0.0, 0.0) for i in range(1, 13)])
        self.assertFalse(s.vr_quiet)
        final_pos = (0.012, 0.0, 0.0)
        self._run_ticks(s, [final_pos] * 30)
        self.assertTrue(s.vr_quiet, '静止 30 拍后未回到压噪态')


if __name__ == '__main__':
    unittest.main()

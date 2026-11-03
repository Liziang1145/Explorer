"""Offline entry-order checks; no sockets, SSH or actuator commands."""
import math
import sys
import pathlib
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from arm_entry import EntrySequence, slew_command
from test_console_safety import SafetyTests

class SequenceTests(unittest.TestCase):
    def test_j1_only_after_three_stable_samples(self):
        e=EntrySequence([0]*6,[1,.2,.3,.4,.5,.6],0)
        mid=e.command[1:]                       # 第一段：本体到半展开构型
        self.assertEqual(e.command[0],0)        # J1 保持
        self.assertNotEqual(mid,[.2,.3,.4,.5,.6])
        for t in (.1,.4): e.observe(e.command,t,t)
        self.assertEqual(e.phase,'body_to_mid')
        e.observe(e.command,.7,.7)
        self.assertEqual(e.phase,'j1')
        self.assertEqual(e.command,[1,*mid])    # 第二段：只转 J1
        for t in (.8,1.1,1.4): e.observe(e.command,t,t)
        self.assertEqual(e.phase,'body_finish')
        for t in (1.5,1.8,2.1,2.4): e.observe([1,.2,.3,.4,.5,.6],t,t)
        self.assertEqual(e.phase,'done')

    def test_duplicate_feedback_does_not_advance(self):
        # 只有 J1 要动、本体本来就在目标 → 计划只有一段 j1
        e=EntrySequence([0]*6,[1,0,0,0,0,0],0)
        self.assertEqual(e.phase,'j1')
        for _ in range(5): e.observe([0]*6,.1,.7)
        self.assertEqual(e.phase,'j1')        # 重复/陈旧样本不推进阶段

    def test_drift_stale_timeout_and_nan_abort(self):
        for mode in ('drift','stale','timeout','nan'):
            e=EntrySequence([0]*6,[1,.2,.3,.4,.5,.6],0)
            with self.assertRaises(ValueError):
                if mode=='drift': e.observe([.1]*6,.1,.1)
                elif mode=='stale': e.check(2.1)
                elif mode=='timeout': e.observed=46;e.check(46)
                else: e.observe([math.nan]*6,.1,.1)

    def test_other_joints_drift_during_j1_aborts(self):
        e=EntrySequence([0]*6,[1,0,0,0,0,0],0)
        for t in (.1,.4,.7): e.observe([0]*6,t,t)
        with self.assertRaises(ValueError): e.observe([.5,.1,0,0,0,0],.8,.8)

class TrajectoryCompletionTests(unittest.TestCase):
    def test_small_trajectory_cannot_finish_before_time_axis_ends(self):
        trajectory = {'times': [0.0, 1.0], 'q': [[0.0] * 6, [0.01] * 6]}
        e = EntrySequence([0.0] * 6, [0.01] * 6, 0.0,
                          arrive_tol=math.radians(6), trajectory=trajectory)
        for t in (0.1, 0.4, 0.7):
            e.observe([0.0] * 6, t, t)
        self.assertNotEqual(e.phase, 'done')
        for t in (1.1, 1.4, 1.7):
            e.observe([0.01] * 6, t, t)
        self.assertEqual(e.phase, 'done')


class ThreePhaseOrderTests(unittest.TestCase):
    """不变量（2026-10-22 双臂互撞仿真定稿）：
    1) 本体（J2–J6）先到 J2=60° 的半展开构型，J1 保持；
    2) 然后转 J1，本体保持；
    3) 最后本体补完。
    理由：J1=0 时若 J2≈92° 两臂夹爪在中线相撞（−0.94 cm），若 J2≈0° 两臂前臂互穿；
    只有半展开区（J2≈45~75°）是干净区。伸展态之间的小调整不经过中线，仍一步到位。
    """

    def test_start_to_zero_rotates_j1_at_mid_pose(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[0,.05,-.05,0,0,0],0)
        self.assertEqual(e.phase,'body_to_mid')
        self.assertAlmostEqual(e.command[0],-.7)               # 第一段 J1 保持不动
        mid=e.command[1:]
        self.assertNotEqual(mid,[.05,-.05,0,0,0])              # 本体停在中间构型，不是直接到位
        for t in (.1,.4,.7): e.observe([-.7,*mid],t,t)
        self.assertEqual(e.phase,'j1')
        self.assertEqual(e.command,[0,*mid])                   # 第二段只转 J1
        for t in (1.0,1.3,1.6): e.observe([0,*mid],t,t)
        self.assertEqual(e.phase,'body_finish')
        self.assertEqual(e.command,[0,.05,-.05,0,0,0])         # 第三段补完本体

    def test_zero_to_start_holds_j1_during_first_body_leg(self):
        e=EntrySequence([0]*6,[-.7,1.6,-.85,-1.1,-1.03,.7],0)
        self.assertEqual(e.phase,'body_to_mid')
        self.assertEqual(e.command[0],0)                       # 先展开一半，J1 仍为 0
        self.assertTrue(0 < abs(e.command[1]) < 1.6)           # 且没直接到 1.6

    def test_left_validation_start_to_zero_is_j1_j4_then_body(self):
        initial = [.7, 1.6, -.8, .9, -1.0, -.6]
        target = [0, .05, -.05, 0, 0, 0]
        e = EntrySequence(initial, target, 0, j1_order='first')
        self.assertEqual([name for name, _ in e.plan], ['j1_j4', 'other_joints'])
        self.assertEqual(e.command, [0, 1.6, -.8, 0, -1.0, -.6])
        with self.assertRaises(ValueError):
            e.observe([0, 1.55, -.8, 0, -1.0, -.6], .1, .1)
        only_j1 = list(initial)
        only_j1[0] = target[0]
        e.observe(only_j1, .4, .4)             # 只有 J1 到位，不允许切阶段
        only_j4 = list(initial)
        only_j4[3] = target[3]
        e.observe(only_j4, .7, .7)             # 只有 J4 到位，同样不允许
        self.assertEqual(e.phase, 'j1_j4')
        for t in (1.0, 1.3, 1.6):
            e.observe(e.command, t, t)         # 两轴均到位且稳定后才切换
        self.assertEqual(e.phase, 'other_joints')
        self.assertEqual(e.command, target)

    def test_left_validation_zero_to_start_holds_j1_j4_then_turns_j1(self):
        initial = [0, .05, -.05, 0, 0, 0]
        target = [.7, 1.6, -.8, .9, -1.0, -.6]
        e = EntrySequence(initial, target, 0, j1_order='last')
        self.assertEqual([name for name, _ in e.plan], ['body_j1_j4_hold', 'j1_j4'])
        self.assertEqual(e.command, [0, 1.6, -.8, 0, -1.0, -.6])
        with self.assertRaises(ValueError):
            e.observe([.1, .05, -.05, 0, 0, 0], .1, .1)
        with self.assertRaises(ValueError):
            e.observe([0, .05, -.05, .1, 0, 0], .2, .2)
        for t in (.4, .7, 1.0):
            e.observe(e.command, t, t)
        self.assertEqual(e.phase, 'j1_j4')
        self.assertEqual(e.command, target)

    def test_slew_command_limits_each_axis_and_reaches_target(self):
        self.assertEqual(slew_command([0] * 6, [.1] * 6, .01), [.01] * 6)
        self.assertEqual(slew_command([0] * 6, [.005] * 6, .01), [.005] * 6)
        with self.assertRaises(ValueError):
            slew_command([0] * 6, [1] * 6, 0)

    def test_mid_pose_sits_at_j2_60_degrees(self):
        e=EntrySequence([0]*6,[-.7,1.6,-.85,-1.1,-1.03,.7],0)
        self.assertAlmostEqual(math.degrees(e.command[1]),60.0,places=6)

    def test_mid_pose_also_60_for_fold_direction(self):
        e=EntrySequence([-.7,1.6,-.85,-1.1,-1.03,.7],[0,.05,-.05,0,0,0],0)
        self.assertAlmostEqual(math.degrees(e.command[1]),60.0,places=6)

    def test_no_split_when_j1_does_not_cross_center(self):
        # J1 -40°→-30°：两端 |J1| 都大，不经过中线危险带，一起动即可
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[-.52,.4,-.25,.1,-.1,.2],0)
        self.assertEqual(e.phase,'all_joints')

    def test_split_when_j1_crosses_center(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[.52,.4,-.25,.1,-.1,.2],0)
        self.assertEqual(e.phase,'body_to_mid')

    def test_no_body_split_when_body_does_not_move(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[-.2,.3,-.2,.1,-.1,.2],0)
        self.assertEqual(e.phase,'j1')
        self.assertEqual(e.command,[-.2,.3,-.2,.1,-.1,.2])

    def test_no_j1_phase_when_j1_already_on_target(self):
        e=EntrySequence([0]*6,[0,.05,-.05,0,0,0],0)
        self.assertEqual(e.phase,'other_joints')

    def test_small_j1_difference_is_held_not_commanded(self):
        # 2026-10-30 实车日志：30.650→32.152° 被 other_joints 同时下发并保持检查，
        # J1 正常执行到 32.140° 后却被误判为异常偏移。
        initial = [30.65,85.54,-37.07,29.97,-48.47,-25.44]
        target = [32.1523,85.14992,-34.88746,30.34649,-48.82691,-25.42854]
        e=EntrySequence([math.radians(v) for v in initial],
                        [math.radians(v) for v in target],0)
        self.assertEqual(e.phase,'other_joints')
        self.assertAlmostEqual(e.command[0],math.radians(30.65))
        self.assertAlmostEqual(e.target[0],math.radians(30.65))
        for t in (.1,.4,.7):
            e.observe(e.command,t,t)
        self.assertEqual(e.phase,'done')

    def test_j1_drift_during_body_leg_aborts(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[0,.05,-.05,0,0,0],0)
        with self.assertRaises(ValueError): e.observe([-.5,.35,-.2,.1,-.1,.2],.1,.1)

    def test_j1_drift_reports_reference_feedback_delta_and_command(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[0,.05,-.05,0,0,0],0)
        with self.assertRaises(ValueError) as caught:
            e.observe([-.5,.35,-.2,.1,-.1,.2],.1,.1)
        message = str(caught.exception)
        self.assertIn('参考 -40.107°', message)
        self.assertIn('实测 -28.648°', message)
        self.assertIn('偏差 +11.459°', message)
        self.assertIn('指令 -40.107°', message)
        self.assertIn('容差 1.000°', message)

    def test_body_drift_during_j1_leg_aborts(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[0,.05,-.05,0,0,0],0)
        mid=e.command[1:]
        for t in (.1,.4,.7): e.observe([-.7,*mid],t,t)
        self.assertEqual(e.phase,'j1')
        with self.assertRaises(ValueError): e.observe([-.6,mid[0]+.3,*mid[1:]],1.0,1.0)

    def test_intermediate_body_phase_does_not_use_final_move_tolerance(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[0,.05,-.05,0,0,0],0,
                        arrive_tol=math.radians(6),label='移动到零位')
        self.assertEqual(e.phase,'body_to_mid')
        self.assertAlmostEqual(e._tol(),EntrySequence.TOL)
        # 复现 17:02 故障：J5 距中间目标还差 5°，在最终 6° 容差内，
        # 但此时绝不能切到 J1 并要求本体冻结。
        almost=list(e.command)
        almost[4]+=math.radians(5)
        for t in (.1,.4,.7):
            e.observe(almost,t,t)
        self.assertEqual(e.phase,'body_to_mid')
        for t in (1.0,1.3,1.6):
            e.observe(e.command,t,t)
        self.assertEqual(e.phase,'j1')

    def test_move_tolerance_governs_final_arrival(self):
        tgt=[.20,.05,-.05,.04,.03,.02]
        def run(arrive_tol, go_precise):
            e=EntrySequence([0]*6,tgt,0,arrive_tol=arrive_tol)
            for t in (.1,.4,.7): e.observe([0,.05,-.05,.04,.03,.02],t,t)
            self.assertEqual(e.phase,'j1')
            for t in (1.0,1.3,1.6): e.observe([.15,.05,-.05,.04,.03,.02],t,t)
            if go_precise:   # 中间 J1 段按 3° 稳定后，最终本体段完成到位
                for t in (1.7,2.0,2.3,2.6): e.observe([.20,.05,-.05,.04,.03,.02],t,t)
            return e.phase
        self.assertEqual(run(math.radians(6),True),'done')
        self.assertEqual(run(None,False),'body_finish')        # 未继续观测最终本体段，不完成

    def test_j1_tolerance_is_never_tighter_than_zero_tol(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[0,.05,-.05,0,0,0],0)
        self.assertEqual(e.phase,'body_to_mid')
        self.assertEqual(e._tol(),e.gate)                      # 本体段用 gate
        mid=e.command[1:]
        for t in (.1,.4,.7): e.observe([-.7,*mid],t,t)
        self.assertEqual(e.phase,'j1')
        self.assertAlmostEqual(e._tol(),EntrySequence.ZERO_TOL)  # J1 段至少放到 3°

    def test_label_reaches_status_message(self):
        e=EntrySequence([-.7,.3,-.2,.1,-.1,.2],[0,.05,-.05,0,0,0],0,label='移动到零位')
        self.assertIn('移动到零位',e.status()['message'])
        self.assertIn('J1',e.status()['message'])


class MoveActionTests(SafetyTests):
    """定点移动 API：目标值、门控与联锁（无 UDP、无 SSH、无线程）。"""

    def _move(self,side,which):
        return {'action':'move','client':'offline-client',
                'safety_epoch':self.app.SAFETY.status()['epoch'],
                'controls':{'mode':'left_joints' if side=='left' else 'right_joints',
                            'move':which}}

    def test_move_to_zero_uses_deploy_clamped_target(self):
        app,s=self.app,self.app.SENDER
        with patch.object(app,'right_read',return_value=(True,[-40,92,-49,-63,-59,40])),\
             patch.object(app,'deploy_running',return_value=True):
            _,code=s.call('move',self._move('right','zero'))
        self.assertEqual(code,200)
        self.assertEqual(s.entries['right'].target,list(app.Q_ZERO))
        # 与左臂一致：起始→零位先同时收回 J1/J4，其余关节保持。
        self.assertEqual(s.entries['right'].phase,'j1_j4')
        self.assertEqual(s.move_side['right'],'zero')
        self.assertEqual([round(math.degrees(v), 5) for v in s.joints],
                         [0,92,-49,0,-59,40])

    def test_move_to_start_from_zero_holds_j1_j4_first(self):
        app,s=self.app,self.app.SENDER
        with patch.object(app,'right_read',return_value=(True,[0]*6)),\
             patch.object(app,'deploy_running',return_value=True):
            _,code=s.call('move',self._move('right','start'))
        self.assertEqual(code,200)
        self.assertEqual(s.entries['right'].phase,'body_j1_j4_hold')
        self.assertEqual(s.joints[0],0)
        self.assertEqual(s.joints[3],0)

    def test_left_move_uses_left_start_pose(self):
        app,s=self.app,self.app.SENDER
        with patch.object(app,'left_read',return_value=(True,[0]*6)),\
             patch.object(app,'deploy_running',return_value=True):
            _,code=s.call('move',self._move('left','start'))
        self.assertEqual(code,200)
        self.assertEqual(s.entries['left'].target,list(app.Q_START_LEFT))
        self.assertEqual(s.left_joints[0],0)

    def test_move_requires_running_deploy(self):
        app,s=self.app,self.app.SENDER
        with patch.object(app,'right_read',return_value=(True,[0]*6)),\
             patch.object(app,'deploy_running',return_value=False):
            body,code=s.call('move',self._move('right','zero'))
        self.assertEqual(code,409)
        self.assertIn('deploy',body['error'])
        self.assertIsNone(s.entries['right'])

    def test_move_rejects_unknown_target(self):
        body,code=self.app.SENDER.call('move',self._move('right','home'))
        self.assertEqual(code,400)

    def test_move_blocked_by_other_page(self):
        app,s=self.app,self.app.SENDER
        s.owner='other-page';s.until=time.monotonic()+10
        with patch.object(app,'right_read',return_value=(True,[0]*6)),\
             patch.object(app,'deploy_running',return_value=True):
            _,code=s.call('move',self._move('right','zero'))
        self.assertEqual(code,409)

    def test_move_respects_latched_stop(self):
        app,s=self.app,self.app.SENDER
        app.SAFETY.stop()
        body,code=s.call('move',self._move('right','zero'))
        self.assertEqual(code,409)
        self.assertIn('停止',body['error'])

    def test_stop_clears_move_state(self):
        app,s=self.app,self.app.SENDER
        with patch.object(app,'right_read',return_value=(True,[0]*6)),\
             patch.object(app,'deploy_running',return_value=True):
            s.call('move',self._move('right','zero'))
        self.assertEqual(s.move_side['right'],'zero')
        with patch.object(app,'stop_all'):
            s.call('stop',dict(self._move('right','zero'),action='stop'))
        self.assertIsNone(s.move_side['right'])
        self.assertIsNone(s.entries['right'])

    def test_move_lease_covers_slow_feedback_read(self):
        # 定点移动没有页面心跳，由 _entry_feedback 续租；租期必须长于一次 SSH 读取
        # （LEFT/RIGHT_READ_PY 内部 1.5s、subprocess 3s 超时），否则慢读取会被 _tick
        # 误判成“页面心跳过期”并触发全局软件停止。
        self.assertGreater(self.app.MOVE_LEASE_S, 3.0)

    def test_status_mask_matches_frame_bits(self):
        s=self.app.SENDER
        self.assertEqual(s.status()['mask'],'0x0001')            # 无会话：仅总使能
        s.owner='offline-client';s.until=time.monotonic()+10
        self.assertEqual(s.status()['mask'],'0x0029')            # +右臂+右夹爪
        s.left_joints=[0]*6
        self.assertEqual(s.status()['mask'],'0x003D')            # +左臂+左夹爪
        s.owner=None;s.left_joints=None
        s.owner_left='offline-client'
        self.assertEqual(s.status()['mask'],'0x0011')            # 仅左夹爪位
        s.owner_left=None

    def test_follow_entry_clears_stale_move_flag(self):
        app,s=self.app,self.app.SENDER
        s.move_side['right']='zero'
        data={'action':'start','client':'offline-client',
              'safety_epoch':app.SAFETY.status()['epoch'],
              'controls':{'mode':'right_joints','right_joints_deg':[10,20,-10,0,0,0]}}
        with patch.object(app,'right_read',return_value=(True,[0]*6)),\
             patch.object(app,'deploy_running',return_value=True):
            _,code=s.call('start',data)
        self.assertEqual(code,200)
        self.assertIsNone(s.move_side['right'])

    def test_vr_start_ignores_stale_web_ik_error(self):
        """VR 启动沿用当前关节目标，不应被此前网页滑块的 IK 失败挡住。"""
        app,s=self.app,self.app.SENDER
        s.ik_err='此前网页目标不可达'
        data={'action':'start','client':'offline-client',
              'safety_epoch':app.SAFETY.status()['epoch'],
              'controls':{'mode':'vr'}}
        start_deg = [math.degrees(v) for v in app.Q_START_RIGHT]
        with patch.object(app,'right_read',return_value=(True,start_deg)),\
             patch.object(app,'deploy_running',return_value=True):
            body,code=s.call('start',data)
        self.assertEqual(code,200,body)
        self.assertIsNone(s.ik_err)
        self.assertTrue(s.vr_on)
        self.assertIsNotNone(s.entries['right'])
        self.assertEqual(s.entries['right'].phase,'done')

class AbortPolicyTests(SafetyTests):
    """中止分级：臂没动过就只撤会话，真的动过才锁存全局软件停止。"""

    def _entry(self,dev):
        e=EntrySequence([0]*6,[.1,.05,-.05,0,0,0],0.0)
        e.max_deviation=dev
        return e

    def test_no_motion_abort_releases_right_without_latch(self):
        app,s=self.app,self.app.SENDER
        s.owner='c1';s.until=time.monotonic()+10;s.joints=[0]*6
        e=self._entry(0.0)
        with s.lock: s.entries['right']=e; s.move_side['right']='zero'
        with patch.object(app,'stop_all') as stop:
            with s.lock: s._abort('right',e,ValueError('进入跟随中止：页面心跳过期'))
            stop.assert_not_called()
        self.assertIsNone(s.entries['right']);self.assertIsNone(s.move_side['right'])
        self.assertIsNone(s.owner)
        self.assertIn('未锁存','' if s.reason is None else s.reason)

    def test_no_motion_abort_releases_left_without_latch(self):
        app,s=self.app,self.app.SENDER
        s.owner_left='c1';s.left_joints=[.2]*6
        e=self._entry(0.0)
        with s.lock: s.entries['left']=e
        with patch.object(app,'stop_all') as stop:
            with s.lock: s._abort('left',e,ValueError('移动到零位中止：关节反馈过期'))
            stop.assert_not_called()
        self.assertIsNone(s.owner_left);self.assertIsNone(s.left_joints)
        self.assertIn('未锁存','' if s.left_reason is None else s.left_reason)

    def test_right_j1_flip_flag_matches_read_script(self):
        # RIGHT_J1_FLIP 必须与真正拼进读脚本的语句一致，避免只改一处。
        app=self.app
        self.assertEqual('-d if cid==0x251' in app.RIGHT_READ_PY, app.RIGHT_J1_FLIP)
        self.assertNotIn('-d if cid==0x251', app.LEFT_READ_PY)   # 左臂始终不取反

    def test_extended_pose_adjust_does_not_detour_through_j1_zero(self):
        # 站在起点位姿(J1=-40,J2=92)只把本体小改一点：J1 不变，也不该绕去半展开。
        e=EntrySequence([math.radians(-40),math.radians(92),math.radians(-49),
                         math.radians(-63),math.radians(-59),math.radians(40)],
                        [math.radians(-40),math.radians(80),math.radians(-44),
                         math.radians(-58),math.radians(-54),math.radians(36)],0)
        self.assertTrue(e.moves_body)
        self.assertEqual(e.phase,'other_joints')      # 直接动本体，不绕行

    def test_move_toward_folded_pose_goes_through_mid_pose(self):
        # 从起点位姿往零位收拢：先在 |J1| 大的一侧收到 J2=60°，再转 J1，再收完。
        # （J1=0 且 J2≈92° 时两臂夹爪在中线相撞，见 03_工具/dual_clearance.py）
        e=EntrySequence([math.radians(-40),math.radians(92),math.radians(-49),
                         math.radians(-63),math.radians(-59),math.radians(40)],
                        [0,math.radians(2.9),math.radians(-2.9),0,0,0],0)
        self.assertEqual(e.phase,'body_to_mid')
        self.assertAlmostEqual(math.degrees(e.command[0]),-40.0,places=6)
        self.assertAlmostEqual(math.degrees(e.command[1]),60.0,places=6)

    def test_stalled_entry_does_not_latch(self):
        # 臂未使能/未上电时关节可能有 1~2° 抖动，但根本没响应指令：
        # 这种“无响应”属于前置条件失败，不应锁存全局软件停止。
        app,s=self.app,self.app.SENDER
        s.owner='c1';s.until=time.monotonic()+10
        e=self._entry(math.radians(2))
        e.stalled=True
        with s.lock: s.entries['right']=e
        with patch.object(app,'stop_all') as stop:
            with s.lock: s._abort('right',e,ValueError('移动到起始位姿中止：机械臂无响应'))
            stop.assert_not_called()
        self.assertIsNone(s.entries['right']);self.assertIsNone(s.owner)

    def test_motion_abort_still_latches(self):
        app,s=self.app,self.app.SENDER
        s.owner='c1';s.until=time.monotonic()+10
        e=self._entry(math.radians(5))
        with s.lock: s.entries['right']=e
        with patch.object(app,'stop_all') as stop:
            with s.lock: s._abort('right',e,ValueError('进入跟随中止：关节反馈过期'))
            stop.assert_called_once()

    def test_sequence_tracks_max_deviation(self):
        e=EntrySequence([0]*6,[.05,.05,-.05,0,0,0],0.0)
        e.observe([0]*6,.1,.1)
        self.assertAlmostEqual(e.max_deviation,0.0)
        e.observe([0,.02,-.02,0,0,0],.4,.4)
        self.assertAlmostEqual(math.degrees(e.max_deviation),math.degrees(.02),places=6)

class EntryIntegrationTests(SafetyTests):
    def test_start_freezes_targets_and_stop_releases_without_latch(self):
        app=self.app;s=app.SENDER;token=app.SAFETY.status()['epoch']
        data={'action':'start','client':'offline-client','safety_epoch':token,'controls':{'right':[.1514,.2885,.2659]}}
        with patch.object(app,'right_read',return_value=(True,[0]*6)), patch.object(app,'deploy_running',return_value=True),patch.object(app,'solve_ik_user',return_value=([.4,.5,-.5,.2,.1,.1],0)):
            _,code=s.call('start',data)
        self.assertEqual(code,200);self.assertEqual(s.joints[0],0)
        entry=s.entries['right'];self.assertIsNotNone(entry)
        data['action']='update';data['controls']['right']=[.3,.3,.3]
        s.call('update',data)
        self.assertEqual(s.entries['right'].target,entry.target)
        # 用户主动停止：撤会话 + 停 deploy，但不锁存全局软件停止（2026-10-22）
        with patch.object(app,'stop_all') as stop:
            s.call('stop',dict(data,action='stop'))
            stop.assert_not_called()
        self.assertIsNone(s.entries['right']);self.assertIsNone(s.owner)
        self.assertFalse(app.SAFETY.status()['stopped'])
        self.assertIn('用户停止','' if s.reason is None else s.reason)

    def test_cancel_while_initial_read_blocks_late_start(self):
        app=self.app;s=app.SENDER
        data={'action':'start','client':'offline-client','safety_epoch':app.SAFETY.status()['epoch'],'controls':{}}
        def read():
            s.call('stop',dict(data,action='stop'))
            return True,[0]*6
        with patch.object(app,'right_read',side_effect=read):
            _,code=s.call('start',data)
        self.assertEqual(code,409);self.assertIsNone(s.owner)

    def test_left_entry_also_holds_j1(self):
        app=self.app;s=app.SENDER
        data={'action':'update','client':'offline-client','safety_epoch':app.SAFETY.status()['epoch'],'controls':{'mode':'left_joints','left_joints_deg':[30,60,-30,0,0,0]}}
        with patch.object(app,'left_read',return_value=(True,[0]*6)),patch.object(app,'deploy_running',return_value=True):
            _,code=s.call('update',data)
        self.assertEqual(code,200);self.assertEqual(s.left_joints[0],0)
        self.assertEqual(s.entries['left'].target,list(app.Q_START_LEFT))

    def test_right_joint_start_uses_unified_start_without_ik(self):
        app=self.app;s=app.SENDER
        data={'action':'start','client':'offline-client','safety_epoch':app.SAFETY.status()['epoch'],'controls':{'mode':'right_joints','right_joints_deg':[30,60,-30,10,20,40],'right_grip':.37}}
        with patch.object(app,'right_read',return_value=(True,[0]*6)),patch.object(app,'deploy_running',return_value=True),patch.object(app,'solve_ik_user',side_effect=AssertionError('joint mode must not use IK')):
            _,code=s.call('start',data)
            self.assertEqual(code,200)
            self.assertEqual(s.joints[0],0)
            self.assertEqual(s.entries['right'].target,list(app.Q_START_RIGHT))
            self.assertAlmostEqual(s.grip,0.0)
            # 模拟入口已完成，随后手动更新不再重建统一起始入口。
            s.entries['right']=None;s.entry_pending['right']=False
            data['action']='update';data['controls']['right_joints_deg']=[0]*6
            _,code=s.call('update',data)
            # C11：全零会被钳到执行端接受范围（J2>=0.05、J3<=-0.05），
            # 这就是 Q_ZERO —— deploy 的 mode=2 本来也会这么裁，现在两边一致。
            self.assertEqual(code,200)
            self.assertEqual([round(v,4) for v in s.joints],[0.0,0.05,-0.05,0.0,0.0,0.0])
            old=s.joints[:]
            data['controls']['right_joints_deg']=[999]*6
            _,code=s.call('update',data)
            self.assertEqual(code,400);self.assertEqual(s.joints,old)


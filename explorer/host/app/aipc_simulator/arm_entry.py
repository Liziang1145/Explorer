"""Feedback-gated entry/move sequencing. No hardware I/O.

关节空间分阶段到位。相位顺序由 `plan_phases` 决定——**它是唯一真源**，
`EntrySequence` 直接消费它，几何预检（arm_geometry.check_entry）也用它重建路径，
避免"预检算的路径"和"实际走的路径"不是同一条。

2026-10-22 第二阶段结论（双臂互撞仿真，.sim_orders2.py / .sim_rev.py）：
  * J1 转过去的时候，本体**不能全展开**：J1=0 且 J2≈92° 时两个夹爪在中线只剩
    9.9 cm，夹爪包络重叠 −0.94 cm（现场实测相撞，与仿真一致）；
  * 也**不能全收拢**：零位附近两臂前臂互穿（−10.4 cm）；
  * 只能在"半展开"构型转 J1。J2 干净区约 45°~75°：
        J2=92° −0.94 cm | 85° +1.10 | 75° +4.56 | 65° +8.19 | 55° +11.69 | 45° +14.86
  * 因此三段式改成：**本体走到 J2 = J2_MID(60°) → 转 J1 → 本体补完**。
    两个方向共用同一套（mid 取在两端点连线上 J2=60° 的那一点）：
        零位→起始：展开到 65% → 转 J1 → 补完（双臂余量 +8.4 cm）
        起始→零位：收到 36% → 转 J1 → 补完
  * 伸展态之间的小调整（J1 不穿中线）仍然一步到位，不绕行。

J1 只在"穿中线危险带"时才分段：两臂夹爪在中线相遇的前提是 |J1| 小，
所以 |J1| 两端都很大的调整（例如 −40°→−30°）直接一起动即可。
"""
import math


def angles(values):
    if not isinstance(values, (list, tuple)) or len(values) != 6 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('需要完整、有限的六轴角度反馈')
    return list(values)


# 相位语义（决定"哪些关节应当保持不动"）
BODY_PHASES = ('body_to_mid', 'body_finish', 'other_joints')   # 本体动，J1 保持
J1_PHASES = ('j1',)                                            # J1 动，本体保持
J1_J4_PHASES = ('j1_j4',)                                      # J1/J4 动，其余保持
BODY_J1_J4_PHASES = ('body_j1_j4_hold',)                       # J2/J3/J5/J6 动，J1/J4 保持
FREE_PHASES = ('all_joints',)                                  # 六轴一起动
HOLD_BODY = ('done',)                                          # 本体保持在目标

_PHASE_TEXT = {
    'body_to_mid': '本体先到半展开（J1 保持）',
    'j1': 'J1 偏航到位中（本体保持）',
    'j1_j4': 'J1/J4 到位中（其余关节保持）',
    'body_j1_j4_hold': '其余关节到位中（J1/J4 保持）',
    'body_finish': '本体补完到位中（J1 保持）',
    'other_joints': '本体到位中（J1 保持）',
    'all_joints': '六轴同时到位中',
    'done': '已到位',
}


def slew_command(current, target, max_step):
    """所有关节同步朝目标逼近，每轴单周期增量不超过 max_step。"""
    current, target = angles(current), angles(target)
    if not isinstance(max_step, (int, float)) or not math.isfinite(max_step) or max_step <= 0:
        raise ValueError('max_step 必须为有限正数')
    return [a + max(-max_step, min(max_step, b - a)) for a, b in zip(current, target)]


def _mid_body(initial, target, cls):
    """取两端点连线上 J2 = J2_MID 的那一点（只算本体 J2–J6）。"""
    d2 = target[1] - initial[1]
    f = 0.5 if abs(d2) < 1e-6 else (cls.J2_MID - initial[1]) / d2
    f = min(cls.MID_MAX_FRAC, max(cls.MID_MIN_FRAC, f))
    return [initial[i] + f * (target[i] - initial[i]) for i in range(1, 6)]


def plan_phases(initial, target, seq=None, j1_order=None):
    """返回将要依次下发的命令序列 [(相位名, 六轴命令)]。**相位顺序的唯一真源**。

    j1_order 仅用于现场指定的左臂定点验证：first=先 J1 后本体，last=先本体后 J1。
    默认 None 保持经过双车几何验证的半展开三段式。
    """
    cls = seq or EntrySequence
    initial, target = angles(initial), angles(target)
    need_body = any(abs(a - b) > cls.TOL for a, b in zip(initial[1:], target[1:]))
    need_j1 = abs(target[0] - initial[0]) > cls.ZERO_GATE
    if not need_j1:
        # other_joints/done 阶段要求 J1 保持，指令也必须保持起始实测值。
        # 不能判定“不需要转 J1”后却仍把略有不同的 target[0] 发下去。
        target[0] = initial[0]

    if not need_body and not need_j1:
        return [('done', list(target))]
    if not need_body:                       # 只转 J1（本体本来就在目标）
        return [('j1', list(target))]
    if not need_j1:                         # 只动本体
        return [('other_joints', list(target))]

    a, b = initial[0], target[0]
    if j1_order == 'first':
        first = list(initial)
        first[0], first[3] = target[0], target[3]
        return [('j1_j4', first), ('other_joints', list(target))]
    if j1_order == 'last':
        first = list(target)
        first[0], first[3] = initial[0], initial[3]
        return [('body_j1_j4_hold', first), ('j1_j4', list(target))]
    if j1_order is not None:
        raise ValueError('未知 J1 相位顺序')
    crosses_center = (a * b <= 0.0) or min(abs(a), abs(b)) < cls.J1_CENTER_BAND
    if not crosses_center:                  # 两端 |J1| 都大，不经过中线危险带
        return [('all_joints', list(target))]

    mid = _mid_body(initial, target, cls)
    return [('body_to_mid', [a, *mid]),
            ('j1', [b, *mid]),
            ('body_finish', list(target))]


class EntrySequence:

    TOL = math.radians(1.0)          # 阶段到位/保持判定
    STABLE = 0.5                     # 到位后需保持的时间（秒）
    FRESH = 2.0                      # 反馈新鲜度上限（秒）
    TIMEOUT = 45.0                   # 每个阶段的上限（秒）
    ZERO_GATE = math.radians(2.0)    # J1 变化超过此值才算"需要转 J1"
    ZERO_TOL = math.radians(3.0)     # J1 到位判定，覆盖实测零点偏置（左臂 J1 ≈ 2°）
    # J1 穿中线危险带：|J1| 小于此值时两个夹爪靠向中线
    J1_CENTER_BAND = math.radians(25.0)
    # 转 J1 时本体的展开度（J2）。见模块文档的余量表：60° 落在干净区中部。
    J2_MID = math.radians(60.0)
    MID_MIN_FRAC = 0.25
    MID_MAX_FRAC = 0.80

    def __init__(self, current, target, now, arrive_tol=None, label='进入跟随',
                 zero_tol=None, j1_order=None, trajectory=None):
        self.j1_order = j1_order
        self.initial = angles(current)
        self.target = angles(target)
        self.trajectory = trajectory
        self._command = list(self.initial)
        if trajectory is None and abs(self.target[0] - self.initial[0]) <= self.ZERO_GATE:
            # 普通入口完成后的持续目标同样不能偷改 J1，否则入口结束下一拍仍会转动。
            self.target[0] = self.initial[0]
        self.arrive_tol = self.TOL if arrive_tol is None else arrive_tol
        # 到位判据：定点移动用宽松容差覆盖实测静态偏置；跟随进入保持 TOL 不变。
        self.gate = max(self.TOL, self.arrive_tol)
        self.zero_tol = self.ZERO_TOL if zero_tol is None else zero_tol
        self.label = label
        self.observed = now
        self.started = now
        self.stable_since = None
        self.samples = 0
        self.error = None
        # 已观测到的最大关节偏离（相对起始实测值）。用于区分"前置条件失败（臂根本没动）"
        # 与"运动过程中失效（必须锁存停止）"。
        self.max_deviation = 0.0
        # 机械臂长时间完全不动时置 True：属于前置条件失败（未使能/未上电/不在 CAN 模式）。
        self.stalled = False
        # C02：把"没观察到位移"和"没有证据"分开。
        #   sent_any      —— 至少有一帧带本臂目标的数据真的发出去了
        #   have_feedback —— 发出之后至少收到过一次通过校验的六轴反馈
        # 只有 sent_any 且 have_feedback 时，"位移很小"才能当作"没动"的证据；
        # 发了目标却一直没反馈，属于"反馈未知"，必须按故障处理。
        self.sent_any = False
        self.have_feedback = False
        self.moves_body = any(abs(a - b) > self.TOL
                              for a, b in zip(self.initial[1:], self.target[1:]))
        if trajectory is None:
            self.plan = plan_phases(self.initial, self.target, self, self.j1_order)
        else:
            times = trajectory.get('times')
            points = trajectory.get('q')
            if (not times or not points or len(times) != len(points) or len(times) < 2
                    or any(not math.isfinite(t) for t in times)
                    or any(b <= a for a, b in zip(times, times[1:]))
                    or any(len(angles(q)) != 6 for q in points)):
                raise ValueError('规划轨迹时间轴或六轴路点无效')
            if (max(abs(a-b) for a, b in zip(points[0], self.initial)) > self.TOL
                    or max(abs(a-b) for a, b in zip(points[-1], self.target)) > self.TOL):
                raise ValueError('规划轨迹端点与本段实测起点／目标不一致')
            self.plan = [('all_joints', list(self.target))]
            self._command = list(points[0])
        self.index = 0
        self.phase = self.plan[0][0]
        # 保持判定的基准用**实测值**而不是指令值：实测存在静态偏置
        # （左臂 J4 约 −4.5°、J6 约 −2.9°、J1 零点约 2°），拿指令值当基准会误判离位。
        self.hold_ref = list(self.initial)

    # ---------------- 指令 ----------------
    @property
    def command(self):
        return list(self._command if self.trajectory is not None else self.plan[self.index][1])

    def _hold_indices(self):
        ph = self.phase
        if ph in BODY_PHASES:
            return (0,)
        if ph in J1_PHASES:
            return (1, 2, 3, 4, 5)
        if ph in J1_J4_PHASES:
            return (1, 2, 4, 5)
        if ph in BODY_J1_J4_PHASES:
            return (0, 3)
        if ph in HOLD_BODY:
            return (1, 2, 3, 4, 5)
        return ()

    def _tol(self):
        # 中间阶段必须真正稳定后才可切换：最终 6° 停车容差若用于 body_to_mid，
        # 本体会在仍有数度误差时进入 J1 阶段，随后继续追击中间目标并被保持保护误杀。
        # 最终阶段仍保留 arrive_tol/zero_tol，不收紧既有到位标准。
        yaw_phase = self.phase in J1_PHASES + J1_J4_PHASES
        if self.index + 1 < len(self.plan):
            return max(self.TOL, self.zero_tol) if yaw_phase else self.TOL
        return max(self.gate, self.zero_tol) if yaw_phase else self.gate

    def _hold_ref(self):
        # 'done' 阶段要保持的是**目标**本体；其它阶段用"进入本段时的实测值"，
        # 这样静态偏置不会被误判成离位。
        return list(self.target) if self.phase in HOLD_BODY else list(self.hold_ref)

    # ---------------- 反馈推进 ----------------
    def check(self, now):
        if now - self.observed > self.FRESH:
            raise ValueError(f'{self.label}中止：关节反馈过期')
        if now - self.started > self.TIMEOUT:
            raise ValueError(f'{self.label}中止：阶段到位超时')
        if self.trajectory is not None:
            # 时间参考只在每拍检查中推进；最终端点后保持目标，不循环、不回跳。
            elapsed = max(0.0, now - self.started)
            times = self.trajectory['times']
            points = self.trajectory['q']
            index = 0
            for i in range(1, len(times)):
                if times[i] > elapsed:
                    break
                index = i
            if index + 1 >= len(times) or elapsed >= times[-1]:
                self._command = list(points[-1])
            else:
                ratio = ((elapsed-times[index]) / (times[index+1]-times[index]))
                ratio = min(1.0, max(0.0, ratio))
                self._command = [a + ratio*(b-a) for a, b in
                                 zip(points[index], points[index+1])]

    def observe(self, current, sampled_at, now):
        current = angles(current)
        self.check(now)
        if sampled_at <= self.observed:
            return
        if now - sampled_at > self.FRESH:
            raise ValueError(f'{self.label}中止：读取结果过期')
        self.observed = sampled_at
        self.have_feedback = True          # C02：这一帧是通过校验的真实反馈
        self.max_deviation = max(self.max_deviation,
                                 max(abs(a - b) for a, b in zip(current, self.initial)))

        cmd = self.command
        tol = self._tol()
        # 1) 本阶段"应当保持"的关节不许漂出去
        href = self._hold_ref()
        for i in self._hold_indices():
            delta = current[i] - href[i]
            if abs(delta) > self.gate:
                detail = (f'J{i + 1} 参考 {math.degrees(href[i]):.3f}°，'
                          f'实测 {math.degrees(current[i]):.3f}°，'
                          f'偏差 {math.degrees(delta):+.3f}°，'
                          f'指令 {math.degrees(cmd[i]):.3f}°，'
                          f'容差 {math.degrees(self.gate):.3f}°')
                if self.phase in BODY_PHASES + BODY_J1_J4_PHASES:
                    raise ValueError(f'{self.label}中止：本体阶段保持关节发生偏移（{detail}）')
                if self.phase in J1_PHASES + J1_J4_PHASES:
                    raise ValueError(f'{self.label}中止：偏航阶段其他关节发生偏移（{detail}）')
                raise ValueError(f'{self.label}中止：到位后本体离开范围（{detail}）')
        # 2) 应动的关节是否到位。规划段必须比较最终目标，不能在中间参考点误判完成。
        if self.phase in FREE_PHASES or self.phase in HOLD_BODY:
            moving = range(6)
        elif self.phase in BODY_PHASES:
            moving = range(1, 6)
        elif self.phase in BODY_J1_J4_PHASES:
            moving = (1, 2, 4, 5)
        elif self.phase in J1_J4_PHASES:
            moving = (0, 3)
        else:
            moving = (0,)
        arrival = self.target if self.trajectory is not None else cmd
        reached = all(abs(current[i] - arrival[i]) <= tol for i in moving)
        if self.trajectory is not None:
            # 小幅度轨迹的总关节变化可能小于到位容差；必须播完时间轴，不能在起点提前释放。
            reached = reached and now - self.started >= self.trajectory['times'][-1]

        if not reached:
            self.stable_since = None
            self.samples = 0
            return
        self.samples += 1
        if self.stable_since is None:
            self.stable_since = sampled_at
        if self.samples >= 3 and sampled_at - self.stable_since >= self.STABLE:
            if self.index + 1 < len(self.plan):
                self.index += 1
                self.phase = self.plan[self.index][0]
                self.hold_ref = list(current)
            else:
                self.phase = 'done'
            self.started = now
            self.stable_since = None
            self.samples = 0

    def status(self):
        return {'phase': self.phase,
                'message': f'{self.label}：{_PHASE_TEXT.get(self.phase, self.phase)}'}

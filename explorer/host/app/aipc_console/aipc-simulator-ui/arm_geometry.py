"""支架干涉的运行时几何预检（离线计算，不触碰任何设备）。

来源与自检
----------
FK 链 `_DTF`/`_FR` 与 `arm_console.py`、`03_工具/joint_fk_viewer.html` 完全同源，
已用两个已知基准值校验过（q=0 法兰 (0, 5.613, 21.328) cm；水平构型法兰
(-15.164, 28.841, 26.614) cm），与工程文档值吻合 < 0.3 mm。
连杆包络半径取自 `assets/meshes/*.STL` 的实测分箱。
扫掠结果与 `03_工具/traj_clearance.py` 一致（起始↔零位最小余量约 +6.0/+6.5 cm）。

坐标与假设
----------
用户/底盘系：+X 右 / +Y 前 / +Z 上；左臂底座 (0,0,0)，右臂底座 (31,0,0)，单位 cm。
支架节点取自 `obstacle-preview.html` / 交接文档第八节。
**杆半径默认按 2 cm 假设**，右臂底座朝向按"与左臂同向"假设——两项都需实测后核对。

用途
----
运动前把"将要下发的关节路径"离散采样，算与支架的最小余量；不足 `MIN_MARGIN_CM`
就拒绝。这是目前唯一能自动防住"把臂送进支架"的检查。
"""
import math

# ---------------- FK（与 arm_console.py 逐字同源） ----------------
def _mm(a, b):
    return tuple(tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]
                       for j in range(3)) for i in range(3))


def _mv(a, v):
    return (a[0][0] * v[0] + a[0][1] * v[1] + a[0][2] * v[2],
            a[1][0] * v[0] + a[1][1] * v[1] + a[1][2] * v[2],
            a[2][0] * v[0] + a[2][1] * v[1] + a[2][2] * v[2])


def _rt(x, y, z, roll, pitch, yaw):
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cw, sw = math.cos(yaw), math.sin(yaw)
    Rx = ((1, 0, 0), (0, cr, -sr), (0, sr, cr))
    Ry = ((cp, 0, sp), (0, 1, 0), (-sp, 0, cp))
    Rz = ((cw, -sw, 0), (sw, cw, 0), (0, 0, 1))
    return _mm(_mm(Rz, Ry), Rx), (x, y, z)


_DTF = (_rt(0, 0, 0.123, 0, 0, 0),
        _rt(0, 0, 0, math.pi / 2, -0.1359, -math.pi),
        _rt(0.28503, 0, 0, 0, 0, -1.7939),
        _rt(-0.021984, -0.25075, 0, math.pi / 2, 0, 0),
        _rt(0, 0, 0, -math.pi / 2, 0, 0),
        _rt(0, -0.091, 0, math.pi / 2, 0, 0))
_FR = ((0, -1, 0), (1, 0, 0), (0, 0, 1))

# 连杆沿轴局部半径（cm，取 STL 分箱保守上界）
_LINK_R = {
    '底座立柱': [(-0.043, 3.6), (0.000, 3.7), (0.012, 5.17), (0.030, 4.2)],
    '上臂':     [(-0.0315, 3.2), (0.000, 6.6), (0.100, 3.2), (0.250, 3.0), (0.3165, 4.8)],
    '前臂':     [(-0.2148, 3.0), (-0.150, 3.4), (-0.050, 3.6), (0.000, 5.65), (0.030, 4.0)],
    '腕部偏置': [(-0.090, 3.4), (0.000, 4.18), (0.0235, 3.5)],
}
_LINK_ORDER = ['底座立柱', '上臂', '前臂', '腕部偏置']

# 支架（cm）；与 obstacle-preview.html 一致：仅 1-3 / 2-3 / 3-4 三根杆
_P1, _P2, _P3, _P4 = (0.0, -31.0, 0.0), (31.0, -31.0, 0.0), (16.0, -16.0, 16.0), (16.0, 4.0, 30.0)
BRACKET = [('P1-P3(左后斜撑)', _P1, _P3),
           ('P2-P3(右后斜撑)', _P2, _P3),
           ('P3-P4(中间上杆)', _P3, _P4)]

# 2026-11-01 安装复核：V3 CAD X/Y＋现场安装面 Z；两臂中心距 30.51 cm。
ARM_BASE_CM = {'left': (0.0, 0.0, 0.0), 'right': (30.51, 0.0, 0.0)}

# 支架杆件截面：**矩形刀片 30 mm 宽 × 4 mm 厚**（用户实测 2026-10-23），不是圆杆。
# 障碍按"外接圆柱"处理以保证保守：外接圆半径 = sqrt(15² + 2²) = 15.13 mm。
# 这样无论刀片朝哪个方向、无论从平面还是从棱边接近，模型障碍都不小于真实实体，
# 因此算出的余量是**下界**（真实余量 ≥ 此值）。若将来换成圆杆，改回实际半径即可。
ROD_R_CM = 1.513      # cm —— 刀片外接圆半径（由 30×4 mm 截面推得）
MIN_MARGIN_CM = 2.0   # 允许的最小余量（中心线距离 − 连杆半径 − 杆半径）


def fk_chain(q):
    """六轴角（rad）→ 7 个关节原点（用户系，米）。"""
    R = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    t = (0.0, 0.0, 0.0)
    pts = [t]
    for i in range(6):
        dt = _mv(R, _DTF[i][1])
        t = (t[0] + dt[0], t[1] + dt[1], t[2] + dt[2])
        pts.append(t)
        R = _mm(_mm(R, _DTF[i][0]), _rt(0, 0, 0, 0, 0, q[i])[0])
    return [_mv(_FR, p) for p in pts]


def _local_r(link, s):
    prof = _LINK_R[link]
    pos = s * (prof[-1][0] - prof[0][0]) + prof[0][0]
    lo = prof[0]
    hi = prof[-1]
    for p, r in prof:
        if p <= pos:
            lo = (p, r)
        if p >= pos:
            hi = (p, r)
            break
    return max(lo[1], hi[1])


def links_cm(q, arm):
    """→ [(连杆名, p0, p1, 起点半径, 终点半径)]，cm。"""
    bx, by, bz = ARM_BASE_CM[arm]
    pts = [(p[0] * 100 + bx, p[1] * 100 + by, p[2] * 100 + bz) for p in fk_chain(q)]
    out, k = [], 0
    for i in range(6):
        a, b = pts[i], pts[i + 1]
        if math.dist(a, b) < 1e-6:
            continue
        name = _LINK_ORDER[k] if k < len(_LINK_ORDER) else 'link%d' % k
        k += 1
        peak = max(r for _, r in _LINK_R[name])
        out.append((name, a, b, _local_r(name, 0.0), peak))
    return out


def seg_seg_st(p1, p2, p3, p4):
    """两线段最短距离，返回 (距离, 第一段参数 s, 第二段参数 t)。

    双臂互撞检查需要**两段各自的参数**去查各自的包络半径；只拿一个参数会让
    半径查错位置（曾经因此把余量算大）。线段-线段（支架）检查仍用 `_seg_seg`。
    """
    d1 = [p2[i] - p1[i] for i in range(3)]
    d2 = [p4[i] - p3[i] for i in range(3)]
    r = [p1[i] - p3[i] for i in range(3)]
    a = sum(x * x for x in d1)
    e = sum(x * x for x in d2)
    f = sum(d2[i] * r[i] for i in range(3))
    eps = 1e-12
    if a <= eps and e <= eps:
        return math.dist(p1, p3), 0.0, 0.0
    if a <= eps:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = sum(d1[i] * r[i] for i in range(3))
        if e <= eps:
            t, s = 0.0, min(1.0, max(0.0, -c / a))
        else:
            b = sum(d1[i] * d2[i] for i in range(3))
            den = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / den)) if den > eps else 0.0
            t = (b * s + f) / e
            if t < 0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    c1 = [p1[i] + d1[i] * s for i in range(3)]
    c2 = [p3[i] + d2[i] * t for i in range(3)]
    return math.dist(c1, c2), s, t


def _seg_seg(p1, p2, p3, p4):
    """两线段最短距离，返回 (距离, 第一段参数 s)。"""
    d, s, _t = seg_seg_st(p1, p2, p3, p4)
    return d, s


def pose_margin(q, arm, rod_r_cm=None):
    """单个构型的余量（cm）→ (margin, 中心线距离, 连杆名, 杆名)。"""
    rod = ROD_R_CM if rod_r_cm is None else rod_r_cm
    best = None
    for name, a, b, _r0, _r1 in links_cm(q, arm):
        for rod_name, b0, b1 in BRACKET:
            d, s = _seg_seg(a, b, b0, b1)
            margin = d - (_local_r(name, s) + rod)
            if best is None or margin < best[0]:
                best = (margin, d, name, rod_name)
    return best


def _rate_limited(q0, q1, vmax, dt):
    step = vmax * dt
    q = list(q0)
    path = [tuple(q)]
    for _ in range(20000):
        if max(abs(q1[i] - q[i]) for i in range(6)) < 1e-9:
            break
        for i in range(6):
            d = q1[i] - q[i]
            if d > step:
                d = step
            if d < -step:
                d = -step
            q[i] += d
        path.append(tuple(q))
    return path


def check_entry(current, target, arm, *, vmax=0.4, dt=0.01, stride=2,
                rod_r_cm=None, min_margin_cm=None, j1_order=None):
    """按**三段式的真实相位顺序**重建路径再预检。

    不能只算"六轴一起动"的单段路径：零位→起始位姿 的单段路径余量只有 +3.5 cm，
    而实际走的是"先在 J1=0 展开、再偏航"，余量 +6.1 cm。两种算法结论差很多，
    所以必须跟 `arm_entry.plan_phases` 用同一套顺序。
    """
    from arm_entry import plan_phases
    nxt = list(current)
    worst = None
    steps = []
    for name, cmd in plan_phases(list(current), list(target), j1_order=j1_order):
        r = check_path(nxt, cmd, arm, vmax=vmax, dt=dt, stride=stride,
                       rod_r_cm=rod_r_cm, min_margin_cm=min_margin_cm)
        steps.append((name, r['margin_cm']))
        if worst is None or (r['margin_cm'] is not None and r['margin_cm'] < worst['margin_cm']):
            worst = r
        nxt = cmd
    worst = dict(worst or {})
    worst['phases'] = steps
    worst['ok'] = bool(worst.get('margin_cm') is not None
                       and worst['margin_cm'] >= (MIN_MARGIN_CM if min_margin_cm is None
                                                  else min_margin_cm))
    return worst


def check_path(q_from, q_to, arm, *, vmax=0.4, dt=0.01, stride=4,
               rod_r_cm=None, min_margin_cm=None):
    """沿"将要下发"的实际关节路径采样，返回预检结论。

    deploy 是逐轴饱和限速再关节空间线性插补，所以路径就是 `_rate_limited` 的结果；
    stride 用于跳采样（默认每 4 拍取一个，40ms，够密且快）。

    返回 dict(ok, margin_cm, distance_cm, link, rod, at_deg, samples)
    """
    need = MIN_MARGIN_CM if min_margin_cm is None else min_margin_cm
    if not isinstance(q_from, (list, tuple)) or not isinstance(q_to, (list, tuple)) \
            or len(q_from) != 6 or len(q_to) != 6:
        return dict(ok=False, error='需要两个六轴角度', margin_cm=None)
    path = _rate_limited(q_from, q_to, vmax, dt)
    worst = None
    taken = 0
    for idx, q in enumerate(path):
        if idx % stride and idx != len(path) - 1:
            continue
        taken += 1
        m = pose_margin(q, arm, rod_r_cm)
        if worst is None or m[0] < worst[0][0]:
            worst = (m, q)
    margin, dist, link, rod = worst[0]
    return dict(ok=margin >= need,
                margin_cm=round(margin, 2),
                distance_cm=round(dist, 2),
                link=link, rod=rod,
                at_deg=[round(math.degrees(v), 1) for v in worst[1]],
                samples=taken,
                need_cm=round(need, 2),
                rod_r_cm=ROD_R_CM if rod_r_cm is None else rod_r_cm)

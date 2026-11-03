import math
import numpy as np
import arm_console as app
import arm_geometry as geometry
from vla_motion_planner import StaticCollisionModel

xyz = [-0.0809, 0.3547, 0.0884]
ok, left = app.left_read()
ok_r, right = app.right_read()
assert ok and ok_r, (left, right)
current = np.radians(app.angles(left))
other = np.radians(app.angles(right))
rotation = app._mm(app._FR, app._fk(current)[1])
target, error = app.solve_layered_j5_pose_user(xyz, rotation, tuple(current), side='left')
print('target_deg', np.degrees(target).tolist() if target is not None else None, error)
model = StaticCollisionModel(other_arm_q={'right': other})
for label, q in [('current', current), ('target', target)]:
    print('\n', label, 'pose', model.pose(q, 'left'))
    links = geometry.links_cm(list(q), 'left')
    values = []
    for name, a, b, r0, r1 in links:
        if name == '底座立柱':
            continue
        z = min(a[2]+s*(b[2]-a[2]) for s in np.linspace(0, 1, 7))
        values.append((z, name, list(a), list(b)))
    print('lowest_links', sorted(values)[:4])
    ga, gb = model._gripper_capsule(q, 'left')
    print('gripper', ga.tolist(), gb.tolist(), 'margins', ga[2]-model.gripper_radius, gb[2]-model.gripper_radius)
    print('required_margin_cm', model.min_margin)

# -*- coding: utf-8 -*-
"""生成一个可复现的 VLA 离线规划示例，不连接硬件。"""
import json
from pathlib import Path

import vla_motion_planner as planner

app = planner.app
goal = app.Q_LEFT_POS3
xyz = app._fk_points(goal, 'left')[0][5]
result = planner.plan_j5_xyz(
    'left', xyz, orientation=planner._rotation(goal, 'left'),
    current_q=app.Q_START_LEFT, other_arm_q={'right': app.Q_START_RIGHT}, seed=7)
result['example'] = '左臂起始位到位置3；保持位置3自身姿态'
result['online_control_connected'] = False
result['step_exact_mesh_connected'] = False
result['not_covered'] = ['STEP精确底盘网格', '夹爪与持物精确外形', 'Gemini 335动态障碍', '真机联调']
output = Path(__file__).resolve().parent / '输出' / 'VLA离线规划示例.json'
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key not in ('times', 'q')},
                 ensure_ascii=False, indent=2))
print(output)

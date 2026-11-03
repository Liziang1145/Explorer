# -*- coding: utf-8 -*-
"""将 AIPC 连续采集样本转换为 LeRobot/SmolVLA 数据集；纯离线处理。"""
import argparse
import json
import math
from pathlib import Path
import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/home/apex/datasets/vla_cup_grasp'))
    parser.add_argument('--output', type=Path, default=Path('/home/apex/datasets/lerobot/cup_pick_v1'))
    parser.add_argument('--repo-id', default='local/cup_pick_v1')
    parser.add_argument('--task', default='Pick up the cup.')
    parser.add_argument('--min-episode', type=int, default=3)
    args = parser.parse_args()
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    if args.output.exists():
        raise ValueError('输出目录已存在，为避免混入旧数据已停止：'+str(args.output))
    features = {
        'observation.images.head': {'dtype':'video', 'shape':(720,1280,3), 'names':['height','width','channel']},
        'observation.state': {'dtype':'float32', 'shape':(7,),
            'names':['j1_rad','j2_rad','j3_rad','j4_rad','j5_rad','j6_rad','gripper_close']},
        'action': {'dtype':'float32', 'shape':(7,),
            'names':['j1_target_rad','j2_target_rad','j3_target_rad','j4_target_rad','j5_target_rad','j6_target_rad','gripper_close_target']},
    }
    dataset = LeRobotDataset.create(repo_id=args.repo_id, root=args.output, fps=5,
        features=features, robot_type='dual-arm-left-seven-dim', use_videos=True,
        image_writer_threads=2, image_writer_processes=0)
    summary = []
    for folder in sorted(args.source.glob('cup_*')):
        number = int(folder.name.split('_')[-1])
        if number < args.min_episode:
            continue
        manifest = json.loads((folder/'manifest.json').read_text())
        if manifest.get('result') != 'success' or manifest.get('errors'):
            continue
        records = [json.loads(line) for line in (folder/'records.jsonl').open()]
        for record in records:
            if not record['actual_feedback_ok']['left']:
                raise ValueError(folder.name+' 存在无效左臂反馈')
            image = cv2.imread(str(folder/record['rgb_file']))
            if image is None or image.shape != (720,1280,3):
                raise ValueError(folder.name+' 图像尺寸异常')
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            state = [math.radians(v) for v in record['actual_left_deg']]
            state.append(float(record['control_status']['control']['left']['grip']))
            target = record['control_status']['control']['left'].get('joints_deg')
            if target is None:
                target = record['actual_left_deg']
            action = [math.radians(v) for v in target]
            action.append(float(record['control_status']['control']['left']['grip']))
            dataset.add_frame({'observation.images.head':image,
                'observation.state':np.asarray(state,dtype=np.float32),
                'action':np.asarray(action,dtype=np.float32),
                'task':args.task})
        dataset.save_episode()
        summary.append({'sample':folder.name,'frames':len(records)})
    dataset.finalize()
    (args.output/'conversion_summary.json').write_text(json.dumps({'episodes':summary,
        'source':str(args.source),'task':args.task,'state':'left actual radians + gripper open',
        'action':'left target radians + gripper open','depth_used':False},indent=2))
    print(json.dumps({'ok':True,'output':str(args.output),'episodes':summary},ensure_ascii=False))


if __name__ == '__main__':
    main()

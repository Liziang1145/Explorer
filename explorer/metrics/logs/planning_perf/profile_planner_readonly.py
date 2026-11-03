#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立离线规划分段计时；无 HTTP、CAN、UDP 或机械臂执行调用。"""
import argparse
import collections
import json
import time

import vla_motion_planner as planner
import exact_collision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('xyz', nargs=3, type=float)
    parser.add_argument('--nearest-orientation', action='store_true')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    elapsed = collections.defaultdict(float)
    calls = collections.defaultdict(int)
    phase = ['initialization']

    def timed(key, function, *args, **kwargs):
        started = time.perf_counter()
        result = function(*args, **kwargs)
        elapsed[key] += time.perf_counter() - started
        calls[key] += 1
        return result

    original_ik = planner.app.solve_layered_j5_pose_user
    def ik(*args, **kwargs):
        return timed('ik', original_ik, *args, **kwargs)
    planner.app.solve_layered_j5_pose_user = ik

    original_init = exact_collision.ExactMeshCollisionModel.__init__
    def init(self, *args, **kwargs):
        return timed('collision_model_init', original_init, self, *args, **kwargs)
    exact_collision.ExactMeshCollisionModel.__init__ = init

    original_pose = exact_collision.ExactMeshCollisionModel.pose
    def pose(self, q, side):
        key = 'pose__' + phase[0]
        return timed(key, original_pose, self, q, side)
    exact_collision.ExactMeshCollisionModel.pose = pose

    original_solve = planner.RRTConnect.solve
    def solve(self, q0, q1):
        phase[0] = 'path_search'
        result = timed('path_search_total', original_solve, self, q0, q1)
        phase[0] = 'shortcut'
        return result
    planner.RRTConnect.solve = solve

    original_shortcut = planner.shortcut
    def shortcut(*args, **kwargs):
        phase[0] = 'shortcut'
        return timed('shortcut_total', original_shortcut, *args, **kwargs)
    planner.shortcut = shortcut

    original_resample = planner.resample
    def resample(*args, **kwargs):
        phase[0] = 'resample'
        result = timed('resample_total', original_resample, *args, **kwargs)
        phase[0] = 'before_toppra'
        return result
    planner.resample = resample

    original_parameterize = planner._parameterize
    def parameterize(*args, **kwargs):
        phase[0] = 'toppra'
        result = timed('toppra_total', original_parameterize, *args, **kwargs)
        phase[0] = 'final_mesh_recheck'
        return result
    planner._parameterize = parameterize

    started = time.perf_counter()
    result = planner.plan_j5_xyz(
        'left', args.xyz, current_q=planner.app.Q_START_LEFT,
        collision_mode='exact', check_gripper=False, collision_workers=args.workers,
        nearest_orientation=args.nearest_orientation)
    total_ms = (time.perf_counter() - started) * 1000
    report = {
        'safety': 'offline_only_no_motion_interfaces',
        'total_ms': round(total_ms, 3),
        'phases_ms': {key: round(value * 1000, 3) for key, value in elapsed.items()},
        'calls': dict(calls),
        'unattributed_ms': round(total_ms - sum(elapsed.values()) * 1000, 3),
        'search': result['search'],
        'path_nodes_before_timing': result['path_nodes_before_timing'],
        'timed_points': len(result['q']),
        'mesh_pose_checks': result['mesh_pose_checks'],
        'mesh_distance_checks': result['mesh_distance_checks'],
        'duration_s': result['duration_s'],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""VLA 离线运动规划单元测试；不连接任何设备。"""
import pathlib
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vla_motion_planner as planner
import transfer_trajectory


class WallCollision(planner.StaticCollisionModel):
    """受控测试环境：q[0]=0 的薄墙，绕过墙需要其他关节配合。"""

    def __init__(self):
        super().__init__(min_margin_cm=0.0)

    def pose(self, q, side):
        q = np.asarray(q, dtype=float)
        if not np.all(np.isfinite(q)) or not np.all(q >= planner.app.JOINT_LO) \
                or not np.all(q <= planner.app.JOINT_HI):
            return planner.CollisionResult(False, '关节限位', -1.0)
        if abs(q[0]) < 0.08 and abs(q[1]) < 0.35:
            return planner.CollisionResult(False, '测试薄墙', -1.0)
        return planner.CollisionResult(True, '测试环境通过', 1.0)


class VlaMotionPlannerTests(unittest.TestCase):
    def setUp(self):
        self.start = np.asarray(planner.app.Q_START_LEFT)
        self.goal = np.asarray(planner.app.Q_LEFT_POS3)
        self.target_xyz = planner.app._fk_points(self.goal, 'left')[0][5]
        self.orientation = planner._rotation(self.goal, 'left')

    def plan(self):
        return planner.plan_j5_xyz(
            'left', self.target_xyz, orientation=self.orientation,
            current_q=self.start, other_arm_q={'right': planner.app.Q_START_RIGHT})

    def test_real_target_plan_has_exact_endpoints_and_safe_timed_path(self):
        result = self.plan()
        self.assertEqual(result['search']['direct'], True)
        self.assertGreater(result['duration_s'], 0.0)
        self.assertEqual(len(result['times']), len(result['q']))
        np.testing.assert_allclose(result['q'][0], self.start, atol=1e-9)
        np.testing.assert_allclose(result['q'][-1], self.goal, atol=1e-8)
        times = np.asarray(result['times'])
        q = np.asarray(result['q'])
        self.assertTrue(np.all(np.diff(times) > 0.0))
        self.assertTrue(np.all(q >= np.asarray(planner.app.JOINT_LO)))
        self.assertTrue(np.all(q <= np.asarray(planner.app.JOINT_HI)))
        velocities = np.abs(np.diff(q, axis=0) / np.diff(times)[:, None])
        self.assertLessEqual(float(np.max(velocities)), transfer_trajectory.VELOCITY_LIMIT+1e-4)
        model = planner.StaticCollisionModel({'right': planner.app.Q_START_RIGHT})
        for a, b in zip(q, q[1:]):
            self.assertTrue(model.segment(a, b, 'left').ok)

    def test_same_seed_is_reproducible(self):
        first, second = self.plan(), self.plan()
        self.assertEqual(first, second)

    def test_unreachable_pose_is_explicitly_rejected(self):
        with self.assertRaisesRegex(ValueError, '目标不可达'):
            planner.plan_j5_xyz('left', (5.0, 5.0, 5.0))

    def test_invalid_target_is_rejected_before_search(self):
        collision = planner.StaticCollisionModel()
        with patch.object(planner.app, 'solve_layered_j5_pose_user',
                          return_value=(self.goal.tolist(), None)), \
             patch.object(planner.StaticCollisionModel, 'pose',
                          side_effect=lambda q, side: planner.CollisionResult(
                              not np.allclose(q, self.goal), '测试目标碰撞', -1.0)), \
             patch.object(planner.RRTConnect, 'solve') as search:
            with self.assertRaisesRegex(ValueError, '目标位置不满足约束'):
                self.plan()
        search.assert_not_called()
        self.assertTrue(collision.pose(self.start, 'left').ok)

    def test_rrt_connect_avoids_controlled_wall_and_shortcut_stays_safe(self):
        collision = WallCollision()
        start = np.asarray([0.0, 0.05, -0.5, 0.0, 0.0, 0.0])
        goal = start.copy()
        start[0], goal[0] = -0.7, 0.7
        path, search = planner.RRTConnect(
            collision, 'left', seed=11, step_rad=0.10, max_iterations=3000).solve(start, goal)
        self.assertFalse(search['direct'])
        np.testing.assert_allclose(path[0], start)
        np.testing.assert_allclose(path[-1], goal)
        optimized = planner.shortcut(path, collision, 'left', np.random.default_rng(12))
        for a, b in zip(optimized, optimized[1:]):
            self.assertTrue(collision.segment(a, b, 'left').ok)

    def test_direct_path_short_circuits_rrt(self):
        collision = WallCollision()
        start = np.asarray([0.0, 0.5, -0.5, 0.0, 0.0, 0.0])
        goal = start.copy()
        start[0], goal[0] = -0.7, -0.6
        path, search = planner.RRTConnect(collision, 'left').solve(start, goal)
        self.assertTrue(search['direct'])
        self.assertEqual(search['iterations'], 0)
        self.assertEqual(len(path), 2)

    def test_known_start_poses_pass_without_adjacent_link_false_positive(self):
        model = planner.StaticCollisionModel()
        for side, q in (('left', planner.app.Q_START_LEFT),
                        ('left', planner.app.Q_LEFT_POS3),
                        ('right', planner.app.Q_START_RIGHT)):
            with self.subTest(side=side):
                result = model.pose(q, side)
                self.assertTrue(result.ok, result.reason)

    def test_real_zero_pose_does_not_false_positive_coarse_wrist_or_gripper(self):
        q = np.radians([0.0, 3.21, -3.27, -0.17, -0.46, 0.0])
        result = planner.StaticCollisionModel().pose(q, 'left')
        self.assertTrue(result.ok, result.reason)

    def test_non_adjacent_self_collision_is_rejected(self):
        q = [1.0175343269877204, 2.952529544457239, -0.06601927332495272,
             1.4179876192732268, 1.0050105182151787, 0.7602688044475294]
        with patch.object(planner.StaticCollisionModel, '_plane_margin', return_value=100.0), \
             patch.object(planner.StaticCollisionModel, '_gripper_capsule',
                          return_value=(np.asarray([0.0, 0.0, 100.0]),
                                        np.asarray([0.0, 0.0, 113.58]))), \
             patch.object(planner.geometry, 'pose_margin', return_value=(100.0, 0.0, '', '')):
            result = planner.StaticCollisionModel().pose(q, 'left')
        self.assertFalse(result.ok)
        self.assertIn('单臂自碰撞', result.reason)
        self.assertLess(result.margin_cm, 0.0)

    def test_gripper_is_forward_axial_capsule_not_large_flange_sphere(self):
        model = planner.StaticCollisionModel(gripper_radius_cm=1.5, gripper_length_cm=10.0)
        a, b = model._gripper_capsule(self.start, 'left')
        self.assertAlmostEqual(float(np.linalg.norm(b-a)), 10.0)
        links = planner.geometry.links_cm(self.start, 'left')
        wrist = links[-1]
        direction = b-a
        wrist_direction = np.asarray(wrist[2])-np.asarray(wrist[1])
        cosine = float(np.dot(direction, wrist_direction) /
                       (np.linalg.norm(direction)*np.linalg.norm(wrist_direction)))
        self.assertAlmostEqual(cosine, 1.0)

    def test_resampled_and_toppra_output_rechecks_are_enforced(self):
        with patch.object(planner, '_parameterize',
                          return_value=(np.asarray([0.0, 0.02]),
                                        np.asarray([self.start, self.goal]), {})):
            self.assertEqual(self.plan()['duration_s'], 0.02)
        with patch.object(planner, '_parameterize',
                          return_value=(np.asarray([0.0, 0.02]),
                                        np.asarray([self.start, np.full(6, np.nan)]), {})):
            with self.assertRaisesRegex(RuntimeError, 'TOPP-RA 输出碰撞复核失败'):
                self.plan()


if __name__ == '__main__':
    unittest.main()

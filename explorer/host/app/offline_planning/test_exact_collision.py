# -*- coding: utf-8 -*-
import unittest
import numpy as np

import vla_motion_planner as planner
from exact_collision import ExactMeshCollisionModel


class ExactMeshCollisionTests(unittest.TestCase):
    def test_known_start_pose_uses_all_self_and_dual_pairs(self):
        model = ExactMeshCollisionModel({'right': planner.app.Q_START_RIGHT})
        result = model.pose(planner.app.Q_START_LEFT, 'left')
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(model.pose_checks, 1)
        # 包围盒粗筛后 11 对机械臂精查；整车 9 次，雷达不重复检查。
        self.assertEqual(model.distance_checks, 20)
        self.assertEqual(model.broadphase_skips, 97)
        self.assertGreater(result.margin_cm, 1.0)

    def test_shoulder_lidar_collision_is_rejected(self):
        model = ExactMeshCollisionModel({'right': planner.app.Q_START_RIGHT})
        q = list(planner.app.Q_START_LEFT)
        q[1] = np.radians(60.0)
        result = model.pose(q, 'left')
        self.assertFalse(result.ok)
        self.assertIn('雷达', result.reason)
        self.assertIn('link2', result.reason)

    def test_right_arm_uses_single_31cm_base_offset(self):
        model = ExactMeshCollisionModel({'left': planner.app.Q_START_LEFT})
        result = model.pose(planner.app.Q_START_RIGHT, 'right')
        self.assertTrue(result.ok, result.reason)
        self.assertGreater(result.margin_cm, 1.0)

    def test_opening_and_mesh_margin_are_validated(self):
        with self.assertRaises(ValueError):
            ExactMeshCollisionModel(opening_m=0.036)
        with self.assertRaises(ValueError):
            ExactMeshCollisionModel(mesh_margin_cm=-0.1)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'collision_mode'):
            planner.plan_j5_xyz('left', (0, 0, 0.3), collision_mode='unknown')


if __name__ == '__main__':
    unittest.main()

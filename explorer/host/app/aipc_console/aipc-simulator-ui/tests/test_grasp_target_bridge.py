import time
import unittest
from unittest.mock import patch

import grasp_target_bridge as bridge


class GraspTargetTests(unittest.TestCase):
    def test_body_point_becomes_arm_j5_pregrasp(self):
        payload = {'point_b_m': [-0.17, 0.78, 0.10],
                   'timestamp': time.time(), 'label': 'cup'}
        with patch.object(bridge, '_live_target', return_value=payload):
            result = bridge.run({'side': 'left'})
        self.assertAlmostEqual(result['xyz'][0], -0.02745)
        self.assertAlmostEqual(result['xyz'][1], 0.34375)
        self.assertAlmostEqual(result['xyz'][2], 0.095)
        self.assertTrue(result['read_only'])
        self.assertFalse(result['execution_enabled'])

    def test_stale_target_is_rejected(self):
        payload = {'point_b_m': [0, 0.7, 0.1], 'timestamp': time.time()-10}
        with patch.object(bridge, '_live_target', return_value=payload):
            with self.assertRaisesRegex(ValueError, '过期'):
                bridge.run({'side': 'left'})

    def test_color_point_uses_candidate_transform(self):
        payload = {'point_color_m': [0, 0, 0.8], 'timestamp': time.time()}
        with patch.object(bridge, '_live_target', return_value=payload):
            result = bridge.run({'side': 'right'})
        self.assertEqual(result['source_frame'], 'color_optical')
        self.assertEqual(len(result['xyz']), 3)


if __name__ == '__main__':
    unittest.main()

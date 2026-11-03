import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from one_euro import OneEuroFilter, OneEuroFilter3


class OneEuroFilterTests(unittest.TestCase):
    def test_constant_input_remains_constant(self):
        filt = OneEuroFilter(0.2)
        outputs = [filt(0.2, i * 0.05) for i in range(100)]
        self.assertAlmostEqual(outputs[-1], 0.2, places=12)

    def test_static_noise_is_attenuated(self):
        filt = OneEuroFilter(0.0)
        raw = [0.001 if i % 2 else -0.001 for i in range(200)]
        outputs = [filt(value, i * 0.05) for i, value in enumerate(raw)]
        raw_tail = max(raw[-40:]) - min(raw[-40:])
        filtered_tail = max(outputs[-40:]) - min(outputs[-40:])
        self.assertLess(filtered_tail, raw_tail * 0.25)

    def test_fast_motion_raises_cutoff(self):
        filt = OneEuroFilter(0.0, min_cutoff=1.2, beta=8.0)
        filt(0.0, 0.0)
        filt(0.0, 0.05)
        quiet_cutoff = filt.last_cutoff
        filt(0.05, 0.10)
        self.assertGreater(filt.last_cutoff, quiet_cutoff)

    def test_duplicate_and_stale_timestamps_are_finite(self):
        filt = OneEuroFilter(0.0)
        filt(0.0, 1.0)
        for timestamp in (1.0, 0.5, 100.0):
            self.assertTrue(math.isfinite(filt(0.001, timestamp)))

    def test_three_channels_are_independent(self):
        filt = OneEuroFilter3((0.0, 0.0, 0.0))
        result = filt((0.01, 0.0, -0.01), 0.0)
        self.assertGreater(result[0], 0.0)
        self.assertEqual(result[1], 0.0)
        self.assertLess(result[2], 0.0)

    def test_invalid_parameters_and_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            OneEuroFilter(min_cutoff=0.0)
        filt = OneEuroFilter()
        with self.assertRaises(ValueError):
            filt(float('nan'), 0.0)
        with self.assertRaises(ValueError):
            filt(0.0, float('inf'))


if __name__ == '__main__':
    unittest.main()

import os
import sys
import types
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

fake_numba = types.ModuleType("numba")


def _fake_njit(*args, **kwargs):
    def _decorator(func):
        return func
    return _decorator


fake_numba.njit = _fake_njit
sys.modules.setdefault("numba", fake_numba)

from zigzag.core import peak_valley_pivots, peak_valley_pivots_dynamic


class TestZigzagDynamicLight(unittest.TestCase):
    def test_dynamic_matches_constant_when_threshold_is_constant(self):
        prices = np.array([100.0, 110.0, 104.0, 115.0, 108.0, 120.0, 112.0], dtype=float)
        up = np.full(len(prices), 0.05, dtype=float)
        down = -up

        fixed = peak_valley_pivots(prices, 0.05, -0.05)
        dynamic = peak_valley_pivots_dynamic(prices, up, down)

        np.testing.assert_array_equal(fixed, dynamic)

    def test_dynamic_higher_early_threshold_reduces_small_early_swings(self):
        prices = np.array([100.0, 106.0, 102.0, 108.0, 104.0, 120.0, 111.0], dtype=float)
        fixed = peak_valley_pivots(prices, 0.03, -0.03)

        up = np.array([0.08, 0.08, 0.08, 0.08, 0.03, 0.03, 0.03], dtype=float)
        down = -up
        dynamic = peak_valley_pivots_dynamic(prices, up, down)

        self.assertLessEqual(int(np.count_nonzero(dynamic)), int(np.count_nonzero(fixed)))


if __name__ == "__main__":
    unittest.main()

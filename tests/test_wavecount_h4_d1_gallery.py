import unittest

from backtests.wavecount.wavecount_context import HTF_MAP
from backtests.wavecount.wavecount_h4_d1_gallery import H4_D1_VISUAL_REVIEW_SPECS


class TestWaveCountH4D1Gallery(unittest.TestCase):
    def test_h4_specs_use_d1_as_htf_context(self):
        self.assertEqual(HTF_MAP["H4"], "D1")
        self.assertTrue(H4_D1_VISUAL_REVIEW_SPECS)
        self.assertTrue(all(spec.timeframe == "H4" for spec in H4_D1_VISUAL_REVIEW_SPECS))

    def test_h4_specs_cover_core_groups(self):
        groups = {spec.group for spec in H4_D1_VISUAL_REVIEW_SPECS}
        self.assertEqual(groups, {"Forex Majors", "Metals", "Index"})


if __name__ == "__main__":
    unittest.main()

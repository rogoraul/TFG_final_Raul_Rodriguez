import unittest

import pandas as pd

from backtests.wavecount import StructuralPivotConfig, build_structural_pivots


def _raw_pivots(items):
    rows = []
    for idx, item in enumerate(items, start=1):
        pivot_type, price, extreme_hour, detected_hour, atr = item
        rows.append(
            {
                "example_id": "synthetic",
                "group": "Test",
                "symbol": "TEST",
                "timeframe": "H1",
                "example_type": "unit",
                "timestamp": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=detected_hour),
                "pivot_state": f"confirmed_{pivot_type}",
                "pivot_type": pivot_type,
                "pivot_extreme_time": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=extreme_hour),
                "pivot_detected_at": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=detected_hour),
                "pivot_extreme_price": price,
                "confirmation_lag_bars": 2,
                "visibility_score": 4.0,
                "atr": atr,
                "lookahead_safe": True,
                "is_candidate": False,
                "is_confirmed": True,
                "is_ambiguous": False,
                "reason": f"synthetic {idx}",
            }
        )
    return pd.DataFrame(rows)


class TestWaveCountStructure(unittest.TestCase):
    def test_builds_alternating_structural_chain_when_moves_are_large(self):
        raw = _raw_pivots(
            [
                ("low", 100.0, 0, 2, 1.0),
                ("high", 110.0, 6, 8, 1.0),
                ("low", 103.0, 12, 14, 1.0),
                ("high", 116.0, 20, 22, 1.0),
            ]
        )
        config = StructuralPivotConfig(
            min_leg_atr_multiplier=2.0,
            min_leg_relative_move_pct=0.01,
            min_leg_bars=2,
        )

        result = build_structural_pivots(raw, config=config)
        structural = result["structural_pivots"]

        self.assertEqual(list(structural["pivot_type"]), ["low", "high", "low", "high"])
        self.assertTrue((structural["structure_state"] == "structural_pivot").all())

    def test_compresses_consecutive_highs_to_the_most_extreme_high(self):
        raw = _raw_pivots(
            [
                ("high", 110.0, 0, 2, 1.0),
                ("high", 112.0, 3, 5, 1.0),
                ("low", 100.0, 9, 11, 1.0),
            ]
        )
        config = StructuralPivotConfig(
            min_leg_atr_multiplier=2.0,
            min_leg_relative_move_pct=0.01,
            min_leg_bars=2,
        )

        result = build_structural_pivots(raw, config=config)
        structural = result["structural_pivots"]
        discarded = result["discarded_minor_pivots"]

        self.assertEqual(float(structural.iloc[0]["pivot_extreme_price"]), 112.0)
        self.assertEqual(list(structural["pivot_type"]), ["high", "low"])
        self.assertIn("superseded", discarded.iloc[0]["reason"])

    def test_discards_minor_opposite_pivot_below_structural_threshold(self):
        raw = _raw_pivots(
            [
                ("low", 100.0, 0, 2, 1.0),
                ("high", 101.0, 6, 8, 1.0),
                ("high", 106.0, 10, 12, 1.0),
            ]
        )
        config = StructuralPivotConfig(
            min_leg_atr_multiplier=3.0,
            min_leg_relative_move_pct=0.05,
            min_leg_bars=2,
        )

        result = build_structural_pivots(raw, config=config)
        structural = result["structural_pivots"]
        discarded = result["discarded_minor_pivots"]

        self.assertEqual(len(structural), 2)
        self.assertEqual(float(structural.iloc[-1]["pivot_extreme_price"]), 106.0)
        self.assertIn("ambiguous_structure", set(discarded["structure_state"]))

    def test_structural_detected_at_is_never_before_raw_pivot_detected_at(self):
        raw = _raw_pivots(
            [
                ("low", 100.0, 0, 2, 1.0),
                ("high", 110.0, 6, 8, 1.0),
                ("low", 103.0, 12, 14, 1.0),
            ]
        )

        result = build_structural_pivots(raw)
        structural = result["structural_pivots"]

        self.assertTrue((structural["structural_detected_at"] >= structural["pivot_detected_at"]).all())


if __name__ == "__main__":
    unittest.main()

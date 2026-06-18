import unittest

from backtests.common.riskguard import (
    CandidateSetup,
    OpenPosition,
    RiskGuard,
    RiskGuardConfig,
    build_risk_snapshot,
    candidate_from_order_intent,
    currency_contributions,
    infer_symbol_currencies,
    parse_direction,
)


class TestRiskGuard(unittest.TestCase):
    def setUp(self):
        self.config = RiskGuardConfig(
            initial_capital=10000.0,
            max_total_open_risk_pct=5.0,
            max_symbol_open_risk_pct=1.0,
            max_currency_gross_risk_pct=3.0,
            max_currency_net_risk_pct=3.0,
        )
        self.guard = RiskGuard(self.config)

    def test_infers_forex_currencies_from_symbol_suffix(self):
        self.assertEqual(infer_symbol_currencies("EURUSD.r"), ("EUR", "USD"))
        self.assertEqual(infer_symbol_currencies("USDCAD"), ("USD", "CAD"))

    def test_parse_direction_accepts_order_intent_sides(self):
        self.assertEqual(parse_direction(side="BUY"), 1)
        self.assertEqual(parse_direction(side="SELL"), -1)
        self.assertEqual(parse_direction(direction=-1), -1)

    def test_currency_contributions_follow_base_quote_direction(self):
        long_eurusd = CandidateSetup("EURUSD.r", 1, 100.0)
        short_gbpusd = CandidateSetup("GBPUSD.r", -1, 100.0)

        self.assertEqual(currency_contributions(long_eurusd), [("EUR", "long", 100.0), ("USD", "short", 100.0)])
        self.assertEqual(currency_contributions(short_gbpusd), [("GBP", "short", 100.0), ("USD", "long", 100.0)])

    def test_accepts_candidate_inside_all_caps(self):
        candidate = CandidateSetup("EURUSD.r", 1, 100.0, strategy="enbolsa:fib_limit", setup_id="s1")

        decision = self.guard.evaluate(candidate, [])

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.reason, "accepted")
        self.assertIn("ACEPTADO", decision.to_message())
        self.assertEqual(decision.to_dict()["strategy"], "enbolsa:fib_limit")

    def test_rejects_total_open_risk_cap(self):
        positions = [
            OpenPosition("EURUSD.r", 1, 100.0),
            OpenPosition("GBPUSD.r", 1, 100.0),
            OpenPosition("AUDJPY.r", 1, 100.0),
            OpenPosition("NZDCAD.r", 1, 100.0),
            OpenPosition("CADCHF.r", 1, 100.0),
        ]
        candidate = CandidateSetup("USDCHF.r", 1, 100.0)

        decision = self.guard.evaluate(candidate, positions)

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "total_open_risk_cap")

    def test_rejects_symbol_cap(self):
        positions = [OpenPosition("EURUSD.r", 1, 50.0)]
        candidate = CandidateSetup("EURUSD.r", -1, 60.0)

        decision = self.guard.evaluate(candidate, positions)

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "symbol_open_risk_cap")
        self.assertIn("EURUSD.r", decision.detail)

    def test_rejects_currency_gross_cap(self):
        config = RiskGuardConfig(
            initial_capital=10000.0,
            max_total_open_risk_pct=10.0,
            max_symbol_open_risk_pct=5.0,
            max_currency_gross_risk_pct=2.0,
            max_currency_net_risk_pct=10.0,
        )
        guard = RiskGuard(config)
        positions = [
            OpenPosition("EURUSD.r", 1, 100.0),
            OpenPosition("USDJPY.r", 1, 100.0),
        ]
        candidate = CandidateSetup("GBPUSD.r", 1, 50.0)

        decision = guard.evaluate(candidate, positions)

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "currency_gross_cap")
        self.assertIn("USD", decision.detail)

    def test_rejects_currency_net_cap(self):
        config = RiskGuardConfig(
            initial_capital=10000.0,
            max_total_open_risk_pct=10.0,
            max_symbol_open_risk_pct=5.0,
            max_currency_gross_risk_pct=10.0,
            max_currency_net_risk_pct=2.0,
        )
        guard = RiskGuard(config)
        positions = [
            OpenPosition("EURUSD.r", 1, 100.0),
            OpenPosition("GBPUSD.r", 1, 100.0),
        ]
        candidate = CandidateSetup("AUDUSD.r", 1, 50.0)

        decision = guard.evaluate(candidate, positions)

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "currency_net_cap")
        self.assertIn("USD", decision.detail)

    def test_evaluate_sequence_is_first_come_first_served(self):
        config = RiskGuardConfig(
            initial_capital=10000.0,
            max_total_open_risk_pct=2.0,
            max_symbol_open_risk_pct=2.0,
            max_currency_gross_risk_pct=10.0,
            max_currency_net_risk_pct=10.0,
        )
        guard = RiskGuard(config)
        candidates = [
            CandidateSetup("EURUSD.r", 1, 100.0, setup_id="first"),
            CandidateSetup("GBPUSD.r", 1, 100.0, setup_id="second"),
            CandidateSetup("AUDUSD.r", 1, 100.0, setup_id="third"),
        ]

        decisions, open_positions = guard.evaluate_sequence(candidates)

        self.assertEqual([item.accepted for item in decisions], [True, True, False])
        self.assertEqual([position.setup_id for position in open_positions], ["first", "second"])
        self.assertEqual(decisions[-1].reason, "total_open_risk_cap")

    def test_candidate_from_order_intent_uses_risk_pct_and_side(self):
        row = {
            "symbol": "EURUSD.r",
            "side": "BUY",
            "risk_pct": 1.0,
            "entry": 1.1,
            "sl": 1.09,
            "tp": 1.12,
            "strategy": "menendez:faithful_operable",
            "setup_id": "intent-1",
        }

        candidate = candidate_from_order_intent(row, initial_capital=10000.0)

        self.assertEqual(candidate.direction, 1)
        self.assertEqual(candidate.risk_amount, 100.0)
        self.assertEqual(candidate.strategy, "menendez:faithful_operable")
        self.assertEqual(candidate.base_currency, "EUR")
        self.assertEqual(candidate.quote_currency, "USD")

    def test_snapshot_exposes_dashboard_ready_percentages(self):
        positions = [
            OpenPosition("EURUSD.r", 1, 100.0),
            OpenPosition("GBPUSD.r", -1, 50.0),
        ]

        snapshot = build_risk_snapshot(positions, self.config).to_dict()

        self.assertEqual(snapshot["total_open_risk_pct"], 1.5)
        self.assertEqual(snapshot["symbol_open_risk_pct"]["EURUSD.r"], 1.0)
        self.assertIn("USD", snapshot["currency_exposure"])


if __name__ == "__main__":
    unittest.main()

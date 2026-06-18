"""Shared backtesting utilities and configuration."""

from backtests.common.riskguard import (
    CandidateSetup,
    CurrencyExposure,
    OpenPosition,
    PortfolioRiskSnapshot,
    RiskGuard,
    RiskGuardConfig,
    RiskGuardDecision,
    build_risk_snapshot,
    candidate_from_order_intent,
    currency_contributions,
    infer_symbol_currencies,
    parse_direction,
)

__all__ = [
    "CandidateSetup",
    "CurrencyExposure",
    "OpenPosition",
    "PortfolioRiskSnapshot",
    "RiskGuard",
    "RiskGuardConfig",
    "RiskGuardDecision",
    "build_risk_snapshot",
    "candidate_from_order_intent",
    "currency_contributions",
    "infer_symbol_currencies",
    "parse_direction",
]

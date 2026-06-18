"""Shared portfolio exposure guard used by backtests and demo-risk audits."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any, Mapping, Sequence


FOREX_CODES = ("AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NZD", "USD")
BUY_ALIASES = {"buy", "long", "largo", "compra", "comprar", "1", "+1"}
SELL_ALIASES = {"sell", "short", "corto", "venta", "vender", "-1"}


def _clean_symbol(symbol: object) -> str:
    return str(symbol or "").split(".", 1)[0].upper().strip()


def _clean_currency(value: object) -> str:
    text = str(value or "").upper().strip()
    return text if text and text != "NAN" else ""


def infer_symbol_currencies(symbol: object, base_currency: object = "", quote_currency: object = "") -> tuple[str, str]:
    """Infer base/quote currencies from explicit metadata or the symbol name."""
    base = _clean_currency(base_currency)
    quote = _clean_currency(quote_currency)
    if base and quote:
        return base, quote

    clean = _clean_symbol(symbol)
    if len(clean) >= 6:
        left = clean[:3]
        right = clean[3:6]
        if left in FOREX_CODES and right in FOREX_CODES:
            return left, right
        if right in FOREX_CODES:
            return clean[:-3] or left, right
    return base or clean or "UNKNOWN", quote or "UNKNOWN"


def parse_direction(direction: object = None, side: object = None) -> int:
    """Normalize long/buy and short/sell aliases to +1/-1."""
    value = direction if direction is not None and str(direction) != "" else side
    if isinstance(value, (int, float)) and isfinite(float(value)):
        numeric = int(float(value))
        if numeric > 0:
            return 1
        if numeric < 0:
            return -1

    text = str(value or "").strip().lower()
    if text in BUY_ALIASES:
        return 1
    if text in SELL_ALIASES:
        return -1
    raise ValueError(f"Direccion no reconocida: {value!r}")


def _first_present(mapping: Mapping[str, Any], names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        if name in mapping and mapping[name] not in (None, ""):
            return mapping[name]
    return default


def _float_or_none(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _pct(value: float, initial_capital: float) -> float:
    return (float(value) / float(initial_capital)) * 100.0 if initial_capital > 0 else 0.0


@dataclass(frozen=True)
class RiskGuardConfig:
    """Exposure limits expressed as percentages of initial capital."""
    initial_capital: float = 10000.0
    max_total_open_risk_pct: float | None = 5.0
    max_symbol_open_risk_pct: float | None = 1.0
    max_currency_gross_risk_pct: float | None = 3.0
    max_currency_net_risk_pct: float | None = 3.0
    epsilon: float = 1e-9


@dataclass(frozen=True)
class CandidateSetup:
    """Candidate setup evaluated before it becomes an open-risk position."""
    symbol: str
    direction: int
    risk_amount: float
    strategy: str = ""
    setup_id: str = ""
    timestamp: object = None
    entry: float | None = None
    stop: float | None = None
    take_profit: float | None = None
    base_currency: str = ""
    quote_currency: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        direction = parse_direction(self.direction)
        risk_amount = float(self.risk_amount)
        if not isfinite(risk_amount):
            risk_amount = 0.0
        base, quote = infer_symbol_currencies(self.symbol, self.base_currency, self.quote_currency)
        object.__setattr__(self, "symbol", str(self.symbol))
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "risk_amount", risk_amount)
        object.__setattr__(self, "base_currency", base)
        object.__setattr__(self, "quote_currency", quote)

    @property
    def side(self) -> str:
        return "BUY" if self.direction == 1 else "SELL"

    def as_open_position(self) -> "OpenPosition":
        return OpenPosition(
            symbol=self.symbol,
            direction=self.direction,
            risk_amount=self.risk_amount,
            strategy=self.strategy,
            setup_id=self.setup_id,
            opened_at=self.timestamp,
            base_currency=self.base_currency,
            quote_currency=self.quote_currency,
            source=self.source,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any], initial_capital: float = 10000.0) -> "CandidateSetup":
        risk_amount = _float_or_none(_first_present(row, ("risk_amount", "setup_risk", "risk_amount_total")))
        if risk_amount is None:
            risk_pct = _float_or_none(_first_present(row, ("risk_pct", "setup_risk_pct", "risk_pct_real")))
            if risk_pct is None:
                raise ValueError("CandidateSetup requiere risk_amount o risk_pct.")
            risk_amount = float(initial_capital) * risk_pct / 100.0

        direction = parse_direction(
            _first_present(row, ("direction", "dir"), None),
            _first_present(row, ("side", "direction_label"), None),
        )
        base, quote = infer_symbol_currencies(
            _first_present(row, ("symbol", "Symbol")),
            _first_present(row, ("base_currency", "SYMBOL_CURRENCY_BASE"), ""),
            _first_present(row, ("quote_currency", "SYMBOL_CURRENCY_PROFIT"), ""),
        )
        return cls(
            symbol=str(_first_present(row, ("symbol", "Symbol"), "")),
            direction=direction,
            risk_amount=risk_amount,
            strategy=str(_first_present(row, ("strategy", "source_strategy"), "")),
            setup_id=str(_first_present(row, ("setup_id", "order_id", "intent_id"), "")),
            timestamp=_first_present(row, ("timestamp", "entry_time", "created_at"), None),
            entry=_float_or_none(_first_present(row, ("entry", "entry_price"), None)),
            stop=_float_or_none(_first_present(row, ("sl", "stop", "stop_price"), None)),
            take_profit=_float_or_none(_first_present(row, ("tp", "take_profit", "target_price"), None)),
            base_currency=base,
            quote_currency=quote,
            source=str(_first_present(row, ("source", "source_run_id"), "")),
            metadata={k: v for k, v in row.items() if k not in {
                "symbol", "Symbol", "direction", "dir", "side", "direction_label",
                "risk_amount", "setup_risk", "risk_amount_total", "risk_pct", "setup_risk_pct",
                "risk_pct_real", "entry", "entry_price", "sl", "stop", "stop_price", "tp",
                "take_profit", "target_price", "strategy", "source_strategy", "setup_id",
                "order_id", "intent_id", "timestamp", "entry_time", "created_at",
                "base_currency", "quote_currency", "SYMBOL_CURRENCY_BASE",
                "SYMBOL_CURRENCY_PROFIT", "source", "source_run_id",
            }},
        )


@dataclass(frozen=True)
class OpenPosition:
    """Existing open-risk position used to compute current exposure."""
    symbol: str
    direction: int
    risk_amount: float
    strategy: str = ""
    setup_id: str = ""
    opened_at: object = None
    base_currency: str = ""
    quote_currency: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        direction = parse_direction(self.direction)
        risk_amount = float(self.risk_amount)
        if not isfinite(risk_amount):
            risk_amount = 0.0
        base, quote = infer_symbol_currencies(self.symbol, self.base_currency, self.quote_currency)
        object.__setattr__(self, "symbol", str(self.symbol))
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "risk_amount", risk_amount)
        object.__setattr__(self, "base_currency", base)
        object.__setattr__(self, "quote_currency", quote)

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any], initial_capital: float = 10000.0) -> "OpenPosition":
        candidate = CandidateSetup.from_mapping(row, initial_capital=initial_capital)
        return candidate.as_open_position()


@dataclass(frozen=True)
class CurrencyExposure:
    """Long/short risk contribution aggregated by currency."""
    currency: str
    long_risk: float = 0.0
    short_risk: float = 0.0
    initial_capital: float = 10000.0

    @property
    def gross_risk(self) -> float:
        return self.long_risk + self.short_risk

    @property
    def net_risk(self) -> float:
        return self.long_risk - self.short_risk

    def to_dict(self) -> dict[str, float | str]:
        return {
            "currency": self.currency,
            "long_risk": round(float(self.long_risk), 6),
            "short_risk": round(float(self.short_risk), 6),
            "gross_risk": round(float(self.gross_risk), 6),
            "net_risk": round(float(self.net_risk), 6),
            "long_risk_pct": round(_pct(self.long_risk, self.initial_capital), 6),
            "short_risk_pct": round(_pct(self.short_risk, self.initial_capital), 6),
            "gross_risk_pct": round(_pct(self.gross_risk, self.initial_capital), 6),
            "abs_net_risk_pct": round(_pct(abs(self.net_risk), self.initial_capital), 6),
        }


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    """Portfolio exposure state before or after adding a candidate."""
    total_open_risk: float
    symbol_open_risk: dict[str, float]
    currency_exposure: dict[str, CurrencyExposure]
    initial_capital: float

    @property
    def total_open_risk_pct(self) -> float:
        return _pct(self.total_open_risk, self.initial_capital)

    def symbol_open_risk_pct(self, symbol: str) -> float:
        return _pct(self.symbol_open_risk.get(symbol, 0.0), self.initial_capital)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_open_risk": round(float(self.total_open_risk), 6),
            "total_open_risk_pct": round(float(self.total_open_risk_pct), 6),
            "symbol_open_risk": {k: round(float(v), 6) for k, v in sorted(self.symbol_open_risk.items())},
            "symbol_open_risk_pct": {
                k: round(_pct(v, self.initial_capital), 6)
                for k, v in sorted(self.symbol_open_risk.items())
            },
            "currency_exposure": {
                currency: exposure.to_dict()
                for currency, exposure in sorted(self.currency_exposure.items())
            },
        }


@dataclass(frozen=True)
class RiskGuardDecision:
    """Decision produced by RiskGuard for one candidate setup."""
    accepted: bool
    reason: str
    detail: str
    candidate: CandidateSetup
    current: PortfolioRiskSnapshot
    projected: PortfolioRiskSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "detail": self.detail,
            "strategy": self.candidate.strategy,
            "symbol": self.candidate.symbol,
            "side": self.candidate.side,
            "setup_id": self.candidate.setup_id,
            "timestamp": str(self.candidate.timestamp),
            "risk_amount": round(float(self.candidate.risk_amount), 6),
            "risk_pct": round(_pct(self.candidate.risk_amount, self.current.initial_capital), 6),
            "current": self.current.to_dict(),
            "projected": self.projected.to_dict(),
        }

    def to_message(self) -> str:
        status = "ACEPTADO" if self.accepted else "RECHAZADO"
        reason = self.reason or "accepted"
        return (
            f"{status} {self.candidate.symbol} {self.candidate.side} "
            f"risk={_pct(self.candidate.risk_amount, self.current.initial_capital):.2f}% "
            f"reason={reason}: {self.detail}"
        ).strip()


def currency_contributions(position: CandidateSetup | OpenPosition) -> list[tuple[str, str, float]]:
    """Return currency-side risk contributions for one position."""
    amount = float(position.risk_amount)
    if int(position.direction) == 1:
        return [
            (position.base_currency or "UNKNOWN", "long", amount),
            (position.quote_currency or "UNKNOWN", "short", amount),
        ]
    return [
        (position.base_currency or "UNKNOWN", "short", amount),
        (position.quote_currency or "UNKNOWN", "long", amount),
    ]


def build_risk_snapshot(
    positions: Sequence[OpenPosition | CandidateSetup],
    config: RiskGuardConfig,
) -> PortfolioRiskSnapshot:
    """Aggregate symbol, currency and total open risk for a position set."""
    symbol_open_risk: dict[str, float] = {}
    raw_currency: dict[str, dict[str, float]] = {}
    total = 0.0

    for position in positions:
        risk = max(0.0, float(position.risk_amount))
        total += risk
        symbol_open_risk[position.symbol] = symbol_open_risk.get(position.symbol, 0.0) + risk
        for currency, side, amount in currency_contributions(position):
            raw_currency.setdefault(currency, {"long": 0.0, "short": 0.0})
            raw_currency[currency][side] += max(0.0, float(amount))

    currency_exposure = {
        currency: CurrencyExposure(
            currency=currency,
            long_risk=values.get("long", 0.0),
            short_risk=values.get("short", 0.0),
            initial_capital=config.initial_capital,
        )
        for currency, values in raw_currency.items()
    }
    return PortfolioRiskSnapshot(
        total_open_risk=total,
        symbol_open_risk=symbol_open_risk,
        currency_exposure=currency_exposure,
        initial_capital=config.initial_capital,
    )


class RiskGuard:
    """Evaluate candidate setups against configured exposure caps."""
    def __init__(self, config: RiskGuardConfig | None = None):
        self.config = config or RiskGuardConfig()

    def evaluate(
        self,
        candidate: CandidateSetup,
        open_positions: Sequence[OpenPosition | CandidateSetup] = (),
    ) -> RiskGuardDecision:
        current_positions = list(open_positions)
        current = build_risk_snapshot(current_positions, self.config)
        projected = build_risk_snapshot(
            [*current_positions, candidate.as_open_position()],
            self.config,
        )

        accepted = True
        reason = "accepted"
        detail = "RiskGuard limits respected."
        risk_pct = _pct(candidate.risk_amount, self.config.initial_capital)

        if candidate.risk_amount <= 0:
            accepted = False
            reason = "invalid_setup_risk"
            detail = f"candidate risk {risk_pct:.2f}% <= 0.00%"
        elif self._breaches(projected.total_open_risk_pct, self.config.max_total_open_risk_pct):
            accepted = False
            reason = "total_open_risk_cap"
            detail = (
                f"total {projected.total_open_risk_pct:.2f}% "
                f"> {float(self.config.max_total_open_risk_pct):.2f}%"
            )
        elif self._breaches(projected.symbol_open_risk_pct(candidate.symbol), self.config.max_symbol_open_risk_pct):
            accepted = False
            reason = "symbol_open_risk_cap"
            detail = (
                f"{candidate.symbol} {projected.symbol_open_risk_pct(candidate.symbol):.2f}% "
                f"> {float(self.config.max_symbol_open_risk_pct):.2f}%"
            )
        else:
            for currency, exposure in sorted(projected.currency_exposure.items()):
                row = exposure.to_dict()
                if self._breaches(float(row["gross_risk_pct"]), self.config.max_currency_gross_risk_pct):
                    accepted = False
                    reason = "currency_gross_cap"
                    detail = (
                        f"{currency} gross {float(row['gross_risk_pct']):.2f}% "
                        f"> {float(self.config.max_currency_gross_risk_pct):.2f}%"
                    )
                    break
                if self._breaches(float(row["abs_net_risk_pct"]), self.config.max_currency_net_risk_pct):
                    accepted = False
                    reason = "currency_net_cap"
                    detail = (
                        f"{currency} net {float(row['abs_net_risk_pct']):.2f}% "
                        f"> {float(self.config.max_currency_net_risk_pct):.2f}%"
                    )
                    break

        return RiskGuardDecision(
            accepted=accepted,
            reason=reason,
            detail=detail,
            candidate=candidate,
            current=current,
            projected=projected,
        )

    def evaluate_sequence(
        self,
        candidates: Sequence[CandidateSetup],
        initial_open_positions: Sequence[OpenPosition | CandidateSetup] = (),
    ) -> tuple[list[RiskGuardDecision], list[OpenPosition]]:
        open_positions = [
            item.as_open_position() if isinstance(item, CandidateSetup) else item
            for item in initial_open_positions
        ]
        decisions: list[RiskGuardDecision] = []
        for candidate in candidates:
            decision = self.evaluate(candidate, open_positions)
            decisions.append(decision)
            if decision.accepted:
                open_positions.append(candidate.as_open_position())
        return decisions, open_positions

    def _breaches(self, value_pct: float, cap_pct: float | None) -> bool:
        if cap_pct is None:
            return False
        return float(value_pct) > float(cap_pct) + float(self.config.epsilon)


def candidate_from_order_intent(row: Mapping[str, Any], initial_capital: float = 10000.0) -> CandidateSetup:
    return CandidateSetup.from_mapping(row, initial_capital=initial_capital)

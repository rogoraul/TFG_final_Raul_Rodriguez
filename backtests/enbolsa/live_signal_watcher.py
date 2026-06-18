from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from backtests.common.backtest_matrix_config import (
    DEFAULT_STRATEGIES,
    get_account_config,
)
from backtests.common.riskguard import (
    CandidateSetup,
    OpenPosition,
    RiskGuard,
    RiskGuardConfig,
    RiskGuardDecision,
)
from backtests.enbolsa.backtest_loader import cargar_portfolios_matriz
from backtests.enbolsa.backtest_pipeline import (
    _macd_breakout_signal_from_arrays,
    _make_position,
    _prepare_symbol_arrays,
    _row_setup_snapshot,
    _strategy_legs,
)


WATCHER_STRATEGY = "enbolsa:macd_breakout"
ENTRY_RULE = "macd_breakout"
DEFAULT_OUTPUT_DIR = Path("artifacts/live-signal-watcher/enbolsa_macd_breakout_v0")
DEFAULT_REGISTRY_FILE = "seen_events.json"
ORDER_INTENT_COLUMNS = [
    "event_key",
    "symbol",
    "timestamp",
    "side",
    "order_type",
    "entry",
    "sl",
    "tp",
    "tp1",
    "tp2",
    "risk_pct",
    "risk_amount",
    "strategy",
    "source",
    "riskguard_accepted",
    "riskguard_reason",
    "riskguard_detail",
    "riskguard_message",
]
RISKGUARD_DECISION_COLUMNS = [
    "accepted",
    "reason",
    "detail",
    "strategy",
    "symbol",
    "side",
    "setup_id",
    "timestamp",
    "risk_amount",
    "risk_pct",
    "current",
    "projected",
]
WATCHLIST_COLUMNS = [
    "strategy",
    "symbol",
    "side",
    "setup_id",
    "timestamp",
    "timeframe_ltf",
    "timeframe_htf",
    "watch_state",
    "missing_confirmation",
    "w2_swing",
    "target_1_0",
    "target_1_618",
    "setup_age",
    "event_key",
]


@dataclass(frozen=True)
class LiveSignalWatcherConfig:
    strategy: str = WATCHER_STRATEGY
    timeframe_ltf: str = "H1"
    timeframe_htf: str = "H4"
    initial_capital: float = 10000.0
    risk_per_trade_pct: float = 1.0
    confirmation_memory_bars: int = 5
    lookback_bars: int = 1


class SeenSignalRegistry:
    def __init__(self, path: str | Path | None = None, initial_keys: Sequence[str] | None = None):
        self.path = Path(path) if path else None
        self.seen: set[str] = set(initial_keys or ())
        if self.path and self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.seen.update(str(item) for item in payload.get("seen_event_keys", []))

    def contains(self, event_key: str) -> bool:
        return str(event_key) in self.seen

    def mark(self, event_key: str) -> None:
        if event_key:
            self.seen.add(str(event_key))

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "seen_event_keys": sorted(self.seen),
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_float(value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if np.isfinite(result) else np.nan


def _safe_timestamp(value: object) -> pd.Timestamp:
    return pd.Timestamp(value)


def _setup_id_for_direction(arrays: Mapping[str, Any], row_pos: int, direction: int) -> int:
    key = "long_setup_id" if direction == 1 else "short_setup_id"
    return int(arrays[key][row_pos])


def _setup_active_for_direction(arrays: Mapping[str, Any], row_pos: int, direction: int) -> bool:
    key = "long_setup_active" if direction == 1 else "short_setup_active"
    return bool(arrays[key][row_pos])


def _is_fresh_macd_signal(
    arrays: Mapping[str, Any],
    row_pos: int,
    direction: int,
    memory_bars: int,
) -> tuple[bool, bool]:
    raw_ready = bool(_macd_breakout_signal_from_arrays(arrays, row_pos, direction, memory_bars))
    if not raw_ready:
        return False, False
    if row_pos <= 0:
        return True, True

    setup_id = _setup_id_for_direction(arrays, row_pos, direction)
    previous_setup_id = _setup_id_for_direction(arrays, row_pos - 1, direction)
    previous_ready = bool(_macd_breakout_signal_from_arrays(arrays, row_pos - 1, direction, memory_bars))
    fresh = not (previous_ready and previous_setup_id == setup_id)
    return raw_ready, fresh


def _event_key(symbol: str, timestamp: object, direction: int, setup_id: object, config: LiveSignalWatcherConfig) -> str:
    ts = pd.Timestamp(timestamp).isoformat()
    side = "BUY" if int(direction) == 1 else "SELL"
    return "|".join([
        str(config.strategy),
        str(symbol),
        f"{config.timeframe_ltf}:{config.timeframe_htf}",
        side,
        str(setup_id),
        ts,
    ])


def _macd_strategy_config(config: LiveSignalWatcherConfig) -> dict[str, Any]:
    strategy_config = dict(DEFAULT_STRATEGIES["macd_breakout"])
    strategy_config["confirmation_memory_bars"] = int(config.confirmation_memory_bars)
    strategy_config["risk_fraction"] = 1.0
    return strategy_config


def _positions_for_signal(
    symbol: str,
    timestamp: object,
    row: pd.Series,
    direction: int,
    config: LiveSignalWatcherConfig,
) -> list[dict[str, Any]]:
    strategy_config = _macd_strategy_config(config)
    legs = [
        leg for leg in _strategy_legs(config.strategy, strategy_config)
        if leg["entry_rule"] == ENTRY_RULE
    ]
    positions = []
    for leg in legs:
        position = _make_position(symbol, timestamp, row, direction, leg)
        if position is not None:
            positions.append(position)
    return positions


def _candidate_from_positions(
    positions: Sequence[Mapping[str, Any]],
    row: pd.Series,
    config: LiveSignalWatcherConfig,
) -> CandidateSetup | None:
    if not positions:
        return None

    first = positions[0]
    risk_fraction = sum(float(position.get("size_fraction", 0.0) or 0.0) for position in positions)
    risk_amount = float(config.initial_capital) * (float(config.risk_per_trade_pct) / 100.0) * risk_fraction
    setup_id = str(first.get("setup_id", ""))
    tp_values = {
        float(position.get("tp_mult", 0.0)): _safe_float(position.get("target_price"))
        for position in positions
    }
    return CandidateSetup(
        symbol=str(first["symbol"]),
        direction=int(first["direction"]),
        risk_amount=risk_amount,
        strategy=config.strategy,
        setup_id=setup_id,
        timestamp=first.get("entry_time"),
        entry=_safe_float(first.get("entry_price")),
        stop=_safe_float(first.get("stop_price")),
        take_profit=tp_values.get(1.0),
        base_currency=row.get("SYMBOL_CURRENCY_BASE", ""),
        quote_currency=row.get("SYMBOL_CURRENCY_PROFIT", ""),
        metadata={
            "timeframe_ltf": config.timeframe_ltf,
            "timeframe_htf": config.timeframe_htf,
            "tp1": tp_values.get(1.0),
            "tp2": tp_values.get(1.618),
            "risk_fraction": risk_fraction,
        },
    )


def _no_signal_reason(snapshot: Mapping[str, Any], raw_ready: bool, fresh: bool) -> str:
    if raw_ready and not fresh:
        return "raw_condition_still_true_but_not_fresh"
    if not snapshot.get("setup_active"):
        return "no_active_setup"
    if snapshot.get("setup_id", 0) == 0:
        return "missing_setup_id"
    if snapshot.get("invalidated"):
        return "setup_invalidated"
    if pd.isna(snapshot.get("w2_swing")):
        return "missing_w2_swing"
    return "waiting_for_trendline_and_macd_confirmation"


def _empty_decision_dict() -> dict[str, Any]:
    return {
        "riskguard_accepted": False,
        "riskguard_reason": "",
        "riskguard_detail": "",
        "riskguard_message": "",
    }


def _decision_columns(decision: RiskGuardDecision | None) -> dict[str, Any]:
    if decision is None:
        return _empty_decision_dict()
    return {
        "riskguard_accepted": bool(decision.accepted),
        "riskguard_reason": decision.reason,
        "riskguard_detail": decision.detail,
        "riskguard_message": decision.to_message(),
    }


def build_watchlist(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot is None or snapshot.empty:
        return pd.DataFrame(columns=WATCHLIST_COLUMNS)

    mask = (
        (snapshot.get("signal_state") == "watching_setup")
        & (snapshot.get("reason") == "waiting_for_trendline_and_macd_confirmation")
        & (snapshot.get("setup_active") == True)
    )
    watchable = snapshot.loc[mask].copy()
    if watchable.empty:
        return pd.DataFrame(columns=WATCHLIST_COLUMNS)

    watchlist = pd.DataFrame({
        "strategy": watchable["strategy"],
        "symbol": watchable["symbol"],
        "side": watchable["side"],
        "setup_id": watchable["setup_id"],
        "timestamp": watchable["timestamp"],
        "timeframe_ltf": watchable["timeframe_ltf"],
        "timeframe_htf": watchable["timeframe_htf"],
        "watch_state": "watching_confirmation",
        "missing_confirmation": "trendline_break_or_macd_cross_within_memory",
        "w2_swing": watchable["w2_swing"],
        "target_1_0": watchable["target_1_0"],
        "target_1_618": watchable["target_1_618"],
        "setup_age": watchable["setup_age"],
        "event_key": watchable.get("event_key", ""),
    })
    return watchlist.reindex(columns=WATCHLIST_COLUMNS).sort_values(["symbol", "side"]).reset_index(drop=True)


def build_macd_breakout_snapshot(
    portfolio: Mapping[str, pd.DataFrame],
    *,
    config: LiveSignalWatcherConfig | None = None,
    registry: SeenSignalRegistry | None = None,
    riskguard: RiskGuard | None = None,
    open_positions: Sequence[OpenPosition | CandidateSetup] = (),
) -> dict[str, pd.DataFrame]:
    config = config or LiveSignalWatcherConfig()
    registry = registry or SeenSignalRegistry()
    account_risk = get_account_config({
        "initial_capital": config.initial_capital,
        "risk_per_trade": config.risk_per_trade_pct / 100.0,
    })
    guard = riskguard or RiskGuard(RiskGuardConfig(
        initial_capital=float(account_risk["initial_capital"]),
        max_total_open_risk_pct=5.0,
        max_symbol_open_risk_pct=1.0,
        max_currency_gross_risk_pct=3.0,
        max_currency_net_risk_pct=3.0,
    ))

    snapshot_rows: list[dict[str, Any]] = []
    candidate_rows: list[tuple[str, CandidateSetup]] = []

    for symbol, frame in sorted((portfolio or {}).items()):
        if frame is None or frame.empty:
            continue
        df = frame.sort_index()
        arrays = _prepare_symbol_arrays(df, config.timeframe_htf)
        start_pos = max(0, len(df) - max(int(config.lookback_bars), 1))

        for row_pos in range(start_pos, len(df)):
            timestamp = _safe_timestamp(df.index[row_pos])
            row = df.iloc[row_pos]
            latest_closed = row_pos == len(df) - 1
            for direction in (1, -1):
                raw_ready, fresh = _is_fresh_macd_signal(
                    arrays,
                    row_pos,
                    direction,
                    int(config.confirmation_memory_bars),
                )
                setup_snapshot = _row_setup_snapshot(row, direction)
                positions = _positions_for_signal(symbol, timestamp, row, direction, config) if raw_ready else []
                candidate = _candidate_from_positions(positions, row, config) if fresh else None
                event_key = (
                    _event_key(symbol, timestamp, direction, setup_snapshot.get("setup_id"), config)
                    if fresh else ""
                )
                already_seen = bool(event_key and registry.contains(event_key))
                entry_ready = bool(candidate is not None and not already_seen)
                state = "entry_ready_new" if entry_ready else "no_signal"
                if candidate is not None and already_seen:
                    state = "ready_already_seen"
                elif raw_ready and not fresh:
                    state = "ready_stale"
                elif setup_snapshot.get("setup_active"):
                    state = "watching_setup"

                base_row = {
                    "strategy": config.strategy,
                    "symbol": symbol,
                    "timeframe_ltf": config.timeframe_ltf,
                    "timeframe_htf": config.timeframe_htf,
                    "timestamp": timestamp,
                    "latest_closed_bar": latest_closed,
                    "direction": direction,
                    "side": "BUY" if direction == 1 else "SELL",
                    "setup_id": setup_snapshot.get("setup_id", 0),
                    "setup_active": bool(setup_snapshot.get("setup_active", False)),
                    "setup_age": setup_snapshot.get("setup_age", 0),
                    "raw_condition_ready": raw_ready,
                    "fresh_signal": fresh,
                    "already_seen": already_seen,
                    "entry_ready": entry_ready,
                    "signal_state": state,
                    "reason": "" if entry_ready else _no_signal_reason(setup_snapshot, raw_ready, fresh),
                    "event_key": event_key,
                    "entry": candidate.entry if candidate else np.nan,
                    "sl": candidate.stop if candidate else np.nan,
                    "tp1": candidate.metadata.get("tp1") if candidate else np.nan,
                    "tp2": candidate.metadata.get("tp2") if candidate else np.nan,
                    "risk_pct": config.risk_per_trade_pct if candidate else np.nan,
                    "risk_amount": candidate.risk_amount if candidate else np.nan,
                    "w2_swing": setup_snapshot.get("w2_swing"),
                    "target_1_0": setup_snapshot.get("target_1_0"),
                    "target_1_618": setup_snapshot.get("target_1_618"),
                }
                snapshot_rows.append(base_row)
                if entry_ready and candidate is not None:
                    candidate_rows.append((event_key, candidate))

    snapshot = pd.DataFrame(snapshot_rows)
    decisions, _ = guard.evaluate_sequence([candidate for _, candidate in candidate_rows], open_positions)
    decision_by_key = {
        event_key: decision
        for (event_key, _), decision in zip(candidate_rows, decisions)
    }

    if not snapshot.empty:
        decision_rows = []
        for _, row in snapshot.iterrows():
            decision_rows.append(_decision_columns(decision_by_key.get(str(row.get("event_key", "")))))
        decision_frame = pd.DataFrame(decision_rows)
        snapshot = pd.concat([snapshot.reset_index(drop=True), decision_frame], axis=1)
    else:
        snapshot = pd.DataFrame(columns=[
            "strategy", "symbol", "timeframe_ltf", "timeframe_htf", "timestamp",
            "direction", "side", "entry_ready", "signal_state", "event_key",
        ])

    intent_rows = []
    decision_rows = []
    for event_key, candidate in candidate_rows:
        decision = decision_by_key[event_key]
        intent_rows.append({
            "event_key": event_key,
            "symbol": candidate.symbol,
            "timestamp": pd.Timestamp(candidate.timestamp),
            "side": candidate.side,
            "order_type": "MARKET",
            "entry": candidate.entry,
            "sl": candidate.stop,
            "tp": candidate.take_profit,
            "tp1": candidate.metadata.get("tp1"),
            "tp2": candidate.metadata.get("tp2"),
            "risk_pct": config.risk_per_trade_pct,
            "risk_amount": candidate.risk_amount,
            "strategy": candidate.strategy,
            "source": "live_signal_watcher_v0",
            **_decision_columns(decision),
        })
        decision_rows.append(decision.to_dict())

    order_intents = pd.DataFrame(intent_rows).reindex(columns=ORDER_INTENT_COLUMNS)
    riskguard_decisions = pd.DataFrame(decision_rows).reindex(columns=RISKGUARD_DECISION_COLUMNS)
    watchlist = build_watchlist(snapshot)
    return {
        "snapshot": snapshot,
        "watchlist": watchlist,
        "order_intents": order_intents,
        "riskguard_decisions": riskguard_decisions,
    }


def mark_emitted_events(registry: SeenSignalRegistry, order_intents: pd.DataFrame) -> None:
    if order_intents is None or order_intents.empty or "event_key" not in order_intents.columns:
        return
    for event_key in order_intents["event_key"].dropna().astype(str):
        registry.mark(event_key)
    registry.save()


def write_snapshot_outputs(result: Mapping[str, pd.DataFrame], output_dir: Path, run_meta: Mapping[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in result.items():
        path = output_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
    (output_dir / "run_meta.json").write_text(
        json.dumps(dict(run_meta), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _build_cli_config(args: argparse.Namespace) -> LiveSignalWatcherConfig:
    return LiveSignalWatcherConfig(
        timeframe_ltf=args.timeframe_ltf,
        timeframe_htf=args.timeframe_htf,
        initial_capital=float(args.initial_capital),
        risk_per_trade_pct=float(args.risk_per_trade_pct),
        confirmation_memory_bars=int(args.confirmation_memory_bars),
        lookback_bars=int(args.lookback_bars),
    )


def run_snapshot_once(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    repo_root = _repo_root()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    registry_path = Path(args.registry_path) if args.registry_path else output_dir / DEFAULT_REGISTRY_FILE
    if not registry_path.is_absolute():
        registry_path = repo_root / registry_path

    config = _build_cli_config(args)
    groups = _parse_csv(args.groups)
    portfolios = cargar_portfolios_matriz(
        groups=groups,
        tf_pairs={config.timeframe_ltf: config.timeframe_htf},
        verbose=bool(args.verbose),
        use_cache=not bool(args.no_cache),
        force_rebuild=bool(args.force_rebuild),
        use_disk_cache=not bool(args.no_disk_cache),
    )
    frames = []
    watchlists = []
    intents = []
    decisions = []
    registry = SeenSignalRegistry(registry_path)
    riskguard = RiskGuard(RiskGuardConfig(
        initial_capital=float(args.initial_capital),
        max_total_open_risk_pct=float(args.max_total_open_risk_pct),
        max_symbol_open_risk_pct=float(args.max_symbol_open_risk_pct),
        max_currency_gross_risk_pct=float(args.max_currency_gross_risk_pct),
        max_currency_net_risk_pct=float(args.max_currency_net_risk_pct),
    ))

    for (group_name, ltf, htf), portfolio in portfolios.items():
        local_config = LiveSignalWatcherConfig(
            strategy=config.strategy,
            timeframe_ltf=ltf,
            timeframe_htf=htf,
            initial_capital=config.initial_capital,
            risk_per_trade_pct=config.risk_per_trade_pct,
            confirmation_memory_bars=config.confirmation_memory_bars,
            lookback_bars=config.lookback_bars,
        )
        result = build_macd_breakout_snapshot(
            portfolio,
            config=local_config,
            registry=registry,
            riskguard=riskguard,
        )
        for frame in result.values():
            if not frame.empty:
                frame.insert(0, "Group", group_name)
        frames.append(result["snapshot"])
        watchlists.append(result["watchlist"])
        intents.append(result["order_intents"])
        decisions.append(result["riskguard_decisions"])

    result = {
        "snapshot": pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(),
        "watchlist": pd.concat(watchlists, ignore_index=True) if watchlists else pd.DataFrame(columns=WATCHLIST_COLUMNS),
        "order_intents": pd.concat(intents, ignore_index=True) if intents else pd.DataFrame(),
        "riskguard_decisions": pd.concat(decisions, ignore_index=True) if decisions else pd.DataFrame(),
    }
    if args.mark_seen:
        mark_emitted_events(registry, result["order_intents"])

    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "strategy": WATCHER_STRATEGY,
        "groups": groups,
        "timeframe_ltf": config.timeframe_ltf,
        "timeframe_htf": config.timeframe_htf,
        "lookback_bars": config.lookback_bars,
        "registry_path": str(registry_path),
        "mark_seen": bool(args.mark_seen),
        "watchlist_rows": int(len(result["watchlist"])),
        "order_intents": int(len(result["order_intents"])),
    }
    write_snapshot_outputs(result, output_dir, run_meta)
    return result


def run_watch(args: argparse.Namespace) -> None:
    iterations = int(args.iterations)
    counter = 0
    while True:
        result = run_snapshot_once(args)
        print(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            f"snapshot={len(result['snapshot'])} intents={len(result['order_intents'])}"
        )
        counter += 1
        if iterations > 0 and counter >= iterations:
            break
        time.sleep(float(args.interval_seconds))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Live Signal Watcher v0 para ENBOLSA macd_breakout.")
    parser.add_argument("--mode", choices=("snapshot", "watch"), default="snapshot")
    parser.add_argument("--groups", default="Forex Majors")
    parser.add_argument("--timeframe-ltf", default="H1")
    parser.add_argument("--timeframe-htf", default="H4")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--registry-path", default="")
    parser.add_argument("--mark-seen", action="store_true")
    parser.add_argument("--lookback-bars", type=int, default=1)
    parser.add_argument("--confirmation-memory-bars", type=int, default=5)
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--risk-per-trade-pct", type=float, default=1.0)
    parser.add_argument("--max-total-open-risk-pct", type=float, default=5.0)
    parser.add_argument("--max-symbol-open-risk-pct", type=float, default=1.0)
    parser.add_argument("--max-currency-gross-risk-pct", type=float, default=3.0)
    parser.add_argument("--max-currency-net-risk-pct", type=float, default=3.0)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--iterations", type=int, default=0)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--no-disk-cache", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.mode == "watch":
        run_watch(args)
    else:
        result = run_snapshot_once(args)
        print(f"snapshot={len(result['snapshot'])} intents={len(result['order_intents'])}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import heapq
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from backtests.common.backtest_matrix_config import get_account_config
from backtests.common.trade_analysis import DEFAULT_METRIC_COLUMNS, metrics_from_trades


DEFAULT_TRADE_LOG = Path("artifacts/benchmark-significance/enbolsa/final/tables/trade_log.csv")
DEFAULT_OUTPUT_DIR = Path("artifacts/benchmark-significance/enbolsa/risk_sensitivity_2026-05-15")
DEFAULT_CAPS = (0.03, 0.05, 0.10)
DEFAULT_STRATEGIES = ("enbolsa:fib_limit", "enbolsa:macd_breakout")

NUMERIC_COLUMNS = (
    "direction",
    "setup_id",
    "tp_mult",
    "size_fraction",
    "entry_price",
    "stop_price",
    "exit_price",
    "weighted_return",
    "pnl",
    "pnl_money",
    "risk_amount",
    "balance_before_entry",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_trade_log(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    for column in ("entry_time", "exit_time"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "source_family" not in frame.columns:
        frame["source_family"] = frame["strategy"].astype(str).str.split(":", n=1).str[0]
    frame["Family"] = frame["source_family"]
    frame["LTF"] = frame["timeframe_ltf"]
    frame["HTF"] = frame["timeframe_htf"]
    frame["TFPair"] = frame["LTF"].astype(str) + ":" + frame["HTF"].astype(str)
    frame["BlockId"] = frame["Group"].map(_clean_group) + "-" + frame["LTF"].str.lower() + "-" + frame["HTF"].str.lower()
    frame["realized_r"] = np.where(
        pd.to_numeric(frame["risk_amount"], errors="coerce") > 0,
        pd.to_numeric(frame["pnl_money"], errors="coerce") / pd.to_numeric(frame["risk_amount"], errors="coerce"),
        0.0,
    )
    return frame


def _parse_csv_arg(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _clean_group(value: object) -> str:
    return str(value).strip().lower().replace(" ", "-")


def _setup_group_columns(frame: pd.DataFrame) -> list[str]:
    candidates = [
        "strategy",
        "source_family",
        "Group",
        "timeframe_ltf",
        "timeframe_htf",
        "symbol",
        "entry_rule",
        "direction",
        "setup_id",
        "entry_time",
        "entry_price",
        "stop_price",
    ]
    return [column for column in candidates if column in frame.columns]


def _iter_setups(block: pd.DataFrame):
    group_cols = _setup_group_columns(block)
    for _, setup in block.groupby(group_cols, dropna=False, sort=True):
        yield setup.sort_values(["exit_time", "tp_mult"]).copy()


def _prepare_setups(block: pd.DataFrame) -> list[dict]:
    setups = []
    for setup in _iter_setups(block):
        legs = []
        for _, leg in setup.iterrows():
            legs.append({
                "entry_time": pd.Timestamp(leg["entry_time"]),
                "exit_time": pd.Timestamp(leg["exit_time"]),
                "size_fraction": float(leg.get("size_fraction", 1.0) or 1.0),
                "realized_r": float(leg.get("realized_r", 0.0) or 0.0),
                "symbol": str(leg.get("symbol", "")),
                "tp_mult": float(leg.get("tp_mult", 0.0) or 0.0),
                "observed_risk": float(leg.get("risk_amount", 0.0) or 0.0),
                "observed_pnl": float(leg.get("pnl_money", 0.0) or 0.0),
                "observed_weighted_return": float(leg.get("weighted_return", 0.0) or 0.0),
            })
        size_fraction = pd.to_numeric(setup["size_fraction"], errors="coerce").fillna(1.0)
        setups.append({
            "entry_time": pd.Timestamp(setup["entry_time"].min()),
            "last_exit": pd.Timestamp(setup["exit_time"].max()),
            "symbol": str(setup["symbol"].iloc[0]) if "symbol" in setup.columns else "",
            "legs": legs,
            "size_fraction_sum": float(size_fraction.sum()),
            "observed_risk": float(pd.to_numeric(setup["risk_amount"], errors="coerce").fillna(0.0).sum()),
            "observed_pnl": float(pd.to_numeric(setup["pnl_money"], errors="coerce").fillna(0.0).sum()),
        })
    return sorted(setups, key=lambda item: (item["entry_time"], item["symbol"], item["last_exit"]))


def _scenario_name(mode: str, cap_pct: float | None) -> str:
    if mode == "observed":
        return "observed_compounded_uncapped"
    if cap_pct is None:
        return f"{mode}_uncapped"
    return f"{mode}_cap_{int(round(cap_pct * 100))}pct"


def _simulate_block(
    block: pd.DataFrame,
    setups: list[dict],
    *,
    initial_capital: float,
    risk_per_trade: float,
    mode: str,
    cap_pct: float | None,
) -> tuple[pd.DataFrame, dict]:
    scenario = _scenario_name(mode, cap_pct)
    if mode == "observed":
        observed = block.copy()
        observed["Scenario"] = scenario
        open_diag = _max_open_diagnostics(observed, setups, initial_capital=initial_capital, observed=True)
        return observed, {
            "Scenario": scenario,
            "RiskMode": "observed_compounded",
            "CapPct": np.nan,
            "SetupsAccepted": len(setups),
            "SetupsSkipped": 0,
            "SetupSkipRate%": 0.0,
            **open_diag,
        }

    balance = float(initial_capital)
    open_risk = 0.0
    pending_exits: list[tuple[pd.Timestamp, int, float, float]] = []
    counter = 0
    accepted_rows = []
    accepted_setups_meta = []
    accepted_setups = 0
    skipped_setups = 0

    for setup in setups:
        entry_time = setup["entry_time"]
        while pending_exits and pending_exits[0][0] < entry_time:
            _, _, pnl_to_settle, risk_to_release = heapq.heappop(pending_exits)
            balance += pnl_to_settle
            open_risk = max(0.0, open_risk - risk_to_release)

        sizing_balance = balance if mode == "compounded" else float(initial_capital)
        if sizing_balance <= 0:
            skipped_setups += 1
            continue

        setup_risk = float(sizing_balance) * float(risk_per_trade) * setup["size_fraction_sum"]
        cap_amount = float(sizing_balance) * float(cap_pct) if cap_pct is not None else np.inf
        if open_risk + setup_risk > cap_amount + 1e-9:
            skipped_setups += 1
            continue

        accepted_setups += 1
        setup_pnl = 0.0
        setup_rows = setup["legs"]
        for leg in setup_rows:
            leg_risk = float(sizing_balance) * float(risk_per_trade) * float(leg.get("size_fraction", 1.0))
            realized_r = float(leg.get("realized_r", 0.0) or 0.0)
            pnl_money = realized_r * leg_risk
            setup_pnl += pnl_money

            row = {
                "Scenario": scenario,
                "entry_time": leg["entry_time"],
                "exit_time": leg["exit_time"],
                "symbol": leg.get("symbol", ""),
                "tp_mult": leg.get("tp_mult", 0.0),
                "risk_amount": leg_risk,
                "pnl_money": pnl_money,
                "pnl": pnl_money,
                "weighted_return": pnl_money / balance if balance > 0 else 0.0,
                "balance_before_entry": balance,
            }
            accepted_rows.append(row)

            open_risk += leg_risk
            counter += 1
            heapq.heappush(
                pending_exits,
                (pd.Timestamp(row["exit_time"]), counter, pnl_money, leg_risk),
            )
        accepted_setups_meta.append({
            "entry_time": entry_time,
            "last_exit": setup["last_exit"],
            "risk": setup_risk,
            "pnl": setup_pnl,
        })

    adjusted = pd.DataFrame(accepted_rows)
    if not adjusted.empty:
        adjusted = adjusted.sort_values(["exit_time", "entry_time", "symbol", "tp_mult"]).reset_index(drop=True)
    adjusted.attrs["initial_capital"] = float(initial_capital)
    open_diag = _max_open_diagnostics(adjusted, accepted_setups_meta, initial_capital=initial_capital, observed=False)
    return adjusted, {
        "Scenario": scenario,
        "RiskMode": mode,
        "CapPct": cap_pct if cap_pct is not None else np.nan,
        "SetupsAccepted": accepted_setups,
        "SetupsSkipped": skipped_setups,
        "SetupSkipRate%": round((skipped_setups / len(setups)) * 100.0, 2) if setups else 0.0,
        **open_diag,
    }


def _max_open_diagnostics(
    trades: pd.DataFrame,
    setups: list[dict],
    *,
    initial_capital: float,
    observed: bool,
) -> dict:
    if trades is None or trades.empty:
        return {
            "MaxOpenMicrolegs": 0,
            "MaxOpenRiskMicro%": 0.0,
            "MaxOpenSetups": 0,
            "MaxOpenRiskSetup%": 0.0,
        }

    micro_events = []
    for _, row in trades.iterrows():
        risk = float(row.get("risk_amount", 0.0) or 0.0)
        pnl = float(row.get("pnl_money", 0.0) or 0.0)
        micro_events.append((pd.Timestamp(row["entry_time"]), 0, risk, 0.0))
        micro_events.append((pd.Timestamp(row["exit_time"]), 1, -risk, pnl))

    setup_events = []
    for setup in setups:
        if observed:
            risk = float(setup.get("observed_risk", 0.0) or 0.0)
            pnl = float(setup.get("observed_pnl", 0.0) or 0.0)
        else:
            risk = float(setup.get("risk", 0.0) or 0.0)
            pnl = float(setup.get("pnl", 0.0) or 0.0)
        setup_events.append((pd.Timestamp(setup["entry_time"]), 0, risk, 0.0))
        setup_events.append((pd.Timestamp(setup["last_exit"]), 1, -risk, pnl))

    def sweep(events):
        balance = float(initial_capital)
        open_count = 0
        open_risk = 0.0
        max_count = 0
        max_pct = 0.0
        for _, event_type, risk_delta, pnl_delta in sorted(events, key=lambda item: (item[0], item[1])):
            if event_type == 0:
                open_count += 1
                open_risk += risk_delta
            else:
                open_count = max(0, open_count - 1)
                open_risk = max(0.0, open_risk + risk_delta)
                balance += pnl_delta
            denominator = balance if balance > 0 else float(initial_capital)
            pct = (open_risk / denominator) * 100.0 if denominator > 0 else 0.0
            if pct > max_pct:
                max_pct = pct
                max_count = open_count
        return max_count, max_pct

    max_microlegs, max_micro_pct = sweep(micro_events)
    max_setups, max_setup_pct = sweep(setup_events)
    return {
        "MaxOpenMicrolegs": int(max_microlegs),
        "MaxOpenRiskMicro%": round(float(max_micro_pct), 2),
        "MaxOpenSetups": int(max_setups),
        "MaxOpenRiskSetup%": round(float(max_setup_pct), 2),
    }


def _metrics_row(block: pd.DataFrame, simulated: pd.DataFrame, diagnostics: dict, initial_capital: float) -> dict:
    scoped = simulated.copy() if simulated is not None else pd.DataFrame()
    scoped.attrs["initial_capital"] = float(initial_capital)
    metrics = metrics_from_trades(scoped)
    first = block.iloc[0]
    return {
        "Variante": first["strategy"],
        "Family": first["source_family"],
        "Group": first["Group"],
        "LTF": first["timeframe_ltf"],
        "HTF": first["timeframe_htf"],
        "TFPair": first["TFPair"],
        "BlockId": first["BlockId"],
        "MetricScope": "risk_sensitivity_block",
        **diagnostics,
        **metrics,
    }


def _aggregate_block_metrics(block_metrics: pd.DataFrame) -> pd.DataFrame:
    if block_metrics.empty:
        return pd.DataFrame()
    rows = []
    for (scenario, variant), group in block_metrics.groupby(["Scenario", "Variante"], sort=True):
        returns = pd.to_numeric(group["Return%"], errors="coerce")
        pf = pd.to_numeric(group["PF"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        max_dd = pd.to_numeric(group["MaxDD%"], errors="coerce")
        rows.append({
            "Scenario": scenario,
            "Variante": variant,
            "Family": str(group["Family"].dropna().iloc[0]) if group["Family"].notna().any() else "",
            "MetricScope": "risk_sensitivity_aggregate",
            "Blocks": int(len(group)),
            "TotalTrades": int(pd.to_numeric(group["Trades"], errors="coerce").fillna(0).sum()),
            "TotalNetProfit": round(float(pd.to_numeric(group["NetProfit"], errors="coerce").fillna(0).sum()), 2),
            "MeanReturn%": round(float(returns.mean()), 2) if returns.notna().any() else 0.0,
            "MedianReturn%": round(float(returns.median()), 2) if returns.notna().any() else 0.0,
            "MinReturn%": round(float(returns.min()), 2) if returns.notna().any() else 0.0,
            "MaxReturn%": round(float(returns.max()), 2) if returns.notna().any() else 0.0,
            "PositiveBlocks": int((returns > 0).sum()),
            "PositiveBlockRate%": round(float((returns > 0).mean() * 100.0), 1) if len(returns) else 0.0,
            "MedianPF": round(float(pf.median()), 2) if pf.notna().any() else 0.0,
            "MedianMaxDD%": round(float(max_dd.median()), 2) if max_dd.notna().any() else 0.0,
            "MaxOpenRiskMicro%": round(float(pd.to_numeric(group["MaxOpenRiskMicro%"], errors="coerce").max()), 2),
            "MaxOpenRiskSetup%": round(float(pd.to_numeric(group["MaxOpenRiskSetup%"], errors="coerce").max()), 2),
        })
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, block_metrics: pd.DataFrame, aggregate: pd.DataFrame, run_meta: dict) -> None:
    focus = block_metrics[
        (block_metrics["Variante"] == "enbolsa:macd_breakout")
        & (block_metrics["BlockId"] == "forex-majors-h1-h4")
    ].copy()
    focus = focus.sort_values("Scenario")
    macd_aggregate = aggregate[aggregate["Variante"] == "enbolsa:macd_breakout"].copy()

    def md_table(frame: pd.DataFrame, cols: list[str]) -> str:
        if frame.empty:
            return "_Sin filas._"
        view = frame[cols].copy()
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
        for _, row in view.iterrows():
            values = []
            for col in cols:
                value = row[col]
                if pd.isna(value):
                    text = ""
                elif isinstance(value, float):
                    text = f"{value:.4g}"
                else:
                    text = str(value)
                values.append(text)
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    lines = [
        "# Sensibilidad de riesgo ENBOLSA",
        "",
        f"Fecha de ejecucion: `{run_meta['generated_at']}`",
        "",
        "## Reproducibilidad",
        "",
        "```powershell",
        run_meta["command"],
        "```",
        "",
        f"Estrategias procesadas: `{', '.join(run_meta['strategies'])}`.",
        "",
        "La prueba reutiliza el `trade_log` canonico y no cambia reglas de entrada, salida, TP, SL ni filtros.",
        "",
        "## Bloque extremo",
        "",
        md_table(
            focus,
            [
                "Scenario",
                "Trades",
                "SetupsAccepted",
                "SetupsSkipped",
                "Return%",
                "PF",
                "MaxDD%",
                "NetProfit",
                "AvgR",
                "MaxOpenRiskMicro%",
                "MaxOpenRiskSetup%",
            ],
        ),
        "",
        "## Agregado macd_breakout",
        "",
        md_table(
            macd_aggregate,
            [
                "Scenario",
                "Blocks",
                "TotalTrades",
                "TotalNetProfit",
                "MeanReturn%",
                "MedianReturn%",
                "PositiveBlockRate%",
                "MedianPF",
                "MedianMaxDD%",
                "MaxOpenRiskMicro%",
                "MaxOpenRiskSetup%",
            ],
        ),
        "",
        "## Lectura",
        "",
        "- El bloque `Forex Majors / H1:H4` sigue siendo positivo en escenarios de riesgo fijo y caps, pero el retorno cae mucho frente al compuesto sin cap.",
        "- Los caps se aplican sobre riesgo abierto de micro-patas; el diagnostico por setup completo puede superar el cap porque conserva el riesgo teorico del setup hasta la ultima salida.",
        "- Los escenarios con cap son path-dependent: si el cap salta operaciones perdedoras, puede mejorar el resultado. No deben interpretarse como optimizacion de cap.",
        "- El resultado canonico no parece un error de calculo; refleja un modelo operativo agresivo.",
        "- Para la memoria conviene presentar `macd_breakout` como estrategia con evidencia favorable, condicionada por riesgo agregado y no como rentabilidad live esperable.",
        "- Para bot o screener operativo, el siguiente requisito es un `RiskGuard` con cap de riesgo abierto y control de correlaciones.",
        "",
        "## Archivos",
        "",
        "- `tables/scenario_block_metrics.csv`",
        "- `tables/aggregate_by_strategy_sensitivity.csv`",
        "- `tables/extreme_block_focus.csv`",
        "- `run_meta.json`",
        "",
    ]
    (output_dir / "RISK_SENSITIVITY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    trade_log_path = Path(args.trade_log)
    if not trade_log_path.is_absolute():
        trade_log_path = repo_root / trade_log_path
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    account_config = get_account_config()
    initial_capital = float(args.initial_capital or account_config["initial_capital"])
    risk_per_trade = float(args.risk_per_trade or account_config["risk_per_trade"])
    caps = [float(item.strip()) / 100.0 for item in args.caps.split(",") if item.strip()]

    trade_log = _read_trade_log(trade_log_path)
    strategies = _parse_csv_arg(args.strategies)
    if strategies:
        trade_log = trade_log[trade_log["strategy"].isin(strategies)].copy()
    if trade_log.empty:
        raise ValueError("No hay trades despues de aplicar el filtro de estrategias.")

    scenarios = [("observed", None), ("fixed_initial", None)]
    scenarios.extend(("fixed_initial", cap) for cap in caps)
    scenarios.extend(("compounded", cap) for cap in caps)

    block_rows = []
    group_cols = ["strategy", "source_family", "Group", "timeframe_ltf", "timeframe_htf"]
    for _, block in trade_log.groupby(group_cols, sort=True, dropna=False):
        block = block.copy()
        setups = _prepare_setups(block)
        for mode, cap_pct in scenarios:
            simulated, diagnostics = _simulate_block(
                block,
                setups,
                initial_capital=initial_capital,
                risk_per_trade=risk_per_trade,
                mode=mode,
                cap_pct=cap_pct,
            )
            row = _metrics_row(block, simulated, diagnostics, initial_capital)
            block_rows.append(row)

    block_metrics = pd.DataFrame(block_rows)
    cols = [
        "Scenario",
        "RiskMode",
        "CapPct",
        "Variante",
        "Family",
        "Group",
        "LTF",
        "HTF",
        "TFPair",
        "BlockId",
        "MetricScope",
        "SetupsAccepted",
        "SetupsSkipped",
        "SetupSkipRate%",
        "MaxOpenMicrolegs",
        "MaxOpenRiskMicro%",
        "MaxOpenSetups",
        "MaxOpenRiskSetup%",
        *DEFAULT_METRIC_COLUMNS,
    ]
    block_metrics = block_metrics[cols].sort_values(["Scenario", "Variante", "Group", "LTF", "HTF"]).reset_index(drop=True)
    aggregate = _aggregate_block_metrics(block_metrics)
    focus = block_metrics[
        (block_metrics["Variante"] == "enbolsa:macd_breakout")
        & (block_metrics["BlockId"] == "forex-majors-h1-h4")
    ].copy()

    block_metrics.to_csv(tables_dir / "scenario_block_metrics.csv", index=False)
    aggregate.to_csv(tables_dir / "aggregate_by_strategy_sensitivity.csv", index=False)
    focus.to_csv(tables_dir / "extreme_block_focus.csv", index=False)

    command = (
        "python -m backtests.benchmarks.analyze_enbolsa_risk_sensitivity "
        f"--trade-log {args.trade_log} --output-dir {args.output_dir} "
        f"--strategies {args.strategies} --caps {args.caps} "
        f"--initial-capital {initial_capital:g} --risk-per-trade {risk_per_trade:g}"
    )
    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "trade_log": str(trade_log_path),
        "output_dir": str(output_dir),
        "initial_capital": initial_capital,
        "risk_per_trade": risk_per_trade,
        "strategies": strategies,
        "caps": caps,
        "scenarios": [_scenario_name(mode, cap) for mode, cap in scenarios],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(output_dir, block_metrics, aggregate, run_meta)
    print(f"Artifacts escritos en: {output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sensibilidad de riesgo sobre el trade_log canonico ENBOLSA.")
    parser.add_argument("--trade-log", default=str(DEFAULT_TRADE_LOG))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--caps", default="3,5,10", help="Caps de riesgo abierto en porcentaje, separados por coma.")
    parser.add_argument("--initial-capital", type=float, default=None)
    parser.add_argument("--risk-per-trade", type=float, default=None)
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())

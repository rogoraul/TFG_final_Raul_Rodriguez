from __future__ import annotations

import argparse
import heapq
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from backtests.common.trade_analysis import metrics_from_trades


DEFAULT_TRADE_LOG = Path("artifacts/benchmark-significance/enbolsa/final/tables/trade_log.csv")
DEFAULT_OUTPUT_DIR = Path("artifacts/benchmark-significance/enbolsa/riskguard_audit_2026-05-15")
DEFAULT_STRATEGY = "enbolsa:macd_breakout"
DEFAULT_RISK_PER_TRADE_PCT = 1.0
FOREX_CODES = ("AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NZD", "USD")


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


def _clean_group(value: object) -> str:
    return str(value).strip().lower().replace(" ", "-")


def _tf_pair(ltf: object, htf: object) -> str:
    return f"{ltf}:{htf}"


def _read_trade_log(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    for column in ("entry_time", "exit_time"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "source_family" not in frame.columns:
        frame["source_family"] = frame["strategy"].astype(str).str.split(":", n=1).str[0]
    frame["TFPair"] = frame["timeframe_ltf"].astype(str) + ":" + frame["timeframe_htf"].astype(str)
    frame["BlockId"] = (
        frame["Group"].map(_clean_group)
        + "-"
        + frame["timeframe_ltf"].astype(str).str.lower()
        + "-"
        + frame["timeframe_htf"].astype(str).str.lower()
    )
    frame["realized_r"] = np.where(
        pd.to_numeric(frame["risk_amount"], errors="coerce") > 0,
        pd.to_numeric(frame["pnl_money"], errors="coerce") / pd.to_numeric(frame["risk_amount"], errors="coerce"),
        0.0,
    )
    return frame


def _parse_optional_csv(value: str | None) -> set[str] | None:
    values = {item.strip() for item in str(value or "").split(",") if item.strip()}
    return values or None


def _normalise_symbol(symbol: object) -> str:
    return str(symbol or "").split(".", 1)[0].upper().strip()


def _normalise_currency(value: object) -> str:
    text = str(value or "").upper().strip()
    return text if text and text != "NAN" else ""


def _infer_currencies(row: pd.Series) -> tuple[str, str]:
    base = _normalise_currency(row.get("SYMBOL_CURRENCY_BASE"))
    quote = _normalise_currency(row.get("SYMBOL_CURRENCY_PROFIT"))
    if base and quote:
        return base, quote

    clean = _normalise_symbol(row.get("symbol"))
    if len(clean) >= 6:
        left = clean[:3]
        right = clean[3:6]
        if left in FOREX_CODES and right in FOREX_CODES:
            return left, right
        if right in FOREX_CODES:
            return clean[:-3] or left, right
    return base or clean or "UNKNOWN", quote or "UNKNOWN"


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


def _prepare_setups(frame: pd.DataFrame, initial_capital: float, risk_per_trade: float, risk_mode: str) -> list[dict]:
    setups = []
    for _, setup in frame.groupby(_setup_group_columns(frame), dropna=False, sort=True):
        setup = setup.sort_values(["exit_time", "tp_mult"]).copy()
        first = setup.iloc[0]
        base, quote = _infer_currencies(first)
        size_fractions = pd.to_numeric(setup["size_fraction"], errors="coerce").fillna(1.0)
        observed_risk = float(pd.to_numeric(setup["risk_amount"], errors="coerce").fillna(0.0).sum())
        fixed_setup_risk = float(initial_capital) * float(risk_per_trade) * float(size_fractions.sum())
        setup_risk = observed_risk if risk_mode == "observed" else fixed_setup_risk

        legs = []
        for _, leg in setup.iterrows():
            size_fraction = float(leg.get("size_fraction", 1.0) or 1.0)
            original_risk = float(leg.get("risk_amount", 0.0) or 0.0)
            risk_amount = original_risk if risk_mode == "observed" else float(initial_capital) * float(risk_per_trade) * size_fraction
            realized_r = float(leg.get("realized_r", 0.0) or 0.0)
            pnl_money = realized_r * risk_amount
            legs.append({
                "tp_mult": float(leg.get("tp_mult", 0.0) or 0.0),
                "size_fraction": size_fraction,
                "entry_time": pd.Timestamp(leg["entry_time"]),
                "exit_time": pd.Timestamp(leg["exit_time"]),
                "exit_reason": str(leg.get("exit_reason", "")),
                "original_risk_amount": original_risk,
                "risk_amount": risk_amount,
                "original_pnl_money": float(leg.get("pnl_money", 0.0) or 0.0),
                "pnl_money": pnl_money,
                "realized_r": realized_r,
            })

        setups.append({
            "strategy": str(first["strategy"]),
            "source_family": str(first.get("source_family", "")),
            "group": str(first["Group"]),
            "ltf": str(first["timeframe_ltf"]),
            "htf": str(first["timeframe_htf"]),
            "tf_pair": _tf_pair(first["timeframe_ltf"], first["timeframe_htf"]),
            "block_id": str(first["BlockId"]),
            "symbol": str(first["symbol"]),
            "entry_rule": str(first.get("entry_rule", "")),
            "direction": int(first["direction"]),
            "setup_id": first.get("setup_id"),
            "entry_time": pd.Timestamp(setup["entry_time"].min()),
            "last_exit": pd.Timestamp(setup["exit_time"].max()),
            "entry_price": float(first.get("entry_price", np.nan)),
            "stop_price": float(first.get("stop_price", np.nan)),
            "base_currency": base,
            "quote_currency": quote,
            "setup_risk": setup_risk,
            "observed_setup_risk": observed_risk,
            "legs": legs,
        })
    return sorted(setups, key=lambda item: (item["entry_time"], item["symbol"], str(item["setup_id"])))


def _currency_contributions(setup: dict, risk_amount: float) -> list[tuple[str, str, float]]:
    direction = int(setup["direction"])
    base = setup["base_currency"] or "UNKNOWN"
    quote = setup["quote_currency"] or "UNKNOWN"
    if direction == 1:
        return [(base, "long", risk_amount), (quote, "short", risk_amount)]
    return [(base, "short", risk_amount), (quote, "long", risk_amount)]


def _add_currency(currency_book: dict[str, dict[str, float]], contributions: list[tuple[str, str, float]], sign: float) -> None:
    for currency, side, amount in contributions:
        currency_book[currency][side] = max(0.0, currency_book[currency][side] + sign * float(amount))


def _currency_snapshot(currency_book: dict[str, dict[str, float]], initial_capital: float) -> list[dict]:
    rows = []
    for currency, sides in sorted(currency_book.items()):
        long_risk = float(sides.get("long", 0.0))
        short_risk = float(sides.get("short", 0.0))
        gross = long_risk + short_risk
        net = long_risk - short_risk
        rows.append({
            "Currency": currency,
            "LongRisk": long_risk,
            "ShortRisk": short_risk,
            "GrossRisk": gross,
            "NetRisk": net,
            "LongRisk%": (long_risk / initial_capital) * 100.0,
            "ShortRisk%": (short_risk / initial_capital) * 100.0,
            "GrossRisk%": (gross / initial_capital) * 100.0,
            "NetRisk%": (net / initial_capital) * 100.0,
            "AbsNetRisk%": (abs(net) / initial_capital) * 100.0,
        })
    return rows


def _update_currency_max(max_book: dict[str, dict[str, float]], currency_book: dict[str, dict[str, float]], initial_capital: float) -> None:
    for row in _currency_snapshot(currency_book, initial_capital):
        record = max_book[row["Currency"]]
        for column in ("LongRisk%", "ShortRisk%", "GrossRisk%", "AbsNetRisk%"):
            record[column] = max(float(record.get(column, 0.0)), float(row[column]))


def _project_currency_limits(
    setup: dict,
    currency_book: dict[str, dict[str, float]],
    initial_capital: float,
    max_gross_pct: float,
    max_net_pct: float,
) -> tuple[bool, str, str]:
    projected = defaultdict(lambda: {"long": 0.0, "short": 0.0})
    for currency, sides in currency_book.items():
        projected[currency]["long"] = float(sides.get("long", 0.0))
        projected[currency]["short"] = float(sides.get("short", 0.0))
    _add_currency(projected, _currency_contributions(setup, setup["setup_risk"]), 1.0)

    for row in _currency_snapshot(projected, initial_capital):
        if row["GrossRisk%"] > max_gross_pct + 1e-9:
            return False, "currency_gross_cap", f"{row['Currency']} gross {row['GrossRisk%']:.2f}% > {max_gross_pct:.2f}%"
        if row["AbsNetRisk%"] > max_net_pct + 1e-9:
            return False, "currency_net_cap", f"{row['Currency']} net {row['AbsNetRisk%']:.2f}% > {max_net_pct:.2f}%"
    return True, "", ""


def _release_until(
    pending_exits: list[tuple[pd.Timestamp, int, dict]],
    entry_time: pd.Timestamp,
    state: dict,
    initial_capital: float,
) -> None:
    while pending_exits and pending_exits[0][0] < entry_time:
        _, _, event = heapq.heappop(pending_exits)
        risk = float(event["risk_amount"])
        state["total_open_risk"] = max(0.0, state["total_open_risk"] - risk)
        state["symbol_open_risk"][event["symbol"]] = max(0.0, state["symbol_open_risk"][event["symbol"]] - risk)
        _add_currency(state["currency_book"], event["currency_contributions"], -1.0)
        _update_currency_max(state["currency_max"], state["currency_book"], initial_capital)


def _accepted_trade_rows(setup: dict, initial_capital: float) -> list[dict]:
    rows = []
    for leg in setup["legs"]:
        risk_amount = float(leg["risk_amount"])
        pnl_money = float(leg["pnl_money"])
        rows.append({
            "strategy": setup["strategy"],
            "source_family": setup["source_family"],
            "Group": setup["group"],
            "timeframe_ltf": setup["ltf"],
            "timeframe_htf": setup["htf"],
            "TFPair": setup["tf_pair"],
            "BlockId": setup["block_id"],
            "symbol": setup["symbol"],
            "entry_rule": setup["entry_rule"],
            "direction": setup["direction"],
            "setup_id": setup["setup_id"],
            "tp_mult": leg["tp_mult"],
            "size_fraction": leg["size_fraction"],
            "entry_time": leg["entry_time"],
            "exit_time": leg["exit_time"],
            "exit_reason": leg["exit_reason"],
            "entry_price": setup["entry_price"],
            "stop_price": setup["stop_price"],
            "base_currency": setup["base_currency"],
            "quote_currency": setup["quote_currency"],
            "original_risk_amount": leg["original_risk_amount"],
            "risk_amount": risk_amount,
            "original_pnl_money": leg["original_pnl_money"],
            "pnl_money": pnl_money,
            "pnl": pnl_money,
            "realized_r": leg["realized_r"],
            "weighted_return": pnl_money / initial_capital if initial_capital > 0 else 0.0,
            "balance_before_entry": initial_capital,
        })
    return rows


def _rejected_row(setup: dict, reason: str, detail: str, state: dict, initial_capital: float) -> dict:
    return {
        "strategy": setup["strategy"],
        "Group": setup["group"],
        "timeframe_ltf": setup["ltf"],
        "timeframe_htf": setup["htf"],
        "TFPair": setup["tf_pair"],
        "BlockId": setup["block_id"],
        "symbol": setup["symbol"],
        "direction": setup["direction"],
        "setup_id": setup["setup_id"],
        "entry_time": setup["entry_time"],
        "last_exit": setup["last_exit"],
        "base_currency": setup["base_currency"],
        "quote_currency": setup["quote_currency"],
        "setup_risk": setup["setup_risk"],
        "setup_risk_pct": (setup["setup_risk"] / initial_capital) * 100.0 if initial_capital > 0 else 0.0,
        "total_open_risk_before": state["total_open_risk"],
        "total_open_risk_before_pct": (state["total_open_risk"] / initial_capital) * 100.0 if initial_capital > 0 else 0.0,
        "symbol_open_risk_before": state["symbol_open_risk"].get(setup["symbol"], 0.0),
        "symbol_open_risk_before_pct": (state["symbol_open_risk"].get(setup["symbol"], 0.0) / initial_capital) * 100.0 if initial_capital > 0 else 0.0,
        "rejection_reason": reason,
        "rejection_detail": detail,
    }


def _simulate_block(setups: list[dict], args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    initial_capital = float(args.initial_capital)
    state = {
        "total_open_risk": 0.0,
        "symbol_open_risk": defaultdict(float),
        "currency_book": defaultdict(lambda: {"long": 0.0, "short": 0.0}),
        "currency_max": defaultdict(dict),
    }
    pending_exits: list[tuple[pd.Timestamp, int, dict]] = []
    event_counter = 0
    accepted_rows = []
    rejected_rows = []
    accepted_setups = 0
    rejected_setups = 0

    for setup in setups:
        _release_until(pending_exits, setup["entry_time"], state, initial_capital)

        setup_risk_pct = (setup["setup_risk"] / initial_capital) * 100.0 if initial_capital > 0 else np.inf
        projected_total_pct = ((state["total_open_risk"] + setup["setup_risk"]) / initial_capital) * 100.0
        projected_symbol_pct = ((state["symbol_open_risk"][setup["symbol"]] + setup["setup_risk"]) / initial_capital) * 100.0

        accept = True
        reason = ""
        detail = ""
        if setup_risk_pct <= 0:
            accept = False
            reason = "invalid_setup_risk"
            detail = f"setup risk {setup_risk_pct:.2f}%"
        elif projected_total_pct > float(args.max_total_open_risk_pct) + 1e-9:
            accept = False
            reason = "total_open_risk_cap"
            detail = f"total {projected_total_pct:.2f}% > {float(args.max_total_open_risk_pct):.2f}%"
        elif projected_symbol_pct > float(args.max_symbol_open_risk_pct) + 1e-9:
            accept = False
            reason = "symbol_open_risk_cap"
            detail = f"{setup['symbol']} {projected_symbol_pct:.2f}% > {float(args.max_symbol_open_risk_pct):.2f}%"
        else:
            accept, reason, detail = _project_currency_limits(
                setup,
                state["currency_book"],
                initial_capital,
                float(args.max_currency_gross_risk_pct),
                float(args.max_currency_net_risk_pct),
            )

        if not accept:
            rejected_setups += 1
            rejected_rows.append(_rejected_row(setup, reason, detail, state, initial_capital))
            continue

        accepted_setups += 1
        accepted_rows.extend(_accepted_trade_rows(setup, initial_capital))
        for leg in setup["legs"]:
            risk = float(leg["risk_amount"])
            contributions = _currency_contributions(setup, risk)
            state["total_open_risk"] += risk
            state["symbol_open_risk"][setup["symbol"]] += risk
            _add_currency(state["currency_book"], contributions, 1.0)
            event_counter += 1
            heapq.heappush(
                pending_exits,
                (pd.Timestamp(leg["exit_time"]), event_counter, {
                    "risk_amount": risk,
                    "symbol": setup["symbol"],
                    "currency_contributions": contributions,
                }),
            )
        _update_currency_max(state["currency_max"], state["currency_book"], initial_capital)

    while pending_exits:
        _release_until(pending_exits, pd.Timestamp.max, state, initial_capital)

    accepted = pd.DataFrame(accepted_rows)
    rejected = pd.DataFrame(rejected_rows)
    exposure_rows = []
    for currency, values in sorted(state["currency_max"].items()):
        exposure_rows.append({
            "Currency": currency,
            "MaxLongRisk%": round(float(values.get("LongRisk%", 0.0)), 4),
            "MaxShortRisk%": round(float(values.get("ShortRisk%", 0.0)), 4),
            "MaxGrossRisk%": round(float(values.get("GrossRisk%", 0.0)), 4),
            "MaxAbsNetRisk%": round(float(values.get("AbsNetRisk%", 0.0)), 4),
        })
    exposure = pd.DataFrame(exposure_rows)
    stats = {
        "AcceptedSetups": accepted_setups,
        "RejectedSetups": rejected_setups,
        "TotalSetups": accepted_setups + rejected_setups,
        "AcceptanceRate%": round((accepted_setups / (accepted_setups + rejected_setups)) * 100.0, 2) if accepted_setups + rejected_setups else 0.0,
    }
    return accepted, rejected, exposure, stats


def _metrics_frame(trades: pd.DataFrame, initial_capital: float) -> dict:
    scoped = trades.copy() if trades is not None else pd.DataFrame()
    scoped.attrs["initial_capital"] = float(initial_capital)
    return metrics_from_trades(scoped)


def _block_metrics(accepted: pd.DataFrame, rejected: pd.DataFrame, original: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    block_keys = ["strategy", "source_family", "Group", "timeframe_ltf", "timeframe_htf", "TFPair", "BlockId"]
    rows = []
    for keys, block_original in original.groupby(block_keys, dropna=False, sort=True):
        key_map = dict(zip(block_keys, keys if isinstance(keys, tuple) else (keys,)))
        if accepted.empty:
            block_accepted = pd.DataFrame()
        else:
            mask = pd.Series(True, index=accepted.index)
            for column, value in key_map.items():
                mask &= accepted[column] == value
            block_accepted = accepted[mask].copy()
        if rejected.empty:
            block_rejected = pd.DataFrame()
        else:
            mask = pd.Series(True, index=rejected.index)
            for column in ("strategy", "Group", "timeframe_ltf", "timeframe_htf", "TFPair", "BlockId"):
                mask &= rejected[column] == key_map[column]
            block_rejected = rejected[mask].copy()

        metrics = _metrics_frame(block_accepted, initial_capital)
        setup_cols = ["symbol", "direction", "setup_id", "entry_time", "entry_price", "stop_price"]
        accepted_setups = len(block_accepted.groupby([col for col in setup_cols if col in block_accepted.columns], dropna=False)) if not block_accepted.empty else 0
        rejected_setups = len(block_rejected) if not block_rejected.empty else 0
        rows.append({
            "Variante": key_map["strategy"],
            "Family": key_map["source_family"],
            "Group": key_map["Group"],
            "LTF": key_map["timeframe_ltf"],
            "HTF": key_map["timeframe_htf"],
            "TFPair": key_map["TFPair"],
            "BlockId": key_map["BlockId"],
            "MetricScope": "riskguard_block",
            "AcceptedSetups": accepted_setups,
            "RejectedSetups": rejected_setups,
            "AcceptanceRate%": round((accepted_setups / (accepted_setups + rejected_setups)) * 100.0, 2) if accepted_setups + rejected_setups else 0.0,
            **metrics,
        })
    return pd.DataFrame(rows)


def _original_block_metrics(original: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    block_keys = ["strategy", "source_family", "Group", "timeframe_ltf", "timeframe_htf", "TFPair", "BlockId"]
    rows = []
    for keys, block in original.groupby(block_keys, dropna=False, sort=True):
        key_map = dict(zip(block_keys, keys if isinstance(keys, tuple) else (keys,)))
        metrics = _metrics_frame(block, initial_capital)
        rows.append({
            "Variante": key_map["strategy"],
            "Family": key_map["source_family"],
            "Group": key_map["Group"],
            "LTF": key_map["timeframe_ltf"],
            "HTF": key_map["timeframe_htf"],
            "TFPair": key_map["TFPair"],
            "BlockId": key_map["BlockId"],
            "MetricScope": "original_block",
            **metrics,
        })
    return pd.DataFrame(rows)


def _comparison(original_metrics: pd.DataFrame, riskguard_metrics: pd.DataFrame) -> pd.DataFrame:
    keys = ["Variante", "Family", "Group", "LTF", "HTF", "TFPair", "BlockId"]
    merged = original_metrics.merge(riskguard_metrics, on=keys, suffixes=("_Original", "_RiskGuard"), how="left")
    rows = []
    for _, row in merged.iterrows():
        rows.append({
            **{key: row[key] for key in keys},
            "OriginalTrades": row.get("Trades_Original", 0),
            "RiskGuardTrades": row.get("Trades_RiskGuard", 0),
            "OriginalReturn%": row.get("Return%_Original", 0.0),
            "RiskGuardReturn%": row.get("Return%_RiskGuard", 0.0),
            "ReturnDeltaPctPoints": round(float(row.get("Return%_RiskGuard", 0.0)) - float(row.get("Return%_Original", 0.0)), 2),
            "OriginalPF": row.get("PF_Original", 0.0),
            "RiskGuardPF": row.get("PF_RiskGuard", 0.0),
            "OriginalMaxDD%": row.get("MaxDD%_Original", 0.0),
            "RiskGuardMaxDD%": row.get("MaxDD%_RiskGuard", 0.0),
            "AcceptedSetups": row.get("AcceptedSetups", 0),
            "RejectedSetups": row.get("RejectedSetups", 0),
            "AcceptanceRate%": row.get("AcceptanceRate%", 0.0),
        })
    return pd.DataFrame(rows)


def _rejection_summary(rejected: pd.DataFrame) -> pd.DataFrame:
    if rejected.empty:
        return pd.DataFrame(columns=["rejection_reason", "Setups"])
    return (
        rejected.groupby("rejection_reason")
        .size()
        .rename("Setups")
        .reset_index()
        .sort_values("Setups", ascending=False)
    )


def _extreme_summary(comparison: pd.DataFrame, rejected: pd.DataFrame, exposure: pd.DataFrame) -> pd.DataFrame:
    row = comparison[
        (comparison["Variante"] == DEFAULT_STRATEGY)
        & (comparison["Group"] == "Forex Majors")
        & (comparison["TFPair"] == "H1:H4")
    ].copy()
    if row.empty:
        return pd.DataFrame()
    top_reasons = (
        rejected[rejected["BlockId"] == "forex-majors-h1-h4"]["rejection_reason"].value_counts().head(5).to_dict()
        if not rejected.empty and "BlockId" in rejected.columns else {}
    )
    max_currency = ""
    if not exposure.empty:
        focus = exposure[exposure["BlockId"] == "forex-majors-h1-h4"].copy() if "BlockId" in exposure.columns else exposure.copy()
        if not focus.empty:
            item = focus.sort_values("MaxGrossRisk%", ascending=False).iloc[0]
            max_currency = f"{item['Currency']} gross {float(item['MaxGrossRisk%']):.2f}%"
    row["TopRejectionReasons"] = json.dumps(top_reasons, ensure_ascii=False)
    row["MaxCurrencyExposure"] = max_currency
    return row


def _write_report(
    output_dir: Path,
    run_meta: dict,
    comparison: pd.DataFrame,
    extreme: pd.DataFrame,
    rejection_summary: pd.DataFrame,
    exposure: pd.DataFrame,
) -> None:
    def md_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
        if frame is None or frame.empty:
            return "_Sin filas._"
        view = frame[columns].head(max_rows).copy()
        lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
        for _, item in view.iterrows():
            values = []
            for col in columns:
                value = item[col]
                if pd.isna(value):
                    text = ""
                elif isinstance(value, float):
                    text = f"{value:.4g}"
                else:
                    text = str(value)
                values.append(text.replace("|", "\\|"))
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    lines = [
        "# Auditoria operativa RiskGuard ENBOLSA",
        "",
        f"Fecha de ejecucion: `{run_meta['generated_at']}`",
        "",
        "## Reproducibilidad",
        "",
        "```powershell",
        run_meta["command"],
        "```",
        "",
        "Esta auditoria no reejecuta senales ni modifica la estrategia original. Reutiliza el `trade_log` canonico y simula una capa operativa first-come-first-served.",
        "",
        "## Politica aplicada",
        "",
        f"- estrategia: `{run_meta['strategy']}`",
        f"- risk_mode: `{run_meta['risk_mode']}`",
        f"- risk_per_trade_pct: `{run_meta['risk_per_trade_pct']}`",
        f"- max_total_open_risk_pct: `{run_meta['max_total_open_risk_pct']}`",
        f"- max_symbol_open_risk_pct: `{run_meta['max_symbol_open_risk_pct']}`",
        f"- max_currency_gross_risk_pct: `{run_meta['max_currency_gross_risk_pct']}`",
        f"- max_currency_net_risk_pct: `{run_meta['max_currency_net_risk_pct']}`",
        "- granularidad: cada setup completo se acepta o rechaza de forma atomica; el riesgo se libera por pata cuando cada TP/SL sale del mercado.",
        "- diversificacion: exposicion por divisa base/quote y direccion; no correlacion estadistica.",
        "",
        "## Comparacion por bloque",
        "",
        md_table(
            comparison.sort_values(["Group", "TFPair"]),
            [
                "Group", "TFPair", "OriginalTrades", "RiskGuardTrades",
                "OriginalReturn%", "RiskGuardReturn%", "OriginalPF", "RiskGuardPF",
                "OriginalMaxDD%", "RiskGuardMaxDD%", "AcceptanceRate%",
            ],
        ),
        "",
        "## Bloque extremo Forex Majors H1:H4",
        "",
        md_table(
            extreme,
            [
                "OriginalTrades", "RiskGuardTrades", "OriginalReturn%", "RiskGuardReturn%",
                "OriginalPF", "RiskGuardPF", "OriginalMaxDD%", "RiskGuardMaxDD%",
                "AcceptanceRate%", "TopRejectionReasons", "MaxCurrencyExposure",
            ],
        ),
        "",
        "## Motivos de rechazo",
        "",
        md_table(rejection_summary, ["rejection_reason", "Setups"]),
        "",
        "## Exposicion maxima por divisa",
        "",
        md_table(
            exposure.sort_values("MaxGrossRisk%", ascending=False),
            ["BlockId", "Currency", "MaxLongRisk%", "MaxShortRisk%", "MaxGrossRisk%", "MaxAbsNetRisk%"],
            max_rows=30,
        ),
        "",
        "## Lectura",
        "",
        "- Esta salida no sustituye al benchmark canonico; es una subfase operativa.",
        "- Si la rentabilidad cae, la lectura no es que la estrategia original estuviera mal, sino que un bot real necesita limitar exposicion agregada.",
        "- La correlacion queda para una posible v1.5; en v1 se mide concentracion por divisa y direccion.",
        "",
    ]
    (output_dir / "RISKGUARD_AUDIT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    trade_log_path = Path(args.trade_log)
    output_dir = Path(args.output_dir)
    if not trade_log_path.is_absolute():
        trade_log_path = repo_root / trade_log_path
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    trade_log = _read_trade_log(trade_log_path)
    trade_log = trade_log[trade_log["strategy"] == args.strategy].copy()
    groups = _parse_optional_csv(args.group)
    tf_pairs = _parse_optional_csv(args.tf_pair)
    if groups:
        trade_log = trade_log[trade_log["Group"].isin(groups)].copy()
    if tf_pairs:
        trade_log = trade_log[trade_log["TFPair"].isin(tf_pairs)].copy()
    if trade_log.empty:
        raise ValueError("No hay trades tras aplicar filtros.")

    risk_per_trade = float(args.risk_per_trade_pct) / 100.0
    setups = _prepare_setups(trade_log, float(args.initial_capital), risk_per_trade, args.risk_mode)
    accepted_frames = []
    rejected_frames = []
    exposure_frames = []
    block_group_cols = ["strategy", "source_family", "Group", "timeframe_ltf", "timeframe_htf"]
    for _, block in trade_log.groupby(block_group_cols, dropna=False, sort=True):
        block_setups = [
            setup for setup in setups
            if (
                setup["strategy"] == str(block["strategy"].iloc[0])
                and setup["group"] == str(block["Group"].iloc[0])
                and setup["ltf"] == str(block["timeframe_ltf"].iloc[0])
                and setup["htf"] == str(block["timeframe_htf"].iloc[0])
            )
        ]
        accepted, rejected, exposure, _ = _simulate_block(block_setups, args)
        if not accepted.empty:
            accepted_frames.append(accepted)
        if not rejected.empty:
            rejected_frames.append(rejected)
        if not exposure.empty:
            exposure["strategy"] = str(block["strategy"].iloc[0])
            exposure["Group"] = str(block["Group"].iloc[0])
            exposure["TFPair"] = _tf_pair(block["timeframe_ltf"].iloc[0], block["timeframe_htf"].iloc[0])
            exposure["BlockId"] = str(block["BlockId"].iloc[0])
            exposure_frames.append(exposure)

    accepted_all = pd.concat(accepted_frames, ignore_index=True) if accepted_frames else pd.DataFrame()
    rejected_all = pd.concat(rejected_frames, ignore_index=True) if rejected_frames else pd.DataFrame()
    exposure_all = pd.concat(exposure_frames, ignore_index=True) if exposure_frames else pd.DataFrame()
    original_metrics = _original_block_metrics(trade_log, float(args.initial_capital))
    riskguard_metrics = _block_metrics(accepted_all, rejected_all, trade_log, float(args.initial_capital))
    comparison = _comparison(original_metrics, riskguard_metrics)
    rejection_summary = _rejection_summary(rejected_all)
    extreme = _extreme_summary(comparison, rejected_all, exposure_all)

    accepted_all.to_csv(tables_dir / "accepted_trades.csv", index=False)
    rejected_all.to_csv(tables_dir / "rejected_setups.csv", index=False)
    riskguard_metrics.to_csv(tables_dir / "block_metrics_riskguard.csv", index=False)
    comparison.to_csv(tables_dir / "comparison_vs_original.csv", index=False)
    exposure_all.to_csv(tables_dir / "currency_exposure_max.csv", index=False)
    extreme.to_csv(tables_dir / "extreme_block_summary.csv", index=False)
    rejection_summary.to_csv(tables_dir / "rejection_summary.csv", index=False)

    command = (
        "python -m backtests.benchmarks.run_enbolsa_riskguard_audit "
        f"--trade-log {args.trade_log} --output-dir {args.output_dir} "
        f"--strategy {args.strategy} --max-total-open-risk-pct {args.max_total_open_risk_pct:g} "
        f"--max-symbol-open-risk-pct {args.max_symbol_open_risk_pct:g} "
        f"--max-currency-gross-risk-pct {args.max_currency_gross_risk_pct:g} "
        f"--max-currency-net-risk-pct {args.max_currency_net_risk_pct:g} "
        f"--initial-capital {args.initial_capital:g} --risk-mode {args.risk_mode} "
        f"--risk-per-trade-pct {args.risk_per_trade_pct:g}"
    )
    if args.group:
        command += f" --group {args.group}"
    if args.tf_pair:
        command += f" --tf-pair {args.tf_pair}"
    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "trade_log": str(trade_log_path),
        "output_dir": str(output_dir),
        "strategy": args.strategy,
        "initial_capital": float(args.initial_capital),
        "risk_mode": args.risk_mode,
        "risk_per_trade_pct": float(args.risk_per_trade_pct),
        "max_total_open_risk_pct": float(args.max_total_open_risk_pct),
        "max_symbol_open_risk_pct": float(args.max_symbol_open_risk_pct),
        "max_currency_gross_risk_pct": float(args.max_currency_gross_risk_pct),
        "max_currency_net_risk_pct": float(args.max_currency_net_risk_pct),
        "group": args.group,
        "tf_pair": args.tf_pair,
        "input_trades": int(len(trade_log)),
        "accepted_trades": int(len(accepted_all)),
        "rejected_setups": int(len(rejected_all)),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    _write_report(output_dir, run_meta, comparison, extreme, rejection_summary, exposure_all)
    print(f"Artifacts escritos en: {output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auditoria post-proceso RiskGuard para ENBOLSA.")
    parser.add_argument("--trade-log", default=str(DEFAULT_TRADE_LOG))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY)
    parser.add_argument("--max-total-open-risk-pct", type=float, default=5.0)
    parser.add_argument("--max-symbol-open-risk-pct", type=float, default=1.0)
    parser.add_argument("--max-currency-gross-risk-pct", type=float, default=3.0)
    parser.add_argument("--max-currency-net-risk-pct", type=float, default=3.0)
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--risk-mode", choices=("fixed_initial", "observed"), default="fixed_initial")
    parser.add_argument("--risk-per-trade-pct", type=float, default=DEFAULT_RISK_PER_TRADE_PCT)
    parser.add_argument("--group", default="")
    parser.add_argument("--tf-pair", default="")
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())

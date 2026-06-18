from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.enbolsa import live_signal_watcher

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/live-signal-watcher/enbolsa_macd_breakout_h1_h4_h4_d1_current_v0"
DEFAULT_TF_PAIRS = "H1:H4,H4:D1"


def parse_tf_pairs(value: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in str(value or "").split(","):
        text = item.strip()
        if not text:
            continue
        if ":" not in text:
            raise ValueError(f"Invalid timeframe pair '{text}'. Expected LTF:HTF.")
        ltf, htf = [part.strip().upper() for part in text.split(":", 1)]
        if not ltf or not htf:
            raise ValueError(f"Invalid timeframe pair '{text}'. Expected LTF:HTF.")
        pairs.append((ltf, htf))
    if not pairs:
        raise ValueError("At least one timeframe pair is required.")
    return pairs


def _resolve(path: str | Path) -> Path:
    result = Path(path)
    return result if result.is_absolute() else REPO_ROOT / result


def _watcher_args(args: argparse.Namespace, ltf: str, htf: str, pair_dir: Path) -> argparse.Namespace:
    watcher_args = live_signal_watcher.build_parser().parse_args(
        [
            "--mode",
            "snapshot",
            "--groups",
            args.groups,
            "--timeframe-ltf",
            ltf,
            "--timeframe-htf",
            htf,
            "--output-dir",
            str(pair_dir),
            "--lookback-bars",
            str(args.lookback_bars),
            "--confirmation-memory-bars",
            str(args.confirmation_memory_bars),
            "--initial-capital",
            str(args.initial_capital),
            "--risk-per-trade-pct",
            str(args.risk_per_trade_pct),
            "--max-total-open-risk-pct",
            str(args.max_total_open_risk_pct),
            "--max-symbol-open-risk-pct",
            str(args.max_symbol_open_risk_pct),
            "--max-currency-gross-risk-pct",
            str(args.max_currency_gross_risk_pct),
            "--max-currency-net-risk-pct",
            str(args.max_currency_net_risk_pct),
        ]
    )
    watcher_args.no_cache = bool(args.no_cache)
    watcher_args.force_rebuild = bool(args.force_rebuild)
    watcher_args.no_disk_cache = bool(args.no_disk_cache)
    watcher_args.verbose = bool(args.verbose)
    return watcher_args


def _combine_frames(results: list[dict[str, pd.DataFrame]], key: str) -> pd.DataFrame:
    frames = [result.get(key, pd.DataFrame()) for result in results]
    non_empty = [frame for frame in frames if frame is not None and not frame.empty]
    if non_empty:
        return pd.concat(non_empty, ignore_index=True, sort=False)
    return frames[0].copy() if frames else pd.DataFrame()


def execute(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = _resolve(args.output_dir)
    pairs = parse_tf_pairs(args.tf_pairs)
    pairs_root = output_dir / "pairs"
    generated_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, pd.DataFrame]] = []
    pair_rows: list[dict[str, Any]] = []

    for ltf, htf in pairs:
        pair_dir = pairs_root / f"{ltf.lower()}_{htf.lower()}"
        watcher_args = _watcher_args(args, ltf, htf, pair_dir)
        result = live_signal_watcher.run_snapshot_once(watcher_args)
        results.append(result)
        pair_rows.append(
            {
                "timeframe_ltf": ltf,
                "timeframe_htf": htf,
                "output_dir": str(pair_dir),
                "snapshot_rows": int(len(result.get("snapshot", []))),
                "watchlist_rows": int(len(result.get("watchlist", []))),
                "order_intents_rows": int(len(result.get("order_intents", []))),
                "riskguard_decisions_rows": int(len(result.get("riskguard_decisions", []))),
                "status": "generated",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    combined = {
        "snapshot": _combine_frames(results, "snapshot"),
        "watchlist": _combine_frames(results, "watchlist"),
        "order_intents": _combine_frames(results, "order_intents"),
        "riskguard_decisions": _combine_frames(results, "riskguard_decisions"),
    }
    for name, frame in combined.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)

    pd.DataFrame(pair_rows).to_csv(output_dir / "pair_generation_audit.csv", index=False)
    run_meta = {
        "generated_at": generated_at,
        "module": "macd_breakout_watcher_combined_v1",
        "strategy": "macd_breakout",
        "groups": [item.strip() for item in str(args.groups).split(",") if item.strip()],
        "tf_pairs": [f"{ltf}:{htf}" for ltf, htf in pairs],
        "snapshot_rows": int(len(combined["snapshot"])),
        "watchlist_rows": int(len(combined["watchlist"])),
        "order_intents_rows": int(len(combined["order_intents"])),
        "riskguard_decisions_rows": int(len(combined["riskguard_decisions"])),
        "is_signal": False,
        "can_execute_order": False,
        "orders_sent": 0,
        "mt5_connected": False,
        "telegram_connected": False,
        "sql_real_written": False,
        "backtests_executed": False,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"combined": combined, "pair_rows": pair_rows, "run_meta": run_meta}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Combined artifact-first macd_breakout watcher for H1/H4 and H4/D1.")
    parser.add_argument("--groups", default="Forex Majors,Metals,Index")
    parser.add_argument("--tf-pairs", default=DEFAULT_TF_PAIRS)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--lookback-bars", type=int, default=1)
    parser.add_argument("--confirmation-memory-bars", type=int, default=5)
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--risk-per-trade-pct", type=float, default=1.0)
    parser.add_argument("--max-total-open-risk-pct", type=float, default=5.0)
    parser.add_argument("--max-symbol-open-risk-pct", type=float, default=1.0)
    parser.add_argument("--max-currency-gross-risk-pct", type=float, default=3.0)
    parser.add_argument("--max-currency-net-risk-pct", type=float, default=3.0)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--no-disk-cache", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> None:
    result = execute(build_parser().parse_args())
    meta = result["run_meta"]
    print(f"snapshot={meta['snapshot_rows']} watchlist={meta['watchlist_rows']} tf_pairs={','.join(meta['tf_pairs'])}")


if __name__ == "__main__":
    main()

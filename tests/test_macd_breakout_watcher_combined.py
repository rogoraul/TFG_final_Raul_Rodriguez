from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from trading_center import macd_breakout_watcher_combined as combined


def test_combined_watcher_merges_h1_and_h4_outputs(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_run_snapshot_once(args):
        calls.append((args.timeframe_ltf, args.timeframe_htf))
        return {
            "snapshot": pd.DataFrame(
                [
                    {
                        "Group": "Forex Majors",
                        "strategy": "enbolsa:macd_breakout",
                        "symbol": f"EURUSD_{args.timeframe_ltf}",
                        "timeframe_ltf": args.timeframe_ltf,
                        "timeframe_htf": args.timeframe_htf,
                    }
                ]
            ),
            "watchlist": pd.DataFrame(columns=["strategy", "symbol", "timeframe_ltf", "timeframe_htf"]),
            "order_intents": pd.DataFrame(columns=["event_key", "symbol", "timeframe_ltf", "timeframe_htf"]),
            "riskguard_decisions": pd.DataFrame(columns=["accepted", "symbol", "timeframe_ltf", "timeframe_htf"]),
        }

    monkeypatch.setattr(combined.live_signal_watcher, "run_snapshot_once", fake_run_snapshot_once)
    out = tmp_path / "combined"

    result = combined.execute(
        combined.build_parser().parse_args(
            [
                "--output-dir",
                str(out),
                "--groups",
                "Forex Majors,Metals,Index",
                "--tf-pairs",
                "H1:H4,H4:D1",
            ]
        )
    )

    snapshot = pd.read_csv(out / "snapshot.csv")
    pair_audit = pd.read_csv(out / "pair_generation_audit.csv")
    run_meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))

    assert calls == [("H1", "H4"), ("H4", "D1")]
    assert set(snapshot["timeframe_ltf"]) == {"H1", "H4"}
    assert set(pair_audit["timeframe_ltf"]) == {"H1", "H4"}
    assert result["run_meta"]["snapshot_rows"] == 2
    assert run_meta["can_execute_order"] is False
    assert run_meta["orders_sent"] == 0
    assert run_meta["mt5_connected"] is False

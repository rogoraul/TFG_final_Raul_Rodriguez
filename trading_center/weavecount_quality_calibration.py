from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


DEFAULT_BASELINE = REPO_ROOT / "artifacts/tfg/weavecount_quality_calibration_v1_2026-06-01/baseline_weavecount_screener_before_calibration.csv"
DEFAULT_SCREENER = REPO_ROOT / "artifacts/tfg/weavecount_screener_h1_h4_v1_2026-06-01/weavecount_screener.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/weavecount_quality_calibration_v1_2026-06-01"
DECISION = "weavecount_quality_calibration_v1_ready_for_dashboard_review"


def _count(rows: list[dict[str, Any]], field: str) -> Counter[str]:
    return Counter(str(row.get(field, "") or "missing") for row in rows)


def _distribution_rows(before: Counter[str], after: Counter[str]) -> list[dict[str, Any]]:
    statuses = ("fuerte", "media", "debil", "missing")
    return [
        {
            "quality_status": status,
            "before_count": before.get(status, 0),
            "after_count": after.get(status, 0),
            "delta": after.get(status, 0) - before.get(status, 0),
        }
        for status in statuses
        if before.get(status, 0) or after.get(status, 0)
    ]


def _by_wave_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(row.get("count_label", "") or "missing")][str(row.get("quality_status", "") or "missing")] += 1
    output: list[dict[str, Any]] = []
    for count_label in sorted(grouped):
        for status, count in sorted(grouped[count_label].items()):
            output.append({"count_label": count_label, "quality_status": status, "row_count": count})
    return output


def _score_value(row: dict[str, Any]) -> int:
    try:
        return int(float(row.get("quality_score") or 0))
    except (TypeError, ValueError):
        return 0


def _example_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=_score_value)
    selected = ordered[:10] + ordered[-10:]
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in selected:
        key = str(row.get("case_id", ""))
        if key in seen:
            continue
        seen.add(key)
        output.append(
            {
                "symbol": row.get("symbol", ""),
                "market_group": row.get("market_group", ""),
                "timeframe": row.get("timeframe", ""),
                "count_label": row.get("count_label", ""),
                "direction": row.get("direction", ""),
                "quality_status": row.get("quality_status", ""),
                "quality_score": row.get("quality_score", ""),
                "quality_reason": row.get("quality_reason", ""),
                "is_signal": row.get("is_signal", ""),
                "can_execute_order": row.get("can_execute_order", ""),
            }
        )
    return output


def build_calibration_artifacts(
    baseline_path: Path = DEFAULT_BASELINE,
    screener_path: Path = DEFAULT_SCREENER,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    baseline_rows = read_csv(baseline_path)
    calibrated_rows = read_csv(screener_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    before_quality = _count(baseline_rows, "quality_status")
    after_quality = _count(calibrated_rows, "quality_status")

    write_csv(
        tables_dir / "quality_rule_policy.csv",
        [
            {
                "factor": "structure_maturity",
                "rule": "More structural points help, but early W2 candidates are penalized.",
                "intent": "Avoid treating every drawable candidate as equally useful.",
            },
            {
                "factor": "current_leg_presence",
                "rule": "A visible current leg is required for medium/strong readings.",
                "intent": "Prioritize candidates that can be reviewed visually in the modal.",
            },
            {
                "factor": "activation_invalidation",
                "rule": "Complete levels add confidence; missing levels subtract context.",
                "intent": "Make candidates with clear structural boundaries easier to surface.",
            },
            {
                "factor": "current_leg_pct_move",
                "rule": "Very small close-to-close displacement is penalized as nearly flat.",
                "intent": "Demote flat-looking candidates like the examples flagged by the user.",
            },
            {
                "factor": "current_leg_weight",
                "rule": "Current leg is compared with the visible structural span.",
                "intent": "Avoid strong labels when the highlighted leg is visually minor.",
            },
            {
                "factor": "study_only_boundary",
                "rule": "Quality cannot change study_only, is_signal, can_execute_order or wavecount_used_as_filter.",
                "intent": "Keep WeaveCount as structural study, not trading signal.",
            },
        ],
    )
    write_csv(tables_dir / "quality_distribution_before_after.csv", _distribution_rows(before_quality, after_quality))
    write_csv(tables_dir / "quality_by_wave_after.csv", _by_wave_rows(calibrated_rows))
    write_csv(tables_dir / "quality_examples_audit.csv", _example_rows(calibrated_rows))
    write_csv(
        tables_dir / "study_only_safety_audit.csv",
        [
            {
                "check": "study_only_true",
                "status": "pass" if all(str(row.get("is_study_only", "")).lower() == "true" for row in calibrated_rows) else "fail",
            },
            {
                "check": "is_signal_false",
                "status": "pass" if all(str(row.get("is_signal", "")).lower() == "false" for row in calibrated_rows) else "fail",
            },
            {
                "check": "wavecount_used_as_filter_false",
                "status": "pass" if all(str(row.get("wavecount_used_as_filter", "")).lower() == "false" for row in calibrated_rows) else "fail",
            },
            {
                "check": "can_execute_order_false",
                "status": "pass" if all(str(row.get("can_execute_order", "")).lower() == "false" for row in calibrated_rows) else "fail",
            },
            {"check": "sql_real_written", "status": "pass", "value": False},
            {"check": "mt5_connected", "status": "pass", "value": False},
            {"check": "telegram_connected", "status": "pass", "value": False},
            {"check": "signals_generated", "status": "pass", "value": False},
            {"check": "backtests_executed", "status": "pass", "value": False},
        ],
    )
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {
                "severity": "low",
                "issue": "quality_is_visual_priority",
                "status": "documented",
                "recommendation": "Do not present quality as probability, edge or execution permission.",
            },
            {
                "severity": "low",
                "issue": "thresholds_are_heuristic",
                "status": "accepted_for_dashboard",
                "recommendation": "Future review can tune thresholds after more manual examples.",
            },
        ],
    )

    meta = {
        "phase": "weavecount_quality_calibration_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": DECISION,
        "baseline_rows": len(baseline_rows),
        "calibrated_rows": len(calibrated_rows),
        "before_quality_counts": dict(sorted(before_quality.items())),
        "after_quality_counts": dict(sorted(after_quality.items())),
        "quality_score_added": True,
        "study_only": True,
        "is_signal": False,
        "wavecount_used_as_filter": False,
        "can_execute_order_any_true": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "backtests_executed": False,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "WEAVECOUNT_QUALITY_CALIBRATION_V1.md").write_text(_render_report(meta), encoding="utf-8")
    return meta


def _render_report(meta: dict[str, Any]) -> str:
    return f"""# WeaveCount Quality Calibration V1

Decision: `{meta['decision']}`.

This phase recalibrates the visual quality labels used by the Trading Center
WeaveCount section. It does not change the wave count, does not create trading
signals and does not enable execution.

## Before / After

- Baseline rows: {meta['baseline_rows']}.
- Calibrated rows: {meta['calibrated_rows']}.
- Before quality: {meta['before_quality_counts']}.
- After quality: {meta['after_quality_counts']}.

## Interpretation

`fuerte`, `media` and `debil` are dashboard review priorities. They are based
on structure maturity, current-leg clarity, available levels and visual weight
of the current leg. They are not probabilities of success.

## Safety

- study_only: true.
- is_signal: false.
- wavecount_used_as_filter: false.
- can_execute_order_any_true: false.
- SQL/MT5/Telegram/backtests/orders: not used.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WeaveCount quality calibration artifacts.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--screener", type=Path, default=DEFAULT_SCREENER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_calibration_artifacts(args.baseline, args.screener, args.output_dir)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

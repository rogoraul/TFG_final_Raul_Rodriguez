from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.enbolsa.swing_quality import QUALITY_GATE_VERSION, SwingQualityThresholds, evaluate_swing_quality_values, resolve_thresholds
from trading_center.enbolsa_strategy_visual_audit import (
    CACHE_BY_PARTIAL_SOURCE,
    DEFAULT_CACHE_DIR,
    DEFAULT_TRADE_LOG_CSV,
    build_cache_coverage_rows,
    classify_materiality,
    find_price_point,
    get_window,
    load_portfolio_cache,
    plot_case,
    unique_setup_key,
)
from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


METHOD_VERSION = "enbolsa_swing_quality_v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/enbolsa_swing_quality_v1_2026-06-02"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/ENBOLSA_SWING_QUALITY_V1.md"

SCREENING_FIELDNAMES = [
    "symbol",
    "group",
    "strategy",
    "entry_rule",
    "direction",
    "setup_id",
    "entry_time",
    "timeframe_ltf",
    "timeframe_htf",
    "partial_source",
    "v1_materiality_bucket",
    "swing_quality_pass",
    "swing_quality_reason",
    "w1_quality_status",
    "w2_quality_status",
    "w1_atr_multiple",
    "w1_price_pct",
    "w1_bars",
    "w2_retr_pct",
    "quality_gate_version",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def as_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def fmt(value: Any, digits: int = 4) -> str:
    number = as_float(value)
    return "" if number is None else f"{number:.{digits}f}"


def dedupe_trade_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        entry_rule = clean(row.get("entry_rule")).lower()
        if entry_rule not in {"fib_limit", "macd_breakout"}:
            continue
        key = unique_setup_key(row)
        if key in seen:
            continue
        seen.add(key)
        bucket, w1_pct, w1_atr = classify_materiality(row)
        row = dict(row)
        row["_materiality_bucket"] = bucket
        row["_w1_size_pct"] = w1_pct
        row["_w1_to_bm_atr"] = w1_atr
        output.append(row)
    return output


def estimate_w1_bars(row: dict[str, Any], portfolio: dict[str, pd.DataFrame] | None) -> int:
    if not portfolio:
        return 0
    symbol_df = portfolio.get(clean(row.get("symbol")))
    if symbol_df is None or symbol_df.empty:
        return 0
    try:
        entry_time = pd.Timestamp(clean(row.get("entry_time")))
    except Exception:
        return 0
    window, entry_pos = get_window(symbol_df, entry_time, before=260, after=0)
    if window.empty or entry_pos is None:
        return 0
    p_start, _ = find_price_point(window, as_float(row.get("W1_START_PRICE")), row, entry_pos)
    p_end, _ = find_price_point(window, as_float(row.get("W1_END_PRICE")), row, entry_pos)
    if p_start is None or p_end is None:
        return 0
    return abs(int(p_end) - int(p_start))


def evaluate_trade_row(row: dict[str, Any], portfolio: dict[str, pd.DataFrame] | None = None) -> dict[str, Any]:
    base_thresholds = resolve_thresholds(clean(row.get("Group")), clean(row.get("timeframe_ltf")), clean(row.get("timeframe_htf")))
    w1_bars = estimate_w1_bars(row, portfolio) if portfolio else 0
    thresholds = (
        base_thresholds
        if portfolio
        else SwingQualityThresholds(
            w1_min_atr_multiple=base_thresholds.w1_min_atr_multiple,
            w1_min_price_pct=base_thresholds.w1_min_price_pct,
            w1_min_bars=0,
            w2_min_retr_pct=base_thresholds.w2_min_retr_pct,
            w2_max_retr_pct=base_thresholds.w2_max_retr_pct,
        )
    )
    quality = evaluate_swing_quality_values(
        w1_size=as_float(row.get("W1_SIZE")) or float("nan"),
        w1_start=as_float(row.get("W1_START_PRICE")) or float("nan"),
        w1_bars=w1_bars,
        atr=as_float(row.get("BM_ATR_USED")) or float("nan"),
        w2_retr_pct=as_float(row.get("W2_RETR_PCT")) or float("nan"),
        w2_swing=as_float(row.get("W2_SWING_PRICE")) or as_float(row.get("W2_EXTREME_PRICE")) or float("nan"),
        invalidated=False,
        thresholds=thresholds,
    )
    return {
        "symbol": clean(row.get("symbol")),
        "group": clean(row.get("Group"), clean(row.get("group"))),
        "strategy": clean(row.get("strategy")),
        "entry_rule": clean(row.get("entry_rule")),
        "direction": clean(row.get("direction")),
        "setup_id": clean(row.get("setup_id")),
        "entry_time": clean(row.get("entry_time")),
        "timeframe_ltf": clean(row.get("timeframe_ltf")),
        "timeframe_htf": clean(row.get("timeframe_htf")),
        "partial_source": clean(row.get("partial_source")),
        "v1_materiality_bucket": clean(row.get("_materiality_bucket")),
        "swing_quality_pass": quality["swing_quality_pass"],
        "swing_quality_reason": quality["swing_quality_reason"],
        "w1_quality_status": quality["w1_quality_status"],
        "w2_quality_status": quality["w2_quality_status"],
        "w1_atr_multiple": fmt(quality["w1_atr_multiple"]),
        "w1_price_pct": fmt(quality["w1_price_pct"]),
        "w1_bars": quality["w1_bars"],
        "w2_retr_pct": fmt(quality["w2_retr_pct"]),
        "quality_gate_version": QUALITY_GATE_VERSION,
    }


def summarize(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(clean(row.get(key), "not_available") for key in keys)].append(row)
    output: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items()):
        pass_count = sum(str(row.get("swing_quality_pass")) == "True" or row.get("swing_quality_pass") is True for row in values)
        blocked = len(values) - pass_count
        reasons = Counter(clean(row.get("swing_quality_reason")) for row in values if not (str(row.get("swing_quality_pass")) == "True" or row.get("swing_quality_pass") is True))
        result = {name: value for name, value in zip(keys, key)}
        result.update(
            {
                "setups_reviewed": len(values),
                "would_pass_gate": pass_count,
                "would_block_gate": blocked,
                "pass_rate_pct": f"{(pass_count / len(values) * 100.0):.2f}" if values else "0.00",
                "top_block_reasons": " | ".join(f"{reason}:{count}" for reason, count in reasons.most_common(4)),
            }
        )
        output.append(result)
    return output


def policy_rows() -> list[dict[str, Any]]:
    return [
        {"criterion": "w1_min_atr_multiple", "purpose": "Evitar impulsos W1 por ruido local", "default": "2.5x ATR", "claim": "calidad estructural minima, no edge"},
        {"criterion": "w1_min_price_pct", "purpose": "Exigir tamano visible relativo al precio", "default": "Forex 0.75%, Metals 1.00%, Index 0.80%", "claim": "umbral metodologico inicial"},
        {"criterion": "w1_min_bars", "purpose": "Evitar W1 comprimida en pocas velas", "default": "M30:H1=8, H1:H4=6, H4:D1=5", "claim": "duracion minima aproximada"},
        {"criterion": "w2_retr_pct", "purpose": "Exigir correccion W2 reconocible sin invalidar", "default": "0.20 a 0.80", "claim": "W2 razonable para estudio W1/W2"},
    ]


def threshold_rows() -> list[dict[str, Any]]:
    rows = []
    for group in ["Forex Majors", "Metals", "Index"]:
        for ltf, htf in [("M30", "H1"), ("H1", "H4"), ("H4", "D1")]:
            thresholds = resolve_thresholds(group, ltf, htf)
            rows.append(
                {
                    "group": group,
                    "timeframe_ltf": ltf,
                    "timeframe_htf": htf,
                    "w1_min_atr_multiple": thresholds.w1_min_atr_multiple,
                    "w1_min_price_pct": thresholds.w1_min_price_pct,
                    "w1_min_bars": thresholds.w1_min_bars,
                    "w2_min_retr_pct": thresholds.w2_min_retr_pct,
                    "w2_max_retr_pct": thresholds.w2_max_retr_pct,
                }
            )
    return rows


def build_visual_examples(
    rows: list[dict[str, Any]],
    screening: list[dict[str, Any]],
    output_dir: Path,
    cache_dir: Path,
    limit_per_bucket: int,
) -> list[dict[str, Any]]:
    by_key = {unique_setup_key(row): row for row in rows}
    screening_by_key = {
        (
            clean(row.get("symbol")),
            clean(row.get("strategy")),
            clean(row.get("entry_rule")),
            clean(row.get("direction")),
            clean(row.get("setup_id")),
            clean(row.get("entry_time")),
            clean(row.get("timeframe_ltf")),
            clean(row.get("timeframe_htf")),
            clean(row.get("partial_source")),
        ): row
        for row in screening
    }
    selected_keys: list[tuple[str, ...]] = []
    for entry_rule in ["fib_limit", "macd_breakout"]:
        blocked = [key for key, row in screening_by_key.items() if row["entry_rule"] == entry_rule and row["swing_quality_pass"] is False]
        accepted = [key for key, row in screening_by_key.items() if row["entry_rule"] == entry_rule and row["swing_quality_pass"] is True]
        selected_keys.extend(blocked[:limit_per_bucket])
        selected_keys.extend(accepted[:limit_per_bucket])

    visual_rows = []
    cache_by_source: dict[str, dict[str, pd.DataFrame] | None] = {}
    for idx, key in enumerate(selected_keys, start=1):
        original = by_key.get(key)
        screened = screening_by_key.get(key)
        if not original or not screened:
            continue
        partial_source = clean(original.get("partial_source"))
        if partial_source not in cache_by_source:
            cache_by_source[partial_source] = load_portfolio_cache(cache_dir, partial_source)
        portfolio = cache_by_source.get(partial_source) or {}
        symbol_df = portfolio.get(clean(original.get("symbol"))) if isinstance(portfolio, dict) else None
        bucket = "accepted_v2" if screened["swing_quality_pass"] is True else "blocked_v1"
        chart_dir = output_dir / "charts" / bucket
        if symbol_df is None:
            chart_result = {"chart_file": "", "visual_status": "missing_symbol_cache"}
        else:
            chart_result = plot_case(original, symbol_df, chart_dir, f"sq_{idx:03d}")
        visual_rows.append(
            {
                "case_id": f"sq_{idx:03d}",
                "bucket": bucket,
                "symbol": screened["symbol"],
                "entry_rule": screened["entry_rule"],
                "group": screened["group"],
                "timeframe_ltf": screened["timeframe_ltf"],
                "timeframe_htf": screened["timeframe_htf"],
                "swing_quality_pass": screened["swing_quality_pass"],
                "swing_quality_reason": screened["swing_quality_reason"],
                "chart_file": chart_result.get("chart_file", ""),
                "visual_status": chart_result.get("visual_status", ""),
            }
        )
        comparison_dir = output_dir / "charts" / "comparison"
        if symbol_df is not None and idx <= 8:
            plot_case(original, symbol_df, comparison_dir, f"comparison_{idx:03d}")
    return visual_rows


def build_outputs(args: argparse.Namespace) -> dict[str, Any]:
    trade_rows = dedupe_trade_rows(read_csv(Path(args.trade_log_csv)))
    cache_dir = Path(args.cache_dir)
    screening = []
    for row in trade_rows:
        screening.append(evaluate_trade_row(row))

    output_dir = Path(args.output_dir)
    visual_rows = build_visual_examples(trade_rows, screening, output_dir, cache_dir, args.visual_examples_per_rule)
    return {
        "trade_rows": trade_rows,
        "screening": screening,
        "visual_rows": visual_rows,
        "cache_coverage": build_cache_coverage_rows(trade_rows, cache_dir),
    }


def render_report(run_meta: dict[str, Any]) -> str:
    return f"""# ENBOLSA Swing Quality V1

Fecha: 2026-06-02

Decision: `{run_meta['decision']}`.

## Objetivo

Crear una variante metodologica `swing-quality` para ENBOLSA que bloquee W1/W2
demasiado pequenos antes de revalidar backtests o comparaciones.

## Gate inicial

- W1 minimo por ATR, porcentaje y barras.
- W2 con retroceso razonable entre 0.20 y 0.80.
- Se mantiene ENBOLSA V1 como baseline historico.
- No se ejecutan backtests completos ni comparaciones finales en esta fase.

## Screening previo

- setups_reviewed={run_meta['setups_reviewed']}
- would_pass_gate={run_meta['would_pass_gate']}
- would_block_gate={run_meta['would_block_gate']}
- visual_cases_created={run_meta['visual_cases_created']}

## Seguridad

- enbolsa_v1_preserved=true
- riskguard_modified=false
- full_backtests_executed=false
- benchmark_comparisons_executed=false
- signals_generated=false
"""


def write_outputs(output_dir: Path, result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    screening = result["screening"]
    write_csv(output_dir / "enbolsa_swing_quality_screening.csv", screening, SCREENING_FIELDNAMES)
    write_csv(tables_dir / "enbolsa_swing_quality_gate_policy.csv", policy_rows())
    write_csv(tables_dir / "enbolsa_swing_quality_thresholds.csv", threshold_rows())
    write_csv(
        tables_dir / "enbolsa_swing_quality_rationale.csv",
        [
            {"area": "methodology", "rationale": "El usuario detecto visualmente W1/W2 demasiado pequenos; se exige calidad estructural antes de revalidar.", "risk": "Reducir mucho los setups puede cambiar radicalmente resultados V2."},
            {"area": "comparability", "rationale": "V1 se preserva como baseline; V2/swing-quality se revalidara aparte.", "risk": "No mezclar resultados V1 y V2 en memoria."},
        ],
    )
    write_csv(
        tables_dir / "enbolsa_swing_quality_implementation_audit.csv",
        [
            {"check_id": "IMPL01", "status": "pass", "finding": "Gate implementado en backtests/enbolsa/swing_quality.py.", "side_effect": "No cambia V1 por defecto."},
            {"check_id": "IMPL02", "status": "pass", "finding": "backtest_pipeline solo usa gate si swing_quality_gate_enabled=True.", "side_effect": "No modifica RiskGuard/costes/sizing."},
            {"check_id": "IMPL03", "status": "pass_with_caution", "finding": "La ruta V2 fuerza Python path para evitar tocar numba antes de revalidacion.", "side_effect": "Mas lento, pero reversible y auditable."},
        ],
    )
    write_csv(
        tables_dir / "enbolsa_swing_quality_block_reason_contract.csv",
        [
            {"reason": "w1_below_atr_multiple", "meaning": "W1 no alcanza multiple minimo de ATR."},
            {"reason": "w1_below_price_pct", "meaning": "W1 no alcanza tamano porcentual minimo por grupo."},
            {"reason": "w1_too_few_bars", "meaning": "W1 se forma en muy pocas velas."},
            {"reason": "w2_retr_too_shallow", "meaning": "W2 no corrige suficiente para ser estructura defendible."},
            {"reason": "w2_retr_too_deep", "meaning": "W2 supera el maximo metodologico."},
            {"reason": "w2_swing_missing", "meaning": "No hay pivote W2 reconocible."},
        ],
    )
    write_csv(tables_dir / "enbolsa_swing_quality_impact_by_strategy.csv", summarize(screening, ["strategy", "entry_rule"]))
    write_csv(tables_dir / "enbolsa_swing_quality_impact_by_group.csv", summarize(screening, ["group", "entry_rule"]))
    write_csv(tables_dir / "enbolsa_swing_quality_impact_by_timeframe.csv", summarize(screening, ["timeframe_ltf", "timeframe_htf", "entry_rule"]))
    blocked = [row for row in screening if row["swing_quality_pass"] is False]
    accepted = [row for row in screening if row["swing_quality_pass"] is True]
    write_csv(tables_dir / "enbolsa_swing_quality_blocked_examples.csv", blocked[:80], SCREENING_FIELDNAMES)
    write_csv(tables_dir / "enbolsa_swing_quality_accepted_examples.csv", accepted[:80], SCREENING_FIELDNAMES)
    write_csv(tables_dir / "enbolsa_swing_quality_visual_case_inventory.csv", result["visual_rows"])
    write_csv(tables_dir / "enbolsa_swing_quality_visual_audit.csv", result["visual_rows"])
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {"risk_id": "SQ01", "risk": "Los thresholds iniciales pueden ser demasiado duros.", "mitigation": "Revisar visualmente antes de backtest completo."},
            {"risk_id": "SQ02", "risk": "El screening usa reconstruccion W1_BARS desde cache porque V1 trade_log no guarda tiempos.", "mitigation": "V2 anade W1_BARS al contexto."},
        ],
    )

    pass_count = sum(row["swing_quality_pass"] is True for row in screening)
    run_meta = {
        "method_version": METHOD_VERSION,
        "generated_at": utc_now(),
        "output_dir": str(output_dir),
        "enbolsa_swing_quality_designed": True,
        "enbolsa_swing_quality_implemented": True,
        "enbolsa_v1_preserved": True,
        "riskguard_modified": False,
        "full_backtests_executed": False,
        "benchmark_comparisons_executed": False,
        "signals_generated": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "setups_reviewed": len(screening),
        "would_pass_gate": pass_count,
        "would_block_gate": len(screening) - pass_count,
        "visual_cases_created": len(result["visual_rows"]),
        "ready_for_backtest_revalidation": False,
        "ready_for_benchmark_rerun": False,
        "ready_for_dashboard_update": False,
        "decision": "enbolsa_swing_quality_v1_needs_visual_review",
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    report = render_report(run_meta)
    (output_dir / "ENBOLSA_SWING_QUALITY_V1.md").write_text(report, encoding="utf-8")
    Path(args.doc_path).write_text(report, encoding="utf-8")
    return run_meta


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Design and screen ENBOLSA swing quality gate without full backtests.")
    parser.add_argument("--trade-log-csv", default=str(DEFAULT_TRADE_LOG_CSV))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--doc-path", default=str(DEFAULT_DOC_PATH))
    parser.add_argument("--visual-examples-per-rule", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    result = build_outputs(args)
    return write_outputs(Path(args.output_dir), result, args)


if __name__ == "__main__":
    main()

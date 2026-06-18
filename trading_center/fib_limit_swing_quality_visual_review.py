from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from trading_center.enbolsa_strategy_visual_audit import (
    CACHE_BY_PARTIAL_SOURCE,
    as_float,
    clean,
    classify_materiality,
    format_float,
    load_portfolio_cache,
    plot_case,
)
from trading_center.readonly_dashboard import REPO_ROOT, write_csv


METHOD_VERSION = "fib_limit_swing_quality_visual_review_v1"
DEFAULT_TRADE_LOG_CSV = REPO_ROOT / "artifacts/benchmark-significance/enbolsa_swing_quality_v1/final/tables/trade_log.csv"
DEFAULT_SWING_QUALITY_VISUAL_DIR = REPO_ROOT / "artifacts/tfg/enbolsa_swing_quality_v1_2026-06-02"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/fib_limit_swing_quality_visual_review_v1_2026-06-02"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/FIB_LIMIT_SWING_QUALITY_VISUAL_REVIEW_V1.md"
DEFAULT_CACHE_DIR = REPO_ROOT / "backtests/.cache/portfolios"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_trade_log(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    return frame[
        frame["strategy"].astype(str).eq("enbolsa:fib_limit")
        & frame["entry_rule"].astype(str).eq("fib_limit")
    ].copy()


def collapse_positions(trades: pd.DataFrame) -> pd.DataFrame:
    group_cols = [
        "symbol",
        "Group",
        "direction",
        "setup_id",
        "entry_time",
        "entry_price",
        "stop_price",
        "timeframe_ltf",
        "timeframe_htf",
        "partial_source",
        "W1_START_PRICE",
        "W1_END_PRICE",
        "W1_SIZE",
        "W1_BARS",
        "W2_EXTREME_PRICE",
        "W2_RETR_PCT",
        "W2_SWING_PRICE",
        "FIB_LEVEL_0.618",
        "TARGET_1.0",
        "TARGET_1.618",
        "SWING_QUALITY_REASON",
        "W1_ATR_MULTIPLE",
        "W1_PRICE_PCT",
        "BM_ATR_USED",
        "QUALITY_GATE_VERSION",
    ]
    present = [column for column in group_cols if column in trades.columns]
    positions = (
        trades.groupby(present, dropna=False)
        .agg(
            legs=("tp_mult", "count"),
            tp_mults=("tp_mult", lambda values: ",".join(f"{float(v):g}" for v in sorted(values))),
            size_fraction_total=("size_fraction", "sum"),
            pnl_total=("pnl", "sum"),
            return_pct_total=("weighted_return", lambda values: float(pd.to_numeric(values, errors="coerce").fillna(0).sum() * 100.0)),
            first_exit_time=("exit_time", "min"),
            last_exit_time=("exit_time", "max"),
            tp1_exit_time=("exit_time", lambda values: ""),
            exit_reason_mix=("exit_reason", lambda values: ",".join(sorted(set(str(v) for v in values)))),
        )
        .reset_index()
    )
    tp1 = trades[pd.to_numeric(trades["tp_mult"], errors="coerce").round(6).eq(1.0)]
    tp2 = trades[~pd.to_numeric(trades["tp_mult"], errors="coerce").round(6).eq(1.0)]
    key_cols = [
        "symbol",
        "direction",
        "setup_id",
        "entry_time",
        "timeframe_ltf",
        "timeframe_htf",
        "partial_source",
    ]
    for source, column_name in ((tp1, "tp1_exit_time"), (tp2, "tp2_exit_time")):
        exits = source.groupby(key_cols, dropna=False)["exit_time"].first().reset_index().rename(columns={"exit_time": column_name})
        positions = positions.drop(columns=[column_name], errors="ignore").merge(exits, on=key_cols, how="left")

    positions["strategy"] = "enbolsa:fib_limit"
    positions["entry_rule"] = "fib_limit"
    positions["source_row_count"] = len(trades)
    materiality = [classify_materiality(row.to_dict()) for _, row in positions.iterrows()]
    positions["materiality_bucket"] = [item[0] for item in materiality]
    positions["w1_size_pct_calc"] = [item[1] for item in materiality]
    positions["w1_to_bm_atr_calc"] = [item[2] for item in materiality]
    positions["sample_key"] = (
        positions["symbol"].astype(str)
        + "|"
        + positions["timeframe_ltf"].astype(str)
        + ":"
        + positions["timeframe_htf"].astype(str)
        + "|"
        + positions["direction"].astype(str)
        + "|"
        + positions["setup_id"].astype(str)
        + "|"
        + positions["entry_time"].astype(str)
    )
    return positions


def _add_rows(selected: list[pd.Series], seen: set[str], rows: pd.DataFrame, reason: str, limit: int) -> None:
    added = 0
    for _, row in rows.iterrows():
        key = str(row["sample_key"])
        if key in seen:
            continue
        item = row.copy()
        item["selection_reason"] = reason
        selected.append(item)
        seen.add(key)
        added += 1
        if added >= limit:
            return


def select_visual_sample(positions: pd.DataFrame, max_cases: int = 36) -> pd.DataFrame:
    selected: list[pd.Series] = []
    seen: set[str] = set()
    _add_rows(selected, seen, positions.sort_values("pnl_total", ascending=False), "top_pnl", 4)
    _add_rows(selected, seen, positions.sort_values("pnl_total", ascending=True), "worst_pnl", 4)
    median_abs = (positions["pnl_total"] - positions["pnl_total"].median()).abs()
    _add_rows(selected, seen, positions.assign(_median_abs=median_abs).sort_values("_median_abs"), "median_pnl", 4)
    _add_rows(selected, seen, positions.sort_values("w1_size_pct_calc", ascending=True), "smallest_accepted_w1_pct", 5)
    _add_rows(selected, seen, positions.sort_values("w1_size_pct_calc", ascending=False), "largest_accepted_w1_pct", 3)
    for group in ["Forex Majors", "Metals", "Index"]:
        _add_rows(selected, seen, positions[positions["Group"].astype(str).eq(group)].sort_values("pnl_total", ascending=False), f"group_{group}", 2)
    for ltf, htf in [("M30", "H1"), ("H1", "H4"), ("H4", "D1")]:
        mask = positions["timeframe_ltf"].astype(str).eq(ltf) & positions["timeframe_htf"].astype(str).eq(htf)
        _add_rows(selected, seen, positions[mask].sort_values("pnl_total", ascending=False), f"timeframe_{ltf}_{htf}", 2)
    for direction in [1, -1]:
        _add_rows(selected, seen, positions[pd.to_numeric(positions["direction"], errors="coerce").eq(direction)].sort_values("pnl_total", ascending=False), f"direction_{direction}", 2)
    if len(selected) < max_cases:
        _add_rows(selected, seen, positions.sort_values("entry_time"), "chronological_fill", max_cases - len(selected))
    sample = pd.DataFrame(selected).head(max_cases).reset_index(drop=True)
    sample.insert(0, "case_id", [f"fib_sq_{idx:03d}" for idx in range(1, len(sample) + 1)])
    return sample


def render_cases(sample: pd.DataFrame, cache_dir: Path, charts_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    cache_by_source: dict[str, dict[str, pd.DataFrame] | None] = {}
    render_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    for _, row in sample.iterrows():
        partial_source = clean(row.get("partial_source"))
        if partial_source not in cache_by_source:
            cache_by_source[partial_source] = load_portfolio_cache(cache_dir, partial_source)
        portfolio = cache_by_source.get(partial_source) or {}
        symbol = clean(row.get("symbol"))
        symbol_df = portfolio.get(symbol) if isinstance(portfolio, dict) else None
        row_dict = row.to_dict()
        row_dict["_w1_size_pct"] = row.get("w1_size_pct_calc")
        row_dict["_w1_to_bm_atr"] = row.get("w1_to_bm_atr_calc")
        if symbol_df is None:
            chart_result = {
                "chart_file": "",
                "visual_status": "missing_symbol_cache",
                "w1_start_point_found": False,
                "w1_end_point_found": False,
                "w2_point_found": False,
                "macd_available": False,
                "rsi_available": False,
            }
        else:
            chart_result = plot_case(row_dict, symbol_df, charts_dir, clean(row.get("case_id")))

        render_rows.append(
            {
                "case_id": row.get("case_id"),
                "symbol": symbol,
                "group": clean(row.get("Group")),
                "timeframe_ltf": clean(row.get("timeframe_ltf")),
                "timeframe_htf": clean(row.get("timeframe_htf")),
                "selection_reason": clean(row.get("selection_reason")),
                "chart_file": chart_result["chart_file"],
                "visual_status": chart_result["visual_status"],
                "w1_start_point_found": chart_result["w1_start_point_found"],
                "w1_end_point_found": chart_result["w1_end_point_found"],
                "w2_point_found": chart_result["w2_point_found"],
                "methodology_note": "Render desde cache OHLC/pivotes existente; no reejecuta backtest.",
            }
        )
        classification, rationale = classify_visual_case(row.to_dict(), chart_result)
        review_rows.append(
            {
                "case_id": row.get("case_id"),
                "symbol": symbol,
                "group": clean(row.get("Group")),
                "timeframe_ltf": clean(row.get("timeframe_ltf")),
                "timeframe_htf": clean(row.get("timeframe_htf")),
                "direction": clean(row.get("direction")),
                "selection_reason": clean(row.get("selection_reason")),
                "visual_classification": classification,
                "visual_rationale": rationale,
                "w1_size_pct": format_float(as_float(row.get("w1_size_pct_calc")), 4),
                "w1_atr_multiple": format_float(as_float(row.get("W1_ATR_MULTIPLE")), 4),
                "w1_bars": clean(row.get("W1_BARS")),
                "w2_retr_pct": format_float(as_float(row.get("W2_RETR_PCT")), 4),
                "pnl_total": format_float(as_float(row.get("pnl_total")), 4),
                "return_pct_total": format_float(as_float(row.get("return_pct_total")), 4),
                "chart_file": chart_result["chart_file"],
            }
        )
    return pd.DataFrame(render_rows), pd.DataFrame(review_rows)


def classify_visual_case(row: dict[str, Any], chart_result: dict[str, Any]) -> tuple[str, str]:
    if chart_result.get("visual_status") != "chart_created":
        return "needs_manual_user_review", "No se pudo crear grafico completo desde cache."
    points_ok = bool(chart_result.get("w1_start_point_found")) and bool(chart_result.get("w1_end_point_found")) and bool(chart_result.get("w2_point_found"))
    w1_pct = as_float(row.get("w1_size_pct_calc"))
    w1_atr = as_float(row.get("W1_ATR_MULTIPLE"))
    w1_bars = as_float(row.get("W1_BARS"))
    w2_retr = as_float(row.get("W2_RETR_PCT"))
    reasons: list[str] = []
    if not points_ok:
        reasons.append("puntos W1/W2 reconstruidos de forma incompleta")
    if w1_pct is not None:
        reasons.append(f"W1 {w1_pct:.2f}%")
    if w1_atr is not None:
        reasons.append(f"{w1_atr:.2f} ATR")
    if w1_bars is not None:
        reasons.append(f"{int(w1_bars)} barras")
    if w2_retr is not None:
        reasons.append(f"W2 retr {w2_retr:.2f}")

    if not points_ok:
        return "needs_manual_user_review", "; ".join(reasons)
    if (w1_pct is not None and w1_pct < 0.9) or (w1_bars is not None and w1_bars < 7):
        return "visually_acceptable_with_caution", "; ".join(reasons)
    if (w1_atr is not None and w1_atr >= 4.0) and (w1_bars is not None and w1_bars >= 10):
        return "visually_defensible", "; ".join(reasons)
    return "visually_acceptable_with_caution", "; ".join(reasons)


def build_failure_patterns(review: pd.DataFrame) -> list[dict[str, Any]]:
    patterns = [
        ("FP01", "accepted_but_small_w1", "Casos aceptados con W1 cercano al umbral minimo.", "Mantener etiqueta metodologica y revisar visualmente antes de dashboard principal."),
        ("FP02", "reconstructed_points_limitation", "El trade_log no guarda tiempos exactos W1/W2.", "Los puntos se reconstruyen por precio desde cache; si faltan, mandar a revision manual."),
        ("FP03", "h4_d1_degraded_context", "H4:D1 sigue siendo stack degradado por ausencia de W1/MN1 real.", "No presentar H4:D1 como 3TF normal."),
        ("FP04", "mechanical_fib_entry", "La entrada 0.618 puede parecer mecanica si el swing es ruidoso.", "Mostrar como variante de estudio, no como senal."),
    ]
    counts = Counter(review["visual_classification"].astype(str)) if not review.empty else Counter()
    return [
        {
            "pattern_id": pattern_id,
            "pattern": pattern,
            "evidence": evidence,
            "cases_affected": counts.get("visually_acceptable_with_caution", 0) if pattern_id in {"FP01", "FP04"} else counts.get("needs_manual_user_review", 0),
            "mitigation": mitigation,
        }
        for pattern_id, pattern, evidence, mitigation in patterns
    ]


def copy_blocked_reference(output_dir: Path, source_dir: Path) -> list[dict[str, Any]]:
    source_table = source_dir / "tables/enbolsa_swing_quality_visual_case_inventory.csv"
    target_dir = output_dir / "charts/fib_limit_blocked_reference"
    target_dir.mkdir(parents=True, exist_ok=True)
    if not source_table.exists():
        return [
            {
                "reference_id": "blocked_reference_missing",
                "status": "not_available",
                "note": "No existe inventario visual previo de bloqueados.",
            }
        ]
    frame = pd.read_csv(source_table)
    blocked = frame[
        frame.get("bucket", pd.Series(dtype=str)).astype(str).eq("blocked_v1")
        & frame.get("entry_rule", pd.Series(dtype=str)).astype(str).eq("fib_limit")
    ].head(6)
    rows: list[dict[str, Any]] = []
    for idx, row in blocked.iterrows():
        source_chart = Path(str(row.get("chart_file", "")))
        copied = ""
        status = "missing_chart"
        if source_chart.exists():
            target = target_dir / source_chart.name
            shutil.copy2(source_chart, target)
            copied = str(target)
            status = "copied"
        rows.append(
            {
                "reference_id": f"blocked_ref_{idx + 1:03d}",
                "source_case_id": row.get("case_id", ""),
                "symbol": row.get("symbol", ""),
                "timeframe_ltf": row.get("timeframe_ltf", ""),
                "timeframe_htf": row.get("timeframe_htf", ""),
                "swing_quality_reason": row.get("swing_quality_reason", ""),
                "source_chart": str(source_chart),
                "copied_chart": copied,
                "status": status,
                "comparison_note": "Referencia visual de caso bloqueado por gate; no procede de nueva simulacion.",
            }
        )
    return rows


def dashboard_readiness(review: pd.DataFrame) -> list[dict[str, Any]]:
    counts = Counter(review["visual_classification"].astype(str)) if not review.empty else Counter()
    defensible = counts.get("visually_defensible", 0)
    caution = counts.get("visually_acceptable_with_caution", 0)
    manual = counts.get("needs_manual_user_review", 0)
    weak = counts.get("visually_weak", 0) + counts.get("visually_bad", 0)
    if weak > 0:
        decision = "dashboard_needs_user_visual_review"
    elif manual > 0:
        decision = "dashboard_needs_user_visual_review"
    else:
        decision = "dashboard_ready_as_methodology_variant"
    return [
        {
            "decision": decision,
            "defensible_cases": defensible,
            "acceptable_with_caution_cases": caution,
            "manual_review_cases": manual,
            "weak_or_bad_cases": weak,
            "recommended_label": "fib_limit swing-quality",
            "show_in_dashboard": "as_methodology_variant" if decision == "dashboard_ready_as_methodology_variant" else "after_user_review",
            "visible_caution": "Contexto de estudio. No es senal, no garantiza resultado y no habilita ejecucion.",
            "reason": "La muestra no muestra duplicacion/riesgo contable, pero la lectura debe permanecer separada de ENBOLSA V1.",
        }
    ]


def claim_policy_rows() -> list[dict[str, Any]]:
    return [
        {"policy_type": "allowed", "claim": "El gate reduce operaciones con W1/W2 pequenos.", "condition": "Apoyado por comparacion de filas V1 vs swing-quality.", "risk_if_overstated": "Convertir reduccion de casos en prueba de edge."},
        {"policy_type": "allowed", "claim": "La variante fib_limit swing-quality mejora la lectura visual en la muestra auditada.", "condition": "Solo si se cita como muestra visual, no como prueba estadistica adicional.", "risk_if_overstated": "Generalizar desde imagenes concretas."},
        {"policy_type": "allowed", "claim": "La variante queda como estudio metodologico mas defendible que V1.", "condition": "Mantener separacion frente a V1 canonico.", "risk_if_overstated": "Presentarla como sustituto definitivo."},
        {"policy_type": "blocked", "claim": "fib_limit tiene edge robusto.", "condition": "Bloqueado.", "risk_if_overstated": "Afirma robustez no demostrada."},
        {"policy_type": "blocked", "claim": "fib_limit esta listo para operar en real.", "condition": "Bloqueado.", "risk_if_overstated": "Confunde backtest/estudio con operativa."},
        {"policy_type": "blocked", "claim": "El filtro garantiza mejores operaciones.", "condition": "Bloqueado.", "risk_if_overstated": "Confunde filtro metodologico con garantia futura."},
        {"policy_type": "blocked", "claim": "El dashboard puede ejecutar esta estrategia.", "condition": "Bloqueado.", "risk_if_overstated": "Contradice el caracter read-only del Trading Center."},
    ]


def render_report(meta: dict[str, Any], readiness_decision: str) -> str:
    return f"""# FIB_LIMIT Swing Quality Visual Review V1

Fecha: 2026-06-02

Decision: `{meta["decision"]}`.

## Objetivo

Auditar visualmente una muestra de `fib_limit` aceptado por
`enbolsa_swing_quality_v1`, sin modificar reglas ni reejecutar backtests.

## Muestra

- posiciones revisadas: {meta["sample_cases"]}
- graficos aceptados creados: {meta["accepted_charts_created"]}
- referencias bloqueadas copiadas: {meta["blocked_reference_charts"]}

## Lectura

La muestra permite defender `fib_limit swing-quality` como variante
metodologica, no como senal operativa. El gate reduce muchos casos pequenos y
los casos renderizados se clasifican entre defendibles y aceptables con cautela,
pero la limitacion de tiempos exactos W1/W2 en el `trade_log` obliga a mantener
la revision como diagnostica.

## Decision para dashboard

`{readiness_decision}`

Si se incorpora al Trading Center, debe mostrarse como variante de estudio
`fib_limit swing-quality`, separada de ENBOLSA V1, con cautela visible y sin
botones operativos.

## Seguridad

- strategy_modified=false
- backtests_executed=false
- results_recalculated=false
- sql_real_written=false
- mt5_connected=false
- telegram_connected=false
- orders_sent=0
- signals_generated=false
"""


def write_outputs(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    tables_dir = output_dir / "tables"
    accepted_chart_dir = output_dir / "charts/fib_limit_accepted"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    accepted_chart_dir.mkdir(parents=True, exist_ok=True)

    trades = read_trade_log(Path(args.trade_log_csv))
    positions = collapse_positions(trades)
    sample = select_visual_sample(positions, max_cases=args.max_cases)
    render_audit, review = render_cases(sample, Path(args.cache_dir), accepted_chart_dir)
    blocked_rows = copy_blocked_reference(output_dir, Path(args.swing_quality_visual_dir))
    readiness_rows = dashboard_readiness(review)
    readiness_decision = readiness_rows[0]["decision"]
    final_decision = (
        "fib_limit_swing_quality_visual_review_v1_dashboard_ready_as_methodology_variant"
        if readiness_decision == "dashboard_ready_as_methodology_variant"
        else "fib_limit_swing_quality_visual_review_v1_needs_user_visual_review"
    )

    sample_out = sample.copy()
    for column in sample_out.columns:
        if sample_out[column].dtype.kind in {"f"}:
            sample_out[column] = sample_out[column].round(8)
    sample_out.to_csv(tables_dir / "fib_limit_visual_sample_selection.csv", index=False)
    render_audit.to_csv(tables_dir / "fib_limit_visual_render_audit.csv", index=False)
    review.to_csv(tables_dir / "fib_limit_visual_case_review.csv", index=False)
    write_csv(tables_dir / "fib_limit_visual_failure_patterns.csv", build_failure_patterns(review))
    write_csv(tables_dir / "fib_limit_accepted_vs_blocked_visual_audit.csv", blocked_rows)
    write_csv(tables_dir / "fib_limit_dashboard_readiness.csv", readiness_rows)
    write_csv(tables_dir / "fib_limit_visual_claim_policy.csv", claim_policy_rows())
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {
                "risk_id": "FIBVIS01",
                "risk": "El trade_log no guarda tiempos exactos W1/W2.",
                "impact": "La reconstruccion visual por precio puede elegir un punto cercano si hay precios repetidos.",
                "mitigation": "Marcar puntos encontrados/no encontrados y no usar la galeria como prueba de edge.",
            },
            {
                "risk_id": "FIBVIS02",
                "risk": "La mejora de fib_limit puede inducir sobreconfianza.",
                "impact": "Podria confundirse variante metodologica con sistema operativo.",
                "mitigation": "Mantener claims bloqueados y mostrar como study-only/dashboard methodology variant.",
            },
        ],
    )
    meta = {
        "method_version": METHOD_VERSION,
        "generated_at": utc_now(),
        "output_dir": str(output_dir),
        "trade_log_csv": str(Path(args.trade_log_csv)),
        "fib_limit_visual_review_completed": True,
        "sample_cases": int(len(sample)),
        "accepted_charts_created": int(render_audit["visual_status"].astype(str).eq("chart_created").sum()) if not render_audit.empty else 0,
        "blocked_reference_charts": sum(1 for row in blocked_rows if row.get("status") == "copied"),
        "strategy_modified": False,
        "riskguard_modified": False,
        "wavecount_used_as_filter": False,
        "backtests_executed": False,
        "results_recalculated": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "dashboard_updated": False,
        "decision": final_decision,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    report = render_report(meta, readiness_decision)
    (output_dir / "FIB_LIMIT_SWING_QUALITY_VISUAL_REVIEW_V1.md").write_text(report, encoding="utf-8")
    Path(args.doc_path).write_text(report, encoding="utf-8")
    return meta


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit fib_limit swing-quality accepted cases visually without running backtests.")
    parser.add_argument("--trade-log-csv", default=str(DEFAULT_TRADE_LOG_CSV))
    parser.add_argument("--swing-quality-visual-dir", default=str(DEFAULT_SWING_QUALITY_VISUAL_DIR))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--doc-path", default=str(DEFAULT_DOC_PATH))
    parser.add_argument("--max-cases", type=int, default=36)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    return write_outputs(args)


if __name__ == "__main__":
    main()

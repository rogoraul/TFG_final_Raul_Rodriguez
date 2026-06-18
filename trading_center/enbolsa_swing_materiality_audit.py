from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_center.readonly_dashboard import REPO_ROOT, read_csv, write_csv


METHOD_VERSION = "enbolsa_swing_materiality_audit_v1"
DEFAULT_TRADE_LOG_CSV = REPO_ROOT / "artifacts/benchmark-significance/enbolsa/final/tables/trade_log.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/enbolsa_swing_materiality_audit_v1_2026-06-02"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/ENBOLSA_SWING_MATERIALITY_AUDIT_V1.md"

ROW_FIELDNAMES = [
    "symbol",
    "group",
    "strategy",
    "entry_rule",
    "direction",
    "setup_id",
    "entry_time",
    "timeframe_ltf",
    "timeframe_htf",
    "w1_size",
    "w1_size_pct",
    "bm_atr_used",
    "w1_to_bm_atr",
    "initial_risk_distance",
    "risk_to_bm_atr",
    "w2_retr_pct",
    "materiality_bucket",
    "materiality_reason",
    "source_trade_log",
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
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def unique_setup_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        clean(row.get("symbol")),
        clean(row.get("strategy")),
        clean(row.get("entry_rule")),
        clean(row.get("direction")),
        clean(row.get("setup_id")),
        clean(row.get("entry_time")),
        clean(row.get("timeframe_ltf")),
        clean(row.get("timeframe_htf")),
        clean(row.get("partial_source")),
    )


def dedupe_trade_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    output: list[dict[str, str]] = []
    for row in rows:
        key = unique_setup_key(row)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def classify_materiality(w1_to_atr: float | None, w1_pct: float | None) -> tuple[str, str]:
    if w1_to_atr is not None and w1_to_atr > 0:
        if w1_to_atr < 1.5:
            return "very_small", f"W1 {w1_to_atr:.2f}x ATR"
        if w1_to_atr < 2.5:
            return "small", f"W1 {w1_to_atr:.2f}x ATR"
        if w1_to_atr < 5.0:
            return "normal", f"W1 {w1_to_atr:.2f}x ATR"
        return "large", f"W1 {w1_to_atr:.2f}x ATR"
    if w1_pct is not None:
        if w1_pct < 0.25:
            return "very_small", f"W1 {w1_pct:.2f}% precio"
        if w1_pct < 0.60:
            return "small", f"W1 {w1_pct:.2f}% precio"
        if w1_pct < 1.50:
            return "normal", f"W1 {w1_pct:.2f}% precio"
        return "large", f"W1 {w1_pct:.2f}% precio"
    return "not_available", "sin W1/ATR suficiente"


def quantile(values: list[float], q: float) -> float | None:
    cleaned = sorted(value for value in values if value is not None and not math.isnan(value))
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    pos = (len(cleaned) - 1) * q
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return cleaned[int(pos)]
    return cleaned[lower] * (upper - pos) + cleaned[upper] * (pos - lower)


def format_float(value: float | None, digits: int = 4) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def build_audit_rows(rows: list[dict[str, str]], source_trade_log: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in dedupe_trade_rows(rows):
        entry_rule = clean(row.get("entry_rule")).lower()
        strategy = clean(row.get("strategy")).lower()
        if entry_rule not in {"macd_breakout", "fib_limit"} and strategy not in {"macd_breakout", "fib_limit"}:
            continue
        w1_size = as_float(row.get("W1_SIZE"))
        w1_start = as_float(row.get("W1_START_PRICE"))
        bm_atr = as_float(row.get("BM_ATR_USED"))
        risk = as_float(row.get("initial_risk_distance"))
        w1_pct = abs(w1_size) / abs(w1_start) * 100.0 if w1_size is not None and w1_start not in {None, 0.0} else None
        w1_to_atr = abs(w1_size) / bm_atr if w1_size is not None and bm_atr and bm_atr > 0 else None
        risk_to_atr = risk / bm_atr if risk is not None and bm_atr and bm_atr > 0 else None
        bucket, reason = classify_materiality(w1_to_atr, w1_pct)
        output.append(
            {
                "symbol": clean(row.get("symbol")),
                "group": clean(row.get("Group"), clean(row.get("group"), "not_available")),
                "strategy": clean(row.get("strategy")),
                "entry_rule": clean(row.get("entry_rule")),
                "direction": clean(row.get("direction")),
                "setup_id": clean(row.get("setup_id")),
                "entry_time": clean(row.get("entry_time")),
                "timeframe_ltf": clean(row.get("timeframe_ltf")),
                "timeframe_htf": clean(row.get("timeframe_htf")),
                "w1_size": format_float(w1_size, 8),
                "w1_size_pct": format_float(w1_pct),
                "bm_atr_used": format_float(bm_atr, 8),
                "w1_to_bm_atr": format_float(w1_to_atr),
                "initial_risk_distance": format_float(risk, 8),
                "risk_to_bm_atr": format_float(risk_to_atr),
                "w2_retr_pct": clean(row.get("W2_RETR_PCT")),
                "materiality_bucket": bucket,
                "materiality_reason": reason,
                "source_trade_log": str(source_trade_log),
            }
        )
    return output


def summarize(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(clean(row.get(key), "not_available") for key in keys)].append(row)
    output: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items()):
        w1_atr_values = [as_float(row.get("w1_to_bm_atr")) for row in values]
        w1_pct_values = [as_float(row.get("w1_size_pct")) for row in values]
        bucket_counts = Counter(clean(row.get("materiality_bucket")) for row in values)
        result = {name: value for name, value in zip(keys, key)}
        result.update(
            {
                "rows": len(values),
                "very_small": bucket_counts.get("very_small", 0),
                "small": bucket_counts.get("small", 0),
                "normal": bucket_counts.get("normal", 0),
                "large": bucket_counts.get("large", 0),
                "median_w1_to_bm_atr": format_float(quantile([value for value in w1_atr_values if value is not None], 0.5)),
                "p10_w1_to_bm_atr": format_float(quantile([value for value in w1_atr_values if value is not None], 0.1)),
                "median_w1_size_pct": format_float(quantile([value for value in w1_pct_values if value is not None], 0.5)),
            }
        )
        output.append(result)
    return output


def build_outputs(rows: list[dict[str, str]], source_trade_log: Path) -> dict[str, Any]:
    audited = build_audit_rows(rows, source_trade_log)
    return {
        "rows": audited,
        "summary": summarize(audited, ["strategy", "entry_rule"]),
        "by_group": summarize(audited, ["group", "entry_rule"]),
        "by_timeframe": summarize(audited, ["timeframe_ltf", "timeframe_htf", "entry_rule"]),
        "small_examples": sorted(
            [row for row in audited if row["materiality_bucket"] in {"very_small", "small"}],
            key=lambda item: as_float(item.get("w1_to_bm_atr")) if as_float(item.get("w1_to_bm_atr")) is not None else 999.0,
        )[:40],
        "source_rows": len(rows),
    }


def render_report(run_meta: dict[str, Any]) -> str:
    return f"""# ENBOLSA Swing Materiality Audit V1

Fecha: 2026-06-02

Decision: `{run_meta['decision']}`.

## Objetivo

Esta auditoria revisa si los W1 usados en resultados historicos de ENBOLSA
para `macd_breakout` y `fib_limit` son suficientemente materiales frente a
ATR/precio. No recalcula backtests, no modifica estrategia y no genera senales.

## Lectura

- `fib_limit` es la regla mas expuesta a swings pequenos porque usa niveles
  Fibonacci del W1/W2.
- `macd_breakout` no entra por Fibonacci, pero un W1 muy pequeno puede afectar
  a stop/objetivos y calidad del setup.
- Los buckets son diagnosticos, no una invalidacion automatica de resultados.

## Resultado

- rows_audited={run_meta['rows_audited']}
- very_small_count={run_meta['very_small_count']}
- small_count={run_meta['small_count']}
- normal_or_large_count={run_meta['normal_or_large_count']}

## Seguridad

- strategy_modified=false
- backtests_executed=false
- signals_generated=false
- mt5_connected=false
- telegram_connected=false
"""


def write_outputs(output_dir: Path, result: dict[str, Any], args: argparse.Namespace, generated_at: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    rows = result["rows"]
    write_csv(output_dir / "enbolsa_swing_materiality_rows.csv", rows, ROW_FIELDNAMES)
    write_csv(tables_dir / "enbolsa_swing_materiality_summary.csv", result["summary"])
    write_csv(tables_dir / "enbolsa_entry_rule_materiality.csv", result["by_group"])
    write_csv(tables_dir / "enbolsa_timeframe_materiality.csv", result["by_timeframe"])
    write_csv(tables_dir / "enbolsa_small_w1_examples.csv", result["small_examples"], ROW_FIELDNAMES)
    write_csv(
        tables_dir / "enbolsa_materiality_risk_audit.csv",
        [
            {"risk_id": "MAT01", "area": "fib_limit", "risk": "W1 pequeno puede hacer niveles Fibonacci poco informativos.", "status": "audit_only", "mitigation": "Revisar ejemplos small/very_small antes de afirmar robustez por fib_limit."},
            {"risk_id": "MAT02", "area": "macd_breakout", "risk": "W1 pequeno puede afectar stop/objetivos aunque la entrada no sea Fibonacci.", "status": "audit_only", "mitigation": "Mantener lectura prudente; no modificar regla sin fase metodologica separada."},
        ],
    )
    write_csv(
        tables_dir / "issues_or_risks.csv",
        [
            {"issue_id": "ENB-MAT01", "severity": "medium", "status": "open", "description": "La auditoria puede detectar setups historicos con W1 pequeno.", "mitigation": "Documentar como sensibilidad metodologica, no cambiar resultados ya validados."},
            {"issue_id": "ENB-MAT02", "severity": "low", "status": "open", "description": "BM_ATR_USED puede faltar en algunos rows.", "mitigation": "Fallback a W1_SIZE porcentual sobre precio."},
        ],
    )
    bucket_counts = Counter(row["materiality_bucket"] for row in rows)
    decision = "enbolsa_swing_materiality_audit_v1_ready_for_methodology_review"
    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": generated_at,
        "decision": decision,
        "source_trade_log": str(args.trade_log_csv),
        "source_rows": result["source_rows"],
        "rows_audited": len(rows),
        "very_small_count": bucket_counts.get("very_small", 0),
        "small_count": bucket_counts.get("small", 0),
        "normal_or_large_count": bucket_counts.get("normal", 0) + bucket_counts.get("large", 0),
        "strategy_modified": False,
        "backtests_executed": False,
        "signals_generated": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "wavecount_used_as_filter": False,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=True), encoding="utf-8")
    report = render_report(run_meta)
    (output_dir / "ENBOLSA_SWING_MATERIALITY_AUDIT_V1.md").write_text(report, encoding="utf-8")
    if args.doc_path:
        args.doc_path.parent.mkdir(parents=True, exist_ok=True)
        args.doc_path.write_text(report, encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Audit ENBOLSA W1 swing materiality without recalculating strategies.")
    parser.add_argument("--trade-log-csv", type=Path, default=DEFAULT_TRADE_LOG_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args(argv)

    rows = read_csv(args.trade_log_csv)
    if not rows and not args.allow_empty:
        raise SystemExit(f"No rows found in {args.trade_log_csv}")
    generated_at = utc_now()
    result = build_outputs(rows, args.trade_log_csv)
    write_outputs(args.output_dir, result, args, generated_at)


if __name__ == "__main__":
    main()

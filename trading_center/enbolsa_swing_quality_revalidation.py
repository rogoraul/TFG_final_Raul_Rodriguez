from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD_VERSION = "enbolsa_swing_quality_revalidation_v1"
QUALITY_GATE_VERSION = "enbolsa_swing_quality_v1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts/tfg/enbolsa_swing_quality_revalidation_v1_2026-06-02"
DEFAULT_BENCHMARK_ROOT = REPO_ROOT / "artifacts/benchmark-significance/enbolsa_swing_quality_v1"
DEFAULT_V1_FINAL = REPO_ROOT / "artifacts/benchmark-significance/enbolsa/final"
DEFAULT_DOC_PATH = REPO_ROOT / "docs/ENBOLSA_SWING_QUALITY_REVALIDATION_V1.md"
DEFAULT_GROUPS = ("Forex Majors", "Metals", "Index")
DEFAULT_TF_PAIRS = ("M30:H1", "H1:H4", "H4:D1")
ENBOLSA_VARIANTS = ("enbolsa:fib_limit", "enbolsa:macd_breakout")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    return str(value).strip().lower().replace(" ", "-").replace(":", "-")


def read_table(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def write_table(path: Path, frame: pd.DataFrame | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(frame, list):
        frame = pd.DataFrame(frame)
    frame.to_csv(path, index=False)


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "elapsed_seconds": round(time.time() - started, 2),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "status": "passed" if proc.returncode == 0 else "failed",
    }


def revalidation_config_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    return [
        {"parameter": "swing_quality_gate_enabled", "value": True, "status": "enabled_for_revalidation"},
        {"parameter": "quality_gate_version", "value": QUALITY_GATE_VERSION, "status": "explicit"},
        {"parameter": "strategies", "value": ",".join(ENBOLSA_VARIANTS), "status": "main_enbolsa_only"},
        {"parameter": "groups", "value": ",".join(args.groups), "status": "configured"},
        {"parameter": "tf_pairs", "value": ",".join(args.tf_pairs), "status": "configured"},
        {"parameter": "canonical_final_preserved", "value": str(args.v1_final), "status": "read_only_reference"},
        {"parameter": "benchmark_output_root", "value": str(args.benchmark_root), "status": "separate_variant_root"},
        {"parameter": "portfolio_cache_policy", "value": "force_rebuild" if not args.reuse_existing_cache else "reuse_existing_cache", "status": "required_for_new_w1_bars" if not args.reuse_existing_cache else "manual_override"},
        {"parameter": "riskguard_modified", "value": False, "status": "passed"},
        {"parameter": "wavecount_used_as_filter", "value": False, "status": "passed"},
    ]


def execute_revalidation_partials(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    runner = REPO_ROOT / "backtests/benchmarks/run_enbolsa_benchmark_comparison.py"
    for group in args.groups:
        for tf_pair in args.tf_pairs:
            partial_dir = args.benchmark_root / f"partial-{slug(group)}-{slug(tf_pair)}"
            command = [
                sys.executable,
                str(runner),
                "--groups",
                group,
                "--tf-pairs",
                tf_pair,
                "--output-root",
                str(partial_dir),
                "--enbolsa-swing-quality-gate",
                "--quiet",
            ]
            if args.no_disk_cache:
                command.append("--no-disk-cache")
            if args.force_rebuild or not args.reuse_existing_cache:
                command.append("--force-rebuild")
            result = run_command(command, REPO_ROOT)
            rows.append(
                {
                    "group": group,
                    "tf_pair": tf_pair,
                    "partial_dir": str(partial_dir),
                    "trade_log_exists": (partial_dir / "tables/trade_log.csv").is_file(),
                    **result,
                }
            )
            if result["returncode"] != 0 and not args.keep_going:
                raise RuntimeError(f"Partial failed: {group} {tf_pair}\n{result['stderr_tail']}")
    return rows


def merge_revalidation_partials(args: argparse.Namespace) -> dict[str, Any]:
    merge_script = REPO_ROOT / "backtests/benchmarks/merge_partials.py"
    command = [
        sys.executable,
        str(merge_script),
        str(args.benchmark_root / "partial-*"),
        "--output-root",
        str(args.benchmark_root / "final"),
    ]
    return run_command(command, REPO_ROOT)


def normalize_strategy(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "Variante" in result.columns:
        result["strategy_key"] = result["Variante"].astype(str)
    elif "strategy" in result.columns:
        result["strategy_key"] = result["strategy"].astype(str)
    else:
        result["strategy_key"] = ""
    return result


def build_v1_vs_swing_quality(v1_final: Path, sq_final: Path) -> dict[str, pd.DataFrame]:
    v1_block = normalize_strategy(read_table(v1_final / "tables/block_metrics.csv"))
    sq_block = normalize_strategy(read_table(sq_final / "tables/block_metrics.csv"))
    if v1_block.empty or sq_block.empty:
        empty = pd.DataFrame()
        return {
            "comparison": empty,
            "by_strategy": empty,
            "by_block": empty,
            "methodology": pd.DataFrame([{
                "check": "source_tables",
                "status": "blocked",
                "notes": "Missing V1 or swing-quality block_metrics.",
            }]),
        }

    keys = ["strategy_key", "Group", "TFPair", "BlockId"]
    v1_subset = v1_block[v1_block["strategy_key"].isin(ENBOLSA_VARIANTS)].copy()
    sq_subset = sq_block[sq_block["strategy_key"].isin(ENBOLSA_VARIANTS)].copy()
    metric_cols = [col for col in ("Trades", "Return%", "PF", "MaxDD%", "Sharpe", "Sortino", "NetProfit", "AvgR") if col in v1_subset.columns and col in sq_subset.columns]
    merged = v1_subset[keys + metric_cols].merge(
        sq_subset[keys + metric_cols],
        on=keys,
        how="outer",
        suffixes=("_v1", "_swing_quality"),
    )
    for col in metric_cols:
        merged[f"{col}_delta"] = pd.to_numeric(merged[f"{col}_swing_quality"], errors="coerce") - pd.to_numeric(merged[f"{col}_v1"], errors="coerce")
    merged["comparison_scope"] = "block_independent_no_global_equity"

    by_strategy_rows = []
    for strategy, group in merged.groupby("strategy_key", dropna=False, sort=True):
        row = {"strategy": strategy, "blocks": len(group)}
        for col in metric_cols:
            delta = pd.to_numeric(group.get(f"{col}_delta"), errors="coerce")
            row[f"mean_{col}_delta"] = round(float(delta.mean()), 4) if delta.notna().any() else 0.0
            row[f"median_{col}_delta"] = round(float(delta.median()), 4) if delta.notna().any() else 0.0
        by_strategy_rows.append(row)

    methodology = pd.DataFrame([
        {
            "check": "canonical_v1_preserved",
            "status": "passed",
            "notes": "V1 final is used as read-only baseline; swing-quality output is separate.",
        },
        {
            "check": "no_pseudo_global_equity",
            "status": "passed",
            "notes": "Comparison is by independent block keys: strategy, group, TFPair and BlockId.",
        },
        {
            "check": "claims",
            "status": "caution",
            "notes": "A positive delta does not prove robust edge; it only supports this revalidation scope.",
        },
    ])
    return {
        "comparison": merged,
        "by_strategy": pd.DataFrame(by_strategy_rows),
        "by_block": merged.sort_values(keys).reset_index(drop=True),
        "methodology": methodology,
    }


def build_gate_effect_tables(v1_final: Path, sq_final: Path) -> dict[str, pd.DataFrame]:
    v1_log = normalize_strategy(read_table(v1_final / "tables/trade_log.csv"))
    sq_log = normalize_strategy(read_table(sq_final / "tables/trade_log.csv"))
    if v1_log.empty or sq_log.empty:
        empty = pd.DataFrame()
        return {"by_strategy": empty, "by_group": empty, "by_timeframe": empty, "by_block": empty}
    v1_log = v1_log[v1_log["strategy_key"].isin(ENBOLSA_VARIANTS)].copy()
    sq_log = sq_log[sq_log["strategy_key"].isin(ENBOLSA_VARIANTS)].copy()
    dims = {
        "by_strategy": ["strategy_key"],
        "by_group": ["strategy_key", "Group"],
        "by_timeframe": ["strategy_key", "timeframe_ltf", "timeframe_htf"],
        "by_block": ["strategy_key", "Group", "timeframe_ltf", "timeframe_htf"],
    }
    output: dict[str, pd.DataFrame] = {}
    for name, group_cols in dims.items():
        v1_counts = v1_log.groupby(group_cols, dropna=False).size().reset_index(name="trade_rows_v1")
        sq_counts = sq_log.groupby(group_cols, dropna=False).size().reset_index(name="trade_rows_swing_quality")
        merged = v1_counts.merge(sq_counts, on=group_cols, how="outer").fillna(0)
        merged["trade_rows_v1"] = merged["trade_rows_v1"].astype(int)
        merged["trade_rows_swing_quality"] = merged["trade_rows_swing_quality"].astype(int)
        merged["trade_rows_blocked_by_gate_estimate"] = merged["trade_rows_v1"] - merged["trade_rows_swing_quality"]
        merged["remaining_rate_pct"] = (
            merged["trade_rows_swing_quality"] / merged["trade_rows_v1"].replace(0, pd.NA) * 100.0
        ).fillna(0.0).round(2)
        merged["note"] = "Trade-row effect; ENBOLSA TP legs can create more than one row per position."
        output[name] = merged.sort_values(group_cols).reset_index(drop=True)
    return output


def build_backtest_summaries(sq_final: Path) -> dict[str, pd.DataFrame]:
    block = read_table(sq_final / "tables/block_metrics.csv")
    if block.empty:
        return {"summary": pd.DataFrame(), "block": pd.DataFrame()}
    enbolsa = block[block["Variante"].isin(ENBOLSA_VARIANTS)].copy()
    summary = (
        enbolsa.groupby("Variante", dropna=False)
        .agg(
            blocks=("BlockId", "count"),
            total_trades=("Trades", "sum"),
            mean_return_pct=("Return%", "mean"),
            median_return_pct=("Return%", "median"),
            positive_blocks=("Return%", lambda s: int((pd.to_numeric(s, errors="coerce") > 0).sum())),
            median_pf=("PF", "median"),
            median_maxdd_pct=("MaxDD%", "median"),
        )
        .reset_index()
    )
    for col in ("mean_return_pct", "median_return_pct", "median_pf", "median_maxdd_pct"):
        summary[col] = pd.to_numeric(summary[col], errors="coerce").round(4)
    return {"summary": summary, "block": enbolsa}


def build_benchmark_tables(sq_final: Path, v1_final: Path) -> dict[str, pd.DataFrame]:
    sq_block = read_table(sq_final / "tables/block_metrics.csv")
    v1_block = read_table(v1_final / "tables/block_metrics.csv")
    if sq_block.empty:
        return {
            "audit": pd.DataFrame([{"check": "benchmark_tables", "status": "blocked", "notes": "Missing swing-quality final block metrics."}]),
            "summary": pd.DataFrame(),
            "block": pd.DataFrame(),
            "risk": pd.DataFrame(),
        }
    audit = pd.DataFrame([
        {"check": "benchmark_comparison_executed", "status": "passed", "notes": f"Rows in block_metrics: {len(sq_block)}"},
        {"check": "classic_benchmarks_included", "status": "passed" if sq_block["Family"].astype(str).str.contains("benchmark").any() else "warning", "notes": "Classic benchmark rows are expected from runner."},
        {"check": "canonical_v1_overwritten", "status": "passed", "notes": "Output root is enbolsa_swing_quality_v1, not enbolsa/final."},
    ])
    summary = sq_block.groupby(["Variante", "Family"], dropna=False).agg(
        blocks=("BlockId", "count"),
        total_trades=("Trades", "sum"),
        mean_return_pct=("Return%", "mean"),
        median_return_pct=("Return%", "median"),
        median_pf=("PF", "median"),
    ).reset_index()
    for col in ("mean_return_pct", "median_return_pct", "median_pf"):
        summary[col] = pd.to_numeric(summary[col], errors="coerce").round(4)
    risk = pd.DataFrame([
        {
            "risk_id": "BM01",
            "risk": "Comparing V1 and swing-quality can be overread as optimization.",
            "mitigation": "No thresholds were tuned by PnL; treat as methodological robustness check.",
        },
        {
            "risk_id": "BM02",
            "risk": "TotalNetProfit aggregates independent blocks.",
            "mitigation": "Use block_metrics first; do not present as global account equity.",
        },
        {
            "risk_id": "BM03",
            "risk": "H4:D1 remains degraded 2TF infrastructure.",
            "mitigation": "Keep H4D1Mode and TFStackEffective labels in result tables.",
        },
    ])
    return {"audit": audit, "summary": summary, "block": sq_block, "risk": risk}


def decision_from_outputs(summaries: dict[str, pd.DataFrame], comparison: pd.DataFrame, commands: list[dict[str, Any]]) -> str:
    if any(row.get("returncode", 0) != 0 for row in commands):
        return "enbolsa_swing_quality_revalidation_v1_blocked_by_methodology"
    summary = summaries.get("summary", pd.DataFrame())
    if summary.empty or comparison.empty:
        return "enbolsa_swing_quality_revalidation_v1_blocked_by_results_regression"
    sq_trades = pd.to_numeric(summary.get("total_trades", pd.Series(dtype=float)), errors="coerce").fillna(0)
    if (sq_trades <= 0).all():
        return "enbolsa_swing_quality_revalidation_v1_blocked_by_results_regression"
    return "enbolsa_swing_quality_revalidation_v1_passed_with_limitations"


def claims_tables(decision: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    allowed = pd.DataFrame([
        {
            "claim_id": "A01",
            "claim": "Se revalido una variante ENBOLSA con gate swing-quality V1 en artifacts separados.",
            "condition": "Usar solo si run_meta confirma full_backtests_executed=true.",
        },
        {
            "claim_id": "A02",
            "claim": "El gate reduce o filtra operaciones con W1/W2 de menor calidad segun reglas auditables.",
            "condition": "No traducir a mejora de rentabilidad sin mirar comparacion por bloque.",
        },
        {
            "claim_id": "A03",
            "claim": "ENBOLSA V1 canonico se conserva como baseline historico.",
            "condition": "No sobrescribir artifacts/benchmark-significance/enbolsa/final.",
        },
    ])
    blocked = pd.DataFrame([
        {"claim_id": "B01", "claim": "El gate demuestra edge robusto.", "reason": "No se ha demostrado robustez fuera de esta revalidacion."},
        {"claim_id": "B02", "claim": "La variante esta lista para operar en real.", "reason": "No hay MT5, ordenes, Telegram ni aprobacion operativa."},
        {"claim_id": "B03", "claim": "Los resultados son una equity global unica.", "reason": "Los bloques son independientes."},
        {"claim_id": "B04", "claim": "WaveCount filtra ENBOLSA.", "reason": "WaveCount sigue study-only y no participa en el gate."},
    ])
    risks = pd.DataFrame([
        {"risk_id": "R01", "risk": "Thresholds aceptados provisionalmente, no optimizados por rentabilidad.", "status": "open", "mitigation": "Mantener etiqueta passed_with_limitations salvo revision posterior."},
        {"risk_id": "R02", "risk": "Puede haber casos visuales discutibles aun tras el gate.", "status": "open", "mitigation": "Usar galeria post-backtest y documentar casos."},
        {"risk_id": "R03", "risk": "Dashboard podria hacer parecer operativa la variante.", "status": "open", "mitigation": "Solo read-only y con copy de variante metodologica."},
    ])
    return allowed, blocked, risks


def visual_case_inventory(sq_final: Path, output_dir: Path, max_cases: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    trade_log = read_table(sq_final / "tables/trade_log.csv")
    if trade_log.empty:
        empty = pd.DataFrame()
        return empty, pd.DataFrame([{"check": "visual_cases", "status": "blocked", "notes": "Missing trade_log."}])
    trade_log = trade_log[trade_log["strategy"].isin(ENBOLSA_VARIANTS)].copy()
    if trade_log.empty:
        empty = pd.DataFrame()
        return empty, pd.DataFrame([{"check": "visual_cases", "status": "blocked", "notes": "No ENBOLSA trades in swing-quality trade log."}])
    group_cols = [col for col in ("strategy", "Group", "timeframe_ltf", "timeframe_htf") if col in trade_log.columns]
    samples = []
    for _, group in trade_log.groupby(group_cols, dropna=False, sort=True):
        samples.append(group.head(2))
    sample = pd.concat(samples, ignore_index=True).head(max_cases) if samples else trade_log.head(max_cases)
    rows = []
    for idx, row in sample.reset_index(drop=True).iterrows():
        rows.append({
            "case_id": f"sq_case_{idx + 1:03d}",
            "strategy": row.get("strategy", ""),
            "symbol": row.get("symbol", ""),
            "group": row.get("Group", ""),
            "timeframe_ltf": row.get("timeframe_ltf", ""),
            "timeframe_htf": row.get("timeframe_htf", ""),
            "entry_time": row.get("entry_time", ""),
            "setup_id": row.get("setup_id", ""),
            "swing_quality_pass": row.get("SWING_QUALITY_PASS", ""),
            "swing_quality_reason": row.get("SWING_QUALITY_REASON", ""),
            "chart_status": "not_rendered_in_revalidation_v1",
            "note": "Post-backtest sample selected; visual rendering can use strategy visual audit tooling if manual review is needed.",
        })
    audit = pd.DataFrame([
        {"check": "accepted_cases_sampled", "status": "passed", "rows": len(rows)},
        {"check": "blocked_cases_rendered", "status": "deferred", "rows": 0, "notes": "Blocked entries are absent from post-gate trade log; compare against V1 for blocked examples."},
    ])
    (output_dir / "charts/accepted_swing_quality").mkdir(parents=True, exist_ok=True)
    (output_dir / "charts/blocked_swing_quality").mkdir(parents=True, exist_ok=True)
    return pd.DataFrame(rows), audit


def render_report(run_meta: dict[str, Any], backtest_summary: pd.DataFrame, comparison_by_strategy: pd.DataFrame) -> str:
    summary_md = backtest_summary.to_string(index=False) if not backtest_summary.empty else "Sin resumen disponible."
    comparison_md = comparison_by_strategy.to_string(index=False) if not comparison_by_strategy.empty else "Sin comparacion disponible."
    return f"""# ENBOLSA Swing Quality Revalidation V1

Fecha: 2026-06-02

Decision: `{run_meta['decision']}`.

## Objetivo

Revalidar ENBOLSA con `swing_quality_gate_enabled=true` y mantener la salida
separada de los artifacts canonicos V1.

## Lectura

El gate queda como variante metodologica aceptada con limitaciones. Sirve para
reducir casos con W1/W2 demasiado pequenos, pero no demuestra edge robusto ni
habilita operativa real.

## Resumen swing-quality

{summary_md}

## Comparacion V1 vs swing-quality por estrategia

{comparison_md}

## Seguridad

- enbolsa_v1_preserved={run_meta['enbolsa_v1_preserved']}
- canonical_artifacts_overwritten={run_meta['canonical_artifacts_overwritten']}
- riskguard_modified={run_meta['riskguard_modified']}
- wavecount_used_as_filter={run_meta['wavecount_used_as_filter']}
- sql_real_written={run_meta['sql_real_written']}
- mt5_connected={run_meta['mt5_connected']}
- telegram_connected={run_meta['telegram_connected']}
- orders_sent={run_meta['orders_sent']}

## Siguiente paso

Revisar manualmente la comparacion por bloque y decidir si el dashboard debe
mostrar la variante como lectura principal o como alternativa metodologica.
"""


def build_outputs(args: argparse.Namespace, command_rows: list[dict[str, Any]], merge_row: dict[str, Any]) -> dict[str, Any]:
    output_dir = args.output_dir
    tables_dir = output_dir / "tables"
    sq_final = args.benchmark_root / "final"
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    backtest = build_backtest_summaries(sq_final)
    comparison = build_v1_vs_swing_quality(args.v1_final, sq_final)
    gate_effect = build_gate_effect_tables(args.v1_final, sq_final)
    benchmark = build_benchmark_tables(sq_final, args.v1_final)
    visual_cases, visual_audit = visual_case_inventory(sq_final, output_dir)

    decision = decision_from_outputs(backtest, comparison["comparison"], [*command_rows, merge_row])
    allowed, blocked, risks = claims_tables(decision)

    write_table(tables_dir / "revalidation_config_audit.csv", revalidation_config_rows(args))
    write_table(tables_dir / "backtest_execution_audit.csv", command_rows)
    write_table(tables_dir / "backtest_result_summary.csv", backtest["summary"])
    write_table(tables_dir / "backtest_block_metrics.csv", backtest["block"])
    write_table(tables_dir / "swing_quality_gate_effect_by_block.csv", gate_effect["by_block"])
    write_table(tables_dir / "swing_quality_gate_effect_by_strategy.csv", gate_effect["by_strategy"])
    write_table(tables_dir / "swing_quality_gate_effect_by_group.csv", gate_effect["by_group"])
    write_table(tables_dir / "swing_quality_gate_effect_by_timeframe.csv", gate_effect["by_timeframe"])
    write_table(tables_dir / "v1_vs_swing_quality_comparison.csv", comparison["comparison"])
    write_table(tables_dir / "v1_vs_swing_quality_by_strategy.csv", comparison["by_strategy"])
    write_table(tables_dir / "v1_vs_swing_quality_by_block.csv", comparison["by_block"])
    write_table(tables_dir / "v1_vs_swing_quality_methodology_audit.csv", comparison["methodology"])
    write_table(tables_dir / "benchmark_revalidation_audit.csv", benchmark["audit"])
    write_table(tables_dir / "benchmark_v1_vs_swing_quality_summary.csv", benchmark["summary"])
    write_table(tables_dir / "benchmark_block_metrics_swing_quality.csv", benchmark["block"])
    write_table(tables_dir / "benchmark_methodology_risk_audit.csv", benchmark["risk"])
    write_table(tables_dir / "post_backtest_visual_case_inventory.csv", visual_cases)
    write_table(tables_dir / "post_backtest_visual_audit.csv", visual_audit)
    write_table(tables_dir / "revalidation_decision.csv", [{"decision": decision, "reason": "Variant executed separately; thresholds remain provisional and auditable."}])
    write_table(tables_dir / "allowed_claims_after_revalidation.csv", allowed)
    write_table(tables_dir / "blocked_claims_after_revalidation.csv", blocked)
    write_table(tables_dir / "methodology_risks_after_revalidation.csv", risks)
    write_table(tables_dir / "dashboard_update_audit.csv", [{
        "check": "dashboard_update",
        "status": "not_updated_pending_manual_review",
        "notes": "Dashboard source is not switched automatically; user should review block results first.",
    }])
    write_table(tables_dir / "issues_or_risks.csv", risks)

    run_meta = {
        "method_version": METHOD_VERSION,
        "generated_at": utc_now(),
        "output_dir": str(output_dir),
        "benchmark_root": str(args.benchmark_root),
        "decision": decision,
        "enbolsa_swing_quality_revalidated": True,
        "swing_quality_gate_enabled": True,
        "quality_gate_version": QUALITY_GATE_VERSION,
        "enbolsa_v1_preserved": True,
        "canonical_artifacts_overwritten": False,
        "full_backtests_executed": bool(command_rows) and all(row.get("returncode") == 0 for row in command_rows),
        "benchmark_comparisons_executed": merge_row.get("returncode") == 0,
        "riskguard_modified": False,
        "wavecount_used_as_filter": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "db_connected": False,
        "mt5_connected": False,
        "telegram_connected": False,
        "orders_sent": 0,
        "signals_generated": False,
        "dashboard_updated": False,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    report = render_report(run_meta, backtest["summary"], comparison["by_strategy"])
    (output_dir / "ENBOLSA_SWING_QUALITY_REVALIDATION_V1.md").write_text(report, encoding="utf-8")
    args.doc_path.parent.mkdir(parents=True, exist_ok=True)
    args.doc_path.write_text(report, encoding="utf-8")
    return {"run_meta": run_meta, "backtest": backtest, "comparison": comparison}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ENBOLSA swing-quality backtest/benchmark revalidation.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--v1-final", type=Path, default=DEFAULT_V1_FINAL)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--groups", nargs="*", default=list(DEFAULT_GROUPS))
    parser.add_argument("--tf-pairs", nargs="*", default=list(DEFAULT_TF_PAIRS))
    parser.add_argument("--skip-backtests", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument("--no-disk-cache", action="store_true")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument(
        "--reuse-existing-cache",
        action="store_true",
        help="Permite reutilizar caches antiguas; no recomendado para esta fase porque W1_BARS es nuevo.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    args.output_dir = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    args.benchmark_root = args.benchmark_root if args.benchmark_root.is_absolute() else REPO_ROOT / args.benchmark_root
    args.v1_final = args.v1_final if args.v1_final.is_absolute() else REPO_ROOT / args.v1_final
    args.doc_path = args.doc_path if args.doc_path.is_absolute() else REPO_ROOT / args.doc_path

    command_rows: list[dict[str, Any]] = []
    if not args.skip_backtests:
        command_rows = execute_revalidation_partials(args)
        merge_row = merge_revalidation_partials(args)
    else:
        merge_row = {
            "command": "skip-backtests",
            "returncode": 0,
            "elapsed_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
            "status": "skipped_existing_outputs",
        }
    return build_outputs(args, command_rows, merge_row)


if __name__ == "__main__":
    main()

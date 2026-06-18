from __future__ import annotations

import argparse
import gc
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from backtests.common.trade_analysis import DEFAULT_METRIC_COLUMNS, metrics_from_trades
from backtests.menendez.menendez_config import (
    DEFAULT_GROUP,
    DEFAULT_TIMEFRAME_HTF,
    DEFAULT_TIMEFRAME_LTF,
    get_experiment_contract,
    get_variant_specs,
)
from backtests.menendez.menendez_loader import cargar_portfolio_menendez
from backtests.menendez.menendez_pipeline import (
    _merge_strategy_overrides,
    construir_bundle_experimental_menendez,
    ejecutar_comparativa,
    extraer_trades_resultado,
    generar_desgloses_resultado,
    resumir_periodos,
    resumir_portfolio_cargado,
)
from data.sql.sql_funcs import get_symbols_by_group_normalized


DEFAULT_VARIANTS = (
    "faithful_operable_sma200_primary",
    "faithful_operable_trigger_or",
    "experimental_composite_x",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = df.copy() if df is not None else pd.DataFrame()
    frame.to_csv(path, index=False)


def _json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _parse_symbols(args) -> list[str] | None:
    if args.symbols:
        return [item.strip() for item in args.symbols.split(",") if item.strip()]
    if args.limit_symbols:
        symbols = get_symbols_by_group_normalized([args.group]).get(args.group, [])
        return list(symbols[: int(args.limit_symbols)])
    return None


def _symbol_stability_table(variant_name: str, portfolio: dict, trades: pd.DataFrame, funnel: dict) -> pd.DataFrame:
    stage_counts = funnel.get("stage_counts", pd.DataFrame()).copy()
    if stage_counts.empty:
        stage_counts = pd.DataFrame(columns=[
            "Activo", "Velas", "H4_BLOCKED", "HTF_OK", "SETUP_ROWS", "RETRACE_OK",
            "FAN_BREAKOUT", "MACD_TRIGGER", "STOCH_TRIGGER", "RR_OK", "ENTRY_READY",
        ])
    stage_counts = stage_counts[stage_counts.get("Activo", "") != "TOTAL"].copy()

    rows = []
    symbols = list(portfolio.keys())
    for symbol in symbols:
        symbol_trades = trades[trades["symbol"] == symbol].copy() if not trades.empty and "symbol" in trades.columns else pd.DataFrame()
        metrics = metrics_from_trades(symbol_trades)
        metrics["Variant"] = variant_name
        metrics["Activo"] = symbol
        rows.append(metrics)

    metrics_df = pd.DataFrame(rows)
    if metrics_df.empty:
        metrics_df = pd.DataFrame(columns=["Variant", "Activo", *DEFAULT_METRIC_COLUMNS])
    else:
        metrics_df = metrics_df[["Variant", "Activo", *DEFAULT_METRIC_COLUMNS]]

    result = metrics_df.merge(stage_counts, on="Activo", how="left")
    count_cols = [
        "Velas", "H4_BLOCKED", "HTF_OK", "SETUP_ROWS", "RETRACE_OK",
        "FAN_BREAKOUT", "MACD_TRIGGER", "STOCH_TRIGGER", "RR_OK", "ENTRY_READY",
    ]
    for col in count_cols:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0).astype(int)
    return result.sort_values(["Variant", "Return%", "PF", "Trades"], ascending=[True, False, False, False])


def _load_enbolsa_reference(repo_root: Path) -> pd.DataFrame:
    path = repo_root / "artifacts" / "benchmark-significance" / "enbolsa" / "final" / "tables" / "aggregate_by_strategy.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "Variante" not in df.columns:
        return pd.DataFrame()
    return df[df["Variante"].astype(str).str.contains("enbolsa:macd_breakout", regex=False)].copy()


def _format_markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df is None or df.empty:
        return "_Sin filas._"
    view = df.head(max_rows).copy()
    columns = [str(col) for col in view.columns]
    rows = ["| " + " | ".join(columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, item in view.iterrows():
        values = []
        for col in view.columns:
            value = item[col]
            if pd.isna(value):
                text = ""
            elif isinstance(value, float):
                text = f"{value:.4g}"
            else:
                text = str(value)
            values.append(text.replace("|", "\\|"))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def _final_classification(summary_table: pd.DataFrame) -> str:
    if summary_table is None or summary_table.empty:
        return "bloque metodologico sin edge demostrado"
    trades = pd.to_numeric(summary_table.get("Trades"), errors="coerce").fillna(0)
    pf = pd.to_numeric(summary_table.get("PF"), errors="coerce").fillna(0)
    returns = pd.to_numeric(summary_table.get("Return%"), errors="coerce").fillna(0)
    if int(trades.sum()) == 0:
        return "linea exploratoria futura"
    if bool(((trades >= 30) & (pf > 1.05) & (returns > 0)).any()):
        return "bloque empirico secundario defendible"
    return "bloque metodologico sin edge demostrado"


def _write_report(
    output_dir: Path,
    run_meta: dict,
    summary_table: pd.DataFrame,
    symbol_stability: pd.DataFrame,
    stage_counts: pd.DataFrame,
    block_reasons: pd.DataFrame,
    enbolsa_reference: pd.DataFrame,
) -> None:
    classification = _final_classification(summary_table)
    total_trades = int(pd.to_numeric(summary_table.get("Trades"), errors="coerce").fillna(0).sum()) if not summary_table.empty else 0
    least_negative = summary_table.sort_values(["Return%", "PF", "Trades"], ascending=[False, False, False]).head(1) if not summary_table.empty else pd.DataFrame()

    lines = [
        "# Cierre empirico Menendez",
        "",
        f"Fecha de ejecucion: `{run_meta['generated_at']}`",
        "",
        "## Reproducibilidad",
        "",
        "Comando equivalente:",
        "",
        "```powershell",
        run_meta["command"],
        "```",
        "",
        "Configuracion:",
        "",
        f"- grupo: `{run_meta['group_name']}`",
        f"- timeframe: `{run_meta['timeframe_htf']} -> {run_meta['timeframe_ltf']}`",
        f"- variantes: `{', '.join(run_meta['variants'])}`",
        f"- simbolos cargados: `{run_meta['loaded_symbols']}` de `{run_meta['requested_symbols']}`",
        f"- cache: `use_cache={run_meta['use_cache']}`, `use_disk_cache={run_meta['use_disk_cache']}`, `force_rebuild={run_meta['force_rebuild']}`",
        "",
        "## Decision",
        "",
        f"Clasificacion final: **{classification}**.",
        "",
        "Menendez queda por debajo de ENBOLSA como eje empirico. La linea es util para el TFG como formalizacion metodologica auditada, pero no demuestra edge robusto con esta corrida.",
        "",
        "## Resumen por variante",
        "",
        _format_markdown_table(summary_table),
        "",
        f"Trades totales agregados en variantes: `{total_trades}`.",
        "",
    ]

    if not least_negative.empty:
        row = least_negative.iloc[0]
        lines.extend([
            "Variante menos negativa por retorno en esta corrida:",
            "",
            f"- `{row.get('Variant', row.get('Variante', ''))}`: Trades `{row.get('Trades')}`, PF `{row.get('PF')}`, Return% `{row.get('Return%')}`, MaxDD% `{row.get('MaxDD%')}`.",
            "- Esta etiqueta no implica edge: solo identifica la menor perdida agregada de la tabla.",
            "",
        ])

    lines.extend([
        "## Estabilidad por simbolo",
        "",
        "Top filas por retorno dentro de cada variante:",
        "",
        _format_markdown_table(symbol_stability.sort_values(["Variant", "Return%", "PF", "Trades"], ascending=[True, False, False, False]), max_rows=30),
        "",
        "## Embudo de senales",
        "",
        _format_markdown_table(stage_counts, max_rows=40),
        "",
        "## Principales bloqueos",
        "",
        _format_markdown_table(block_reasons, max_rows=40),
        "",
        "## Comparacion conceptual con ENBOLSA",
        "",
    ])

    if not enbolsa_reference.empty:
        lines.extend([
            "Referencia canonica ENBOLSA `macd_breakout` tomada de `artifacts/benchmark-significance/enbolsa/final/tables/aggregate_by_strategy.csv`:",
            "",
            _format_markdown_table(enbolsa_reference),
            "",
        ])
    else:
        lines.extend([
            "No se encontro referencia ENBOLSA canonica en artifacts. La comparacion queda conceptual.",
            "",
        ])

    lines.extend([
        "Lectura: ENBOLSA ya tiene un benchmark por bloques y evidencia positiva documentada. Menendez, en cambio, genera pocas senales y no muestra estabilidad suficiente como para sostenerlo como eje empirico principal.",
        "",
        "## Archivos generados",
        "",
        "- `tables/summary_by_variant.csv`",
        "- `tables/symbol_stability.csv`",
        "- `tables/stage_counts_by_variant.csv`",
        "- `tables/block_reasons_by_variant.csv`",
        "- `tables/status_distribution_by_variant.csv`",
        "- `tables/period_metrics_by_variant.csv`",
        "- `tables/exit_breakdown_by_variant.csv`",
        "- `tables/trade_log_all.csv`",
        "- `tables/risk_audit_all.csv`",
        "- `tables/current_screener_rows.csv`",
        "- `run_meta.json`",
        "",
        "## Limitaciones",
        "",
        "- No se han optimizado reglas ni parametros.",
        "- No hay simulacion tick a tick ni swap.",
        "- El resultado depende de los datos SQL/MT5 locales y de la cache indicada.",
        "- `experimental_composite_x` es metodologicamente relevante, pero sigue sin edge demostrado.",
        "",
    ])

    (output_dir / "MENENDEZ_EMPIRICAL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run(args) -> None:
    repo_root = _repo_root()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    variants = [item.strip() for item in args.variants.split(",") if item.strip()]
    symbols = _parse_symbols(args)
    requested_symbols = symbols or get_symbols_by_group_normalized([args.group]).get(args.group, [])
    contract = get_experiment_contract({
        "group_name": args.group,
        "timeframe_ltf": args.timeframe_ltf,
        "timeframe_htf": args.timeframe_htf,
    })
    variant_specs = get_variant_specs(variants)

    summary_rows = []
    stage_frames = []
    block_frames = []
    status_frames = []
    symbol_frames = []
    period_frames = []
    trade_frames = []
    risk_frames = []
    exit_frames = []
    current_screener_frames = []
    portfolio_coverage_frames = []
    loaded_symbol_set = set()

    for variant_name, spec in variant_specs.items():
        merged_context = dict(spec.get("context_overrides", {}))
        strategy_defs = _merge_strategy_overrides(spec.get("strategy_overrides"))

        portfolio = cargar_portfolio_menendez(
            symbols=symbols,
            group_name=args.group,
            timeframe_ltf=args.timeframe_ltf,
            timeframe_htf=args.timeframe_htf,
            context_config=merged_context,
            indicator_config=None,
            verbose=not args.quiet,
            use_cache=args.use_cache,
            force_rebuild=args.force_rebuild,
            use_disk_cache=args.use_disk_cache,
            parallel=not args.no_parallel,
            max_workers=args.max_workers,
        )
        loaded_symbol_set.update(portfolio.keys())

        result = ejecutar_comparativa(
            portfolio,
            estrategias=strategy_defs,
            timeframe_ltf=args.timeframe_ltf,
            timeframe_htf=args.timeframe_htf,
            account_config=None,
            return_details=True,
            parallel=not args.no_parallel,
            max_workers=args.max_workers,
        )
        bundle = construir_bundle_experimental_menendez(
            portfolio=portfolio,
            resultado=result,
            variant_name=variant_name,
            classification=spec.get("classification", "resultado_valido"),
            notes=spec.get("notes", ""),
            context_config=merged_context,
            indicator_config=None,
            account_config=None,
            contract_overrides=contract,
            use_cache=args.use_cache,
            use_disk_cache=args.use_disk_cache,
            force_rebuild=args.force_rebuild,
        )

        variant_dir = tables_dir / variant_name
        trades = extraer_trades_resultado(result)
        summary = bundle["summary_metrics"].copy()
        if not summary.empty:
            summary["Variant"] = variant_name
            summary["VariantClass"] = spec.get("classification", "resultado_valido")
            summary_rows.append(summary)

        funnel = bundle["signal_funnel"]
        for key, frames, filename in (
            ("stage_counts", stage_frames, "stage_counts.csv"),
            ("block_reasons", block_frames, "block_reasons.csv"),
            ("status_distribution", status_frames, "status_distribution.csv"),
        ):
            frame = funnel.get(key, pd.DataFrame()).copy()
            if not frame.empty:
                frame["Variant"] = variant_name
                frame["VariantClass"] = spec.get("classification", "resultado_valido")
                frames.append(frame)
            _csv(variant_dir / filename, frame)

        coverage = resumir_portfolio_cargado(portfolio)
        coverage["Variant"] = variant_name
        portfolio_coverage_frames.append(coverage)
        _csv(variant_dir / "portfolio_coverage.csv", coverage)

        stability = _symbol_stability_table(variant_name, portfolio, trades, funnel)
        symbol_frames.append(stability)
        _csv(variant_dir / "symbol_stability.csv", stability)

        if not trades.empty and "entry_time" in trades.columns:
            period_metrics = resumir_periodos(trades)
        else:
            period_metrics = pd.DataFrame()
        if not period_metrics.empty:
            period_metrics["Variant"] = variant_name
            period_frames.append(period_metrics)
        _csv(variant_dir / "period_metrics.csv", period_metrics)

        trade_log = bundle["trade_log"].copy()
        if not trade_log.empty:
            trade_log["Variant"] = variant_name
            trade_frames.append(trade_log)
        _csv(variant_dir / "trade_log.csv", trade_log)

        risk_audit = bundle["risk_audit"].copy()
        if not risk_audit.empty:
            risk_audit["Variant"] = variant_name
            risk_frames.append(risk_audit)
        _csv(variant_dir / "risk_audit.csv", risk_audit)

        current_screener = bundle.get("screener_rows_current", pd.DataFrame()).copy()
        if not current_screener.empty:
            current_screener["Variant"] = variant_name
            current_screener_frames.append(current_screener)
        _csv(variant_dir / "current_screener_rows.csv", current_screener)

        breakdowns = generar_desgloses_resultado(result)
        exits = breakdowns.get("salidas", pd.DataFrame()).copy()
        if not exits.empty:
            exits["Variant"] = variant_name
            exit_frames.append(exits)
        _csv(variant_dir / "exit_breakdown.csv", exits)

        _json(variant_dir / "run_meta.json", bundle["run_meta"])

        del portfolio, result, bundle, trades
        gc.collect()

    summary_table = pd.concat(summary_rows, ignore_index=True) if summary_rows else pd.DataFrame()
    stage_counts = pd.concat(stage_frames, ignore_index=True) if stage_frames else pd.DataFrame()
    block_reasons = pd.concat(block_frames, ignore_index=True) if block_frames else pd.DataFrame()
    status_distribution = pd.concat(status_frames, ignore_index=True) if status_frames else pd.DataFrame()
    symbol_stability = pd.concat(symbol_frames, ignore_index=True) if symbol_frames else pd.DataFrame()
    period_metrics = pd.concat(period_frames, ignore_index=True) if period_frames else pd.DataFrame()
    trade_log_all = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    risk_audit_all = pd.concat(risk_frames, ignore_index=True) if risk_frames else pd.DataFrame()
    exit_breakdown = pd.concat(exit_frames, ignore_index=True) if exit_frames else pd.DataFrame()
    current_screener = pd.concat(current_screener_frames, ignore_index=True) if current_screener_frames else pd.DataFrame()
    portfolio_coverage = pd.concat(portfolio_coverage_frames, ignore_index=True) if portfolio_coverage_frames else pd.DataFrame()

    _csv(tables_dir / "summary_by_variant.csv", summary_table)
    _csv(tables_dir / "symbol_stability.csv", symbol_stability)
    _csv(tables_dir / "stage_counts_by_variant.csv", stage_counts)
    _csv(tables_dir / "block_reasons_by_variant.csv", block_reasons)
    _csv(tables_dir / "status_distribution_by_variant.csv", status_distribution)
    _csv(tables_dir / "period_metrics_by_variant.csv", period_metrics)
    _csv(tables_dir / "trade_log_all.csv", trade_log_all)
    _csv(tables_dir / "risk_audit_all.csv", risk_audit_all)
    _csv(tables_dir / "exit_breakdown_by_variant.csv", exit_breakdown)
    _csv(tables_dir / "current_screener_rows.csv", current_screener)
    _csv(tables_dir / "portfolio_coverage_by_variant.csv", portfolio_coverage)

    command = (
        "python -m backtests.menendez.run_empirical_close "
        f"--output-dir {args.output_dir} "
        f"--variants {','.join(variants)} "
        f"--group \"{args.group}\" "
        f"--timeframe-ltf {args.timeframe_ltf} --timeframe-htf {args.timeframe_htf}"
    )
    if args.symbols:
        command += f" --symbols {args.symbols}"
    if args.limit_symbols:
        command += f" --limit-symbols {args.limit_symbols}"
    if args.no_parallel:
        command += " --no-parallel"
    if args.max_workers:
        command += f" --max-workers {args.max_workers}"

    run_meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "group_name": args.group,
        "timeframe_ltf": args.timeframe_ltf,
        "timeframe_htf": args.timeframe_htf,
        "variants": variants,
        "requested_symbols": len(requested_symbols),
        "loaded_symbols": len(loaded_symbol_set),
        "symbols": sorted(loaded_symbol_set),
        "use_cache": args.use_cache,
        "use_disk_cache": args.use_disk_cache,
        "force_rebuild": args.force_rebuild,
        "parallel": not args.no_parallel,
        "max_workers": args.max_workers,
    }
    _json(output_dir / "run_meta.json", run_meta)

    enbolsa_reference = _load_enbolsa_reference(repo_root)
    _write_report(
        output_dir=output_dir,
        run_meta=run_meta,
        summary_table=summary_table,
        symbol_stability=symbol_stability,
        stage_counts=stage_counts,
        block_reasons=block_reasons,
        enbolsa_reference=enbolsa_reference,
    )
    print(f"Artifacts escritos en: {output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cierre empirico reproducible de la linea Menendez.")
    parser.add_argument("--output-dir", default="artifacts/menendez/cierre_empirico_2026-05-14")
    parser.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    parser.add_argument("--group", default=DEFAULT_GROUP)
    parser.add_argument("--timeframe-ltf", default=DEFAULT_TIMEFRAME_LTF)
    parser.add_argument("--timeframe-htf", default=DEFAULT_TIMEFRAME_HTF)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit-symbols", type=int, default=0)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--no-parallel", action="store_true")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--no-cache", dest="use_cache", action="store_false")
    parser.add_argument("--no-disk-cache", dest="use_disk_cache", action="store_false")
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(use_cache=True, use_disk_cache=True)
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())

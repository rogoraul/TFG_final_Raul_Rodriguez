from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table, safe_id


DEFAULT_INPUT_DIR = Path("artifacts/tfg/wavecount_live_parameter_grid_v2_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_visual_manual_audit_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_VISUAL_MANUAL_AUDIT.md")
FOCUSED_CONFIGS = (
    "baseline_actual",
    "very_conservative_diagnostic",
    "time_hard_a",
    "time_hard_b",
)
VISUAL_CONFIGS = (
    "baseline_actual",
    "very_conservative_diagnostic",
    "time_hard_a",
    "time_hard_b",
    "market_group_probe",
)


@dataclass(frozen=True)
class VisualManualAuditConfig:
    input_dir: Path = DEFAULT_INPUT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    focused_configs: tuple[str, ...] = FOCUSED_CONFIGS
    visual_configs: tuple[str, ...] = VISUAL_CONFIGS


@dataclass(frozen=True)
class VisualManualAuditResult:
    visual_chart_audit: pd.DataFrame
    problem_cut_audit: pd.DataFrame
    focused_config_comparison: pd.DataFrame
    append_only_implications: pd.DataFrame
    decision_summary: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_visual_manual_audit(config: VisualManualAuditConfig | None = None) -> VisualManualAuditResult:
    config = config or VisualManualAuditConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_grid_v2_sources(config.input_dir)
    visual = build_visual_chart_audit(config, sources)
    problem_cuts = build_problem_cut_audit(sources)
    focused = build_focused_config_comparison(config, sources)
    append_only = build_append_only_implications(problem_cuts, focused)
    decision_summary = build_decision_summary(visual, problem_cuts, focused, append_only)
    decision = str(decision_summary.iloc[0]["decision"])
    issues = build_issues_or_risks(visual, problem_cuts, focused, append_only, decision)
    run_meta = build_run_meta(generated_at, config, visual, problem_cuts, decision)
    written = write_outputs(
        config=config,
        visual_chart_audit=visual,
        problem_cut_audit=problem_cuts,
        focused_config_comparison=focused,
        append_only_implications=append_only,
        decision_summary=decision_summary,
        issues_or_risks=issues,
        run_meta=run_meta,
    )
    write_docs(config, visual, problem_cuts, focused, append_only, decision_summary, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_VISUAL_MANUAL_AUDIT.md"
    return VisualManualAuditResult(
        visual_chart_audit=visual,
        problem_cut_audit=problem_cuts,
        focused_config_comparison=focused,
        append_only_implications=append_only,
        decision_summary=decision_summary,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_grid_v2_sources(input_dir: Path) -> dict[str, pd.DataFrame | dict[str, Any] | Path]:
    required = {
        "config_comparison": input_dir / "config_comparison_v2.csv",
        "candidate_evaluation": input_dir / "candidate_evaluation.csv",
        "market_group_sensitivity": input_dir / "market_group_sensitivity.csv",
        "pivot_stability": input_dir / "pivot_stability_by_config.csv",
        "label_transition": input_dir / "label_transition_by_config.csv",
        "anti_lookahead": input_dir / "anti_lookahead_by_config.csv",
        "recommended_next_action": input_dir / "recommended_next_action.csv",
        "issues_or_risks": input_dir / "issues_or_risks.csv",
        "chart_review": input_dir / "chart_review.csv",
        "run_meta": input_dir / "run_meta.json",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing grid v2 audit inputs: {missing}")
    return {
        "input_dir": input_dir,
        "config_comparison": pd.read_csv(required["config_comparison"]),
        "candidate_evaluation": pd.read_csv(required["candidate_evaluation"]),
        "market_group_sensitivity": pd.read_csv(required["market_group_sensitivity"]),
        "pivot_stability": pd.read_csv(required["pivot_stability"]),
        "label_transition": pd.read_csv(required["label_transition"]),
        "anti_lookahead": pd.read_csv(required["anti_lookahead"]),
        "recommended_next_action": pd.read_csv(required["recommended_next_action"]),
        "issues_or_risks": pd.read_csv(required["issues_or_risks"]),
        "chart_review": pd.read_csv(required["chart_review"]),
        "run_meta": json.loads(required["run_meta"].read_text(encoding="utf-8")),
    }


def build_visual_chart_audit(config: VisualManualAuditConfig, sources: dict[str, Any]) -> pd.DataFrame:
    chart_review = sources["chart_review"].copy()
    pivot = sources["pivot_stability"].copy()
    comparison = sources["config_comparison"].copy()
    sensitivity = sources["market_group_sensitivity"].copy()
    known_configs = sorted(set(comparison["config_name"].astype(str)), key=len, reverse=True)
    known_symbols = sorted(set(pivot["symbol"].astype(str)), key=len, reverse=True)
    rows = []
    for record in chart_review.to_dict(orient="records"):
        chart_file = str(record["chart_file"])
        name = Path(chart_file).name
        config_name = infer_config_name(name, known_configs)
        if config_name not in config.visual_configs:
            continue
        symbol = infer_symbol(name, known_symbols)
        market_group = infer_market_group(symbol, pivot)
        timeframe = infer_timeframe(symbol, pivot)
        config_metrics = comparison[comparison["config_name"] == config_name]
        group_metrics = sensitivity[(sensitivity["config_name"] == config_name) & (sensitivity["market_group"] == market_group)]
        metric = config_metrics.iloc[0].to_dict() if not config_metrics.empty else {}
        group_metric = group_metrics.iloc[0].to_dict() if not group_metrics.empty else {}
        rows.append(
            {
                "chart_file": chart_file,
                "config_name": config_name,
                "symbol": symbol,
                "market_group": market_group,
                "timeframe": timeframe,
                "manual_readability": manual_readability(config_name, metric, group_metric),
                "pivot_density_visual": pivot_density_visual(config_name, metric, group_metric),
                "lag_visual_concern": lag_visual_concern(metric),
                "structure_label_plausible": structure_label_plausible(config_name, metric),
                "notes": visual_notes(config_name, symbol, metric, group_metric),
            }
        )
    return pd.DataFrame(rows)


def infer_config_name(filename: str, known_configs: list[str]) -> str:
    for config_name in known_configs:
        if filename.startswith(f"{config_name}_"):
            return config_name
    return ""


def infer_symbol(filename: str, known_symbols: list[str]) -> str:
    for symbol in known_symbols:
        safe_symbol = safe_id(symbol)
        if f"_{safe_symbol}_" in filename:
            return symbol
    return ""


def infer_market_group(symbol: str, pivot_stability: pd.DataFrame) -> str:
    if not symbol:
        return ""
    if "market_group" in pivot_stability.columns:
        part = pivot_stability[pivot_stability["symbol"].astype(str) == symbol]
        if not part.empty and str(part.iloc[0].get("market_group", "")).strip():
            return str(part.iloc[0].get("market_group", ""))
    upper = symbol.upper()
    if upper.startswith(("EUR", "GBP", "USD", "AUD", "NZD", "CAD", "CHF", "JPY")):
        return "Forex Majors"
    if "XAU" in upper or "GOLD" in upper:
        return "Metals"
    if "US500" in upper or "SPX" in upper or "NAS" in upper or "DAX" in upper:
        return "Index"
    return "Unknown"


def infer_timeframe(symbol: str, pivot_stability: pd.DataFrame) -> str:
    if not symbol:
        return ""
    part = pivot_stability[pivot_stability["symbol"].astype(str) == symbol]
    if part.empty:
        return ""
    return str(part.iloc[0].get("timeframe", ""))


def manual_readability(config_name: str, metric: dict[str, Any], group_metric: dict[str, Any]) -> str:
    if config_name == "baseline_actual":
        return "too_noisy"
    if config_name == "time_hard_b":
        return "late_but_readable"
    if config_name == "time_hard_a":
        return "borderline"
    if config_name == "very_conservative_diagnostic":
        return "borderline"
    if config_name == "market_group_probe":
        noisy = float(group_metric.get("too_noisy_pct", 1.0))
        return "borderline" if noisy <= 0.25 else "too_noisy"
    return "borderline"


def pivot_density_visual(config_name: str, metric: dict[str, Any], group_metric: dict[str, Any]) -> str:
    structural_density = float(group_metric.get("structural_pivots_per_100_bars", metric.get("structural_pivots_per_100_bars", 0.0)))
    if config_name == "baseline_actual" or structural_density > 3.0:
        return "high"
    if structural_density < 0.9:
        return "low"
    return "medium"


def lag_visual_concern(metric: dict[str, Any]) -> str:
    late_pct = float(metric.get("late_cut_pct", 0.0))
    if late_pct >= 0.9:
        return "high"
    if late_pct >= 0.4:
        return "moderate"
    return "none"


def structure_label_plausible(config_name: str, metric: dict[str, Any]) -> str:
    if config_name == "baseline_actual":
        return "false"
    if float(metric.get("completed_impulse_pct", 0.0)) > 0.75:
        return "unclear"
    if float(metric.get("late_cut_pct", 0.0)) >= 0.9:
        return "unclear"
    return "true"


def visual_notes(config_name: str, symbol: str, metric: dict[str, Any], group_metric: dict[str, Any]) -> str:
    if config_name == "baseline_actual":
        return "Pivot clutter is visually obvious; completed impulse label is not credible as live context."
    if config_name == "time_hard_b":
        return (
            "Visually cleaner and swing-level pivots are readable, but the high confirmation lag means the context is stale/provisional rather than live-ready."
        )
    if config_name == "time_hard_a":
        return "Less extreme than time_hard_b and still fairly readable, but lag is still high and some noise remains."
    if config_name == "very_conservative_diagnostic":
        return "Cleaner than baseline, but still less stable/noise-controlled than time-filtered configs."
    if config_name == "market_group_probe":
        return "Useful diagnostic for market-group differences; not stable enough as a global configuration."
    return "Manual review required before promotion."


def build_problem_cut_audit(sources: dict[str, Any]) -> pd.DataFrame:
    pivot = sources["pivot_stability"].copy()
    transitions = sources["label_transition"].copy()
    focus = pivot[pivot["config_name"] == "time_hard_b"].copy()
    if focus.empty:
        return pd.DataFrame()
    merged = focus.merge(
        transitions[transitions["config_name"] == "time_hard_b"][
            ["symbol", "timeframe", "cut_number", "transition_type", "phase_changed", "structure_phase"]
        ],
        on=["symbol", "timeframe", "cut_number"],
        how="left",
        suffixes=("", "_transition"),
    )
    rows = []
    for record in merged.to_dict(orient="records"):
        problems = []
        if truthy(record.get("unstable_pivots")):
            problems.append("unstable_pivots")
        if truthy(record.get("late_confirmation")):
            problems.append("late_confirmation")
        if truthy(record.get("phase_changed")):
            problems.append("label_change")
        if str(record.get("transition_type", "")) == "abrupt_reclassification":
            problems.append("abrupt_transition")
        if str(record.get("structure_phase", "")) == "completed_impulse_candidate":
            problems.append("completed_impulse_candidate")
        if not problems:
            continue
        rows.append(
            {
                "config_name": "time_hard_b",
                "symbol": record.get("symbol", ""),
                "market_group": infer_market_group(str(record.get("symbol", "")), focus),
                "cut_number": int(record.get("cut_number", 0)),
                "as_of_bar_time": record.get("as_of_bar_time", ""),
                "structure_phase": record.get("structure_phase", record.get("structure_phase_transition", "")),
                "detected_pivots": int(record.get("detected_pivots", 0)),
                "structural_pivots": int(record.get("structural_pivots", 0)),
                "late_confirmation": truthy(record.get("late_confirmation")),
                "unstable_pivots": truthy(record.get("unstable_pivots")),
                "transition_type": record.get("transition_type", ""),
                "problem_type": ";".join(problems),
                "severity": problem_severity(problems),
                "interpretation": problem_interpretation(problems),
            }
        )
    return pd.DataFrame(rows).sort_values(["severity", "symbol", "cut_number"], ascending=[False, True, True]).reset_index(drop=True)


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def problem_severity(problems: list[str]) -> str:
    if "abrupt_transition" in problems or ("unstable_pivots" in problems and "late_confirmation" in problems):
        return "high"
    if "unstable_pivots" in problems or "label_change" in problems:
        return "medium"
    return "low"


def problem_interpretation(problems: list[str]) -> str:
    if "unstable_pivots" in problems and "late_confirmation" in problems:
        return "Readable pivots are obtained by waiting too long; append-only SQL must preserve this as provisional/stale context."
    if "abrupt_transition" in problems:
        return "Abrupt label movement requires manual review before any staging."
    if "completed_impulse_candidate" in problems:
        return "Completed impulse remains a hypothesis, not an operational conclusion."
    return "Problem is diagnostic and blocks promotion until broader review."


def build_focused_config_comparison(config: VisualManualAuditConfig, sources: dict[str, Any]) -> pd.DataFrame:
    comparison = sources["config_comparison"].copy()
    candidate = sources["candidate_evaluation"].copy()
    focus = comparison[comparison["config_name"].isin(config.focused_configs)].copy()
    focus = focus.merge(
        candidate[["config_name", "failed_criteria", "candidate_label"]],
        on="config_name",
        how="left",
    )
    focus["visual_verdict"] = focus.apply(focused_visual_verdict, axis=1)
    focus["lag_acceptability"] = focus["late_cut_pct"].map(lambda value: "not_acceptable" if float(value) > 0.5 else "acceptable")
    focus["sql_blocker"] = focus.apply(
        lambda row: bool(
            not truthy(row["candidate_pass"])
            or float(row["late_cut_pct"]) > 0.5
            or float(row["unstable_cut_pct"]) > 0.25
        ),
        axis=1,
    )
    return focus.sort_values("rank").reset_index(drop=True)


def focused_visual_verdict(row: pd.Series) -> str:
    name = str(row["config_name"])
    if name == "baseline_actual":
        return "discard_for_live_readability"
    if name == "very_conservative_diagnostic":
        return "inferior_to_time_filters"
    if name == "time_hard_a":
        return "broader_review_candidate_but_still_late"
    if name == "time_hard_b":
        return "best_visual_readability_but_too_late_and_unstable"
    return "manual_review_required"


def build_append_only_implications(problem_cuts: pd.DataFrame, focused: pd.DataFrame) -> pd.DataFrame:
    time_b = focused[focused["config_name"] == "time_hard_b"]
    unstable_count = int(problem_cuts["unstable_pivots"].astype(bool).sum()) if not problem_cuts.empty else 0
    phase_changes = int((problem_cuts["problem_type"].astype(str).str.contains("label_change")).sum()) if not problem_cuts.empty else 0
    late_count = int(problem_cuts["late_confirmation"].astype(bool).sum()) if not problem_cuts.empty else 0
    return pd.DataFrame(
        [
            {
                "question": "Can label changes be accepted as live evolution?",
                "answer": "yes_but_only_append_only",
                "implication": "Each hypothesis should be inserted as a new row; prior rows must not be rewritten.",
                "recommended_fields": "prior_context_id;supersedes_context_id;revision_reason;label_stability_status",
            },
            {
                "question": "Do disappearing/replaced structural pivots block naive SQL staging?",
                "answer": "yes",
                "implication": f"time_hard_b has {unstable_count} unstable cut rows; SQL needs stability metadata before dashboard use.",
                "recommended_fields": "pivot_set_hash;structural_pivot_count;unstable_pivots_flag;revision_reason",
            },
            {
                "question": "Is high confirmation lag tolerable?",
                "answer": "only_if_displayed_as_stale_or_provisional",
                "implication": f"time_hard_b has {late_count} late-confirmation rows; dashboard must not present it as fresh live context.",
                "recommended_fields": "confirmation_lag_bars;lag_status;context_freshness_status",
            },
            {
                "question": "Should current and historical hypotheses be separated?",
                "answer": "yes",
                "implication": "Future SQL should separate current_hypothesis views from historical_hypothesis_audit rows.",
                "recommended_fields": "current_hypothesis;historical_hypothesis_audit;as_of_bar_time;detected_at",
            },
            {
                "question": "Can provisional labels be shown in dashboard?",
                "answer": "yes_after_stability_model",
                "implication": "A dashboard could show provisional/stale labels, but only after append-only stability semantics are designed.",
                "recommended_fields": "hypothesis_status;label_stability_status;can_filter_trade=false",
            },
        ]
    )


def build_decision_summary(
    visual: pd.DataFrame,
    problem_cuts: pd.DataFrame,
    focused: pd.DataFrame,
    append_only: pd.DataFrame,
) -> pd.DataFrame:
    time_b = focused[focused["config_name"] == "time_hard_b"].iloc[0]
    time_a = focused[focused["config_name"] == "time_hard_a"].iloc[0]
    decision = "needs_append_only_stability_model"
    rationale = (
        "`time_hard_b` is visually cleaner than baseline/v1 and worth broader review, "
        "but late confirmation and pivot instability block SQL staging until append-only stability semantics exist."
    )
    if float(time_b["late_cut_pct"]) >= 1.0 and float(time_b["unstable_cut_pct"]) > 0.5:
        decision = "needs_append_only_stability_model"
    if float(time_a["late_cut_pct"]) < float(time_b["late_cut_pct"]) and float(time_a["unstable_cut_pct"]) < float(time_b["unstable_cut_pct"]):
        preferred_next_config = "time_hard_a"
        next_review = "compare_time_hard_a_and_time_hard_b_on_more_real_cuts"
    else:
        preferred_next_config = "time_hard_b"
        next_review = "broader_time_hard_b_review_with_append_only_stability"
    return pd.DataFrame(
        [
            {
                "decision": decision,
                "preferred_next_config": preferred_next_config,
                "time_hard_b_visual_status": "late_but_readable",
                "time_hard_a_visual_status": "borderline_less_extreme",
                "candidate_live_readability_config_v0": False,
                "sql_staging_allowed": False,
                "dashboard_allowed": False,
                "signals_allowed": False,
                "next_review": next_review,
                "rationale": rationale,
            }
        ]
    )


def build_issues_or_risks(
    visual: pd.DataFrame,
    problem_cuts: pd.DataFrame,
    focused: pd.DataFrame,
    append_only: pd.DataFrame,
    decision: str,
) -> pd.DataFrame:
    time_b = focused[focused["config_name"] == "time_hard_b"].iloc[0]
    time_a = focused[focused["config_name"] == "time_hard_a"].iloc[0]
    return pd.DataFrame(
        [
            {
                "severity": "medium",
                "risk": "late_confirmation",
                "description": f"`time_hard_b` has late_confirmation in {float(time_b['late_cut_pct']):.1%} of cuts.",
                "recommendation": "Treat as stale/provisional context, not fresh live structure.",
            },
            {
                "severity": "medium",
                "risk": "append_only_instability",
                "description": f"`time_hard_b` has unstable_pivots in {int(time_b['unstable_pivot_cuts'])}/40 cuts.",
                "recommendation": "Design append-only stability metadata before SQL staging.",
            },
            {
                "severity": "low",
                "risk": "time_hard_a_tradeoff",
                "description": f"`time_hard_a` has less instability ({int(time_a['unstable_pivot_cuts'])}/40) but more noise ({int(time_a['too_noisy_cuts'])}/40).",
                "recommendation": "Keep it as comparison candidate for broader review, not as approved config.",
            },
            {
                "severity": "medium",
                "risk": "visual_review_scope",
                "description": f"Reviewed {len(visual)} existing diagnostic charts; this is not full market validation.",
                "recommendation": "Review more cuts/time windows before any SQL/dashboard design.",
            },
            {
                "severity": "blocking",
                "risk": "no_candidate",
                "description": f"Final decision `{decision}` does not declare `candidate_live_readability_config_v0`.",
                "recommendation": "Keep WaveCount live out of SQL/dashboard until stability model and broader review are done.",
            },
        ]
    )


def build_run_meta(
    generated_at: str,
    config: VisualManualAuditConfig,
    visual: pd.DataFrame,
    problem_cuts: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_visual_manual_audit",
        "source_audited": str(config.input_dir),
        "configs_reviewed": list(config.visual_configs),
        "focused_configs": list(config.focused_configs),
        "charts_reviewed": int(len(visual)),
        "problem_cut_rows": int(len(problem_cuts)),
        "decision": decision,
        "safety": {
            "real_sql_executed": False,
            "ddl_executed": False,
            "mt5_connected": False,
            "backtests_executed": False,
            "signals_generated": False,
            "dashboard_implemented": False,
            "telegram_implemented": False,
            "bot_implemented": False,
        },
        "limitations": [
            "Manual/visual audit is lightweight and based on existing diagnostic charts.",
            "No PnL, no backtest, no signal generation and no SQL writes.",
            "Decision is methodological for future review, not operational approval.",
        ],
    }


def write_outputs(
    *,
    config: VisualManualAuditConfig,
    visual_chart_audit: pd.DataFrame,
    problem_cut_audit: pd.DataFrame,
    focused_config_comparison: pd.DataFrame,
    append_only_implications: pd.DataFrame,
    decision_summary: pd.DataFrame,
    issues_or_risks: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "visual_chart_audit": config.output_dir / "visual_chart_audit.csv",
        "problem_cut_audit": config.output_dir / "problem_cut_audit.csv",
        "focused_config_comparison": config.output_dir / "focused_config_comparison.csv",
        "append_only_implications": config.output_dir / "append_only_implications.csv",
        "decision_summary": config.output_dir / "decision_summary.csv",
        "issues_or_risks": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    visual_chart_audit.to_csv(paths["visual_chart_audit"], index=False)
    problem_cut_audit.to_csv(paths["problem_cut_audit"], index=False)
    focused_config_comparison.to_csv(paths["focused_config_comparison"], index=False)
    append_only_implications.to_csv(paths["append_only_implications"], index=False)
    decision_summary.to_csv(paths["decision_summary"], index=False)
    issues_or_risks.to_csv(paths["issues_or_risks"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    config: VisualManualAuditConfig,
    visual: pd.DataFrame,
    problem_cuts: pd.DataFrame,
    focused: pd.DataFrame,
    append_only: pd.DataFrame,
    decision_summary: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    doc = f"""# WaveCount Live Visual Manual Audit

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta fase revisa visual y manualmente los resultados del grid v2 de
`wavecount_live_context_v0`. No es un backtest, no mide edge, no genera senales,
no filtra ENBOLSA y no toca SQL real.

## Graficos Revisados

Se revisan {len(visual)} graficos existentes para baseline,
`very_conservative_diagnostic`, `time_hard_a`, `time_hard_b` y
`market_group_probe`.

{markdown_table(visual)}

## Cortes Problematicos

{markdown_table(problem_cuts)}

## Comparacion Focalizada

{markdown_table(focused)}

## Implicaciones Append-Only

{markdown_table(append_only)}

## Decision Summary

{markdown_table(decision_summary)}

## Riesgos

{markdown_table(issues)}

## Lectura Tecnica

- `baseline_actual` queda descartado visualmente por saturacion de pivotes.
- `time_hard_b` es el mas limpio y legible, pero llega tarde y no es estable
  suficiente para SQL/dashboard.
- `time_hard_a` merece mantenerse como comparador porque es menos extremo, pero
  tampoco es candidata.
- La inestabilidad de pivotes obliga a pensar en un modelo append-only antes de
  staging: no reescribir etiquetas pasadas, registrar supersedencias y mostrar
  estados provisionales/stale.

## Seguridad

- `real_sql_executed=false`
- `ddl_executed=false`
- `mt5_connected=false`
- `backtests_executed=false`
- `signals_generated=false`
- `dashboard_implemented=false`
- `telegram_implemented=false`
- `bot_implemented=false`

## Que Sigue Bloqueado

- SQL staging automatico de WaveCount live.
- Dashboard con WaveCount live.
- Telegram/bot.
- MT5.
- Cualquier senal o filtro operativo derivado de WaveCount.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_LIVE_VISUAL_MANUAL_AUDIT.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit WaveCount live grid v2 charts and append-only implications.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_visual_manual_audit(
        VisualManualAuditConfig(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "charts_reviewed": int(len(result.visual_chart_audit)),
                "problem_cut_rows": int(len(result.problem_cut_audit)),
                "output_dir": str(args.output_dir),
                "real_sql_executed": False,
                "mt5_connected": False,
                "backtests_executed": False,
                "signals_generated": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

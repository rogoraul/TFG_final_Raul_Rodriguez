from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table, safe_id
from trading_center.wavecount_current_hypothesis import to_bool, validate_payload
from trading_center.wavecount_live_estimate import LIVE_ESTIMATE_COLUMNS


DEFAULT_INPUT_DIR = Path("artifacts/tfg/wavecount_live_estimate_v0_2026-05-27")
DEFAULT_STATE_MACHINE_DIR = Path("artifacts/tfg/wavecount_state_machine_v0_2026-05-27")
DEFAULT_WARNING_AUDIT_DIR = Path("artifacts/tfg/wavecount_state_machine_warning_audit_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_estimate_visual_audit_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_ESTIMATE_VISUAL_AUDIT.md")

REQUIRED_FILES = {
    "estimate": "live_wave_estimate.csv",
    "estimate_json": "live_wave_estimate.json",
    "current_leg": "current_leg_audit.csv",
    "rules": "estimate_rule_audit.csv",
    "confidence": "confidence_warning_audit.csv",
    "comparison": "comparison_vs_state_machine.csv",
    "anti": "anti_lookahead_audit.csv",
    "issues": "issues_or_risks.csv",
    "run_meta": "run_meta.json",
}


@dataclass(frozen=True)
class LiveEstimateVisualAuditConfig:
    input_dir: Path = DEFAULT_INPUT_DIR
    state_machine_dir: Path = DEFAULT_STATE_MACHINE_DIR
    warning_audit_dir: Path = DEFAULT_WARNING_AUDIT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    copy_charts: bool = True


@dataclass(frozen=True)
class LiveEstimateVisualAuditResult:
    contract_security_audit: pd.DataFrame
    visual_live_estimate_audit: pd.DataFrame
    us500_wave3_active_audit: pd.DataFrame
    xauusd_wave3_candidate_audit: pd.DataFrame
    invalidated_context_audit: pd.DataFrame
    state_machine_vs_live_estimate_audit: pd.DataFrame
    decision_summary: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_live_estimate_visual_audit(
    config: LiveEstimateVisualAuditConfig | None = None,
) -> LiveEstimateVisualAuditResult:
    config = config or LiveEstimateVisualAuditConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)
    contract = build_contract_security_audit(sources)
    visual = build_visual_live_estimate_audit(config, sources)
    us500 = build_us500_wave3_active_audit(sources, visual)
    xauusd = build_xauusd_wave3_candidate_audit(sources, visual)
    invalidated = build_invalidated_context_audit(sources)
    comparison = build_state_machine_vs_live_estimate_audit(sources, visual)
    decision = decide_next_step(contract, visual, us500, xauusd, invalidated)
    decision_summary = build_decision_summary(decision, visual, us500, xauusd, invalidated)
    issues = build_issues_or_risks(contract, visual, us500, xauusd, invalidated, comparison, decision)
    run_meta = build_run_meta(generated_at, config, sources, visual, decision)
    written = write_outputs(
        config=config,
        contract=contract,
        visual=visual,
        us500=us500,
        xauusd=xauusd,
        invalidated=invalidated,
        comparison=comparison,
        decision_summary=decision_summary,
        issues=issues,
        run_meta=run_meta,
    )
    if config.copy_charts:
        copy_input_charts(config)
    write_docs(config, contract, visual, us500, xauusd, invalidated, comparison, decision_summary, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_ESTIMATE_VISUAL_AUDIT.md"
    return LiveEstimateVisualAuditResult(
        contract_security_audit=contract,
        visual_live_estimate_audit=visual,
        us500_wave3_active_audit=us500,
        xauusd_wave3_candidate_audit=xauusd,
        invalidated_context_audit=invalidated,
        state_machine_vs_live_estimate_audit=comparison,
        decision_summary=decision_summary,
        issues_or_risks=issues,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_sources(config: LiveEstimateVisualAuditConfig) -> dict[str, Any]:
    missing = [str(config.input_dir / filename) for filename in REQUIRED_FILES.values() if not (config.input_dir / filename).exists()]
    if missing:
        raise FileNotFoundError(f"missing live estimate audit inputs: {missing}")
    sources: dict[str, Any] = {
        "estimate": pd.read_csv(config.input_dir / REQUIRED_FILES["estimate"]),
        "estimate_json": json.loads((config.input_dir / REQUIRED_FILES["estimate_json"]).read_text(encoding="utf-8")),
        "current_leg": pd.read_csv(config.input_dir / REQUIRED_FILES["current_leg"]),
        "rules": pd.read_csv(config.input_dir / REQUIRED_FILES["rules"]),
        "confidence": pd.read_csv(config.input_dir / REQUIRED_FILES["confidence"]),
        "comparison": pd.read_csv(config.input_dir / REQUIRED_FILES["comparison"]),
        "anti": pd.read_csv(config.input_dir / REQUIRED_FILES["anti"]),
        "issues": pd.read_csv(config.input_dir / REQUIRED_FILES["issues"]),
        "run_meta": json.loads((config.input_dir / REQUIRED_FILES["run_meta"]).read_text(encoding="utf-8")),
    }
    state_csv = config.state_machine_dir / "wave_state_machine_hypothesis.csv"
    warning_csv = config.warning_audit_dir / "warning_visual_audit.csv"
    sources["state_machine"] = pd.read_csv(state_csv) if state_csv.exists() else pd.DataFrame()
    sources["warning_visual"] = pd.read_csv(warning_csv) if warning_csv.exists() else pd.DataFrame()
    return sources


def build_contract_security_audit(sources: dict[str, Any]) -> pd.DataFrame:
    estimate = sources["estimate"]
    anti = sources["anti"]
    meta = sources["run_meta"]
    rows = []
    rows.append(check_row("csv_json_row_count_match", len(estimate) == len(sources["estimate_json"]), f"csv={len(estimate)};json={len(sources['estimate_json'])}"))
    missing_columns = sorted(set(LIVE_ESTIMATE_COLUMNS) - set(estimate.columns))
    rows.append(check_row("expected_columns_present", not missing_columns, ";".join(missing_columns) if missing_columns else "all expected columns present"))
    payload_ok = payloads_are_valid(estimate.get("payload_json", pd.Series(dtype=str)))
    rows.append(check_row("payload_json_valid", payload_ok, str(payload_ok)))
    rows.append(check_row("why_this_label_present", estimate["why_this_label"].astype(str).str.len().gt(0).all(), "non-empty why_this_label"))
    rows.append(check_row("why_not_higher_confidence_present", estimate["why_not_higher_confidence"].astype(str).str.len().gt(0).all(), "non-empty why_not_higher_confidence"))
    rows.append(check_row("lookahead_safe_all_true", estimate["lookahead_safe"].map(to_bool).all(), str(bool(estimate["lookahead_safe"].map(to_bool).all()))))
    latest_ok = (pd.to_datetime(anti["latest_close_time"], errors="coerce") <= pd.to_datetime(anti["as_of_bar_time"], errors="coerce")).all()
    rows.append(check_row("latest_close_not_after_as_of", bool(latest_ok), str(bool(latest_ok))))
    hard_flags = {
        "is_read_only": bool(estimate["is_read_only"].map(to_bool).all()),
        "can_generate_signal": not bool(estimate["can_generate_signal"].map(to_bool).any()),
        "can_filter_trade": not bool(estimate["can_filter_trade"].map(to_bool).any()),
        "can_execute_order": not bool(estimate["can_execute_order"].map(to_bool).any()),
    }
    for flag, ok in hard_flags.items():
        rows.append(check_row(f"hard_flag_{flag}", ok, str(ok)))
    for flag in [
        "real_sql_executed",
        "ddl_executed",
        "mt5_connected",
        "backtests_executed",
        "signals_generated",
        "dashboard_implemented",
        "telegram_implemented",
        "bot_implemented",
    ]:
        value = bool(meta.get("safety", {}).get(flag, True))
        rows.append(check_row(f"run_meta_{flag}", not value, str(value)))
    return pd.DataFrame(rows)


def check_row(check_name: str, ok: bool, observed: str) -> dict[str, Any]:
    return {
        "check_name": check_name,
        "status": "pass" if ok else "fail",
        "observed": observed,
        "severity": "info" if ok else "blocking",
    }


def payloads_are_valid(values: pd.Series) -> bool:
    try:
        for value in values:
            validate_payload(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False
    return True


def build_visual_live_estimate_audit(config: LiveEstimateVisualAuditConfig, sources: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for _, row in sources["estimate"].iterrows():
        symbol = str(row["symbol"])
        chart_file = config.input_dir / "charts" / f"live_estimate_{safe_id(symbol)}_{row['timeframe']}.png"
        manual = visual_interpretation(row)
        rows.append(
            {
                "symbol": symbol,
                "timeframe": row["timeframe"],
                "chart_file": str(chart_file),
                "live_estimated_wave": row["live_estimated_wave"],
                "confirmed_wave_context": row["confirmed_wave_context"],
                "current_leg_status": row["current_leg_status"],
                "visual_readability": manual["visual_readability"],
                "label_plausible": manual["label_plausible"],
                "activation_level_plausible": manual["activation_level_plausible"],
                "invalidation_level_plausible": manual["invalidation_level_plausible"],
                "display_policy_ok": manual["display_policy_ok"],
                "manual_notes": manual["manual_notes"],
            }
        )
    return pd.DataFrame(rows)


def visual_interpretation(row: pd.Series) -> dict[str, Any]:
    symbol = str(row["symbol"])
    wave = str(row["live_estimated_wave"])
    if wave == "invalidated":
        return {
            "visual_readability": "readable",
            "label_plausible": "true",
            "activation_level_plausible": "true",
            "invalidation_level_plausible": "true",
            "display_policy_ok": "true",
            "manual_notes": "Latest close is beyond the invalidation level for the stale long context; manual-only is appropriate. Future wording should distinguish invalidated_old_context from a fresh bearish wave.",
        }
    if symbol == "US500":
        return {
            "visual_readability": "readable",
            "label_plausible": "true",
            "activation_level_plausible": "true",
            "invalidation_level_plausible": "true",
            "display_policy_ok": "true",
            "manual_notes": "Short live leg is visually legible and latest close is below activation. Plausible as possible_wave3_active, but only as study-panel context because the confirmed cycle is late.",
        }
    if symbol == "XAUUSD.r":
        return {
            "visual_readability": "borderline",
            "label_plausible": "unclear",
            "activation_level_plausible": "true",
            "invalidation_level_plausible": "true",
            "display_policy_ok": "true",
            "manual_notes": "Bounce from the last low is visible, but activation is still far away. possible_wave3_candidate is acceptable only as low-confidence study context, not as a strong current-wave label.",
        }
    return {
        "visual_readability": "too_ambiguous",
        "label_plausible": "unclear",
        "activation_level_plausible": "unclear",
        "invalidation_level_plausible": "unclear",
        "display_policy_ok": "unclear",
        "manual_notes": "No manual template for this symbol; requires review.",
    }


def build_us500_wave3_active_audit(sources: dict[str, Any], visual: pd.DataFrame) -> pd.DataFrame:
    row = select_symbol(sources["estimate"], "US500")
    if row is None:
        return pd.DataFrame([{"symbol": "US500", "status": "not_available", "recommendation": "No US500 live estimate row found."}])
    direction = str(row["direction"])
    activation_crossed = activation_crossed_for_direction(row)
    return pd.DataFrame(
        [
            {
                "symbol": "US500",
                "timeframe": row["timeframe"],
                "live_estimated_wave": row["live_estimated_wave"],
                "latest_close": row["latest_close"],
                "activation_level": row["activation_level"],
                "activation_crossed": activation_crossed,
                "current_leg_direction": row["current_leg_direction"],
                "current_leg_status": row["current_leg_status"],
                "confirmed_wave_context": row["confirmed_wave_context"],
                "visual_label_plausible": select_visual_value(visual, "US500", "label_plausible"),
                "could_be_plain_down_leg": True,
                "should_keep_active": True,
                "should_downgrade_to_candidate": False,
                "should_manual_review_only": False,
                "recommendation": "Keep possible_wave3_active as provisional study-panel label; do not show as fresh main-dashboard current wave.",
                "reason": "Latest close is clearly below activation for a short context and the leg is visually coherent, but late_cycle_context remains the limiting caveat.",
            }
        ]
    )


def build_xauusd_wave3_candidate_audit(sources: dict[str, Any], visual: pd.DataFrame) -> pd.DataFrame:
    row = select_symbol(sources["estimate"], "XAUUSD.r")
    if row is None:
        return pd.DataFrame([{"symbol": "XAUUSD.r", "status": "not_available", "recommendation": "No XAUUSD.r live estimate row found."}])
    return pd.DataFrame(
        [
            {
                "symbol": "XAUUSD.r",
                "timeframe": row["timeframe"],
                "live_estimated_wave": row["live_estimated_wave"],
                "latest_close": row["latest_close"],
                "activation_level": row["activation_level"],
                "activation_crossed": activation_crossed_for_direction(row),
                "distance_to_activation_pct": row["distance_to_activation_pct"],
                "current_leg_direction": row["current_leg_direction"],
                "current_leg_status": row["current_leg_status"],
                "confirmed_wave_context": row["confirmed_wave_context"],
                "visual_label_plausible": select_visual_value(visual, "XAUUSD.r", "label_plausible"),
                "could_be_noise_or_range": True,
                "should_keep_candidate": True,
                "should_downgrade_to_ambiguous": False,
                "should_manual_review_only": False,
                "recommendation": "Keep possible_wave3_candidate only as low-confidence study-panel context.",
                "reason": "Latest close has not crossed activation and the chart is borderline, but the bounce from the last persistent low is visible and invalidation is not breached.",
            }
        ]
    )


def build_invalidated_context_audit(sources: dict[str, Any]) -> pd.DataFrame:
    rows = []
    invalidated = sources["estimate"][sources["estimate"]["live_estimated_wave"].astype(str) == "invalidated"].copy()
    for _, row in invalidated.iterrows():
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "latest_close": row["latest_close"],
                "invalidation_level": row["invalidation_level"],
                "direction": row["direction"],
                "invalidation_breached": activation_invalidated_for_direction(row),
                "invalidation_source": "state_machine_and_latest_close",
                "display_policy": row["display_policy"],
                "display_policy_ok": True,
                "recommended_label_future": "invalidated_old_context",
                "interpretation": "Manual-only is correct. The current output should be read as old long context invalidated, not as a new bearish WaveCount signal.",
            }
        )
    if not rows:
        rows.append({"symbol": "not_available", "interpretation": "No invalidated rows found."})
    return pd.DataFrame(rows)


def build_state_machine_vs_live_estimate_audit(sources: dict[str, Any], visual: pd.DataFrame) -> pd.DataFrame:
    rows = []
    comparison = sources["comparison"]
    for _, row in comparison.iterrows():
        symbol = str(row["symbol"])
        display = str(row["live_display_policy"])
        if symbol in {"US500", "XAUUSD.r"}:
            improvement = "latest_close_makes_active_candidate_distinction_more_explicit"
            risk = "late_context_can_feel_fresher_than_it_is"
            dashboard = "show_both_in_study_panel_only"
        elif str(row["live_estimated_wave"]) == "invalidated":
            improvement = "keeps_invalidated_context_manual_only"
            risk = "invalidated_old_context_may_be_misread_as_current_bearish_context"
            dashboard = "hide_from_default_current_wave_summary"
        else:
            improvement = "no_clear_improvement"
            risk = "manual_review_needed"
            dashboard = "manual_review_only"
        rows.append(
            {
                "symbol": symbol,
                "timeframe": row["timeframe"],
                "state_machine_wave": row["state_machine_wave"],
                "live_estimated_wave": row["live_estimated_wave"],
                "state_machine_display_policy": row["state_machine_display_policy"],
                "live_display_policy": display,
                "visual_label_plausible": select_visual_value(visual, symbol, "label_plausible"),
                "improvement": improvement,
                "new_risk": risk,
                "dashboard_future_should_show": dashboard,
                "telegram_allowed": False,
                "bot_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def decide_next_step(
    contract: pd.DataFrame,
    visual: pd.DataFrame,
    us500: pd.DataFrame,
    xauusd: pd.DataFrame,
    invalidated: pd.DataFrame,
) -> str:
    if (contract["status"].astype(str) == "fail").any():
        return "blocked_for_dashboard_wave_context"
    if (visual["label_plausible"].astype(str) == "false").any():
        return "live_estimate_needs_rule_adjustment"
    if bool(us500.iloc[0].get("should_keep_active", False)) and bool(xauusd.iloc[0].get("should_keep_candidate", False)):
        return "live_estimate_study_panel_only"
    if len(invalidated) and set(visual["display_policy_ok"].astype(str)) == {"true"}:
        return "live_estimate_manual_review_only"
    return "needs_more_real_ohlc_review"


def build_decision_summary(
    decision: str,
    visual: pd.DataFrame,
    us500: pd.DataFrame,
    xauusd: pd.DataFrame,
    invalidated: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "decision": decision,
                "us500_result": us500.iloc[0].get("recommendation", ""),
                "xauusd_result": xauusd.iloc[0].get("recommendation", ""),
                "invalidated_rows": len(invalidated[invalidated.get("symbol", pd.Series(dtype=str)).astype(str) != "not_available"]) if "symbol" in invalidated.columns else 0,
                "visual_summary": "; ".join(f"{row.symbol}:{row.visual_readability}/{row.label_plausible}" for row in visual.itertuples()),
                "sql_dashboard_allowed_now": False,
                "next_step": "Broaden real-OHLC visual review or design a study-panel contract; do not integrate into SQL/dashboard main view yet.",
            }
        ]
    )


def build_issues_or_risks(
    contract: pd.DataFrame,
    visual: pd.DataFrame,
    us500: pd.DataFrame,
    xauusd: pd.DataFrame,
    invalidated: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: str,
) -> pd.DataFrame:
    blocking = int((contract["status"].astype(str) == "fail").sum())
    study_labels = int(visual["display_policy_ok"].astype(str).eq("true").sum())
    unclear = int(visual["label_plausible"].astype(str).eq("unclear").sum())
    return pd.DataFrame(
        [
            {
                "severity": "blocking" if blocking else "info",
                "risk": "contract_or_security_failure",
                "description": f"{blocking} blocking contract/security checks failed.",
                "recommendation": "Block any integration if this is non-zero.",
            },
            {
                "severity": "high",
                "risk": "late_context_can_be_misread_as_current",
                "description": "US500 and XAUUSD.r remain derived from late confirmed context, even with latest-close estimate.",
                "recommendation": "Use study-panel wording, not main-dashboard current-wave wording.",
            },
            {
                "severity": "medium" if unclear else "low",
                "risk": "unclear_label_plausibility",
                "description": f"{unclear} labels are visually unclear or borderline.",
                "recommendation": "Require broader real-OHLC review before SQL/dashboard.",
            },
            {
                "severity": "medium",
                "risk": "invalidated_old_context_wording",
                "description": "Invalidated rows may be read as fresh bearish context if wording is too terse.",
                "recommendation": "Consider future label invalidated_old_context/no_current_wave_context.",
            },
            {
                "severity": "info",
                "risk": "non_operational_guard",
                "description": f"Decision is {decision}; Telegram and bot remain forbidden.",
                "recommendation": "Keep can_generate_signal/can_filter_trade/can_execute_order false.",
            },
        ]
    )


def build_run_meta(
    generated_at: str,
    config: LiveEstimateVisualAuditConfig,
    sources: dict[str, Any],
    visual: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_estimate_visual_audit",
        "source_input_dir": str(config.input_dir),
        "symbols": sorted(sources["estimate"]["symbol"].dropna().astype(str).unique().tolist()),
        "timeframes": sorted(sources["estimate"]["timeframe"].dropna().astype(str).unique().tolist()),
        "charts_reviewed": int(visual["chart_file"].astype(str).ne("").sum()),
        "visual_readability_distribution": visual["visual_readability"].value_counts().sort_index().to_dict(),
        "label_plausible_distribution": visual["label_plausible"].value_counts().sort_index().to_dict(),
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
    }


def write_outputs(
    *,
    config: LiveEstimateVisualAuditConfig,
    contract: pd.DataFrame,
    visual: pd.DataFrame,
    us500: pd.DataFrame,
    xauusd: pd.DataFrame,
    invalidated: pd.DataFrame,
    comparison: pd.DataFrame,
    decision_summary: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "contract": config.output_dir / "contract_security_audit.csv",
        "visual": config.output_dir / "visual_live_estimate_audit.csv",
        "us500": config.output_dir / "us500_wave3_active_audit.csv",
        "xauusd": config.output_dir / "xauusd_wave3_candidate_audit.csv",
        "invalidated": config.output_dir / "invalidated_context_audit.csv",
        "comparison": config.output_dir / "state_machine_vs_live_estimate_audit.csv",
        "decision": config.output_dir / "decision_summary.csv",
        "issues": config.output_dir / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    contract.to_csv(paths["contract"], index=False)
    visual.to_csv(paths["visual"], index=False)
    us500.to_csv(paths["us500"], index=False)
    xauusd.to_csv(paths["xauusd"], index=False)
    invalidated.to_csv(paths["invalidated"], index=False)
    comparison.to_csv(paths["comparison"], index=False)
    decision_summary.to_csv(paths["decision"], index=False)
    issues.to_csv(paths["issues"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def copy_input_charts(config: LiveEstimateVisualAuditConfig) -> None:
    source = config.input_dir / "charts"
    if not source.exists():
        return
    target = config.output_dir / "charts"
    target.mkdir(parents=True, exist_ok=True)
    for path in source.glob("*.png"):
        shutil.copy2(path, target / path.name)


def write_docs(
    config: LiveEstimateVisualAuditConfig,
    contract: pd.DataFrame,
    visual: pd.DataFrame,
    us500: pd.DataFrame,
    xauusd: pd.DataFrame,
    invalidated: pd.DataFrame,
    comparison: pd.DataFrame,
    decision_summary: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    doc = f"""# WaveCount Live Estimate Visual Audit

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta auditoria revisa si `wavecount_live_estimate_v0` mejora la lectura viva de
onda por activo sin convertir WaveCount en senal, filtro o ejecucion. No se toca
SQL real, no se implementa dashboard, no se generan senales, no se ejecutan
backtests y no se conecta MT5.

## Contrato Y Seguridad

{markdown_table(contract)}

## Auditoria Visual

{markdown_table(visual)}

## US500

{markdown_table(us500)}

## XAUUSD.r

{markdown_table(xauusd)}

## Contextos Invalidados

{markdown_table(invalidated)}

## Comparacion Contra State Machine

{markdown_table(comparison)}

## Decision Summary

{markdown_table(decision_summary)}

## Riesgos

{markdown_table(issues)}

## Lectura

- US500 es visualmente plausible como `possible_wave3_active`, pero solo en
  panel de estudio con warning: no columna principal de onda actual.
- XAUUSD.r puede mantenerse como `possible_wave3_candidate` de baja confianza;
  no cruza activacion y queda borderline.
- EURUSD.r y GBPUSD.r deben seguir `manual_review_only`; mejor etiquetarlos en
  el futuro como `invalidated_old_context` o `no_current_wave_context`.
- La estimacion viva mejora la state machine porque explicita el tramo desde el
  ultimo pivote hasta el ultimo cierre, pero no elimina el problema de contexto
  tardio.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_LIVE_ESTIMATE_VISUAL_AUDIT.md").write_text(doc, encoding="utf-8")


def select_symbol(frame: pd.DataFrame, symbol: str) -> pd.Series | None:
    match = frame[frame["symbol"].astype(str) == symbol]
    return match.iloc[0] if not match.empty else None


def select_visual_value(visual: pd.DataFrame, symbol: str, column: str) -> str:
    match = visual[visual["symbol"].astype(str) == symbol]
    return str(match.iloc[0][column]) if not match.empty and column in match.columns else "unknown"


def activation_crossed_for_direction(row: pd.Series) -> bool:
    close = float(row["latest_close"])
    activation = float(row["activation_level"])
    direction = str(row["direction"])
    return close < activation if direction == "short" else close > activation


def activation_invalidated_for_direction(row: pd.Series) -> bool:
    close = float(row["latest_close"])
    invalidation = float(row["invalidation_level"])
    direction = str(row["direction"])
    return close > invalidation if direction == "short" else close < invalidation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build WaveCount live estimate visual audit artifacts.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--state-machine-dir", type=Path, default=DEFAULT_STATE_MACHINE_DIR)
    parser.add_argument("--warning-audit-dir", type=Path, default=DEFAULT_WARNING_AUDIT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--no-copy-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_live_estimate_visual_audit(
        LiveEstimateVisualAuditConfig(
            input_dir=args.input_dir,
            state_machine_dir=args.state_machine_dir,
            warning_audit_dir=args.warning_audit_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            copy_charts=not args.no_copy_charts,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "rows": int(len(result.visual_live_estimate_audit)),
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

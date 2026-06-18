from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from trading_center.wavecount_current_hypothesis import safe_id, to_bool
from trading_center.wavecount_study_screener import SCREENER_COLUMNS


DEFAULT_CURRENT_SCREENER_DIR = Path("artifacts/tfg/wavecount_study_screener_v0_2026-05-27")
DEFAULT_LIVE_ESTIMATE_DIR = Path("artifacts/tfg/wavecount_live_estimate_v0_2026-05-27")
DEFAULT_LIVE_ESTIMATE_AUDIT_DIR = Path("artifacts/tfg/wavecount_live_estimate_visual_audit_2026-05-27")
DEFAULT_STATE_MACHINE_DIR = Path("artifacts/tfg/wavecount_state_machine_v0_2026-05-27")
DEFAULT_CYCLE_STATE_DIR = Path("artifacts/tfg/wavecount_cycle_state_v0_2026-05-27")
DEFAULT_PERSISTENT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27")
DEFAULT_REAL_OHLC_DIR = Path("artifacts/tfg/wavecount_live_context_v0_real_ohlc_cut_review_2026-05-26")
DEFAULT_GRID_V2_DIR = Path("artifacts/tfg/wavecount_live_parameter_grid_v2_2026-05-27")
DEFAULT_LAG_STABILITY_DIR = Path("artifacts/tfg/wavecount_live_lag_stability_resolution_2026-05-27")
DEFAULT_DASHBOARD_REVIEW_DIR = Path("artifacts/tfg/trading_center_readonly_v1_2026-05-28")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_study_screener_review_v1_2026-05-28")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_STUDY_SCREENER_REVIEW_V1.md")

FALSE_FLAGS = [
    "telegram_allowed",
    "bot_allowed",
    "can_generate_signal",
    "can_filter_trade",
    "can_execute_order",
]

EXPANDED_COLUMNS = [
    "case_id",
    "case_source",
    "symbol",
    "market_group",
    "timeframe",
    "higher_timeframe",
    "as_of_bar_time",
    "case_type",
    "screener_bucket",
    "panel_priority",
    "live_estimated_wave",
    "confirmed_wave_context",
    "display_policy",
    "confidence_bucket",
    "freshness_status",
    "visual_readability",
    "label_plausible",
    "chart_file",
    "why_in_screener",
    "why_not_signal",
    "required_warning",
    "recommended_study_action",
    "study_only",
    "telegram_allowed",
    "bot_allowed",
    "can_generate_signal",
    "can_filter_trade",
    "can_execute_order",
    "panel_design_use",
    "source_artifact",
    "notes",
]


@dataclass(frozen=True)
class StudyScreenerReviewConfig:
    current_screener_dir: Path = DEFAULT_CURRENT_SCREENER_DIR
    live_estimate_dir: Path = DEFAULT_LIVE_ESTIMATE_DIR
    live_estimate_audit_dir: Path = DEFAULT_LIVE_ESTIMATE_AUDIT_DIR
    state_machine_dir: Path = DEFAULT_STATE_MACHINE_DIR
    cycle_state_dir: Path = DEFAULT_CYCLE_STATE_DIR
    persistent_dir: Path = DEFAULT_PERSISTENT_DIR
    real_ohlc_dir: Path = DEFAULT_REAL_OHLC_DIR
    grid_v2_dir: Path = DEFAULT_GRID_V2_DIR
    lag_stability_dir: Path = DEFAULT_LAG_STABILITY_DIR
    dashboard_review_dir: Path = DEFAULT_DASHBOARD_REVIEW_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH


@dataclass(frozen=True)
class StudyScreenerReviewResult:
    decision: str
    current_screener_audit: pd.DataFrame
    available_sources: pd.DataFrame
    expanded_screener: pd.DataFrame
    bucket_readiness: pd.DataFrame
    warning_copy_audit: pd.DataFrame
    visual_case_inventory: pd.DataFrame
    dashboard_panel_requirements: pd.DataFrame
    issues_or_risks: pd.DataFrame
    run_meta: dict[str, Any]
    written_files: dict[str, Path]


def build_study_screener_review(config: StudyScreenerReviewConfig | None = None) -> StudyScreenerReviewResult:
    config = config or StudyScreenerReviewConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)
    current = sources["current_screener"]
    current_audit = build_current_screener_audit(config, current)
    available = build_available_sources(config, sources)
    expanded = build_expanded_screener(config, sources, generated_at)
    buckets = build_panel_bucket_readiness(expanded)
    warnings = build_warning_copy_audit(expanded)
    visuals = build_visual_case_inventory(config, sources, expanded)
    requirements = build_dashboard_panel_requirements(expanded, buckets, visuals)
    issues = build_issues_or_risks(current, expanded, available)
    decision = decide_review(current, expanded, available, buckets)
    run_meta = build_run_meta(generated_at, config, current, expanded, available, decision)
    written = write_outputs(
        config=config,
        current_audit=current_audit,
        available=available,
        expanded=expanded,
        buckets=buckets,
        warnings=warnings,
        visuals=visuals,
        requirements=requirements,
        issues=issues,
        run_meta=run_meta,
    )
    write_docs(config, current_audit, available, expanded, buckets, warnings, visuals, requirements, issues, decision)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_STUDY_SCREENER_REVIEW_V1.md"
    return StudyScreenerReviewResult(
        decision=decision,
        current_screener_audit=current_audit,
        available_sources=available,
        expanded_screener=expanded,
        bucket_readiness=buckets,
        warning_copy_audit=warnings,
        visual_case_inventory=visuals,
        dashboard_panel_requirements=requirements,
        issues_or_risks=issues,
        run_meta=run_meta,
        written_files=written,
    )


def read_sources(config: StudyScreenerReviewConfig) -> dict[str, pd.DataFrame]:
    current_path = config.current_screener_dir / "wavecount_study_screener.csv"
    if not current_path.exists():
        raise FileNotFoundError(f"missing current screener input: {current_path}")
    return {
        "current_screener": read_csv(current_path),
        "live_estimate": read_optional_csv(config.live_estimate_dir / "live_wave_estimate.csv"),
        "live_visual": read_optional_csv(config.live_estimate_audit_dir / "visual_live_estimate_audit.csv"),
        "state_machine": read_optional_csv(config.state_machine_dir / "wave_state_machine_hypothesis.csv"),
        "cycle_state": read_optional_csv(config.cycle_state_dir / "cycle_state_hypothesis.csv"),
        "persistent": read_optional_csv(config.persistent_dir / "persistent_wave_hypothesis.csv"),
        "real_ohlc_context": read_optional_csv(config.real_ohlc_dir / "wavecount_live_context.csv"),
        "real_ohlc_inventory": read_optional_csv(config.real_ohlc_dir / "source_ohlc_inventory.csv"),
        "lag_visual": read_optional_csv(config.lag_stability_dir / "lag_stability_visual_review.csv"),
        "lag_comparison": read_optional_csv(config.lag_stability_dir / "lag_stability_config_comparison.csv"),
        "grid_comparison": read_optional_csv(config.grid_v2_dir / "config_comparison_v2.csv"),
        "dashboard_review": read_optional_csv(config.dashboard_review_dir / "tables/wavecount_display_validation.csv"),
    }


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def read_optional_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def build_current_screener_audit(config: StudyScreenerReviewConfig, current: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    current_json = config.current_screener_dir / "wavecount_study_screener.json"
    json_rows = []
    if current_json.exists():
        json_rows = json.loads(current_json.read_text(encoding="utf-8"))
    missing = [column for column in SCREENER_COLUMNS if column not in current.columns]
    rows.append(check_row("expected_columns_present", not missing, f"missing={missing}"))
    rows.append(check_row("csv_json_row_count_match", len(current) == len(json_rows), f"csv={len(current)};json={len(json_rows)}"))
    rows.append(check_row("payload_json_valid", payloads_valid(current), "payload_json parseable"))
    rows.append(check_row("study_only_all_true", bool_column_all(current, "study_only", True), value_distribution(current, "study_only")))
    rows.append(check_row("main_dashboard_all_false", bool_column_all(current, "show_in_main_dashboard", False), value_distribution(current, "show_in_main_dashboard")))
    for flag in FALSE_FLAGS:
        rows.append(check_row(f"{flag}_all_false", bool_column_all(current, flag, False), value_distribution(current, flag)))
    rows.append(check_row("current_case_count", len(current) >= 6, f"rows={len(current)}; current universe is narrow for panel design", "warn"))
    rows.append(check_row("bucket_variety", current["screener_bucket"].nunique() >= 4, value_distribution(current, "screener_bucket"), "warn"))
    rows.append(check_row("warnings_present", non_empty_all(current, "required_warning"), "required_warning populated"))
    rows.append(check_row("why_not_signal_present", non_empty_all(current, "why_not_signal"), "why_not_signal populated"))
    return pd.DataFrame(rows)


def check_row(check_name: str, passed: bool, observed: str, severity_if_failed: str = "blocker") -> dict[str, Any]:
    return {
        "check_name": check_name,
        "status": "pass" if passed else "fail",
        "severity": "info" if passed else severity_if_failed,
        "observed": observed,
    }


def bool_column_all(frame: pd.DataFrame, column: str, expected: bool) -> bool:
    return column in frame.columns and frame[column].map(to_bool).eq(expected).all()


def non_empty_all(frame: pd.DataFrame, column: str) -> bool:
    return column in frame.columns and frame[column].fillna("").astype(str).str.strip().ne("").all()


def value_distribution(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns:
        return "missing"
    return json.dumps(frame[column].fillna("not_available").astype(str).value_counts().sort_index().to_dict(), sort_keys=True)


def payloads_valid(frame: pd.DataFrame) -> bool:
    if "payload_json" not in frame.columns:
        return False
    for value in frame["payload_json"].fillna("{}"):
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return False
        if not isinstance(parsed, dict):
            return False
    return True


def build_available_sources(config: StudyScreenerReviewConfig, sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    specs = [
        ("current_screener_v0", config.current_screener_dir / "wavecount_study_screener.csv", "current final screener", True),
        ("live_estimate_v0", config.live_estimate_dir / "live_wave_estimate.csv", "latest-close live estimate", True),
        ("live_estimate_visual_audit", config.live_estimate_audit_dir / "visual_live_estimate_audit.csv", "visual audit and chart links", True),
        ("state_machine_v0", config.state_machine_dir / "wave_state_machine_hypothesis.csv", "late context and invalidation guards", True),
        ("cycle_state_v0", config.cycle_state_dir / "cycle_state_hypothesis.csv", "cycle/reset cases", True),
        ("persistent_hypothesis_v0", config.persistent_dir / "persistent_wave_hypothesis.csv", "progressive persistent pivot cuts", True),
        ("real_ohlc_cut_review", config.real_ohlc_dir / "wavecount_live_context.csv", "40 progressive causal cuts", True),
        ("parameter_grid_v2", config.grid_v2_dir / "config_comparison_v2.csv", "configuration noise/lag cases", False),
        ("lag_stability_resolution", config.lag_stability_dir / "lag_stability_visual_review.csv", "lag/stability chart cases", True),
        ("readonly_dashboard_v1", config.dashboard_review_dir / "tables/wavecount_display_validation.csv", "dashboard study-only validation", False),
    ]
    key_by_source = {
        "current_screener_v0": "current_screener",
        "live_estimate_v0": "live_estimate",
        "live_estimate_visual_audit": "live_visual",
        "state_machine_v0": "state_machine",
        "cycle_state_v0": "cycle_state",
        "persistent_hypothesis_v0": "persistent",
        "real_ohlc_cut_review": "real_ohlc_context",
        "parameter_grid_v2": "grid_comparison",
        "lag_stability_resolution": "lag_visual",
        "readonly_dashboard_v1": "dashboard_review",
    }
    rows = []
    for source_id, path, role, can_expand in specs:
        frame = sources.get(key_by_source[source_id], pd.DataFrame())
        exists = path.exists()
        symbols = sorted(frame["symbol"].dropna().astype(str).unique().tolist()) if "symbol" in frame.columns else []
        timeframes = sorted(frame["timeframe"].dropna().astype(str).unique().tolist()) if "timeframe" in frame.columns else []
        cuts = int(frame["cut_number"].nunique()) if "cut_number" in frame.columns else 0
        rows.append(
            {
                "source_id": source_id,
                "path": str(path),
                "exists": exists,
                "rows": int(len(frame)),
                "symbols": "|".join(symbols),
                "timeframes": "|".join(timeframes),
                "has_progressive_cuts": cuts > 0,
                "cut_count": cuts,
                "has_labels_or_estimates": has_any_column(frame, ["live_estimated_wave", "estimated_current_wave", "structure_phase", "screener_bucket"]),
                "has_visual_cases": has_any_column(frame, ["chart_file", "visual_readability", "manual_readability"]) or (path.parent / "charts").exists(),
                "usable_for_expansion": bool(exists and not frame.empty and can_expand),
                "source_role": role,
                "limitations": source_limitation(source_id, frame),
            }
        )
    return pd.DataFrame(rows)


def has_any_column(frame: pd.DataFrame, names: list[str]) -> bool:
    return any(name in frame.columns for name in names)


def source_limitation(source_id: str, frame: pd.DataFrame) -> str:
    if frame.empty:
        return "missing_or_empty"
    if source_id == "current_screener_v0":
        return "narrow final universe: 4 H4 rows"
    if source_id in {"real_ohlc_cut_review", "persistent_hypothesis_v0"}:
        return "progressive causal cases; useful for panel buckets, not live candidates"
    if source_id in {"parameter_grid_v2", "lag_stability_resolution"}:
        return "parameter/visual diagnostics only; no trading interpretation"
    return "study-only source; no signal/filter/execution"


def build_expanded_screener(config: StudyScreenerReviewConfig, sources: dict[str, pd.DataFrame], generated_at: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in sources["current_screener"].iterrows():
        rows.append(expanded_row_from_current(row, generated_at, config.current_screener_dir / "wavecount_study_screener.csv"))
    for _, row in sources["state_machine"].iterrows():
        rows.append(expanded_row_from_state_machine(row, generated_at, config.state_machine_dir / "wave_state_machine_hypothesis.csv"))
    for _, row in sources["cycle_state"].iterrows():
        rows.append(expanded_row_from_cycle_state(row, generated_at, config.cycle_state_dir / "cycle_state_hypothesis.csv"))
    for _, row in latest_by_symbol_timeframe(sources["persistent"], "as_of_bar_time").iterrows():
        rows.append(expanded_row_from_persistent(row, generated_at, config.persistent_dir / "persistent_wave_hypothesis.csv"))
    for _, row in sources["lag_visual"].iterrows():
        rows.append(expanded_row_from_lag_visual(row, generated_at, config.lag_stability_dir / "lag_stability_visual_review.csv"))
    for _, row in sources["real_ohlc_context"].iterrows():
        rows.append(expanded_row_from_real_ohlc(row, generated_at, config.real_ohlc_dir / "wavecount_live_context.csv"))
    frame = pd.DataFrame(rows)
    for column in EXPANDED_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    frame = frame.reindex(columns=EXPANDED_COLUMNS)
    for flag in ["study_only", *FALSE_FLAGS]:
        if flag == "study_only":
            frame[flag] = True
        else:
            frame[flag] = False
    return frame.sort_values(["panel_priority", "case_source", "symbol", "as_of_bar_time"]).reset_index(drop=True)


def expanded_base(
    *,
    generated_at: str,
    case_source: str,
    source_artifact: Path,
    symbol: str,
    timeframe: str,
    bucket: str,
    case_type: str,
    priority: int,
    wave: str = "",
    confirmed: str = "",
    market_group: str = "",
    higher_timeframe: str = "",
    as_of_bar_time: str = "",
    display_policy: str = "",
    confidence: str = "",
    freshness: str = "",
    visual_readability: str = "",
    label_plausible: str = "",
    chart_file: str = "",
    why_in_screener: str = "",
    warning: str = "",
    action: str = "",
    notes: str = "",
) -> dict[str, Any]:
    required_warning = warning or warning_for_bucket(bucket)
    return {
        "case_id": f"{case_source}_{safe_id(symbol or 'unknown')}_{safe_id(timeframe or 'tf')}_{safe_id(as_of_bar_time or case_type)}",
        "case_source": case_source,
        "symbol": symbol,
        "market_group": market_group,
        "timeframe": timeframe,
        "higher_timeframe": higher_timeframe,
        "as_of_bar_time": as_of_bar_time,
        "case_type": case_type,
        "screener_bucket": bucket,
        "panel_priority": priority,
        "live_estimated_wave": wave,
        "confirmed_wave_context": confirmed,
        "display_policy": display_policy,
        "confidence_bucket": confidence,
        "freshness_status": freshness,
        "visual_readability": visual_readability,
        "label_plausible": label_plausible,
        "chart_file": chart_file,
        "why_in_screener": why_in_screener or "Derived from existing WaveCount study artifacts for panel design coverage.",
        "why_not_signal": "WaveCount screener rows are study-only; ENBOLSA/RiskGuard remain the operational path.",
        "required_warning": required_warning,
        "recommended_study_action": action or action_for_bucket(bucket),
        "study_only": True,
        "telegram_allowed": False,
        "bot_allowed": False,
        "can_generate_signal": False,
        "can_filter_trade": False,
        "can_execute_order": False,
        "panel_design_use": "bucket_coverage_and_warning_design",
        "source_artifact": str(source_artifact),
        "notes": f"{notes} generated_at={generated_at}",
    }


def expanded_row_from_current(row: pd.Series, generated_at: str, source: Path) -> dict[str, Any]:
    return expanded_base(
        generated_at=generated_at,
        case_source="current_screener_v0",
        source_artifact=source,
        symbol=str(row.get("symbol", "")),
        market_group=str(row.get("market_group", "")),
        timeframe=str(row.get("timeframe", "")),
        higher_timeframe=str(row.get("higher_timeframe", "")),
        as_of_bar_time=str(row.get("as_of_bar_time", "")),
        bucket=str(row.get("screener_bucket", "")),
        case_type="current_screener_row",
        priority=int(float(row.get("screener_rank", 50))),
        wave=str(row.get("live_estimated_wave", "")),
        confirmed=str(row.get("confirmed_wave_context", "")),
        display_policy=str(row.get("display_policy", "")),
        confidence=str(row.get("confidence_bucket", "")),
        freshness=str(row.get("freshness_status", "")),
        visual_readability=str(row.get("visual_readability", "")),
        label_plausible=str(row.get("label_plausible", "")),
        warning=str(row.get("required_warning", "")),
        action=str(row.get("recommended_study_action", "")),
        why_in_screener=str(row.get("why_in_screener", "")),
        notes="canonical current screener row; not operational",
    )


def expanded_row_from_state_machine(row: pd.Series, generated_at: str, source: Path) -> dict[str, Any]:
    wave = str(row.get("estimated_current_wave", ""))
    if wave == "invalidated":
        bucket = "invalidated_old_context"
        priority = 70
    elif str(row.get("context_freshness_status", "")) == "late":
        bucket = "late_context_study"
        priority = 45
    elif str(row.get("display_policy", "")) == "manual_review_only":
        bucket = "manual_review_only"
        priority = 80
    else:
        bucket = "no_current_wave_context"
        priority = 85
    return expanded_base(
        generated_at=generated_at,
        case_source="state_machine_v0",
        source_artifact=source,
        symbol=str(row.get("symbol", "")),
        market_group=str(row.get("market_group", "")),
        timeframe=str(row.get("timeframe", "")),
        higher_timeframe=str(row.get("higher_timeframe", "")),
        as_of_bar_time=str(row.get("as_of_bar_time", "")),
        bucket=bucket,
        case_type="state_machine_late_or_invalidated_context",
        priority=priority,
        wave=wave,
        confirmed=str(row.get("confirmed_wave_context", "")),
        display_policy=str(row.get("display_policy", "")),
        freshness=str(row.get("context_freshness_status", "")),
        why_in_screener=f"state_machine display={row.get('display_policy', '')}; blockers={row.get('transition_blockers', '')}",
        notes="state machine context is for study/audit only",
    )


def expanded_row_from_cycle_state(row: pd.Series, generated_at: str, source: Path) -> dict[str, Any]:
    return expanded_base(
        generated_at=generated_at,
        case_source="cycle_state_v0",
        source_artifact=source,
        symbol=str(row.get("symbol", "")),
        market_group=str(row.get("market_group", "")),
        timeframe=str(row.get("timeframe", "")),
        higher_timeframe=str(row.get("higher_timeframe", "")),
        as_of_bar_time=str(row.get("as_of_bar_time", "")),
        bucket="needs_chart_review" if str(row.get("cycle_status", "")) == "reset_candidate" else "late_context_study",
        case_type="cycle_reset_case",
        priority=55,
        wave=str(row.get("estimated_current_wave", "")),
        confirmed=str(row.get("confirmed_wave_context", "")),
        display_policy=str(row.get("display_policy", "")),
        freshness=str(row.get("freshness_status", "")),
        why_in_screener=f"cycle_status={row.get('cycle_status', '')}; reset_reason={row.get('cycle_reset_reason', '')}",
        notes="cycle/reset case for future panel wording",
    )


def expanded_row_from_persistent(row: pd.Series, generated_at: str, source: Path) -> dict[str, Any]:
    wave = str(row.get("estimated_current_wave", ""))
    bucket = "needs_chart_review" if "wave5" in wave else "late_context_study"
    return expanded_base(
        generated_at=generated_at,
        case_source="persistent_hypothesis_v0_latest",
        source_artifact=source,
        symbol=str(row.get("symbol", "")),
        market_group=str(row.get("market_group", "")),
        timeframe=str(row.get("timeframe", "")),
        higher_timeframe=str(row.get("higher_timeframe", "")),
        as_of_bar_time=str(row.get("as_of_bar_time", "")),
        bucket=bucket,
        case_type="persistent_latest_case",
        priority=60,
        wave=wave,
        confirmed=str(row.get("confirmed_wave_context", "")),
        display_policy=str(row.get("display_policy", "")),
        confidence=str(row.get("hypothesis_status", "")),
        freshness=str(row.get("freshness_status", "")),
        why_in_screener=f"persistent_pivots={row.get('persistent_pivot_count', '')}; candidates={row.get('candidate_pivot_count', '')}",
        notes="persistent model latest row; useful to show false-precision risks",
    )


def expanded_row_from_lag_visual(row: pd.Series, generated_at: str, source: Path) -> dict[str, Any]:
    readability = str(row.get("manual_readability", ""))
    if readability == "too_noisy":
        bucket = "ambiguous_wave_context"
        priority = 75
    elif readability == "late_but_readable":
        bucket = "late_context_study"
        priority = 45
    else:
        bucket = "needs_chart_review"
        priority = 50
    return expanded_base(
        generated_at=generated_at,
        case_source=f"lag_stability_{row.get('config_name', 'config')}",
        source_artifact=source,
        symbol=str(row.get("symbol", "")),
        market_group=str(row.get("market_group", "")),
        timeframe=str(row.get("timeframe", "")),
        as_of_bar_time=f"cut_{row.get('cut_number', '')}",
        bucket=bucket,
        case_type="lag_stability_visual_case",
        priority=priority,
        confirmed=str(row.get("config_name", "")),
        display_policy="study_only_chart_case",
        freshness="late_or_unstable",
        visual_readability=readability,
        chart_file=str(row.get("chart_file", "")),
        why_in_screener=f"visual={readability}; lag={row.get('lag_visual_concern', '')}; stability={row.get('stability_visual_concern', '')}",
        notes=str(row.get("notes", "")),
    )


def expanded_row_from_real_ohlc(row: pd.Series, generated_at: str, source: Path) -> dict[str, Any]:
    phase = str(row.get("structure_phase", ""))
    status = str(row.get("hypothesis_status", ""))
    if phase == "completed_impulse_candidate":
        bucket = "needs_chart_review"
        priority = 58
    elif phase == "invalidated":
        bucket = "invalidated_old_context"
        priority = 70
    elif phase in {"ambiguous", "unknown", "not_available"}:
        bucket = "ambiguous_wave_context"
        priority = 75
    elif status == "confirmed":
        bucket = "late_context_study"
        priority = 48
    else:
        bucket = "candidate_wave_watch"
        priority = 40
    return expanded_base(
        generated_at=generated_at,
        case_source="real_ohlc_progressive_cut",
        source_artifact=source,
        symbol=str(row.get("symbol", "")),
        market_group=str(row.get("market_group", "")),
        timeframe=str(row.get("timeframe", "")),
        higher_timeframe=str(row.get("higher_timeframe", "")),
        as_of_bar_time=str(row.get("as_of_bar_time", "")),
        bucket=bucket,
        case_type=f"progressive_cut_{row.get('hypothesis_status', '')}",
        priority=priority,
        wave=phase,
        confirmed=status,
        display_policy="study_only_progressive_cut",
        confidence=str(row.get("confidence_bucket", "")),
        freshness="progressive_cut_artifact",
        why_in_screener=f"cut={extract_payload_value(row.get('payload_json', '{}'), 'cut_number')}; phase={phase}; status={status}",
        notes="real local OHLC cut review row; historical cut for panel bucket coverage",
    )


def latest_by_symbol_timeframe(frame: pd.DataFrame, time_column: str) -> pd.DataFrame:
    if frame.empty or "symbol" not in frame.columns or "timeframe" not in frame.columns:
        return pd.DataFrame()
    part = frame.copy()
    part["_sort_time"] = pd.to_datetime(part.get(time_column, ""), errors="coerce")
    part = part.sort_values(["symbol", "timeframe", "_sort_time"])
    return part.groupby(["symbol", "timeframe"], as_index=False).tail(1).drop(columns=["_sort_time"], errors="ignore")


def extract_payload_value(value: Any, key: str) -> Any:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return ""
    return payload.get(key, "") if isinstance(payload, dict) else ""


def warning_for_bucket(bucket: str) -> str:
    warnings = {
        "active_wave_study_candidate": "Contexto de estudio activo; no es senal, no es filtro y no es ejecutable.",
        "candidate_wave_watch": "Candidato de estudio pendiente de activacion; no operar ni filtrar por esta etiqueta.",
        "invalidated_old_context": "Contexto WaveCount antiguo invalidado; no leer como nueva senal contraria.",
        "manual_review_only": "Requiere revision manual; ocultar de cualquier resumen de candidatos.",
        "not_displayable": "Sin contexto WaveCount util para mostrar.",
        "late_context_study": "Contexto confirmado tarde; mostrar solo en panel de estudio con aviso de lag.",
        "ambiguous_wave_context": "Contexto ambiguo o ruidoso; no presentar como onda actual.",
        "needs_chart_review": "Caso para abrir grafico y revisar; la etiqueta no queda aprobada visualmente.",
        "no_current_wave_context": "No hay hipotesis viva actual suficientemente clara.",
        "stale_wave_context": "Contexto obsoleto por frescura insuficiente.",
        "conflicting_with_enbolsa_context": "Conflicto con contexto ENBOLSA; no usar como filtro ni decision.",
    }
    return warnings.get(bucket, "Contexto WaveCount de estudio; no operativo.")


def action_for_bucket(bucket: str) -> str:
    actions = {
        "active_wave_study_candidate": "open_chart_and_review_levels",
        "candidate_wave_watch": "watch_activation_and_review_chart",
        "invalidated_old_context": "keep_audit_hidden_from_live_candidates",
        "manual_review_only": "manual_review_before_display",
        "late_context_study": "show_lag_warning_and_compare_confirmed_vs_live",
        "ambiguous_wave_context": "show_only_as_ambiguous_or_hide_by_default",
        "needs_chart_review": "open_chart_before_trusting_label",
        "no_current_wave_context": "show_empty_state_or_hide",
        "stale_wave_context": "show_stale_warning_or_hide",
        "conflicting_with_enbolsa_context": "show_conflict_badge_without_filtering_trade",
        "not_displayable": "do_not_show",
    }
    return actions.get(bucket, "study_review_only")


def build_panel_bucket_readiness(expanded: pd.DataFrame) -> pd.DataFrame:
    bucket_specs = [
        ("active_wave_study_candidate", "Hipotesis viva plausible para abrir grafico.", 1, True, True, False),
        ("candidate_wave_watch", "Hipotesis candidata pendiente de activacion.", 2, True, True, False),
        ("late_context_study", "Contexto confirmado tarde o diagnostico legible pero con lag.", 3, True, True, False),
        ("needs_chart_review", "Caso visible solo como cola de revision visual/manual.", 4, True, True, True),
        ("invalidated_old_context", "Contexto viejo invalidado; sirve para explicar descarte.", 5, True, False, True),
        ("ambiguous_wave_context", "Ruido, ambiguedad o secuencia no creible.", 6, True, True, True),
        ("manual_review_only", "No entra como candidato sin revision humana.", 7, True, True, True),
        ("no_current_wave_context", "No hay contexto vivo claro.", 8, True, False, True),
        ("stale_wave_context", "Contexto demasiado antiguo.", 9, True, False, True),
        ("conflicting_with_enbolsa_context", "Contexto estructural contradice ENBOLSA.", 10, True, True, True),
        ("not_displayable", "Oculto por defecto.", 11, False, False, True),
    ]
    counts = expanded["screener_bucket"].value_counts().to_dict() if not expanded.empty else {}
    rows = []
    for bucket, meaning, priority, show, needs_chart, hidden in bucket_specs:
        rows.append(
            {
                "screener_bucket": bucket,
                "meaning": meaning,
                "observed_case_count": int(counts.get(bucket, 0)),
                "support_status": "observed" if counts.get(bucket, 0) else "required_for_panel_contract",
                "warning_required": warning_for_bucket(bucket),
                "show_in_panel": show,
                "visual_priority": priority,
                "needs_chart": needs_chart,
                "hidden_by_default": hidden,
                "never_do": "generate_signal|filter_trade|execute_order|telegram_trade_call",
            }
        )
    return pd.DataFrame(rows)


def build_warning_copy_audit(expanded: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in expanded.iterrows():
        warning = str(row.get("required_warning", ""))
        why_not_signal = str(row.get("why_not_signal", ""))
        required = str(row.get("why_in_screener", ""))
        copy_ok = bool(warning and why_not_signal and required)
        rows.append(
            {
                "case_id": row.get("case_id", ""),
                "screener_bucket": row.get("screener_bucket", ""),
                "has_why_in_screener": bool(required.strip()),
                "has_why_not_signal": bool(why_not_signal.strip()),
                "has_required_warning": bool(warning.strip()),
                "warning_mentions_non_operational": mentions_non_operational(warning + " " + why_not_signal),
                "copy_status": "ok" if copy_ok and mentions_non_operational(warning + " " + why_not_signal) else "needs_copy_review",
                "recommended_warning": warning_for_bucket(str(row.get("screener_bucket", ""))),
            }
        )
    return pd.DataFrame(rows)


def mentions_non_operational(text: str) -> bool:
    lowered = text.lower()
    tokens = ["no es senal", "not a signal", "no es filtro", "not a filter", "no es ejecutable", "not executable", "study-only", "study only"]
    return any(token in lowered for token in tokens)


def build_visual_case_inventory(config: StudyScreenerReviewConfig, sources: dict[str, pd.DataFrame], expanded: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in sources["live_visual"].iterrows():
        rows.append(visual_row("live_estimate_visual_audit", row.get("symbol", ""), row.get("timeframe", ""), row.get("chart_file", ""), row.get("live_estimated_wave", ""), row.get("visual_readability", ""), "current live estimate case"))
    for _, row in sources["lag_visual"].iterrows():
        rows.append(visual_row("lag_stability_visual_review", row.get("symbol", ""), row.get("timeframe", ""), row.get("chart_file", ""), row.get("config_name", ""), row.get("manual_readability", ""), "lag/stability representative case"))
    for source_id, chart_dir in [
        ("live_estimate_charts", config.live_estimate_dir / "charts"),
        ("state_machine_charts", config.state_machine_dir / "charts"),
        ("cycle_state_charts", config.cycle_state_dir / "charts"),
    ]:
        for path in sorted(chart_dir.glob("*.png")) if chart_dir.exists() else []:
            rows.append(visual_row(source_id, infer_symbol_from_chart(path), "H4", str(path), "", "available", "existing chart artifact"))
    if not rows:
        return pd.DataFrame(columns=["visual_case_id", "case_source", "symbol", "timeframe", "chart_file", "exists", "case_label", "visual_readability", "panel_bucket_hint", "notes"])
    frame = pd.DataFrame(rows).drop_duplicates(subset=["case_source", "chart_file"]).reset_index(drop=True)
    if not expanded.empty:
        bucket_map = (
            expanded[["symbol", "timeframe", "screener_bucket"]]
            .drop_duplicates()
            .groupby(["symbol", "timeframe"])["screener_bucket"]
            .apply(lambda values: "|".join(sorted(values.astype(str).unique())))
            .to_dict()
        )
        frame["panel_bucket_hint"] = frame.apply(
            lambda row: bucket_map.get((str(row["symbol"]), str(row["timeframe"])), "study_case"),
            axis=1,
        )
    else:
        frame["panel_bucket_hint"] = "study_case"
    return frame


def visual_row(source_id: str, symbol: Any, timeframe: Any, chart_file: Any, label: Any, readability: Any, notes: str) -> dict[str, Any]:
    path = Path(str(chart_file)) if str(chart_file) else Path()
    return {
        "visual_case_id": f"{source_id}_{safe_id(str(symbol))}_{safe_id(str(label or readability))}",
        "case_source": source_id,
        "symbol": str(symbol),
        "timeframe": str(timeframe),
        "chart_file": str(chart_file),
        "exists": path.exists() if str(chart_file) else False,
        "case_label": str(label),
        "visual_readability": str(readability),
        "notes": notes,
    }


def infer_symbol_from_chart(path: Path) -> str:
    name = path.stem
    for prefix in ["live_estimate_", "wave_state_machine_", "cycle_state_"]:
        if name.startswith(prefix):
            name = name[len(prefix) :]
    if name.endswith("_H4"):
        name = name[:-3]
    return name.replace("_r", ".r")


def build_dashboard_panel_requirements(expanded: pd.DataFrame, buckets: pd.DataFrame, visuals: pd.DataFrame) -> pd.DataFrame:
    visual_cases = int(visuals["exists"].sum()) if "exists" in visuals.columns else 0
    observed_buckets = int((buckets["observed_case_count"] > 0).sum()) if not buckets.empty else 0
    return pd.DataFrame(
        [
            {
                "requirement_id": "WC_PANEL_01",
                "requirement": "Panel separado de estudio WaveCount; nunca mezclado con watchlist operativa.",
                "source_evidence": f"expanded_rows={len(expanded)}; observed_buckets={observed_buckets}",
                "priority": "must",
            },
            {
                "requirement_id": "WC_PANEL_02",
                "requirement": "Cada fila debe mostrar bucket, warning, why_in_screener y why_not_signal.",
                "source_evidence": "warning_copy_audit",
                "priority": "must",
            },
            {
                "requirement_id": "WC_PANEL_03",
                "requirement": "Soportar estados con grafico disponible y sin grafico disponible.",
                "source_evidence": f"visual_cases_existing={visual_cases}",
                "priority": "must",
            },
            {
                "requirement_id": "WC_PANEL_04",
                "requirement": "Permitir filtro visual por bucket/familia/simbolo, sin accion operativa.",
                "source_evidence": "panel_bucket_readiness",
                "priority": "should",
            },
            {
                "requirement_id": "WC_PANEL_05",
                "requirement": "Mostrar `invalidated_old_context` como descarte/auditoria, no como senal bajista.",
                "source_evidence": "live_estimate_visual_audit",
                "priority": "must",
            },
            {
                "requirement_id": "WC_PANEL_06",
                "requirement": "Diferenciar hipotesis viva, contexto confirmado tarde, ruido/ambiguedad y revision manual.",
                "source_evidence": "state_machine|cycle_state|lag_stability artifacts",
                "priority": "must",
            },
        ]
    )


def build_issues_or_risks(current: pd.DataFrame, expanded: pd.DataFrame, available: pd.DataFrame) -> pd.DataFrame:
    current_rows = len(current)
    optional_sources = int(available["usable_for_expansion"].sum()) if "usable_for_expansion" in available.columns else 0
    return pd.DataFrame(
        [
            {
                "severity": "medium",
                "risk": "current_screener_universe_narrow",
                "description": f"Current screener has {current_rows} final H4 rows.",
                "recommendation": "Design P05 with bucket contract and empty/limited-state handling; do not infer broad coverage.",
            },
            {
                "severity": "info",
                "risk": "expanded_rows_are_study_cases",
                "description": f"Expanded screener has {len(expanded)} rows from artifacts/cuts, not new live candidates.",
                "recommendation": "Use for panel requirements and warning design only.",
            },
            {
                "severity": "medium" if optional_sources < 4 else "low",
                "risk": "source_coverage_limit",
                "description": f"Usable expansion sources={optional_sources}.",
                "recommendation": "If P05 needs richer examples, keep no-chart and unknown states explicit.",
            },
            {
                "severity": "high",
                "risk": "wavecount_can_look_actionable",
                "description": "Active/candidate labels can be misread as trading recommendations.",
                "recommendation": "Every panel row must keep no-signal/no-filter/no-execution copy visible.",
            },
        ]
    )


def decide_review(current: pd.DataFrame, expanded: pd.DataFrame, available: pd.DataFrame, buckets: pd.DataFrame) -> str:
    forbidden = expanded[FALSE_FLAGS].map(to_bool).any().any() if not expanded.empty else False
    if forbidden:
        return "wavecount_screener_blocked_for_panel_design"
    if len(current) < 4:
        return "wavecount_screener_needs_more_real_cases"
    observed = int((buckets["observed_case_count"] > 0).sum()) if not buckets.empty else 0
    usable_sources = int(available["usable_for_expansion"].sum()) if not available.empty else 0
    if len(expanded) >= 20 and observed >= 5 and usable_sources >= 5:
        return "wavecount_screener_ready_for_panel_design"
    if len(expanded) > len(current):
        return "wavecount_screener_study_only_minimal_panel"
    return "wavecount_screener_needs_more_real_cases"


def build_run_meta(
    generated_at: str,
    config: StudyScreenerReviewConfig,
    current: pd.DataFrame,
    expanded: pd.DataFrame,
    available: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    safety = {
        "real_sql_executed": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "mt5_connected": False,
        "backtests_executed": False,
        "signals_generated": False,
        "dashboard_implemented": False,
        "telegram_implemented": False,
        "bot_implemented": False,
        "wavecount_used_as_filter": False,
    }
    return {
        "generated_at": generated_at,
        "version": "wavecount_study_screener_review_v1",
        "decision": decision,
        "current_screener_rows": int(len(current)),
        "expanded_screener_rows": int(len(expanded)),
        "current_symbols": sorted(current["symbol"].dropna().astype(str).unique().tolist()) if "symbol" in current.columns else [],
        "expanded_symbols": sorted(expanded["symbol"].dropna().astype(str).unique().tolist()) if "symbol" in expanded.columns else [],
        "expanded_bucket_distribution": expanded["screener_bucket"].value_counts().sort_index().to_dict() if not expanded.empty else {},
        "usable_sources": int(available["usable_for_expansion"].sum()) if "usable_for_expansion" in available.columns else 0,
        "output_dir": str(config.output_dir),
        **safety,
        "safety": safety,
    }


def write_outputs(
    *,
    config: StudyScreenerReviewConfig,
    current_audit: pd.DataFrame,
    available: pd.DataFrame,
    expanded: pd.DataFrame,
    buckets: pd.DataFrame,
    warnings: pd.DataFrame,
    visuals: pd.DataFrame,
    requirements: pd.DataFrame,
    issues: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    tables = config.output_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    paths = {
        "current": tables / "current_screener_audit.csv",
        "sources": tables / "available_wavecount_sources.csv",
        "expanded": tables / "expanded_screener.csv",
        "buckets": tables / "panel_bucket_readiness.csv",
        "warnings": tables / "warning_copy_audit.csv",
        "visuals": tables / "visual_case_inventory.csv",
        "requirements": tables / "dashboard_panel_requirements.csv",
        "issues": tables / "issues_or_risks.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    current_audit.to_csv(paths["current"], index=False)
    available.to_csv(paths["sources"], index=False)
    expanded.to_csv(paths["expanded"], index=False)
    buckets.to_csv(paths["buckets"], index=False)
    warnings.to_csv(paths["warnings"], index=False)
    visuals.to_csv(paths["visuals"], index=False)
    requirements.to_csv(paths["requirements"], index=False)
    issues.to_csv(paths["issues"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    config: StudyScreenerReviewConfig,
    current_audit: pd.DataFrame,
    available: pd.DataFrame,
    expanded: pd.DataFrame,
    buckets: pd.DataFrame,
    warnings: pd.DataFrame,
    visuals: pd.DataFrame,
    requirements: pd.DataFrame,
    issues: pd.DataFrame,
    decision: str,
) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    copy_needs_review = int((warnings["copy_status"] != "ok").sum()) if not warnings.empty else 0
    doc = f"""# WaveCount Study Screener Review V1

Fecha: 2026-05-28

## Decision

Decision: `{decision}`.

Esta fase amplia y audita `wavecount_study_screener_v0` como herramienta de
estudio visual/manual antes de disenar el panel WaveCount. No se ha tocado SQL
real, no se ha creado DDL, no se ha implementado Telegram, bot ni MT5, no se
han ejecutado backtests y no se han generado senales.

## Resultado

- Screener actual: {len(current_audit)} checks de contrato/seguridad.
- Casos ampliados de estudio: {len(expanded)}.
- Buckets observados: {expanded['screener_bucket'].nunique() if not expanded.empty else 0}.
- Fuentes reutilizables: {int(available['usable_for_expansion'].sum()) if 'usable_for_expansion' in available.columns else 0}.
- Casos visuales inventariados: {len(visuals)}.
- Filas de copy a revisar: {copy_needs_review}.

## Auditoria Del Screener Actual

{markdown_table(current_audit)}

## Fuentes Disponibles

{markdown_table(available)}

## Distribucion Del Screener Ampliado

{markdown_table(expanded['screener_bucket'].value_counts().rename_axis('screener_bucket').reset_index(name='row_count') if not expanded.empty else pd.DataFrame())}

## Buckets Para Panel

{markdown_table(buckets)}

## Requisitos Para P05

{markdown_table(requirements)}

## Riesgos

{markdown_table(issues)}

## Lectura

- El screener actual no es suficiente como unica muestra porque solo contiene 4
  activos H4 finales.
- Los artifacts previos si aportan variedad para disenar el panel: cortes
  progresivos, contextos tardios, casos ambiguos/ruidosos, invalidaciones,
  reset/ciclo y casos con grafico.
- `expanded_screener.csv` no es un universo operativo: es un inventario de
  casos de estudio para que el panel soporte bien buckets, warnings y estados
  sin grafico.
- P05 puede disenar el panel si mantiene WaveCount separado como study-only y
  muestra warnings junto a cada fila.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_STUDY_SCREENER_REVIEW_V1.md").write_text(doc, encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    if frame is None or frame.empty:
        return "_Sin filas._"
    text = frame.fillna("").astype(str)
    columns = list(text.columns)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = ["| " + " | ".join(str(row[col]).replace("\n", " ") for col in columns) + " |" for _, row in text.iterrows()]
    return "\n".join([header, separator, *rows])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review and broaden WaveCount study screener for panel design.")
    parser.add_argument("--current-screener-dir", type=Path, default=DEFAULT_CURRENT_SCREENER_DIR)
    parser.add_argument("--live-estimate-dir", type=Path, default=DEFAULT_LIVE_ESTIMATE_DIR)
    parser.add_argument("--live-estimate-audit-dir", type=Path, default=DEFAULT_LIVE_ESTIMATE_AUDIT_DIR)
    parser.add_argument("--state-machine-dir", type=Path, default=DEFAULT_STATE_MACHINE_DIR)
    parser.add_argument("--cycle-state-dir", type=Path, default=DEFAULT_CYCLE_STATE_DIR)
    parser.add_argument("--persistent-dir", type=Path, default=DEFAULT_PERSISTENT_DIR)
    parser.add_argument("--real-ohlc-dir", type=Path, default=DEFAULT_REAL_OHLC_DIR)
    parser.add_argument("--grid-v2-dir", type=Path, default=DEFAULT_GRID_V2_DIR)
    parser.add_argument("--lag-stability-dir", type=Path, default=DEFAULT_LAG_STABILITY_DIR)
    parser.add_argument("--dashboard-review-dir", type=Path, default=DEFAULT_DASHBOARD_REVIEW_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_study_screener_review(
        StudyScreenerReviewConfig(
            current_screener_dir=args.current_screener_dir,
            live_estimate_dir=args.live_estimate_dir,
            live_estimate_audit_dir=args.live_estimate_audit_dir,
            state_machine_dir=args.state_machine_dir,
            cycle_state_dir=args.cycle_state_dir,
            persistent_dir=args.persistent_dir,
            real_ohlc_dir=args.real_ohlc_dir,
            grid_v2_dir=args.grid_v2_dir,
            lag_stability_dir=args.lag_stability_dir,
            dashboard_review_dir=args.dashboard_review_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "expanded_rows": int(len(result.expanded_screener)),
                "output_dir": str(args.output_dir),
                "sql_real_written": False,
                "mt5_connected": False,
                "backtests_executed": False,
                "signals_generated": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

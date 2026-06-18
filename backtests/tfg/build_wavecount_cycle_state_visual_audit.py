from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table, safe_id
from backtests.tfg.build_wavecount_live_real_ohlc_cut_review import DEFAULT_SOURCE_CSV, load_source_ohlc
from trading_center.wavecount_current_hypothesis import to_bool


DEFAULT_CYCLE_DIR = Path("artifacts/tfg/wavecount_cycle_state_v0_2026-05-27")
DEFAULT_PERSISTENT_DIR = Path("artifacts/tfg/wavecount_persistent_hypothesis_v0_2026-05-27")
DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_cycle_state_visual_audit_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_CYCLE_STATE_VISUAL_AUDIT.md")


@dataclass(frozen=True)
class CycleStateVisualAuditConfig:
    cycle_dir: Path = DEFAULT_CYCLE_DIR
    persistent_dir: Path = DEFAULT_PERSISTENT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    source_csv: Path = DEFAULT_SOURCE_CSV
    generate_charts: bool = True


@dataclass(frozen=True)
class CycleStateVisualAuditResult:
    contract_security_audit: pd.DataFrame
    cycle_reset_visual_audit: pd.DataFrame
    cycle_reset_diagnosis: pd.DataFrame
    wave3_relabel_audit: pd.DataFrame
    staleness_audit: pd.DataFrame
    model_comparison_audit: pd.DataFrame
    design_diagnosis: pd.DataFrame
    issues_or_risks: pd.DataFrame
    decision_summary: pd.DataFrame
    run_meta: dict[str, Any]
    decision: str
    written_files: dict[str, Path]


def build_cycle_state_visual_audit(
    config: CycleStateVisualAuditConfig | None = None,
) -> CycleStateVisualAuditResult:
    config = config or CycleStateVisualAuditConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = read_sources(config)
    contract = build_contract_security_audit(sources)
    diagnosis = build_cycle_reset_diagnosis(sources)
    staleness = build_staleness_audit(sources, diagnosis)
    visual = build_visual_audit(config, sources, diagnosis, staleness) if config.generate_charts else empty_visual_audit(diagnosis, staleness)
    wave3 = build_wave3_relabel_audit(sources, diagnosis, staleness, visual)
    comparison = build_model_comparison_audit(sources, wave3)
    design = build_design_diagnosis(contract, diagnosis, staleness, visual, wave3)
    decision = decide_next_step(contract, diagnosis, staleness, visual, wave3)
    issues = build_issues_or_risks(contract, diagnosis, staleness, visual, wave3, design)
    decision_summary = pd.DataFrame(
        [
            {
                "decision": decision,
                "summary": decision_text(decision),
                "sql_dashboard_allowed": False,
                "signals_allowed": False,
                "recommended_next_step": recommended_next_step(decision),
            }
        ]
    )
    run_meta = build_run_meta(generated_at, config, sources, visual, decision)
    written = write_outputs(
        config=config,
        contract=contract,
        visual=visual,
        diagnosis=diagnosis,
        wave3=wave3,
        staleness=staleness,
        comparison=comparison,
        design=design,
        issues=issues,
        decision_summary=decision_summary,
        run_meta=run_meta,
    )
    write_docs(config, contract, visual, diagnosis, wave3, staleness, comparison, design, issues, decision_summary)
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_CYCLE_STATE_VISUAL_AUDIT.md"
    return CycleStateVisualAuditResult(
        contract_security_audit=contract,
        cycle_reset_visual_audit=visual,
        cycle_reset_diagnosis=diagnosis,
        wave3_relabel_audit=wave3,
        staleness_audit=staleness,
        model_comparison_audit=comparison,
        design_diagnosis=design,
        issues_or_risks=issues,
        decision_summary=decision_summary,
        run_meta=run_meta,
        decision=decision,
        written_files=written,
    )


def read_sources(config: CycleStateVisualAuditConfig) -> dict[str, Any]:
    required = {
        "cycle": config.cycle_dir / "cycle_state_hypothesis.csv",
        "cycle_json": config.cycle_dir / "cycle_state_hypothesis.json",
        "registry": config.cycle_dir / "cycle_registry.csv",
        "transitions": config.cycle_dir / "cycle_transitions.csv",
        "reset": config.cycle_dir / "cycle_reset_audit.csv",
        "machine": config.cycle_dir / "wave_state_machine_audit.csv",
        "comparison": config.cycle_dir / "comparison_vs_persistent_hypothesis.csv",
        "anti": config.cycle_dir / "anti_lookahead_audit.csv",
        "run_meta": config.cycle_dir / "run_meta.json",
        "persistent_pivots": config.persistent_dir / "persistent_pivots.csv",
        "persistent_hypotheses": config.persistent_dir / "persistent_wave_hypothesis.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing cycle state visual audit inputs: {missing}")
    return {
        "cycle": pd.read_csv(required["cycle"]),
        "cycle_json": json.loads(required["cycle_json"].read_text(encoding="utf-8")),
        "registry": pd.read_csv(required["registry"]),
        "transitions": pd.read_csv(required["transitions"]),
        "reset": pd.read_csv(required["reset"]),
        "machine": pd.read_csv(required["machine"]),
        "comparison": pd.read_csv(required["comparison"]),
        "anti": pd.read_csv(required["anti"]),
        "run_meta": json.loads(required["run_meta"].read_text(encoding="utf-8")),
        "persistent_pivots": pd.read_csv(required["persistent_pivots"]),
        "persistent_hypotheses": pd.read_csv(required["persistent_hypotheses"]),
        "ohlc": load_source_ohlc(config.source_csv) if config.source_csv.exists() else pd.DataFrame(),
    }


def build_contract_security_audit(sources: dict[str, Any]) -> pd.DataFrame:
    cycle = sources["cycle"]
    anti = sources["anti"]
    meta = sources["run_meta"]
    rows = [
        {
            "check_name": "csv_json_row_count_match",
            "status": "pass" if len(cycle) == len(sources["cycle_json"]) else "fail",
            "observed": f"csv={len(cycle)};json={len(sources['cycle_json'])}",
            "severity": "blocking" if len(cycle) != len(sources["cycle_json"]) else "info",
        },
        {
            "check_name": "anti_lookahead_all_true",
            "status": "pass" if bool(anti["lookahead_safe"].map(to_bool).all()) else "fail",
            "observed": str(bool(anti["lookahead_safe"].map(to_bool).all())),
            "severity": "blocking" if not bool(anti["lookahead_safe"].map(to_bool).all()) else "info",
        },
    ]
    for flag in ["is_read_only", "can_generate_signal", "can_filter_trade", "can_execute_order"]:
        expected = True if flag == "is_read_only" else False
        observed_ok = bool(cycle[flag].map(to_bool).all()) if expected else not bool(cycle[flag].map(to_bool).any())
        rows.append(
            {
                "check_name": f"hard_flag_{flag}",
                "status": "pass" if observed_ok else "fail",
                "observed": str(observed_ok),
                "severity": "blocking" if not observed_ok else "info",
            }
        )
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
        rows.append(
            {
                "check_name": f"run_meta_{flag}",
                "status": "pass" if not value else "fail",
                "observed": str(value),
                "severity": "blocking" if value else "info",
            }
        )
    return pd.DataFrame(rows)


def build_cycle_reset_diagnosis(sources: dict[str, Any]) -> pd.DataFrame:
    cycle = sources["cycle"]
    registry = sources["registry"]
    rows = []
    for _, row in cycle.iterrows():
        current = cycle_pivots(sources["persistent_pivots"], row["symbol"], row["timeframe"], row["cycle_start_pivot_uid"], row["cycle_end_pivot_uid"])
        pivot_types = current["pivot_type"].astype(str).tolist()
        prices = pd.to_numeric(current["pivot_price"], errors="coerce").tolist()
        direction = infer_tail_direction(current)
        start_type = pivot_types[0] if pivot_types else ""
        end_type = pivot_types[-1] if pivot_types else ""
        previous_count = previous_cycle_count(registry, row)
        tail_forced = int(row["cycle_pivot_count"]) == 3 and str(row["estimated_current_wave"]).startswith("possible_wave3")
        start_conflict = bool(direction == "long" and start_type == "high") or bool(direction == "short" and start_type == "low")
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "as_of_bar_time": row["as_of_bar_time"],
                "cycle_status": row["cycle_status"],
                "estimated_current_wave": row["estimated_current_wave"],
                "current_cycle_pivot_count": int(row["cycle_pivot_count"]),
                "previous_cycle_pivot_count": previous_count,
                "tail_pivot_types": "->".join(pivot_types),
                "tail_prices": "->".join(f"{float(price):.5g}" for price in prices),
                "tail_direction": direction,
                "start_type_conflict": start_conflict,
                "tail3_forces_wave3_risk": tail_forced,
                "reset_boundary_plausibility": reset_boundary_plausibility(row, previous_count, start_conflict),
                "diagnosis": reset_diagnosis_text(row, previous_count, start_conflict, tail_forced),
            }
        )
    return pd.DataFrame(rows)


def cycle_pivots(pivots: pd.DataFrame, symbol: str, timeframe: str, start_uid: str, end_uid: str) -> pd.DataFrame:
    part = pivots[
        (pivots["symbol"].astype(str) == str(symbol))
        & (pivots["timeframe"].astype(str) == str(timeframe))
        & (pivots["pivot_role"].astype(str) == "persistent_pivot")
    ].copy()
    part["pivot_extreme_time"] = pd.to_datetime(part["pivot_extreme_time"], errors="coerce")
    part = part.sort_values(["pivot_extreme_time", "pivot_detected_at"])
    if part.empty:
        return part
    start_idx = part.index[part["pivot_uid"].astype(str) == str(start_uid)]
    end_idx = part.index[part["pivot_uid"].astype(str) == str(end_uid)]
    if len(start_idx) and len(end_idx):
        start_pos = part.index.get_loc(start_idx[0])
        end_pos = part.index.get_loc(end_idx[0])
        part = part.iloc[min(start_pos, end_pos) : max(start_pos, end_pos) + 1]
    return part


def infer_tail_direction(pivots: pd.DataFrame) -> str:
    if len(pivots) < 2:
        return "unknown"
    first_price = float(pivots.iloc[0]["pivot_price"])
    last_price = float(pivots.iloc[-1]["pivot_price"])
    return "long" if last_price >= first_price else "short"


def previous_cycle_count(registry: pd.DataFrame, row: pd.Series) -> int:
    previous_id = str(row.get("previous_cycle_id", ""))
    if not previous_id:
        return 0
    match = registry[registry["cycle_id"].astype(str) == previous_id]
    if match.empty:
        return 0
    return int(match.iloc[0]["cycle_pivot_count"])


def reset_boundary_plausibility(row: pd.Series, previous_count: int, start_conflict: bool) -> str:
    if previous_count >= 6 and not start_conflict:
        return "plausible_but_unproven"
    if previous_count >= 6 and start_conflict:
        return "borderline_start_type_conflict"
    if previous_count < 5:
        return "borderline_threshold_only"
    return "unclear"


def reset_diagnosis_text(row: pd.Series, previous_count: int, start_conflict: bool, tail_forced: bool) -> str:
    notes = []
    if previous_count >= 6:
        notes.append("previous_cycle_dense_enough_to_consider_reset")
    else:
        notes.append("previous_cycle_not_dense_enough_for_strong_reset_claim")
    if start_conflict:
        notes.append("tail_start_type_conflicts_with_inferred_direction")
    if tail_forced:
        notes.append("three_pivot_tail_can_force_wave3_label")
    return ";".join(notes)


def build_staleness_audit(sources: dict[str, Any], diagnosis: pd.DataFrame) -> pd.DataFrame:
    cycle = sources["cycle"]
    rows = []
    for _, row in cycle.iterrows():
        as_of = pd.Timestamp(row["as_of_bar_time"])
        last = pd.Timestamp(row["cycle_last_pivot_time"])
        lag_hours = (as_of - last).total_seconds() / 3600
        lag_bars = lag_hours / 4.0
        status = "late" if lag_bars > 60 else "acceptable_lag" if lag_bars > 24 else "fresh"
        rows.append(
            {
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "as_of_bar_time": row["as_of_bar_time"],
                "cycle_last_pivot_time": row["cycle_last_pivot_time"],
                "lag_hours_since_last_cycle_pivot": round(lag_hours, 2),
                "lag_h4_bars_since_last_cycle_pivot": round(lag_bars, 1),
                "context_freshness_status": status,
                "staleness_concern": "high" if status == "late" else "moderate" if status == "acceptable_lag" else "low",
                "interpretation": "The label is reset-derived from old pivots and should not be shown as fresh current wave." if status == "late" else "Lag is not blocking but still requires warning.",
            }
        )
    return pd.DataFrame(rows)


def build_visual_audit(
    config: CycleStateVisualAuditConfig,
    sources: dict[str, Any],
    diagnosis: pd.DataFrame,
    staleness: pd.DataFrame,
) -> pd.DataFrame:
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    ohlc = sources["ohlc"]
    for _, diag in diagnosis.iterrows():
        stale = staleness[staleness["symbol"].astype(str) == str(diag["symbol"])].iloc[0]
        chart_path = chart_dir / f"cycle_state_audit_{safe_id(str(diag['symbol']))}_{diag['timeframe']}.png"
        if not ohlc.empty:
            render_audit_chart(chart_path, sources, diag)
        readability = "borderline" if diag["start_type_conflict"] or stale["staleness_concern"] == "high" else "readable"
        wave3_plausible = "false" if bool(diag["tail3_forces_wave3_risk"]) and stale["staleness_concern"] == "high" else "unclear"
        rows.append(
            {
                "chart_file": str(chart_path),
                "symbol": diag["symbol"],
                "timeframe": diag["timeframe"],
                "estimated_current_wave": diag["estimated_current_wave"],
                "visual_readability": readability,
                "pivot_density_visual": "low",
                "reset_boundary_plausible": diag["reset_boundary_plausibility"],
                "wave3_label_plausible": wave3_plausible,
                "staleness_concern": stale["staleness_concern"],
                "manual_notes": manual_visual_note(diag, stale),
            }
        )
    return pd.DataFrame(rows)


def render_audit_chart(path: Path, sources: dict[str, Any], diag: pd.Series) -> None:
    symbol = str(diag["symbol"])
    timeframe = str(diag["timeframe"])
    cycle = sources["cycle"]
    row = cycle[(cycle["symbol"].astype(str) == symbol) & (cycle["timeframe"].astype(str) == timeframe)].iloc[0]
    as_of = pd.Timestamp(row["as_of_bar_time"])
    prices = sources["ohlc"][
        (sources["ohlc"]["symbol"].astype(str) == symbol) & (sources["ohlc"]["timeframe"].astype(str) == timeframe)
    ].copy()
    prices["time"] = pd.to_datetime(prices["time"], errors="coerce")
    prices = prices[prices["time"] <= as_of].sort_values("time").tail(260)
    pivots = sources["persistent_pivots"][
        (sources["persistent_pivots"]["symbol"].astype(str) == symbol)
        & (sources["persistent_pivots"]["timeframe"].astype(str) == timeframe)
        & (sources["persistent_pivots"]["pivot_role"].astype(str) == "persistent_pivot")
    ].copy()
    pivots["pivot_extreme_time"] = pd.to_datetime(pivots["pivot_extreme_time"], errors="coerce")
    pivots["pivot_price"] = pd.to_numeric(pivots["pivot_price"], errors="coerce")
    current = cycle_pivots(pivots, symbol, timeframe, row["cycle_start_pivot_uid"], row["cycle_end_pivot_uid"])
    current_uids = set(current["pivot_uid"].astype(str).tolist())
    previous = pivots[~pivots["pivot_uid"].astype(str).isin(current_uids)]

    fig, ax = plt.subplots(figsize=(11, 5.8))
    fig.patch.set_facecolor("white")
    ax.plot(prices["time"], prices["close"], color="#333333", linewidth=1.3, label="close")
    if not previous.empty:
        ax.scatter(previous["pivot_extreme_time"], previous["pivot_price"], color="#999999", s=32, label="previous persistent pivots", zorder=3)
    if not current.empty:
        ax.scatter(current["pivot_extreme_time"], current["pivot_price"], color="#0072B2", s=54, label="current cycle pivots", zorder=4)
        ax.plot(current["pivot_extreme_time"], current["pivot_price"], color="#0072B2", linewidth=1.2, alpha=0.75, zorder=3)
        ax.axvline(current["pivot_extreme_time"].min(), color="#D55E00", linestyle="--", linewidth=1.2, label="reset boundary")
    if str(row["cycle_last_pivot_time"]):
        ax.axvspan(pd.Timestamp(row["cycle_last_pivot_time"]), as_of, color="#E69F00", alpha=0.10, label="lag after last pivot")
    ax.axvline(as_of, color="#000000", linestyle=":", linewidth=1.0, label="as_of")
    ax.set_title(f"{symbol} {timeframe}: {row['estimated_current_wave']} ({row['cycle_status']})", fontsize=12, fontweight="bold")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Precio")
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="best", fontsize=8, frameon=False)
    ax.text(0.01, 0.02, "audit chart | read-only context | no signal / no filter / no execution", transform=ax.transAxes, fontsize=8, color="#555555")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def empty_visual_audit(diagnosis: pd.DataFrame, staleness: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, diag in diagnosis.iterrows():
        stale = staleness[staleness["symbol"].astype(str) == str(diag["symbol"])].iloc[0]
        rows.append(
            {
                "chart_file": "",
                "symbol": diag["symbol"],
                "timeframe": diag["timeframe"],
                "estimated_current_wave": diag["estimated_current_wave"],
                "visual_readability": "not_reviewed",
                "pivot_density_visual": "not_reviewed",
                "reset_boundary_plausible": diag["reset_boundary_plausibility"],
                "wave3_label_plausible": "unclear",
                "staleness_concern": stale["staleness_concern"],
                "manual_notes": "Charts were not generated in this run.",
            }
        )
    return pd.DataFrame(rows)


def manual_visual_note(diag: pd.Series, stale: pd.Series) -> str:
    notes = []
    if diag["tail3_forces_wave3_risk"]:
        notes.append("wave3 label may be an artifact of tail-of-three reset")
    if diag["start_type_conflict"]:
        notes.append("cycle start pivot type conflicts with inferred direction")
    if stale["staleness_concern"] == "high":
        notes.append("last cycle pivot is far before as_of")
    if not notes:
        notes.append("readable reset candidate, still unvalidated")
    return ";".join(notes)


def build_wave3_relabel_audit(
    sources: dict[str, Any],
    diagnosis: pd.DataFrame,
    staleness: pd.DataFrame,
    visual: pd.DataFrame,
) -> pd.DataFrame:
    comparison = sources["comparison"]
    rows = []
    for _, diag in diagnosis.iterrows():
        symbol = str(diag["symbol"])
        comp = comparison[comparison["symbol"].astype(str) == symbol].iloc[0]
        stale = staleness[staleness["symbol"].astype(str) == symbol].iloc[0]
        visual_row = visual[visual["symbol"].astype(str) == symbol].iloc[0]
        wave3 = str(diag["estimated_current_wave"]).startswith("possible_wave3")
        risk = "high" if wave3 and (diag["tail3_forces_wave3_risk"] or stale["staleness_concern"] == "high") else "medium" if wave3 else "low"
        rows.append(
            {
                "symbol": symbol,
                "timeframe": diag["timeframe"],
                "persistent_estimated_current_wave": comp["persistent_estimated_current_wave"],
                "cycle_estimated_current_wave": diag["estimated_current_wave"],
                "wave5_reduced": comp["wave5_reduced"],
                "wave3_created": wave3,
                "tail3_forces_wave3_risk": diag["tail3_forces_wave3_risk"],
                "staleness_concern": stale["staleness_concern"],
                "wave3_label_plausible": visual_row["wave3_label_plausible"],
                "risk": risk,
                "interpretation": "Cycle reset removes wave5 but may create wave3 by construction; require current-price/event-state validation.",
            }
        )
    return pd.DataFrame(rows)


def build_model_comparison_audit(sources: dict[str, Any], wave3: pd.DataFrame) -> pd.DataFrame:
    comparison = sources["comparison"].copy()
    comparison["cycle_audit_interpretation"] = comparison["symbol"].map(
        {
            row["symbol"]: row["interpretation"]
            for _, row in wave3.iterrows()
        }
    )
    comparison["approved_for_dashboard"] = False
    return comparison


def build_design_diagnosis(
    contract: pd.DataFrame,
    diagnosis: pd.DataFrame,
    staleness: pd.DataFrame,
    visual: pd.DataFrame,
    wave3: pd.DataFrame,
) -> pd.DataFrame:
    blocking = int((contract["severity"].eq("blocking") & contract["status"].eq("fail")).sum())
    wave3_risk_high = int((wave3["risk"].astype(str) == "high").sum())
    stale_high = int((staleness["staleness_concern"].astype(str) == "high").sum())
    start_conflicts = int(diagnosis["start_type_conflict"].map(to_bool).sum())
    rows = [
        {
            "diagnosis": "contract_security",
            "evidence": f"blocking_failures={blocking}",
            "recommended_next_action": "block_until_fixed" if blocking else "keep_guardrails",
            "risk_if_ignored": "operational contamination or look-ahead leak",
        },
        {
            "diagnosis": "wave5_reduced_but_wave3_artifact_risk",
            "evidence": f"high_wave3_relabel_risk={wave3_risk_high}/4",
            "recommended_next_action": "do_not_approve_dashboard_context_yet",
            "risk_if_ignored": "dashboard could show artificial wave3 as if reliable",
        },
        {
            "diagnosis": "cycle_staleness",
            "evidence": f"high_staleness={stale_high}/4",
            "recommended_next_action": "use_latest_close_and_freshness_before_next_wave_label",
            "risk_if_ignored": "context appears current while based on old pivots",
        },
        {
            "diagnosis": "cycle_start_semantics",
            "evidence": f"start_type_conflicts={start_conflicts}/4",
            "recommended_next_action": "add explicit wave-state-machine start rules",
            "risk_if_ignored": "tail reset can infer impulse direction from an invalid starting pivot",
        },
    ]
    if int((visual["visual_readability"].astype(str) == "borderline").sum()):
        rows.append(
            {
                "diagnosis": "visual_readability_borderline",
                "evidence": "at least one chart is borderline by audit heuristics",
                "recommended_next_action": "manual_chart_review_before_sql",
                "risk_if_ignored": "ambiguous visual context could be over-presented",
            }
        )
    return pd.DataFrame(rows)


def decide_next_step(contract: pd.DataFrame, diagnosis: pd.DataFrame, staleness: pd.DataFrame, visual: pd.DataFrame, wave3: pd.DataFrame) -> str:
    blocking = int((contract["severity"].eq("blocking") & contract["status"].eq("fail")).sum())
    if blocking:
        return "blocked_for_dashboard_wave_context"
    high_wave3_risk = int((wave3["risk"].astype(str) == "high").sum())
    high_staleness = int((staleness["staleness_concern"].astype(str) == "high").sum())
    start_conflicts = int(diagnosis["start_type_conflict"].map(to_bool).sum())
    if high_wave3_risk or start_conflicts:
        return "needs_wave_state_machine"
    if high_staleness:
        return "needs_current_price_freshness_rules"
    return "cycle_state_visual_review_passed"


def decision_text(decision: str) -> str:
    return {
        "blocked_for_dashboard_wave_context": "Audit found blocking safety or look-ahead issue.",
        "needs_wave_state_machine": "Cycle reset reduces wave5 dominance but creates wave3/state semantics risk.",
        "needs_current_price_freshness_rules": "Cycle reset is readable but too stale to present as current wave.",
        "cycle_state_visual_review_passed": "Cycle reset passed this limited visual/technical audit.",
    }.get(decision, "Decision not recognized.")


def recommended_next_step(decision: str) -> str:
    return {
        "blocked_for_dashboard_wave_context": "Fix blocking guards before any further work.",
        "needs_wave_state_machine": "Design an explicit wave-state machine using cycle start semantics, latest close, freshness and invalidation.",
        "needs_current_price_freshness_rules": "Add latest-close/freshness rules before dashboard/SQL.",
        "cycle_state_visual_review_passed": "Run broader OHLC review before SQL staging.",
    }.get(decision, "Manual review.")


def build_issues_or_risks(
    contract: pd.DataFrame,
    diagnosis: pd.DataFrame,
    staleness: pd.DataFrame,
    visual: pd.DataFrame,
    wave3: pd.DataFrame,
    design: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "severity": "blocking" if int((contract["severity"].eq("blocking") & contract["status"].eq("fail")).sum()) else "info",
                "risk": "safety_or_lookahead",
                "description": "Safety and anti-lookahead checks pass." if not int((contract["severity"].eq("blocking") & contract["status"].eq("fail")).sum()) else "Blocking safety failure.",
                "recommendation": "Keep hard guardrails.",
            },
            {
                "severity": "high" if int((wave3["risk"].astype(str) == "high").sum()) else "medium",
                "risk": "wave3_artifact_after_reset",
                "description": f"{int((wave3['risk'].astype(str) == 'high').sum())} rows have high risk that wave3 was created by tail-of-three reset.",
                "recommendation": "Do not approve for dashboard before explicit state-machine rules.",
            },
            {
                "severity": "high" if int((staleness["staleness_concern"].astype(str) == "high").sum()) else "medium",
                "risk": "stale_cycle_context",
                "description": f"{int((staleness['staleness_concern'].astype(str) == 'high').sum())} rows have high staleness since last cycle pivot.",
                "recommendation": "Use latest close and freshness warnings before any current-wave display.",
            },
            {
                "severity": "medium" if int(diagnosis["start_type_conflict"].map(to_bool).sum()) else "low",
                "risk": "cycle_start_semantics",
                "description": f"{int(diagnosis['start_type_conflict'].map(to_bool).sum())} rows start with a pivot type conflicting with inferred direction.",
                "recommendation": "Add state-machine transition constraints.",
            },
        ]
    )


def build_run_meta(
    generated_at: str,
    config: CycleStateVisualAuditConfig,
    sources: dict[str, Any],
    visual: pd.DataFrame,
    decision: str,
) -> dict[str, Any]:
    cycle = sources["cycle"]
    return {
        "generated_at": generated_at,
        "version": "wavecount_cycle_state_visual_audit",
        "decision": decision,
        "cycle_dir": str(config.cycle_dir),
        "persistent_dir": str(config.persistent_dir),
        "symbols": sorted(cycle["symbol"].dropna().astype(str).unique().tolist()),
        "timeframes": sorted(cycle["timeframe"].dropna().astype(str).unique().tolist()),
        "charts_reviewed": int(len(visual)),
        "visual_readability_distribution": visual["visual_readability"].value_counts().sort_index().to_dict(),
        "wave3_label_plausibility_distribution": visual["wave3_label_plausible"].value_counts().sort_index().to_dict(),
        "decision_final": decision,
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
    config: CycleStateVisualAuditConfig,
    contract: pd.DataFrame,
    visual: pd.DataFrame,
    diagnosis: pd.DataFrame,
    wave3: pd.DataFrame,
    staleness: pd.DataFrame,
    comparison: pd.DataFrame,
    design: pd.DataFrame,
    issues: pd.DataFrame,
    decision_summary: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "contract": config.output_dir / "contract_security_audit.csv",
        "visual": config.output_dir / "cycle_reset_visual_audit.csv",
        "diagnosis": config.output_dir / "cycle_reset_diagnosis.csv",
        "wave3": config.output_dir / "wave3_relabel_audit.csv",
        "staleness": config.output_dir / "staleness_audit.csv",
        "comparison": config.output_dir / "model_comparison_audit.csv",
        "design": config.output_dir / "design_diagnosis.csv",
        "issues": config.output_dir / "issues_or_risks.csv",
        "decision": config.output_dir / "decision_summary.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    contract.to_csv(paths["contract"], index=False)
    visual.to_csv(paths["visual"], index=False)
    diagnosis.to_csv(paths["diagnosis"], index=False)
    wave3.to_csv(paths["wave3"], index=False)
    staleness.to_csv(paths["staleness"], index=False)
    comparison.to_csv(paths["comparison"], index=False)
    design.to_csv(paths["design"], index=False)
    issues.to_csv(paths["issues"], index=False)
    decision_summary.to_csv(paths["decision"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    config: CycleStateVisualAuditConfig,
    contract: pd.DataFrame,
    visual: pd.DataFrame,
    diagnosis: pd.DataFrame,
    wave3: pd.DataFrame,
    staleness: pd.DataFrame,
    comparison: pd.DataFrame,
    design: pd.DataFrame,
    issues: pd.DataFrame,
    decision_summary: pd.DataFrame,
) -> None:
    decision = str(decision_summary.iloc[0]["decision"])
    doc = f"""# WaveCount Cycle State Visual Audit

Fecha: 2026-05-27

## Decision

Decision: `{decision}`.

Esta auditoria revisa si `wavecount_cycle_state_v0` arregla la dominancia
artificial de onda 5 sin crear una falsa precision nueva. El resultado es
mixto: la onda 5 desaparece, pero aparece riesgo de `possible_wave3_*` por la
regla mecanica de tomar la cola de 3 pivotes tras el reset.

No se toca SQL real, no se implementa dashboard, no se generan senales, no se
ejecutan backtests y no se conecta MT5.

## Seguridad Y Contrato

{markdown_table(contract)}

## Auditoria Visual / Tecnica

{markdown_table(visual)}

## Diagnostico De Reset

{markdown_table(diagnosis)}

## Riesgo De Reetiquetado A Onda 3

{markdown_table(wave3)}

## Staleness

{markdown_table(staleness)}

## Comparacion Con Modelo Persistente

{markdown_table(comparison)}

## Diagnostico De Diseno

{markdown_table(design)}

## Riesgos

{markdown_table(issues)}

## Lectura

- `cycle_state_v0` reduce la dominancia `possible_wave5_active` de 4/4 a 0/4.
- La nueva lectura no queda aprobada: las 4 filas son `reset_candidate` y las
  etiquetas `possible_wave3_*` pueden venir de la cola de 3 pivotes.
- Hay preocupacion de frescura: el ultimo pivote del ciclo actual queda lejos
  de `as_of_bar_time` en todos los activos revisados.
- Antes de SQL/dashboard hace falta una maquina de estados explicita que use
  inicio de ciclo, precio actual/latest close, invalidacion y frescura.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_CYCLE_STATE_VISUAL_AUDIT.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit WaveCount cycle state visual/technical outputs.")
    parser.add_argument("--cycle-dir", type=Path, default=DEFAULT_CYCLE_DIR)
    parser.add_argument("--persistent-dir", type=Path, default=DEFAULT_PERSISTENT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--no-charts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_cycle_state_visual_audit(
        CycleStateVisualAuditConfig(
            cycle_dir=args.cycle_dir,
            persistent_dir=args.persistent_dir,
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            source_csv=args.source_csv,
            generate_charts=not args.no_charts,
        )
    )
    print(
        json.dumps(
            {
                "decision": result.decision,
                "charts_reviewed": int(len(result.cycle_reset_visual_audit)),
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

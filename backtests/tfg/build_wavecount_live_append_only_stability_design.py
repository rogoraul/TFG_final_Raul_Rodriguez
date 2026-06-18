from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backtests.tfg.build_wavecount_live_parameter_review import markdown_table


DEFAULT_OUTPUT_DIR = Path("artifacts/tfg/wavecount_live_append_only_stability_design_2026-05-27")
DEFAULT_DOC_PATH = Path("docs/WAVECOUNT_LIVE_APPEND_ONLY_STABILITY_DESIGN.md")
DEFAULT_VISUAL_AUDIT_DIR = Path("artifacts/tfg/wavecount_live_visual_manual_audit_2026-05-27")
DEFAULT_GRID_V2_DIR = Path("artifacts/tfg/wavecount_live_parameter_grid_v2_2026-05-27")


@dataclass(frozen=True)
class AppendOnlyStabilityDesignConfig:
    output_dir: Path = DEFAULT_OUTPUT_DIR
    doc_path: Path = DEFAULT_DOC_PATH
    visual_audit_dir: Path = DEFAULT_VISUAL_AUDIT_DIR
    grid_v2_dir: Path = DEFAULT_GRID_V2_DIR


@dataclass(frozen=True)
class AppendOnlyStabilityDesignResult:
    stability_state_model: pd.DataFrame
    context_identity_fields: pd.DataFrame
    append_only_policy: pd.DataFrame
    sql_future_tables: pd.DataFrame
    sql_future_views: pd.DataFrame
    integration_contracts: pd.DataFrame
    staging_entry_criteria: pd.DataFrame
    do_not_do_yet: pd.DataFrame
    open_decisions: pd.DataFrame
    run_meta: dict[str, Any]
    written_files: dict[str, Path]


def build_append_only_stability_design(
    config: AppendOnlyStabilityDesignConfig | None = None,
) -> AppendOnlyStabilityDesignResult:
    config = config or AppendOnlyStabilityDesignConfig()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    evidence = load_evidence(config)
    stability = stability_state_model()
    fields = context_identity_fields()
    policy = append_only_policy()
    tables = sql_future_tables()
    views = sql_future_views()
    integration = integration_contracts()
    criteria = staging_entry_criteria()
    blocked = do_not_do_yet()
    open_items = open_decisions()
    run_meta = build_run_meta(generated_at, config, evidence)
    written = write_outputs(
        config=config,
        stability_state_model=stability,
        context_identity_fields=fields,
        append_only_policy=policy,
        sql_future_tables=tables,
        sql_future_views=views,
        integration_contracts=integration,
        staging_entry_criteria=criteria,
        do_not_do_yet=blocked,
        open_decisions=open_items,
        run_meta=run_meta,
    )
    write_docs(
        config=config,
        evidence=evidence,
        stability_state_model=stability,
        context_identity_fields=fields,
        append_only_policy=policy,
        sql_future_tables=tables,
        sql_future_views=views,
        integration_contracts=integration,
        staging_entry_criteria=criteria,
        do_not_do_yet=blocked,
        open_decisions=open_items,
    )
    written["doc"] = config.doc_path
    written["artifact_doc"] = config.output_dir / "WAVECOUNT_LIVE_APPEND_ONLY_STABILITY_DESIGN.md"
    return AppendOnlyStabilityDesignResult(
        stability_state_model=stability,
        context_identity_fields=fields,
        append_only_policy=policy,
        sql_future_tables=tables,
        sql_future_views=views,
        integration_contracts=integration,
        staging_entry_criteria=criteria,
        do_not_do_yet=blocked,
        open_decisions=open_items,
        run_meta=run_meta,
        written_files=written,
    )


def load_evidence(config: AppendOnlyStabilityDesignConfig) -> dict[str, Any]:
    required = {
        "visual_decision": config.visual_audit_dir / "decision_summary.csv",
        "append_only_implications": config.visual_audit_dir / "append_only_implications.csv",
        "problem_cut_audit": config.visual_audit_dir / "problem_cut_audit.csv",
        "focused_config_comparison": config.visual_audit_dir / "focused_config_comparison.csv",
        "grid_label_transition": config.grid_v2_dir / "label_transition_by_config.csv",
        "grid_pivot_stability": config.grid_v2_dir / "pivot_stability_by_config.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing append-only design evidence: {missing}")
    visual_decision = pd.read_csv(required["visual_decision"])
    problem_cuts = pd.read_csv(required["problem_cut_audit"])
    focused = pd.read_csv(required["focused_config_comparison"])
    return {
        "visual_decision": visual_decision,
        "append_only_implications": pd.read_csv(required["append_only_implications"]),
        "problem_cut_audit": problem_cuts,
        "focused_config_comparison": focused,
        "problem_cut_rows": int(len(problem_cuts)),
        "high_problem_cut_rows": int((problem_cuts["severity"].astype(str) == "high").sum()) if not problem_cuts.empty else 0,
        "decision": str(visual_decision.iloc[0]["decision"]) if not visual_decision.empty else "unknown",
        "preferred_next_config": str(visual_decision.iloc[0].get("preferred_next_config", "")) if not visual_decision.empty else "",
        "sql_staging_allowed": bool(visual_decision.iloc[0].get("sql_staging_allowed", False)) if not visual_decision.empty else False,
    }


def stability_state_model() -> pd.DataFrame:
    rows = [
        state("label_stability_status", "new", "First context in a revision group or first cut for symbol/timeframe.", "A fresh hypothesis with no prior live row to compare.", "show_with_warning", "yes", "no_signal; optional status summary only", "read_context_only", "Treating as stable or tradable."),
        state("label_stability_status", "unchanged", "Same phase, pivot_set_hash and freshness band as the prior context.", "Hypothesis survived the new cut without relevant revision.", "show_current", "yes", "no_signal", "read_context_only", "Using as risk permission."),
        state("label_stability_status", "evolved", "Expected forward phase movement without abrupt jump or pivot replacement.", "Context changed as live evidence progressed.", "show_with_warning", "yes", "no_signal; optional educational note later", "read_context_only", "Promoting operation."),
        state("label_stability_status", "superseded", "A later context replaces this hypothesis through a revision link.", "Historical row remains valid as what was known then, but not current.", "hide_from_current_view", "yes", "no", "no", "Overwriting or deleting historical row."),
        state("label_stability_status", "invalidated", "Closed-bar invalidation rule or invalidation event is observed.", "Hypothesis failed; insert invalidation event/context.", "show_with_warning", "yes", "no_signal; only system status later", "read_context_only", "Using invalidation as trade signal."),
        state("label_stability_status", "stale_due_to_lag", "confirmation_lag_bars exceeds accepted lag policy or late_confirmation flag is true.", "Readable but late context; not fresh live state.", "show_with_warning", "yes", "no_signal", "read_context_only", "Presenting as current fresh wave."),
        state("label_stability_status", "unstable_pivots", "pivot_set_hash changes unexpectedly, pivots disappear/replace, or unstable_pivots flag is true.", "Structural evidence changed enough to require caution.", "manual_review_only", "yes", "no", "no", "Selecting as dashboard current without warning."),
        state("label_stability_status", "manual_review_required", "Abrupt reclassification, conflicting evidence, visual audit warning or operator flag.", "Human review is needed before display as current context.", "manual_review_only", "yes", "no", "no", "Automating action from this state."),
        state("context_freshness_status", "fresh", "detected_at/evidence_window_end close to as_of_bar_time and lag within policy.", "Context can be shown without lag warning.", "show_current", "yes", "no_signal", "read_context_only", "Assuming edge."),
        state("context_freshness_status", "acceptable_lag", "Lag is non-zero but below accepted threshold.", "Context is usable as read-only structural context.", "show_with_warning", "yes", "no_signal", "read_context_only", "Using as entry permission."),
        state("context_freshness_status", "late", "Lag exceeds threshold but context remains visually readable.", "Show only with stale/provisional warning.", "show_with_warning", "yes", "no_signal", "read_context_only", "Showing as fresh."),
        state("context_freshness_status", "stale", "as_of_bar_time is too old for current data or context has been superseded.", "Not eligible for current dashboard state.", "hide_from_current_view", "yes", "no", "no", "Using in bot/risk decisions."),
        state("context_freshness_status", "not_applicable", "No context available or test/documentation row.", "Freshness cannot be evaluated.", "manual_review_only", "yes_if_research", "no", "no", "Operational display."),
        state("revision_reason", "new_cut", "New as_of_bar_time processed.", "Normal live append.", "show_current", "yes", "no_signal", "read_context_only", "No prohibitions beyond guardrails."),
        state("revision_reason", "pivot_replacement", "Structural pivot set changed versus prior row.", "Evidence changed; link old/new contexts.", "show_with_warning", "yes", "no", "read_context_only", "Mutating old pivot row."),
        state("revision_reason", "phase_change", "structure_phase changed without abrupt jump.", "Expected evolution.", "show_with_warning", "yes", "no_signal", "read_context_only", "Trading from the change."),
        state("revision_reason", "abrupt_reclassification", "Phase rank jumps/regresses beyond expected transition.", "Requires manual review.", "manual_review_only", "yes", "no", "no", "Automatic current display."),
        state("revision_reason", "late_confirmation", "Context appears after excessive confirmation_lag_bars.", "Mark stale_due_to_lag/late.", "show_with_warning", "yes", "no", "read_context_only", "Fresh signal language."),
        state("revision_reason", "invalidated_level", "Closed bar breaches invalidation level.", "Insert invalidation event and link prior context.", "show_with_warning", "yes", "no", "read_context_only", "Using invalidation to trade."),
        state("revision_reason", "manual_override_future", "Reserved for future human annotation.", "Must be explicit and audited.", "manual_review_only", "yes", "no", "no", "Hidden edits."),
        state("revision_reason", "not_applicable", "No revision relation.", "Default for isolated rows.", "show_with_warning", "yes", "no", "read_context_only", "Inferring stability."),
        state("display_policy", "show_current", "Context is current, not late, not unstable and read-only flags are safe.", "Dashboard can show as current structural context.", "show_current", "yes", "no_signal", "read_context_only", "Buttons/actions."),
        state("display_policy", "show_with_warning", "Context is late/provisional/evolved but still informative.", "Dashboard can show warning badges.", "show_with_warning", "yes", "informative_only", "read_context_only", "Signal wording."),
        state("display_policy", "hide_from_current_view", "Superseded/stale/not operational row.", "Only history/audit views should show it.", "hide_from_current_view", "yes", "no", "no", "Current dashboard card."),
        state("display_policy", "manual_review_only", "Unstable/abrupt/conflicting context.", "Only manual review queue/history.", "manual_review_only", "yes", "no", "no", "Automation or silent current display."),
    ]
    return pd.DataFrame(rows)


def state(
    status_type: str,
    status_value: str,
    when_assigned: str,
    meaning: str,
    dashboard_policy: str,
    statistics_policy: str,
    telegram_policy: str,
    bot_policy: str,
    prohibited: str,
) -> dict[str, str]:
    return {
        "status_type": status_type,
        "status_value": status_value,
        "when_assigned": when_assigned,
        "meaning": meaning,
        "dashboard_policy": dashboard_policy,
        "statistics_policy": statistics_policy,
        "telegram_policy": telegram_policy,
        "bot_policy": bot_policy,
        "prohibited": prohibited,
    }


def context_identity_fields() -> pd.DataFrame:
    rows = [
        field("context_id", "string", "stable id for this immutable context event", "producer", "hash/run/symbol/timeframe/as_of/phase/revision_number", "base event primary key"),
        field("context_run_id", "string", "id of generation batch/cut", "producer", "one per generation run", "links to wavecount_live_context_runs"),
        field("as_of_bar_time", "datetime", "last closed bar included in evidence", "producer", "from input cut", "causal reconstruction key"),
        field("detected_at", "datetime", "when hypothesis became detectable", "producer", "max pivot_detected_at/evidence event", "must be <= as_of_bar_time"),
        field("symbol", "string", "instrument", "producer", "from OHLC/snapshot", "join key with dashboard/snapshot"),
        field("timeframe", "string", "primary WaveCount timeframe", "producer", "from OHLC/snapshot", "join key"),
        field("structure_phase", "enum", "WaveCount live phase", "producer", "from classifier", "hypothesis, not signal"),
        field("hypothesis_status", "enum", "forming/provisional/confirmed/invalidated/expired", "producer", "from classifier and revision logic", "display and statistics"),
        field("pivot_set_hash", "string", "deterministic hash of structural pivots used", "producer", "hash ordered pivot type/time/price/detected_at", "detects pivot replacement/disappearance"),
        field("prior_context_id", "string", "previous context in same revision group", "linker/view", "latest prior symbol/timeframe row", "may be null"),
        field("supersedes_context_id", "string", "context this row supersedes", "revision_links", "insert link old->new", "prefer link table over update"),
        field("superseded_by_context_id", "string", "later context superseding this row", "view/revision_links", "derived reverse link", "do not store in base event if pure append-only"),
        field("revision_group_id", "string", "stable chain id for symbol/timeframe/direction/degree", "producer/linker", "deterministic symbol/timeframe/degree/context lineage", "groups revisions"),
        field("revision_number", "int", "monotonic number inside revision group", "linker", "prior max + 1", "supports history ordering"),
        field("revision_reason", "enum", "why this event differs from prior", "linker", "new_cut/pivot_replacement/phase_change/etc.", "audit dimension"),
        field("label_stability_status", "enum", "stability classification", "linker", "compare phase/pivot hash/lag/transitions", "dashboard warning"),
        field("context_freshness_status", "enum", "freshness/lag class", "producer/linker", "based on lag policy and data freshness", "dashboard warning"),
        field("confirmation_lag_bars", "int", "bars between pivot extreme and detection", "producer", "from causal pivot detector", "late/stale decision"),
        field("is_current", "bool", "whether view considers row current", "view", "latest displayable non-superseded row", "derived, not base truth"),
        field("is_superseded", "bool", "whether row has outgoing superseding link", "view", "exists link from context_id", "derived"),
        field("is_invalidated", "bool", "whether hypothesis invalidated", "producer/linker", "status/reason invalidated", "display warning"),
        field("is_late", "bool", "whether lag exceeds threshold", "producer/linker", "confirmation_lag_bars > policy", "display warning"),
        field("is_displayable", "bool", "eligible for dashboard safe view", "view", "display_policy in show_current/show_with_warning", "does not mean tradable"),
        field("requires_manual_review", "bool", "manual review required", "linker/view", "unstable/abrupt/low confidence", "manual queue"),
        field("can_generate_signal", "bool", "hard safety flag", "producer", "always false", "must remain false"),
        field("can_filter_trade", "bool", "hard safety flag", "producer", "always false", "must remain false"),
        field("can_execute_order", "bool", "hard safety flag", "producer", "always false", "must remain false"),
    ]
    return pd.DataFrame(rows)


def field(
    field_name: str,
    data_type: str,
    purpose: str,
    assigned_by: str,
    assignment_rule: str,
    notes: str,
) -> dict[str, str]:
    return {
        "field_name": field_name,
        "data_type": data_type,
        "purpose": purpose,
        "assigned_by": assigned_by,
        "assignment_rule": assignment_rule,
        "notes": notes,
    }


def append_only_policy() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "policy_id": "base_rule",
                "option": "B_append_only_events_plus_links",
                "recommendation": "recommended",
                "rule": "The base context event row is immutable; every new cut inserts a new event.",
                "why": "Keeps historical truth and avoids recalculating past labels with future evidence.",
                "tradeoff": "Consumers need views/links to know current state.",
            },
            {
                "policy_id": "supersedence",
                "option": "B_append_only_events_plus_links",
                "recommendation": "recommended",
                "rule": "Use wavecount_live_context_revision_links for supersedes/superseded_by instead of updating base events.",
                "why": "Pure append-only history; reverse relation is derived in views.",
                "tradeoff": "One extra table and join.",
            },
            {
                "policy_id": "invalidations",
                "option": "B_append_only_events_plus_links",
                "recommendation": "recommended",
                "rule": "Invalidation creates a new context event and an invalidates link to prior context.",
                "why": "The original row remains what was known at its as_of_bar_time.",
                "tradeoff": "Current views must exclude or warn invalidated chains.",
            },
            {
                "policy_id": "current_views",
                "option": "B_append_only_events_plus_links",
                "recommendation": "recommended",
                "rule": "Current context is a view selecting the latest displayable event per symbol/timeframe/revision_group.",
                "why": "Separates truth storage from dashboard convenience.",
                "tradeoff": "View logic must be tested carefully.",
            },
            {
                "policy_id": "light_update_option",
                "option": "A_base_append_only_plus_light_update",
                "recommendation": "not_recommended_for_v0",
                "rule": "Update is_current/is_superseded flags in old rows.",
                "why": "Simpler queries but violates pure append-only semantics and can hide history bugs.",
                "tradeoff": "Tempting but less auditable.",
            },
            {
                "policy_id": "event_sourcing_option",
                "option": "C_full_event_sourcing",
                "recommendation": "defer",
                "rule": "Store every pivot/label/revision as domain events only.",
                "why": "Most rigorous but too heavy before SQL staging and dashboard needs are known.",
                "tradeoff": "High implementation cost.",
            },
        ]
    )


def sql_future_tables() -> pd.DataFrame:
    rows = [
        table("wavecount_live_context_runs", "one row per generation/cut/batch", "context_run_id, generated_at, producer, method_version, source_artifacts, config_name, run_kind, status, rows_generated, safety_flags_json", "wavecount live staging job", "dashboard/statistics audit", "execute trading or store broker state", "future_sql_staging"),
        table("wavecount_live_context_events", "append-only main hypothesis table", "context_id, context_run_id, as_of_bar_time, detected_at, symbol, timeframe, structure_phase, hypothesis_status, pivot_set_hash, label_stability_status, context_freshness_status, display_policy, confirmation_lag_bars, hard flags, payload_json", "wavecount live staging job", "current/history/statistics views", "update historical hypothesis or set can_filter_trade true", "future_sql_staging"),
        table("wavecount_live_context_revision_links", "append-only relation table between context events", "link_id, revision_group_id, from_context_id, to_context_id, link_type, revision_reason, created_at, evidence_summary, payload_json", "stability linker", "current/history views", "mutate old context event rows", "future_sql_staging"),
        table("wavecount_live_pivot_sets", "hash and summary of structural pivots used by a context", "pivot_set_hash, context_id, pivot_count, first_pivot_time, last_pivot_detected_at, max_confirmation_lag_bars, unstable_pivots_flag, pivot_summary_json", "wavecount live staging job", "audit/statistics/manual review", "become signal source", "future_sql_staging_or_defer"),
        table("wavecount_live_manual_review_queue", "cases that need human review", "review_id, context_id, reason, severity, created_at, status, reviewer_notes_future, source_chart_path, payload_json", "safe dashboard/manual review job", "manual review view", "approve live trading", "defer_until_dashboard_review"),
    ]
    return pd.DataFrame(rows)


def table(
    table_name: str,
    objective: str,
    minimum_columns: str,
    writes: str,
    reads: str,
    must_not_do: str,
    timing: str,
) -> dict[str, str]:
    return {
        "table_name": table_name,
        "objective": objective,
        "minimum_columns": minimum_columns,
        "writes": writes,
        "reads": reads,
        "must_not_do": must_not_do,
        "timing": timing,
    }


def sql_future_views() -> pd.DataFrame:
    rows = [
        view("v_wavecount_live_current_context", "latest displayable event per symbol/timeframe/revision group", "context_events + revision_links", "dashboard/snapshot summary", "filters out superseded/stale/manual_review_only unless explicitly requested"),
        view("v_wavecount_live_context_history", "full immutable history with derived superseded/current flags", "context_events + revision_links", "statistics/audit", "does not hide old rows"),
        view("v_wavecount_live_manual_review", "contexts requiring manual review", "context_events + manual_review_queue + pivot_sets", "dashboard/manual review", "never suggests a trade action"),
        view("v_wavecount_live_dashboard_safe", "dashboard-safe subset with warning fields and hard flags", "current_context + safety filters", "Trading Center", "only exposes can_generate_signal=false/can_filter_trade=false/can_execute_order=false"),
    ]
    return pd.DataFrame(rows)


def view(
    view_name: str,
    objective: str,
    source_tables: str,
    consumers: str,
    guardrail: str,
) -> dict[str, str]:
    return {
        "view_name": view_name,
        "objective": objective,
        "source_tables": source_tables,
        "consumers": consumers,
        "guardrail": guardrail,
    }


def integration_contracts() -> pd.DataFrame:
    rows = [
        contract("live_context_snapshot_rows.payload_json", "store only latest WaveCount summary and ids", "context_id, structure_phase, label_stability_status, context_freshness_status, display_policy, can_filter_trade=false", "does not carry full history; consumers can link to WaveCount tables later"),
        contract("SQL operational core", "keeps core stable; WaveCount live remains separate staging module", "snapshot_id/context_id link only after staging approved", "no DDL in this phase"),
        contract("dashboard Trading Center", "shows context badge with warning", "fresh/late/unstable/manual_review status", "must not recalculate WaveCount or expose trade buttons"),
        contract("statistics ENBOLSA+WaveCount", "uses as_of_bar_time and immutable history", "context_history rows joined to later outcomes", "posterior/offline labels cannot feed live rows"),
        contract("Telegram informative", "may mention system/context status only in future", "no_signal wording, warnings only", "no WaveCount signal alerts"),
        contract("dry-run bot", "may read WaveCount as explanatory context later", "read-only flags and display_policy", "cannot accept/reject using WaveCount in v0"),
    ]
    return pd.DataFrame(rows)


def contract(component: str, role: str, allowed_data: str, forbidden: str) -> dict[str, str]:
    return {
        "component": component,
        "role": role,
        "allowed_data": allowed_data,
        "forbidden": forbidden,
    }


def staging_entry_criteria() -> pd.DataFrame:
    rows = [
        criterion("append_only_contract_approved", "must_have", "This design is reviewed and accepted.", "No SQL staging without approved immutability policy."),
        criterion("links_vs_updates_decision", "must_have", "Choose pure link table or light update.", "Recommended: pure links."),
        criterion("no_overwrite_tests", "must_have", "Tests prove older context rows remain unchanged.", "Use fixture/in-memory store before DB."),
        criterion("historical_reconstruction_test", "must_have", "Given as_of_bar_time, reconstruct what dashboard would have known.", "Prevents future leakage."),
        criterion("hard_flags_test", "must_have", "can_generate_signal/can_filter_trade/can_execute_order remain false.", "Blocks operational misuse."),
        criterion("lag_policy_decision", "must_have", "Define max acceptable lag for fresh/acceptable_lag/late.", "time_hard_b currently late in 40/40 cuts."),
        criterion("visual_review_extension", "must_have", "Review more cuts/time windows for time_hard_a/time_hard_b.", "Current visual audit is lightweight."),
        criterion("current_view_semantics", "must_have", "Define how current view treats superseded/late/manual review rows.", "Needed before dashboard."),
        criterion("manual_review_queue_policy", "should_have", "Define manual review status lifecycle.", "Can be deferred if dashboard not yet implemented."),
        criterion("no_candidate_operational_claim", "must_have", "Staging is contextual only, not candidate_live_readability_config_v0.", "No signal/filter permissions."),
    ]
    return pd.DataFrame(rows)


def criterion(criterion_id: str, priority: str, requirement: str, rationale: str) -> dict[str, str]:
    return {
        "criterion_id": criterion_id,
        "priority": priority,
        "requirement": requirement,
        "rationale": rationale,
    }


def do_not_do_yet() -> pd.DataFrame:
    items = [
        ("create_sql_ddl", "DDL must wait for staging entry criteria."),
        ("write_to_real_sql", "No DB writes in design phase."),
        ("integrate_dashboard", "Dashboard needs safe views and warning semantics first."),
        ("telegram_wavecount_alerts", "Would look like signal generation."),
        ("bot_uses_wavecount", "WaveCount is context only."),
        ("change_wavecount_defaults", "time_hard_b is not approved candidate."),
        ("declare_candidate_live_readability_config_v0", "Visual audit blocks candidate."),
        ("run_backtests_or_pnl", "This is not edge validation."),
        ("connect_mt5", "MT5 remains blocked."),
    ]
    return pd.DataFrame([{"item": item, "reason": reason} for item, reason in items])


def open_decisions() -> pd.DataFrame:
    rows = [
        ("max_lag_threshold", "What lag separates acceptable_lag from late/stale?", "Needed before current dashboard view."),
        ("current_view_policy", "Should late_but_readable rows appear in current view or only with warning?", "Needed before dashboard."),
        ("manual_review_scope", "Which unstable states require human review queue?", "Needed before SQL staging."),
        ("time_hard_a_vs_time_hard_b", "Which time-filter family deserves broader OHLC review?", "Needed before config promotion."),
        ("pivot_set_hash_definition", "Exact deterministic hash inputs and rounding.", "Needed before no-overwrite tests."),
        ("revision_group_id_policy", "How to group revisions across direction/degree changes.", "Needed before link table."),
        ("offline_label_join_policy", "How posterior/offline labels join without contaminating live rows.", "Needed before statistics."),
    ]
    return pd.DataFrame([{"decision_id": item, "question": question, "why_it_matters": why} for item, question, why in rows])


def build_run_meta(generated_at: str, config: AppendOnlyStabilityDesignConfig, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "version": "wavecount_live_append_only_stability_design",
        "visual_audit_dir": str(config.visual_audit_dir),
        "grid_v2_dir": str(config.grid_v2_dir),
        "source_decision": evidence["decision"],
        "preferred_next_config": evidence["preferred_next_config"],
        "problem_cut_rows": evidence["problem_cut_rows"],
        "high_problem_cut_rows": evidence["high_problem_cut_rows"],
        "recommended_model": "B_append_only_events_plus_revision_links",
        "real_sql_executed": False,
        "ddl_executed": False,
        "mt5_connected": False,
        "backtests_executed": False,
        "signals_generated": False,
        "dashboard_implemented": False,
        "telegram_implemented": False,
        "bot_implemented": False,
        "limitations": [
            "Design only; no DDL, no SQL writes and no runtime integration.",
            "Does not declare candidate_live_readability_config_v0.",
            "WaveCount remains structural context only.",
        ],
    }


def write_outputs(
    *,
    config: AppendOnlyStabilityDesignConfig,
    stability_state_model: pd.DataFrame,
    context_identity_fields: pd.DataFrame,
    append_only_policy: pd.DataFrame,
    sql_future_tables: pd.DataFrame,
    sql_future_views: pd.DataFrame,
    integration_contracts: pd.DataFrame,
    staging_entry_criteria: pd.DataFrame,
    do_not_do_yet: pd.DataFrame,
    open_decisions: pd.DataFrame,
    run_meta: dict[str, Any],
) -> dict[str, Path]:
    tables_dir = config.output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "stability_state_model": tables_dir / "stability_state_model.csv",
        "context_identity_fields": tables_dir / "context_identity_fields.csv",
        "append_only_policy": tables_dir / "append_only_policy.csv",
        "sql_future_tables": tables_dir / "sql_future_tables.csv",
        "sql_future_views": tables_dir / "sql_future_views.csv",
        "integration_contracts": tables_dir / "integration_contracts.csv",
        "staging_entry_criteria": tables_dir / "staging_entry_criteria.csv",
        "do_not_do_yet": tables_dir / "do_not_do_yet.csv",
        "open_decisions": tables_dir / "open_decisions.csv",
        "run_meta": config.output_dir / "run_meta.json",
    }
    stability_state_model.to_csv(paths["stability_state_model"], index=False)
    context_identity_fields.to_csv(paths["context_identity_fields"], index=False)
    append_only_policy.to_csv(paths["append_only_policy"], index=False)
    sql_future_tables.to_csv(paths["sql_future_tables"], index=False)
    sql_future_views.to_csv(paths["sql_future_views"], index=False)
    integration_contracts.to_csv(paths["integration_contracts"], index=False)
    staging_entry_criteria.to_csv(paths["staging_entry_criteria"], index=False)
    do_not_do_yet.to_csv(paths["do_not_do_yet"], index=False)
    open_decisions.to_csv(paths["open_decisions"], index=False)
    paths["run_meta"].write_text(json.dumps(run_meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return paths


def write_docs(
    *,
    config: AppendOnlyStabilityDesignConfig,
    evidence: dict[str, Any],
    stability_state_model: pd.DataFrame,
    context_identity_fields: pd.DataFrame,
    append_only_policy: pd.DataFrame,
    sql_future_tables: pd.DataFrame,
    sql_future_views: pd.DataFrame,
    integration_contracts: pd.DataFrame,
    staging_entry_criteria: pd.DataFrame,
    do_not_do_yet: pd.DataFrame,
    open_decisions: pd.DataFrame,
) -> None:
    doc = f"""# WaveCount Live Append-Only Stability Design

Fecha: 2026-05-27

## Decision

Modelo recomendado: `B_append_only_events_plus_revision_links`.

La tabla base futura de WaveCount live debe ser append-only pura. Cada nuevo
corte inserta un nuevo contexto; las supersedencias, invalidaciones y cambios de
fase se representan en una tabla de enlaces de revision. Las vistas pueden
derivar `current_context`, `historical_context`, `superseded_context`,
`late_context` y `manual_review`, pero la fila historica no se reescribe.

Esta fase es solo diseno: no crea DDL, no escribe SQL real, no toca dashboard,
no genera senales y no cambia el motor.

## Evidencia Que Motiva El Diseno

- Decision previa: `{evidence['decision']}`.
- Config preferida para revisar despues: `{evidence['preferred_next_config']}`.
- Cortes problematicos auditados: {evidence['problem_cut_rows']}.
- Cortes problematicos severidad alta: {evidence['high_problem_cut_rows']}.
- SQL staging permitido por la auditoria visual: `{evidence['sql_staging_allowed']}`.

`time_hard_b` es visualmente mas limpio, pero `late_confirmation` e
`unstable_pivots` obligan a registrar estabilidad, lag y relaciones entre
hipotesis antes de cualquier staging SQL.

## Estados De Estabilidad

{markdown_table(stability_state_model)}

## Campos De Identidad Y Relacion

{markdown_table(context_identity_fields)}

## Politica Append-Only

{markdown_table(append_only_policy)}

## Tablas SQL Futuras

{markdown_table(sql_future_tables)}

## Vistas SQL Futuras

{markdown_table(sql_future_views)}

## Integracion Con Snapshot Y Consumidores

{markdown_table(integration_contracts)}

## Criterios Antes De SQL Staging

{markdown_table(staging_entry_criteria)}

## No Hacer Todavia

{markdown_table(do_not_do_yet)}

## Decisiones Abiertas

{markdown_table(open_decisions)}

## Cierre Metodologico

- WaveCount live sigue siendo contexto estructural.
- `candidate_live_readability_config_v0` no queda declarada.
- Dashboard podria mostrar contexto con warning cuando exista una vista segura,
  pero no debe recalcular WaveCount ni mostrarlo como senal.
- Telegram no debe enviar senales WaveCount.
- Bot dry-run no debe aceptar/rechazar por WaveCount.
- Estadistica futura debe reconstruir lo que se sabia en cada `as_of_bar_time`,
  no usar etiquetas recalculadas con futuro.
"""
    config.doc_path.write_text(doc, encoding="utf-8")
    (config.output_dir / "WAVECOUNT_LIVE_APPEND_ONLY_STABILITY_DESIGN.md").write_text(doc, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build WaveCount live append-only stability design artifacts.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--visual-audit-dir", type=Path, default=DEFAULT_VISUAL_AUDIT_DIR)
    parser.add_argument("--grid-v2-dir", type=Path, default=DEFAULT_GRID_V2_DIR)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = build_append_only_stability_design(
        AppendOnlyStabilityDesignConfig(
            output_dir=args.output_dir,
            doc_path=args.doc_path,
            visual_audit_dir=args.visual_audit_dir,
            grid_v2_dir=args.grid_v2_dir,
        )
    )
    print(
        json.dumps(
            {
                "recommended_model": result.run_meta["recommended_model"],
                "source_decision": result.run_meta["source_decision"],
                "output_dir": str(args.output_dir),
                "real_sql_executed": False,
                "ddl_executed": False,
                "signals_generated": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

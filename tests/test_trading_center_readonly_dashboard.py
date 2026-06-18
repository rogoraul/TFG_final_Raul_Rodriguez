from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from trading_center.readonly_dashboard import build_dashboard


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fixtures(tmp_path: Path) -> dict[str, Path]:
    snapshot = tmp_path / "snapshot.csv"
    _write_csv(
        snapshot,
        [
            {
                "row_id": 1,
                "snapshot_id": "snap_1",
                "generated_at": "2026-05-28T10:00:00",
                "symbol": "EURUSD.r",
                "market_group": "Forex Majors",
                "strategy": "enbolsa:macd_breakout",
                "timeframe_ltf": "H1",
                "timeframe_htf": "H4",
                "last_closed_bar_time": "2026-05-28T08:00:00",
                "data_freshness_status": "latest_closed_bar",
                "signal_state": "watching_setup",
                "side": "BUY",
                "setup_id": "setup_1",
                "entry": "1.10",
                "sl": "1.09",
                "tp1": "1.12",
                "tp2": "1.13",
                "has_order_intent": "0",
                "intent_status": "not_applicable",
                "riskguard_status": "not_evaluated",
                "riskguard_reason": "",
                "wavecount_available": "0",
                "wavecount_policy_bucket": "not_available",
                "wavecount_context_status": "not_available",
                "dry_run_eligible": "0",
                "is_read_only": "1",
                "can_execute_order": "0",
                "wavecount_should_filter_trade": "0",
                "run_kind": "bootstrap_current",
                "data_origin": "live_context_snapshot_v0",
                "is_operational": "1",
            }
        ],
    )
    security = tmp_path / "security.csv"
    _write_csv(
        security,
        [
            {"check_name": "can_execute_order_true", "value": 0, "expected": 0, "status": "passed"},
            {"check_name": "wavecount_should_filter_trade_true", "value": 0, "expected": 0, "status": "passed"},
        ],
    )
    counts = tmp_path / "counts.csv"
    _write_csv(counts, [{"metric_group": "view_counts", "metric": "v_dashboard_watchlist", "value": 1}])
    migrations = tmp_path / "migrations.csv"
    _write_csv(migrations, [{"migration_id": "001_create_operational_core", "description": "core", "status": "registered"}])
    manifest = tmp_path / "manifest.csv"
    _write_csv(manifest, [{"artifact": "snapshot.csv", "source": "test", "rows": 1, "status": "generated"}])
    wavecount = tmp_path / "wavecount.csv"
    _write_csv(
        wavecount,
        [
            {
                "symbol": "US500",
                "market_group": "Index",
                "timeframe": "H4",
                "screener_bucket": "active_wave_study_candidate",
                "screener_score": 72,
                "live_estimated_wave": "possible_wave3_active",
                "display_policy": "show_live_estimate_with_warning",
                "why_not_signal": "study only",
                "study_only": "True",
                "can_generate_signal": "False",
                "can_filter_trade": "False",
                "can_execute_order": "False",
            }
        ],
    )
    expanded = tmp_path / "expanded_screener.csv"
    _write_csv(
        expanded,
        [
            {
                "case_id": "case_1",
                "case_source": "test",
                "symbol": "US500",
                "market_group": "Index",
                "timeframe": "H4",
                "screener_bucket": "active_wave_study_candidate",
                "panel_priority": 1,
                "live_estimated_wave": "possible_wave3_active",
                "confirmed_wave_context": "possible_wave3_active_late",
                "display_policy": "show_live_estimate_with_warning",
                "confidence_bucket": "medium",
                "freshness_status": "live_estimate_from_close",
                "visual_readability": "readable",
                "chart_file": "charts/us500.png",
                "why_in_screener": "study case",
                "why_not_signal": "WaveCount screener rows are study-only.",
                "required_warning": "Contexto de estudio; no es senal, no es filtro y no es ejecutable.",
                "recommended_study_action": "revisar grafico",
                "study_only": "True",
                "telegram_allowed": "False",
                "bot_allowed": "False",
                "can_generate_signal": "False",
                "can_filter_trade": "False",
                "can_execute_order": "False",
                "source_artifact": "test_artifact",
            }
        ],
    )
    buckets = tmp_path / "buckets.csv"
    _write_csv(
        buckets,
        [
            {
                "screener_bucket": "active_wave_study_candidate",
                "observed_case_count": 1,
                "show_in_panel": "True",
                "default_visibility": "visible",
                "visual_priority": 1,
                "badge_tone": "accent",
                "row_click_behavior": "open_study_detail_only",
                "chart_requirement": "preferred",
                "warning_required": "Contexto de estudio; no es senal, no es filtro y no es ejecutable.",
                "never_do": "generate_signal|filter_trade|execute_order|telegram_trade_call",
            }
        ],
    )
    visual_cases = tmp_path / "visual_cases.csv"
    _write_csv(
        visual_cases,
        [
            {
                "visual_case_id": "visual_1",
                "case_source": "test",
                "symbol": "US500",
                "timeframe": "H4",
                "chart_file": "charts/us500.png",
                "exists": "True",
                "case_label": "possible_wave3_active",
                "visual_readability": "readable",
                "notes": "test chart",
                "panel_bucket_hint": "active_wave_study_candidate",
            }
        ],
    )
    no_action = tmp_path / "no_action.csv"
    _write_csv(
        no_action,
        [
            {
                "policy_id": "NOACT_01",
                "surface": "panel_global",
                "allowed_wording": "Contexto de estudio; no es senal, no es filtro y no es ejecutable.",
                "prohibited_wording": "comprar|vender|ejecutar",
                "required_behavior": "show global warning",
                "gate": "block implementation if missing",
            }
        ],
    )
    widgets = tmp_path / "widgets.csv"
    _write_csv(
        widgets,
        [
            {"widget_id": "snapshot_status", "screen_id": "overview", "source_name": "snapshot"},
            {"widget_id": "watchlist_table", "screen_id": "watchlist", "source_name": "snapshot"},
            {"widget_id": "wavecount_study_screener", "screen_id": "wavecount_study", "source_name": "wavecount"},
        ],
    )
    telegram_meta = tmp_path / "telegram_sender_review_meta.json"
    telegram_meta.write_text(
        json.dumps(
            {
                "decision": "telegram_real_sender_v1_review_passed_fail_closed",
                "telegram_connected": False,
                "telegram_real_messages_sent": 0,
            }
        ),
        encoding="utf-8",
    )
    return {
        "snapshot": snapshot,
        "security": security,
        "counts": counts,
        "migrations": migrations,
        "manifest": manifest,
        "wavecount": wavecount,
        "expanded": expanded,
        "buckets": buckets,
        "visual_cases": visual_cases,
        "no_action": no_action,
        "widgets": widgets,
        "telegram_meta": telegram_meta,
    }


def test_readonly_dashboard_generates_outputs(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path)
    output_dir = tmp_path / "out"

    build_dashboard(
        output_dir=output_dir,
        snapshot_csv=paths["snapshot"],
        security_flags_csv=paths["security"],
        counts_csv=paths["counts"],
        migrations_csv=paths["migrations"],
        export_manifest_csv=paths["manifest"],
        wavecount_csv=paths["wavecount"],
        wavecount_expanded_csv=paths["expanded"],
        wavecount_buckets_csv=paths["buckets"],
        wavecount_visual_cases_csv=paths["visual_cases"],
        wavecount_no_action_csv=paths["no_action"],
        design_widgets_csv=paths["widgets"],
        telegram_sender_review_meta=paths["telegram_meta"],
    )

    index = output_dir / "dashboard/index.html"
    assert index.exists()
    assert (output_dir / "tables/data_source_audit.csv").exists()
    assert (output_dir / "tables/widget_implementation_audit.csv").exists()
    assert (output_dir / "tables/no_action_validation.csv").exists()
    assert (output_dir / "tables/wavecount_display_validation.csv").exists()
    assert (output_dir / "tables/wavecount_panel_data_audit.csv").exists()
    assert (output_dir / "tables/wavecount_panel_implementation_audit.csv").exists()
    assert (output_dir / "tables/wavecount_panel_no_action_validation.csv").exists()
    assert (output_dir / "tables/wavecount_panel_visual_state_audit.csv").exists()
    assert (output_dir / "tables/visual_direction_audit.csv").exists()
    assert (output_dir / "tables/ai_reference_cleanup_audit.csv").exists()
    assert (output_dir / "tables/telegram_dashboard_secret_policy.csv").exists()
    assert (output_dir / "tables/no_action_visual_regression_audit.csv").exists()
    assert (output_dir / "tables/browser_smoke_audit.csv").exists()
    assert (output_dir / "tables/technical_validation_audit.csv").exists()
    assert (output_dir / "TRADING_CENTER_READONLY_V1.md").exists()
    assert (output_dir / "WAVECOUNT_STUDY_PANEL_V1.md").exists()
    assert (output_dir / "TRADING_CENTER_VISUAL_REFINEMENT_V1.md").exists()

    html = index.read_text(encoding="utf-8")
    assert "Trading Center" in html
    assert "WaveCount study panel" in html
    assert "Buckets de estudio" in html
    assert "Detalle de caso" in html
    assert "<button" not in html.lower()
    assert "<form" not in html.lower()
    assert "localStorage" not in html
    assert "sessionStorage" not in html
    assert not re.search(r"<input[^>]*(token|chat|api|secret|telegram)", html, flags=re.IGNORECASE)
    assert not re.search(r"\b(AI|IA|Codex|OpenAI|asistente|analyst)\b|hecho\s+con\s+IA", html, flags=re.IGNORECASE)
    assert "Telegram informativo" in html
    assert "El dashboard nunca pide token ni chat id" in html
    assert "environment_secrets" in html
    assert "Contexto de estudio; no es senal" in html

    run_meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert run_meta["visual_refinement_applied"] is True
    assert run_meta["ai_visible_references_removed"] is True
    assert run_meta["telegram_dashboard_secret_inputs_present"] is False
    assert run_meta["dashboard_implemented"] is True
    assert run_meta["dashboard_updated"] is True
    assert run_meta["dashboard_read_only"] is True
    assert run_meta["wavecount_panel_implemented"] is True
    assert run_meta["wavecount_study_only"] is True
    assert run_meta["sql_real_written"] is False
    assert run_meta["ddl_executed"] is False
    assert run_meta["telegram_implemented"] is False
    assert run_meta["telegram_connected"] is False
    assert run_meta["bot_implemented"] is False
    assert run_meta["mt5_connected"] is False
    assert run_meta["backtests_executed"] is False
    assert run_meta["signals_generated"] is False
    assert run_meta["wavecount_used_as_filter"] is False
    assert run_meta["wavecount_rows"] == 1

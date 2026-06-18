import json
import re
from pathlib import Path

import pandas as pd

from trading_center.telegram_mt5_bot_informational import (
    TelegramMt5BotInformationalConfig,
    build_no_action_audit,
    build_telegram_mt5_bot_informational,
)


def test_fixture_generates_outputs_and_fail_closed_flags(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "SHOULD_NOT_BE_READ")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "SHOULD_NOT_BE_READ")
    out = tmp_path / "telegram"

    result = build_telegram_mt5_bot_informational(
        TelegramMt5BotInformationalConfig(
            output_dir=out,
            doc_path=tmp_path / "docs" / "TELEGRAM_MT5_BOT_INFORMATIONAL_V1.md",
            fixture_mode=True,
            include_ai_review=True,
            include_wavecount_study=True,
        )
    )

    assert result.decision == "telegram_mt5_bot_informational_v1_ready_for_sender_gate_alignment"
    assert (out / "rendered_messages.csv").exists()
    assert (out / "rendered_messages.json").exists()
    assert (out / "tables" / "source_data_audit.csv").exists()
    assert (out / "tables" / "no_action_message_audit.csv").exists()
    assert (out / "tables" / "delivery_simulation_audit.csv").exists()
    assert (out / "run_meta.json").exists()

    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["telegram_mt5_bot_informational_implemented"] is True
    assert meta["dry_run_only"] is True
    assert meta["telegram_connected"] is False
    assert meta["telegram_messages_sent"] == 0
    assert meta["telegram_real_messages_sent"] == 0
    assert meta["telegram_command_bot_implemented"] is False
    assert meta["telegram_can_confirm"] is False
    assert meta["telegram_can_trade"] is False
    assert meta["telegram_confirms_orders"] is False
    assert meta["telegram_modifies_positions"] is False
    assert meta["telegram_tokens_read"] is False
    assert meta["telegram_chat_ids_read"] is False
    assert meta["mt5_connected"] is False
    assert meta["orders_sent"] == 0
    assert meta["mt5_orders_sent"] == 0
    assert meta["sql_real_written"] is False
    assert meta["backtests_executed"] is False

    combined = "\n".join(path.read_text(encoding="utf-8") for path in out.rglob("*.*"))
    assert "SHOULD_NOT_BE_READ" not in combined


def test_fixture_renders_required_message_types(tmp_path: Path) -> None:
    out = tmp_path / "telegram"
    build_telegram_mt5_bot_informational(
        TelegramMt5BotInformationalConfig(
            output_dir=out,
            doc_path=tmp_path / "doc.md",
            fixture_mode=True,
            include_ai_review=True,
            include_wavecount_study=True,
        )
    )

    messages = json.loads((out / "rendered_messages.json").read_text(encoding="utf-8"))
    types = {row["message_type"] for row in messages}
    assert "mt5_bot_status_digest" in types
    assert "mt5_account_snapshot_notice" in types
    assert "mt5_positions_digest" in types
    assert "riskguard_block_notice" in types
    assert "demo_order_event_notice" in types
    assert "demo_position_close_notice" in types
    assert "refresh_pipeline_notice" in types
    assert "ai_review_available_notice" in types
    assert "daily_summary" in types
    assert "wavecount_study_digest" in types

    for row in messages:
        assert "title" in row
        assert "body" in row
        assert "dedup_key" in row
        assert "cooldown_minutes" in row
        assert row["send_real"] is False
        assert row["telegram_connected"] is False
        assert row["telegram_message_sent"] is False


def test_key_mt5_messages_are_visual_and_human_readable(tmp_path: Path) -> None:
    out = tmp_path / "telegram"
    build_telegram_mt5_bot_informational(
        TelegramMt5BotInformationalConfig(output_dir=out, doc_path=tmp_path / "doc.md", fixture_mode=True)
    )
    messages = json.loads((out / "rendered_messages.json").read_text(encoding="utf-8"))
    by_type = {row["message_type"]: row["body"] for row in messages}

    status = by_type["mt5_bot_status_digest"]
    assert "Estado informativo del MT5 Bot\nDatos publicados:" in status
    assert "Decisiones shadow: 2\nDecisiones RiskGuard: 1" in status
    assert "Telegram: solo informativo\nLive trading: bloqueado" in status
    published_line = next(line for line in status.splitlines() if line.startswith("Datos publicados:"))
    assert re.fullmatch(r"Datos publicados: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", published_line)

    account = by_type["mt5_account_snapshot_notice"]
    assert "Cuenta MT5" in account
    assert "Balance:" in account
    assert "Margen libre:" in account
    assert "Lectura: 20" in account
    read_line = next(line for line in account.splitlines() if line.startswith("Lectura:"))
    assert re.fullmatch(r"Lectura: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", read_line)
    assert "floating_pnl" not in account
    assert "free_margin" not in account

    positions = by_type["mt5_positions_digest"]
    assert "Posiciones abiertas" in positions
    assert "Activo    Dir    Vol   Rentab.  Entrada  Actual" in positions
    assert "EURUSD.r  Largo  0.01" in positions
    assert "Rentabilidad flotante:" in positions
    assert "floating_pnl" not in positions
    assert "open_price" not in positions

    order_event = by_type["demo_order_event_notice"]
    assert "Orden demo" in order_event
    assert "Resultado MT5:" in order_event
    assert "Codigo broker:" in order_event
    assert "result_status" not in order_event
    assert "request_status" not in order_event


def test_wavecount_and_ai_are_opt_in(tmp_path: Path) -> None:
    out = tmp_path / "telegram"
    build_telegram_mt5_bot_informational(
        TelegramMt5BotInformationalConfig(output_dir=out, doc_path=tmp_path / "doc.md", fixture_mode=True)
    )

    messages = json.loads((out / "rendered_messages.json").read_text(encoding="utf-8"))
    types = {row["message_type"] for row in messages}
    assert "wavecount_study_digest" not in types
    assert "ai_review_available_notice" not in types


def test_wording_blocks_commands_but_allows_demo_event_language() -> None:
    rows = build_no_action_audit(
        [
            {
                "message_id": "bad_confirm",
                "message_type": "demo_order_event_notice",
                "title": "Confirma esta orden",
                "body": "Confirma esta orden desde Telegram",
            },
            {
                "message_id": "bad_execute",
                "message_type": "demo_order_event_notice",
                "title": "Ejecutar orden",
                "body": "Ejecutar orden ahora",
            },
            {
                "message_id": "safe_demo",
                "message_type": "demo_order_event_notice",
                "title": "Orden demo enviada",
                "body": "Orden demo enviada segun artifact auditado.",
            },
        ]
    )
    by_id = {row["message_id"]: row for row in rows}
    assert by_id["bad_confirm"]["audit_status"] == "blocked"
    assert by_id["bad_execute"]["audit_status"] == "blocked"
    assert by_id["safe_demo"]["audit_status"] == "pass"
    assert by_id["safe_demo"]["safe_to_send"] is True


def test_delivery_omits_events_without_condition(tmp_path: Path) -> None:
    out = tmp_path / "telegram"
    latest = tmp_path / "latest"
    latest.mkdir()
    (latest / "latest_manifest.json").write_text(json.dumps({"decision": "ok"}), encoding="utf-8")

    build_telegram_mt5_bot_informational(
        TelegramMt5BotInformationalConfig(
            latest_dir=latest,
            mt5_readonly_dir=tmp_path / "missing_mt5",
            mt5_shadow_dir=tmp_path / "missing_shadow",
            riskguard_dir=tmp_path / "missing_riskguard",
            sender_dir=tmp_path / "missing_sender",
            manager_dir=tmp_path / "missing_manager",
            ai_analyst_dir=tmp_path / "missing_ai",
            output_dir=out,
            doc_path=tmp_path / "doc.md",
            allow_missing=True,
        )
    )

    delivery = pd.read_csv(out / "tables" / "delivery_simulation_audit.csv")
    status_by_type = dict(zip(delivery["message_type"], delivery["delivery_status"]))
    assert status_by_type["mt5_bot_status_digest"] == "preview_allowed"
    assert status_by_type["mt5_account_snapshot_notice"] == "preview_allowed"
    assert status_by_type["daily_summary"] == "preview_allowed"
    assert status_by_type["riskguard_block_notice"] == "omitted_no_condition"
    assert status_by_type["demo_order_event_notice"] == "omitted_no_condition"
    assert status_by_type["demo_position_close_notice"] == "omitted_no_condition"

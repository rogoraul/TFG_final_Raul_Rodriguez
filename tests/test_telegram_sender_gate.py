import json
import subprocess
from pathlib import Path

from trading_center.telegram_sender_gate import (
    TelegramSenderGateConfig,
    TelegramSenderGateOptions,
    build_telegram_sender_gate,
)
from trading_center.telegram_mt5_bot_informational import (
    TelegramMt5BotInformationalConfig,
    build_telegram_mt5_bot_informational,
)


def test_sender_gate_blocks_all_by_default(tmp_path: Path) -> None:
    source_root = _write_gate_fixture(tmp_path)
    output_dir = tmp_path / "out"

    result = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=output_dir,
            doc_path=tmp_path / "docs" / "TELEGRAM_SENDER_GATE_V1.md",
            repo_root=tmp_path,
        )
    )

    assert result.decision == "telegram_sender_gate_v1_ready_for_sender_dry_run_review"
    assert not result.allowed_to_send
    assert len(result.blocked_to_send) == 8
    assert {row["gate_reason"] for row in result.blocked_to_send} == {"telegram_disabled"}
    assert (output_dir / "allowed_to_send.csv").exists()
    assert (output_dir / "blocked_to_send.csv").exists()
    assert (output_dir / "gate_decision_audit.csv").exists()
    assert (output_dir / "run_meta.json").exists()
    allowed_header = (output_dir / "allowed_to_send.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "title" in allowed_header
    assert "body" in allowed_header
    assert "dedup_key" in allowed_header
    assert "cooldown_minutes" in allowed_header

    meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["sender_gate_implemented"] is True
    assert meta["sender_gate_only"] is True
    assert meta["telegram_connected"] is False
    assert meta["telegram_real_messages_sent"] == 0
    assert meta["telegram_tokens_printed"] is False
    assert meta["telegram_chat_ids_printed"] is False
    assert meta["telegram_tokens_stored"] is False
    assert meta["telegram_chat_ids_stored"] is False
    assert meta["sql_real_written"] is False
    assert meta["ddl_executed"] is False
    assert meta["bot_implemented"] is False
    assert meta["mt5_connected"] is False
    assert meta["backtests_executed"] is False
    assert meta["signals_generated"] is False
    assert meta["wavecount_used_as_filter"] is False


def test_sender_gate_accepts_mt5_bot_informational_messages_when_explicitly_enabled(tmp_path: Path) -> None:
    renderer_dir = tmp_path / "renderer"
    build_telegram_mt5_bot_informational(
        TelegramMt5BotInformationalConfig(
            output_dir=renderer_dir,
            doc_path=tmp_path / "renderer.md",
            fixture_mode=True,
            include_ai_review=True,
        )
    )

    result = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=renderer_dir,
            output_dir=tmp_path / "gate",
            doc_path=tmp_path / "gate.md",
            repo_root=tmp_path,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
    )

    allowed_types = {row["message_type"] for row in result.allowed_to_send}
    assert "mt5_bot_status_digest" in allowed_types
    assert "mt5_account_snapshot_notice" in allowed_types
    assert "riskguard_block_notice" in allowed_types
    assert "demo_order_event_notice" in allowed_types
    assert "demo_position_close_notice" in allowed_types
    assert "daily_summary" in allowed_types
    assert all(row["send_real_executed"] is False for row in result.allowed_to_send)
    assert all(row["telegram_connected"] is False for row in result.allowed_to_send)
    assert all(row["telegram_real_message_sent"] is False for row in result.allowed_to_send)


def test_sender_gate_allows_safe_preview_messages_when_explicitly_enabled(tmp_path: Path) -> None:
    source_root = _write_gate_fixture(tmp_path)

    result = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=tmp_path,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
    )

    allowed_types = {row["message_type"] for row in result.allowed_to_send}
    assert allowed_types == {"platform_daily_summary", "watchlist_status_digest", "system_audit_notice"}
    assert all(row["send_real_executed"] is False for row in result.allowed_to_send)
    assert all(row["telegram_connected"] is False for row in result.allowed_to_send)
    assert _gate_reason(result, "data_health_alert") == "delivery_not_preview_allowed"
    assert "no_condition" in _gate_reasons(result, "data_health_alert")
    assert _gate_reason(result, "pipeline_error_notice") == "delivery_not_preview_allowed"
    assert _gate_reason(result, "manual_review_reminder") == "delivery_not_preview_allowed"
    assert _gate_reason(result, "wavecount_study_digest") == "delivery_not_preview_allowed"


def test_sender_gate_keeps_wavecount_blocked_unless_explicitly_allowed(tmp_path: Path) -> None:
    source_root = _write_gate_fixture(tmp_path, wavecount_delivery_status="preview_allowed")
    config = TelegramSenderGateConfig(
        input_dir=source_root / "input",
        design_dir=source_root / "design",
        output_dir=tmp_path / "out1",
        doc_path=tmp_path / "doc1.md",
        repo_root=tmp_path,
    )
    options = TelegramSenderGateOptions(
        telegram_enabled=True,
        allow_real_send=True,
        send_real=True,
        manual_confirmation=True,
        allow_wavecount_study=False,
    )

    blocked = build_telegram_sender_gate(config, options)
    assert _gate_reason(blocked, "wavecount_study_digest") == "wavecount_not_allowed"

    allowed = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=tmp_path / "out2",
            doc_path=tmp_path / "doc2.md",
            repo_root=tmp_path,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
            allow_wavecount_study=True,
        ),
    )
    wavecount_rows = [row for row in allowed.allowed_to_send if row["message_type"] == "wavecount_study_digest"]
    assert len(wavecount_rows) == 1
    assert wavecount_rows[0]["wavecount_study_only"] is True
    assert wavecount_rows[0]["send_real_executed"] is False


def test_sender_gate_blocks_unsafe_unknown_severity_and_pre_gate_send_real(tmp_path: Path) -> None:
    source_root = _write_gate_fixture(
        tmp_path,
        extra_messages=[
            _message("unsafe", "platform_daily_summary", safe_to_send=False),
            _message("unknown", "unknown_type"),
            _message("bad_severity", "platform_daily_summary", severity="critical"),
            _message("pre_send", "platform_daily_summary", send_real=True),
        ],
    )

    result = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=tmp_path,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
    )

    assert "unsafe_message" in _gate_reasons_by_id(result, "unsafe")
    assert "blocked_by_no_action" in _gate_reasons_by_id(result, "unsafe")
    assert "message_type_not_allowed" in _gate_reasons_by_id(result, "unknown")
    assert "severity_not_allowed" in _gate_reasons_by_id(result, "bad_severity")
    assert "send_real_pre_gate_true" in _gate_reasons_by_id(result, "pre_send")


def test_sender_gate_external_secret_check_is_boolean_and_never_stores_values(tmp_path: Path, monkeypatch) -> None:
    source_root = _write_gate_fixture(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    missing = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=tmp_path / "missing",
            doc_path=tmp_path / "missing.md",
            repo_root=tmp_path,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
            check_external_secrets=True,
        ),
    )
    assert all("missing_external_token" in row["gate_reasons"] for row in missing.gate_decision_audit)
    assert all("missing_external_chat_id" in row["gate_reasons"] for row in missing.gate_decision_audit)

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "SUPER_SECRET_TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    present = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=tmp_path / "present",
            doc_path=tmp_path / "present.md",
            repo_root=tmp_path,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
            check_external_secrets=True,
        ),
    )

    combined_artifacts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            tmp_path / "present" / "secret_presence_audit.csv",
            tmp_path / "present" / "run_meta.json",
            tmp_path / "present" / "TELEGRAM_SENDER_GATE_V1.md",
        ]
    )
    assert "SUPER_SECRET_TOKEN" not in combined_artifacts
    assert "123456789" not in combined_artifacts
    assert any(row["gate_decision"] == "allowed_to_send" for row in present.gate_decision_audit)


def test_sender_gate_allows_ignored_local_env_as_warning(tmp_path: Path) -> None:
    source_root = _write_gate_fixture(tmp_path)
    _git(source_root, "init")
    (source_root / ".gitignore").write_text(".env\n", encoding="utf-8")
    (source_root / ".env").write_text("SECRET_VALUE_SHOULD_NOT_APPEAR", encoding="utf-8")

    result = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=source_root,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
    )

    env_row = next(row for row in result.secret_policy_audit if row["candidate"] == ".env")
    assert env_row["policy_decision"] == "allow_local_ignored_secret_warning"
    assert env_row["blocks_gate"] is False
    assert any(row["gate_decision"] == "allowed_to_send" for row in result.gate_decision_audit)
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            tmp_path / "out" / "secret_presence_audit.csv",
            tmp_path / "out" / "secret_policy_audit.csv",
            tmp_path / "out" / "TELEGRAM_SENDER_GATE_V1.md",
        ]
    )
    assert "SECRET_VALUE_SHOULD_NOT_APPEAR" not in combined


def test_sender_gate_blocks_tracked_secret_file(tmp_path: Path) -> None:
    source_root = _write_gate_fixture(tmp_path)
    _git(source_root, "init")
    (source_root / "telegram_token.txt").write_text("SECRET_VALUE_SHOULD_NOT_APPEAR", encoding="utf-8")
    _git(source_root, "add", "-f", "telegram_token.txt")

    result = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=source_root,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
    )

    token_row = next(row for row in result.secret_policy_audit if row["candidate"] == "telegram_token.txt")
    assert token_row["policy_decision"] == "block_tracked_secret"
    assert token_row["blocks_gate"] is True
    assert all("secret_file_blocking_policy" in row["gate_reasons"] for row in result.gate_decision_audit)


def test_sender_gate_blocks_unignored_local_secret_file(tmp_path: Path) -> None:
    source_root = _write_gate_fixture(tmp_path)
    _git(source_root, "init")
    (source_root / "telegram_chat_id.txt").write_text("SECRET_VALUE_SHOULD_NOT_APPEAR", encoding="utf-8")

    result = build_telegram_sender_gate(
        TelegramSenderGateConfig(
            input_dir=source_root / "input",
            design_dir=source_root / "design",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=source_root,
        ),
        TelegramSenderGateOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
    )

    chat_row = next(row for row in result.secret_policy_audit if row["candidate"] == "telegram_chat_id.txt")
    assert chat_row["policy_decision"] == "block_unignored_local_secret"
    assert chat_row["blocks_gate"] is True
    assert all("secret_file_blocking_policy" in row["gate_reasons"] for row in result.gate_decision_audit)


def _write_gate_fixture(
    root: Path,
    *,
    wavecount_delivery_status: str = "manual_only",
    extra_messages: list[dict[str, object]] | None = None,
) -> Path:
    input_dir = root / "input"
    design_tables = root / "design" / "tables"
    (input_dir / "tables").mkdir(parents=True, exist_ok=True)
    design_tables.mkdir(parents=True, exist_ok=True)

    messages = [
        _message("platform", "platform_daily_summary"),
        _message("watchlist", "watchlist_status_digest"),
        _message("data_health", "data_health_alert", severity="warning", condition_status="no_condition"),
        _message("riskguard", "riskguard_status_notice", severity="warning", condition_status="no_condition"),
        _message("system", "system_audit_notice"),
        _message("pipeline", "pipeline_error_notice", severity="error", condition_status="no_condition"),
        _message("manual", "manual_review_reminder", severity="manual_review", condition_status="no_condition"),
        _message(
            "wavecount",
            "wavecount_study_digest",
            severity="manual_review",
            condition_status="allowed_digest" if wavecount_delivery_status == "preview_allowed" else "manual_only",
            contains_wavecount=True,
            wavecount_study_only=True,
        ),
    ]
    if extra_messages:
        messages.extend(extra_messages)

    delivery_rows = []
    no_action_rows = []
    for message in messages:
        delivery_status = (
            wavecount_delivery_status
            if message["message_type"] == "wavecount_study_digest"
            else "omitted_no_condition"
            if message["condition_status"] == "no_condition"
            else "preview_allowed"
        )
        delivery_rows.append(
            {
                "message_id": message["message_id"],
                "message_type": message["message_type"],
                "dedup_key": message["dedup_key"],
                "cooldown_minutes": message["cooldown_minutes"],
                "max_per_day": 8,
                "global_max_messages": 20,
                "safe_to_send": message["safe_to_send"],
                "condition_status": message["condition_status"],
                "condition_reason": message["condition_reason"],
                "manual_preview_required": False,
                "manual_preview": False,
                "event_count": 1 if message["condition_status"] != "no_condition" else 0,
                "send_real": False,
                "delivery_status": delivery_status,
                "delivery_reason": delivery_status,
                "would_send_in_dry_run": delivery_status == "preview_allowed",
            }
        )
        no_action_rows.append(
            {
                "message_id": message["message_id"],
                "message_type": message["message_type"],
                "safe_to_send": message["safe_to_send"],
                "blocked_patterns": "comprar" if not message["safe_to_send"] else "",
                "send_real": False,
                "audit_status": "pass" if message["safe_to_send"] else "blocked",
                "notes": "fixture",
            }
        )

    _write_csv(input_dir / "rendered_messages.csv", messages)
    (input_dir / "rendered_messages.json").write_text(json.dumps(messages, indent=2), encoding="utf-8")
    _write_csv(input_dir / "tables" / "delivery_simulation_audit.csv", delivery_rows)
    _write_csv(input_dir / "tables" / "no_action_message_audit.csv", no_action_rows)
    _write_csv(input_dir / "tables" / "source_data_audit.csv", [{"source_id": "fixture", "status": "available"}])
    (input_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "telegram_connected": False,
                "telegram_real_messages_sent": 0,
                "sql_real_written": False,
                "ddl_executed": False,
                "bot_implemented": False,
                "mt5_connected": False,
                "signals_generated": False,
                "wavecount_used_as_filter": False,
            }
        ),
        encoding="utf-8",
    )
    _write_csv(design_tables / "sender_gate_required_conditions.csv", [{"condition_id": "fixture"}])
    _write_csv(design_tables / "sender_gate_blocking_conditions.csv", [{"block_id": "fixture"}])
    _write_csv(design_tables / "sender_gate_future_config_contract.csv", [{"field": "telegram_enabled"}])
    _write_csv(design_tables / "sender_gate_audit_log_contract.csv", [{"field": "message_id"}])
    return root


def _message(
    message_id: str,
    message_type: str,
    *,
    severity: str = "info",
    safe_to_send: bool = True,
    send_real: bool = False,
    condition_status: str = "allowed_digest",
    contains_wavecount: bool = False,
    wavecount_study_only: bool = False,
) -> dict[str, object]:
    return {
        "message_id": message_id,
        "message_type": message_type,
        "severity": severity,
        "dedup_key": f"dedup:{message_id}",
        "cooldown_minutes": 120,
        "source_artifacts": "fixture.csv",
        "title": f"title {message_id}",
        "body": "Contexto informativo; no es señal, no es filtro y no es ejecutable.",
        "safe_to_send": safe_to_send,
        "why_safe": "fixture",
        "why_not_operational": "fixture",
        "contains_wavecount": contains_wavecount,
        "wavecount_study_only": wavecount_study_only,
        "condition_status": condition_status,
        "condition_reason": condition_status,
        "manual_preview_required": False,
        "event_count": 1 if condition_status != "no_condition" else 0,
        "generated_at": "2026-05-29T00:00:00Z",
        "send_real": send_real,
        "method_version": "fixture",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _gate_reason(result, message_type: str) -> str:
    return next(row["gate_reason"] for row in result.gate_decision_audit if row["message_type"] == message_type)


def _gate_reasons(result, message_type: str) -> str:
    return next(row["gate_reasons"] for row in result.gate_decision_audit if row["message_type"] == message_type)


def _gate_reasons_by_id(result, message_id: str) -> str:
    return next(row["gate_reasons"] for row in result.gate_decision_audit if row["message_id"] == message_id)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)

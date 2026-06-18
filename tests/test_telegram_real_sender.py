import json
from pathlib import Path

from trading_center.telegram_real_sender import (
    TelegramRealSenderConfig,
    TelegramRealSenderOptions,
    TelegramTransportResult,
    build_telegram_real_sender,
)


def test_real_sender_blocks_all_by_default(tmp_path: Path) -> None:
    source_root = _write_sender_fixture(tmp_path)
    output_dir = tmp_path / "out"

    result = build_telegram_real_sender(
        TelegramRealSenderConfig(
            input_dir=source_root / "gate",
            output_dir=output_dir,
            doc_path=tmp_path / "docs" / "TELEGRAM_REAL_SENDER_V1.md",
            repo_root=tmp_path,
        )
    )

    assert result.decision == "telegram_real_sender_v1_implemented_fail_closed"
    assert len(result.send_attempts) == 3
    assert not result.sent_messages_audit
    assert len(result.blocked_before_send) == 3
    assert {row["failure_reason"] for row in result.blocked_before_send} == {"telegram_disabled"}
    assert (output_dir / "send_attempts.csv").exists()
    assert (output_dir / "send_attempts.json").exists()
    assert (output_dir / "blocked_before_send.csv").exists()
    assert (output_dir / "run_meta.json").exists()

    meta = json.loads((output_dir / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["real_sender_implemented"] is True
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
    assert meta["signals_generated"] is False


def test_real_sender_sends_only_with_explicit_flags_external_secrets_and_mock_transport(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_root = _write_sender_fixture(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "SUPER_SECRET_TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    calls: list[str] = []

    def fake_transport(token: str, chat_id: str, text: str, timeout_seconds: int) -> TelegramTransportResult:
        calls.append(text)
        assert token == "SUPER_SECRET_TOKEN"
        assert chat_id == "123456789"
        assert timeout_seconds == 10
        return TelegramTransportResult(True, "telegram_api_ok", "hash123")

    result = build_telegram_real_sender(
        TelegramRealSenderConfig(
            input_dir=source_root / "gate",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=tmp_path,
        ),
        TelegramRealSenderOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
        transport=fake_transport,
    )

    assert result.decision == "telegram_real_sender_v1_real_send_executed"
    assert len(calls) == 3
    assert len(result.sent_messages_audit) == 3
    assert not result.blocked_before_send
    assert all(row["send_real_executed"] is True for row in result.sent_messages_audit)
    assert all(row["telegram_connected"] is True for row in result.sent_messages_audit)

    combined = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / "out").rglob("*.*"))
    assert "SUPER_SECRET_TOKEN" not in combined
    assert "123456789" not in combined


def test_real_sender_blocks_explicit_send_when_external_secrets_are_missing(tmp_path: Path, monkeypatch) -> None:
    source_root = _write_sender_fixture(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = build_telegram_real_sender(
        TelegramRealSenderConfig(
            input_dir=source_root / "gate",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=tmp_path,
        ),
        TelegramRealSenderOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
        transport=_failing_transport,
    )

    assert not result.sent_messages_audit
    assert len(result.blocked_before_send) == 3
    assert all("missing_external_token" in row["pre_send_reasons"] for row in result.blocked_before_send)
    assert all("missing_external_chat_id" in row["pre_send_reasons"] for row in result.blocked_before_send)


def test_real_sender_blocks_non_allowed_or_previously_sent_rows(tmp_path: Path, monkeypatch) -> None:
    source_root = _write_sender_fixture(
        tmp_path,
        extra_allowed_rows=[
            _allowed_row("bad_gate", "platform_daily_summary", gate_decision="blocked_to_send"),
            _allowed_row("already_sent", "platform_daily_summary", send_real_executed=True),
        ],
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")

    result = build_telegram_real_sender(
        TelegramRealSenderConfig(
            input_dir=source_root / "gate",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=tmp_path,
        ),
        TelegramRealSenderOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
            max_messages=10,
        ),
        transport=_success_transport,
    )

    assert _reason(result, "bad_gate") == "message_not_allowed_by_gate"
    assert _reason(result, "already_sent") == "send_real_already_executed"


def test_real_sender_blocks_operational_wording_and_missing_content(tmp_path: Path, monkeypatch) -> None:
    source_root = _write_sender_fixture(
        tmp_path,
        allowed_rows=[
            _allowed_row("unsafe", "platform_daily_summary", body="Comprar ahora"),
            _allowed_row("accented_signal", "platform_daily_summary", body="Se\u00f1al de compra"),
            _allowed_row("missing_body", "system_audit_notice", body=""),
        ],
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")

    result = build_telegram_real_sender(
        TelegramRealSenderConfig(
            input_dir=source_root / "gate",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=tmp_path,
        ),
        TelegramRealSenderOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
        ),
        transport=_success_transport,
    )

    assert _reason(result, "unsafe") == "operational_wording_detected"
    assert _reason(result, "accented_signal") == "operational_wording_detected"
    assert _reason(result, "missing_body") == "message_content_missing"
    assert not result.sent_messages_audit


def test_real_sender_allows_safe_mt5_demo_order_notice_but_blocks_confirmation_language(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_root = _write_sender_fixture(
        tmp_path,
        allowed_rows=[
            _allowed_row(
                "safe_demo_order",
                "demo_order_event_notice",
                delivery_status="event_allowed",
                body="Orden demo enviada segun artifact auditado. Telegram solo informa; no solicita ni confirma operaciones.",
            ),
            _allowed_row(
                "bad_confirm_order",
                "demo_order_event_notice",
                delivery_status="event_allowed",
                body="Confirmar esta orden desde Telegram.",
            ),
            _allowed_row(
                "bad_execute_order",
                "demo_order_event_notice",
                delivery_status="event_allowed",
                body="Ejecutar esta orden ahora.",
            ),
        ],
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")

    result = build_telegram_real_sender(
        TelegramRealSenderConfig(
            input_dir=source_root / "gate",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=tmp_path,
        ),
        TelegramRealSenderOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
            max_messages=10,
        ),
        transport=_success_transport,
    )

    sent_ids = {row["message_id"] for row in result.sent_messages_audit}
    assert "safe_demo_order" in sent_ids
    assert _reason(result, "bad_confirm_order") == "operational_wording_detected"
    assert _reason(result, "bad_execute_order") == "operational_wording_detected"


def test_real_sender_keeps_wavecount_off_by_default_and_allows_only_when_explicit(tmp_path: Path, monkeypatch) -> None:
    source_root = _write_sender_fixture(
        tmp_path,
        allowed_rows=[_allowed_row("wave", "wavecount_study_digest", severity="manual_review", contains_wavecount=True)],
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")
    config = TelegramRealSenderConfig(
        input_dir=source_root / "gate",
        output_dir=tmp_path / "blocked",
        doc_path=tmp_path / "blocked.md",
        repo_root=tmp_path,
    )
    options = TelegramRealSenderOptions(
        telegram_enabled=True,
        allow_real_send=True,
        send_real=True,
        manual_confirmation=True,
        allowed_message_types=("wavecount_study_digest",),
        allowed_severities=("manual_review",),
    )

    blocked = build_telegram_real_sender(config, options, transport=_success_transport)
    assert _reason(blocked, "wave") == "wavecount_not_allowed"

    allowed = build_telegram_real_sender(
        TelegramRealSenderConfig(
            input_dir=source_root / "gate",
            output_dir=tmp_path / "allowed",
            doc_path=tmp_path / "allowed.md",
            repo_root=tmp_path,
        ),
        TelegramRealSenderOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
            allow_wavecount_study=True,
            allowed_message_types=("wavecount_study_digest",),
            allowed_severities=("manual_review",),
        ),
        transport=_success_transport,
    )
    assert len(allowed.sent_messages_audit) == 1
    assert allowed.sent_messages_audit[0]["contains_wavecount"] is True


def test_real_sender_respects_max_messages(tmp_path: Path, monkeypatch) -> None:
    source_root = _write_sender_fixture(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT")

    result = build_telegram_real_sender(
        TelegramRealSenderConfig(
            input_dir=source_root / "gate",
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            repo_root=tmp_path,
        ),
        TelegramRealSenderOptions(
            telegram_enabled=True,
            allow_real_send=True,
            send_real=True,
            manual_confirmation=True,
            max_messages=1,
        ),
        transport=_success_transport,
    )

    assert len(result.sent_messages_audit) == 1
    assert len(result.blocked_before_send) == 2
    assert all(row["failure_reason"] == "max_messages_exceeded" for row in result.blocked_before_send)


def _write_sender_fixture(
    root: Path,
    *,
    allowed_rows: list[dict[str, object]] | None = None,
    extra_allowed_rows: list[dict[str, object]] | None = None,
) -> Path:
    gate = root / "gate"
    gate.mkdir(parents=True, exist_ok=True)
    rows = allowed_rows or [
        _allowed_row("platform", "platform_daily_summary"),
        _allowed_row("watchlist", "watchlist_status_digest"),
        _allowed_row("system", "system_audit_notice"),
    ]
    if extra_allowed_rows:
        rows.extend(extra_allowed_rows)
    _write_csv(gate / "allowed_to_send.csv", rows)
    _write_csv(gate / "blocked_to_send.csv", [])
    _write_csv(gate / "gate_decision_audit.csv", rows)
    _write_csv(gate / "gate_config_audit.csv", [{"config_key": "sender_gate_only", "config_value": True}])
    _write_csv(gate / "secret_policy_audit.csv", [{"candidate": ".env", "policy_decision": "not_present"}])
    (gate / "run_meta.json").write_text(
        json.dumps(
            {
                "phase": "telegram_sender_gate_v1",
                "sender_gate_only": True,
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
    return root


def _allowed_row(
    message_id: str,
    message_type: str,
    *,
    severity: str = "info",
    gate_decision: str = "allowed_to_send",
    send_real_executed: bool = False,
    body: str = "Contexto informativo; no es senal, no es filtro y no es ejecutable.",
    delivery_status: str = "preview_allowed",
    contains_wavecount: bool = False,
) -> dict[str, object]:
    return {
        "message_id": message_id,
        "message_type": message_type,
        "severity": severity,
        "gate_decision": gate_decision,
        "gate_reason": "allowed_in_gate_dry_run",
        "gate_reasons": "allowed_in_gate_dry_run",
        "safe_to_send": True,
        "no_action_audit_status": "pass",
        "delivery_status": delivery_status,
        "condition_status": "allowed_digest",
        "condition_reason": "fixture",
        "contains_wavecount": contains_wavecount,
        "wavecount_study_only": contains_wavecount,
        "original_send_real": False,
        "send_real_requested": True,
        "send_real_executed": send_real_executed,
        "telegram_connected": False,
        "telegram_real_message_sent": False,
        "sender_gate_only": True,
        "source_artifacts": "fixture",
        "evaluated_at": "2026-05-29T00:00:00Z",
        "title": f"Title {message_id}",
        "body": body,
        "dedup_key": f"dedup:{message_id}",
        "cooldown_minutes": 120,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _success_transport(token: str, chat_id: str, text: str, timeout_seconds: int) -> TelegramTransportResult:
    return TelegramTransportResult(True, "telegram_api_ok", "hash")


def _failing_transport(token: str, chat_id: str, text: str, timeout_seconds: int) -> TelegramTransportResult:
    raise AssertionError("transport must not be called")


def _reason(result, message_id: str) -> str:
    return next(row["failure_reason"] for row in result.send_attempts if row["message_id"] == message_id)

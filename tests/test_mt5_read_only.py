import json
from pathlib import Path

from trading_center import mt5_read_only
from trading_center.mt5_read_only import Mt5ReadOnlyConfig, execute


def test_audit_only_does_not_import_mt5(tmp_path: Path, monkeypatch) -> None:
    def fail_import():
        raise AssertionError("MT5 import should not happen in audit-only")

    monkeypatch.setattr(mt5_read_only, "import_mt5", fail_import)
    result = execute(Mt5ReadOnlyConfig(output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md", audit_only=True))

    assert result.run_meta["audit_only"] is True
    assert result.run_meta["mt5_connection_attempted"] is False
    assert result.run_meta["mt5_connected"] is False
    assert result.run_meta["mt5_orders_sent"] == 0


def test_default_does_not_connect(tmp_path: Path, monkeypatch) -> None:
    def fail_import():
        raise AssertionError("MT5 import should not happen by default")

    monkeypatch.setattr(mt5_read_only, "import_mt5", fail_import)
    result = execute(Mt5ReadOnlyConfig(output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md"))

    assert result.run_meta["mt5_connection_attempted"] is False
    assert result.run_meta["mt5_connected"] is False
    policy = _read_csv_text(tmp_path / "out" / "tables" / "mt5_connection_policy_audit.csv")
    assert "connect_flag_false_default_no_connection" in policy


def test_connect_requires_env_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(mt5_read_only.READ_ONLY_ENV, raising=False)
    monkeypatch.delenv(mt5_read_only.TRADING_DISABLED_ENV, raising=False)

    def fail_import():
        raise AssertionError("MT5 import should not happen when gates are missing")

    monkeypatch.setattr(mt5_read_only, "import_mt5", fail_import)
    result = execute(Mt5ReadOnlyConfig(output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md", connect=True))

    assert result.decision == "mt5_read_only_connection_v1_blocked_by_mt5_environment"
    assert result.run_meta["mt5_connection_attempted"] is False
    assert result.run_meta["mt5_connected"] is False
    assert "blocked_by_readonly_config" in _read_csv_text(tmp_path / "out" / "tables" / "issues_or_risks.csv")


def test_fixture_generates_snapshots_and_manifest(tmp_path: Path) -> None:
    result = execute(Mt5ReadOnlyConfig(output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md", fixture_mode=True))
    out = tmp_path / "out"

    assert (out / "mt5_account_snapshot.csv").exists()
    assert (out / "mt5_account_snapshot.json").exists()
    assert (out / "mt5_positions_snapshot.csv").exists()
    assert (out / "mt5_positions_snapshot.json").exists()
    assert (out / "mt5_pending_orders_snapshot.csv").exists()
    assert (out / "mt5_pending_orders_snapshot.json").exists()
    assert (out / "mt5_readonly_manifest.json").exists()
    assert len(result.position_rows) == 2
    assert len(result.pending_order_rows) == 1

    manifest = json.loads((out / "mt5_readonly_manifest.json").read_text(encoding="utf-8"))
    assert manifest["read_only"] is True
    assert manifest["positions_count"] == 2
    assert manifest["pending_orders_count"] == 1
    assert manifest["can_send_order_any_true"] is False


def test_account_id_is_hashed_and_secrets_are_not_stored(tmp_path: Path) -> None:
    out = tmp_path / "out"
    execute(Mt5ReadOnlyConfig(output_dir=out, doc_path=tmp_path / "doc.md", fixture_mode=True))
    account = json.loads((out / "mt5_account_snapshot.json").read_text(encoding="utf-8"))[0]
    all_output = "\n".join(path.read_text(encoding="utf-8") for path in out.rglob("*") if path.is_file() and path.suffix in {".json", ".csv", ".md"})

    assert account["account_id_hash"] != "fixture-account"
    assert len(account["account_id_hash"]) == 16
    assert "fixture-account" not in all_output
    assert "password" not in all_output.lower() or "password_printed" in all_output
    assert "login_printed" in all_output
    assert "CLI has no login argument." in all_output
    assert "CLI has no password argument." in all_output


def test_broker_server_are_sanitized_in_real_snapshot_builder() -> None:
    account = {
        "login": 123456,
        "company": "Broker password secret",
        "server": "server=secret-host",
        "currency": "EUR",
        "balance": 1,
        "equity": 1,
        "margin": 0,
        "margin_free": 1,
        "margin_level": 0,
    }
    rows, positions, pending = mt5_read_only.build_real_snapshots(
        Mt5ReadOnlyConfig(account_label="test"),
        mt5_read_only.datetime.now(mt5_read_only.timezone.utc),
        terminal_info=None,
        account_info=account,
        positions=(),
        pending_orders=(),
        mt5_connected=True,
    )

    assert rows[0]["account_id_hash"] != "123456"
    assert rows[0]["broker_name_sanitized"] == "sanitized"
    assert rows[0]["server_name_sanitized"] == "sanitized"
    assert positions == []
    assert pending == []


def test_positions_and_pending_outputs_are_read_only(tmp_path: Path) -> None:
    result = execute(Mt5ReadOnlyConfig(output_dir=tmp_path / "out", doc_path=tmp_path / "doc.md", fixture_mode=True))

    assert {row["can_modify_position"] for row in result.position_rows} == {False}
    assert {row["can_send_order"] for row in result.position_rows} == {False}
    assert {row["can_send_order"] for row in result.pending_order_rows} == {False}
    assert result.run_meta["can_modify_position_any_true"] is False
    assert result.run_meta["can_send_order_any_true"] is False


def test_exposure_is_calculated(tmp_path: Path) -> None:
    out = tmp_path / "out"
    execute(Mt5ReadOnlyConfig(output_dir=out, doc_path=tmp_path / "doc.md", fixture_mode=True))

    exposure = _read_csv_text(out / "tables" / "mt5_exposure_audit.csv")
    assert "EURUSD.r" in exposure
    assert "XAUUSD.r" in exposure
    assert "long_volume" in exposure
    assert "short_volume" in exposure


def test_run_meta_fail_closed(tmp_path: Path) -> None:
    out = tmp_path / "out"
    execute(Mt5ReadOnlyConfig(output_dir=out, doc_path=tmp_path / "doc.md", fixture_mode=True))
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))

    assert meta["mt5_readonly_connection_implemented"] is True
    assert meta["mt5_mode"] == "read_only"
    assert meta["mt5_orders_enabled"] is False
    assert meta["mt5_orders_sent"] == 0
    assert meta["telegram_connected"] is False
    assert meta["telegram_can_trade"] is False
    assert meta["sql_real_written"] is False
    assert meta["ddl_executed"] is False
    assert meta["orders_sent"] == 0
    assert meta["signals_generated"] is False
    assert meta["backtests_executed"] is False


def test_no_trading_tokens_exist_in_module_source() -> None:
    source = Path(mt5_read_only.__file__).read_text(encoding="utf-8")
    forbidden = [
        "order" + "_send",
        "TRADE_ACTION_" + "DEAL",
        "TRADE_ACTION_" + "PENDING",
        "position" + "_close",
    ]
    for token in forbidden:
        assert token not in source


def test_cli_parse_has_no_credentials_arguments() -> None:
    args = mt5_read_only.parse_args(["--fixture-mode", "--account-label", "demo_review"])
    assert not hasattr(args, "password")
    assert not hasattr(args, "login")
    assert args.fixture_mode is True
    assert args.account_label == "demo_review"


def _read_csv_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

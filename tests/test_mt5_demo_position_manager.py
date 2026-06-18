from __future__ import annotations

from pathlib import Path

from trading_center import mt5_demo_position_manager as manager
from trading_center.mt5_demo_position_manager import Mt5DemoPositionManagerConfig, execute


def test_fixture_dry_run_prepares_close_without_closing(tmp_path: Path) -> None:
    result = execute(
        Mt5DemoPositionManagerConfig(
            output_dir=tmp_path,
            doc_path=tmp_path / "doc.md",
            fixture_mode=True,
            dry_run=True,
            connect=True,
            close_demo_positions=True,
            audit_only=False,
        )
    )

    assert len(result.request_rows) == 1
    assert result.result_rows[0]["result_status"] == "not_closed_dry_run"
    assert result.run_meta["positions_closed"] == 0


def test_missing_confirmation_blocks(tmp_path: Path) -> None:
    account, positions, _confirmations = manager.fixture_inputs(manager.utc_now())
    manager.write_csv(tmp_path / "account.csv", account)
    manager.write_csv(tmp_path / "positions.csv", positions)
    result = execute(
        Mt5DemoPositionManagerConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            mt5_positions_snapshot_csv=tmp_path / "positions.csv",
            manual_confirmations_csv=tmp_path / "missing_confirmations.csv",
            allow_missing_inputs=True,
        )
    )

    assert result.request_rows == []
    assert result.result_rows[0]["result_status"] == "blocked_by_missing_manual_confirmation"


def test_non_demo_account_blocks(tmp_path: Path) -> None:
    account, positions, confirmations = manager.fixture_inputs(manager.utc_now())
    account[0]["account_label"] = "live_account"
    account[0]["server_name_sanitized"] = "Live-Server"
    manager.write_csv(tmp_path / "account.csv", account)
    manager.write_csv(tmp_path / "positions.csv", positions)
    manager.write_csv(tmp_path / "confirmations.csv", confirmations)
    result = execute(
        Mt5DemoPositionManagerConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            mt5_positions_snapshot_csv=tmp_path / "positions.csv",
            manual_confirmations_csv=tmp_path / "confirmations.csv",
        )
    )

    assert result.request_rows == []
    assert result.result_rows[0]["result_status"] == "blocked_by_no_demo_account"


def test_symbol_filter_only_prepares_matching_position(tmp_path: Path) -> None:
    result = execute(
        Mt5DemoPositionManagerConfig(
            output_dir=tmp_path,
            doc_path=tmp_path / "doc.md",
            fixture_mode=True,
            dry_run=True,
            connect=True,
            close_demo_positions=True,
            audit_only=False,
            symbol="EURUSD.r",
        )
    )

    assert len(result.request_rows) == 1
    assert result.request_rows[0]["symbol"] == "EURUSD.r"


def test_multiple_positions_same_symbol_block_as_ambiguous(tmp_path: Path) -> None:
    account, positions, confirmations = manager.fixture_inputs(manager.utc_now())
    second = dict(positions[0])
    second["position_id_hash"] = "fixture-position-hash-2"
    positions.append(second)
    confirmations.append(
        {
            "manual_confirmation_id": "fixture-position-close-confirmation-2",
            "position_id_hash": "fixture-position-hash-2",
            "status": "confirmed",
        }
    )
    manager.write_csv(tmp_path / "account.csv", account)
    manager.write_csv(tmp_path / "positions.csv", positions)
    manager.write_csv(tmp_path / "confirmations.csv", confirmations)

    result = execute(
        Mt5DemoPositionManagerConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            mt5_positions_snapshot_csv=tmp_path / "positions.csv",
            manual_confirmations_csv=tmp_path / "confirmations.csv",
        )
    )

    assert result.request_rows == []
    assert {row["result_status"] for row in result.result_rows} == {"blocked_by_multiple_positions_same_symbol"}


def test_default_cli_is_audit_only_without_close_flag(tmp_path: Path) -> None:
    args = manager.parse_args(["--fixture-mode", "--output-dir", str(tmp_path), "--doc-path", str(tmp_path / "doc.md")])
    config = manager.Mt5DemoPositionManagerConfig(
        output_dir=args.output_dir,
        doc_path=args.doc_path,
        fixture_mode=args.fixture_mode,
        audit_only=bool(args.audit_only or not args.close_demo_positions),
        close_demo_positions=args.close_demo_positions,
    )

    assert config.audit_only is True
    assert config.close_demo_positions is False


def test_run_meta_keeps_non_trading_boundaries(tmp_path: Path) -> None:
    result = execute(Mt5DemoPositionManagerConfig(output_dir=tmp_path, doc_path=tmp_path / "doc.md", fixture_mode=True))

    assert result.run_meta["live_trading_enabled"] is False
    assert result.run_meta["telegram_connected"] is False
    assert result.run_meta["sql_real_written"] is False


def test_readonly_ticket_hash_matches_readonly_snapshot_hash() -> None:
    assert manager.readonly_ticket_hash(123456789) == "15e2b0d3c33891eb"

from __future__ import annotations

import json
from pathlib import Path

from trading_center import mt5_demo_order_sender as sender
from trading_center.mt5_demo_order_sender import Mt5DemoOrderSenderConfig, execute


def test_fixture_audit_only_prepares_request_without_sending(tmp_path: Path) -> None:
    result = execute(Mt5DemoOrderSenderConfig(output_dir=tmp_path, doc_path=tmp_path / "doc.md", fixture_mode=True))

    assert (tmp_path / "demo_order_requests.csv").exists()
    assert (tmp_path / "demo_order_results.csv").exists()
    assert len(result.request_rows) == 1
    assert result.result_rows[0]["result_status"] == "not_sent_audit_only"
    assert result.run_meta["orders_sent"] == 0
    assert result.run_meta["mt5_orders_sent"] == 0


def test_default_cli_is_audit_only_unless_send_requested(tmp_path: Path) -> None:
    args = sender.parse_args(["--fixture-mode", "--output-dir", str(tmp_path), "--doc-path", str(tmp_path / "doc.md")])
    config = sender.Mt5DemoOrderSenderConfig(
        output_dir=args.output_dir,
        doc_path=args.doc_path,
        fixture_mode=args.fixture_mode,
        audit_only=bool(args.audit_only or not args.send_demo_orders),
        send_demo_orders=args.send_demo_orders,
    )

    assert config.audit_only is True
    assert config.send_demo_orders is False


def test_missing_manual_confirmation_blocks(tmp_path: Path) -> None:
    intents, decisions, accounts, _confirmations = sender.fixture_inputs(sender.utc_now())
    sender.write_csv(tmp_path / "intents.csv", intents)
    sender.write_csv(tmp_path / "decisions.csv", decisions)
    sender.write_csv(tmp_path / "account.csv", accounts)
    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            intents_csv=tmp_path / "intents.csv",
            riskguard_decisions_csv=tmp_path / "decisions.csv",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            manual_confirmations_csv=tmp_path / "missing_confirmations.csv",
            allow_missing_inputs=True,
        )
    )

    assert result.request_rows == []
    assert result.result_rows[0]["result_status"] == "blocked_by_missing_manual_confirmation"


def test_non_demo_account_blocks(tmp_path: Path) -> None:
    intents, decisions, accounts, confirmations = sender.fixture_inputs(sender.utc_now())
    accounts[0]["account_mode"] = "real"
    accounts[0]["account_label"] = "live_account"
    sender.write_csv(tmp_path / "intents.csv", intents)
    sender.write_csv(tmp_path / "decisions.csv", decisions)
    sender.write_csv(tmp_path / "account.csv", accounts)
    sender.write_csv(tmp_path / "confirmations.csv", confirmations)
    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            intents_csv=tmp_path / "intents.csv",
            riskguard_decisions_csv=tmp_path / "decisions.csv",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            manual_confirmations_csv=tmp_path / "confirmations.csv",
        )
    )

    assert result.request_rows == []
    assert result.result_rows[0]["result_status"] == "blocked_by_no_demo_account"


def test_riskguard_not_accepted_blocks(tmp_path: Path) -> None:
    intents, decisions, accounts, confirmations = sender.fixture_inputs(sender.utc_now())
    decisions[0]["riskguard_decision"] = "blocked_by_late_setup"
    sender.write_csv(tmp_path / "intents.csv", intents)
    sender.write_csv(tmp_path / "decisions.csv", decisions)
    sender.write_csv(tmp_path / "account.csv", accounts)
    sender.write_csv(tmp_path / "confirmations.csv", confirmations)
    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            intents_csv=tmp_path / "intents.csv",
            riskguard_decisions_csv=tmp_path / "decisions.csv",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            manual_confirmations_csv=tmp_path / "confirmations.csv",
        )
    )

    assert result.result_rows[0]["result_status"] == "blocked_by_riskguard"


def test_send_flag_without_environment_does_not_send(tmp_path: Path) -> None:
    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path,
            doc_path=tmp_path / "doc.md",
            fixture_mode=True,
            audit_only=False,
            dry_run=False,
            connect=True,
            send_demo_orders=True,
        )
    )

    assert result.request_rows == []
    assert result.result_rows[0]["result_status"] == "blocked_by_environment_gates"
    assert result.run_meta["orders_sent"] == 0


def test_dry_run_with_send_flag_prepares_but_does_not_send(tmp_path: Path) -> None:
    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path,
            doc_path=tmp_path / "doc.md",
            fixture_mode=True,
            audit_only=False,
            dry_run=True,
            connect=True,
            send_demo_orders=True,
        )
    )

    assert len(result.request_rows) == 1
    assert result.result_rows[0]["result_status"] == "not_sent_dry_run"
    assert result.run_meta["orders_sent"] == 0


def test_no_live_or_telegram_flags_in_run_meta(tmp_path: Path) -> None:
    result = execute(Mt5DemoOrderSenderConfig(output_dir=tmp_path, doc_path=tmp_path / "doc.md", fixture_mode=True))

    assert result.run_meta["live_trading_enabled"] is False
    assert result.run_meta["telegram_connected"] is False
    assert result.run_meta["sql_real_written"] is False


def test_output_json_matches_request_rows(tmp_path: Path) -> None:
    result = execute(Mt5DemoOrderSenderConfig(output_dir=tmp_path, doc_path=tmp_path / "doc.md", fixture_mode=True))
    payload = json.loads((tmp_path / "demo_order_requests.json").read_text(encoding="utf-8"))

    assert len(payload) == len(result.request_rows)


def test_missing_volume_is_calculated_from_risk_and_sl(tmp_path: Path) -> None:
    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path,
            doc_path=tmp_path / "doc.md",
            fixture_mode=True,
            dry_run=True,
            audit_only=False,
            connect=True,
            send_demo_orders=True,
        )
    )

    assert result.request_rows[0]["volume_source"] == "risk_pct_equity_entry_sl"
    assert result.request_rows[0]["sizing_status"] == "calculated"
    assert result.request_rows[0]["volume"] == "0.05"
    assert result.request_rows[0]["risk_amount"] == "25.00"


def test_missing_sizing_metadata_blocks_without_min_lot_fallback(tmp_path: Path) -> None:
    intents, decisions, accounts, confirmations = sender.fixture_inputs(sender.utc_now())
    intents[0]["entry_price"] = ""
    intents[0]["volume"] = ""
    sender.write_csv(tmp_path / "intents.csv", intents)
    sender.write_csv(tmp_path / "decisions.csv", decisions)
    sender.write_csv(tmp_path / "account.csv", accounts)
    sender.write_csv(tmp_path / "confirmations.csv", confirmations)

    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            intents_csv=tmp_path / "intents.csv",
            riskguard_decisions_csv=tmp_path / "decisions.csv",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            manual_confirmations_csv=tmp_path / "confirmations.csv",
        )
    )

    assert result.request_rows == []
    assert result.result_rows[0]["result_status"] == "blocked_by_missing_entry"


def test_blocked_sizing_status_blocks_even_with_volume(tmp_path: Path) -> None:
    intents, decisions, accounts, confirmations = sender.fixture_inputs(sender.utc_now())
    intents[0]["volume"] = "0.05"
    intents[0]["sizing_status"] = "blocked"
    sender.write_csv(tmp_path / "intents.csv", intents)
    sender.write_csv(tmp_path / "decisions.csv", decisions)
    sender.write_csv(tmp_path / "account.csv", accounts)
    sender.write_csv(tmp_path / "confirmations.csv", confirmations)

    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            intents_csv=tmp_path / "intents.csv",
            riskguard_decisions_csv=tmp_path / "decisions.csv",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            manual_confirmations_csv=tmp_path / "confirmations.csv",
        )
    )

    assert result.request_rows == []
    assert result.result_rows[0]["result_status"] == "blocked_by_sizing"


def test_min_lot_fallback_must_be_explicit(tmp_path: Path) -> None:
    intents, decisions, accounts, confirmations = sender.fixture_inputs(sender.utc_now())
    intents[0]["entry_price"] = "1.1000"
    intents[0]["sl"] = ""
    intents[0]["volume"] = ""
    sender.write_csv(tmp_path / "intents.csv", intents)
    sender.write_csv(tmp_path / "decisions.csv", decisions)
    sender.write_csv(tmp_path / "account.csv", accounts)
    sender.write_csv(tmp_path / "confirmations.csv", confirmations)

    result = execute(
        Mt5DemoOrderSenderConfig(
            output_dir=tmp_path / "out",
            doc_path=tmp_path / "doc.md",
            intents_csv=tmp_path / "intents.csv",
            riskguard_decisions_csv=tmp_path / "decisions.csv",
            mt5_account_snapshot_csv=tmp_path / "account.csv",
            manual_confirmations_csv=tmp_path / "confirmations.csv",
            allow_min_lot_fallback=True,
        )
    )

    assert result.request_rows == []
    assert result.result_rows[0]["result_status"] == "blocked_by_missing_sl"

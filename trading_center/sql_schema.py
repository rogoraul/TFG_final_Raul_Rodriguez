from __future__ import annotations

from pathlib import Path


SCHEMA_NAME = "trading_ops"

RUN_KIND_POLICY = {
    "bootstrap_current": {
        "is_operational": True,
        "description": "Current snapshot used as the first SQL baseline after cutover.",
    },
    "live_observed": {
        "is_operational": True,
        "description": "Snapshots generated after cutover as observed live operational history.",
    },
    "historical_backfill": {
        "is_operational": False,
        "description": "Old or reconstructed data for research; excluded from operational views.",
    },
    "test_fixture": {
        "is_operational": False,
        "description": "Synthetic/test loads; never visible to operational consumers.",
    },
}

CORE_TABLES = [
    "schema_migrations",
    "snapshot_runs",
    "live_context_snapshot_rows",
    "snapshot_source_inventory",
    "strategy_registry",
    "signal_events",
    "risk_config",
    "bot_config",
    "data_health_snapshot",
]

DEFERRED_TABLES = [
    "technical_indicator_snapshot",
    "wavecount_context_snapshot",
    "correlation_snapshot",
    "trade_quality_snapshot",
    "bot_state",
    "dry_run_decision_ledger",
    "open_positions_snapshot",
    "telegram_event_queue",
    "telegram_sent_log",
    "manual_signal_annotations",
]

CORE_VIEWS = [
    "v_live_context_latest",
    "v_dashboard_trading_center",
    "v_dashboard_watchlist",
    "v_signal_events_latest",
    "v_data_health_latest",
    "v_bot_config_active",
    "v_risk_config_active",
]

SECURITY_DEFAULTS = {
    "snapshot_runs.run_kind": "bootstrap_current",
    "snapshot_runs.is_operational": "1",
    "live_context_snapshot_rows.is_read_only": "1",
    "live_context_snapshot_rows.can_execute_order": "0",
    "live_context_snapshot_rows.wavecount_should_filter_trade": "0",
    "bot_config.bot_enabled": "0",
    "bot_config.mode": "off",
    "bot_config.mt5_enabled": "0",
    "bot_config.live_enabled": "0",
    "bot_config.requires_manual_approval": "1",
    "risk_config.kill_switch_enabled": "1",
}

DDL_DIR = Path("sql/ops")
CORE_TABLES_DDL = DDL_DIR / "001_create_operational_core.sql"
CORE_VIEWS_DDL = DDL_DIR / "002_create_operational_core_views.sql"


def load_core_tables_ddl(repo_root: Path | None = None) -> str:
    return _read_sql(CORE_TABLES_DDL, repo_root=repo_root)


def load_core_views_ddl(repo_root: Path | None = None) -> str:
    return _read_sql(CORE_VIEWS_DDL, repo_root=repo_root)


def load_core_ddl(repo_root: Path | None = None) -> str:
    return "\n\n".join(
        [
            load_core_tables_ddl(repo_root=repo_root),
            load_core_views_ddl(repo_root=repo_root),
        ]
    )


def assert_no_deferred_tables_in_ddl(ddl_text: str) -> None:
    lower = ddl_text.lower()
    forbidden = [table for table in DEFERRED_TABLES if table.lower() in lower]
    if forbidden:
        raise ValueError(f"DDL contains deferred tables: {', '.join(forbidden)}")


def _read_sql(relative_path: Path, *, repo_root: Path | None = None) -> str:
    root = repo_root or Path(__file__).resolve().parents[1]
    return (root / relative_path).read_text(encoding="utf-8")

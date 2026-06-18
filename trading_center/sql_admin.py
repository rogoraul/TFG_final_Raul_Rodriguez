from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import mysql.connector
import pandas as pd

from data.sql.db_config import load_db_config
from trading_center.sql_loader import load_snapshot_artifacts_to_store
from trading_center.sql_schema import CORE_TABLES_DDL, CORE_VIEWS_DDL, SCHEMA_NAME
from trading_center.sql_store import MySqlOperationalStore


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "artifacts" / "tfg" / "live_context_snapshot_v0"
DEFAULT_VERIFY_DIR = REPO_ROOT / "artifacts" / "tfg" / "sql_operational_core_v0_2026-05-25"
DEFAULT_EXPORT_DIR = REPO_ROOT / "artifacts" / "tfg" / "sql_operational_core_v0_export"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

MIGRATIONS = [
    (
        "001_create_operational_core",
        CORE_TABLES_DDL,
        "Create SQL operational core tables.",
    ),
    (
        "002_create_operational_core_views",
        CORE_VIEWS_DDL,
        "Create SQL operational core views.",
    ),
]


def audit_connection_config() -> dict[str, Any]:
    config, source = load_db_config()
    return {
        "host": config.get("host"),
        "port": config.get("port"),
        "user": config.get("user"),
        "database": config.get("database"),
        "has_password": bool(config.get("password")),
        "config_source": source,
        "is_local": is_local_host(str(config.get("host"))),
    }


def connect_local_mysql(*, use_config_database: bool = True):
    config, _ = load_db_config()
    if not is_local_host(str(config.get("host"))):
        raise RuntimeError("Refusing to connect: TRADING_DB_HOST is not local.")
    connect_config = dict(config)
    if not use_config_database:
        connect_config.pop("database", None)
    return mysql.connector.connect(**connect_config)


def apply_core_ddl(connection, *, repo_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    applied = []
    for migration_id, relative_path, description in MIGRATIONS:
        sql_path = repo_root / relative_path
        sql_text = sql_path.read_text(encoding="utf-8")
        execute_sql_text(connection, sql_text)
        checksum = sha256_text(sql_text)
        register_migration(connection, migration_id, checksum, description)
        applied.append(
            {
                "migration_id": migration_id,
                "checksum": checksum,
                "description": description,
                "path": str(relative_path),
            }
        )
    connection.commit()
    return applied


def load_bootstrap_snapshot(connection, snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR):
    use_schema(connection)
    store = MySqlOperationalStore(connection)
    result = load_snapshot_artifacts_to_store(
        snapshot_dir,
        store,
        run_kind="bootstrap_current",
        data_origin="live_context_snapshot_v0",
    )
    connection.commit()
    return result


def verify_sql_core(connection) -> dict[str, Any]:
    use_schema(connection)
    table_counts = {
        name: scalar(connection, f"SELECT COUNT(*) FROM {name}")
        for name in [
            "snapshot_runs",
            "live_context_snapshot_rows",
            "snapshot_source_inventory",
            "signal_events",
            "data_health_snapshot",
        ]
    }
    view_counts = {
        name: scalar(connection, f"SELECT COUNT(*) FROM {name}")
        for name in [
            "v_live_context_latest",
            "v_dashboard_trading_center",
        ]
    }
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "schema_name": SCHEMA_NAME,
        "table_counts": table_counts,
        "view_counts": view_counts,
        "run_kind_distribution": grouped_counts(connection, "snapshot_runs", "run_kind"),
        "is_operational_distribution": grouped_counts(connection, "snapshot_runs", "is_operational"),
        "hard_flag_counts": {
            "can_execute_order_true": scalar(
                connection,
                "SELECT COUNT(*) FROM live_context_snapshot_rows WHERE can_execute_order <> 0",
            ),
            "wavecount_should_filter_trade_true": scalar(
                connection,
                "SELECT COUNT(*) FROM live_context_snapshot_rows WHERE wavecount_should_filter_trade <> 0",
            ),
            "non_read_only_rows": scalar(
                connection,
                "SELECT COUNT(*) FROM live_context_snapshot_rows WHERE is_read_only <> 1",
            ),
            "non_operational_backfill_or_test_visible": scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM snapshot_runs
                WHERE run_kind IN ('historical_backfill', 'test_fixture')
                  AND is_operational <> 0
                """,
            ),
        },
    }
    return summary


def write_verification_artifacts(summary: dict[str, Any], output_dir: Path = DEFAULT_VERIFY_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sql_load_verification.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    rows = []
    for group_name in ["table_counts", "view_counts", "hard_flag_counts"]:
        for key, value in summary[group_name].items():
            rows.append({"metric_group": group_name, "metric": key, "value": value})
    for key, value in summary["run_kind_distribution"].items():
        rows.append({"metric_group": "run_kind_distribution", "metric": key, "value": value})
    for key, value in summary["is_operational_distribution"].items():
        rows.append({"metric_group": "is_operational_distribution", "metric": str(key), "value": value})
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(tables_dir / "sql_load_verification.csv", index=False)


def export_latest_snapshot(connection, output_dir: Path = DEFAULT_EXPORT_DIR) -> dict[str, Any]:
    use_schema(connection)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = query_dataframe(
        connection,
        """
        SELECT *
        FROM v_live_context_latest
        ORDER BY symbol, strategy, timeframe_ltf, timeframe_htf, side, setup_id
        """,
    )
    csv_path = output_dir / "live_context_snapshot_from_sql.csv"
    json_path = output_dir / "live_context_snapshot_from_sql.json"
    frame.to_csv(csv_path, index=False)
    json_payload = frame.astype("object").where(pd.notna(frame), None).to_dict(orient="records")
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "trading_ops.v_live_context_latest",
        "rows": int(len(frame)),
        "csv_path": str(csv_path.relative_to(REPO_ROOT)),
        "json_path": str(json_path.relative_to(REPO_ROOT)),
        "real_sql_executed": True,
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def register_migration(connection, migration_id: str, checksum: str, description: str) -> None:
    use_schema(connection)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO schema_migrations (migration_id, checksum, description)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
              checksum = VALUES(checksum),
              description = VALUES(description)
            """,
            (migration_id, checksum, description),
        )
    finally:
        cursor.close()


def execute_sql_text(connection, sql_text: str) -> None:
    cursor = connection.cursor()
    try:
        for statement in split_sql_statements(sql_text):
            cursor.execute(statement)
    finally:
        cursor.close()


def split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape = False
    for char in sql_text:
        current.append(char)
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == ";":
            statement = "".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def use_schema(connection) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {SCHEMA_NAME}")
    finally:
        cursor.close()


def scalar(connection, query: str, params: tuple[Any, ...] | None = None) -> Any:
    cursor = connection.cursor()
    try:
        cursor.execute(query, params or ())
        row = cursor.fetchone()
        return row[0] if row else 0
    finally:
        cursor.close()


def grouped_counts(connection, table_name: str, column_name: str) -> dict[str, int]:
    cursor = connection.cursor()
    try:
        cursor.execute(f"SELECT {column_name}, COUNT(*) FROM {table_name} GROUP BY {column_name}")
        return {str(key): int(value) for key, value in cursor.fetchall()}
    finally:
        cursor.close()


def query_dataframe(connection, query: str) -> pd.DataFrame:
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description] if cursor.description else []
    finally:
        cursor.close()
    return pd.DataFrame(rows, columns=columns)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_local_host(host: str) -> bool:
    return host.strip().lower() in LOCAL_HOSTS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply and verify the SQL operational core v0 on a local MySQL server.")
    parser.add_argument("--apply-core", action="store_true", help="Apply DDL, register migrations, load bootstrap snapshot and export verification.")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--verification-dir", type=Path, default=DEFAULT_VERIFY_DIR)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    audit = audit_connection_config()
    if not args.apply_core:
        print(json.dumps({"connection_audit": audit, "applied": False}, indent=2, ensure_ascii=False))
        return
    if not audit["is_local"]:
        raise SystemExit("Refusing to apply SQL: configured host is not local.")
    connection = connect_local_mysql(use_config_database=True)
    try:
        migrations = apply_core_ddl(connection)
        first_load = load_bootstrap_snapshot(connection, args.snapshot_dir)
        second_load = load_bootstrap_snapshot(connection, args.snapshot_dir)
        verification = verify_sql_core(connection)
        verification["connection_audit"] = audit
        verification["migrations"] = migrations
        verification["first_load"] = first_load.__dict__
        verification["second_load"] = second_load.__dict__
        write_verification_artifacts(verification, args.verification_dir)
        export_meta = export_latest_snapshot(connection, args.export_dir)
        print(
            json.dumps(
                {
                    "applied": True,
                    "schema_name": SCHEMA_NAME,
                    "migrations": [item["migration_id"] for item in migrations],
                    "verification": verification,
                    "export": export_meta,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

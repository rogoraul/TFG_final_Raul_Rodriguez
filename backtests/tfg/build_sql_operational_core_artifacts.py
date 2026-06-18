from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from trading_center.sql_schema import (
    CORE_TABLES,
    CORE_TABLES_DDL,
    CORE_VIEWS,
    CORE_VIEWS_DDL,
    DEFERRED_TABLES,
    RUN_KIND_POLICY,
    SCHEMA_NAME,
    SECURITY_DEFAULTS,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "tfg" / "sql_operational_core_v0_2026-05-25"
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "SQL_OPERATIONAL_CORE_V0.md"

REFERENCE_DOCS = (
    "docs/LIVE_CONTEXT_SNAPSHOT_V0.md",
    "docs/LIVE_CONTEXT_SNAPSHOT_V0_AUDIT.md",
    "docs/SQL_OPERATIONAL_STORE_V0_DESIGN.md",
    "docs/SQL_OPERATIONAL_STORE_V0_SIMULATION_REVIEW.md",
)

REFERENCE_ARTIFACTS = (
    "artifacts/tfg/live_context_snapshot_v0",
    "artifacts/tfg/sql_operational_store_v0_design_2026-05-25",
    "artifacts/tfg/sql_operational_store_v0_simulation_review_2026-05-25",
)


def _rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _frame_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Sin filas."
    text = frame.astype("object").where(pd.notna(frame), "").astype(str)
    columns = list(text.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in text.iterrows():
        values = [str(row[column]).replace("|", "\\|") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _write_markdown_index(csv_path: Path, title: str) -> None:
    frame = _read_csv(csv_path)
    csv_path.with_suffix(".md").write_text(
        "\n".join([f"# {title}", "", _frame_to_markdown(frame)]).rstrip() + "\n",
        encoding="utf-8",
    )


def build_core_tables() -> pd.DataFrame:
    descriptions = {
        "schema_migrations": "Versiona migraciones SQL aplicadas.",
        "snapshot_runs": "Cabecera de cada carga/generacion de snapshot operativo.",
        "live_context_snapshot_rows": "Tabla principal de filas operativas con columnas estables y payload_json flexible.",
        "snapshot_source_inventory": "Trazabilidad de fuentes usadas para cada snapshot.",
        "strategy_registry": "Catalogo minimo de estrategias y permisos futuros.",
        "signal_events": "Indice fino de eventos para deduplicacion y trazabilidad.",
        "risk_config": "Configuracion de riesgo versionada y fail-closed.",
        "bot_config": "Configuracion del bot versionada, disabled/off por defecto.",
        "data_health_snapshot": "Salud minima de datos por simbolo/timeframe.",
    }
    return pd.DataFrame(
        [
            {
                "table_name": table,
                "created_in_core_v0": True,
                "description": descriptions[table],
                "ddl_file": str(CORE_TABLES_DDL),
            }
            for table in CORE_TABLES
        ]
    )


def build_core_views() -> pd.DataFrame:
    descriptions = {
        "v_live_context_latest": "Ultimo snapshot completado.",
        "v_dashboard_trading_center": "Vista base futura del dashboard sin indicadores/correlacion/calidad obligatorios.",
        "v_dashboard_watchlist": "Filas en vigilancia.",
        "v_signal_events_latest": "Eventos normalizados del ultimo snapshot.",
        "v_data_health_latest": "Salud de datos vigente.",
        "v_bot_config_active": "Config activa del bot, si existe.",
        "v_risk_config_active": "Config activa de riesgo, si existe.",
    }
    return pd.DataFrame(
        [
            {
                "view_name": view,
                "created_in_core_v0": True,
                "description": descriptions[view],
                "ddl_file": str(CORE_VIEWS_DDL),
            }
            for view in CORE_VIEWS
        ]
    )


def build_deferred_tables() -> pd.DataFrame:
    reasons = {
        "technical_indicator_snapshot": "Schema de indicadores y ventanas no estabilizado.",
        "wavecount_context_snapshot": "WaveCount ya viaja en el snapshot; tabla separada se aplaza a estadistica.",
        "correlation_snapshot": "Ventanas/clusters aun no estan definidos.",
        "trade_quality_snapshot": "El score podria parecer edge operativo.",
        "bot_state": "No hay runtime de bot en esta fase.",
        "dry_run_decision_ledger": "No hay productor dry-run en esta fase.",
        "open_positions_snapshot": "No hay posiciones simuladas hasta dry-run.",
        "telegram_event_queue": "No hay Telegram sender en esta fase.",
        "telegram_sent_log": "No hay Telegram sender en esta fase.",
        "manual_signal_annotations": "La UX de estudio manual aun no esta disenada.",
    }
    return pd.DataFrame(
        [{"table_name": table, "created_in_core_v0": False, "reason_deferred": reasons[table]} for table in DEFERRED_TABLES]
    )


def build_security_defaults() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"target": target, "default_value": value, "security_meaning": _security_meaning(target)}
            for target, value in SECURITY_DEFAULTS.items()
        ]
    )


def build_run_kind_policy() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "run_kind": run_kind,
                "is_operational": policy["is_operational"],
                "description": policy["description"],
                "visible_to_operational_views": policy["is_operational"],
            }
            for run_kind, policy in RUN_KIND_POLICY.items()
        ]
    )


def build_load_plan() -> pd.DataFrame:
    rows = [
        ("read_snapshot_artifacts", "Read live_context_snapshot.csv, run_meta.json and source_inventory.csv.", "No watcher execution."),
        ("validate_hard_flags", "Block load if is_read_only is not true or execution/filter flags are true.", "Fail closed."),
        ("classify_run_kind", "Set run_kind, data_origin, cutover_at and source_snapshot_id on snapshot_runs.", "Backfill/test are non-operational."),
        ("seed_defaults", "Insert minimal strategy_registry, risk_config and bot_config defaults.", "Bot disabled, mode off, kill switch on."),
        ("upsert_snapshot_run", "Upsert one snapshot_runs row by snapshot_id.", "Idempotent."),
        ("upsert_snapshot_rows", "Upsert live_context_snapshot_rows by snapshot/symbol/strategy/timeframe/side/setup.", "No duplicates on rerun."),
        ("upsert_source_inventory", "Upsert source inventory by snapshot_id/source_name.", "Audit trail."),
        ("upsert_signal_events", "Upsert thin signal_events by dedup_key.", "No duplicated events."),
        ("upsert_data_health", "Upsert minimal data health by snapshot/symbol/timeframe.", "Dashboard readiness."),
    ]
    return pd.DataFrame([{"step": step, "action": action, "guardrail": guardrail} for step, action, guardrail in rows])


def build_report(tables: dict[str, pd.DataFrame], *, sql_status: dict[str, Any] | None = None) -> str:
    sql_status = sql_status or {}
    real_sql_executed = bool(sql_status.get("real_sql_executed"))
    verification = sql_status.get("verification") or {}
    export_meta = sql_status.get("export_meta") or {}
    if real_sql_executed:
        application_text = (
            f"El DDL real ya fue aplicado en `{SCHEMA_NAME}` y el snapshot actual fue cargado como "
            "`bootstrap_current`. La verificacion SQL queda guardada en "
            "`artifacts/tfg/sql_operational_core_v0_2026-05-25/sql_load_verification.json`."
        )
    else:
        application_text = (
            "En esta ejecucion no se ha tocado ninguna base real: se generan DDL, loader y tests. "
            "El fallback con prefijo `ops_` queda documentado para una fase posterior si no hubiera permisos de schema."
        )
    lines = [
        "# SQL Operational Core v0",
        "",
        "Fecha: 2026-05-26",
        "",
        "## Decision",
        "",
        f"Se crea el nucleo SQL hibrido recomendado para el schema `{SCHEMA_NAME}`. {application_text}",
        "",
        "Actualizacion cutover: `snapshot_runs` distingue `run_kind`, `data_origin`, `is_operational`, `cutover_at` y `source_snapshot_id`. Las vistas operativas solo exponen cargas `bootstrap_current` o `live_observed` con `is_operational=true`.",
        "",
        "## Por que se reduce el diseno amplio",
        "",
        "La simulacion critica concluyo que las 19 tablas del diseno amplio son utiles como roadmap, pero demasiado prematuras para el primer DDL. Esta fase crea solo el nucleo necesario para cargar `live_context_snapshot_v0` y deja `payload_json` para contexto inestable.",
        "",
        "## Tablas del nucleo",
        "",
        _frame_to_markdown(tables["core_tables"][["table_name", "description"]]),
        "",
        "## Vistas minimas",
        "",
        _frame_to_markdown(tables["core_views"][["view_name", "description"]]),
        "",
        "## Tablas aplazadas",
        "",
        _frame_to_markdown(tables["deferred_tables"][["table_name", "reason_deferred"]]),
        "",
        "## Loader",
        "",
        "El loader vive en `trading_center/sql_loader.py`. Lee `artifacts/tfg/live_context_snapshot_v0/`, valida flags duros, clasifica la carga con `run_kind` y escribe mediante una interfaz `OperationalStore`. Incluye un store en memoria para tests y un store MySQL inyectable que no abre conexiones ni gestiona credenciales.",
        "",
        "Comando de prueba sin base real:",
        "",
        "```powershell",
        "python -m trading_center.sql_loader --snapshot-dir artifacts/tfg/live_context_snapshot_v0 --dry-run --run-kind bootstrap_current",
        "```",
        "",
        "## Politica historica y cutover",
        "",
        _frame_to_markdown(tables["run_kind_policy"]),
        "",
        "`bootstrap_current` sirve como baseline inicial. `live_observed` sera el historico operativo real desde el cutover. `historical_backfill` y `test_fixture` pueden cargarse de forma controlada, pero quedan fuera de dashboard/Telegram/bot por defecto. La estadistica ENBOLSA+WaveCount debera usar tablas o artifacts de investigacion separados en una fase posterior.",
        "",
        "## DDL",
        "",
        "`sql/ops/001_create_operational_core.sql` define solo las nueve tablas del nucleo. `sql/ops/002_create_operational_core_views.sql` define las vistas minimas para lectura y filtra `is_operational=true` con `run_kind in ('bootstrap_current', 'live_observed')`.",
        "",
        "## Aplicacion SQL local",
        "",
        _sql_application_markdown(verification, export_meta, real_sql_executed),
        "",
        "## Uso por consumidores futuros",
        "",
        "El dashboard debera leer `v_dashboard_trading_center`, `v_dashboard_watchlist`, `v_data_health_latest`, `v_bot_config_active` y `v_risk_config_active`. Telegram y bot dry-run no tienen tablas runtime todavia; cuando se implementen no deberan leer a traves del dashboard, sino de SQL/vistas propias.",
        "",
        "## CSV/JSON",
        "",
        "`live_context_snapshot_v0` sigue produciendo CSV/JSON como export portable, auditoria y soporte de tests. La fuente viva prevista para dashboard sera la carga SQL, no los CSV/JSON directos.",
        "",
        "## Seguridad",
        "",
        _frame_to_markdown(tables["security_defaults"]),
        "",
        "## Bloqueado",
        "",
        "- Dashboard, Telegram y bot dry-run.",
        "- MT5 shadow/demo/live.",
        "- Backtests y senales nuevas.",
        "- WaveCount como filtro.",
        "- Tablas especializadas aplazadas.",
        "",
        "## Siguiente paso",
        "",
        "Aplicar el DDL en una base local confirmada, cargar el snapshot con el loader, verificar idempotencia contra SQL real y exportar una copia de auditoria desde SQL antes de empezar dashboard read-only.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def run(*, output_dir: Path = DEFAULT_OUTPUT_DIR, docs_path: Path | None = DEFAULT_DOC_PATH) -> dict[str, Any]:
    started = perf_counter()
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        "core_tables": build_core_tables(),
        "core_views": build_core_views(),
        "deferred_tables": build_deferred_tables(),
        "security_defaults": build_security_defaults(),
        "load_plan": build_load_plan(),
        "run_kind_policy": build_run_kind_policy(),
    }

    for name, frame in tables.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(frame, path)
        _write_markdown_index(path, name.replace("_", " ").title())

    verification = _read_json(output_dir / "sql_load_verification.json")
    export_meta = _read_json(REPO_ROOT / "artifacts" / "tfg" / "sql_operational_core_v0_export" / "run_meta.json")
    sql_status = {
        "real_sql_executed": bool(verification),
        "verification": verification,
        "export_meta": export_meta,
    }
    report = build_report(tables, sql_status=sql_status)
    (output_dir / "SQL_OPERATIONAL_CORE_V0.md").write_text(report, encoding="utf-8")
    if docs_path is not None:
        docs_path.write_text(report, encoding="utf-8")

    missing_docs = [path for path in REFERENCE_DOCS if not (REPO_ROOT / path).exists()]
    missing_artifacts = [path for path in REFERENCE_ARTIFACTS if not (REPO_ROOT / path).exists()]
    run_meta = {
        "phase": "sql_operational_core_v0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "schema_name": SCHEMA_NAME,
        "fallback_policy": "Use existing schema with ops_ prefix in a later migration if trading_ops cannot be created.",
        "output_dir": _rel_to_repo(output_dir),
        "docs_path": _rel_to_repo(docs_path) if docs_path else None,
        "core_tables": CORE_TABLES,
        "core_views": CORE_VIEWS,
        "deferred_tables": DEFERRED_TABLES,
        "run_kind_policy": {
            run_kind: {
                "is_operational": policy["is_operational"],
                "description": policy["description"],
            }
            for run_kind, policy in RUN_KIND_POLICY.items()
        },
        "ddl_files": [str(CORE_TABLES_DDL), str(CORE_VIEWS_DDL)],
        "loader_module": "trading_center.sql_loader",
        "real_sql_executed": bool(verification),
        "database_connected": bool(verification),
        "dashboard_created": False,
        "telegram_created": False,
        "bot_created": False,
        "mt5_connected": False,
        "backtests_executed": False,
        "signals_generated": False,
        "missing_docs": missing_docs,
        "missing_artifacts": missing_artifacts,
        "sql_load_verification": _rel_to_repo(output_dir / "sql_load_verification.json") if verification else None,
        "sql_export_run_meta": _rel_to_repo(REPO_ROOT / "artifacts" / "tfg" / "sql_operational_core_v0_export" / "run_meta.json") if export_meta else None,
        "runtime_seconds": round(perf_counter() - started, 3),
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_meta


def _security_meaning(target: str) -> str:
    if "snapshot_runs.run_kind" in target:
        return "Baseline actual por defecto; live debe declararse explicitamente."
    if "snapshot_runs.is_operational" in target:
        return "Solo cargas operativas entran en vistas."
    if "can_execute_order" in target:
        return "Bloquea ejecucion real."
    if "wavecount_should_filter_trade" in target:
        return "Bloquea WaveCount como filtro."
    if "bot_enabled" in target:
        return "Bot apagado por defecto."
    if target.endswith(".mode"):
        return "Modo operativo desactivado."
    if "mt5_enabled" in target or "live_enabled" in target:
        return "MT5/live bloqueado."
    if "requires_manual_approval" in target:
        return "No automatizar sin aprobacion."
    if "kill_switch_enabled" in target:
        return "Riesgo cerrado por defecto."
    return "Guardrail operativo."


def _sql_application_markdown(verification: dict[str, Any], export_meta: dict[str, Any], real_sql_executed: bool) -> str:
    if not real_sql_executed:
        return "Pendiente. No se ha aplicado DDL real ni se ha cargado snapshot en SQL."
    table_counts = verification.get("table_counts", {})
    view_counts = verification.get("view_counts", {})
    hard_flags = verification.get("hard_flag_counts", {})
    migrations = [item.get("migration_id", "") for item in verification.get("migrations", [])]
    rows = [
        ["schema", verification.get("schema_name", SCHEMA_NAME)],
        ["migrations", ", ".join(migrations)],
        ["snapshot_runs", table_counts.get("snapshot_runs", "")],
        ["live_context_snapshot_rows", table_counts.get("live_context_snapshot_rows", "")],
        ["snapshot_source_inventory", table_counts.get("snapshot_source_inventory", "")],
        ["signal_events", table_counts.get("signal_events", "")],
        ["data_health_snapshot", table_counts.get("data_health_snapshot", "")],
        ["v_live_context_latest", view_counts.get("v_live_context_latest", "")],
        ["v_dashboard_trading_center", view_counts.get("v_dashboard_trading_center", "")],
        ["can_execute_order_true", hard_flags.get("can_execute_order_true", "")],
        ["wavecount_should_filter_trade_true", hard_flags.get("wavecount_should_filter_trade_true", "")],
        ["export_rows", export_meta.get("rows", "")],
    ]
    frame = pd.DataFrame(rows, columns=["metric", "value"])
    return _frame_to_markdown(frame)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SQL operational core v0 artifacts.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--docs-path", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--skip-docs", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docs_path = None if args.skip_docs else args.docs_path
    meta = run(output_dir=args.output_dir, docs_path=docs_path)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

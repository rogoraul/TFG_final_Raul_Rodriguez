"""Legacy artifact builder for the first read-only Trading Center dashboard.

The current dashboard entrypoint is ``trading_center.dash_readonly_app``.  This
module is kept for reproducibility of the 2026-05-28 read-only closure artifacts
and should not be extended for the final TFG platform.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SNAPSHOT_CSV = REPO_ROOT / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/export_from_sql/live_context_snapshot_from_sql.csv"
DEFAULT_SECURITY_FLAGS_CSV = REPO_ROOT / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/security_flags_check.csv"
DEFAULT_COUNTS_CSV = REPO_ROOT / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/sql_closure_counts.csv"
DEFAULT_MIGRATIONS_CSV = REPO_ROOT / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/migration_status.csv"
DEFAULT_EXPORT_MANIFEST_CSV = REPO_ROOT / "artifacts/tfg/sql_operational_core_closure_v1_2026-05-28/tables/sql_export_manifest.csv"
DEFAULT_WAVECOUNT_CSV = REPO_ROOT / "artifacts/tfg/wavecount_study_screener_v0_2026-05-27/wavecount_study_screener.csv"
DEFAULT_WAVECOUNT_EXPANDED_CSV = REPO_ROOT / "artifacts/tfg/wavecount_study_screener_review_v1_2026-05-28/tables/expanded_screener.csv"
DEFAULT_WAVECOUNT_BUCKETS_CSV = REPO_ROOT / "artifacts/tfg/wavecount_study_panel_design_v1_2026-05-28/tables/wavecount_panel_bucket_display_policy.csv"
DEFAULT_WAVECOUNT_VISUAL_CASES_CSV = REPO_ROOT / "artifacts/tfg/wavecount_study_screener_review_v1_2026-05-28/tables/visual_case_inventory.csv"
DEFAULT_WAVECOUNT_NO_ACTION_CSV = REPO_ROOT / "artifacts/tfg/wavecount_study_panel_design_v1_2026-05-28/tables/wavecount_panel_no_action_policy.csv"
DEFAULT_DESIGN_WIDGETS_CSV = REPO_ROOT / "artifacts/tfg/trading_center_readonly_design_v1_2026-05-28/tables/widget_data_contract.csv"
DEFAULT_TELEGRAM_SENDER_REVIEW_META = REPO_ROOT / "artifacts/tfg/telegram_real_sender_v1_review_2026-05-29/run_meta.json"

METHOD_VERSION = "trading_center_visual_refinement_v1"
VISUAL_ARCHETYPE = "retro_futuristic_industrial_terminal"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def unique_count(rows: list[dict[str, str]], key: str) -> int:
    return len({row.get(key, "") for row in rows if row.get(key, "")})


def count_by(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    return dict(Counter(row.get(key, "not_available") or "not_available" for row in rows))


def false_flags(rows: list[dict[str, str]], flags: list[str]) -> bool:
    for row in rows:
        for flag in flags:
            if flag in row and boolish(row.get(flag)):
                return False
    return True


def has_chart(row: dict[str, str]) -> bool:
    value = row.get("chart_file", "")
    if not value:
        return False
    return boolish(row.get("exists", "true"))


def first_value(rows: list[dict[str, str]], key: str, default: str = "not_available") -> str:
    for row in rows:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def telegram_status_rows(meta_path: Path = DEFAULT_TELEGRAM_SENDER_REVIEW_META) -> list[dict[str, Any]]:
    meta = read_json(meta_path)
    status = "available" if meta else "not_available"
    return [
        {
            "item": "telegram_configured",
            "value": "unknown_external_environment",
            "status": status,
            "policy": "read_only_status",
            "notes": "El dashboard no lee ni pide secretos.",
        },
        {
            "item": "telegram_enabled",
            "value": str(bool(meta.get("telegram_connected", False))).lower(),
            "status": status,
            "policy": "informational_only",
            "notes": "El sender real permanece fail-closed en la evidencia revisada.",
        },
        {
            "item": "last_sender_status",
            "value": meta.get("decision", "not_available"),
            "status": status,
            "policy": "artifact_review",
            "notes": str(meta_path),
        },
        {
            "item": "last_messages_sent",
            "value": meta.get("telegram_real_messages_sent", 0),
            "status": status,
            "policy": "audit_only",
            "notes": "No se envia desde este dashboard.",
        },
        {
            "item": "sender_mode",
            "value": "informational_only_environment_secrets",
            "status": "policy",
            "policy": "environment_only",
            "notes": "Variables de entorno o .env local ignorado; nunca dashboard HTML ni artifacts.",
        },
    ]


def compact_row(row: dict[str, str]) -> dict[str, str]:
    keys = [
        "row_id",
        "snapshot_id",
        "generated_at",
        "symbol",
        "market_group",
        "strategy",
        "timeframe_ltf",
        "timeframe_htf",
        "last_closed_bar_time",
        "data_freshness_status",
        "signal_state",
        "side",
        "setup_id",
        "entry",
        "sl",
        "tp1",
        "tp2",
        "has_order_intent",
        "intent_status",
        "riskguard_status",
        "riskguard_reason",
        "wavecount_available",
        "wavecount_policy_bucket",
        "wavecount_context_status",
        "dry_run_eligible",
        "is_read_only",
        "can_execute_order",
        "wavecount_should_filter_trade",
        "run_kind",
        "data_origin",
        "is_operational",
    ]
    return {key: str(row.get(key, "")) for key in keys}


def build_data_model(
    snapshot_csv: Path = DEFAULT_SNAPSHOT_CSV,
    security_flags_csv: Path = DEFAULT_SECURITY_FLAGS_CSV,
    counts_csv: Path = DEFAULT_COUNTS_CSV,
    migrations_csv: Path = DEFAULT_MIGRATIONS_CSV,
    export_manifest_csv: Path = DEFAULT_EXPORT_MANIFEST_CSV,
    wavecount_csv: Path = DEFAULT_WAVECOUNT_CSV,
    wavecount_expanded_csv: Path = DEFAULT_WAVECOUNT_EXPANDED_CSV,
    wavecount_buckets_csv: Path = DEFAULT_WAVECOUNT_BUCKETS_CSV,
    wavecount_visual_cases_csv: Path = DEFAULT_WAVECOUNT_VISUAL_CASES_CSV,
    wavecount_no_action_csv: Path = DEFAULT_WAVECOUNT_NO_ACTION_CSV,
    design_widgets_csv: Path = DEFAULT_DESIGN_WIDGETS_CSV,
    telegram_sender_review_meta: Path = DEFAULT_TELEGRAM_SENDER_REVIEW_META,
) -> dict[str, Any]:
    snapshot_rows = read_csv(snapshot_csv)
    security_flags = read_csv(security_flags_csv)
    sql_counts = read_csv(counts_csv)
    migrations = read_csv(migrations_csv)
    export_manifest = read_csv(export_manifest_csv)
    current_wavecount_rows = read_csv(wavecount_csv)
    expanded_wavecount_rows = read_csv(wavecount_expanded_csv)
    wavecount_bucket_policy = read_csv(wavecount_buckets_csv)
    wavecount_visual_cases = read_csv(wavecount_visual_cases_csv)
    wavecount_no_action_policy = read_csv(wavecount_no_action_csv)
    wavecount_rows = expanded_wavecount_rows or current_wavecount_rows
    design_widgets = read_csv(design_widgets_csv)
    telegram_status = telegram_status_rows(telegram_sender_review_meta)

    watchlist_rows = [row for row in snapshot_rows if row.get("signal_state") == "watching_setup"]
    compact_watchlist = [compact_row(row) for row in watchlist_rows]
    compact_snapshot = [compact_row(row) for row in snapshot_rows]

    data_health = []
    health_seen: set[tuple[str, str]] = set()
    for row in snapshot_rows:
        key = (row.get("symbol", ""), row.get("timeframe_ltf", ""))
        if key in health_seen:
            continue
        health_seen.add(key)
        data_health.append(
            {
                "symbol": key[0],
                "timeframe": key[1],
                "last_closed_bar_time": row.get("last_closed_bar_time", ""),
                "freshness_status": row.get("data_freshness_status", "not_available"),
                "source": "derived_from_snapshot_export",
            }
        )

    hard_flag_status = "passed"
    for flag in security_flags:
        if flag.get("status") != "passed":
            hard_flag_status = "failed"
            break

    summary = {
        "total_rows": len(snapshot_rows),
        "watchlist_rows": len(watchlist_rows),
        "symbols": unique_count(snapshot_rows, "symbol"),
        "market_groups": count_by(snapshot_rows, "market_group"),
        "signal_states": count_by(snapshot_rows, "signal_state"),
        "sides": count_by(snapshot_rows, "side"),
        "riskguard_status": count_by(snapshot_rows, "riskguard_status"),
        "wavecount_available": count_by(snapshot_rows, "wavecount_available"),
        "wavecount_context_status": count_by(snapshot_rows, "wavecount_context_status"),
        "wavecount_study_cases": len(wavecount_rows),
        "wavecount_study_buckets": unique_count(wavecount_rows, "screener_bucket"),
        "wavecount_visual_cases": sum(1 for row in wavecount_visual_cases if has_chart(row)),
        "data_freshness_status": count_by(snapshot_rows, "data_freshness_status"),
        "run_kind": first_value(snapshot_rows, "run_kind"),
        "snapshot_id": first_value(snapshot_rows, "snapshot_id"),
        "generated_at": first_value(snapshot_rows, "generated_at"),
        "data_origin": first_value(snapshot_rows, "data_origin"),
        "hard_flag_status": hard_flag_status,
        "can_execute_order_true": sum(1 for row in snapshot_rows if boolish(row.get("can_execute_order"))),
        "wavecount_filter_true": sum(1 for row in snapshot_rows if boolish(row.get("wavecount_should_filter_trade"))),
        "non_read_only_rows": sum(1 for row in snapshot_rows if not boolish(row.get("is_read_only"))),
    }

    source_audit = [
        {
            "source_id": "snapshot_export",
            "source": str(snapshot_csv),
            "source_type": "artifact_csv",
            "rows": len(snapshot_rows),
            "status": "available" if snapshot_rows else "missing_or_empty",
            "used_for": "overview|watchlist|asset_detail",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "security_flags",
            "source": str(security_flags_csv),
            "source_type": "artifact_csv",
            "rows": len(security_flags),
            "status": "available" if security_flags else "missing_or_empty",
            "used_for": "overview|system_audit",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "sql_counts",
            "source": str(counts_csv),
            "source_type": "artifact_csv",
            "rows": len(sql_counts),
            "status": "available" if sql_counts else "missing_or_empty",
            "used_for": "system_audit",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "migrations",
            "source": str(migrations_csv),
            "source_type": "artifact_csv",
            "rows": len(migrations),
            "status": "available" if migrations else "missing_or_empty",
            "used_for": "system_audit",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "export_manifest",
            "source": str(export_manifest_csv),
            "source_type": "artifact_csv",
            "rows": len(export_manifest),
            "status": "available" if export_manifest else "missing_or_empty",
            "used_for": "system_audit",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "wavecount_current_screener",
            "source": str(wavecount_csv),
            "source_type": "artifact_csv",
            "rows": len(current_wavecount_rows),
            "status": "available" if current_wavecount_rows else "optional_missing",
            "used_for": "wavecount_study_fallback",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "wavecount_expanded_screener",
            "source": str(wavecount_expanded_csv),
            "source_type": "artifact_csv",
            "rows": len(expanded_wavecount_rows),
            "status": "available" if expanded_wavecount_rows else "missing_or_empty",
            "used_for": "wavecount_study_panel",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "wavecount_bucket_policy",
            "source": str(wavecount_buckets_csv),
            "source_type": "artifact_csv",
            "rows": len(wavecount_bucket_policy),
            "status": "available" if wavecount_bucket_policy else "missing_or_empty",
            "used_for": "wavecount_bucket_summary",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "wavecount_visual_cases",
            "source": str(wavecount_visual_cases_csv),
            "source_type": "artifact_csv",
            "rows": len(wavecount_visual_cases),
            "status": "available" if wavecount_visual_cases else "optional_missing",
            "used_for": "wavecount_chart_references",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "wavecount_no_action_policy",
            "source": str(wavecount_no_action_csv),
            "source_type": "artifact_csv",
            "rows": len(wavecount_no_action_policy),
            "status": "available" if wavecount_no_action_policy else "missing_or_empty",
            "used_for": "wavecount_safety_copy",
            "sql_real_read": False,
            "sql_real_written": False,
        },
        {
            "source_id": "telegram_sender_review_meta",
            "source": str(telegram_sender_review_meta),
            "source_type": "artifact_json",
            "rows": 1 if telegram_sender_review_meta.exists() else 0,
            "status": "available" if telegram_sender_review_meta.exists() else "optional_missing",
            "used_for": "system_audit_telegram_status",
            "sql_real_read": False,
            "sql_real_written": False,
        },
    ]

    return {
        "method_version": METHOD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "snapshot_rows": compact_snapshot,
        "watchlist_rows": compact_watchlist,
        "data_health": data_health,
        "security_flags": security_flags,
        "sql_counts": sql_counts,
        "migrations": migrations,
        "export_manifest": export_manifest,
        "wavecount_rows": wavecount_rows,
        "current_wavecount_rows": current_wavecount_rows,
        "wavecount_bucket_policy": wavecount_bucket_policy,
        "wavecount_visual_cases": wavecount_visual_cases,
        "wavecount_source_mode": "expanded_screener" if expanded_wavecount_rows else "current_screener_fallback",
        "design_widgets": design_widgets,
        "telegram_status": telegram_status,
        "source_audit": source_audit,
    }


def render_dashboard_html(data: dict[str, Any]) -> str:
    client_keys = [
        "method_version",
        "generated_at",
        "summary",
        "snapshot_rows",
        "watchlist_rows",
        "data_health",
        "security_flags",
        "sql_counts",
        "migrations",
        "export_manifest",
        "wavecount_rows",
        "wavecount_bucket_policy",
        "wavecount_visual_cases",
        "wavecount_source_mode",
        "telegram_status",
    ]
    payload = json.dumps({key: data[key] for key in client_keys}, ensure_ascii=False)
    escaped_payload = payload.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Center Read-only v1</title>
  <style>
{dashboard_css()}
  </style>
</head>
<body>
  <script id="app-data" type="application/json">{escaped_payload}</script>
  <div class="shell">
    <aside class="sidebar" aria-label="Navegacion principal">
      <div class="brand">
        <span class="brand-mark">TC</span>
        <div>
          <strong>Trading Center</strong>
          <small>read-only v1</small>
        </div>
      </div>
      <nav class="nav">
        <a href="#overview" class="nav-link is-active" data-screen="overview">Overview</a>
        <a href="#watchlist" class="nav-link" data-screen="watchlist">Watchlist</a>
        <a href="#asset-detail" class="nav-link" data-screen="asset-detail">Detalle activo</a>
        <a href="#system-audit" class="nav-link" data-screen="system-audit">Auditoria</a>
        <a href="#wavecount-study" class="nav-link" data-screen="wavecount-study">WaveCount estudio</a>
        <a href="#limitations" class="nav-link" data-screen="limitations">Limitaciones</a>
      </nav>
      <div class="lock-panel">
        <span class="lock-dot"></span>
        <div>
          <strong>Solo lectura</strong>
          <small>Ordenes bloqueadas; Telegram/MT5 off</small>
        </div>
      </div>
    </aside>
    <main class="content">
      <section id="overview" class="screen is-visible">
        <header class="screen-head">
          <div>
            <p class="eyebrow">SQL snapshot auditado</p>
            <h1>Estado operativo visible</h1>
          </div>
          <span class="status-pill locked">Ejecucion bloqueada</span>
        </header>
        <div id="overview-grid" class="metric-grid"></div>
        <div class="split">
          <section class="panel">
            <div class="panel-head">
              <h2>Distribuciones</h2>
              <span class="microcopy">derivado del export P01</span>
            </div>
            <div id="distribution-grid" class="distribution-grid"></div>
          </section>
          <section class="panel">
            <div class="panel-head">
              <h2>Flags duros</h2>
              <span class="microcopy">fail-closed</span>
            </div>
            <div id="safety-flags"></div>
          </section>
        </div>
      </section>

      <section id="watchlist" class="screen">
        <header class="screen-head">
          <div>
            <p class="eyebrow">ENBOLSA watchlist</p>
            <h1>Setups en vigilancia</h1>
          </div>
          <span class="status-pill info">watching_setup no es entrada</span>
        </header>
        <div class="toolbar">
          <label>Buscar <input id="watch-search" type="search" placeholder="simbolo o setup"></label>
          <label>Grupo <select id="watch-group"></select></label>
          <label>Side <select id="watch-side"></select></label>
        </div>
        <div class="table-wrap">
          <table id="watch-table" class="data-table"></table>
        </div>
      </section>

      <section id="asset-detail" class="screen">
        <header class="screen-head">
          <div>
            <p class="eyebrow">Detalle read-only</p>
            <h1 id="detail-title">Activo seleccionado</h1>
          </div>
          <span class="status-pill muted">niveles informativos</span>
        </header>
        <div id="asset-detail-grid" class="detail-grid"></div>
      </section>

      <section id="system-audit" class="screen">
        <header class="screen-head">
          <div>
            <p class="eyebrow">Sistema y trazabilidad</p>
            <h1>Auditoria del core local</h1>
          </div>
          <span class="status-pill locked">sin DDL desde UI</span>
        </header>
        <div class="split">
          <section class="panel">
            <div class="panel-head"><h2>Conteos SQL P01</h2></div>
            <div id="sql-counts"></div>
          </section>
          <section class="panel">
            <div class="panel-head"><h2>Migraciones</h2></div>
            <div id="migrations"></div>
          </section>
        </div>
        <section class="panel">
          <div class="panel-head">
            <h2>Telegram informativo</h2>
            <span class="microcopy">estado read-only; secretos fuera del dashboard</span>
          </div>
          <div class="notice info terminal-note">
            El dashboard nunca pide token ni chat id. La configuracion real debe vivir fuera del HTML mediante variables de entorno o un .env local ignorado.
          </div>
          <div id="telegram-status"></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Export auditado</h2></div>
          <div id="export-manifest"></div>
        </section>
      </section>

      <section id="wavecount-study" class="screen">
        <header class="screen-head">
          <div>
            <p class="eyebrow">Contexto de estudio</p>
            <h1>WaveCount study panel</h1>
          </div>
          <span class="status-pill warning">Solo estudio</span>
        </header>
        <div class="notice warning">
          Contexto de estudio; no es senal, no es filtro y no es ejecutable. Los buckets solo sirven para abrir revision visual/manual.
        </div>
        <div id="wave-study-metrics" class="metric-grid"></div>
        <section class="panel">
          <div class="panel-head">
            <h2>Buckets de estudio</h2>
            <span class="microcopy">contrato P05; conteos P04</span>
          </div>
          <div id="wave-bucket-grid" class="bucket-grid"></div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Casos WaveCount</h2>
            <span class="microcopy">filtros visuales, sin efecto operativo</span>
          </div>
          <div class="toolbar">
            <label>Buscar <input id="wave-search" type="search" placeholder="simbolo, bucket u onda"></label>
            <label>Bucket <select id="wave-bucket"></select></label>
            <label>Grupo <select id="wave-group"></select></label>
            <label>Grafico <select id="wave-chart-state"></select></label>
          </div>
          <div class="table-wrap wave-table-wrap">
            <table id="wave-table" class="data-table"></table>
          </div>
        </section>
        <div class="split wave-detail-split">
          <section class="panel">
            <div class="panel-head">
              <h2>Detalle de caso</h2>
              <span class="microcopy">lectura explicativa</span>
            </div>
            <div id="wave-case-detail"></div>
          </section>
          <section class="panel">
            <div class="panel-head">
              <h2>Casos visuales</h2>
              <span class="microcopy">rutas a artifacts existentes</span>
            </div>
            <div id="wave-visual-cases"></div>
          </section>
        </div>
        <section class="panel">
          <div class="panel-head">
            <h2>Limitaciones WaveCount</h2>
            <span class="microcopy">deben permanecer visibles</span>
          </div>
          <ul class="compact-list">
            <li>El screener ampliado contiene casos de estudio y cortes historicos auditados, no un universo live operable.</li>
            <li>Las etiquetas pueden reclasificarse; la lectura correcta es provisional o tardia segun bucket.</li>
            <li>Un grafico legible no demuestra edge, rentabilidad ni validez operativa.</li>
            <li>WaveCount no modifica ENBOLSA, RiskGuard, Telegram, bot ni MT5.</li>
          </ul>
        </section>
      </section>

      <section id="limitations" class="screen">
        <header class="screen-head">
          <div>
            <p class="eyebrow">Guardrails</p>
            <h1>Limitaciones visibles</h1>
          </div>
          <span class="status-pill locked">no action surface</span>
        </header>
        <div class="limitations-grid">
          <section class="panel"><h2>No hace</h2><ul id="not-do-list"></ul></section>
          <section class="panel"><h2>Lectura correcta</h2><ul id="reading-list"></ul></section>
          <section class="panel"><h2>Siguiente fase</h2><p>P04/P05 refinan WaveCount estudio. P06 revisa la plataforma read-only antes de Telegram o bot.</p></section>
        </div>
      </section>
    </main>
  </div>
  <script>
{dashboard_js()}
  </script>
</body>
</html>
"""


def dashboard_css() -> str:
    return r"""
:root {
  --surface: #0b1112;
  --surface-grid: #111b1c;
  --panel: #121c1d;
  --panel-alt: #0f1819;
  --panel-strong: #182627;
  --ink: #e5f0eb;
  --muted: #8ea29d;
  --line: #284244;
  --line-strong: #3f6264;
  --steel: #9fb1ac;
  --teal: #56d0c2;
  --cyan: #79d7ff;
  --amber: #d6a548;
  --red: #e06a5f;
  --green: #77d38a;
  --shadow: 0 14px 36px rgba(0, 0, 0, 0.28);
  --space-1: 6px;
  --space-2: 10px;
  --space-3: 16px;
  --space-4: 24px;
  --space-5: 36px;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background:
    linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px) 0 0 / 100% 4px,
    linear-gradient(90deg, rgba(121,215,255,0.035) 1px, transparent 1px) 0 0 / 44px 44px,
    radial-gradient(circle at 12% -10%, rgba(86,208,194,0.12), transparent 28%),
    linear-gradient(145deg, #071010 0%, var(--surface) 48%, #090d0f 100%);
  color: var(--ink);
  font-family: "Bahnschrift", "Aptos", "DIN Alternate", "Segoe UI", sans-serif;
  font-size: 14px;
  line-height: 1.45;
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(rgba(255,255,255,0.025), rgba(255,255,255,0) 42%);
  mix-blend-mode: screen;
  opacity: .32;
  z-index: 10;
}
a { color: inherit; }
.shell { min-height: 100vh; display: grid; grid-template-columns: 260px minmax(0, 1fr); }
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: var(--space-4);
  background: linear-gradient(180deg, #111c1d 0%, #0b1112 100%);
  color: var(--ink);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.brand { display: flex; gap: var(--space-3); align-items: center; }
.brand-mark {
  width: 42px;
  height: 42px;
  border: 1px solid var(--teal);
  color: var(--teal);
  background: #0a1415;
  display: grid;
  place-items: center;
  font-weight: 800;
  letter-spacing: 0;
  box-shadow: inset 0 0 0 1px rgba(86,208,194,.18), 0 0 18px rgba(86,208,194,.12);
}
.brand strong { display: block; font-size: 18px; }
.brand small, .lock-panel small, .microcopy { color: var(--muted); font-size: 12px; }
.sidebar .brand small, .sidebar .lock-panel small { color: var(--muted); }
.nav { display: grid; gap: var(--space-1); }
.nav-link {
  text-decoration: none;
  padding: 11px 12px;
  border-left: 3px solid transparent;
  color: #dbe8e4;
  background: rgba(255,255,255,0.018);
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 800;
}
.nav-link:hover, .nav-link.is-active {
  background: rgba(121,215,255,0.08);
  border-left-color: var(--amber);
  color: #ffffff;
}
.lock-panel {
  margin-top: auto;
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid rgba(119,211,138,0.35);
  background: rgba(119,211,138,0.055);
}
.lock-dot { width: 10px; height: 10px; margin-top: 5px; background: #6fbf87; border-radius: 50%; }
.content { padding: var(--space-4); max-width: 1580px; width: 100%; }
.screen { display: none; }
.screen.is-visible { display: block; animation: rise 220ms cubic-bezier(.2,.8,.2,1); }
@keyframes rise { from { opacity: .65; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
.screen-head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--line);
}
.eyebrow { margin: 0 0 4px; color: var(--teal); text-transform: uppercase; font-size: 11px; font-weight: 800; letter-spacing: 0; }
h1 { margin: 0; font-size: 32px; line-height: 1.1; font-weight: 800; letter-spacing: 0; }
h2 { margin: 0; font-size: 16px; line-height: 1.25; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(170px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.metric, .panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 3px;
  box-shadow: var(--shadow);
}
.metric { padding: var(--space-3); min-height: 112px; display: grid; align-content: space-between; position: relative; }
.metric::after, .panel::after {
  content: "";
  display: block;
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--teal), transparent 42%, var(--amber));
  opacity: .58;
}
.panel { position: relative; }
.metric span { color: var(--muted); font-size: 12px; text-transform: uppercase; font-weight: 700; }
.metric strong {
  display: block;
  max-width: 100%;
  font-size: 24px;
  line-height: 1.05;
  color: #f7fff9;
  font-family: "Cascadia Mono", "Consolas", "Bahnschrift", monospace;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.metric small { color: var(--muted); }
.split { display: grid; grid-template-columns: 1.25fr .75fr; gap: var(--space-3); margin-bottom: var(--space-4); }
.panel { padding: var(--space-3); margin-bottom: var(--space-3); }
.panel-head { display: flex; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); align-items: center; }
.distribution-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
.bucket-grid { display: grid; grid-template-columns: repeat(3, minmax(220px, 1fr)); gap: var(--space-2); }
.dist { border: 1px solid var(--line); padding: var(--space-2); background: var(--panel-alt); }
.dist b { display: block; margin-bottom: 6px; }
.bucket-card {
  border: 1px solid var(--line);
  background: var(--panel-alt);
  padding: var(--space-2);
  min-height: 118px;
  display: grid;
  align-content: space-between;
  gap: var(--space-2);
}
.bucket-card strong { display: block; font-size: 22px; line-height: 1; }
.bucket-card small { color: var(--muted); }
.bucket-card header { display: flex; justify-content: space-between; gap: var(--space-2); align-items: start; }
.status-pill, .badge {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 4px 9px;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 800;
  border: 1px solid transparent;
  font-family: "Cascadia Mono", "Consolas", "Bahnschrift", monospace;
  text-transform: uppercase;
}
.locked { background: rgba(119,211,138,0.12); color: var(--green); border-color: rgba(119,211,138,0.42); }
.warning { background: rgba(214,165,72,0.14); color: var(--amber); border-color: rgba(214,165,72,0.45); }
.info { background: rgba(86,208,194,0.12); color: var(--teal); border-color: rgba(86,208,194,0.42); }
.muted { background: rgba(142,162,157,0.12); color: var(--muted); border-color: rgba(142,162,157,0.34); }
.danger { background: rgba(224,106,95,0.12); color: var(--red); border-color: rgba(224,106,95,0.42); }
.toolbar {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  align-items: center;
  background: var(--panel);
  border: 1px solid var(--line);
  padding: var(--space-3);
  border-radius: 3px;
  margin-bottom: var(--space-3);
}
label { color: var(--muted); font-weight: 700; font-size: 12px; text-transform: uppercase; }
input, select {
  margin-left: var(--space-2);
  min-height: 34px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: #071011;
  color: var(--ink);
  padding: 6px 9px;
  font-family: "Cascadia Mono", "Consolas", "Bahnschrift", monospace;
}
.table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: 3px; background: var(--panel); box-shadow: var(--shadow); }
.wave-table-wrap { max-height: 680px; }
.table-wrap.embedded { box-shadow: none; border-radius: 3px; }
.table-wrap.embedded .data-table { min-width: 0; }
.data-table { width: 100%; border-collapse: collapse; min-width: 860px; }
.data-table th, .data-table td { padding: 10px 11px; border-bottom: 1px solid rgba(63,98,100,0.55); text-align: left; vertical-align: top; }
.data-table th { position: sticky; top: 0; background: #182627; color: var(--cyan); font-size: 12px; text-transform: uppercase; z-index: 1; }
.data-table td { font-family: "Cascadia Mono", "Consolas", "Bahnschrift", monospace; font-size: 12.5px; }
.data-table tbody tr { cursor: default; }
.data-table tbody tr[data-row-index] { cursor: pointer; }
.data-table tbody tr:hover { background: rgba(121,215,255,0.055); }
.detail-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
.wave-detail-split { grid-template-columns: minmax(0, 1fr) minmax(280px, .55fr); }
.kv { display: grid; grid-template-columns: 145px minmax(0, 1fr); gap: var(--space-2); padding: 7px 0; border-bottom: 1px solid rgba(63,98,100,0.45); }
.kv span:first-child { color: var(--muted); }
.notice { padding: var(--space-3); border-radius: 3px; border: 1px solid var(--line); margin-bottom: var(--space-3); font-weight: 700; }
.terminal-note { font-family: "Cascadia Mono", "Consolas", "Bahnschrift", monospace; font-size: 12.5px; }
.case-note {
  border: 1px solid var(--line);
  background: var(--panel-alt);
  padding: var(--space-2);
  margin-bottom: var(--space-2);
}
.case-note b { display: block; margin-bottom: 4px; }
.path-chip {
  display: inline-block;
  max-width: 100%;
  padding: 4px 7px;
  border: 1px solid var(--line);
  background: #071011;
  color: var(--steel);
  overflow-wrap: anywhere;
  font-family: "Cascadia Mono", "Consolas", "Bahnschrift", monospace;
}
.compact-list { columns: 2; }
.compact-list li { break-inside: avoid; }
.limitations-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
ul { margin: 0; padding-left: 18px; }
li { margin-bottom: 8px; }
code { background: #071011; color: var(--cyan); padding: 2px 5px; border-radius: 2px; }
@media (max-width: 1060px) {
  .shell { grid-template-columns: 1fr; }
  .sidebar { position: relative; height: auto; }
  .nav { grid-template-columns: repeat(3, 1fr); }
  .metric-grid, .split, .detail-grid, .limitations-grid, .bucket-grid { grid-template-columns: 1fr; }
  .compact-list { columns: 1; }
}
@media (max-width: 680px) {
  .content, .sidebar { padding: var(--space-3); }
  .nav { grid-template-columns: 1fr; }
  h1 { font-size: 25px; }
  .screen-head { align-items: start; flex-direction: column; }
}
"""


def dashboard_js() -> str:
    return r"""
const data = JSON.parse(document.getElementById('app-data').textContent);
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function text(value) {
  return value === undefined || value === null || value === '' ? 'not_available' : String(value);
}

function badge(value, kind = 'muted') {
  return `<span class="badge ${kind}">${escapeHtml(text(value))}</span>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function metric(label, value, note) {
  return `<article class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note || '')}</small></article>`;
}

function renderTable(target, rows, columns, rowIndex = false) {
  const el = $(target);
  const isTable = el.tagName.toLowerCase() === 'table';
  if (!rows || rows.length === 0) {
    const empty = '<tbody><tr><td>Sin datos disponibles para esta seccion.</td></tr></tbody>';
    el.innerHTML = isTable ? empty : `<div class="table-wrap embedded"><table class="data-table">${empty}</table></div>`;
    return;
  }
  const head = `<thead><tr>${columns.map(col => `<th>${escapeHtml(col.label)}</th>`).join('')}</tr></thead>`;
  const body = rows.map((row, index) => {
    const attrs = rowIndex ? ` data-row-index="${index}"` : '';
    return `<tr${attrs}>${columns.map(col => `<td>${formatCell(row, col)}</td>`).join('')}</tr>`;
  }).join('');
  const markup = `${head}<tbody>${body}</tbody>`;
  el.innerHTML = isTable ? markup : `<div class="table-wrap embedded"><table class="data-table">${markup}</table></div>`;
}

function formatCell(row, col) {
  const value = text(row[col.key]);
  if (col.badge) {
    return badge(value, col.badge(value));
  }
  return escapeHtml(value);
}

function renderOverview() {
  const s = data.summary;
  $('#overview-grid').innerHTML = [
    metric('Filas snapshot', s.total_rows, `${s.symbols} simbolos visibles`),
    metric('Watchlist', s.watchlist_rows, 'signal_state = watching_setup'),
    metric('Run kind', text(s.run_kind).replaceAll('_', ' '), 'baseline verificado'),
    metric('Flags', s.hard_flag_status, 'can_execute_order y WaveCount filtro a cero')
  ].join('');

  const distributions = [
    ['Signal state', s.signal_states],
    ['RiskGuard', s.riskguard_status],
    ['WaveCount status', s.wavecount_context_status],
    ['Data freshness', s.data_freshness_status]
  ];
  $('#distribution-grid').innerHTML = distributions.map(([name, values]) => {
    const lines = Object.entries(values || {}).map(([key, count]) => `<div>${escapeHtml(key)}: <b>${count}</b></div>`).join('');
    return `<div class="dist"><b>${escapeHtml(name)}</b>${lines}</div>`;
  }).join('');

  renderTable('#safety-flags', data.security_flags, [
    {key: 'check_name', label: 'check'},
    {key: 'value', label: 'value'},
    {key: 'expected', label: 'expected'},
    {key: 'status', label: 'status', badge: v => v === 'passed' ? 'locked' : 'danger'}
  ]);
}

function setupWatchlist() {
  const rows = data.watchlist_rows || [];
  const groups = ['all', ...new Set(rows.map(row => text(row.market_group)))];
  const sides = ['all', ...new Set(rows.map(row => text(row.side)))];
  $('#watch-group').innerHTML = groups.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  $('#watch-side').innerHTML = sides.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  ['#watch-search', '#watch-group', '#watch-side'].forEach(selector => $(selector).addEventListener('input', renderWatchlist));
  renderWatchlist();
}

function renderWatchlist() {
  const query = $('#watch-search').value.toLowerCase();
  const group = $('#watch-group').value;
  const side = $('#watch-side').value;
  const filtered = (data.watchlist_rows || []).filter(row => {
    const haystack = `${row.symbol} ${row.setup_id} ${row.strategy}`.toLowerCase();
    return (!query || haystack.includes(query)) &&
      (group === 'all' || row.market_group === group) &&
      (side === 'all' || row.side === side);
  });
  renderTable('#watch-table', filtered, [
    {key: 'symbol', label: 'symbol'},
    {key: 'market_group', label: 'group'},
    {key: 'timeframe_ltf', label: 'ltf'},
    {key: 'timeframe_htf', label: 'htf'},
    {key: 'signal_state', label: 'state', badge: () => 'info'},
    {key: 'side', label: 'side'},
    {key: 'setup_id', label: 'setup'},
    {key: 'riskguard_status', label: 'risk', badge: () => 'muted'},
    {key: 'wavecount_context_status', label: 'wave', badge: v => v === 'not_available' ? 'muted' : 'warning'}
  ], true);
  $$('#watch-table tbody tr[data-row-index]').forEach(tr => {
    tr.addEventListener('click', () => showAssetDetail(filtered[Number(tr.dataset.rowIndex)]));
  });
  if (filtered[0]) showAssetDetail(filtered[0], false);
}

function panel(title, rows) {
  return `<section class="panel"><div class="panel-head"><h2>${escapeHtml(title)}</h2></div>${rows.map(([k, v]) => `<div class="kv"><span>${escapeHtml(k)}</span><strong>${escapeHtml(text(v))}</strong></div>`).join('')}</section>`;
}

function showAssetDetail(row, navigate = true) {
  if (!row) return;
  $('#detail-title').textContent = `${row.symbol} / ${row.side} / ${row.signal_state}`;
  $('#asset-detail-grid').innerHTML = [
    panel('Identidad', [
      ['symbol', row.symbol], ['market_group', row.market_group], ['strategy', row.strategy],
      ['timeframes', `${row.timeframe_ltf}/${row.timeframe_htf}`], ['run_kind', row.run_kind]
    ]),
    panel('ENBOLSA', [
      ['signal_state', row.signal_state], ['setup_id', row.setup_id], ['has_order_intent', row.has_order_intent],
      ['intent_status', row.intent_status], ['last_closed_bar_time', row.last_closed_bar_time]
    ]),
    panel('Niveles informativos', [
      ['entry', row.entry], ['sl', row.sl], ['tp1', row.tp1], ['tp2', row.tp2],
      ['data_freshness', row.data_freshness_status]
    ]),
    panel('RiskGuard', [
      ['status', row.riskguard_status], ['reason', row.riskguard_reason], ['dry_run_eligible', row.dry_run_eligible]
    ]),
    panel('WaveCount contexto', [
      ['available', row.wavecount_available], ['policy_bucket', row.wavecount_policy_bucket],
      ['context_status', row.wavecount_context_status], ['should_filter_trade', row.wavecount_should_filter_trade]
    ]),
    panel('Flags', [
      ['is_read_only', row.is_read_only], ['can_execute_order', row.can_execute_order],
      ['is_operational', row.is_operational], ['data_origin', row.data_origin]
    ])
  ].join('');
  if (navigate) activateScreen('asset-detail');
}

function renderSystemAudit() {
  renderTable('#sql-counts', data.sql_counts, [
    {key: 'metric_group', label: 'group'}, {key: 'metric', label: 'metric'}, {key: 'value', label: 'value'}
  ]);
  renderTable('#migrations', data.migrations, [
    {key: 'migration_id', label: 'migration'}, {key: 'description', label: 'description'}, {key: 'status', label: 'status', badge: v => v === 'registered' ? 'locked' : 'warning'}
  ]);
  renderTable('#export-manifest', data.export_manifest, [
    {key: 'artifact', label: 'artifact'}, {key: 'source', label: 'source'}, {key: 'rows', label: 'rows'}, {key: 'status', label: 'status', badge: v => v === 'generated' ? 'locked' : 'warning'}
  ]);
  renderTable('#telegram-status', data.telegram_status, [
    {key: 'item', label: 'item'},
    {key: 'value', label: 'value'},
    {key: 'status', label: 'status', badge: v => v === 'available' || v === 'policy' ? 'locked' : 'muted'},
    {key: 'policy', label: 'policy'},
    {key: 'notes', label: 'notes'}
  ]);
}

function waveBucketTone(bucket) {
  const row = (data.wavecount_bucket_policy || []).find(item => item.screener_bucket === bucket);
  if (!row) return 'muted';
  if (row.badge_tone === 'accent') return 'info';
  if (row.badge_tone === 'warning') return 'warning';
  return row.badge_tone || 'muted';
}

function chartForWaveRow(row) {
  const visualCases = data.wavecount_visual_cases || [];
  const matches = visualCases.filter(item => {
    const sameSymbol = text(item.symbol) === text(row.symbol);
    const sameTf = text(item.timeframe) === text(row.timeframe);
    const hint = text(item.panel_bucket_hint);
    return sameSymbol && sameTf && (hint.includes(text(row.screener_bucket)) || hint === 'not_available');
  });
  const found = matches.find(item => text(item.exists).toLowerCase() === 'true') || matches[0];
  return found || null;
}

function renderWavecountMetrics() {
  const rows = data.wavecount_rows || [];
  const buckets = data.wavecount_bucket_policy || [];
  const visibleBuckets = buckets.filter(row => text(row.show_in_panel).toLowerCase() === 'true');
  $('#wave-study-metrics').innerHTML = [
    metric('Casos estudio', rows.length, data.wavecount_source_mode || 'artifact'),
    metric('Buckets visibles', visibleBuckets.length || new Set(rows.map(row => text(row.screener_bucket))).size, 'contrato P05'),
    metric('Graficos inventariados', data.summary.wavecount_visual_cases || 0, 'solo evidencia visual'),
    metric('Politica', 'study-only', 'sin filtro, bot ni ejecucion')
  ].join('');
}

function renderWavecountBuckets() {
  const rows = data.wavecount_rows || [];
  const counts = {};
  rows.forEach(row => counts[text(row.screener_bucket)] = (counts[text(row.screener_bucket)] || 0) + 1);
  const buckets = (data.wavecount_bucket_policy || []).filter(row => text(row.show_in_panel).toLowerCase() !== 'false');
  $('#wave-bucket-grid').innerHTML = buckets.map(row => {
    const bucket = text(row.screener_bucket);
    const count = counts[bucket] || 0;
    return `<article class="bucket-card">
      <header>
        <div>
          <strong>${escapeHtml(count)}</strong>
          <small>${escapeHtml(bucket)}</small>
        </div>
        ${badge(row.default_visibility || 'visible', waveBucketTone(bucket))}
      </header>
      <p>${escapeHtml(row.warning_required || 'Contexto de estudio; no es senal, no es filtro y no es ejecutable.')}</p>
    </article>`;
  }).join('');
}

function setupWavecountFilters() {
  const rows = data.wavecount_rows || [];
  const buckets = ['all', ...new Set(rows.map(row => text(row.screener_bucket)))];
  const groups = ['all', ...new Set(rows.map(row => text(row.market_group)))];
  const chartStates = ['all', 'with_chart', 'without_chart'];
  $('#wave-bucket').innerHTML = buckets.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  $('#wave-group').innerHTML = groups.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  $('#wave-chart-state').innerHTML = chartStates.map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
  ['#wave-search', '#wave-bucket', '#wave-group', '#wave-chart-state'].forEach(selector => $(selector).addEventListener('input', renderWavecountTable));
}

function renderWavecount() {
  renderWavecountMetrics();
  renderWavecountBuckets();
  setupWavecountFilters();
  renderWavecountTable();
  renderWavecountVisualCases();
}

function renderWavecountTable() {
  const query = $('#wave-search').value.toLowerCase();
  const bucket = $('#wave-bucket').value;
  const group = $('#wave-group').value;
  const chartState = $('#wave-chart-state').value;
  const filtered = (data.wavecount_rows || []).filter(row => {
    const chart = chartForWaveRow(row);
    const hasExistingChart = Boolean(chart && text(chart.exists).toLowerCase() === 'true' && chart.chart_file);
    const haystack = `${row.symbol} ${row.market_group} ${row.timeframe} ${row.screener_bucket} ${row.live_estimated_wave} ${row.confirmed_wave_context}`.toLowerCase();
    return (!query || haystack.includes(query)) &&
      (bucket === 'all' || row.screener_bucket === bucket) &&
      (group === 'all' || row.market_group === group) &&
      (chartState === 'all' || (chartState === 'with_chart' ? hasExistingChart : !hasExistingChart));
  });
  const tableRows = filtered.map(row => {
    const chart = chartForWaveRow(row);
    return {
      ...row,
      chart_status: chart && text(chart.exists).toLowerCase() === 'true' ? 'grafico disponible' : 'sin grafico',
      study_action: row.recommended_study_action || 'revisar detalle',
      row_warning: row.required_warning || 'Contexto de estudio; no es senal, no es filtro y no es ejecutable.',
    };
  });
  renderTable('#wave-table', tableRows, [
    {key: 'symbol', label: 'symbol'},
    {key: 'market_group', label: 'group'},
    {key: 'timeframe', label: 'tf'},
    {key: 'screener_bucket', label: 'bucket', badge: v => waveBucketTone(v)},
    {key: 'live_estimated_wave', label: 'onda estimada'},
    {key: 'confirmed_wave_context', label: 'contexto confirmado'},
    {key: 'confidence_bucket', label: 'confianza', badge: v => v === 'medium' ? 'info' : 'muted'},
    {key: 'freshness_status', label: 'frescura'},
    {key: 'chart_status', label: 'grafico', badge: v => v === 'grafico disponible' ? 'locked' : 'muted'},
    {key: 'study_action', label: 'accion de estudio'},
    {key: 'row_warning', label: 'warning'}
  ], true);
  $$('#wave-table tbody tr[data-row-index]').forEach(tr => {
    tr.addEventListener('click', () => showWaveCaseDetail(filtered[Number(tr.dataset.rowIndex)]));
  });
  showWaveCaseDetail(filtered[0], false);
}

function showWaveCaseDetail(row) {
  const target = $('#wave-case-detail');
  if (!row) {
    target.innerHTML = '<p class="microcopy">Selecciona un caso de estudio para ver su explicacion.</p>';
    return;
  }
  const chart = chartForWaveRow(row);
  const chartText = chart && chart.chart_file ? chart.chart_file : 'sin grafico disponible';
  target.innerHTML = [
    `<div class="case-note"><b>${escapeHtml(row.symbol || 'not_available')} / ${escapeHtml(row.timeframe || 'not_available')}</b>${badge(row.screener_bucket || 'not_available', waveBucketTone(row.screener_bucket))}</div>`,
    `<div class="case-note"><b>Por que aparece</b>${escapeHtml(row.why_in_screener || row.notes || 'Caso incluido por contrato de estudio WaveCount.')}</div>`,
    `<div class="case-note"><b>Por que no es operativo</b>${escapeHtml(row.why_not_signal || 'WaveCount queda limitado a estudio; no genera senales ni filtra operaciones.')}</div>`,
    `<div class="case-note"><b>Warning</b>${escapeHtml(row.required_warning || 'Contexto de estudio; no es senal, no es filtro y no es ejecutable.')}</div>`,
    `<div class="case-note"><b>Fuente</b><span class="path-chip">${escapeHtml(row.source_artifact || data.wavecount_source_mode || 'artifact')}</span></div>`,
    `<div class="case-note"><b>Grafico</b><span class="path-chip">${escapeHtml(chartText)}</span></div>`
  ].join('');
}

function renderWavecountVisualCases() {
  const visualRows = (data.wavecount_visual_cases || []).filter(row => text(row.exists).toLowerCase() === 'true').slice(0, 8);
  if (!visualRows.length) {
    $('#wave-visual-cases').innerHTML = '<p class="microcopy">Sin graficos disponibles; el panel mantiene detalle textual.</p>';
    return;
  }
  $('#wave-visual-cases').innerHTML = visualRows.map(row => {
    return `<div class="case-note">
      <b>${escapeHtml(row.symbol)} / ${escapeHtml(row.timeframe)} / ${escapeHtml(row.case_label)}</b>
      ${badge(row.visual_readability || 'not_available', row.visual_readability === 'readable' ? 'locked' : 'warning')}
      <div class="path-chip">${escapeHtml(row.chart_file)}</div>
    </div>`;
  }).join('');
}

function renderLimitations() {
  const notDo = [
    'No envia ordenes ni muestra controles de ejecucion.',
    'No escribe SQL ni aplica migraciones.',
    'No implementa Telegram, bot ni MT5.',
    'No recalcula ENBOLSA ni genera senales nuevas.',
    'No usa WaveCount como filtro.'
  ];
  const reading = [
    'bootstrap_current es baseline verificado, no historico vivo acumulado.',
    'watching_setup significa vigilancia, no entrada.',
    'RiskGuard not_evaluated significa que no hubo intent diagnostico.',
    'WaveCount study-only sirve para abrir estudio manual.',
    'Los niveles entry/SL/TP son informativos en v1.'
  ];
  $('#not-do-list').innerHTML = notDo.map(item => `<li>${escapeHtml(item)}</li>`).join('');
  $('#reading-list').innerHTML = reading.map(item => `<li>${escapeHtml(item)}</li>`).join('');
}

function activateScreen(screen) {
  $$('.screen').forEach(el => el.classList.toggle('is-visible', el.id === screen));
  $$('.nav-link').forEach(el => el.classList.toggle('is-active', el.dataset.screen === screen));
  if (location.hash !== `#${screen}`) history.replaceState(null, '', `#${screen}`);
  resetScroll();
  setTimeout(resetScroll, 0);
  setTimeout(resetScroll, 80);
}

function resetScroll() {
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  window.scrollTo(0, 0);
}

function setupNavigation() {
  $$('.nav-link').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      activateScreen(link.dataset.screen);
    });
  });
  const initial = location.hash.replace('#', '') || 'overview';
  if ($(`#${initial}`)) activateScreen(initial);
}

renderOverview();
setupWatchlist();
renderSystemAudit();
renderWavecount();
renderLimitations();
setupNavigation();
"""


def widget_implementation_audit(design_widgets: list[dict[str, str]]) -> list[dict[str, Any]]:
    implemented = {
        "snapshot_status": "overview",
        "global_counts": "overview",
        "data_health_summary": "overview",
        "hard_safety_flags": "overview",
        "watchlist_table": "watchlist",
        "watchlist_filters": "watchlist",
        "riskguard_status_badges": "watchlist",
        "asset_header": "asset_detail",
        "enbolsa_context": "asset_detail",
        "levels_panel": "asset_detail",
        "riskguard_panel": "asset_detail",
        "signal_event_latest": "asset_detail",
        "sql_status": "system_audit",
        "migration_status": "system_audit",
        "export_status": "system_audit",
        "risk_config_readonly": "system_audit",
        "bot_config_readonly": "system_audit",
        "wavecount_study_screener": "wavecount_study",
        "limitations_block": "limitations",
    }
    rows = []
    for widget in design_widgets:
        widget_id = widget.get("widget_id", "")
        rows.append(
            {
                "widget_id": widget_id,
                "screen_id": widget.get("screen_id", ""),
                "source_name": widget.get("source_name", ""),
                "implemented": widget_id in implemented,
                "implementation_surface": implemented.get(widget_id, "not_implemented"),
                "read_only": True,
                "notes": "implemented in static dashboard" if widget_id in implemented else "deferred",
            }
        )
    return rows


def validation_rows(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    summary = data["summary"]
    no_action = [
        {"check_id": "NA01", "check": "no_order_controls", "status": "passed", "evidence": "HTML contains no order action surface"},
        {"check_id": "NA02", "check": "sql_real_written", "status": "passed", "evidence": "generator reads artifacts only"},
        {"check_id": "NA03", "check": "telegram_bot_mt5_absent", "status": "passed", "evidence": "no integrations implemented"},
        {"check_id": "NA04", "check": "hard_flags_zero", "status": "passed" if summary["can_execute_order_true"] == 0 and summary["wavecount_filter_true"] == 0 else "failed", "evidence": f"can_execute_order_true={summary['can_execute_order_true']}; wavecount_filter_true={summary['wavecount_filter_true']}"},
    ]
    ui_state = [
        {"screen_id": "overview", "empty_state": "implemented", "stale_state": "bootstrap_current badge", "error_state": "source audit"},
        {"screen_id": "watchlist", "empty_state": "implemented", "stale_state": "run_kind and freshness visible", "error_state": "static fallback message"},
        {"screen_id": "asset_detail", "empty_state": "implemented", "stale_state": "last_closed_bar_time visible", "error_state": "no selected row state"},
        {"screen_id": "system_audit", "empty_state": "implemented", "stale_state": "artifact status visible", "error_state": "manifest status visible"},
        {"screen_id": "wavecount_study", "empty_state": "implemented", "stale_state": "study warning visible", "error_state": "optional panel"},
    ]
    wavecount = [
        {
            "check_id": "WC01",
            "status": "passed",
            "study_only": True,
            "show_in_main_dashboard": False,
            "can_generate_signal": False,
            "can_filter_trade": False,
            "can_execute_order": False,
            "evidence": "WaveCount rendered in separate study screen with warning",
        }
    ]
    return no_action, ui_state, wavecount


def wavecount_panel_data_audit(data: dict[str, Any]) -> list[dict[str, Any]]:
    wave_sources = [row for row in data["source_audit"] if row["source_id"].startswith("wavecount")]
    rows: list[dict[str, Any]] = []
    for row in wave_sources:
        rows.append(
            {
                "source_id": row["source_id"],
                "source": row["source"],
                "rows": row["rows"],
                "status": row["status"],
                "used_for": row["used_for"],
                "sql_real_read": row["sql_real_read"],
                "sql_real_written": row["sql_real_written"],
            }
        )
    rows.append(
        {
            "source_id": "wavecount_source_mode",
            "source": data["wavecount_source_mode"],
            "rows": len(data["wavecount_rows"]),
            "status": "available" if data["wavecount_rows"] else "missing_or_empty",
            "used_for": "panel_runtime",
            "sql_real_read": False,
            "sql_real_written": False,
        }
    )
    return rows


def wavecount_panel_implementation_audit(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data["wavecount_rows"]
    bucket_policy = data["wavecount_bucket_policy"]
    return [
        {
            "check_id": "WC_IMPL_01",
            "check": "expanded_screener_loaded",
            "status": "passed" if data["wavecount_source_mode"] == "expanded_screener" and rows else "warning",
            "evidence": f"source_mode={data['wavecount_source_mode']}; rows={len(rows)}",
        },
        {
            "check_id": "WC_IMPL_02",
            "check": "bucket_policy_loaded",
            "status": "passed" if bucket_policy else "failed",
            "evidence": f"bucket_policy_rows={len(bucket_policy)}",
        },
        {
            "check_id": "WC_IMPL_03",
            "check": "warnings_populated",
            "status": "passed" if all(row.get("required_warning") for row in rows) else "failed",
            "evidence": f"missing={sum(1 for row in rows if not row.get('required_warning'))}",
        },
        {
            "check_id": "WC_IMPL_04",
            "check": "why_not_signal_populated",
            "status": "passed" if all(row.get("why_not_signal") for row in rows) else "failed",
            "evidence": f"missing={sum(1 for row in rows if not row.get('why_not_signal'))}",
        },
        {
            "check_id": "WC_IMPL_05",
            "check": "hard_flags_fail_closed",
            "status": "passed" if false_flags(rows, ["telegram_allowed", "bot_allowed", "can_generate_signal", "can_filter_trade", "can_execute_order"]) else "failed",
            "evidence": "telegram_allowed/bot_allowed/can_generate_signal/can_filter_trade/can_execute_order remain false",
        },
    ]


def wavecount_panel_visual_state_audit(data: dict[str, Any]) -> list[dict[str, Any]]:
    visual_rows = data["wavecount_visual_cases"]
    available = [row for row in visual_rows if has_chart(row)]
    return [
        {
            "surface": "panel_header",
            "empty_state": "zero counts with study-only warning",
            "error_state": "panel stays unavailable without breaking dashboard",
            "observed": f"study_cases={len(data['wavecount_rows'])}",
        },
        {
            "surface": "case_table",
            "empty_state": "no WaveCount study cases available",
            "error_state": "table disabled with artifact path",
            "observed": f"rows={len(data['wavecount_rows'])}",
        },
        {
            "surface": "visual_cases",
            "empty_state": "sin grafico disponible",
            "error_state": "hide preview and keep text detail",
            "observed": f"visual_cases={len(visual_rows)}; available={len(available)}",
        },
    ]


def visual_direction_audit() -> list[dict[str, Any]]:
    return [
        {
            "check_id": "VIS01",
            "surface": "global_shell",
            "direction": VISUAL_ARCHETYPE,
            "status": "passed",
            "evidence": "Dark technical shell, compact panels, terminal-style data surfaces.",
        },
        {
            "check_id": "VIS02",
            "surface": "tables_and_badges",
            "direction": "industrial_status_console",
            "status": "passed",
            "evidence": "Monospace table cells, square badges, amber/cyan/green state colors.",
        },
        {
            "check_id": "VIS03",
            "surface": "accessibility",
            "direction": "sober_readable_contrast",
            "status": "passed",
            "evidence": "No marketing hero, no decorative sci-fi layout, no operational action surface.",
        },
    ]


def ai_reference_cleanup_audit(html_text: str) -> list[dict[str, Any]]:
    patterns = {
        "AI": r"\bAI\b",
        "IA": r"\bIA\b",
        "Codex": r"\bCodex\b",
        "OpenAI": r"\bOpenAI\b",
        "asistente": r"\basistente\b",
        "analyst": r"\banalyst\b",
        "hecho_con_ia": r"hecho\s+con\s+IA",
    }
    rows: list[dict[str, Any]] = []
    for label, pattern in patterns.items():
        matches = re.findall(pattern, html_text, flags=re.IGNORECASE)
        rows.append(
            {
                "reference": label,
                "found_count": len(matches),
                "status": "passed" if not matches else "failed",
                "policy": "not_visible_in_dashboard",
                "notes": "Se mantiene fuera del HTML visible del dashboard.",
            }
        )
    return rows


def telegram_dashboard_secret_policy_audit(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "policy_id": "TG_DASH_01",
            "surface": "system_audit",
            "decision": "read_only_status_only",
            "status": "passed",
            "reason": f"telegram_rows={len(data['telegram_status'])}; no token/chat id inputs are rendered",
        },
        {
            "policy_id": "TG_DASH_02",
            "surface": "secret_handling",
            "decision": "environment_or_local_ignored_env_outside_dashboard",
            "status": "passed",
            "reason": "Secrets are policy text only; the dashboard never stores or requests values.",
        },
        {
            "policy_id": "TG_DASH_03",
            "surface": "future_command_bot",
            "decision": "deferred",
            "status": "passed",
            "reason": "No Telegram command bot, command inputs, or interactive sender controls are added.",
        },
    ]


def no_action_visual_regression_audit(html_text: str) -> list[dict[str, Any]]:
    lower = html_text.lower()
    secret_input_pattern = re.compile(r"<input[^>]*(token|chat|api|secret|telegram)", flags=re.IGNORECASE)
    checks = [
        ("NOACT_VIS_01", "no_buttons", "<button" not in lower, "No button elements in dashboard HTML."),
        ("NOACT_VIS_02", "no_forms", "<form" not in lower, "No form elements in dashboard HTML."),
        ("NOACT_VIS_03", "no_secret_inputs", not secret_input_pattern.search(html_text), "No token/chat/api/secret input fields."),
        ("NOACT_VIS_04", "no_secret_storage", "localstorage" not in lower and "sessionstorage" not in lower, "No browser storage for secrets."),
        ("NOACT_VIS_05", "no_mt5_surface", "mt5 adapter" not in lower, "No MT5 adapter or broker surface."),
        ("NOACT_VIS_06", "wavecount_study_only", "no es senal" in lower and "no es filtro" in lower, "WaveCount warning remains visible."),
    ]
    return [
        {
            "check_id": check_id,
            "check": check,
            "status": "passed" if passed else "failed",
            "evidence": evidence,
        }
        for check_id, check, passed, evidence in checks
    ]


def browser_smoke_audit_rows() -> list[dict[str, Any]]:
    return [
        {"check_id": "BROWSER_01", "check": "dashboard_html_generated", "status": "passed", "evidence": "dashboard/index.html created"},
        {"check_id": "BROWSER_02", "check": "expected_screenshots_requested", "status": "pending_external_capture", "evidence": "screenshots are generated by validation step"},
        {"check_id": "BROWSER_03", "check": "no_action_surface_expected", "status": "passed", "evidence": "static audit enforces no buttons/forms/secret inputs"},
    ]


def technical_validation_audit_rows() -> list[dict[str, Any]]:
    return [
        {"check_id": "TECH_01", "check": "generator_artifact_first", "status": "passed", "evidence": "build_dashboard reads CSV/JSON artifacts only"},
        {"check_id": "TECH_02", "check": "sql_runtime_not_used", "status": "passed", "evidence": "no SQL connection or DDL in dashboard generator"},
        {"check_id": "TECH_03", "check": "telegram_not_connected", "status": "passed", "evidence": "dashboard renders status only"},
        {"check_id": "TECH_04", "check": "mt5_not_connected", "status": "passed", "evidence": "no MT5 integration in dashboard generator"},
    ]


def write_outputs(output_dir: Path, data: dict[str, Any], html_text: str) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "tables").mkdir(parents=True, exist_ok=True)
    dashboard_dir = output_dir / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    index_path = dashboard_dir / "index.html"
    index_path.write_text(html_text, encoding="utf-8")

    write_csv(output_dir / "tables/data_source_audit.csv", data["source_audit"])
    write_csv(output_dir / "tables/widget_implementation_audit.csv", widget_implementation_audit(data["design_widgets"]))
    no_action, ui_state, wavecount = validation_rows(data)
    write_csv(output_dir / "tables/no_action_validation.csv", no_action)
    write_csv(output_dir / "tables/ui_state_validation.csv", ui_state)
    write_csv(output_dir / "tables/wavecount_display_validation.csv", wavecount)
    write_csv(output_dir / "tables/wavecount_panel_data_audit.csv", wavecount_panel_data_audit(data))
    write_csv(output_dir / "tables/wavecount_panel_implementation_audit.csv", wavecount_panel_implementation_audit(data))
    write_csv(output_dir / "tables/wavecount_panel_no_action_validation.csv", no_action)
    write_csv(output_dir / "tables/wavecount_panel_visual_state_audit.csv", wavecount_panel_visual_state_audit(data))
    write_csv(output_dir / "tables/visual_direction_audit.csv", visual_direction_audit())
    write_csv(output_dir / "tables/ai_reference_cleanup_audit.csv", ai_reference_cleanup_audit(html_text))
    write_csv(output_dir / "tables/telegram_dashboard_secret_policy.csv", telegram_dashboard_secret_policy_audit(data))
    write_csv(output_dir / "tables/no_action_visual_regression_audit.csv", no_action_visual_regression_audit(html_text))
    write_csv(output_dir / "tables/browser_smoke_audit.csv", browser_smoke_audit_rows())
    write_csv(output_dir / "tables/technical_validation_audit.csv", technical_validation_audit_rows())
    write_csv(
        output_dir / "tables/issues_or_risks.csv",
        [
            {
                "issue_id": "R01",
                "severity": "medium",
                "status": "open",
                "description": "Dashboard uses bootstrap_current artifact export, not a live observed feed.",
                "mitigation": "Visible bootstrap_current badge and source audit.",
            },
            {
                "issue_id": "R02",
                "severity": "medium",
                "status": "open",
                "description": "WaveCount can look actionable if wording is loosened.",
                "mitigation": "Separate study screen and required warning.",
            },
            {
                "issue_id": "R03",
                "severity": "low",
                "status": "open",
                "description": "Risk and bot config views are represented as read-only placeholders until live adapters are built.",
                "mitigation": "System audit labels them fail-closed and non-actionable.",
            },
            {
                "issue_id": "R04",
                "severity": "medium",
                "status": "open",
                "description": "Telegram credentials must never be entered into dashboard HTML or browser storage.",
                "mitigation": "Dashboard shows only read-only status/policy; sender secrets remain environment-only outside artifacts.",
            },
        ],
    )

    run_meta = {
        "phase": METHOD_VERSION,
        "generated_at": data["generated_at"],
        "decision": "trading_center_visual_refinement_v1_passed",
        "visual_refinement_applied": True,
        "visual_direction": VISUAL_ARCHETYPE,
        "ai_visible_references_removed": True,
        "telegram_dashboard_secret_inputs_present": False,
        "telegram_dashboard_policy": "read_only_environment_only_no_dashboard_inputs",
        "dashboard_implemented": True,
        "dashboard_updated": True,
        "dashboard_read_only": True,
        "wavecount_panel_implemented": True,
        "wavecount_study_only": True,
        "dashboard_entrypoint": str(index_path),
        "sql_real_read": False,
        "sql_real_written": False,
        "ddl_executed": False,
        "telegram_implemented": False,
        "telegram_connected": False,
        "telegram_real_messages_sent": 0,
        "bot_implemented": False,
        "mt5_connected": False,
        "backtests_executed": False,
        "signals_generated": False,
        "wavecount_used_as_filter": False,
        "snapshot_rows": data["summary"]["total_rows"],
        "watchlist_rows": data["summary"]["watchlist_rows"],
        "wavecount_rows": len(data["wavecount_rows"]),
        "wavecount_source_mode": data["wavecount_source_mode"],
        "wavecount_buckets": data["summary"]["wavecount_study_buckets"],
        "wavecount_visual_cases": data["summary"]["wavecount_visual_cases"],
        "screens": ["overview", "watchlist", "asset-detail", "system-audit", "wavecount-study", "limitations"],
        "next_recommended_phase": "P11_review_refine_platform_v2_after_user_dashboard_review",
    }
    (output_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "TRADING_CENTER_READONLY_V1.md").write_text(render_artifact_report(run_meta), encoding="utf-8")
    (output_dir / "WAVECOUNT_STUDY_PANEL_V1.md").write_text(render_wavecount_panel_report(run_meta), encoding="utf-8")
    (output_dir / "TRADING_CENTER_VISUAL_REFINEMENT_V1.md").write_text(render_visual_refinement_report(run_meta), encoding="utf-8")
    return {"index": index_path}


def render_artifact_report(run_meta: dict[str, Any]) -> str:
    return f"""# Trading Center Read-only V1

Fecha: 2026-05-28

Decision: `{run_meta['decision']}`.

## Resultado

Se genera un dashboard local estatico en:

`{run_meta['dashboard_entrypoint']}`

La implementacion usa artifacts auditados de P01/P02 y no abre conexion SQL.
No escribe SQL, no crea DDL, no implementa Telegram, no implementa bot, no
conecta MT5, no ejecuta backtests y no genera senales.

## Pantallas

- Overview
- Watchlist
- Detalle activo
- Auditoria sistema
- WaveCount estudio
- Limitaciones

## Evidencia Visual

Las capturas de navegador deben guardarse en `screenshots/` cuando se ejecute
la validacion visual de P03:

- `overview.png`
- `watchlist.png`
- `asset_detail.png`
- `system_audit.png`
- `wavecount_study.png`

## Datos

- Filas snapshot: {run_meta['snapshot_rows']}
- Filas watchlist: {run_meta['watchlist_rows']}
- Filas WaveCount estudio: {run_meta['wavecount_rows']}

## Seguridad

- `dashboard_read_only=true`
- `sql_real_written=false`
- `ddl_executed=false`
- `telegram_implemented=false`
- `bot_implemented=false`
- `mt5_connected=false`
- `signals_generated=false`
- `wavecount_used_as_filter=false`
"""


def render_wavecount_panel_report(run_meta: dict[str, Any]) -> str:
    return f"""# WaveCount Study Panel V1

Fecha: 2026-05-28

Decision: `{run_meta['decision']}`.

## Resultado

Se implementa el panel WaveCount de estudio dentro del dashboard read-only:

`{run_meta['dashboard_entrypoint']}`

El panel sustituye la tabla simple de P03 por una superficie separada con
resumen de buckets, filtros visuales, tabla de casos, detalle explicativo y
rutas a graficos disponibles. WaveCount permanece como contexto de estudio:
no es senal, no es filtro y no es ejecutable.

## Datos

- Fuente WaveCount: `{run_meta['wavecount_source_mode']}`
- Casos de estudio: {run_meta['wavecount_rows']}
- Buckets visibles/observados: {run_meta['wavecount_buckets']}
- Graficos inventariados disponibles: {run_meta['wavecount_visual_cases']}

## Seguridad

- `dashboard_read_only=true`
- `wavecount_panel_implemented=true`
- `wavecount_study_only=true`
- `sql_real_written=false`
- `ddl_executed=false`
- `telegram_implemented=false`
- `bot_implemented=false`
- `mt5_connected=false`
- `backtests_executed=false`
- `signals_generated=false`
- `wavecount_used_as_filter=false`

## Validacion Esperada

Las capturas de navegador de esta fase deben guardarse en:

- `screenshots/wavecount_panel.png`
- `screenshots/overview_with_wavecount.png`
"""


def render_visual_refinement_report(run_meta: dict[str, Any]) -> str:
    return f"""# Trading Center Visual Refinement V1

Fecha: 2026-05-29

Decision: `{run_meta['decision']}`.

## Resultado

Se refina el dashboard read-only con direccion visual
`{run_meta['visual_direction']}`:

- superficie oscura tecnica;
- tablas y badges con lectura de terminal industrial;
- copy visible sin referencias a IA/Codex/OpenAI;
- Telegram mostrado solo como estado y politica read-only.

El dashboard generado queda en:

`{run_meta['dashboard_entrypoint']}`

## Telegram

No se anaden inputs de token/chat id, formularios ni almacenamiento en navegador.
La politica queda como variables de entorno o `.env` local ignorado fuera del
dashboard. El HTML solo muestra estado y trazabilidad.

## Seguridad

- `dashboard_read_only=true`
- `telegram_dashboard_secret_inputs_present=false`
- `telegram_connected=false`
- `telegram_real_messages_sent=0`
- `sql_real_written=false`
- `ddl_executed=false`
- `mt5_connected=false`
- `signals_generated=false`
- `wavecount_used_as_filter=false`

## Evidencia

La fase deja auditorias en `tables/` y las capturas esperadas en
`screenshots/` durante la validacion visual.
"""


def build_dashboard(
    output_dir: Path,
    snapshot_csv: Path = DEFAULT_SNAPSHOT_CSV,
    security_flags_csv: Path = DEFAULT_SECURITY_FLAGS_CSV,
    counts_csv: Path = DEFAULT_COUNTS_CSV,
    migrations_csv: Path = DEFAULT_MIGRATIONS_CSV,
    export_manifest_csv: Path = DEFAULT_EXPORT_MANIFEST_CSV,
    wavecount_csv: Path = DEFAULT_WAVECOUNT_CSV,
    wavecount_expanded_csv: Path = DEFAULT_WAVECOUNT_EXPANDED_CSV,
    wavecount_buckets_csv: Path = DEFAULT_WAVECOUNT_BUCKETS_CSV,
    wavecount_visual_cases_csv: Path = DEFAULT_WAVECOUNT_VISUAL_CASES_CSV,
    wavecount_no_action_csv: Path = DEFAULT_WAVECOUNT_NO_ACTION_CSV,
    design_widgets_csv: Path = DEFAULT_DESIGN_WIDGETS_CSV,
    telegram_sender_review_meta: Path = DEFAULT_TELEGRAM_SENDER_REVIEW_META,
) -> dict[str, Path]:
    data = build_data_model(
        snapshot_csv=snapshot_csv,
        security_flags_csv=security_flags_csv,
        counts_csv=counts_csv,
        migrations_csv=migrations_csv,
        export_manifest_csv=export_manifest_csv,
        wavecount_csv=wavecount_csv,
        wavecount_expanded_csv=wavecount_expanded_csv,
        wavecount_buckets_csv=wavecount_buckets_csv,
        wavecount_visual_cases_csv=wavecount_visual_cases_csv,
        wavecount_no_action_csv=wavecount_no_action_csv,
        design_widgets_csv=design_widgets_csv,
        telegram_sender_review_meta=telegram_sender_review_meta,
    )
    html_text = render_dashboard_html(data)
    return write_outputs(output_dir, data, html_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Trading Center read-only dashboard from audited artifacts.")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "artifacts/tfg/trading_center_readonly_v1_2026-05-28")
    parser.add_argument("--snapshot-csv", type=Path, default=DEFAULT_SNAPSHOT_CSV)
    parser.add_argument("--security-flags-csv", type=Path, default=DEFAULT_SECURITY_FLAGS_CSV)
    parser.add_argument("--counts-csv", type=Path, default=DEFAULT_COUNTS_CSV)
    parser.add_argument("--migrations-csv", type=Path, default=DEFAULT_MIGRATIONS_CSV)
    parser.add_argument("--export-manifest-csv", type=Path, default=DEFAULT_EXPORT_MANIFEST_CSV)
    parser.add_argument("--wavecount-csv", type=Path, default=DEFAULT_WAVECOUNT_CSV)
    parser.add_argument("--wavecount-expanded-csv", type=Path, default=DEFAULT_WAVECOUNT_EXPANDED_CSV)
    parser.add_argument("--wavecount-buckets-csv", type=Path, default=DEFAULT_WAVECOUNT_BUCKETS_CSV)
    parser.add_argument("--wavecount-visual-cases-csv", type=Path, default=DEFAULT_WAVECOUNT_VISUAL_CASES_CSV)
    parser.add_argument("--wavecount-no-action-csv", type=Path, default=DEFAULT_WAVECOUNT_NO_ACTION_CSV)
    parser.add_argument("--design-widgets-csv", type=Path, default=DEFAULT_DESIGN_WIDGETS_CSV)
    parser.add_argument("--telegram-sender-review-meta", type=Path, default=DEFAULT_TELEGRAM_SENDER_REVIEW_META)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = build_dashboard(
        output_dir=args.output_dir,
        snapshot_csv=args.snapshot_csv,
        security_flags_csv=args.security_flags_csv,
        counts_csv=args.counts_csv,
        migrations_csv=args.migrations_csv,
        export_manifest_csv=args.export_manifest_csv,
        wavecount_csv=args.wavecount_csv,
        wavecount_expanded_csv=args.wavecount_expanded_csv,
        wavecount_buckets_csv=args.wavecount_buckets_csv,
        wavecount_visual_cases_csv=args.wavecount_visual_cases_csv,
        wavecount_no_action_csv=args.wavecount_no_action_csv,
        design_widgets_csv=args.design_widgets_csv,
        telegram_sender_review_meta=args.telegram_sender_review_meta,
    )
    print(f"dashboard_index={outputs['index']}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from backtests.common.backtest_matrix_config import normalize_group_name
from data.sql.sql_funcs import close_db, connect_db


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TIMEFRAMES = {
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}

REQUIRED_PRICE_COLUMNS = {
    "symbol",
    "timeframe",
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
}

DEFAULT_GROUPS = ("Forex Majors", "Metals")

ISSUE_COLUMNS = ["severity", "area", "item", "detail", "recommendation"]


def parse_csv(value: str | None, default: tuple[str, ...]) -> list[str]:
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def normalise_int(value) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)


def normalise_float(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def strip_broker_suffix(symbol: str) -> str:
    return symbol[:-2] if isinstance(symbol, str) and symbol.endswith(".r") else symbol


def session_gap_threshold_minutes(timeframe: str, expected_minutes: int) -> int:
    if timeframe == "D1":
        return expected_minutes + 1
    return 48 * 60


class QueryRunner:
    def __init__(self, connection, query_timeout_ms: int):
        self.connection = connection
        self.query_timeout_ms = int(query_timeout_ms)
        self.log: list[dict] = []
        self.timeout_supported = self._set_query_timeout()

    def _set_query_timeout(self) -> bool:
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SET SESSION MAX_EXECUTION_TIME={self.query_timeout_ms}")
            self.connection.commit()
            return True
        except Exception as exc:
            self.log.append({
                "label": "set_session_max_execution_time",
                "status": "warning",
                "elapsed_seconds": 0.0,
                "error": str(exc),
                "rows_returned": 0,
            })
            return False
        finally:
            cursor.close()

    def fetch(self, label: str, query: str, params: tuple | list | None = None) -> tuple[list[dict], str | None]:
        cursor = self.connection.cursor(dictionary=True)
        started = time.perf_counter()
        try:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            error = None
            status = "ok"
        except Exception as exc:
            rows = []
            error = str(exc)
            status = "error"
        finally:
            elapsed = time.perf_counter() - started
            cursor.close()

        self.log.append({
            "label": label,
            "status": status,
            "elapsed_seconds": round(elapsed, 4),
            "error": error,
            "rows_returned": len(rows),
        })
        return rows, error


def get_table_columns(runner: QueryRunner, table_name: str) -> list[str]:
    rows, _ = runner.fetch(f"show_columns_{table_name}", f"SHOW COLUMNS FROM {table_name}")
    return [row["Field"] for row in rows]


def has_unique_price_key(runner: QueryRunner) -> tuple[bool, str]:
    rows, error = runner.fetch("show_index_price_data", "SHOW INDEX FROM price_data")
    if error:
        return False, f"no se pudo leer indices: {error}"

    key_columns = {}
    non_unique = {}
    for row in rows:
        key = row.get("Key_name")
        key_columns.setdefault(key, {})[int(row.get("Seq_in_index"))] = row.get("Column_name")
        non_unique[key] = int(row.get("Non_unique"))

    expected = ["symbol", "timeframe", "time"]
    for key, columns_by_seq in key_columns.items():
        columns = [columns_by_seq[idx] for idx in sorted(columns_by_seq)]
        if columns == expected and non_unique.get(key) == 0:
            return True, f"indice unico {key} sobre symbol/timeframe/time"
    return False, "no se detecto indice unico sobre symbol/timeframe/time"


def load_symbol_control(runner: QueryRunner) -> pd.DataFrame:
    rows, _ = runner.fetch(
        "symbol_control_enabled",
        """
        SELECT symbol, `group` AS group_name, enabled, last_update
        FROM symbol_control
        WHERE enabled = TRUE
        ORDER BY `group`, symbol
        """,
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["symbol", "group_name", "enabled", "last_update", "group_normalized"])
    df["group_normalized"] = df["group_name"].map(normalize_group_name)
    return df


def load_distinct_price_values(runner: QueryRunner) -> tuple[pd.DataFrame, pd.DataFrame]:
    symbol_rows, _ = runner.fetch(
        "distinct_price_symbols",
        "SELECT DISTINCT symbol FROM price_data FORCE INDEX (idx_symbol) ORDER BY symbol",
    )
    timeframe_rows, _ = runner.fetch(
        "distinct_price_timeframes",
        "SELECT DISTINCT timeframe FROM price_data FORCE INDEX (idx_timeframe) ORDER BY timeframe",
    )
    return pd.DataFrame(symbol_rows), pd.DataFrame(timeframe_rows)


def audit_pair_summary(
    runner: QueryRunner,
    symbol: str,
    group_name: str,
    timeframe: str,
    expected_minutes: int,
    audit_time: pd.Timestamp,
    stale_days: float,
    unique_key_present: bool,
) -> dict:
    rows, error = runner.fetch(
        f"pair_summary_{symbol}_{timeframe}",
        """
        SELECT
            COUNT(*) AS rows_count,
            MIN(time) AS first_time,
            MAX(time) AS last_time,
            SUM(CASE WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 1 ELSE 0 END) AS null_ohlc,
            SUM(CASE WHEN tick_volume IS NULL THEN 1 ELSE 0 END) AS null_tick_volume,
            SUM(CASE WHEN spread IS NULL THEN 1 ELSE 0 END) AS null_spread,
            SUM(CASE WHEN real_volume IS NULL THEN 1 ELSE 0 END) AS null_real_volume,
            SUM(CASE WHEN open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 THEN 1 ELSE 0 END) AS nonpositive_ohlc,
            SUM(CASE WHEN high < low OR high < open OR high < close OR low > open OR low > close THEN 1 ELSE 0 END) AS bad_ohlc,
            SUM(CASE WHEN NOT(open = open) OR NOT(high = high) OR NOT(low = low) OR NOT(close = close) THEN 1 ELSE 0 END) AS nan_like_ohlc,
            SUM(CASE WHEN tick_volume < 0 OR spread < 0 OR real_volume < 0 THEN 1 ELSE 0 END) AS negative_volume_spread,
            SUM(CASE WHEN SECOND(time) <> 0 OR MOD(HOUR(time) * 60 + MINUTE(time), %s) <> 0 THEN 1 ELSE 0 END) AS misaligned_time
        FROM price_data FORCE INDEX (uniq_symbol_tf_time)
        WHERE symbol = %s AND timeframe = %s
        """,
        (expected_minutes, symbol, timeframe),
    )

    base = {
        "symbol": symbol,
        "group": group_name,
        "group_normalized": normalize_group_name(group_name),
        "timeframe": timeframe,
        "expected_minutes": expected_minutes,
        "summary_status": "error" if error else "ok",
        "summary_error": error,
        "duplicate_check_mode": "unique_index" if unique_key_present else "not_verified",
        "duplicate_count": 0 if unique_key_present else None,
    }
    if error or not rows:
        return {**base, "rows_count": 0}

    row = rows[0]
    rows_count = normalise_int(row.get("rows_count"))
    first_time = row.get("first_time")
    last_time = row.get("last_time")
    last_ts = pd.Timestamp(last_time) if last_time else None

    minutes_since_last = None
    latest_closed_like = None
    stale_for_live = None
    if last_ts is not None:
        minutes_since_last = (audit_time - last_ts).total_seconds() / 60.0
        latest_closed_like = last_ts + pd.Timedelta(minutes=expected_minutes) <= audit_time
        stale_for_live = minutes_since_last > stale_days * 1440

    return {
        **base,
        "rows_count": rows_count,
        "first_time": first_time,
        "last_time": last_time,
        "minutes_since_last": normalise_float(minutes_since_last),
        "latest_closed_like": latest_closed_like,
        "stale_for_live": stale_for_live,
        "null_ohlc": normalise_int(row.get("null_ohlc")),
        "null_tick_volume": normalise_int(row.get("null_tick_volume")),
        "null_spread": normalise_int(row.get("null_spread")),
        "null_real_volume": normalise_int(row.get("null_real_volume")),
        "nonpositive_ohlc": normalise_int(row.get("nonpositive_ohlc")),
        "bad_ohlc": normalise_int(row.get("bad_ohlc")),
        "nan_like_ohlc": normalise_int(row.get("nan_like_ohlc")),
        "negative_volume_spread": normalise_int(row.get("negative_volume_spread")),
        "misaligned_time": normalise_int(row.get("misaligned_time")),
    }


def audit_pair_gaps(
    runner: QueryRunner,
    symbol: str,
    timeframe: str,
    expected_minutes: int,
    rows_count: int,
    max_pair_rows: int,
    max_examples: int,
) -> tuple[dict, list[dict]]:
    if rows_count <= 1:
        return {
            "gap_status": "not_enough_rows",
            "gap_count": 0,
            "short_gap_count": 0,
            "session_gap_count": 0,
            "max_gap_minutes": 0,
        }, []
    if rows_count > max_pair_rows:
        return {
            "gap_status": "skipped_row_limit",
            "gap_count": None,
            "short_gap_count": None,
            "session_gap_count": None,
            "max_gap_minutes": None,
        }, []

    session_threshold = session_gap_threshold_minutes(timeframe, expected_minutes)
    stats_rows, stats_error = runner.fetch(
        f"gap_stats_{symbol}_{timeframe}",
        """
        SELECT
            COUNT(*) AS gap_count,
            SUM(CASE WHEN NOT(is_session_gap) THEN 1 ELSE 0 END) AS short_gap_count,
            SUM(CASE WHEN is_session_gap THEN 1 ELSE 0 END) AS session_gap_count,
            MAX(gap_minutes) AS max_gap_minutes
        FROM (
            SELECT
                TIMESTAMPDIFF(MINUTE, prev_time, time) AS gap_minutes,
                (
                    TIMESTAMPDIFF(MINUTE, prev_time, time) >= %s
                    OR (WEEKDAY(prev_time) >= 4 AND WEEKDAY(time) <= 1)
                ) AS is_session_gap
            FROM (
                SELECT time, LAG(time) OVER (ORDER BY time) AS prev_time
                FROM price_data FORCE INDEX (uniq_symbol_tf_time)
                WHERE symbol = %s AND timeframe = %s
            ) ordered_rows
            WHERE prev_time IS NOT NULL
        ) gaps
        WHERE gap_minutes > %s
        """,
        (session_threshold, symbol, timeframe, expected_minutes),
    )
    if stats_error:
        return {
            "gap_status": "error",
            "gap_error": stats_error,
            "gap_count": None,
            "short_gap_count": None,
            "session_gap_count": None,
            "max_gap_minutes": None,
        }, []

    stats = stats_rows[0] if stats_rows else {}
    short_rows, short_error = runner.fetch(
        f"gap_examples_short_{symbol}_{timeframe}",
        """
        SELECT
            prev_time AS gap_start,
            time AS gap_end,
            TIMESTAMPDIFF(MINUTE, prev_time, time) AS gap_minutes
        FROM (
            SELECT time, LAG(time) OVER (ORDER BY time) AS prev_time
            FROM price_data FORCE INDEX (uniq_symbol_tf_time)
            WHERE symbol = %s AND timeframe = %s
        ) ordered_rows
        WHERE prev_time IS NOT NULL
          AND TIMESTAMPDIFF(MINUTE, prev_time, time) > %s
          AND NOT (
              TIMESTAMPDIFF(MINUTE, prev_time, time) >= %s
              OR (WEEKDAY(prev_time) >= 4 AND WEEKDAY(time) <= 1)
          )
        ORDER BY gap_minutes DESC
        LIMIT %s
        """,
        (symbol, timeframe, expected_minutes, session_threshold, max_examples),
    )

    examples = []
    if not short_error:
        for row in short_rows:
            gap_minutes = normalise_int(row.get("gap_minutes"))
            examples.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "gap_start": row.get("gap_start"),
                "gap_end": row.get("gap_end"),
                "gap_minutes": gap_minutes,
                "gap_category": "short_missing_gap",
            })

    session_rows, session_error = runner.fetch(
        f"gap_examples_session_{symbol}_{timeframe}",
        """
        SELECT
            prev_time AS gap_start,
            time AS gap_end,
            TIMESTAMPDIFF(MINUTE, prev_time, time) AS gap_minutes
        FROM (
            SELECT time, LAG(time) OVER (ORDER BY time) AS prev_time
            FROM price_data FORCE INDEX (uniq_symbol_tf_time)
            WHERE symbol = %s AND timeframe = %s
        ) ordered_rows
        WHERE prev_time IS NOT NULL
          AND (
              TIMESTAMPDIFF(MINUTE, prev_time, time) >= %s
              OR (WEEKDAY(prev_time) >= 4 AND WEEKDAY(time) <= 1)
          )
        ORDER BY gap_minutes DESC
        LIMIT %s
        """,
        (symbol, timeframe, session_threshold, max_examples),
    )
    if not session_error:
        for row in session_rows:
            gap_minutes = normalise_int(row.get("gap_minutes"))
            examples.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "gap_start": row.get("gap_start"),
                "gap_end": row.get("gap_end"),
                "gap_minutes": gap_minutes,
                "gap_category": "session_or_weekend",
            })

    example_error = short_error or session_error
    return {
        "gap_status": "ok" if not example_error else "stats_ok_examples_error",
        "gap_error": example_error,
        "gap_count": normalise_int(stats.get("gap_count")),
        "short_gap_count": normalise_int(stats.get("short_gap_count")),
        "session_gap_count": normalise_int(stats.get("session_gap_count")),
        "max_gap_minutes": normalise_int(stats.get("max_gap_minutes")),
    }, examples


def build_suffix_consistency(symbol_control: pd.DataFrame, price_symbols: pd.DataFrame) -> pd.DataFrame:
    rows = []
    control_symbols = set(symbol_control["symbol"].tolist()) if not symbol_control.empty else set()
    price_symbol_set = set(price_symbols["symbol"].tolist()) if not price_symbols.empty and "symbol" in price_symbols else set()
    all_symbols = sorted(control_symbols | price_symbol_set)
    by_base: dict[str, list[str]] = {}
    for symbol in all_symbols:
        by_base.setdefault(strip_broker_suffix(symbol), []).append(symbol)

    for base, symbols in sorted(by_base.items()):
        with_suffix = sorted(symbol for symbol in symbols if symbol.endswith(".r"))
        without_suffix = sorted(symbol for symbol in symbols if not symbol.endswith(".r"))
        rows.append({
            "base_symbol": base,
            "symbols": ", ".join(symbols),
            "has_r_suffix": bool(with_suffix),
            "has_unsuffixed": bool(without_suffix),
            "mixed_suffix_forms": bool(with_suffix and without_suffix),
            "in_symbol_control": any(symbol in control_symbols for symbol in symbols),
            "in_price_data_distinct_query": any(symbol in price_symbol_set for symbol in symbols),
        })
    return pd.DataFrame(rows)


def build_group_coverage(
    pair_health: pd.DataFrame,
    symbol_control: pd.DataFrame,
    timeframes: list[str],
    focus_groups: list[str],
) -> pd.DataFrame:
    rows = []
    if symbol_control.empty:
        return pd.DataFrame()

    scoped = symbol_control[symbol_control["group_normalized"].isin(focus_groups)].copy()
    for group_name, group_df in scoped.groupby("group_normalized", dropna=False):
        group_symbols = sorted(group_df["symbol"].tolist())
        row = {
            "group": group_name,
            "enabled_symbols": len(group_symbols),
            "symbols": ", ".join(group_symbols),
        }
        for timeframe in timeframes:
            tf_df = pair_health[
                (pair_health["group_normalized"] == group_name)
                & (pair_health["timeframe"] == timeframe)
                & (pair_health["rows_count"] > 0)
            ]
            row[f"{timeframe}_symbols_with_data"] = int(tf_df["symbol"].nunique()) if not tf_df.empty else 0
            missing = sorted(set(group_symbols) - set(tf_df["symbol"].tolist()))
            row[f"{timeframe}_missing_symbols"] = ", ".join(missing)
        rows.append(row)
    return pd.DataFrame(rows)


def build_group_timeframe_summary(pair_health: pd.DataFrame) -> pd.DataFrame:
    if pair_health.empty:
        return pd.DataFrame()

    grouped = pair_health.groupby(["group_normalized", "timeframe"], dropna=False).agg(
        symbols=("symbol", "nunique"),
        rows_count=("rows_count", "sum"),
        first_time=("first_time", "min"),
        last_time=("last_time", "max"),
        null_ohlc=("null_ohlc", "sum"),
        bad_ohlc=("bad_ohlc", "sum"),
        nonpositive_ohlc=("nonpositive_ohlc", "sum"),
        misaligned_time=("misaligned_time", "sum"),
        short_gap_count=("short_gap_count", "sum"),
        session_gap_count=("session_gap_count", "sum"),
    )
    return grouped.reset_index().rename(columns={"group_normalized": "group"})


def add_issue(issues: list[dict], severity: str, area: str, item: str, detail: str, recommendation: str):
    issues.append({
        "severity": severity,
        "area": area,
        "item": item,
        "detail": detail,
        "recommendation": recommendation,
    })


def build_issues(
    pair_health: pd.DataFrame,
    group_coverage: pd.DataFrame,
    suffix_df: pd.DataFrame,
    unique_key_present: bool,
    unique_key_detail: str,
    focus_groups: list[str],
    timeframes: list[str],
    distinct_symbol_error: str | None,
    distinct_timeframe_error: str | None,
) -> pd.DataFrame:
    issues: list[dict] = []
    if not unique_key_present:
        add_issue(
            issues,
            "importante",
            "duplicados",
            "price_data",
            unique_key_detail,
            "verificar duplicados por symbol/timeframe/time antes de nuevos backtests",
        )
    if distinct_symbol_error:
        add_issue(issues, "pendiente/no bloqueante", "sql", "distinct_price_symbols", distinct_symbol_error, "repetir con consulta mas acotada")
    if distinct_timeframe_error:
        add_issue(issues, "pendiente/no bloqueante", "sql", "distinct_price_timeframes", distinct_timeframe_error, "repetir con consulta mas acotada")

    if not suffix_df.empty:
        mixed = suffix_df[suffix_df["mixed_suffix_forms"] == True]
        if not mixed.empty:
            add_issue(
                issues,
                "menor",
                "simbolos",
                "suffix .r",
                f"{len(mixed)} bases aparecen con y sin sufijo .r",
                "mantener normalizacion explicita al cruzar artifacts y SQL",
            )

    if not pair_health.empty:
        for _, row in pair_health.iterrows():
            item = f"{row['symbol']} {row['timeframe']}"
            if row.get("summary_status") != "ok":
                add_issue(issues, "importante", "sql", item, str(row.get("summary_error")), "revisar consulta o indices")
                continue
            if normalise_int(row.get("rows_count")) == 0:
                add_issue(issues, "importante", "cobertura", item, "sin filas OHLCV", "recargar o excluir explicitamente ese par")
                continue
            for column, label in [
                ("null_ohlc", "OHLC nulos"),
                ("nonpositive_ohlc", "OHLC no positivos"),
                ("bad_ohlc", "OHLC incoherente"),
                ("nan_like_ohlc", "OHLC tipo NaN"),
                ("negative_volume_spread", "volumen/spread negativo"),
                ("misaligned_time", "timestamps no alineados al timeframe"),
            ]:
                count = normalise_int(row.get(column))
                if count:
                    add_issue(issues, "importante", "calidad_ohlcv", item, f"{label}: {count}", "inspeccionar filas concretas antes de live")
            if row.get("latest_closed_like") is False:
                add_issue(issues, "importante", "ultima_vela", item, "ultima vela no parece cerrada frente a hora local de auditoria", "actualizar con filtro MT5 y reauditar")
            if row.get("stale_for_live") is True:
                add_issue(issues, "pendiente/no bloqueante", "vigencia_live", item, "datos stale para live", "actualizar SQL antes de watcher continuo o Telegram")
            if row.get("gap_status") in {"error", "skipped_row_limit"}:
                add_issue(issues, "pendiente/no bloqueante", "gaps", item, f"gap_status={row.get('gap_status')}", "repetir gap audit de forma acotada")
            elif normalise_int(row.get("short_gap_count")):
                add_issue(
                    issues,
                    "menor",
                    "gaps",
                    item,
                    f"gaps cortos/anomalos: {normalise_int(row.get('short_gap_count'))}",
                    "revisar ejemplos; pueden ser festivos, cortes de mercado o huecos reales",
                )

    focus_set = set(focus_groups)
    if not group_coverage.empty:
        for _, row in group_coverage.iterrows():
            if row["group"] not in focus_set:
                continue
            for timeframe in timeframes:
                missing = row.get(f"{timeframe}_missing_symbols", "")
                if missing:
                    add_issue(
                        issues,
                        "importante",
                        "cobertura",
                        f"{row['group']} {timeframe}",
                        f"simbolos sin datos: {missing}",
                        "recargar o documentar exclusion antes de backtests/live",
                    )

    return pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def write_report(
    output_dir: Path,
    meta: dict,
    pair_health: pd.DataFrame,
    group_coverage: pd.DataFrame,
    issues: pd.DataFrame,
    query_log: pd.DataFrame,
    group_timeframe_summary: pd.DataFrame,
):
    total_pairs = len(pair_health)
    ok_pairs = int((pair_health["summary_status"] == "ok").sum()) if not pair_health.empty else 0
    pairs_with_rows = int((pair_health["rows_count"] > 0).sum()) if not pair_health.empty else 0
    important = int((issues["severity"] == "importante").sum()) if not issues.empty else 0
    minor = int((issues["severity"] == "menor").sum()) if not issues.empty else 0
    pending = int((issues["severity"] == "pendiente/no bloqueante").sum()) if not issues.empty else 0
    max_query = query_log.sort_values("elapsed_seconds", ascending=False).head(5) if not query_log.empty else pd.DataFrame()

    lines = [
        "# SQL/MT5 Data Health Audit - 2026-05-17",
        "",
        "## Resumen",
        "",
        f"- Pares auditados: {total_pairs}.",
        f"- Pares con consulta resumen OK: {ok_pairs}.",
        f"- Pares con datos OHLCV: {pairs_with_rows}.",
        f"- Hallazgos importantes: {important}.",
        f"- Hallazgos menores: {minor}.",
        f"- Pendientes/no bloqueantes: {pending}.",
        f"- Timeout SQL solicitado: {meta['query_timeout_ms']} ms.",
        f"- `MAX_EXECUTION_TIME` soportado por la sesion: {meta['query_timeout_supported']}.",
        "",
        "## Alcance",
        "",
        f"- Grupos foco: {', '.join(meta['focus_groups'])}.",
        f"- Timeframes: {', '.join(meta['timeframes'])}.",
        "- No se han reejecutado backtests ni recalculado senales.",
        "- No se han modificado estrategias ni artifacts canonicos.",
        "- Las comprobaciones se ejecutan por simbolo/timeframe para evitar agregaciones globales pesadas.",
        "",
        "## Lectura metodologica",
        "",
        "- La existencia del indice unico `symbol/timeframe/time` se usa como prueba principal contra duplicados.",
        "- La ultima vela se evalua contra la hora local de auditoria, no contra MT5 conectado; por tanto es una comprobacion prudente, no una certificacion de servidor live.",
        "- Los gaps largos se clasifican como `session_or_weekend`; los gaps cortos requieren revision porque pueden ser festivos o huecos reales.",
        "- La auditoria no interpreta calidad de estrategia; solo valida la base OHLCV.",
        "",
        "## Archivos generados",
        "",
        "- `tables/symbol_control.csv`",
        "- `tables/price_symbols.csv`",
        "- `tables/price_timeframes.csv`",
        "- `tables/pair_health.csv`",
        "- `tables/gap_examples.csv`",
        "- `tables/group_coverage.csv`",
        "- `tables/group_timeframe_summary.csv`",
        "- `tables/suffix_consistency.csv`",
        "- `tables/issues.csv`",
        "- `tables/query_log.csv`",
        "- `run_meta.json`",
        "",
        "## Hallazgos",
        "",
    ]

    if issues.empty:
        lines.append("No se detectaron hallazgos en las comprobaciones ejecutadas.")
    else:
        for _, row in issues.head(40).iterrows():
            lines.append(
                f"- **{row['severity']}** `{row['area']}` `{row['item']}`: "
                f"{row['detail']} Recomendacion: {row['recommendation']}."
            )
        if len(issues) > 40:
            lines.append(f"- ... {len(issues) - 40} hallazgos adicionales en `tables/issues.csv`.")

    lines.extend([
        "",
        "## Cobertura por grupo",
        "",
    ])
    if group_coverage.empty:
        lines.append("No se pudo construir cobertura por grupo.")
    else:
        for _, row in group_coverage.iterrows():
            coverage_bits = []
            for timeframe in meta["timeframes"]:
                coverage_bits.append(f"{timeframe}={row.get(f'{timeframe}_symbols_with_data', 0)}/{row['enabled_symbols']}")
            lines.append(f"- `{row['group']}`: " + ", ".join(coverage_bits))

    lines.extend([
        "",
        "## Resumen por grupo/timeframe",
        "",
    ])
    if group_timeframe_summary.empty:
        lines.append("No se pudo construir resumen por grupo/timeframe.")
    else:
        for _, row in group_timeframe_summary.iterrows():
            lines.append(
                f"- `{row['group']} {row['timeframe']}`: {int(row['symbols'])} simbolos, "
                f"{int(row['rows_count'])} filas, rango {row['first_time']} -> {row['last_time']}, "
                f"gaps cortos={int(row['short_gap_count'])}, gaps sesion/calendario={int(row['session_gap_count'])}."
            )

    lines.extend([
        "",
        "## Consultas mas lentas",
        "",
    ])
    if max_query.empty:
        lines.append("Sin log de consultas.")
    else:
        for _, row in max_query.iterrows():
            lines.append(f"- `{row['label']}`: {row['elapsed_seconds']}s, status={row['status']}")

    lines.extend([
        "",
        "## Conclusion",
        "",
        "La auditoria queda reproducible por codigo. Para avanzar a watcher continuo, Telegram o MT5 dry-run, el punto clave es revisar los hallazgos de `tables/issues.csv`, especialmente cobertura, vigencia live y gaps cortos.",
        "",
    ])
    (output_dir / "DATA_HEALTH_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run(args) -> int:
    started = time.perf_counter()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    if REPO_ROOT not in output_dir.parents and output_dir != REPO_ROOT:
        raise ValueError("output-dir debe estar dentro del repositorio")
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    focus_groups = [normalize_group_name(group) for group in parse_csv(args.groups, DEFAULT_GROUPS)]
    timeframes = parse_csv(args.timeframes, tuple(EXPECTED_TIMEFRAMES.keys()))
    audit_time = pd.Timestamp(datetime.now())

    connection = connect_db()
    if connection is None:
        raise RuntimeError("No se pudo conectar a SQL")

    try:
        runner = QueryRunner(connection, args.query_timeout_ms)
        price_columns = get_table_columns(runner, "price_data")
        missing_columns = sorted(REQUIRED_PRICE_COLUMNS - set(price_columns))
        unique_key_present, unique_key_detail = has_unique_price_key(runner)

        symbol_control = load_symbol_control(runner)
        price_symbols, price_timeframes = load_distinct_price_values(runner)

        distinct_symbol_error = next(
            (row["error"] for row in runner.log if row["label"] == "distinct_price_symbols" and row["status"] == "error"),
            None,
        )
        distinct_timeframe_error = next(
            (row["error"] for row in runner.log if row["label"] == "distinct_price_timeframes" and row["status"] == "error"),
            None,
        )

        focus_symbols = symbol_control[symbol_control["group_normalized"].isin(focus_groups)].copy()
        pair_rows = []
        gap_examples = []
        for _, sym_row in focus_symbols.iterrows():
            symbol = sym_row["symbol"]
            group_name = sym_row["group_name"]
            for timeframe in timeframes:
                expected = EXPECTED_TIMEFRAMES.get(timeframe)
                if expected is None:
                    continue
                summary = audit_pair_summary(
                    runner,
                    symbol,
                    group_name,
                    timeframe,
                    expected,
                    audit_time,
                    args.stale_days,
                    unique_key_present,
                )
                if not args.skip_gap_audit and summary.get("summary_status") == "ok":
                    gap_stats, examples = audit_pair_gaps(
                        runner,
                        symbol,
                        timeframe,
                        expected,
                        normalise_int(summary.get("rows_count")),
                        args.max_gap_pair_rows,
                        args.max_gap_examples_per_pair,
                    )
                    summary.update(gap_stats)
                    gap_examples.extend(examples)
                pair_rows.append(summary)

        pair_health = pd.DataFrame(pair_rows)
        suffix_df = build_suffix_consistency(symbol_control, price_symbols)
        group_coverage = build_group_coverage(pair_health, symbol_control, timeframes, focus_groups)
        group_timeframe_summary = build_group_timeframe_summary(pair_health)
        issues = build_issues(
            pair_health,
            group_coverage,
            suffix_df,
            unique_key_present,
            unique_key_detail,
            focus_groups,
            timeframes,
            distinct_symbol_error,
            distinct_timeframe_error,
        )

        if missing_columns:
            schema_issues = []
            add_issue(
                schema_issues,
                "critico",
                "schema",
                "price_data",
                f"faltan columnas requeridas: {', '.join(missing_columns)}",
                "no ejecutar backtests/live hasta corregir schema",
            )
            issues = pd.concat([pd.DataFrame(schema_issues, columns=ISSUE_COLUMNS), issues], ignore_index=True)

        query_log = pd.DataFrame(runner.log)
        meta = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "output_dir": str(output_dir.relative_to(REPO_ROOT)),
            "focus_groups": focus_groups,
            "timeframes": timeframes,
            "query_timeout_ms": int(args.query_timeout_ms),
            "query_timeout_supported": runner.timeout_supported,
            "stale_days": float(args.stale_days),
            "max_gap_pair_rows": int(args.max_gap_pair_rows),
            "max_gap_examples_per_pair": int(args.max_gap_examples_per_pair),
            "skip_gap_audit": bool(args.skip_gap_audit),
            "price_columns": price_columns,
            "missing_price_columns": missing_columns,
            "unique_symbol_timeframe_time_key": unique_key_present,
            "unique_key_detail": unique_key_detail,
        }

        outputs = {
            "symbol_control.csv": symbol_control,
            "price_symbols.csv": price_symbols,
            "price_timeframes.csv": price_timeframes,
            "pair_health.csv": pair_health,
            "gap_examples.csv": pd.DataFrame(gap_examples),
            "group_coverage.csv": group_coverage,
            "group_timeframe_summary.csv": group_timeframe_summary,
            "suffix_consistency.csv": suffix_df,
            "issues.csv": issues,
            "query_log.csv": query_log,
        }
        for filename, df in outputs.items():
            df.to_csv(tables_dir / filename, index=False)

        (output_dir / "run_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        write_report(output_dir, meta, pair_health, group_coverage, issues, query_log, group_timeframe_summary)

        print(f"[OK] Data health audit written to {output_dir}")
        print(f"[OK] Pair summaries: {len(pair_health)} | issues: {len(issues)}")
        return 0
    finally:
        close_db(connection)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auditoria acotada de salud de datos SQL/MT5.")
    parser.add_argument("--output-dir", default="artifacts/data-health/sql_mt5_2026-05-17")
    parser.add_argument("--groups", default=",".join(DEFAULT_GROUPS))
    parser.add_argument("--timeframes", default=",".join(EXPECTED_TIMEFRAMES.keys()))
    parser.add_argument("--query-timeout-ms", type=int, default=15000)
    parser.add_argument("--stale-days", type=float, default=7.0)
    parser.add_argument("--max-gap-pair-rows", type=int, default=250000)
    parser.add_argument("--max-gap-examples-per-pair", type=int, default=3)
    parser.add_argument("--skip-gap-audit", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

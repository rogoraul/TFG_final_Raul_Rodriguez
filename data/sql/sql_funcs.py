"""SQL helpers for market ingestion and symbol metadata.

These functions can open a real local MySQL connection. Tests should mock the
connector unless they explicitly validate local infrastructure.
"""

from __future__ import annotations

import mysql.connector
from mysql.connector import Error
import pandas as pd
import time

from backtests.common.backtest_matrix_config import normalize_group_name
from data.sql.db_config import load_db_config

SYMBOL_METADATA_COLUMNS = (
    "symbol",
    "digits",
    "point_size",
    "trade_tick_size",
    "trade_tick_value",
    "trade_tick_value_profit",
    "trade_tick_value_loss",
    "trade_contract_size",
    "volume_min",
    "volume_max",
    "volume_step",
    "currency_base",
    "currency_profit",
    "currency_margin",
    "trade_mode",
    "source",
    "updated_at",
)

def connect_db():
    """Open a MySQL connection from local config, returning None on failure."""
    db_config, config_source = load_db_config()
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            return connection
    except Error as e:
        print(
            "Error conectando a MySQL: "
            f"{e}. Config source: {config_source}. "
            "Define TRADING_DB_* en el entorno o crea un .env local."
        )
    return None

def close_db(connection):
    """Close an open DB connection if it is still connected."""
    if connection is not None and connection.is_connected():
        connection.close()


def _fetch_dataframe(connection, query, params=None):
    """Execute a read query and return rows as a DataFrame."""
    cursor = connection.cursor()
    try:
        cursor.execute(query, params or ())
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description] if cursor.description else []
    finally:
        cursor.close()

    if not rows:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(rows, columns=columns)


def _get_table_columns(connection, table_name):
    """Return column names for a SQL table."""
    cursor = connection.cursor()
    try:
        cursor.execute(f"SHOW COLUMNS FROM {table_name}")
        rows = cursor.fetchall()
    finally:
        cursor.close()

    if not rows:
        return []

    return [row[0] for row in rows]

def get_enabled_symbols():
    """
    Devuelve una lista con los simbolos que estan activados (enabled = TRUE).
    """
    connection = connect_db()
    if connection is None:
        return []

    query = "SELECT symbol FROM symbol_control WHERE enabled = TRUE;"
    try:
        df = pd.read_sql(query, connection)
        symbols = df["symbol"].tolist()
    except Error as e:
        print(f"Error al consultar simbolos habilitados: {e}")
        symbols = []
    finally:
        close_db(connection)

    return symbols

def get_symbols_by_group():
    """
    Devuelve un diccionario {grupo: [lista_de_symbols]} desde symbol_control.
    Solo incluye simbolos habilitados (enabled = TRUE).
    """
    connection = connect_db()
    if connection is None:
        return {}

    query = "SELECT symbol, `group` FROM symbol_control WHERE enabled = TRUE;"
    try:
        df = pd.read_sql(query, connection)
        grupos = {}
        for _, row in df.iterrows():
            grupo = row['group'] if row['group'] else 'Sin Grupo'
            if grupo not in grupos:
                grupos[grupo] = []
            grupos[grupo].append(row['symbol'])
    except Error as e:
        print(f"Error al consultar grupos: {e}")
        grupos = {}
    finally:
        close_db(connection)

    return grupos

def get_symbol_groups():
    """
    Devuelve un DataFrame con las columnas 'symbol' y 'group'.
    Util para hacer merge con resultados de backtest.
    """
    connection = connect_db()
    if connection is None:
        return pd.DataFrame()

    query = "SELECT symbol, `group` FROM symbol_control WHERE enabled = TRUE;"
    try:
        df = pd.read_sql(query, connection)
    except Error as e:
        print(f"Error al consultar grupos: {e}")
        df = pd.DataFrame()
    finally:
        close_db(connection)

    return df


def get_symbols_by_group_normalized(selected_groups=None):
    """
    Devuelve grupos normalizados para backtests y comparativas.

    Args:
        selected_groups: iterable opcional con los grupos ya normalizados
            que se quieren conservar.
    """
    raw_groups = get_symbols_by_group()
    normalized = {}

    for group_name, symbols in raw_groups.items():
        normalized_name = normalize_group_name(group_name)
        if normalized_name is None:
            continue
        normalized.setdefault(normalized_name, []).extend(symbols)

    if selected_groups is None:
        return normalized

    wanted = set(selected_groups)
    return {group: normalized.get(group, []) for group in wanted}


def upsert_symbol_metadata(symbol, digits, point_size, source="MT5", **extra_fields):
    """
    Inserta o actualiza precision del simbolo en `symbol_metadata`.
    """
    connection = connect_db()
    if connection is None:
        print("No se pudo conectar a la base de datos.")
        return False

    try:
        available_columns = set(_get_table_columns(connection, "symbol_metadata"))
        if not available_columns:
            return False

        payload = {
            "symbol": symbol,
            "digits": int(digits),
            "point_size": float(point_size),
            "source": source,
        }
        payload.update(extra_fields or {})

        insert_columns = [
            column for column in SYMBOL_METADATA_COLUMNS
            if column in available_columns and column in payload and payload[column] is not None
        ]

        if not insert_columns:
            return False

        placeholders = ", ".join(["%s"] * len(insert_columns))
        update_columns = [
            f"{column} = VALUES({column})"
            for column in insert_columns
            if column != "symbol"
        ]
        if "updated_at" in available_columns:
            update_columns.append("updated_at = CURRENT_TIMESTAMP")

        query = f"""
            INSERT INTO symbol_metadata ({", ".join(insert_columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE
                {", ".join(update_columns)}
        """

        values = [payload[column] for column in insert_columns]
        cursor = connection.cursor()
        cursor.execute(query, values)
        connection.commit()
        return True
    except Error as e:
        print(f"Error guardando metadata de {symbol}: {e}")
        return False
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        close_db(connection)


def get_symbol_metadata_map(symbols=None):
    """
    Devuelve {symbol: {...}} con los metadatos disponibles en SQL.

    Si la tabla `symbol_metadata` todavia no existe, devuelve {} para
    mantener compatibilidad y dejar que el sistema use fallback.
    """
    connection = connect_db()
    if connection is None:
        return {}

    try:
        available_columns = _get_table_columns(connection, "symbol_metadata")
        if not available_columns:
            return {}

        select_columns = [
            column for column in SYMBOL_METADATA_COLUMNS
            if column in available_columns
        ]
        params = []
        query = f"SELECT {', '.join(select_columns)} FROM symbol_metadata"
        if symbols:
            placeholders = ', '.join(['%s'] * len(symbols))
            query += f" WHERE symbol IN ({placeholders})"
            params.extend(symbols)
        query += " ORDER BY symbol ASC"

        df = _fetch_dataframe(connection, query, params)
    except Error as e:
        print(f"[WARN] No se pudo leer symbol_metadata: {e}")
        return {}
    finally:
        close_db(connection)

    if df.empty:
        return {}

    metadata = {}
    for _, row in df.iterrows():
        item = {}
        for column in df.columns:
            value = row[column]
            if pd.isna(value):
                item[column] = None
            elif column in {
                'digits',
                'trade_mode',
            }:
                item[column] = int(value)
            elif column in {
                'point_size',
                'trade_tick_size',
                'trade_tick_value',
                'trade_tick_value_profit',
                'trade_tick_value_loss',
                'trade_contract_size',
                'volume_min',
                'volume_max',
                'volume_step',
            }:
                item[column] = float(value)
            else:
                item[column] = value
        metadata[row['symbol']] = item

    return metadata

def insertar_datos(df, symbol, timeframe):
    """
    Inserta un DataFrame con las columnas: time, open, high, low, close, tick_volume, spread, real_volume.
    """
    connection = connect_db()
    if connection is None:
        print("No se pudo conectar a la base de datos.")
        return

    cursor = connection.cursor()
    insert_query = """
        INSERT INTO price_data 
        (symbol, timeframe, time, open, high, low, close, tick_volume, spread, real_volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            open=VALUES(open),
            high=VALUES(high),
            low=VALUES(low),
            close=VALUES(close),
            tick_volume=VALUES(tick_volume),
            spread=VALUES(spread),
            real_volume=VALUES(real_volume)
    """

    records = [
        (symbol, timeframe, row.time, row.open, row.high, row.low, row.close, row.tick_volume, row.spread, row.real_volume)
        for _, row in df.iterrows()
    ]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            cursor.executemany(insert_query, records)
            connection.commit()
            print(f"Insertadas/actualizadas {cursor.rowcount} filas para {symbol}-{timeframe}")
            break # Éxito, salir del bucle
        except Error as e:
            if e.errno == 1213: # Deadlock
                if attempt < max_retries - 1:
                    sleep_time = (attempt + 1) * 2 # 2s, 4s...
                    print(f"Deadlock detectado (1213). Reintentando en {sleep_time}s... (Intento {attempt+1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    print(f"Deadlock persistente después de {max_retries} intentos. Abortando {symbol}-{timeframe}.")
            else:
                print(f"Error insertando datos: {e}")
                break
    cursor.close()
    close_db(connection)

def obtener_ultima_fecha(symbol, timeframe):
    """
    Devuelve la última fecha almacenada en la tabla price_data 
    para el símbolo y timeframe indicados.
    Retorna None si no existen datos.
    """
    connection = connect_db()
    if connection is None:
        print("No se pudo conectar a la base de datos.")
        return None

    query = """
        SELECT MAX(time) AS last_time
        FROM price_data
        WHERE symbol = %s AND timeframe = %s;
    """

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (symbol, timeframe))
        result = cursor.fetchone()
        last_date = result["last_time"] if result and result["last_time"] is not None else None
        return last_date
    except Error as e:
        print(f"Error al obtener la última fecha: {e}")
        return None
    finally:
        cursor.close()
        close_db(connection)

def cargar_datos_ohlc(symbol, timeframe):
    """
    Carga todos los datos OHLCV para un activo y timeframe.
    Devuelve un DataFrame con índice Datetime, o None si falla.
    """
    print(f"--- Cargando {symbol} ({timeframe}) desde SQL ---")
    conn = connect_db()
    if not conn:
        print("Error: No se pudo conectar a la BD.")
        return None
    
    query = f"""
        SELECT time, open, high, low, close, tick_volume as volume, spread
        FROM price_data
        WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'
        ORDER BY time ASC
    """
    
    try:
        df = pd.read_sql(query, conn)
    except Exception as e:
        print(f"Error SQL: {e}")
        close_db(conn)
        return None
    finally:
        close_db(conn)
    
    if not df.empty:
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        return df
    else:
        print("Advertencia: DataFrame vacío.")
        return None


def cargar_datos_ohlc_batch(symbols, timeframe, connection=None):
    """
    Carga OHLCV para varios simbolos y devuelve {symbol: DataFrame}.
    """
    if not symbols:
        return {}

    conn = connection or connect_db()
    if not conn:
        return {}

    own_connection = connection is None
    placeholders = ', '.join(['%s'] * len(symbols))
    query = f"""
        SELECT symbol, time, open, high, low, close, tick_volume as volume, spread
        FROM price_data
        WHERE symbol IN ({placeholders}) AND timeframe = %s
        ORDER BY symbol ASC, time ASC
    """

    try:
        df = _fetch_dataframe(conn, query, [*symbols, timeframe])
    finally:
        if own_connection:
            close_db(conn)

    if df.empty:
        return {}

    df['time'] = pd.to_datetime(df['time'])
    datasets = {}
    for symbol, sym_df in df.groupby('symbol', sort=False):
        datasets[symbol] = sym_df.drop(columns=['symbol']).set_index('time')

    return datasets


def cargar_datos_close(symbol, timeframe):
    """
    Carga SOLO time y close para un activo y timeframe.
    Optimizado para calcular tendencias HTF sin cargar todo el volumen de datos.
    """
    print(f"--- Cargando Close {symbol} ({timeframe}) desde SQL ---")
    conn = connect_db()
    if not conn:
        return None
    
    query = f"""
        SELECT time, close
        FROM price_data
        WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'
        ORDER BY time ASC
    """
    
    try:
        df = pd.read_sql(query, conn)
    except Exception as e:
        print(f"Error SQL: {e}")
        close_db(conn)
        return None
    finally:
        close_db(conn)
    
    if not df.empty:
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        return df
    return None


def cargar_datos_close_batch(symbols, timeframe, connection=None):
    """
    Carga time y close para varios simbolos y devuelve {symbol: DataFrame}.
    """
    if not symbols:
        return {}

    conn = connection or connect_db()
    if not conn:
        return {}

    own_connection = connection is None
    placeholders = ', '.join(['%s'] * len(symbols))
    query = f"""
        SELECT symbol, time, close
        FROM price_data
        WHERE symbol IN ({placeholders}) AND timeframe = %s
        ORDER BY symbol ASC, time ASC
    """

    try:
        df = _fetch_dataframe(conn, query, [*symbols, timeframe])
    finally:
        if own_connection:
            close_db(conn)

    if df.empty:
        return {}

    df['time'] = pd.to_datetime(df['time'])
    datasets = {}
    for symbol, sym_df in df.groupby('symbol', sort=False):
        datasets[symbol] = sym_df.drop(columns=['symbol']).set_index('time')

    return datasets



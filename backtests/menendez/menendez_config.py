from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy

from backtests.common.backtest_matrix_config import TEMPORAL_SPLITS


DEFAULT_GROUP = "Forex Majors"
DEFAULT_TIMEFRAME_LTF = "M30"
DEFAULT_TIMEFRAME_HTF = "H4"

TIMEFRAME_FREQ = {
    "M30": "30min",
    "H4": "4h",
}

DEFAULT_INDICATOR_CONFIG = {
    "psar_step": 0.02,
    "psar_max_step": 0.20,
    "sma_periods": (5, 8, 13, 21, 50, 200),
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "stoch_k": 14,
    "stoch_d": 3,
    "stoch_smooth": 3,
    "bb_length": 20,
    "bb_std": 2.0,
}

DEFAULT_CONTEXT_CONFIG = {
    "retracement_min": 0.382,
    "retracement_max": 0.618,
    "macd_neutral_threshold": 0.001,
    "macd_standby_bars": 12,
    "use_h4_standby_filter": False,
    "h4_trend_filter": "sma21_slope",
    "macd_memory_bars": 1,
    "signal_memory_bars": 5,
    "candidate_window_mode": "memory",
    "candidate_window_max_bars": 0,
    "stoch_memory_bars": 3,
    "stoch_oversold": 20.0,
    "stoch_overbought": 80.0,
    "fan_breakout_tolerance": 0.0,
    "min_rr": 1.0,
    "entry_primary_trigger_mode": "fan_breakout",
    "entry_momentum_confirm_mode": "macd_and_stoch",
    "tp_include_bollinger": True,
    "session_filter_enabled": False,
    "session_start_hour_utc": 7,
    "session_end_hour_utc": 17,
    "corrective_equivalents": (1, 7, 11, 15, 19),
    "motor_equivalents": (5, 9, 13, 17),
    # ZLR (Zero Line Reversal): cuando el histograma MACD cruza el cero, Menendez
    # lo trata como señal de timing, no como condicion de bloqueo. Activar esto
    # permite el atractor H4 en el momento exacto del cruce aunque el histograma
    # estuviera en zona neutral el bar anterior.
    "use_zlr_as_macd_ok": True,
    # Numero de barras H4 durante las que el flag ZLR permanece activo tras el cruce.
    # 1 = solo el bar exacto del crossover. 3 = el cruce y los 2 bars H4 siguientes
    # (~24 barras M30), lo que da margen para que el setup W-X-entry se forme.
    "zlr_memory_bars": 3,
    # X compuesta: permite que X agrupe multiples segmentos PSAR.
    # Por defecto solo se admite ABC (3 segmentos). Las correcciones complejas
    # deben usar equivalentes correctivos 7/11/15 y activarse explicitamente
    # elevando composite_x_max_segments. Se excluye 5 porque pertenece a la
    # familia motora, no a la correccion X ordinaria.
    "use_composite_x": False,
    "composite_x_max_segments": 3,
    "composite_x_allowed_segment_counts": (3, 7, 11, 15),
    # Lateralidad H4: demasiados flips recientes del PSAR sugieren rango/chop.
    # Se calcula siempre como diagnostico, pero solo bloquea el atractor si una
    # variante experimental lo activa explicitamente.
    "use_h4_psar_lateral_filter": False,
    "psar_lateral_window_bars": 8,
    "psar_lateral_min_flips": 3,
}

DEFAULT_STRATEGIES = OrderedDict((
    ("menendez_core", {
        "entry_rule": "menendez_core",
        "risk_fraction": 1.0,
        "min_rr": 1.0,
    }),
))

DEFAULT_EXPERIMENT_CONTRACT = {
    "group_name": DEFAULT_GROUP,
    "timeframe_ltf": DEFAULT_TIMEFRAME_LTF,
    "timeframe_htf": DEFAULT_TIMEFRAME_HTF,
    "risk_per_trade": 0.01,
    "commission_model": "fpmarkets_raw_mt45",
    "account_currency": "USD",
    "use_cache": True,
    "use_disk_cache": True,
    "data_source": "SQL+MT5 metadata",
    "classification_valid": "resultado_valido",
    "classification_exploratory": "resultado_exploratorio",
    "classification_invalid": "resultado_no_defendible",
}

DEFAULT_VARIANT_SPECS = OrderedDict((
    ("faithful_strict", {
        "label": "Faithful Strict",
        "classification": "resultado_valido",
        "notes": "Referencia base mas fiel a la documentacion resumida; H4_STANDBY queda solo como diagnostico.",
        "context_overrides": {},
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("experimental_h4_standby_12", {
        "label": "Experimental - H4 Standby 12",
        "classification": "resultado_exploratorio",
        "notes": "Reintroduce el filtro de 12 barras H4 con MACD neutral como hipotesis operativa, no como regla fiel a la literatura.",
        "context_overrides": {
            "use_h4_standby_filter": True,
            "macd_standby_bars": 12,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_signal_window", {
        "label": "Faithful Operable - Signal Window",
        "classification": "resultado_valido",
        "notes": "Amplia solo la ventana de observacion del segmento gatillo.",
        "context_overrides": {
            "candidate_window_mode": "segment",
            "candidate_window_max_bars": 12,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_stoch_memory", {
        "label": "Faithful Operable - Stoch Memory",
        "classification": "resultado_valido",
        "notes": "Amplia solo la memoria del disparador estocastico.",
        "context_overrides": {
            "stoch_memory_bars": 5,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_macd_neutral", {
        "label": "Faithful Operable - MACD Neutral",
        "classification": "resultado_valido",
        "notes": "Relaja solo el umbral de neutralidad MACD.",
        "context_overrides": {
            "macd_neutral_threshold": 0.0008,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_fan_tolerance", {
        "label": "Faithful Operable - Fan Tolerance",
        "classification": "resultado_valido",
        "notes": "Anade solo una tolerancia minima al breakout del abanico.",
        "context_overrides": {
            "fan_breakout_tolerance": 0.00005,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_retrace_band", {
        "label": "Faithful Operable - Retrace Band",
        "classification": "resultado_valido",
        "notes": "Relaja solo la banda de retroceso manteniendo el resto.",
        "context_overrides": {
            "retracement_min": 0.35,
            "retracement_max": 0.65,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_min_rr", {
        "label": "Faithful Operable - Min RR",
        "classification": "resultado_valido",
        "notes": "Reduce solo el minimo de RR para diagnosticar el cierre del embudo.",
        "context_overrides": {},
        "strategy_overrides": {"menendez_core": {"min_rr": 0.9}},
    }),
    ("faithful_h4_sma200", {
        "label": "Faithful - H4 SMA200",
        "classification": "resultado_valido",
        "notes": "Mantiene el motor base pero usa SMA200 como filtro principal de tendencia madre en H4.",
        "context_overrides": {
            "h4_trend_filter": "sma200_position",
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_trigger_or", {
        "label": "Faithful Operable - Trigger OR",
        "classification": "resultado_valido",
        "notes": "Usa ruptura de abanico o flip PSAR como disparador primario, con confirmacion de momento por MACD o Stoch.",
        "context_overrides": {
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_trigger_or_macd_neutral", {
        "label": "Faithful Operable - Trigger OR + MACD Neutral",
        "classification": "resultado_valido",
        "notes": "Mantiene la variante principal y solo estrecha la zona neutral del MACD H4 para reducir bloqueos de contexto.",
        "context_overrides": {
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
            "macd_neutral_threshold": 0.0008,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_trigger_or_macd_memory", {
        "label": "Faithful Operable - Trigger OR + MACD Memory",
        "classification": "resultado_valido",
        "notes": "Mantiene la variante principal y da unas pocas velas de margen al disparo MACD M30 para evitar coincidencia excesivamente estricta en una sola barra.",
        "context_overrides": {
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
            "macd_memory_bars": 4,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_trigger_or_tp_no_bollinger", {
        "label": "Faithful Operable - Trigger OR + TP No Bollinger",
        "classification": "resultado_valido",
        "notes": "Mantiene la entrada principal y excluye Bollinger del clúster TP para comprobar si la salida está dominando indebidamente la estrategia.",
        "context_overrides": {
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
            "tp_include_bollinger": False,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_trigger_or_sessions", {
        "label": "Faithful Operable - Trigger OR + Sessions",
        "classification": "resultado_valido",
        "notes": "Mantiene la variante principal y solo permite entradas dentro de la ventana operativa principal para comprobar si mejora la calidad de las señales.",
        "context_overrides": {
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
            "session_filter_enabled": True,
            "session_start_hour_utc": 7,
            "session_end_hour_utc": 17,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("faithful_operable_trigger_or_sma200", {
        "label": "Faithful Operable - Trigger OR + SMA200",
        "classification": "resultado_valido",
        "notes": "Combina filtro de tendencia madre por SMA200 en H4 con gatillo M30 menos estricto.",
        "context_overrides": {
            "h4_trend_filter": "sma200_position",
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("exploratory_relaxed", {
        "label": "Exploratory Relaxed",
        "classification": "resultado_exploratorio",
        "notes": "Variante combinada para sensibilidad y aprendizaje, no principal.",
        "context_overrides": {
            "candidate_window_mode": "segment",
            "candidate_window_max_bars": 16,
            "stoch_memory_bars": 5,
            "macd_neutral_threshold": 0.0008,
            "h4_trend_filter": "sma200_position",
            "fan_breakout_tolerance": 0.00005,
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
            "retracement_min": 0.35,
            "retracement_max": 0.70,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 0.85}},
    }),
    ("faithful_operable_sma200_primary", {
        "label": "Faithful Operable - SMA200 Primary (MACD diagnostico)",
        "classification": "resultado_valido",
        "notes": (
            "SMA200 como unico filtro de tendencia madre en H4. MACD pasa a ser "
            "diagnostico: la literatura establece una jerarquia donde SMA200 es "
            "el filtro primario y MACD es "
            "confirmacion temporal, no condicion bloqueante del atractor."
        ),
        "context_overrides": {
            "h4_trend_filter": "sma200_primary",
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("experimental_composite_x", {
        "label": "Experimental - X Compuesta ABC",
        "classification": "resultado_exploratorio",
        "notes": (
            "Permite que X sea una estructura ABC de 3 segmentos PSAR. "
            "Separado de la logica simple para preservar auditabilidad. "
            "Combina con sma200_primary y trigger_or sin admitir 5 segmentos "
            "correctivos, porque 5 se reserva para equivalentes motores."
        ),
        "context_overrides": {
            "use_composite_x": True,
            "composite_x_max_segments": 3,
            "h4_trend_filter": "sma200_primary",
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
    ("experimental_sma200_primary_psar_lateral", {
        "label": "Experimental - SMA200 Primary + PSAR Lateral H4",
        "classification": "resultado_exploratorio",
        "notes": (
            "Mantiene la linea sma200_primary y bloquea el atractor H4 cuando el PSAR "
            "ha flipado demasiadas veces en una ventana corta, como proxy de lateralidad."
        ),
        "context_overrides": {
            "h4_trend_filter": "sma200_primary",
            "entry_primary_trigger_mode": "fan_or_psar",
            "entry_momentum_confirm_mode": "macd_or_stoch",
            "use_h4_psar_lateral_filter": True,
            "psar_lateral_window_bars": 8,
            "psar_lateral_min_flips": 3,
        },
        "strategy_overrides": {"menendez_core": {"min_rr": 1.0}},
    }),
))

DEFAULT_ACCOUNT_CONFIG = {
    "initial_capital": 10000.0,
    "risk_per_trade": 0.01,
    "skip_if_below_min_volume": True,
    "account_currency": "USD",
    "commission_model": "fpmarkets_raw_mt45",
}


def get_indicator_config(overrides=None):
    config = dict(DEFAULT_INDICATOR_CONFIG)
    if overrides:
        config.update(overrides)
    return config


def get_context_config(overrides=None):
    config = dict(DEFAULT_CONTEXT_CONFIG)
    if overrides:
        config.update(overrides)
    return config


def get_strategy_definitions(strategies=None):
    if strategies is None:
        return OrderedDict((name, deepcopy(config)) for name, config in DEFAULT_STRATEGIES.items())
    if isinstance(strategies, dict):
        return OrderedDict((name, deepcopy(config)) for name, config in strategies.items())
    if isinstance(strategies, (list, tuple)):
        if all(isinstance(item, str) for item in strategies):
            return OrderedDict(
                (name, deepcopy(DEFAULT_STRATEGIES[name]))
                for name in strategies
                if name in DEFAULT_STRATEGIES
            )
    return OrderedDict((name, deepcopy(config)) for name, config in strategies)


def get_account_config(account_config=None):
    config = dict(DEFAULT_ACCOUNT_CONFIG)
    if account_config:
        config.update(account_config)
    return config


def get_experiment_contract(contract_overrides=None):
    contract = dict(DEFAULT_EXPERIMENT_CONTRACT)
    if contract_overrides:
        contract.update(contract_overrides)
    return contract


def get_variant_specs(variant_names=None):
    if variant_names is None:
        return OrderedDict((name, deepcopy(spec)) for name, spec in DEFAULT_VARIANT_SPECS.items())
    if isinstance(variant_names, str):
        variant_names = [variant_names]
    return OrderedDict(
        (name, deepcopy(DEFAULT_VARIANT_SPECS[name]))
        for name in variant_names
        if name in DEFAULT_VARIANT_SPECS
    )

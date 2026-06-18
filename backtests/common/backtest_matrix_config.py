"""Canonical matrix configuration for strategy/backtest comparison runs."""

from collections import OrderedDict
from copy import deepcopy


DEFAULT_ASSET_GROUPS = ("Forex Majors", "Metals", "Index")

GROUP_ALIASES = {
    "Forex": "Forex Majors",
    "Forex Majors": "Forex Majors",
    "Metals": "Metals",
    "Metal": "Metals",
    "Index": "Index",
    "Indices": "Index",
}

TIMEFRAME_PAIRS = OrderedDict((
    ("M30", "H1"),
    ("H1", "H4"),
    ("H4", "D1"),
))

TIMEFRAME_FREQ = {
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
}

TEMPORAL_SPLITS = OrderedDict((
    ("2009-2012", (None, "2013-01-01")),
    ("2013-2015", ("2013-01-01", "2016-01-01")),
    ("2016-2018", ("2016-01-01", "2019-01-01")),
    ("2019-2021", ("2019-01-01", "2022-01-01")),
    ("2022-2024", ("2022-01-01", "2025-01-01")),
    ("2025-2026", ("2025-01-01", None)),
))

DEFAULT_STRATEGIES = OrderedDict((
    ("fib_limit", {
        "entry_rule": "fib_limit",
        "risk_fraction": 1.0,
        "tp_levels": (1.0, 1.618),
    }),
    ("macd_breakout", {
        "entry_rule": "macd_breakout",
        "risk_fraction": 1.0,
        "confirmation_memory_bars": 5,
        "tp_levels": (1.0, 1.618),
    }),
    ("combined_split", {
        "entry_rule": "combined_split",
        "risk_fraction": 1.0,
        "legs": (
            {"entry_rule": "fib_limit", "risk_fraction": 0.5, "tp_levels": (1.0, 1.618)},
            {
                "entry_rule": "macd_breakout",
                "risk_fraction": 0.5,
                "confirmation_memory_bars": 5,
                "tp_levels": (1.0, 1.618),
            },
        ),
    }),
))

DEFAULT_CONTEXT_CONFIG = {
    "trend_fast": 50,
    "trend_slow": 150,
    "trend_type": "wma",
    "zigzag_deviation": 0.005,
    "tolerance": 0.001,
}

DEFAULT_GROUP_CONTEXT_CONFIG = {
    "Forex Majors": {
        "zigzag_deviation": 0.005,
        "zigzag_mode": "expanding_atr_median",
        "zigzag_atr_multiplier": 2.5,
        "zigzag_min_periods": 200,
        "zigzag_shift_bars": 1,
        "zigzag_floor": 0.0035,
        "zigzag_ceiling": 0.0100,
    },
    "Metals": {
        "zigzag_deviation": 0.010,
        "zigzag_mode": "expanding_atr_median",
        "zigzag_atr_multiplier": 2.5,
        "zigzag_min_periods": 200,
        "zigzag_shift_bars": 1,
        "zigzag_floor": 0.006,
        "zigzag_ceiling": 0.012,
    },
    "Index": {
        "zigzag_deviation": 0.0075,
        "zigzag_mode": "expanding_atr_median",
        "zigzag_atr_multiplier": 2.5,
        "zigzag_min_periods": 200,
        "zigzag_shift_bars": 1,
        "zigzag_floor": 0.0050,
        "zigzag_ceiling": 0.0200,
    },
}

DEFAULT_STRATEGY_SETTINGS = {
    "entry_level": 0.618,
    "entry_zone_lo": 0.5,
    "entry_zone_hi": 0.618,
    "valid_retrace_max": 0.8,
}

DEFAULT_ACCOUNT_CONFIG = {
    "initial_capital": 10000.0,
    "risk_per_trade": 0.01,
    "skip_if_below_min_volume": True,
    "account_currency": "USD",
    "commission_model": "fpmarkets_raw_mt45",
}


def normalize_group_name(group_name):
    """Map user-facing group aliases to canonical group names."""
    if group_name is None:
        return None
    return GROUP_ALIASES.get(group_name, group_name)


def get_selected_groups(groups=None):
    """Return normalized asset groups for a benchmark run."""
    groups = groups or DEFAULT_ASSET_GROUPS
    return tuple(normalize_group_name(group) for group in groups)


def get_timeframe_pairs(tf_pairs=None):
    """Return ordered LTF->HTF pairs, preserving caller order when provided."""
    if tf_pairs is None:
        return TIMEFRAME_PAIRS.copy()
    if isinstance(tf_pairs, dict):
        return OrderedDict(tf_pairs.items())
    return OrderedDict(tf_pairs)


def _clone_strategy_definitions(strategy_map):
    return OrderedDict(
        (name, deepcopy(config))
        for name, config in strategy_map.items()
    )


def get_strategy_definitions(strategies=None):
    """Return deep-copied strategy definitions to avoid caller side effects."""
    if strategies is None:
        return _clone_strategy_definitions(DEFAULT_STRATEGIES)
    if isinstance(strategies, dict):
        return _clone_strategy_definitions(OrderedDict(strategies.items()))
    if isinstance(strategies, (list, tuple)):
        if all(isinstance(item, str) for item in strategies):
            return _clone_strategy_definitions(OrderedDict(
                (name, DEFAULT_STRATEGIES[name])
                for name in strategies
                if name in DEFAULT_STRATEGIES
            ))
    return _clone_strategy_definitions(OrderedDict(strategies))


def get_account_config(account_config=None):
    """Return account/risk config with caller overrides applied."""
    config = DEFAULT_ACCOUNT_CONFIG.copy()
    if account_config:
        config.update(account_config)
    return config


def get_context_config(group_name=None, timeframe_ltf=None, context_config=None):
    """Return group-aware context config with explicit overrides last."""
    config = DEFAULT_CONTEXT_CONFIG.copy()
    normalized_group = normalize_group_name(group_name)

    # Fixed group overrides first. We keep timeframe reserved in the signature so
    # we can extend this cleanly to group+timeframe later without touching callers.
    if normalized_group in DEFAULT_GROUP_CONTEXT_CONFIG:
        config.update(DEFAULT_GROUP_CONTEXT_CONFIG[normalized_group])

    # Explicit caller overrides always win.
    if context_config:
        config.update(context_config)

    return config

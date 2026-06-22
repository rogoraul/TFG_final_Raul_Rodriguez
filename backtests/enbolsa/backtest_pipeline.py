"""
Pipeline multi-timeframe para setups formalizados.

Motor de backtest sin look-ahead para:
  - fib_limit
  - macd_breakout
  - combined_split
"""

from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when numba is unavailable
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def _decorator(func):
            return func
        return _decorator

from backtests.enbolsa.backtest_loader import cargar_portfolios_matriz
from backtests.common.backtest_matrix_config import (
    DEFAULT_STRATEGIES,
    TEMPORAL_SPLITS,
    TIMEFRAME_FREQ,
    get_account_config,
    get_strategy_definitions,
    get_timeframe_pairs,
)
from backtests.common.position_sizing import (
    SYMBOL_SPEC_COLUMN_MAP,
    apply_risk_position_sizing,
)
from backtests.enbolsa.swing_quality import (
    QUALITY_GATE_VERSION,
    evaluate_swing_quality_row,
)


SYMBOL_SPEC_COLUMNS = tuple(SYMBOL_SPEC_COLUMN_MAP.values())
TRADE_SETUP_COLUMNS = (
    'W1_START_PRICE',
    'W1_END_PRICE',
    'W1_SIZE',
    'W1_BARS',
    'W2_EXTREME_PRICE',
    'W2_RETR_PCT',
    'W2_SWING_PRICE',
    'FIB_LEVEL_0.5',
    'FIB_LEVEL_0.618',
    'FIB_LEVEL_0.8',
    'TARGET_1.0',
    'TARGET_1.618',
    'SWING_QUALITY_PASS',
    'SWING_QUALITY_REASON',
    'W1_QUALITY_STATUS',
    'W2_QUALITY_STATUS',
    'W1_ATR_MULTIPLE',
    'W1_PRICE_PCT',
    'QUALITY_GATE_VERSION',
)


def _trend_col(timeframe_htf):
    return f'TENDENCIA_ESTRUCTURAL_{timeframe_htf}'


def _freq_from_timeframe(timeframe_ltf):
    return TIMEFRAME_FREQ.get(timeframe_ltf, '1h')


def _safe_float(value):
    if pd.isna(value):
        return np.nan
    return float(value)


def _strategy_legs(strategy_name, config):
    if config.get('entry_rule') == 'combined_split':
        legs = []
        for subleg in config.get('legs', ()):
            tp_levels = subleg.get('tp_levels', (1.0, 1.618))
            leg_risk = subleg.get('risk_fraction', 0.5)
            confirmation_memory_bars = int(subleg.get('confirmation_memory_bars', 1))
            micro_size = leg_risk / len(tp_levels)
            for tp_mult in tp_levels:
                legs.append({
                    'strategy_name': strategy_name,
                    'entry_rule': subleg['entry_rule'],
                    'confirmation_memory_bars': confirmation_memory_bars,
                    'tp_mult': tp_mult,
                    'size_fraction': micro_size,
                    'swing_quality_gate_enabled': bool(subleg.get('swing_quality_gate_enabled', config.get('swing_quality_gate_enabled', False))),
                })
        return legs

    tp_levels = config.get('tp_levels', (1.0, 1.618))
    risk_fraction = config.get('risk_fraction', 1.0)
    confirmation_memory_bars = int(config.get('confirmation_memory_bars', 1))
    micro_size = risk_fraction / len(tp_levels)
    return [{
        'strategy_name': strategy_name,
        'entry_rule': config['entry_rule'],
        'confirmation_memory_bars': confirmation_memory_bars,
        'tp_mult': tp_mult,
        'size_fraction': micro_size,
        'swing_quality_gate_enabled': bool(config.get('swing_quality_gate_enabled', False)),
    } for tp_mult in tp_levels]


def _row_setup_snapshot(row, direction):
    prefix = 'LONG' if direction == 1 else 'SHORT'
    return {
        'setup_id': int(row.get(f'{prefix}_SETUP_ID', 0) or 0),
        'setup_active': bool(row.get(f'{prefix}_SETUP_ACTIVE', False)),
        'setup_age': int(row.get(f'{prefix}_SETUP_AGE', 0) or 0),
        'w1_start': _safe_float(row.get(f'{prefix}_W1_START_PRICE')),
        'w1_end': _safe_float(row.get(f'{prefix}_W1_END_PRICE')),
        'w1_size': _safe_float(row.get(f'{prefix}_W1_SIZE')),
        'w1_bars': int(row.get(f'{prefix}_W1_BARS', 0) or 0),
        'w2_extreme': _safe_float(row.get(f'{prefix}_W2_EXTREME_PRICE')),
        'w2_retr_pct': _safe_float(row.get(f'{prefix}_W2_RETR_PCT')),
        'w2_swing': _safe_float(row.get(f'{prefix}_W2_SWING_PRICE')),
        'valid_80': bool(row.get(f'{prefix}_W2_VALID_80', False)),
        'invalidated': bool(row.get(f'{prefix}_W2_INVALIDATED', False)),
        'fib_50': _safe_float(row.get(f'{prefix}_FIB_LEVEL_0.5')),
        'fib_618': _safe_float(row.get(f'{prefix}_FIB_LEVEL_0.618')),
        'fib_80': _safe_float(row.get(f'{prefix}_FIB_LEVEL_0.8')),
        'fib_touch_618': bool(row.get(f'{prefix}_FIB_TOUCH_618', False)),
        'trendline_broken': bool(row.get(f'{prefix}_W2_TRENDLINE_BROKEN', False)),
        'target_1_0': _safe_float(row.get(f'{prefix}_TARGET_1.0')),
        'target_1_618': _safe_float(row.get(f'{prefix}_TARGET_1.618')),
        'spread_price': _safe_float(row.get('spread_price', 0.0)),
        'atr': _safe_float(row.get('ATR')),
    }


def _entry_signal(row, direction, entry_rule, trend_col, swing_quality_gate_enabled=False):
    trend_value = row.get(trend_col, np.nan)
    if pd.isna(trend_value) or int(trend_value) != direction:
        return False

    snapshot = _row_setup_snapshot(row, direction)
    if not snapshot['setup_active'] or snapshot['setup_id'] == 0:
        return False
    if snapshot['invalidated']:
        return False
    if swing_quality_gate_enabled and not evaluate_swing_quality_row(row, direction)['swing_quality_pass']:
        return False

    if entry_rule == 'fib_limit':
        fib_level = snapshot['fib_618']
        spread_price = snapshot['spread_price']
        if pd.isna(fib_level):
            return False

        if direction == 1:
            bid_low = _safe_float(row.get('low'))
            if pd.isna(bid_low):
                return False
            fib_touched = (bid_low + spread_price) <= fib_level
        else:
            bid_high = _safe_float(row.get('high'))
            if pd.isna(bid_high):
                return False
            fib_touched = bid_high >= fib_level

        return (
            snapshot['setup_age'] >= 1 and
            snapshot['valid_80'] and
            fib_touched
        )

    return False


def _macd_breakout_signal_from_arrays(arrays, row_pos, direction, memory_bars):
    if direction == 1:
        trend_match = arrays['trend'][row_pos] == 1
        setup_id = arrays['long_setup_id'][row_pos]
        setup_active = arrays['long_setup_active'][row_pos]
        invalidated = arrays['long_invalidated'][row_pos]
        w2_swing = arrays['long_w2_swing'][row_pos]
        setup_ids = arrays['long_setup_id']
        invalidated_series = arrays['long_invalidated']
        trendline_broken = arrays['long_trendline_broken']
        macd_cross = arrays['macd_long']
    else:
        trend_match = arrays['trend'][row_pos] == -1
        setup_id = arrays['short_setup_id'][row_pos]
        setup_active = arrays['short_setup_active'][row_pos]
        invalidated = arrays['short_invalidated'][row_pos]
        w2_swing = arrays['short_w2_swing'][row_pos]
        setup_ids = arrays['short_setup_id']
        invalidated_series = arrays['short_invalidated']
        trendline_broken = arrays['short_trendline_broken']
        macd_cross = arrays['macd_short']

    if (not trend_match) or (not setup_active) or setup_id == 0 or invalidated or pd.isna(w2_swing):
        return False

    start = max(0, row_pos - max(int(memory_bars), 1) + 1)
    hist_setup_ids = setup_ids[start:row_pos + 1]
    mask = hist_setup_ids == setup_id
    if not np.any(mask):
        return False

    recent_invalidated = bool(np.any(invalidated_series[start:row_pos + 1][mask]))
    if recent_invalidated:
        return False

    recent_break = bool(np.any(trendline_broken[start:row_pos + 1][mask]))
    recent_macd = bool(np.any(macd_cross[start:row_pos + 1][mask]))
    return recent_break and recent_macd


def _make_position(symbol, timestamp, row, direction, leg_spec):
    snapshot = _row_setup_snapshot(row, direction)
    quality = evaluate_swing_quality_row(row, direction) if leg_spec.get('swing_quality_gate_enabled') else None
    tp_col = 'target_1_0' if abs(leg_spec['tp_mult'] - 1.0) < 1e-9 else 'target_1_618'
    spread_price = 0.0 if pd.isna(snapshot['spread_price']) else float(snapshot['spread_price'])
    symbol_spec = {
        column_name: row.get(column_name, np.nan)
        for column_name in SYMBOL_SPEC_COLUMNS
    }

    if leg_spec['entry_rule'] == 'fib_limit':
        entry_price = snapshot['fib_618']
        stop_price = snapshot['w1_start']
        dynamic_target = True
        target_price = snapshot[tp_col]
    else:
        entry_price = _safe_float(row['close'])
        stop_price = snapshot['w2_swing'] if pd.notna(snapshot['w2_swing']) else snapshot['w1_start']
        dynamic_target = False
        target_price = snapshot[tp_col]

    if direction == 1 and leg_spec['entry_rule'] != 'fib_limit':
        entry_price += spread_price

    if pd.isna(entry_price) or pd.isna(stop_price) or pd.isna(target_price):
        return None
    if direction == 1 and stop_price >= entry_price:
        return None
    if direction == -1 and stop_price <= entry_price:
        return None

    prefix = 'LONG' if direction == 1 else 'SHORT'
    return {
        'symbol': symbol,
        'strategy': leg_spec['strategy_name'],
        'entry_rule': leg_spec['entry_rule'],
        'tp_mult': leg_spec['tp_mult'],
        'size_fraction': leg_spec['size_fraction'],
        'direction': direction,
        'setup_id': snapshot['setup_id'],
        'setup_prefix': prefix,
        'entry_time': timestamp,
        'entry_price': float(entry_price),
        'stop_price': float(stop_price),
        'target_price': float(target_price),
        'dynamic_target': dynamic_target,
        'active_from_pos': None,
        'W1_START_PRICE': snapshot['w1_start'],
        'W1_END_PRICE': snapshot['w1_end'],
        'W1_SIZE': snapshot['w1_size'],
        'W1_BARS': snapshot['w1_bars'],
        'W2_EXTREME_PRICE': snapshot['w2_extreme'],
        'W2_RETR_PCT': snapshot['w2_retr_pct'],
        'W2_SWING_PRICE': snapshot['w2_swing'],
        'FIB_LEVEL_0.5': snapshot['fib_50'],
        'FIB_LEVEL_0.618': snapshot['fib_618'],
        'FIB_LEVEL_0.8': snapshot['fib_80'],
        'TARGET_1.0': snapshot['target_1_0'],
        'TARGET_1.618': snapshot['target_1_618'],
        'SWING_QUALITY_PASS': quality['swing_quality_pass'] if quality else np.nan,
        'SWING_QUALITY_REASON': quality['swing_quality_reason'] if quality else '',
        'W1_QUALITY_STATUS': quality['w1_quality_status'] if quality else '',
        'W2_QUALITY_STATUS': quality['w2_quality_status'] if quality else '',
        'W1_ATR_MULTIPLE': quality['w1_atr_multiple'] if quality else np.nan,
        'W1_PRICE_PCT': quality['w1_price_pct'] if quality else np.nan,
        'QUALITY_GATE_VERSION': quality['quality_gate_version'] if quality else '',
        **symbol_spec,
    }


def _update_dynamic_targets(position, row):
    if not position['dynamic_target']:
        return

    setup_id_col = f"{position['setup_prefix']}_SETUP_ID"
    if int(row.get(setup_id_col, 0) or 0) != position['setup_id']:
        return

    if abs(position['tp_mult'] - 1.0) < 1e-9:
        target_col = f"{position['setup_prefix']}_TARGET_1.0"
    else:
        target_col = f"{position['setup_prefix']}_TARGET_1.618"

    target_price = _safe_float(row.get(target_col))
    if pd.notna(target_price):
        position['target_price'] = float(target_price)


def _close_position(position, timestamp, exit_price, exit_reason, exit_spread=0.0):
    if pd.isna(exit_spread):
        exit_spread = 0.0
    net_exit_price = exit_price + exit_spread if position['direction'] == -1 else exit_price
    raw_return = position['direction'] * ((net_exit_price - position['entry_price']) / position['entry_price'])
    weighted_return = raw_return * position['size_fraction']
    closed = {
        'symbol': position['symbol'],
        'strategy': position['strategy'],
        'entry_rule': position['entry_rule'],
        'direction': position['direction'],
        'setup_id': position['setup_id'],
        'tp_mult': position['tp_mult'],
        'size_fraction': position['size_fraction'],
        'entry_time': position['entry_time'],
        'exit_time': timestamp,
        'entry_price': position['entry_price'],
        'stop_price': position['stop_price'],
        'exit_price': net_exit_price,
        'exit_reason': exit_reason,
        'return_pct': raw_return * 100.0,
        'weighted_return': weighted_return,
        'pnl': weighted_return,
    }
    for column_name in TRADE_SETUP_COLUMNS:
        closed[column_name] = position.get(column_name, np.nan)
    for column_name in SYMBOL_SPEC_COLUMNS:
        closed[column_name] = position.get(column_name, np.nan)
    return closed


def _series_to_float_array(df, column_name, default=np.nan):
    if column_name not in df.columns:
        return np.full(len(df), default, dtype=np.float64)
    return pd.to_numeric(df[column_name], errors='coerce').to_numpy(dtype=np.float64, copy=False)


def _series_to_int_array(df, column_name, default=0):
    if column_name not in df.columns:
        return np.full(len(df), default, dtype=np.int64)
    return df[column_name].fillna(default).astype(np.int64).to_numpy(copy=False)


def _series_to_bool_array(df, column_name):
    if column_name not in df.columns:
        return np.zeros(len(df), dtype=np.bool_)
    return df[column_name].fillna(False).astype(bool).to_numpy(copy=False)


def _prepare_symbol_arrays(df, timeframe_htf):
    trend_col = _trend_col(timeframe_htf)
    arrays = {
        'low': _series_to_float_array(df, 'low'),
        'high': _series_to_float_array(df, 'high'),
        'close': _series_to_float_array(df, 'close'),
        'spread_price': _series_to_float_array(df, 'spread_price', default=0.0),
        'trend': _series_to_int_array(df, trend_col),
        'macd_long': _series_to_bool_array(df, 'MACD_CROSS_LONG'),
        'macd_short': _series_to_bool_array(df, 'MACD_CROSS_SHORT'),
        'long_setup_id': _series_to_int_array(df, 'LONG_SETUP_ID'),
        'long_setup_active': _series_to_bool_array(df, 'LONG_SETUP_ACTIVE'),
        'long_setup_age': _series_to_int_array(df, 'LONG_SETUP_AGE'),
        'long_w1_start': _series_to_float_array(df, 'LONG_W1_START_PRICE'),
        'long_w2_swing': _series_to_float_array(df, 'LONG_W2_SWING_PRICE'),
        'long_valid_80': _series_to_bool_array(df, 'LONG_W2_VALID_80'),
        'long_invalidated': _series_to_bool_array(df, 'LONG_W2_INVALIDATED'),
        'long_fib_618': _series_to_float_array(df, 'LONG_FIB_LEVEL_0.618'),
        'long_fib_touch': _series_to_bool_array(df, 'LONG_FIB_TOUCH_618'),
        'long_trendline_broken': _series_to_bool_array(df, 'LONG_W2_TRENDLINE_BROKEN'),
        'long_target_1_0': _series_to_float_array(df, 'LONG_TARGET_1.0'),
        'long_target_1_618': _series_to_float_array(df, 'LONG_TARGET_1.618'),
        'short_setup_id': _series_to_int_array(df, 'SHORT_SETUP_ID'),
        'short_setup_active': _series_to_bool_array(df, 'SHORT_SETUP_ACTIVE'),
        'short_setup_age': _series_to_int_array(df, 'SHORT_SETUP_AGE'),
        'short_w1_start': _series_to_float_array(df, 'SHORT_W1_START_PRICE'),
        'short_w2_swing': _series_to_float_array(df, 'SHORT_W2_SWING_PRICE'),
        'short_valid_80': _series_to_bool_array(df, 'SHORT_W2_VALID_80'),
        'short_invalidated': _series_to_bool_array(df, 'SHORT_W2_INVALIDATED'),
        'short_fib_618': _series_to_float_array(df, 'SHORT_FIB_LEVEL_0.618'),
        'short_fib_touch': _series_to_bool_array(df, 'SHORT_FIB_TOUCH_618'),
        'short_trendline_broken': _series_to_bool_array(df, 'SHORT_W2_TRENDLINE_BROKEN'),
        'short_target_1_0': _series_to_float_array(df, 'SHORT_TARGET_1.0'),
        'short_target_1_618': _series_to_float_array(df, 'SHORT_TARGET_1.618'),
    }
    return arrays


def _encode_legs(legs):
    leg_entry_rules = []
    leg_memory_bars = []
    leg_tp_codes = []
    leg_sizes = []

    for leg in legs:
        leg_entry_rules.append(1 if leg['entry_rule'] == 'fib_limit' else 2)
        leg_memory_bars.append(int(leg.get('confirmation_memory_bars', 1)))
        leg_tp_codes.append(0 if abs(leg['tp_mult'] - 1.0) < 1e-9 else 1)
        leg_sizes.append(float(leg['size_fraction']))

    return (
        np.asarray(leg_entry_rules, dtype=np.int64),
        np.asarray(leg_memory_bars, dtype=np.int64),
        np.asarray(leg_tp_codes, dtype=np.int64),
        np.asarray(leg_sizes, dtype=np.float64),
    )


@njit(cache=True)
def _simulate_symbol_core(
    low,
    high,
    close,
    spread_price,
    trend,
    macd_long,
    macd_short,
    long_setup_id,
    long_setup_active,
    long_setup_age,
    long_w1_start,
    long_w2_swing,
    long_valid_80,
    long_invalidated,
    long_fib_618,
    long_fib_touch,
    long_trendline_broken,
    long_target_1_0,
    long_target_1_618,
    short_setup_id,
    short_setup_active,
    short_setup_age,
    short_w1_start,
    short_w2_swing,
    short_valid_80,
    short_invalidated,
    short_fib_618,
    short_fib_touch,
    short_trendline_broken,
    short_target_1_0,
    short_target_1_618,
    leg_entry_rules,
    leg_memory_bars,
    leg_tp_codes,
    leg_sizes,
):
    n = len(close)
    leg_count = len(leg_entry_rules)
    max_positions = max(16, leg_count * 4)
    max_records = max(1, n * max(8, leg_count * 2))

    pos_active = np.zeros(max_positions, dtype=np.bool_)
    pos_direction = np.zeros(max_positions, dtype=np.int64)
    pos_entry_rule = np.zeros(max_positions, dtype=np.int64)
    pos_tp_code = np.zeros(max_positions, dtype=np.int64)
    pos_setup_id = np.zeros(max_positions, dtype=np.int64)
    pos_size_fraction = np.zeros(max_positions, dtype=np.float64)
    pos_entry_idx = np.zeros(max_positions, dtype=np.int64)
    pos_entry_price = np.zeros(max_positions, dtype=np.float64)
    pos_stop_price = np.zeros(max_positions, dtype=np.float64)
    pos_target_price = np.zeros(max_positions, dtype=np.float64)
    pos_dynamic_target = np.zeros(max_positions, dtype=np.bool_)
    pos_active_from = np.zeros(max_positions, dtype=np.int64)

    rec_entry_idx = np.zeros(max_records, dtype=np.int64)
    rec_exit_idx = np.zeros(max_records, dtype=np.int64)
    rec_direction = np.zeros(max_records, dtype=np.int64)
    rec_setup_id = np.zeros(max_records, dtype=np.int64)
    rec_entry_rule = np.zeros(max_records, dtype=np.int64)
    rec_tp_code = np.zeros(max_records, dtype=np.int64)
    rec_size_fraction = np.zeros(max_records, dtype=np.float64)
    rec_entry_price = np.zeros(max_records, dtype=np.float64)
    rec_stop_price = np.zeros(max_records, dtype=np.float64)
    rec_exit_price = np.zeros(max_records, dtype=np.float64)
    rec_exit_reason = np.zeros(max_records, dtype=np.int64)

    used_rule = np.zeros(max_records, dtype=np.int64)
    used_direction = np.zeros(max_records, dtype=np.int64)
    used_setup = np.zeros(max_records, dtype=np.int64)
    used_count = 0
    record_count = 0

    for row_pos in range(n):
        row_low = low[row_pos]
        row_high = high[row_pos]
        row_close = close[row_pos]
        row_spread = spread_price[row_pos]

        for pos_idx in range(max_positions):
            if not pos_active[pos_idx]:
                continue
            if row_pos < pos_active_from[pos_idx]:
                continue

            stop_hit = False
            target_hit = False

            if pos_direction[pos_idx] == 1:
                stop_hit = row_low <= pos_stop_price[pos_idx]
                target_hit = row_high >= pos_target_price[pos_idx]
            else:
                stop_hit = (row_high + row_spread) >= pos_stop_price[pos_idx]
                target_hit = (row_low + row_spread) <= pos_target_price[pos_idx]

            if stop_hit or target_hit:
                rec_entry_idx[record_count] = pos_entry_idx[pos_idx]
                rec_exit_idx[record_count] = row_pos
                rec_direction[record_count] = pos_direction[pos_idx]
                rec_setup_id[record_count] = pos_setup_id[pos_idx]
                rec_entry_rule[record_count] = pos_entry_rule[pos_idx]
                rec_tp_code[record_count] = pos_tp_code[pos_idx]
                rec_size_fraction[record_count] = pos_size_fraction[pos_idx]
                rec_entry_price[record_count] = pos_entry_price[pos_idx]
                rec_stop_price[record_count] = pos_stop_price[pos_idx]
                rec_exit_price[record_count] = (
                    (pos_stop_price[pos_idx] if stop_hit else pos_target_price[pos_idx])
                )
                rec_exit_reason[record_count] = 0 if stop_hit else 1
                record_count += 1
                pos_active[pos_idx] = False

        for direction in (1, -1):
            for entry_rule_code in (1, 2):
                same_open = False
                for pos_idx in range(max_positions):
                    if (
                        pos_active[pos_idx] and
                        pos_direction[pos_idx] == direction and
                        pos_entry_rule[pos_idx] == entry_rule_code
                    ):
                        same_open = True
                        break
                if same_open:
                    continue

                if direction == 1:
                    trend_match = trend[row_pos] == 1
                    setup_id = long_setup_id[row_pos]
                    setup_active = long_setup_active[row_pos]
                    setup_age = long_setup_age[row_pos]
                    invalidated = long_invalidated[row_pos]
                    valid_80 = long_valid_80[row_pos]
                    fib_touch = long_fib_touch[row_pos]
                    trendline_broken = long_trendline_broken[row_pos]
                    macd_cross = macd_long[row_pos]
                    w2_swing = long_w2_swing[row_pos]
                else:
                    trend_match = trend[row_pos] == -1
                    setup_id = short_setup_id[row_pos]
                    setup_active = short_setup_active[row_pos]
                    setup_age = short_setup_age[row_pos]
                    invalidated = short_invalidated[row_pos]
                    valid_80 = short_valid_80[row_pos]
                    fib_touch = short_fib_touch[row_pos]
                    trendline_broken = short_trendline_broken[row_pos]
                    macd_cross = macd_short[row_pos]
                    w2_swing = short_w2_swing[row_pos]

                if (not trend_match) or (not setup_active) or setup_id == 0 or invalidated:
                    continue

                entry_ok = False
                if entry_rule_code == 1:
                    if direction == 1:
                        entry_ok = (
                            (setup_age >= 1) and
                            valid_80 and
                            (not np.isnan(long_fib_618[row_pos])) and
                            ((row_low + row_spread) <= long_fib_618[row_pos])
                        )
                    else:
                        entry_ok = (
                            (setup_age >= 1) and
                            valid_80 and
                            (not np.isnan(short_fib_618[row_pos])) and
                            (row_high >= short_fib_618[row_pos])
                        )
                else:
                    memory_bars = 1
                    for leg_idx in range(leg_count):
                        if leg_entry_rules[leg_idx] == entry_rule_code and leg_memory_bars[leg_idx] > memory_bars:
                            memory_bars = leg_memory_bars[leg_idx]

                    start = row_pos - memory_bars + 1
                    if start < 0:
                        start = 0
                    recent_break = False
                    recent_macd = False
                    recent_invalidated = False
                    for hist_pos in range(start, row_pos + 1):
                        if direction == 1:
                            if long_setup_id[hist_pos] != setup_id:
                                continue
                            if long_invalidated[hist_pos]:
                                recent_invalidated = True
                            if long_trendline_broken[hist_pos]:
                                recent_break = True
                            if macd_long[hist_pos]:
                                recent_macd = True
                        else:
                            if short_setup_id[hist_pos] != setup_id:
                                continue
                            if short_invalidated[hist_pos]:
                                recent_invalidated = True
                            if short_trendline_broken[hist_pos]:
                                recent_break = True
                            if macd_short[hist_pos]:
                                recent_macd = True

                    entry_ok = (not recent_invalidated) and recent_break and recent_macd and (not np.isnan(w2_swing))
                if not entry_ok:
                    continue

                already_used = False
                for used_idx in range(used_count):
                    if (
                        used_rule[used_idx] == entry_rule_code and
                        used_direction[used_idx] == direction and
                        used_setup[used_idx] == setup_id
                    ):
                        already_used = True
                        break
                if already_used:
                    continue

                opened_any = False
                for leg_idx in range(leg_count):
                    if leg_entry_rules[leg_idx] != entry_rule_code:
                        continue

                    if direction == 1:
                        if entry_rule_code == 1:
                            entry_price = long_fib_618[row_pos]
                            stop_price = long_w1_start[row_pos]
                            target_price = long_target_1_0[row_pos] if leg_tp_codes[leg_idx] == 0 else long_target_1_618[row_pos]
                            dynamic_target = True
                        else:
                            entry_price = row_close + row_spread
                            stop_price = long_w2_swing[row_pos] if not np.isnan(long_w2_swing[row_pos]) else long_w1_start[row_pos]
                            target_price = long_target_1_0[row_pos] if leg_tp_codes[leg_idx] == 0 else long_target_1_618[row_pos]
                            dynamic_target = False
                    else:
                        if entry_rule_code == 1:
                            entry_price = short_fib_618[row_pos]
                            stop_price = short_w1_start[row_pos]
                            target_price = short_target_1_0[row_pos] if leg_tp_codes[leg_idx] == 0 else short_target_1_618[row_pos]
                            dynamic_target = True
                        else:
                            entry_price = row_close
                            stop_price = short_w2_swing[row_pos] if not np.isnan(short_w2_swing[row_pos]) else short_w1_start[row_pos]
                            target_price = short_target_1_0[row_pos] if leg_tp_codes[leg_idx] == 0 else short_target_1_618[row_pos]
                            dynamic_target = False

                    if np.isnan(entry_price) or np.isnan(stop_price) or np.isnan(target_price):
                        continue
                    if direction == 1 and stop_price >= entry_price:
                        continue
                    if direction == -1 and stop_price <= entry_price:
                        continue

                    slot = -1
                    for pos_idx in range(max_positions):
                        if not pos_active[pos_idx]:
                            slot = pos_idx
                            break
                    if slot == -1:
                        continue

                    pos_active[slot] = True
                    pos_direction[slot] = direction
                    pos_entry_rule[slot] = entry_rule_code
                    pos_tp_code[slot] = leg_tp_codes[leg_idx]
                    pos_setup_id[slot] = setup_id
                    pos_size_fraction[slot] = leg_sizes[leg_idx]
                    pos_entry_idx[slot] = row_pos
                    pos_entry_price[slot] = entry_price
                    pos_stop_price[slot] = stop_price
                    pos_target_price[slot] = target_price
                    pos_dynamic_target[slot] = dynamic_target
                    pos_active_from[slot] = row_pos + 1
                    opened_any = True

                if opened_any:
                    used_rule[used_count] = entry_rule_code
                    used_direction[used_count] = direction
                    used_setup[used_count] = setup_id
                    used_count += 1

        for pos_idx in range(max_positions):
            if not pos_active[pos_idx] or not pos_dynamic_target[pos_idx]:
                continue

            if pos_direction[pos_idx] == 1 and long_setup_id[row_pos] == pos_setup_id[pos_idx]:
                pos_target_price[pos_idx] = (
                    long_target_1_0[row_pos] if pos_tp_code[pos_idx] == 0 else long_target_1_618[row_pos]
                )
            elif pos_direction[pos_idx] == -1 and short_setup_id[row_pos] == pos_setup_id[pos_idx]:
                pos_target_price[pos_idx] = (
                    short_target_1_0[row_pos] if pos_tp_code[pos_idx] == 0 else short_target_1_618[row_pos]
                )

    if n > 0:
        last_idx = n - 1
        last_close = close[last_idx]
        for pos_idx in range(max_positions):
            if not pos_active[pos_idx]:
                continue

            rec_entry_idx[record_count] = pos_entry_idx[pos_idx]
            rec_exit_idx[record_count] = last_idx
            rec_direction[record_count] = pos_direction[pos_idx]
            rec_setup_id[record_count] = pos_setup_id[pos_idx]
            rec_entry_rule[record_count] = pos_entry_rule[pos_idx]
            rec_tp_code[record_count] = pos_tp_code[pos_idx]
            rec_size_fraction[record_count] = pos_size_fraction[pos_idx]
            rec_entry_price[record_count] = pos_entry_price[pos_idx]
            rec_stop_price[record_count] = pos_stop_price[pos_idx]
            rec_exit_price[record_count] = last_close + (spread_price[last_idx] if pos_direction[pos_idx] == -1 else 0.0)
            rec_exit_reason[record_count] = 2
            record_count += 1

    return (
        record_count,
        rec_entry_idx[:record_count],
        rec_exit_idx[:record_count],
        rec_direction[:record_count],
        rec_setup_id[:record_count],
        rec_entry_rule[:record_count],
        rec_tp_code[:record_count],
        rec_size_fraction[:record_count],
        rec_entry_price[:record_count],
        rec_stop_price[:record_count],
        rec_exit_price[:record_count],
        rec_exit_reason[:record_count],
    )


def _simular_estrategia_en_symbol_python(
    symbol,
    df,
    strategy_name,
    strategy_config,
    timeframe_ltf,
    timeframe_htf,
):
    if not df.index.is_monotonic_increasing:
        df = df.sort_index()
    trend_col = _trend_col(timeframe_htf)
    legs = _strategy_legs(strategy_name, strategy_config)
    arrays = _prepare_symbol_arrays(df, timeframe_htf)

    open_positions = []
    closed_positions = []
    used_setups = set()

    for row_pos, (timestamp, row) in enumerate(df.iterrows()):
        row_spread = _safe_float(row.get('spread_price', 0.0))
        if pd.isna(row_spread):
            row_spread = 0.0
        survivors = []
        for position in open_positions:
            if row_pos >= position['active_from_pos']:
                stop_hit = False
                target_hit = False

                if position['direction'] == 1:
                    stop_hit = row['low'] <= position['stop_price']
                    target_hit = row['high'] >= position['target_price']
                else:
                    stop_hit = (row['high'] + row_spread) >= position['stop_price']
                    target_hit = (row['low'] + row_spread) <= position['target_price']

                if stop_hit:
                    closed_positions.append(
                        _close_position(position, timestamp, position['stop_price'], 'SL')
                    )
                    continue
                if target_hit:
                    closed_positions.append(
                        _close_position(position, timestamp, position['target_price'], 'TP')
                    )
                    continue

            survivors.append(position)

        open_positions = survivors

        for direction in (1, -1):
            for entry_rule in ('fib_limit', 'macd_breakout'):
                if any(
                    pos['direction'] == direction and pos['entry_rule'] == entry_rule
                    for pos in open_positions
                ):
                    continue

                matching_legs = [
                    leg for leg in legs
                    if leg['entry_rule'] == entry_rule
                ]
                if not matching_legs:
                    continue

                if entry_rule == 'fib_limit':
                    entry_ok = _entry_signal(
                        row,
                        direction,
                        entry_rule,
                        trend_col,
                        swing_quality_gate_enabled=any(leg.get('swing_quality_gate_enabled') for leg in matching_legs),
                    )
                else:
                    memory_bars = max(
                        int(leg.get('confirmation_memory_bars', 1))
                        for leg in matching_legs
                    )
                    entry_ok = _macd_breakout_signal_from_arrays(
                        arrays,
                        row_pos,
                        direction,
                        memory_bars,
                    )
                    if entry_ok and any(leg.get('swing_quality_gate_enabled') for leg in matching_legs):
                        entry_ok = bool(evaluate_swing_quality_row(row, direction)['swing_quality_pass'])

                if not entry_ok:
                    continue

                setup_id = int(_row_setup_snapshot(row, direction)['setup_id'])
                if (entry_rule, direction, setup_id) in used_setups:
                    continue

                new_positions = []
                for leg_spec in matching_legs:
                    position = _make_position(symbol, timestamp, row, direction, leg_spec)
                    if position is not None:
                        position['active_from_pos'] = row_pos + 1
                        new_positions.append(position)

                if new_positions:
                    used_setups.add((entry_rule, direction, setup_id))
                    open_positions.extend(new_positions)

        for position in open_positions:
            _update_dynamic_targets(position, row)

    if not df.empty:
        last_timestamp = df.index[-1]
        last_close = float(df['close'].iloc[-1])
        for position in open_positions:
            closed_positions.append(
                _close_position(
                    position,
                    last_timestamp,
                    last_close,
                    'EOD',
                    exit_spread=_safe_float(df['spread_price'].iloc[-1]) if ('spread_price' in df.columns and position['direction'] == -1) else 0.0,
                )
            )

    trades = pd.DataFrame(closed_positions)
    if trades.empty:
        return trades

    trades = trades.sort_values(['exit_time', 'entry_time', 'symbol']).reset_index(drop=True)
    trades['timeframe_ltf'] = timeframe_ltf
    trades['timeframe_htf'] = timeframe_htf
    trades['freq'] = _freq_from_timeframe(timeframe_ltf)
    return trades


def _simular_estrategia_en_symbol_numba(
    symbol,
    df,
    strategy_name,
    strategy_config,
    timeframe_ltf,
    timeframe_htf,
):
    if not df.index.is_monotonic_increasing:
        df = df.sort_index()

    legs = _strategy_legs(strategy_name, strategy_config)
    arrays = _prepare_symbol_arrays(df, timeframe_htf)
    leg_entry_rules, leg_memory_bars, leg_tp_codes, leg_sizes = _encode_legs(legs)

    result = _simulate_symbol_core(
        arrays['low'],
        arrays['high'],
        arrays['close'],
        arrays['spread_price'],
        arrays['trend'],
        arrays['macd_long'],
        arrays['macd_short'],
        arrays['long_setup_id'],
        arrays['long_setup_active'],
        arrays['long_setup_age'],
        arrays['long_w1_start'],
        arrays['long_w2_swing'],
        arrays['long_valid_80'],
        arrays['long_invalidated'],
        arrays['long_fib_618'],
        arrays['long_fib_touch'],
        arrays['long_trendline_broken'],
        arrays['long_target_1_0'],
        arrays['long_target_1_618'],
        arrays['short_setup_id'],
        arrays['short_setup_active'],
        arrays['short_setup_age'],
        arrays['short_w1_start'],
        arrays['short_w2_swing'],
        arrays['short_valid_80'],
        arrays['short_invalidated'],
        arrays['short_fib_618'],
        arrays['short_fib_touch'],
        arrays['short_trendline_broken'],
        arrays['short_target_1_0'],
        arrays['short_target_1_618'],
        leg_entry_rules,
        leg_memory_bars,
        leg_tp_codes,
        leg_sizes,
    )

    record_count = result[0]
    if record_count == 0:
        return pd.DataFrame()

    entry_idx, exit_idx, direction, setup_id, entry_rule_code, tp_code, size_fraction, entry_price, stop_price, exit_price, exit_reason_code = result[1:]
    timestamps = df.index.to_numpy()
    entry_time = timestamps[entry_idx]
    exit_time = timestamps[exit_idx]

    entry_rule = np.where(entry_rule_code == 1, 'fib_limit', 'macd_breakout')
    tp_mult = np.where(tp_code == 0, 1.0, 1.618)
    exit_reason = np.where(exit_reason_code == 0, 'SL', np.where(exit_reason_code == 1, 'TP', 'EOD'))
    raw_return = direction * ((exit_price - entry_price) / entry_price)
    weighted_return = raw_return * size_fraction

    trades = pd.DataFrame({
        'symbol': symbol,
        'strategy': strategy_name,
        'entry_rule': entry_rule,
        'direction': direction,
        'setup_id': setup_id,
        'tp_mult': tp_mult,
        'size_fraction': size_fraction,
        'entry_time': entry_time,
        'exit_time': exit_time,
        'entry_price': entry_price,
        'stop_price': stop_price,
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'return_pct': raw_return * 100.0,
        'weighted_return': weighted_return,
        'pnl': weighted_return,
    })
    long_mask = direction == 1
    short_mask = ~long_mask
    trades['W1_START_PRICE'] = np.where(long_mask, arrays['long_w1_start'][entry_idx], arrays['short_w1_start'][entry_idx])
    trades['W1_END_PRICE'] = np.where(
        long_mask,
        _series_to_float_array(df, 'LONG_W1_END_PRICE')[entry_idx],
        _series_to_float_array(df, 'SHORT_W1_END_PRICE')[entry_idx],
    )
    trades['W1_SIZE'] = np.where(
        long_mask,
        _series_to_float_array(df, 'LONG_W1_SIZE')[entry_idx],
        _series_to_float_array(df, 'SHORT_W1_SIZE')[entry_idx],
    )
    trades['W2_EXTREME_PRICE'] = np.where(
        long_mask,
        _series_to_float_array(df, 'LONG_W2_EXTREME_PRICE')[entry_idx],
        _series_to_float_array(df, 'SHORT_W2_EXTREME_PRICE')[entry_idx],
    )
    trades['W2_RETR_PCT'] = np.where(
        long_mask,
        _series_to_float_array(df, 'LONG_W2_RETR_PCT')[entry_idx],
        _series_to_float_array(df, 'SHORT_W2_RETR_PCT')[entry_idx],
    )
    trades['W2_SWING_PRICE'] = np.where(long_mask, arrays['long_w2_swing'][entry_idx], arrays['short_w2_swing'][entry_idx])
    trades['FIB_LEVEL_0.5'] = np.where(
        long_mask,
        _series_to_float_array(df, 'LONG_FIB_LEVEL_0.5')[entry_idx],
        _series_to_float_array(df, 'SHORT_FIB_LEVEL_0.5')[entry_idx],
    )
    trades['FIB_LEVEL_0.618'] = np.where(long_mask, arrays['long_fib_618'][entry_idx], arrays['short_fib_618'][entry_idx])
    trades['FIB_LEVEL_0.8'] = np.where(
        long_mask,
        _series_to_float_array(df, 'LONG_FIB_LEVEL_0.8')[entry_idx],
        _series_to_float_array(df, 'SHORT_FIB_LEVEL_0.8')[entry_idx],
    )
    trades['TARGET_1.0'] = np.where(long_mask, arrays['long_target_1_0'][entry_idx], arrays['short_target_1_0'][entry_idx])
    trades['TARGET_1.618'] = np.where(long_mask, arrays['long_target_1_618'][entry_idx], arrays['short_target_1_618'][entry_idx])
    if not df.empty:
        first_row = df.iloc[0]
        for column_name in SYMBOL_SPEC_COLUMNS:
            trades[column_name] = first_row.get(column_name, np.nan)
    trades = trades.sort_values(['exit_time', 'entry_time', 'symbol']).reset_index(drop=True)
    trades['timeframe_ltf'] = timeframe_ltf
    trades['timeframe_htf'] = timeframe_htf
    trades['freq'] = _freq_from_timeframe(timeframe_ltf)
    return trades


def simular_estrategia_en_symbol(
    symbol,
    df,
    strategy_name,
    strategy_config,
    timeframe_ltf,
    timeframe_htf,
):
    if strategy_config.get('swing_quality_gate_enabled'):
        return _simular_estrategia_en_symbol_python(
            symbol,
            df,
            strategy_name,
            strategy_config,
            timeframe_ltf,
            timeframe_htf,
        )

    if NUMBA_AVAILABLE:
        try:
            return _simular_estrategia_en_symbol_numba(
                symbol,
                df,
                strategy_name,
                strategy_config,
                timeframe_ltf,
                timeframe_htf,
            )
        except Exception:
            pass

    return _simular_estrategia_en_symbol_python(
        symbol,
        df,
        strategy_name,
        strategy_config,
        timeframe_ltf,
        timeframe_htf,
    )


def simular_estrategia_portfolio(
    portfolio,
    strategy_name,
    strategy_config,
    timeframe_ltf,
    timeframe_htf,
    account_config=None,
):
    trades = []
    for symbol, df in portfolio.items():
        sym_trades = simular_estrategia_en_symbol(
            symbol,
            df,
            strategy_name,
            strategy_config,
            timeframe_ltf,
            timeframe_htf,
        )
        if not sym_trades.empty:
            trades.append(sym_trades)

    if not trades:
        return pd.DataFrame()

    trade_frame = pd.concat(trades, ignore_index=True)
    if account_config is None:
        return trade_frame
    return apply_risk_position_sizing(trade_frame, account_config=account_config)


def _metricas_desde_trades(trades):
    if trades.empty:
        return {
            'Trades': 0,
            'WR%': 0.0,
            'AvgWin%': 0.0,
            'AvgLoss%': 0.0,
            'R:R': 0.0,
            'PF': 0.0,
            'Return%': 0.0,
            'Sharpe': 0.0,
            'Sortino': 0.0,
            'MaxDD%': 0.0,
            'Calmar': 0.0,
        }

    pnl_col = 'pnl_money' if 'pnl_money' in trades.columns else 'pnl'
    wins = trades[trades[pnl_col] > 0]
    losses = trades[trades[pnl_col] <= 0]
    n_trades = len(trades)
    wr = len(wins) / n_trades * 100
    avg_win = wins['return_pct'].mean() if not wins.empty else 0.0
    avg_loss = losses['return_pct'].mean() if not losses.empty else 0.0
    rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    gross_win = wins[pnl_col].sum()
    gross_loss = abs(losses[pnl_col].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else np.inf

    if 'pnl_money' in trades.columns:
        initial_capital = float(trades.attrs.get(
            'initial_capital',
            trades.get('balance_before_entry', pd.Series([10000.0])).iloc[0]
            if 'balance_before_entry' in trades.columns else 10000.0
        ))
        event_pnl = trades.groupby('exit_time')['pnl_money'].sum().sort_index()
        equity_before = initial_capital + event_pnl.cumsum().shift(1, fill_value=0.0)
        event_returns = event_pnl / equity_before.replace(0.0, np.nan)
        event_returns = event_returns.fillna(0.0)
        equity = initial_capital + event_pnl.cumsum()
        equity_growth = equity / initial_capital
        total_return = ((equity.iloc[-1] / initial_capital) - 1.0) * 100 if not equity.empty else 0.0
    else:
        event_returns = trades.groupby('exit_time')['weighted_return'].sum().sort_index()
        equity = (1.0 + event_returns).cumprod()
        equity_growth = equity
        total_return = (equity.iloc[-1] - 1.0) * 100 if not equity.empty else 0.0

    if len(event_returns) > 1 and event_returns.std(ddof=0) > 0:
        sharpe = (event_returns.mean() / event_returns.std(ddof=0)) * sqrt(len(event_returns))
    else:
        sharpe = 0.0

    downside = event_returns[event_returns < 0]
    if len(downside) > 0 and downside.std(ddof=0) > 0:
        sortino = (event_returns.mean() / downside.std(ddof=0)) * sqrt(len(event_returns))
    else:
        sortino = 0.0

    if not equity.empty:
        rolling_peak = equity.cummax()
        drawdown = equity / rolling_peak - 1.0
        max_dd = abs(drawdown.min()) * 100
        days = max((equity.index[-1] - equity.index[0]).days, 1)
        years = days / 365.25
        final_growth = float(equity_growth.iloc[-1]) if not equity_growth.empty else np.nan
        if years > 0 and np.isfinite(final_growth):
            if final_growth > 0:
                annual_return = final_growth ** (1 / years) - 1.0
            else:
                # If the equity path ends at or below zero, CAGR is undefined.
                # Treat it as a practical wipeout instead of raising a runtime warning.
                annual_return = -1.0
        else:
            annual_return = 0.0
        calmar = annual_return / abs(drawdown.min()) if drawdown.min() < 0 else 0.0
    else:
        max_dd = 0.0
        calmar = 0.0

    return {
        'Trades': int(n_trades),
        'WR%': round(wr, 1),
        'AvgWin%': round(avg_win, 2),
        'AvgLoss%': round(avg_loss, 2),
        'R:R': round(rr, 2),
        'PF': round(pf, 2) if np.isfinite(pf) else np.inf,
        'Return%': round(total_return, 2),
        'Sharpe': round(sharpe, 2),
        'Sortino': round(sortino, 2),
        'MaxDD%': round(max_dd, 2),
        'Calmar': round(calmar, 2),
    }


def extraer_metricas(trades):
    return _metricas_desde_trades(trades)


def _trade_book_to_frame(trade_book):
    frames = []

    for strategy_name, trades in (trade_book or {}).items():
        if trades is None or trades.empty:
            continue
        frame = trades.copy()
        if 'strategy' not in frame.columns:
            frame['strategy'] = strategy_name
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def generar_desgloses_resultado(resultado, top_n=8):
    trade_book = resultado.get('trades', resultado) if isinstance(resultado, dict) else resultado
    all_trades = _trade_book_to_frame(trade_book)

    metric_cols = [
        'Trades', 'WR%', 'AvgWin%', 'AvgLoss%', 'R:R',
        'PF', 'Return%', 'Sharpe', 'Sortino', 'MaxDD%', 'Calmar'
    ]

    empty_asset = pd.DataFrame(columns=['Variante', 'Activo', *metric_cols])
    empty_exit = pd.DataFrame(columns=['Variante', 'Salida', 'Trades', 'Pct%'])

    if all_trades.empty:
        return {
            'por_activo_estrategia': empty_asset,
            'top_activos': empty_asset.copy(),
            'bottom_activos': empty_asset.copy(),
            'salidas': empty_exit,
        }

    rows = []
    for (strategy_name, symbol), group in all_trades.groupby(['strategy', 'symbol'], sort=True):
        metricas = _metricas_desde_trades(group)
        metricas['Variante'] = strategy_name
        metricas['Activo'] = symbol
        rows.append(metricas)

    por_activo = pd.DataFrame(rows)
    por_activo = por_activo[[
        'Variante', 'Activo', 'Trades', 'WR%', 'AvgWin%', 'AvgLoss%',
        'R:R', 'PF', 'Return%', 'Sharpe', 'Sortino', 'MaxDD%', 'Calmar'
    ]].sort_values(
        ['Variante', 'Return%', 'PF', 'Trades'],
        ascending=[True, False, False, False]
    ).reset_index(drop=True)

    top_rows = []
    bottom_rows = []
    for strategy_name, group in por_activo.groupby('Variante', sort=False):
        top_rows.append(group.head(top_n))
        bottom_rows.append(
            group.sort_values(
                ['Return%', 'PF', 'Trades'],
                ascending=[True, True, False]
            ).head(top_n)
        )

    salidas = (
        all_trades.groupby(['strategy', 'exit_reason'])
        .size()
        .rename('Trades')
        .reset_index()
        .rename(columns={'strategy': 'Variante', 'exit_reason': 'Salida'})
    )
    salidas['Pct%'] = (
        salidas['Trades'] / salidas.groupby('Variante')['Trades'].transform('sum') * 100.0
    ).round(1)
    salidas = salidas[['Variante', 'Salida', 'Trades', 'Pct%']].sort_values(
        ['Variante', 'Trades'],
        ascending=[True, False]
    ).reset_index(drop=True)

    return {
        'por_activo_estrategia': por_activo,
        'top_activos': pd.concat(top_rows, ignore_index=True) if top_rows else empty_asset.copy(),
        'bottom_activos': pd.concat(bottom_rows, ignore_index=True) if bottom_rows else empty_asset.copy(),
        'salidas': salidas,
    }


def _normalize_direction_filter(direction):
    if direction is None:
        return None
    if isinstance(direction, str):
        text = direction.strip().lower()
        if text in {'long', 'largo', 'buy', 'compras', 'compra'}:
            return 1
        if text in {'short', 'corto', 'sell', 'ventas', 'venta'}:
            return -1
    try:
        direction_value = int(direction)
    except (TypeError, ValueError):
        return None
    return direction_value if direction_value in {1, -1} else None


def extraer_trades_resultado(
    resultado,
    strategy=None,
    symbol=None,
    direction=None,
    exit_reason=None,
):
    if isinstance(resultado, pd.DataFrame):
        trades = resultado.copy()
    elif isinstance(resultado, dict):
        if 'trades' in resultado:
            trades = _trade_book_to_frame(resultado.get('trades'))
        else:
            trades = _trade_book_to_frame(resultado)
    else:
        trades = pd.DataFrame()

    if trades.empty:
        return trades

    if strategy is not None:
        strategies = {strategy} if isinstance(strategy, str) else set(strategy)
        trades = trades[trades['strategy'].isin(strategies)]
    if symbol is not None:
        symbols = {symbol} if isinstance(symbol, str) else set(symbol)
        trades = trades[trades['symbol'].isin(symbols)]

    direction_filter = _normalize_direction_filter(direction)
    if direction_filter is not None and 'direction' in trades.columns:
        trades = trades[trades['direction'] == direction_filter]

    if exit_reason is not None and 'exit_reason' in trades.columns:
        reasons = {exit_reason} if isinstance(exit_reason, str) else set(exit_reason)
        trades = trades[trades['exit_reason'].isin(reasons)]

    sort_cols = [col for col in ('entry_time', 'exit_time', 'symbol', 'tp_mult') if col in trades.columns]
    if sort_cols:
        trades = trades.sort_values(sort_cols).reset_index(drop=True)
    else:
        trades = trades.reset_index(drop=True)
    return trades


def extraer_operaciones_resultado(
    resultado,
    strategy=None,
    symbol=None,
    direction=None,
    exit_reason=None,
):
    trades = extraer_trades_resultado(
        resultado,
        strategy=strategy,
        symbol=symbol,
        direction=direction,
        exit_reason=exit_reason,
    )

    columns = [
        'strategy', 'symbol', 'entry_rule', 'direction', 'direction_label',
        'setup_id', 'entry_time', 'entry_price', 'stop_price',
        'W1_START_PRICE', 'W1_END_PRICE', 'W1_SIZE',
        'W2_EXTREME_PRICE', 'W2_RETR_PCT', 'W2_SWING_PRICE',
        'FIB_LEVEL_0.5', 'FIB_LEVEL_0.618', 'FIB_LEVEL_0.8',
        'TARGET_1.0', 'TARGET_1.618',
        'legs', 'tp_mults', 'tp1_exit_time', 'tp2_exit_time',
        'first_exit_time', 'last_exit_time', 'exit_reason_mix',
        'size_fraction_total', 'risk_amount_total', 'lots_total',
        'pnl_money_total', 'weighted_return_total',
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)

    group_cols = [
        col for col in (
            'strategy', 'symbol', 'entry_rule', 'direction', 'setup_id',
            'entry_time', 'entry_price', 'stop_price',
        ) if col in trades.columns
    ]

    rows = []
    for _, group in trades.groupby(group_cols, sort=True, dropna=False):
        group = group.sort_values(['tp_mult', 'exit_time'], ascending=[True, True]).reset_index(drop=True)
        row = {col: group.iloc[0][col] for col in group_cols}
        row['direction_label'] = 'LONG' if int(group.iloc[0].get('direction', 0)) == 1 else 'SHORT'
        for column_name in TRADE_SETUP_COLUMNS:
            if column_name in group.columns:
                row[column_name] = group.iloc[0][column_name]
        row['legs'] = int(len(group))
        row['tp_mults'] = ', '.join(f"{float(value):.3f}".rstrip('0').rstrip('.') for value in group['tp_mult'].tolist())
        row['tp1_exit_time'] = (
            pd.Timestamp(group.loc[group['tp_mult'] == 1.0, 'exit_time'].iloc[0])
            if 'tp_mult' in group.columns and (group['tp_mult'] == 1.0).any()
            else pd.NaT
        )
        row['tp2_exit_time'] = (
            pd.Timestamp(group.loc[group['tp_mult'] != 1.0, 'exit_time'].iloc[0])
            if 'tp_mult' in group.columns and (group['tp_mult'] != 1.0).any()
            else pd.NaT
        )
        row['first_exit_time'] = pd.Timestamp(group['exit_time'].min()) if 'exit_time' in group.columns else pd.NaT
        row['last_exit_time'] = pd.Timestamp(group['exit_time'].max()) if 'exit_time' in group.columns else pd.NaT
        if 'exit_reason' in group.columns:
            exit_reasons = list(dict.fromkeys(group['exit_reason'].astype(str).tolist()))
            row['exit_reason_mix'] = ' / '.join(exit_reasons)
        else:
            row['exit_reason_mix'] = ''
        row['size_fraction_total'] = float(
            pd.to_numeric(group['size_fraction'], errors='coerce').fillna(0.0).sum()
        ) if 'size_fraction' in group.columns else 0.0
        row['risk_amount_total'] = float(
            pd.to_numeric(group['risk_amount'], errors='coerce').fillna(0.0).sum()
        ) if 'risk_amount' in group.columns else 0.0
        row['lots_total'] = float(
            pd.to_numeric(group['lots'], errors='coerce').fillna(0.0).sum()
        ) if 'lots' in group.columns else 0.0
        row['weighted_return_total'] = float(
            pd.to_numeric(group['weighted_return'], errors='coerce').fillna(0.0).sum()
        ) if 'weighted_return' in group.columns else 0.0
        if 'pnl_money' in group.columns:
            row['pnl_money_total'] = float(pd.to_numeric(group['pnl_money'], errors='coerce').fillna(0.0).sum())
        else:
            row['pnl_money_total'] = np.nan
        rows.append(row)

    return pd.DataFrame(rows).reindex(columns=columns).sort_values(
        ['entry_time', 'symbol', 'setup_id'],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def generar_auditoria_riesgo(
    resultado,
    strategy=None,
    symbol=None,
    direction=None,
    exit_reason=None,
    max_rows=None,
):
    trades = extraer_trades_resultado(
        resultado,
        strategy=strategy,
        symbol=symbol,
        direction=direction,
        exit_reason=exit_reason,
    )

    audit_columns = [
        'strategy', 'symbol', 'direction_label', 'entry_rule', 'setup_id', 'exit_reason',
        'entry_time', 'exit_time', 'entry_price', 'stop_price', 'exit_price',
        'W1_START_PRICE', 'W1_END_PRICE', 'W1_SIZE',
        'W2_EXTREME_PRICE', 'W2_RETR_PCT', 'W2_SWING_PRICE',
        'FIB_LEVEL_0.5', 'FIB_LEVEL_0.618', 'FIB_LEVEL_0.8',
        'TARGET_1.0', 'TARGET_1.618',
        'size_fraction', 'balance_before_entry', 'risk_amount', 'risk_pct_real',
        'stop_distance', 'stop_ticks', 'loss_per_lot', 'lots_raw', 'lots',
        'expected_loss_at_sl', 'risk_gap', 'ticks_moved', 'tick_value_used',
        'commission_per_side_per_lot', 'commission_entry', 'commission_exit', 'commission_total',
        'pnl_money_gross', 'pnl_money', 'pnl_formula_money', 'pnl_formula_diff', 'pnl_net_diff',
    ]
    if trades.empty:
        return pd.DataFrame(columns=audit_columns)

    audit = trades.copy()

    def _series_from_audit(column_name, default=np.nan):
        if column_name in audit.columns:
            return pd.to_numeric(audit[column_name], errors='coerce')
        return pd.Series(default, index=audit.index, dtype=float)

    audit['direction_label'] = np.where(audit.get('direction', 0) == 1, 'LONG', 'SHORT')

    if 'balance_before_entry' in audit.columns and 'risk_amount' in audit.columns:
        balance = pd.to_numeric(audit['balance_before_entry'], errors='coerce')
        risk_amount = pd.to_numeric(audit['risk_amount'], errors='coerce')
        audit['risk_pct_real'] = np.where(balance > 0, (risk_amount / balance) * 100.0, np.nan)
    else:
        audit['risk_pct_real'] = np.nan

    stop_distance = _series_from_audit('stop_distance')
    tick_size = _series_from_audit('SYMBOL_TRADE_TICK_SIZE')
    audit['stop_ticks'] = np.where(tick_size > 0, stop_distance / tick_size, np.nan)

    lots = _series_from_audit('lots')
    loss_per_lot = _series_from_audit('loss_per_lot')
    audit['expected_loss_at_sl'] = loss_per_lot * lots

    risk_amount = _series_from_audit('risk_amount')
    audit['risk_gap'] = audit['expected_loss_at_sl'] - risk_amount

    ticks_moved = _series_from_audit('ticks_moved')
    tick_value_used = _series_from_audit('tick_value_used')
    audit['pnl_formula_money'] = ticks_moved * tick_value_used * lots

    pnl_money_gross = _series_from_audit('pnl_money_gross')
    if pnl_money_gross.isna().all():
        pnl_money_gross = _series_from_audit('pnl_money')
    pnl_money_net = _series_from_audit('pnl_money')
    commission_total = _series_from_audit('commission_total', default=0.0).fillna(0.0)
    audit['pnl_formula_diff'] = pnl_money_gross - audit['pnl_formula_money']
    audit['pnl_net_diff'] = pnl_money_net - (audit['pnl_formula_money'] - commission_total)

    if max_rows is not None:
        audit = audit.head(int(max_rows))

    present_cols = [col for col in audit_columns if col in audit.columns]
    return audit[present_cols].reset_index(drop=True)


def resumir_portfolio_cargado(portfolio):
    rows = []
    if not portfolio:
        return pd.DataFrame(columns=[
            'Activo', 'Velas', 'Inicio', 'Fin', 'Dias', 'VelasVsMax%', 'VelasMenosQueMax'
        ])

    max_rows = max(len(df) for df in portfolio.values()) if portfolio else 0
    for symbol, df in portfolio.items():
        if df is None or df.empty:
            rows.append({
                'Activo': symbol,
                'Velas': 0,
                'Inicio': pd.NaT,
                'Fin': pd.NaT,
                'Dias': 0.0,
                'VelasVsMax%': 0.0,
                'VelasMenosQueMax': max_rows,
            })
            continue

        start = pd.Timestamp(df.index.min())
        end = pd.Timestamp(df.index.max())
        n_rows = len(df)
        rows.append({
            'Activo': symbol,
            'Velas': n_rows,
            'Inicio': start,
            'Fin': end,
            'Dias': round((end - start).total_seconds() / 86400.0, 1),
            'VelasVsMax%': round((n_rows / max_rows) * 100.0, 1) if max_rows > 0 else 0.0,
            'VelasMenosQueMax': int(max_rows - n_rows),
        })

    return pd.DataFrame(rows).sort_values(
        ['Velas', 'Activo'],
        ascending=[False, True],
    ).reset_index(drop=True)


def extraer_ventana_trade(
    portfolio,
    resultado,
    trade_index=0,
    strategy=None,
    symbol=None,
    direction=None,
    bars_before=25,
    bars_after=25,
):
    trades = extraer_trades_resultado(
        resultado,
        strategy=strategy,
        symbol=symbol,
        direction=direction,
    )
    if trades.empty:
        return pd.DataFrame()

    trade_row = trades.iloc[int(trade_index)]
    symbol_name = trade_row['symbol']
    df = portfolio.get(symbol_name)
    if df is None or df.empty:
        return pd.DataFrame()

    entry_time = pd.Timestamp(trade_row['entry_time'])
    exit_time = pd.Timestamp(trade_row['exit_time'])
    direction_value = int(trade_row['direction'])
    prefix = 'LONG' if direction_value == 1 else 'SHORT'

    entry_pos = df.index.get_indexer([entry_time], method='nearest')[0]
    exit_pos = df.index.get_indexer([exit_time], method='nearest')[0]
    start_pos = max(0, entry_pos - int(bars_before))
    end_pos = min(len(df), exit_pos + int(bars_after) + 1)

    timeframe_htf = trade_row.get('timeframe_htf')
    trend_column = _trend_col(timeframe_htf) if timeframe_htf else None

    candidate_columns = [
        'open', 'high', 'low', 'close', 'spread', 'spread_price',
        trend_column,
        f'{prefix}_SETUP_ID',
        f'{prefix}_SETUP_ACTIVE',
        f'{prefix}_SETUP_AGE',
        f'{prefix}_W1_START_PRICE',
        f'{prefix}_W1_END_PRICE',
        f'{prefix}_W1_SIZE',
        f'{prefix}_W2_EXTREME_PRICE',
        f'{prefix}_W2_RETR_PCT',
        f'{prefix}_W2_SWING_PRICE',
        f'{prefix}_W2_VALID_80',
        f'{prefix}_W2_INVALIDATED',
        f'{prefix}_FIB_LEVEL_0.5',
        f'{prefix}_FIB_LEVEL_0.618',
        f'{prefix}_FIB_LEVEL_0.8',
        f'{prefix}_W2_TRENDLINE_BROKEN',
        f'{prefix}_TARGET_1.0',
        f'{prefix}_TARGET_1.618',
        'MACD_CROSS_LONG' if direction_value == 1 else 'MACD_CROSS_SHORT',
    ]
    columns = [col for col in candidate_columns if col and col in df.columns]
    window = df.iloc[start_pos:end_pos][columns].copy()
    window['TRADE_ENTRY'] = window.index == entry_time
    window['TRADE_EXIT'] = window.index == exit_time
    window['TRADE_ENTRY_PRICE'] = np.where(window['TRADE_ENTRY'], float(trade_row['entry_price']), np.nan)
    window['TRADE_STOP_PRICE'] = float(trade_row['stop_price'])
    window['TRADE_EXIT_PRICE'] = np.where(window['TRADE_EXIT'], float(trade_row['exit_price']), np.nan)
    window.attrs['trade'] = trade_row.to_dict()
    return window


def resumir_periodos(trades, splits=None):
    if trades is None or trades.empty or 'entry_time' not in trades.columns:
        return pd.DataFrame()

    rows = []
    for period_name, (start, end) in (splits or TEMPORAL_SPLITS).items():
        period_trades = trades.copy()
        if start is not None:
            period_trades = period_trades[period_trades['entry_time'] >= pd.Timestamp(start)]
        if end is not None:
            period_trades = period_trades[period_trades['entry_time'] < pd.Timestamp(end)]
        metricas = _metricas_desde_trades(period_trades)
        metricas['Periodo'] = period_name
        rows.append(metricas)

    if not rows:
        return pd.DataFrame()

    cols = [
        'Periodo', 'Trades', 'WR%', 'AvgWin%', 'AvgLoss%', 'R:R',
        'PF', 'Return%', 'Sharpe', 'Sortino', 'MaxDD%', 'Calmar'
    ]
    return pd.DataFrame(rows)[cols]


def ejecutar_comparativa(
    portfolio_base,
    estrategias=None,
    timeframe_ltf='H1',
    timeframe_htf='H4',
    account_config=None,
    return_details=False,
):
    strategy_defs = get_strategy_definitions(estrategias or DEFAULT_STRATEGIES)
    account_settings = get_account_config(account_config)
    summary_rows = []
    trade_book = {}
    split_rows = []

    for strategy_name, strategy_config in strategy_defs.items():
        print(f"\n{'=' * 50}")
        print(f"  {strategy_name}")
        print(f"{'=' * 50}")

        trades = simular_estrategia_portfolio(
            portfolio_base,
            strategy_name,
            strategy_config,
            timeframe_ltf,
            timeframe_htf,
            account_config=account_settings,
        )
        trade_book[strategy_name] = trades

        metricas = _metricas_desde_trades(trades)
        metricas['Variante'] = strategy_name
        metricas['LTF'] = timeframe_ltf
        metricas['HTF'] = timeframe_htf
        summary_rows.append(metricas)

        period_df = resumir_periodos(trades)
        if not period_df.empty:
            period_df['Variante'] = strategy_name
            period_df['LTF'] = timeframe_ltf
            period_df['HTF'] = timeframe_htf
            split_rows.append(period_df)

        print(
            f"  Trades: {metricas['Trades']} | WR: {metricas['WR%']}% | "
            f"PF: {metricas['PF']} | Ret: {metricas['Return%']:+.2f}%"
        )

    summary = pd.DataFrame(summary_rows)
    if summary.empty:
        summary = pd.DataFrame(columns=[
            'Variante', 'LTF', 'HTF', 'Trades', 'WR%', 'AvgWin%', 'AvgLoss%',
            'R:R', 'PF', 'Return%', 'Sharpe', 'Sortino', 'MaxDD%', 'Calmar'
        ])
    else:
        summary = summary[[
            'Variante', 'LTF', 'HTF', 'Trades', 'WR%', 'AvgWin%', 'AvgLoss%',
            'R:R', 'PF', 'Return%', 'Sharpe', 'Sortino', 'MaxDD%', 'Calmar'
        ]]

    if not return_details:
        return summary

    return {
        'summary': summary,
        'splits': pd.concat(split_rows, ignore_index=True) if split_rows else pd.DataFrame(),
        'trades': trade_book,
    }


def ejecutar_matriz_backtest(
    grupos=None,
    tf_pairs=None,
    estrategias=None,
    context_config=None,
    indicator_config=None,
    account_config=None,
    verbose=True,
    return_details=False,
    use_cache=True,
    force_rebuild=False,
    use_disk_cache=True,
):
    portfolios = cargar_portfolios_matriz(
        groups=grupos,
        tf_pairs=tf_pairs,
        context_config=context_config,
        indicator_config=indicator_config,
        verbose=verbose,
        use_cache=use_cache,
        force_rebuild=force_rebuild,
        use_disk_cache=use_disk_cache,
    )

    summary_rows = []
    split_rows = []
    detail_map = {}
    strategy_defs = get_strategy_definitions(estrategias or DEFAULT_STRATEGIES)

    for (group_name, timeframe_ltf, timeframe_htf), portfolio in portfolios.items():
        if not portfolio:
            continue

        result = ejecutar_comparativa(
            portfolio,
            estrategias=strategy_defs,
            timeframe_ltf=timeframe_ltf,
            timeframe_htf=timeframe_htf,
            account_config=account_config,
            return_details=True,
        )
        summary = result['summary'].copy()
        summary['Group'] = group_name
        summary_rows.append(summary)

        splits = result['splits'].copy()
        if not splits.empty:
            splits['Group'] = group_name
            split_rows.append(splits)

        if return_details:
            detail_map[(group_name, timeframe_ltf, timeframe_htf)] = result

    summary_df = pd.concat(summary_rows, ignore_index=True) if summary_rows else pd.DataFrame()
    split_df = pd.concat(split_rows, ignore_index=True) if split_rows else pd.DataFrame()

    if not return_details:
        return summary_df

    return {
        'summary': summary_df,
        'splits': split_df,
        'details': detail_map,
        'timeframe_pairs': dict(get_timeframe_pairs(tf_pairs)),
    }


def colorear_comparativa(df_comp):
    def _color_row(row):
        styles = [''] * len(row)

        if 'PF' in row.index:
            pf_idx = list(row.index).index('PF')
            if row['PF'] >= 1.5:
                styles[pf_idx] = 'background-color: #2d5a27; color: white'
            elif row['PF'] >= 1.0:
                styles[pf_idx] = 'background-color: #1a4a1a; color: #90ee90'
            else:
                styles[pf_idx] = 'background-color: #5a2727; color: white'

        if 'Return%' in row.index:
            ret_idx = list(row.index).index('Return%')
            if row['Return%'] > 0:
                styles[ret_idx] = 'background-color: #1a4a1a; color: #90ee90'
            else:
                styles[ret_idx] = 'background-color: #4a1a1a; color: #ee9090'

        return styles

    compact = [{'selector': 'th, td', 'props': [
        ('font-size', '11px'),
        ('padding', '3px 6px'),
        ('white-space', 'nowrap'),
    ]}]

    formatters = {
        'WR%': '{:.1f}',
        'AvgWin%': '{:+.2f}',
        'AvgLoss%': '{:+.2f}',
        'R:R': '{:.2f}',
        'PF': '{:.2f}',
        'Return%': '{:+.2f}',
        'Sharpe': '{:.2f}',
        'Sortino': '{:.2f}',
        'MaxDD%': '{:.2f}',
        'Calmar': '{:.2f}',
    }

    formatters = {key: value for key, value in formatters.items() if key in df_comp.columns}
    return df_comp.style.apply(_color_row, axis=1).format(formatters).set_table_styles(compact)


def cargar_y_ejecutar_grupo(
    group_name,
    timeframe_ltf,
    timeframe_htf,
    estrategias=None,
    context_config=None,
    indicator_config=None,
    account_config=None,
    verbose=True,
    return_details=False,
    use_cache=True,
    force_rebuild=False,
    use_disk_cache=True,
):
    from backtests.common.backtest_matrix_config import normalize_group_name

    normalized = normalize_group_name(group_name)
    portfolios = cargar_portfolios_matriz(
        groups=[normalized],
        tf_pairs={timeframe_ltf: timeframe_htf},
        context_config=context_config,
        indicator_config=indicator_config,
        verbose=verbose,
        use_cache=use_cache,
        force_rebuild=force_rebuild,
        use_disk_cache=use_disk_cache,
    )
    portfolio = portfolios.get((normalized, timeframe_ltf, timeframe_htf), {})

    return ejecutar_comparativa(
        portfolio,
        estrategias=estrategias,
        timeframe_ltf=timeframe_ltf,
        timeframe_htf=timeframe_htf,
        account_config=account_config,
        return_details=return_details,
    )


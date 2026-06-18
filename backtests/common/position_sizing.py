"""Shared position sizing helpers for backtests and risk-aware comparisons."""

from __future__ import annotations

import heapq
import math

import numpy as np
import pandas as pd


SYMBOL_SPEC_COLUMN_MAP = {
    'digits': 'SYMBOL_DIGITS',
    'point_size': 'SYMBOL_POINT_SIZE',
    'trade_tick_size': 'SYMBOL_TRADE_TICK_SIZE',
    'trade_tick_value': 'SYMBOL_TRADE_TICK_VALUE',
    'trade_tick_value_profit': 'SYMBOL_TRADE_TICK_VALUE_PROFIT',
    'trade_tick_value_loss': 'SYMBOL_TRADE_TICK_VALUE_LOSS',
    'trade_contract_size': 'SYMBOL_TRADE_CONTRACT_SIZE',
    'volume_min': 'SYMBOL_VOLUME_MIN',
    'volume_max': 'SYMBOL_VOLUME_MAX',
    'volume_step': 'SYMBOL_VOLUME_STEP',
    'currency_base': 'SYMBOL_CURRENCY_BASE',
    'currency_profit': 'SYMBOL_CURRENCY_PROFIT',
    'currency_margin': 'SYMBOL_CURRENCY_MARGIN',
}

SYMBOL_SPEC_DEFAULTS = {
    'digits': None,
    'point_size': None,
    'trade_tick_size': None,
    'trade_tick_value': None,
    'trade_tick_value_profit': None,
    'trade_tick_value_loss': None,
    'trade_contract_size': None,
    'volume_min': 0.01,
    'volume_max': 100.0,
    'volume_step': 0.01,
    'currency_base': None,
    'currency_profit': None,
    'currency_margin': None,
}

DEFAULT_ACCOUNT_CONFIG = {
    'initial_capital': 10000.0,
    'risk_per_trade': 0.01,
    'skip_if_below_min_volume': True,
    'account_currency': 'USD',
    'commission_model': 'fpmarkets_raw_mt45',
}


FP_MARKETS_RAW_COMMISSION_PER_SIDE = {
    'USD': 3.0,
    'EUR': 2.75,
    'GBP': 2.25,
}


def _safe_float(value, default=None):
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=None):
    if value is None or pd.isna(value):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _decimal_places(step):
    if step is None or step <= 0:
        return 2
    text = f"{float(step):.10f}".rstrip('0').rstrip('.')
    return len(text.split('.')[-1]) if '.' in text else 0


def _normalize_text(value):
    if value is None or pd.isna(value):
        return None
    return str(value).strip().upper()


def infer_symbol_asset_class(symbol):
    """Infer a coarse asset class from the symbol name."""
    raw_symbol = _normalize_text(symbol)
    if not raw_symbol:
        return 'unknown'

    clean_symbol = raw_symbol.split('.')[0]

    if clean_symbol.startswith(('XAU', 'XAG')):
        return 'metals'

    if len(clean_symbol) >= 6 and clean_symbol[:6].isalpha():
        return 'forex'

    return 'index'


def get_commission_per_side_per_lot(symbol, account_config=None):
    """Return per-side commission per lot for the configured broker model."""
    config = dict(DEFAULT_ACCOUNT_CONFIG)
    if account_config:
        config.update(account_config)

    model = str(config.get('commission_model', 'none') or 'none').strip().lower()
    if model in {'none', 'off', 'disabled', 'false', '0'}:
        return 0.0

    asset_class = infer_symbol_asset_class(symbol)
    if asset_class not in {'forex', 'metals'}:
        return 0.0

    if model == 'fpmarkets_raw_mt45':
        account_currency = _normalize_text(config.get('account_currency')) or 'USD'
        return float(FP_MARKETS_RAW_COMMISSION_PER_SIDE.get(account_currency, FP_MARKETS_RAW_COMMISSION_PER_SIDE['USD']))

    commission_per_side = _safe_float(config.get('commission_per_lot_per_side'), 0.0)
    return max(0.0, float(commission_per_side or 0.0))


def calculate_trade_commissions(symbol, lots, account_config=None):
    """Calculate entry, exit and total commission for a sized trade."""
    lots = max(0.0, _safe_float(lots, 0.0) or 0.0)
    commission_per_side = get_commission_per_side_per_lot(symbol, account_config=account_config)
    commission_entry = lots * commission_per_side
    commission_exit = lots * commission_per_side
    return {
        'commission_per_side_per_lot': commission_per_side,
        'commission_entry': commission_entry,
        'commission_exit': commission_exit,
        'commission_total': commission_entry + commission_exit,
    }


def attach_symbol_spec_columns(df, symbol_meta=None):
    """Attach symbol metadata columns to a trade DataFrame."""
    df = df.copy()
    symbol_meta = symbol_meta or {}

    for meta_key, column_name in SYMBOL_SPEC_COLUMN_MAP.items():
        value = symbol_meta.get(meta_key, SYMBOL_SPEC_DEFAULTS.get(meta_key))
        df[column_name] = value

    return df


def extract_symbol_spec_from_row(row):
    """Extract normalized symbol spec fields from a trade row."""
    spec = {}
    for meta_key, column_name in SYMBOL_SPEC_COLUMN_MAP.items():
        value = row.get(column_name, SYMBOL_SPEC_DEFAULTS.get(meta_key))
        if meta_key == 'digits':
            spec[meta_key] = _safe_int(value, SYMBOL_SPEC_DEFAULTS.get(meta_key))
        elif meta_key.startswith('currency_'):
            spec[meta_key] = value if value is not None and not pd.isna(value) else None
        else:
            spec[meta_key] = _safe_float(value, SYMBOL_SPEC_DEFAULTS.get(meta_key))
    return spec


def normalize_symbol_spec(symbol_spec):
    """Fill and coerce symbol metadata used by sizing/PnL calculations."""
    normalized = dict(SYMBOL_SPEC_DEFAULTS)
    if symbol_spec:
        normalized.update(symbol_spec)

    normalized['digits'] = _safe_int(normalized.get('digits'), SYMBOL_SPEC_DEFAULTS['digits'])
    for key in (
        'point_size',
        'trade_tick_size',
        'trade_tick_value',
        'trade_tick_value_profit',
        'trade_tick_value_loss',
        'trade_contract_size',
        'volume_min',
        'volume_max',
        'volume_step',
    ):
        normalized[key] = _safe_float(normalized.get(key), SYMBOL_SPEC_DEFAULTS.get(key))

    if not normalized['trade_tick_size'] or normalized['trade_tick_size'] <= 0:
        normalized['trade_tick_size'] = normalized.get('point_size')
    if not normalized['trade_tick_value_loss'] or normalized['trade_tick_value_loss'] <= 0:
        normalized['trade_tick_value_loss'] = (
            normalized.get('trade_tick_value') or normalized.get('trade_tick_value_profit')
        )
    if not normalized['trade_tick_value_profit'] or normalized['trade_tick_value_profit'] <= 0:
        normalized['trade_tick_value_profit'] = (
            normalized.get('trade_tick_value') or normalized.get('trade_tick_value_loss')
        )
    if not normalized['trade_tick_value'] or normalized['trade_tick_value'] <= 0:
        normalized['trade_tick_value'] = (
            normalized.get('trade_tick_value_profit') or normalized.get('trade_tick_value_loss')
        )

    if not normalized['volume_step'] or normalized['volume_step'] <= 0:
        normalized['volume_step'] = 0.01
    if normalized['volume_min'] is None or normalized['volume_min'] <= 0:
        normalized['volume_min'] = normalized['volume_step']
    if normalized['volume_max'] is None or normalized['volume_max'] <= 0:
        normalized['volume_max'] = 100.0

    return normalized


def calculate_lot_size_for_risk(
    balance,
    risk_per_trade,
    leg_fraction,
    entry_price,
    stop_price,
    symbol_spec,
    skip_if_below_min_volume=True,
):
    """Calculate lots from monetary risk, stop distance and symbol metadata."""
    spec = normalize_symbol_spec(symbol_spec)
    stop_distance = abs(float(entry_price) - float(stop_price))
    risk_amount = float(balance) * float(risk_per_trade) * float(leg_fraction)

    tick_size = spec.get('trade_tick_size')
    tick_value_loss = spec.get('trade_tick_value_loss') or spec.get('trade_tick_value')

    if (
        risk_amount <= 0 or
        stop_distance <= 0 or
        tick_size is None or tick_size <= 0 or
        tick_value_loss is None or tick_value_loss <= 0
    ):
        return {
            'executed': False,
            'risk_amount': risk_amount,
            'stop_distance': stop_distance,
            'loss_per_lot': np.nan,
            'lots_raw': 0.0,
            'lots': 0.0,
        }

    loss_per_lot = (stop_distance / tick_size) * tick_value_loss
    if loss_per_lot <= 0:
        return {
            'executed': False,
            'risk_amount': risk_amount,
            'stop_distance': stop_distance,
            'loss_per_lot': loss_per_lot,
            'lots_raw': 0.0,
            'lots': 0.0,
        }

    lots_raw = risk_amount / loss_per_lot
    step = spec['volume_step']
    volume_min = spec['volume_min']
    volume_max = spec['volume_max']

    lots = math.floor(lots_raw / step) * step if step > 0 else lots_raw
    lots = round(max(0.0, lots), _decimal_places(step))

    if lots < volume_min:
        if skip_if_below_min_volume:
            return {
                'executed': False,
                'risk_amount': risk_amount,
                'stop_distance': stop_distance,
                'loss_per_lot': loss_per_lot,
                'lots_raw': lots_raw,
                'lots': 0.0,
            }
        lots = volume_min

    lots = min(lots, volume_max)
    lots = round(lots, _decimal_places(step))

    return {
        'executed': lots > 0,
        'risk_amount': risk_amount,
        'stop_distance': stop_distance,
        'loss_per_lot': loss_per_lot,
        'lots_raw': lots_raw,
        'lots': lots,
    }


def calculate_trade_pnl_money(entry_price, exit_price, direction, lots, symbol_spec):
    """Calculate gross PnL in account currency from tick metadata."""
    spec = normalize_symbol_spec(symbol_spec)
    tick_size = spec.get('trade_tick_size')
    if tick_size is None or tick_size <= 0 or lots <= 0:
        return {
            'pnl_money': 0.0,
            'ticks_moved': 0.0,
            'tick_value_used': np.nan,
        }

    signed_ticks = float(direction) * ((float(exit_price) - float(entry_price)) / tick_size)
    tick_value = (
        spec.get('trade_tick_value_profit')
        if signed_ticks >= 0 else
        spec.get('trade_tick_value_loss')
    )
    if tick_value is None or tick_value <= 0:
        tick_value = spec.get('trade_tick_value')
    if tick_value is None or tick_value <= 0:
        return {
            'pnl_money': 0.0,
            'ticks_moved': signed_ticks,
            'tick_value_used': np.nan,
        }

    pnl_money = signed_ticks * tick_value * float(lots)
    return {
        'pnl_money': pnl_money,
        'ticks_moved': signed_ticks,
        'tick_value_used': tick_value,
    }


def apply_risk_position_sizing(trades, account_config=None):
    """Apply chronological risk-based sizing to a trade log."""
    if trades is None or trades.empty:
        return pd.DataFrame(columns=list(trades.columns) if trades is not None else [])

    config = dict(DEFAULT_ACCOUNT_CONFIG)
    if account_config:
        config.update(account_config)

    initial_capital = float(config['initial_capital'])
    risk_per_trade = float(config['risk_per_trade'])
    skip_if_below_min_volume = bool(config.get('skip_if_below_min_volume', True))

    ordered = trades.sort_values(
        ['entry_time', 'exit_time', 'symbol', 'tp_mult'],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)

    settled_balance = initial_capital
    pending_exits = []
    executed_rows = []

    for _, row in ordered.iterrows():
        entry_time = pd.Timestamp(row['entry_time'])
        while pending_exits and pending_exits[0][0] < entry_time:
            _, settled_pnl = heapq.heappop(pending_exits)
            settled_balance += settled_pnl

        symbol_spec = extract_symbol_spec_from_row(row)
        sizing = calculate_lot_size_for_risk(
            balance=settled_balance,
            risk_per_trade=risk_per_trade,
            leg_fraction=row.get('size_fraction', 1.0),
            entry_price=row['entry_price'],
            stop_price=row['stop_price'],
            symbol_spec=symbol_spec,
            skip_if_below_min_volume=skip_if_below_min_volume,
        )

        if not sizing['executed']:
            continue

        pnl_info = calculate_trade_pnl_money(
            entry_price=row['entry_price'],
            exit_price=row['exit_price'],
            direction=row['direction'],
            lots=sizing['lots'],
            symbol_spec=symbol_spec,
        )
        commission_info = calculate_trade_commissions(
            symbol=row.get('symbol'),
            lots=sizing['lots'],
            account_config=config,
        )
        pnl_money_gross = pnl_info['pnl_money']
        pnl_money_net = pnl_money_gross - commission_info['commission_total']

        row_out = row.copy()
        row_out['balance_before_entry'] = settled_balance
        row_out['risk_amount'] = sizing['risk_amount']
        row_out['stop_distance'] = sizing['stop_distance']
        row_out['loss_per_lot'] = sizing['loss_per_lot']
        row_out['lots_raw'] = sizing['lots_raw']
        row_out['lots'] = sizing['lots']
        row_out['ticks_moved'] = pnl_info['ticks_moved']
        row_out['tick_value_used'] = pnl_info['tick_value_used']
        row_out['commission_per_side_per_lot'] = commission_info['commission_per_side_per_lot']
        row_out['commission_entry'] = commission_info['commission_entry']
        row_out['commission_exit'] = commission_info['commission_exit']
        row_out['commission_total'] = commission_info['commission_total']
        row_out['pnl_money_gross'] = pnl_money_gross
        row_out['pnl_money'] = pnl_money_net
        row_out['weighted_return'] = (
            pnl_money_net / settled_balance if settled_balance > 0 else 0.0
        )
        row_out['pnl'] = pnl_money_net
        executed_rows.append(row_out)

        heapq.heappush(
            pending_exits,
            (pd.Timestamp(row_out['exit_time']), float(row_out['pnl_money'])),
        )

    if not executed_rows:
        return pd.DataFrame(columns=list(trades.columns) + [
            'balance_before_entry', 'risk_amount', 'stop_distance', 'loss_per_lot',
            'lots_raw', 'lots', 'ticks_moved', 'tick_value_used',
            'commission_per_side_per_lot', 'commission_entry', 'commission_exit',
            'commission_total', 'pnl_money_gross', 'pnl_money',
        ])

    sized = pd.DataFrame(executed_rows).sort_values(
        ['exit_time', 'entry_time', 'symbol', 'tp_mult'],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)

    event_pnl = sized.groupby('exit_time')['pnl_money'].sum().sort_index()
    event_balance_before = initial_capital + event_pnl.cumsum().shift(1, fill_value=0.0)
    event_balance_after = initial_capital + event_pnl.cumsum()
    event_return = event_pnl / event_balance_before.replace(0.0, np.nan)

    sized['balance_before_exit_event'] = sized['exit_time'].map(event_balance_before)
    sized['balance_after_exit_event'] = sized['exit_time'].map(event_balance_after)
    sized['event_return'] = sized['exit_time'].map(event_return).fillna(0.0)
    sized.attrs['initial_capital'] = initial_capital
    sized.attrs['risk_per_trade'] = risk_per_trade
    sized.attrs['account_currency'] = _normalize_text(config.get('account_currency')) or 'USD'
    sized.attrs['commission_model'] = str(config.get('commission_model', 'none') or 'none')
    return sized

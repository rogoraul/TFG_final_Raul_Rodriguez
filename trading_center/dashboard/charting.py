from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from trading_center.dashboard.formatting import safe_float


SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def local_image_data_uri(path_value: Any) -> str:
    chart_path = Path(str(path_value or "").strip())
    if not chart_path.exists() or chart_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        return ""
    mime = "image/jpeg" if chart_path.suffix.lower() in {".jpg", ".jpeg"} else f"image/{chart_path.suffix.lower().lstrip('.')}"
    encoded = base64.b64encode(chart_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def normalized_timestamp(value: Any) -> str:
    return str(value or "").replace("T", " ").strip()[:19]


def compact_time_tick_values(times: list[str], max_ticks: int = 6) -> list[str]:
    if not times:
        return []
    if len(times) <= max_ticks:
        return times
    step = max(1, len(times) // (max_ticks - 1))
    values = times[::step]
    if values[-1] != times[-1]:
        last_selected_index = (len(values) - 1) * step
        if len(times) - 1 - last_selected_index < max(2, step // 2):
            values[-1] = times[-1]
        else:
            values.append(times[-1])
    return values


def compact_time_tick_text(values: list[str]) -> list[str]:
    labels: list[str] = []
    for value in values:
        try:
            parsed = datetime.fromisoformat(value.replace(" ", "T"))
        except ValueError:
            labels.append(value)
            continue
        labels.append(parsed.strftime("%b %d<br>%H:%M"))
    return labels


def rsi_series_from_candles(candles: list[dict[str, Any]], period: int = 14) -> list[float | None]:
    closes: list[float] = []
    for item in candles:
        close = safe_float(item.get("close"))
        closes.append(float("nan") if close is None else close)
    if len(closes) <= period or any(np.isnan(value) for value in closes[: period + 1]):
        return [None for _ in closes]

    output: list[float | None] = [None for _ in closes]
    deltas = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [max(-delta, 0.0) for delta in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def current_rsi(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0
        rs_value = gain / loss
        return 100.0 - (100.0 / (1.0 + rs_value))

    output[period] = round(current_rsi(avg_gain, avg_loss), 2)
    for index in range(period + 1, len(closes)):
        if np.isnan(closes[index]) or np.isnan(closes[index - 1]):
            output[index] = None
            continue
        gain = gains[index - 1]
        loss = losses[index - 1]
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        output[index] = round(current_rsi(avg_gain, avg_loss), 2)
    return output


def ema_series(values: list[float], period: int) -> list[float | None]:
    if len(values) < period or any(np.isnan(value) for value in values[:period]):
        return [None for _ in values]
    output: list[float | None] = [None for _ in values]
    multiplier = 2.0 / (period + 1.0)
    ema_value = sum(values[:period]) / period
    output[period - 1] = ema_value
    for index in range(period, len(values)):
        if np.isnan(values[index]):
            output[index] = None
            continue
        ema_value = ((values[index] - ema_value) * multiplier) + ema_value
        output[index] = ema_value
    return output


def macd_series_from_candles(candles: list[dict[str, Any]], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[list[float | None], list[float | None]]:
    closes: list[float] = []
    for item in candles:
        close = safe_float(item.get("close"))
        closes.append(float("nan") if close is None else close)
    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    macd_values: list[float | None] = []
    for fast_value, slow_value in zip(fast_ema, slow_ema):
        if fast_value is None or slow_value is None:
            macd_values.append(None)
        else:
            macd_values.append(round(fast_value - slow_value, 7))

    signal_values: list[float | None] = [None for _ in macd_values]
    valid_values = [value for value in macd_values if value is not None]
    if len(valid_values) < signal:
        return macd_values, signal_values
    signal_seed = sum(valid_values[:signal]) / signal
    multiplier = 2.0 / (signal + 1.0)
    valid_seen = 0
    signal_value = signal_seed
    for index, macd_value in enumerate(macd_values):
        if macd_value is None:
            continue
        valid_seen += 1
        if valid_seen < signal:
            continue
        if valid_seen == signal:
            signal_values[index] = round(signal_value, 7)
            continue
        signal_value = ((macd_value - signal_value) * multiplier) + signal_value
        signal_values[index] = round(signal_value, 7)
    return macd_values, signal_values


def day_separator_shapes(x_values: list[str]) -> list[dict[str, Any]]:
    shapes: list[dict[str, Any]] = []
    previous_day = ""
    for index, value in enumerate(x_values):
        try:
            parsed = datetime.fromisoformat(value.replace(" ", "T"))
            day = parsed.strftime("%Y-%m-%d")
        except ValueError:
            day = value[:10]
        if index == 0:
            previous_day = day
            continue
        if day and day != previous_day:
            shapes.append(
                {
                    "type": "line",
                    "xref": "x",
                    "yref": "paper",
                    "x0": value,
                    "x1": value,
                    "y0": 0,
                    "y1": 1,
                    "line": {"color": "rgba(150,160,160,.24)", "width": 1},
                    "layer": "below",
                }
            )
        previous_day = day
    return shapes


def annotation_yshifts(prices: list[float]) -> dict[float, int]:
    if not prices:
        return {}
    unique_prices = sorted(set(prices))
    price_span = max(unique_prices) - min(unique_prices)
    min_gap = max(price_span * 0.045, abs(unique_prices[-1]) * 0.00045, 1e-9)
    groups: list[list[float]] = []
    current_group: list[float] = []
    for price in unique_prices:
        if current_group and abs(price - current_group[-1]) > min_gap:
            groups.append(current_group)
            current_group = []
        current_group.append(price)
    if current_group:
        groups.append(current_group)

    shifts: dict[float, int] = {}
    for group in groups:
        middle = (len(group) - 1) / 2
        for index, price in enumerate(group):
            shifts[price] = int((index - middle) * 30)
    return shifts


def last_number(values: list[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None

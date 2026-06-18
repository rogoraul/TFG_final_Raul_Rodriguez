from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


HTF_MAP = {
    "M30": "H1",
    "H1": "H4",
    "H4": "D1",
}


@dataclass(frozen=True)
class WaveContextConfig:
    ema_fast: int = 50
    ema_slow: int = 150
    slope_bars: int = 3
    ewo_fast: int = 5
    ewo_slow: int = 35
    min_alignment_separation_pct: float = 0.00005
    flat_slope_pct: float = 0.00002
    flat_ewo_pct: float = 0.00002
    ewo_method: str = "sma_mid"


def context_config_to_dict(config: WaveContextConfig) -> dict[str, Any]:
    return asdict(config)


def classify_ema_alignment(
    ema_fast: float,
    ema_slow: float,
    reference_price: float,
    *,
    min_separation_pct: float = 0.00005,
) -> str:
    if pd.isna(ema_fast) or pd.isna(ema_slow) or pd.isna(reference_price):
        return "mixed_or_unclear"
    denominator = max(abs(float(reference_price)), abs(float(ema_slow)), 1e-12)
    separation = (float(ema_fast) - float(ema_slow)) / denominator
    if separation > min_separation_pct:
        return "bullish_alignment"
    if separation < -min_separation_pct:
        return "bearish_alignment"
    return "mixed_or_unclear"


def classify_price_vs_band(close: float, ema_fast: float, ema_slow: float) -> str:
    if pd.isna(close) or pd.isna(ema_fast) or pd.isna(ema_slow):
        return "unknown"
    lower = min(float(ema_fast), float(ema_slow))
    upper = max(float(ema_fast), float(ema_slow))
    if float(close) > upper:
        return "above_band"
    if float(close) < lower:
        return "below_band"
    return "inside_band"


def classify_transition(previous_alignment: str, current_alignment: str) -> str:
    if previous_alignment == "bearish_alignment" and current_alignment == "bullish_alignment":
        return "bullish_transition"
    if previous_alignment == "bullish_alignment" and current_alignment == "bearish_alignment":
        return "bearish_transition"
    return "no_transition"


def classify_trend_state(alignment: str, ema_fast_slope_pct: float, ema_slow_slope_pct: float, config: WaveContextConfig) -> str:
    if alignment == "bullish_alignment" and ema_fast_slope_pct >= -config.flat_slope_pct and ema_slow_slope_pct >= -config.flat_slope_pct:
        return "bullish_alignment"
    if alignment == "bearish_alignment" and ema_fast_slope_pct <= config.flat_slope_pct and ema_slow_slope_pct <= config.flat_slope_pct:
        return "bearish_alignment"
    return "mixed_or_unclear"


def calculate_ewo_5_35(frame: pd.DataFrame, config: WaveContextConfig) -> pd.Series:
    if config.ewo_method == "sma_mid":
        mid_price = (pd.to_numeric(frame["high"], errors="coerce") + pd.to_numeric(frame["low"], errors="coerce")) / 2.0
        fast = mid_price.rolling(config.ewo_fast, min_periods=config.ewo_fast).mean()
        slow = mid_price.rolling(config.ewo_slow, min_periods=config.ewo_slow).mean()
        return fast - slow
    if config.ewo_method == "ema_close":
        close = pd.to_numeric(frame["close"], errors="coerce")
        fast = close.ewm(span=config.ewo_fast, adjust=False, min_periods=1).mean()
        slow = close.ewm(span=config.ewo_slow, adjust=False, min_periods=1).mean()
        return fast - slow
    raise ValueError(f"Unsupported ewo_method: {config.ewo_method}")


def _classify_ewo_direction(row: pd.Series, config: WaveContextConfig) -> str:
    value = row.get("ewo_5_35")
    close = row.get("close")
    if pd.isna(value) or pd.isna(close):
        return "flat_or_unknown"
    threshold = abs(float(close)) * config.flat_ewo_pct
    if float(value) > threshold:
        return "positive"
    if float(value) < -threshold:
        return "negative"
    return "flat_or_unknown"


def calculate_wave_context(
    frame: pd.DataFrame,
    *,
    symbol: str = "",
    timeframe: str = "",
    example_id: str = "",
    group: str = "",
    config: WaveContextConfig | None = None,
) -> pd.DataFrame:
    config = config or WaveContextConfig()
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("frame must use a DatetimeIndex")

    df = frame.sort_index().copy()
    close = pd.to_numeric(df["close"], errors="coerce")
    df["ema_50"] = close.ewm(span=config.ema_fast, adjust=False, min_periods=1).mean()
    df["ema_150"] = close.ewm(span=config.ema_slow, adjust=False, min_periods=1).mean()
    df["ema50_slope"] = df["ema_50"] - df["ema_50"].shift(config.slope_bars)
    df["ema150_slope"] = df["ema_150"] - df["ema_150"].shift(config.slope_bars)
    denominator = close.abs().replace(0.0, np.nan)
    df["ema50_slope_pct"] = df["ema50_slope"] / denominator
    df["ema150_slope_pct"] = df["ema150_slope"] / denominator
    df["ema_separation_pct"] = (df["ema_50"] - df["ema_150"]) / denominator
    df["ema_band_width_pct"] = (df["ema_50"] - df["ema_150"]).abs() / denominator
    df["ema_band_width_delta"] = df["ema_band_width_pct"] - df["ema_band_width_pct"].shift(config.slope_bars)
    df["ema_band_state"] = np.select(
        [
            df["ema_band_width_delta"] > config.min_alignment_separation_pct,
            df["ema_band_width_delta"] < -config.min_alignment_separation_pct,
        ],
        ["expanding", "compressing"],
        default="flat_or_unclear",
    )
    df["ewo_5_35"] = calculate_ewo_5_35(df, config)
    df["ewo_5_35_slope"] = df["ewo_5_35"] - df["ewo_5_35"].shift(config.slope_bars)
    df["ewo_5_35_direction"] = df.apply(lambda row: _classify_ewo_direction(row, config), axis=1)
    previous_abs_ewo = df["ewo_5_35"].abs().shift(config.slope_bars)
    df["ewo_5_35_expanding"] = (df["ewo_5_35"].abs() > previous_abs_ewo).fillna(False)

    df["ema_alignment"] = df.apply(
        lambda row: classify_ema_alignment(
            row["ema_50"],
            row["ema_150"],
            row["close"],
            min_separation_pct=config.min_alignment_separation_pct,
        ),
        axis=1,
    )
    df["price_vs_ema_band"] = df.apply(lambda row: classify_price_vs_band(row["close"], row["ema_50"], row["ema_150"]), axis=1)
    previous_alignment = df["ema_alignment"].shift(1).fillna("mixed_or_unclear")
    df["transition_state"] = [
        classify_transition(previous, current)
        for previous, current in zip(previous_alignment, df["ema_alignment"])
    ]
    df["trend_state"] = df.apply(
        lambda row: classify_trend_state(row["ema_alignment"], row["ema50_slope_pct"], row["ema150_slope_pct"], config),
        axis=1,
    )
    df["possible_momentum_confirmation"] = (
        ((df["ewo_5_35_direction"] == "positive") & (df["ewo_5_35_slope"] > 0))
        | ((df["ewo_5_35_direction"] == "negative") & (df["ewo_5_35_slope"] < 0))
    ).fillna(False)
    df["possible_momentum_loss"] = (
        ((df["ewo_5_35_direction"] == "positive") & (df["ewo_5_35_slope"] < 0))
        | ((df["ewo_5_35_direction"] == "negative") & (df["ewo_5_35_slope"] > 0))
    ).fillna(False)

    df = df.reset_index().rename(columns={df.index.name or "index": "timestamp"})
    df["symbol"] = symbol
    df["timeframe"] = timeframe
    df["example_id"] = example_id
    df["group"] = group
    ordered = [
        "example_id",
        "group",
        "symbol",
        "timeframe",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "ema_50",
        "ema_150",
        "ema_alignment",
        "trend_state",
        "transition_state",
        "price_vs_ema_band",
        "ema50_slope",
        "ema150_slope",
        "ema50_slope_pct",
        "ema150_slope_pct",
        "ema_separation_pct",
        "ema_band_width_pct",
        "ema_band_state",
        "ewo_5_35",
        "ewo_5_35_slope",
        "ewo_5_35_direction",
        "ewo_5_35_expanding",
        "possible_momentum_confirmation",
        "possible_momentum_loss",
    ]
    return df[[column for column in ordered if column in df.columns]]


def prepare_htf_context_for_alignment(htf_context: pd.DataFrame, htf_timeframe: str) -> pd.DataFrame:
    if htf_context.empty:
        return pd.DataFrame()
    context_columns = [
        "ema_alignment",
        "trend_state",
        "transition_state",
        "price_vs_ema_band",
        "ema50_slope_pct",
        "ema150_slope_pct",
        "ema_separation_pct",
        "ema_band_width_pct",
        "ema_band_state",
        "ewo_5_35",
        "ewo_5_35_slope",
        "ewo_5_35_direction",
        "ewo_5_35_expanding",
        "possible_momentum_confirmation",
        "possible_momentum_loss",
    ]
    aligned = htf_context[["timestamp"] + [column for column in context_columns if column in htf_context.columns]].copy()
    aligned["htf_context_source_time"] = htf_context["timestamp"].shift(1)
    for column in context_columns:
        if column in aligned.columns:
            aligned[column] = aligned[column].shift(1)
    aligned["htf_timeframe"] = htf_timeframe
    rename = {
        column: f"htf_{column}"
        for column in context_columns
        if column in aligned.columns
    }
    return aligned.rename(columns=rename)


def align_htf_context(ltf_context: pd.DataFrame, htf_context: pd.DataFrame, *, htf_timeframe: str) -> pd.DataFrame:
    ltf = ltf_context.sort_values("timestamp").copy()
    if htf_context.empty:
        ltf["htf_timeframe"] = htf_timeframe
        ltf["htf_context_source_time"] = pd.NaT
        ltf["htf_lookahead_safe"] = True
        return ltf

    htf_ready = prepare_htf_context_for_alignment(htf_context.sort_values("timestamp"), htf_timeframe)
    merged = pd.merge_asof(ltf, htf_ready.sort_values("timestamp"), on="timestamp", direction="backward")
    merged["htf_lookahead_safe"] = (
        merged["htf_context_source_time"].isna()
        | (pd.to_datetime(merged["htf_context_source_time"]) <= pd.to_datetime(merged["timestamp"]))
    )
    return merged


def context_row_at(context: pd.DataFrame, timestamp: Any) -> pd.Series | None:
    if context.empty or pd.isna(timestamp):
        return None
    target = pd.to_datetime(timestamp)
    subset = context[pd.to_datetime(context["timestamp"]) <= target].sort_values("timestamp")
    if subset.empty:
        return None
    return subset.iloc[-1]


def direction_matches(direction: str, alignment: str) -> bool:
    if direction == "bullish":
        return alignment == "bullish_alignment"
    if direction == "bearish":
        return alignment == "bearish_alignment"
    return False


def direction_conflicts(direction: str, alignment: str) -> bool:
    if direction == "bullish":
        return alignment == "bearish_alignment"
    if direction == "bearish":
        return alignment == "bullish_alignment"
    return False


def transition_matches(direction: str, transition: str) -> bool:
    if direction == "bullish":
        return transition == "bullish_transition"
    if direction == "bearish":
        return transition == "bearish_transition"
    return False


def momentum_matches(direction: str, row: pd.Series | None) -> bool:
    if row is None:
        return False
    ewo = row.get("ewo_5_35")
    slope = row.get("ewo_5_35_slope")
    if pd.isna(ewo) or pd.isna(slope):
        return False
    if direction == "bullish":
        return float(ewo) > 0 and float(slope) >= 0
    if direction == "bearish":
        return float(ewo) < 0 and float(slope) <= 0
    return False


def price_band_matches(direction: str, band: str) -> bool:
    if direction == "bullish":
        return band == "above_band"
    if direction == "bearish":
        return band == "below_band"
    return False


def summarize_context(row: pd.Series | None, *, htf: bool = False) -> str:
    if row is None:
        return "missing_context"
    prefix = "htf_" if htf else ""
    trend = row.get(f"{prefix}trend_state", row.get("trend_state", ""))
    band = row.get(f"{prefix}price_vs_ema_band", row.get("price_vs_ema_band", ""))
    transition = row.get(f"{prefix}transition_state", row.get("transition_state", ""))
    ewo = row.get(f"{prefix}ewo_5_35_direction", row.get("ewo_5_35_direction", ""))
    return f"trend={trend}|band={band}|transition={transition}|ewo={ewo}"


def classify_candidate_context(candidate: pd.Series, start_row: pd.Series | None, end_row: pd.Series | None) -> dict[str, Any]:
    direction = str(candidate.get("direction", ""))
    if end_row is None:
        return {
            "trend_context_label": "unclear_context",
            "context_score": 0,
            "context_reason": "missing end context",
        }

    ltf_alignment = str(end_row.get("ema_alignment", "mixed_or_unclear"))
    ltf_transition = str(end_row.get("transition_state", "no_transition"))
    htf_alignment = str(end_row.get("htf_ema_alignment", "mixed_or_unclear"))
    htf_transition = str(end_row.get("htf_transition_state", "no_transition"))
    htf_available = not pd.isna(end_row.get("htf_context_source_time", pd.NaT))

    ltf_match = direction_matches(direction, ltf_alignment)
    htf_match = direction_matches(direction, htf_alignment) if htf_available else False
    ltf_conflict = direction_conflicts(direction, ltf_alignment)
    htf_conflict = direction_conflicts(direction, htf_alignment) if htf_available else False
    transition_match = transition_matches(direction, ltf_transition) or transition_matches(direction, htf_transition)
    band_match = price_band_matches(direction, str(end_row.get("price_vs_ema_band", "")))
    momentum_match = momentum_matches(direction, end_row)

    if htf_match and (ltf_match or transition_match):
        label = "impulse_with_htf"
    elif htf_conflict and (ltf_match or transition_match or momentum_match):
        label = "correction_against_htf"
    elif transition_match:
        label = "transition_structure"
    elif htf_conflict or ltf_conflict:
        label = "conflict_with_htf"
    else:
        label = "unclear_context"

    score = 0
    score += 25 if htf_match else 0
    score += 20 if ltf_match else 0
    score += 15 if transition_match else 0
    score += 15 if band_match else 0
    score += 20 if momentum_match else 0
    score += 5 if str(end_row.get("ema_band_state", "")) == "expanding" else 0
    if htf_conflict and not label == "correction_against_htf":
        score -= 15
    score = max(0, min(100, score))

    reasons = []
    if htf_match:
        reasons.append("HTF aligned with candidate direction")
    if htf_conflict:
        reasons.append("HTF conflicts with candidate direction")
    if ltf_match:
        reasons.append("LTF EMA alignment matches candidate")
    if transition_match:
        reasons.append("transition matches candidate direction")
    if momentum_match:
        reasons.append("EWO 5-35 confirms direction")
    if not reasons:
        reasons.append("context unclear")

    return {
        "trend_context_label": label,
        "context_score": score,
        "context_reason": "; ".join(reasons),
        "ltf_direction_match": ltf_match,
        "htf_direction_match": htf_match,
        "ltf_direction_conflict": ltf_conflict,
        "htf_direction_conflict": htf_conflict,
        "transition_matches_direction": transition_match,
        "price_band_matches_direction": band_match,
        "momentum_matches_direction": momentum_match,
        "context_at_start": summarize_context(start_row, htf=False),
        "context_at_end": summarize_context(end_row, htf=False),
        "htf_context_at_end": summarize_context(end_row, htf=True),
    }


def build_candidate_context(candidates: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, candidate in candidates.iterrows():
        example_context = context[context["example_id"] == candidate["example_id"]].copy()
        start_row = context_row_at(example_context, candidate.get("start_time"))
        end_row = context_row_at(example_context, candidate.get("end_time"))
        classified = classify_candidate_context(candidate, start_row, end_row)
        base = candidate.to_dict()
        base.update(classified)
        if end_row is not None:
            base.update(
                {
                    "end_ltf_trend_state": end_row.get("trend_state", ""),
                    "end_ltf_ema_alignment": end_row.get("ema_alignment", ""),
                    "end_ltf_price_vs_ema_band": end_row.get("price_vs_ema_band", ""),
                    "end_ltf_transition_state": end_row.get("transition_state", ""),
                    "end_ltf_ewo_5_35": end_row.get("ewo_5_35", np.nan),
                    "end_ltf_ewo_5_35_slope": end_row.get("ewo_5_35_slope", np.nan),
                    "end_ltf_ewo_5_35_direction": end_row.get("ewo_5_35_direction", ""),
                    "htf_timeframe": end_row.get("htf_timeframe", ""),
                    "htf_context_source_time": end_row.get("htf_context_source_time", pd.NaT),
                    "htf_trend_state": end_row.get("htf_trend_state", ""),
                    "htf_ema_alignment": end_row.get("htf_ema_alignment", ""),
                    "htf_price_vs_ema_band": end_row.get("htf_price_vs_ema_band", ""),
                    "htf_transition_state": end_row.get("htf_transition_state", ""),
                    "htf_lookahead_safe": bool(end_row.get("htf_lookahead_safe", True)),
                }
            )
        rows.append(base)
    return pd.DataFrame(rows)

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StructuralPivotConfig:
    """Configuration for WaveCount Phase 1.5 structural pivots.

    This layer compresses raw causal pivots into larger alternating swings. It
    does not count Elliott waves and it does not produce trading signals.
    """

    min_leg_atr_multiplier: float = 3.0
    min_leg_relative_move_pct: float = 0.003
    min_leg_bars: int = 6
    allow_first_pivot: bool = True

    def __post_init__(self) -> None:
        if self.min_leg_atr_multiplier < 0:
            raise ValueError("min_leg_atr_multiplier must be >= 0")
        if self.min_leg_relative_move_pct < 0:
            raise ValueError("min_leg_relative_move_pct must be >= 0")
        if self.min_leg_bars < 0:
            raise ValueError("min_leg_bars must be >= 0")


def _coerce_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def _timeframe_to_minutes(timeframe: str) -> int | None:
    mapping = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
    }
    return mapping.get(str(timeframe).upper())


def _normalise_raw_pivots(raw_pivots: pd.DataFrame) -> pd.DataFrame:
    if raw_pivots is None or raw_pivots.empty:
        return pd.DataFrame()

    df = raw_pivots.copy()
    for column in ["timestamp", "pivot_extreme_time", "pivot_detected_at"]:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")

    if "is_confirmed" in df.columns:
        df = df[_coerce_bool(df["is_confirmed"])]
    elif "pivot_state" in df.columns:
        df = df[df["pivot_state"].isin(["confirmed_high", "confirmed_low"])]

    if df.empty:
        return df

    required = ["pivot_type", "pivot_extreme_time", "pivot_detected_at", "pivot_extreme_price"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"missing raw pivot columns: {missing}")

    df = df[df["pivot_type"].isin(["high", "low"])].copy()
    df["pivot_extreme_price"] = pd.to_numeric(df["pivot_extreme_price"], errors="coerce")
    if "atr" in df.columns:
        df["atr"] = pd.to_numeric(df["atr"], errors="coerce")
    else:
        df["atr"] = np.nan
    df = df.dropna(subset=["pivot_extreme_time", "pivot_detected_at", "pivot_extreme_price"])
    df = df.sort_values(["pivot_detected_at", "pivot_extreme_time", "pivot_type"]).reset_index(drop=True)
    df["raw_pivot_id"] = np.arange(1, len(df) + 1)
    return df


def _is_more_extreme(new_row: pd.Series, old_row: dict[str, Any]) -> bool:
    if new_row["pivot_type"] == "high":
        return float(new_row["pivot_extreme_price"]) > float(old_row["pivot_extreme_price"])
    return float(new_row["pivot_extreme_price"]) < float(old_row["pivot_extreme_price"])


def _leg_metrics(previous: dict[str, Any], current: pd.Series, config: StructuralPivotConfig) -> dict[str, Any]:
    previous_price = float(previous["pivot_extreme_price"])
    current_price = float(current["pivot_extreme_price"])
    move_abs = abs(current_price - previous_price)
    reference_price = max(abs(previous_price), 1e-12)
    move_pct = move_abs / reference_price

    atr_values = [
        float(value)
        for value in [previous.get("atr"), current.get("atr")]
        if value is not None and not pd.isna(value) and float(value) > 0
    ]
    atr_reference = float(np.mean(atr_values)) if atr_values else np.nan
    move_atr = move_abs / atr_reference if atr_reference and not pd.isna(atr_reference) else np.nan

    timeframe = current.get("timeframe") or previous.get("timeframe")
    minutes = _timeframe_to_minutes(str(timeframe))
    time_delta = pd.Timestamp(current["pivot_extreme_time"]) - pd.Timestamp(previous["pivot_extreme_time"])
    bars = time_delta.total_seconds() / 60.0 / minutes if minutes else np.nan
    bars_abs = abs(float(bars)) if not pd.isna(bars) else np.nan

    atr_pass = bool(not pd.isna(move_atr) and move_atr >= config.min_leg_atr_multiplier)
    pct_pass = bool(move_pct >= config.min_leg_relative_move_pct)
    bars_pass = bool(pd.isna(bars_abs) or bars_abs >= config.min_leg_bars)
    visible = (atr_pass or pct_pass) and bars_pass

    return {
        "leg_move_abs": move_abs,
        "leg_move_pct": move_pct,
        "leg_move_atr": move_atr,
        "bars_from_previous": bars_abs,
        "atr_pass": atr_pass,
        "pct_pass": pct_pass,
        "bars_pass": bars_pass,
        "visible": visible,
    }


def _base_output_row(row: pd.Series, state: str, reason: str) -> dict[str, Any]:
    return {
        "example_id": row.get("example_id", ""),
        "group": row.get("group", ""),
        "symbol": row.get("symbol", ""),
        "timeframe": row.get("timeframe", ""),
        "example_type": row.get("example_type", ""),
        "raw_pivot_id": int(row["raw_pivot_id"]),
        "structure_state": state,
        "pivot_type": row["pivot_type"],
        "pivot_extreme_time": row["pivot_extreme_time"],
        "pivot_detected_at": row["pivot_detected_at"],
        "pivot_extreme_price": float(row["pivot_extreme_price"]),
        "atr": float(row["atr"]) if not pd.isna(row["atr"]) else np.nan,
        "structural_detected_at": row["pivot_detected_at"],
        "reason": reason,
    }


def _mark_structural_ids(structural_rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(structural_rows)
    if frame.empty:
        return frame
    frame = frame.sort_values(["structural_detected_at", "pivot_extreme_time", "raw_pivot_id"]).reset_index(drop=True)
    frame["structural_pivot_id"] = np.arange(1, len(frame) + 1)
    frame["previous_structural_pivot_id"] = frame["structural_pivot_id"].shift(1)
    return frame


def build_structural_pivots(
    raw_pivots: pd.DataFrame,
    config: StructuralPivotConfig | None = None,
) -> dict[str, pd.DataFrame]:
    """Build alternating major swings from confirmed causal pivots.

    The function is causal in event time: replacement or acceptance decisions are
    timestamped at the raw pivot detection time that made the decision possible.
    """

    config = config or StructuralPivotConfig()
    confirmed = _normalise_raw_pivots(raw_pivots)
    if confirmed.empty:
        empty = pd.DataFrame()
        return {
            "structural_pivots": empty,
            "discarded_minor_pivots": empty,
            "structure_summary": pd.DataFrame(
                [
                    {
                        "raw_confirmed_pivots": 0,
                        "structural_pivots": 0,
                        "discarded_minor_pivots": 0,
                        "ambiguous_structure": 0,
                        "compression_ratio": np.nan,
                    }
                ]
            ),
        }

    structural_rows: list[dict[str, Any]] = []
    discarded_rows: list[dict[str, Any]] = []

    for _, row in confirmed.iterrows():
        if not structural_rows:
            if not config.allow_first_pivot:
                discarded_rows.append(_base_output_row(row, "ambiguous_structure", "first pivot held until structure starts"))
                continue
            base = _base_output_row(row, "structural_pivot", "initial structural pivot")
            base.update(
                {
                    "leg_move_abs": np.nan,
                    "leg_move_pct": np.nan,
                    "leg_move_atr": np.nan,
                    "bars_from_previous": np.nan,
                    "replacement_of_raw_pivot_id": np.nan,
                }
            )
            structural_rows.append(base)
            continue

        last = structural_rows[-1]
        same_type = row["pivot_type"] == last["pivot_type"]
        if same_type:
            if _is_more_extreme(row, last):
                replaced = last.copy()
                replaced["structure_state"] = "discarded_minor_pivot"
                replaced["reason"] = "superseded by more extreme same-type pivot"
                replaced["replaced_by_raw_pivot_id"] = int(row["raw_pivot_id"])
                discarded_rows.append(replaced)

                replacement = _base_output_row(row, "structural_pivot", "more extreme same-type pivot replaces previous structural pivot")
                replacement.update(
                    {
                        "leg_move_abs": last.get("leg_move_abs", np.nan),
                        "leg_move_pct": last.get("leg_move_pct", np.nan),
                        "leg_move_atr": last.get("leg_move_atr", np.nan),
                        "bars_from_previous": last.get("bars_from_previous", np.nan),
                        "replacement_of_raw_pivot_id": int(last["raw_pivot_id"]),
                    }
                )
                structural_rows[-1] = replacement
            else:
                discarded = _base_output_row(row, "discarded_minor_pivot", "less extreme same-type pivot")
                discarded["replaced_by_raw_pivot_id"] = int(last["raw_pivot_id"])
                discarded_rows.append(discarded)
            continue

        metrics = _leg_metrics(last, row, config)
        if not metrics["visible"]:
            reason_parts = []
            if not (metrics["atr_pass"] or metrics["pct_pass"]):
                reason_parts.append("leg below ATR/relative structural threshold")
            if not metrics["bars_pass"]:
                reason_parts.append("leg too close in bars")
            discarded = _base_output_row(row, "ambiguous_structure", "; ".join(reason_parts) or "ambiguous structure")
            discarded.update({key: metrics[key] for key in ["leg_move_abs", "leg_move_pct", "leg_move_atr", "bars_from_previous"]})
            discarded["previous_raw_pivot_id"] = int(last["raw_pivot_id"])
            discarded_rows.append(discarded)
            continue

        accepted = _base_output_row(row, "structural_pivot", "opposite-type pivot passes structural leg filter")
        accepted.update({key: metrics[key] for key in ["leg_move_abs", "leg_move_pct", "leg_move_atr", "bars_from_previous"]})
        accepted["replacement_of_raw_pivot_id"] = np.nan
        structural_rows.append(accepted)

    structural = _mark_structural_ids(structural_rows)
    discarded = pd.DataFrame(discarded_rows)
    if not discarded.empty:
        discarded = discarded.sort_values(["structural_detected_at", "pivot_extreme_time", "raw_pivot_id"]).reset_index(drop=True)

    ambiguous_count = int((discarded["structure_state"] == "ambiguous_structure").sum()) if not discarded.empty else 0
    minor_count = int((discarded["structure_state"] == "discarded_minor_pivot").sum()) if not discarded.empty else 0
    summary = pd.DataFrame(
        [
            {
                "raw_confirmed_pivots": len(confirmed),
                "structural_pivots": len(structural),
                "discarded_minor_pivots": minor_count,
                "ambiguous_structure": ambiguous_count,
                "compression_ratio": len(structural) / len(confirmed) if len(confirmed) else np.nan,
                "min_leg_atr_multiplier": config.min_leg_atr_multiplier,
                "min_leg_relative_move_pct": config.min_leg_relative_move_pct,
                "min_leg_bars": config.min_leg_bars,
            }
        ]
    )

    return {
        "structural_pivots": structural,
        "discarded_minor_pivots": discarded,
        "structure_summary": summary,
    }


def build_structural_pivots_by_group(
    raw_pivots: pd.DataFrame,
    config: StructuralPivotConfig | None = None,
    group_columns: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    config = config or StructuralPivotConfig()
    group_columns = group_columns or ["example_id"]
    confirmed = _normalise_raw_pivots(raw_pivots)
    if confirmed.empty:
        return build_structural_pivots(confirmed, config)

    structural_frames = []
    discarded_frames = []
    summary_frames = []

    for group_values, group_df in confirmed.groupby(group_columns, dropna=False, sort=False):
        result = build_structural_pivots(group_df, config)
        structural_frames.append(result["structural_pivots"])
        discarded_frames.append(result["discarded_minor_pivots"])
        summary = result["structure_summary"].copy()
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        for column, value in zip(group_columns, group_values):
            summary[column] = value
        summary_frames.append(summary)

    non_empty_structural = [frame for frame in structural_frames if not frame.empty]
    non_empty_discarded = [frame for frame in discarded_frames if not frame.empty]
    structural = pd.concat(non_empty_structural, ignore_index=True) if non_empty_structural else pd.DataFrame()
    discarded = pd.concat(non_empty_discarded, ignore_index=True) if non_empty_discarded else pd.DataFrame()
    summary = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    return {
        "structural_pivots": structural,
        "discarded_minor_pivots": discarded,
        "structure_summary": summary,
    }


def structural_config_to_dict(config: StructuralPivotConfig) -> dict[str, Any]:
    return asdict(config)

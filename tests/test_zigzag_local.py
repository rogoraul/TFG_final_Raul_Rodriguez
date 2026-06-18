"""Smoke tests for the vendored/local zigzag package."""

from __future__ import annotations

import numpy as np

from zigzag import max_drawdown, peak_valley_pivots, pivots_to_modes


def test_zigzag_local_package_smoke() -> None:
    prices = np.array([10, 12, 11, 14, 13, 16, 10, 5, 8, 4, 1])

    pivots = peak_valley_pivots(prices, 0.2, -0.2)
    modes = pivots_to_modes(pivots)
    drawdown = max_drawdown(prices)

    assert len(pivots) == len(prices)
    assert len(modes) == len(prices)
    assert np.count_nonzero(pivots) > 0
    assert drawdown >= 0

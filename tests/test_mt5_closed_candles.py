import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from data.mt5.closed_candles import remove_open_candles_with_server_time
from data.mt5 import historical_loader, updater


class TestMt5ClosedCandles(unittest.TestCase):
    def _frame(self):
        return pd.DataFrame({
            "time": pd.to_datetime([
                "2026-05-16 08:00:00",
                "2026-05-16 09:00:00",
            ]),
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.1, 1.2],
        })

    def test_removes_last_candle_when_server_time_is_before_close(self):
        result = remove_open_candles_with_server_time(
            self._frame(),
            "H1",
            pd.Timestamp("2026-05-16 09:30:00"),
            verbose=False,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[-1]["time"], pd.Timestamp("2026-05-16 08:00:00"))

    def test_keeps_last_candle_when_server_time_reaches_close(self):
        result = remove_open_candles_with_server_time(
            self._frame(),
            "H1",
            pd.Timestamp("2026-05-16 10:00:00"),
            verbose=False,
        )

        self.assertEqual(len(result), 2)

    def test_unknown_timeframe_keeps_data_unchanged(self):
        frame = self._frame()

        result = remove_open_candles_with_server_time(
            frame,
            "UNKNOWN",
            pd.Timestamp("2026-05-16 09:30:00"),
            verbose=False,
        )

        self.assertIs(result, frame)

    def test_updater_wrapper_uses_mt5_server_time(self):
        with patch(
            "data.mt5.updater.mt5.symbol_info_tick",
            return_value=SimpleNamespace(time=pd.Timestamp("2026-05-16 09:30:00").timestamp()),
        ), patch("builtins.print"):
            result = updater.remove_open_candles(
                self._frame(),
                updater.mt5.TIMEFRAME_H1,
                "EURUSD",
            )

        self.assertEqual(len(result), 1)

    def test_historical_loader_wrapper_uses_mt5_server_time(self):
        with patch(
            "data.mt5.historical_loader.mt5.symbol_info_tick",
            return_value=SimpleNamespace(time=pd.Timestamp("2026-05-16 09:30:00").timestamp()),
        ), patch("builtins.print"):
            result = historical_loader.remove_open_candles(
                self._frame(),
                "H1",
                "EURUSD",
            )

        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()

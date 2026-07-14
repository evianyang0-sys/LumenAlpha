import sys
import types
import unittest

import pandas as pd


sys.modules.setdefault("akshare", types.ModuleType("akshare"))

from lumen_qlib.sector_rotation_pipeline import (  # noqa: E402
    STOCK_MARKER_DAYS,
    build_stock_charts,
)


class SectorRotationMarkerTest(unittest.TestCase):
    def test_stock_chart_keeps_significant_signals_from_twenty_trading_days(self):
        dates = pd.date_range("2026-01-01", periods=30, freq="B")
        close = [100.0] * 30
        close[10] = 108.0
        close[25] = 108.0
        frame = pd.DataFrame(
            {
                "日期": dates,
                "开盘": [100.0] * 30,
                "最高": [value * 1.01 for value in close],
                "最低": [value * 0.99 for value in close],
                "收盘": close,
                "成交量": [100.0] * 30,
            }
        )

        charts = build_stock_charts(
            pd.DataFrame({"code": ["000001"]}),
            {"000001": frame},
            pd.DataFrame(),
            chart_days=30,
            marker_days=5,
        )
        old_signal_date = dates[10].strftime("%Y-%m-%d")

        self.assertEqual(20, STOCK_MARKER_DAYS)
        self.assertTrue(any(row["date"] == old_signal_date for row in charts["000001"]["markers"]))


if __name__ == "__main__":
    unittest.main()

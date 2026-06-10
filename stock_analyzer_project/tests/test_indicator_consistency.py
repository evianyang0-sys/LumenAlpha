import unittest

import numpy as np
import pandas as pd

from stock_analyzer_project.backtest import calculate_basic_indicators
from stock_analyzer_project.indicator_engine import INDICATOR_SPECS
from stock_analyzer_project.indicators import IndicatorCalculator
from stock_analyzer_project.indicators import LegacyIndicatorCalculator


def sample_prices(size=260):
    index = np.arange(size, dtype=float)
    close = 20 + index * 0.03 + np.sin(index / 7) * 1.5
    return pd.DataFrame(
        {
            "日期": pd.date_range("2025-01-01", periods=size, freq="D"),
            "开盘": close - 0.1,
            "收盘": close,
            "最高": close + 0.8,
            "最低": close - 0.7,
            "成交量": 100000 + index * 100 + (index % 9) * 500,
        }
    )


class IndicatorConsistencyTest(unittest.TestCase):
    def test_backtest_uses_canonical_values(self):
        prices = sample_prices()
        canonical = IndicatorCalculator.calculate_all(prices)
        backtest = calculate_basic_indicators(prices)
        columns = [
            "MA5",
            "EMA20",
            "AO",
            "BBD",
            "DIF",
            "DEA",
            "MACD",
            "RSI",
            "K",
            "D",
            "J",
            "CCI",
            "ATR",
            "VWAP",
        ]
        for column in columns:
            pd.testing.assert_series_equal(
                canonical[column],
                backtest[column],
                check_names=False,
            )

    def test_legacy_entry_points_are_forced_to_canonical_engine(self):
        prices = sample_prices()
        canonical = IndicatorCalculator.calculate_all(prices)
        legacy_entry = LegacyIndicatorCalculator.calculate_all(prices)
        pd.testing.assert_series_equal(
            canonical["RSI"],
            legacy_entry["RSI"],
            check_names=False,
        )
        pd.testing.assert_series_equal(
            canonical["AO"],
            legacy_entry["AO"],
            check_names=False,
        )

    def test_ao_uses_median_price_and_5_34_periods(self):
        prices = sample_prices(50)
        result = IndicatorCalculator.calculate_all(prices)
        median = (prices["最高"] + prices["最低"]) / 2
        expected = median.rolling(5).mean() - median.rolling(34).mean()
        pd.testing.assert_series_equal(result["AO"], expected, check_names=False)

    def test_vwap_uses_typical_price(self):
        prices = sample_prices(20)
        result = IndicatorCalculator.calculate_all(prices)
        typical = (prices["最高"] + prices["最低"] + prices["收盘"]) / 3
        expected = (typical * prices["成交量"]).cumsum() / prices["成交量"].cumsum()
        pd.testing.assert_series_equal(result["VWAP"], expected, check_names=False)

    def test_indicator_registry_documents_custom_bbd(self):
        self.assertIn("project-defined", INDICATOR_SPECS["BBD"]["source"])
        self.assertIn("daily cumulative", INDICATOR_SPECS["VWAP"]["source"])


if __name__ == "__main__":
    unittest.main()

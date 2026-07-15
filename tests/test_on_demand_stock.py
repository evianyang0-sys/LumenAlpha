import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts.on_demand_stock import (
    StockLookupError,
    calculate_stock,
    lumen_percentile,
    rank_price_feature,
    resolve_stock,
)


class OnDemandStockTest(unittest.TestCase):
    def test_resolve_stock_accepts_exact_name_and_code(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ranks = root / "ranks.csv"
            detail = root / "detail.csv"
            pd.DataFrame(
                [
                    {"code": "601138", "name": "工业富联", "rank": 38, "market_all_count": 5530},
                    {"code": "000001", "name": "平安银行", "rank": 120, "market_all_count": 5530},
                ]
            ).to_csv(ranks, index=False)
            pd.DataFrame(
                [
                    {
                        "code": "601138",
                        "name": "工业富联",
                        "board_l1": "科技",
                        "board_l2": "AI算力与数据中心",
                        "board_l3": "算力服务器",
                        "board_path": "科技>AI算力与数据中心>算力服务器",
                    }
                ]
            ).to_csv(detail, index=False)

            by_name = resolve_stock("工业富联", ranks, detail)
            by_code = resolve_stock("601138", ranks, detail)

            self.assertEqual("601138", by_name["code"])
            self.assertEqual("算力服务器", by_name["board_l3"])
            self.assertEqual("工业富联", by_code["name"])

    def test_resolve_stock_rejects_ambiguous_partial_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ranks = root / "ranks.csv"
            detail = root / "detail.csv"
            pd.DataFrame(
                [
                    {"code": "000001", "name": "测试科技一", "rank": 1},
                    {"code": "000002", "name": "测试科技二", "rank": 2},
                ]
            ).to_csv(ranks, index=False)
            pd.DataFrame(columns=["code", "name"]).to_csv(detail, index=False)

            with self.assertRaises(StockLookupError) as context:
                resolve_stock("测试科技", ranks, detail)

            self.assertEqual(2, len(context.exception.candidates))

    def test_rank_price_feature_uses_reference_universe(self):
        raw = {
            "code": "601138",
            "close": 30.0,
            "ret_1d": 0.02,
            "ret_5d": 0.20,
            "ret_20d": 0.30,
            "ma20_bias": 0.10,
            "volume_ratio_20": 2.0,
            "volatility_20": 0.02,
        }
        reference = pd.DataFrame(
            [
                {"code": "000001", "ret_5d": -0.1, "ret_20d": -0.2, "ma20_bias": -0.1, "volume_ratio_20": 0.5, "volatility_20": 0.08},
                {"code": "000002", "ret_5d": 0.0, "ret_20d": 0.0, "ma20_bias": 0.0, "volume_ratio_20": 1.0, "volatility_20": 0.05},
            ]
        )

        ranked = rank_price_feature(raw, reference)

        self.assertGreater(ranked["qlib_factor_score"], 80)
        self.assertEqual(100.0, ranked["qlib_mom_20_rank"])

    def test_lumen_percentile_replaces_existing_target_snapshot(self):
        reference = pd.DataFrame(
            [
                {"code": "601138", "lumen_score": 100.0},
                {"code": "000001", "lumen_score": 0.0},
            ]
        )

        self.assertEqual(100.0, lumen_percentile(10.0, reference, "601138"))

    def test_calculate_stock_returns_dashboard_compatible_payload(self):
        dates = pd.date_range("2026-01-01", periods=90, freq="B")
        closes = [20 + index * 0.1 for index in range(90)]
        history = pd.DataFrame(
            {
                "日期": dates,
                "开盘": [value - 0.05 for value in closes],
                "最高": [value + 0.2 for value in closes],
                "最低": [value - 0.2 for value in closes],
                "收盘": closes,
                "成交量": [1_000_000 + index * 1000 for index in range(90)],
                "涨跌幅": pd.Series(closes).pct_change().fillna(0) * 100,
            }
        )
        stock = {
            "code": "601138",
            "name": "工业富联",
            "rank": 38,
            "market_all_count": 5530,
            "board_l1": "科技",
            "board_l2": "AI算力与数据中心",
            "board_l3": "算力服务器",
            "board_path": "科技>AI算力与数据中心>算力服务器",
        }
        reference = pd.DataFrame(
            [
                {"code": "000001", "ret_5d": -0.05, "ret_20d": -0.1, "ma20_bias": -0.03, "volume_ratio_20": 0.8, "volatility_20": 0.05, "lumen_score": 1.0},
                {"code": "000002", "ret_5d": 0.01, "ret_20d": 0.02, "ma20_bias": 0.01, "volume_ratio_20": 1.1, "volatility_20": 0.03, "lumen_score": 2.0},
            ]
        )
        sectors = pd.DataFrame(
            [
                {
                    "board_path": stock["board_path"],
                    "sector_ret_5d": 0.03,
                    "sector_ret_20d": 0.08,
                    "sector_trend_score": 72.0,
                }
            ]
        )
        lumen_summary = pd.DataFrame([{"code": "601138", "lumen_score": 3.0, "lumen_rating": "偏多", "lumen_signal_count": 1}])

        with patch("scripts.on_demand_stock.build_lumen_signal_rows", return_value=([], lumen_summary)):
            payload = calculate_stock(stock, history, "fixture", reference, sectors)

        self.assertTrue(payload["ok"])
        self.assertEqual("工业富联", payload["leader"]["name"])
        self.assertTrue(payload["leader"]["on_demand"])
        self.assertEqual(30, len(payload["chart"]["candles"]))
        self.assertGreater(len(payload["signals"]), 0)
        self.assertTrue(payload["quality"]["components"]["sector"])
        self.assertEqual({payload["latestDate"]}, {row["date"] for row in payload["signals"]})

    def test_script_can_run_directly_from_the_repository(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "scripts/on_demand_stock.py"), "--query", "ZZZZ_NOT_A_STOCK"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual("NOT_FOUND", json.loads(result.stdout)["errorCode"])


if __name__ == "__main__":
    unittest.main()

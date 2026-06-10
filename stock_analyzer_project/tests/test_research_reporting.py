import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from stock_analyzer_project.indicators import IndicatorCalculator
from stock_analyzer_project.research_reporting import save_research_report


class ResearchReportingTest(unittest.TestCase):
    def test_generates_explainable_stock_sections(self):
        index = np.arange(260, dtype=float)
        close = 20 + index * 0.05 + np.sin(index / 8)
        frame = pd.DataFrame(
            {
                "日期": pd.date_range("2025-01-01", periods=260),
                "开盘": close - 0.1,
                "收盘": close,
                "最高": close + 0.5,
                "最低": close - 0.5,
                "成交量": 100000 + index * 100,
            }
        )
        frame = IndicatorCalculator.calculate_all(frame)
        result = {
            "代码": "300308",
            "名称": "中际旭创",
            "板块": "光模块",
            "日期": "2026-06-09",
            "signals": [],
            "df": frame,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "research.html"
            save_research_report([result], "2026-06-10", path)
            html = path.read_text(encoding="utf-8")
        self.assertIn("综合判断", html)
        self.assertIn("支持因素", html)
        self.assertIn("判断失效", html)
        self.assertIn("光模块", html)
        self.assertIn("LumenAlpha 行业研究报告", html)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from stock_analyzer_project.reporting import save_backtest_report, save_daily_report


class ReportingTest(unittest.TestCase):
    def test_generates_separate_html_reports(self):
        backtest = {
            "信号_RSI超卖": {
                "3日": {
                    "signal": "RSI超卖",
                    "days": 3,
                    "count": 20,
                    "win_rate": 60.0,
                    "avg_return": 1.2,
                    "max_return": 8.0,
                    "min_return": -4.0,
                    "signal_type": "buy",
                    "category": "短线",
                }
            }
        }
        daily = [
            {
                "代码": "300750",
                "名称": "宁德时代",
                "板块": "新能源电池",
                "日期": "2026-06-09",
                "收盘": 250.0,
                "涨跌": 2.0,
                "得分": 72,
                "评级": "偏多",
                "信号": "MACD金叉",
                "数据源": "test",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            backtest_path = Path(directory) / "backtest.html"
            daily_path = Path(directory) / "daily.html"
            save_backtest_report(backtest, "300750", "宁德时代", "test", backtest_path)
            save_daily_report(daily, "2026-06-09", daily_path)
            self.assertIn("LumenAlpha 回测报告", backtest_path.read_text(encoding="utf-8"))
            self.assertIn("LumenAlpha 天级报告", daily_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from stock_analyzer_project.guide_report import parse_stock_pool


class GuideReportTest(unittest.TestCase):
    def test_parses_only_focus_pool_tables(self):
        content = """
## 重点关注股票池
### 光模块
| 股票代码 | 股票名称 | 板块 |
|---|---|---|
| 300308 | 中际旭创 | 光模块 |
| 300502 | 新易盛 | 光模块 |
## 批量分析命令
python tool.py --codes 600519
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text(content, encoding="utf-8")
            stocks = parse_stock_pool(path)
        self.assertEqual([item["代码"] for item in stocks], ["300308", "300502"])
        self.assertEqual(stocks[0]["名称"], "中际旭创")


if __name__ == "__main__":
    unittest.main()

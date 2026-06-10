#!/usr/bin/env python3
"""Generate a daily report from the stock pool in OPENCLAW_GUIDE.md."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from .data_fetcher import DataFetcher
from .indicators import IndicatorCalculator, SignalGenerator
from .reporting import save_daily_report
from .research_reporting import save_research_report


DEFAULT_GUIDE = Path(r"D:\trae_project\stock_analyzer_project\OPENCLAW_GUIDE.md")


def parse_stock_pool(guide_path: str | Path) -> list[dict]:
    text = Path(guide_path).read_text(encoding="utf-8")
    match = re.search(
        r"## 重点关注股票池(?P<body>.*?)## 批量分析命令",
        text,
        flags=re.S,
    )
    if not match:
        raise ValueError("未找到“重点关注股票池”章节")

    stocks = []
    current_sector = ""
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            current_sector = line[4:].strip()
            continue
        row = re.match(
            r"\|\s*(\d{6})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
            line,
        )
        if row:
            stocks.append(
                {
                    "代码": row.group(1),
                    "名称": row.group(2).strip(),
                    "板块": row.group(3).strip() or current_sector,
                }
            )

    unique = {item["代码"]: item for item in stocks}
    if not unique:
        raise ValueError("股票池章节中没有解析出六位股票代码")
    return list(unique.values())


def analyze_stock_pool(stocks: list[dict]) -> tuple[list[dict], list[str]]:
    codes = [item["代码"] for item in stocks]
    metadata = {item["代码"]: item for item in stocks}
    fetcher = DataFetcher(codes, is_index=False)
    if not fetcher.fetch():
        raise RuntimeError("股票池数据获取失败")

    results = []
    failed = []
    for code in codes:
        frame = fetcher.df[fetcher.df["代码"] == code].copy()
        if frame.empty:
            failed.append(code)
            continue
        frame = frame.sort_values("日期").reset_index(drop=True)
        try:
            frame = IndicatorCalculator.calculate_all(frame)
            score, rating, signals = SignalGenerator(frame).calculate_score()
            current = frame.iloc[-1]
            previous = frame.iloc[-2]
            info = metadata[code]
            results.append(
                {
                    "代码": code,
                    "名称": info["名称"],
                    "板块": info["板块"],
                    "日期": str(current["日期"])[:10],
                    "收盘": current["收盘"],
                    "涨跌": (
                        current["收盘"] - previous["收盘"]
                        if pd.notna(previous["收盘"])
                        else 0
                    ),
                    "MA5": current.get("MA5"),
                    "MA10": current.get("MA10"),
                    "MA20": current.get("MA20"),
                    "AO": current.get("AO"),
                    "BBD": current.get("BBD"),
                    "DIF": current.get("DIF"),
                    "DEA": current.get("DEA"),
                    "MACD": current.get("MACD"),
                    "RSI": current.get("RSI"),
                    "得分": score,
                    "评级": rating,
                    "信号": ", ".join(signal["name"] for signal in signals) if signals else "无",
                    "数据源": fetcher.source,
                    "signals": signals,
                    "df": frame,
                }
            )
        except Exception as exc:
            print(f"分析失败 {code}: {exc}")
            failed.append(code)
    return results, failed


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="从 OPENCLAW_GUIDE.md 生成股票池报告")
    parser.add_argument("--guide", default=str(DEFAULT_GUIDE), help="指南文件路径")
    args = parser.parse_args()

    stocks = parse_stock_pool(args.guide)
    print(f"已解析股票池: {len(stocks)} 只")
    results, failed = analyze_stock_pool(stocks)
    if not results:
        raise RuntimeError("没有成功分析的股票")

    path = save_daily_report(results, datetime.now().strftime("%Y-%m-%d"))
    research_path = save_research_report(results, datetime.now().strftime("%Y-%m-%d"))
    print(f"成功分析: {len(results)} 只")
    if failed:
        print(f"未取得数据或分析失败: {', '.join(failed)}")
    print(f"报告已生成: {path}")
    print(f"研究报告已生成: {research_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

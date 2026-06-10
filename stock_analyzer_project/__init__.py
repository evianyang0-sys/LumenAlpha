#!/usr/bin/env python3
"""
LumenAlpha Package

A股量化分析工具包
整合数据获取、技术指标计算、买卖信号生成、可视化展示

模块说明:
    - data_fetcher: 数据获取模块 (支持 baostock, akshare, tushare)
    - indicators: 技术指标计算与买卖信号模块
    - visualizer: 可视化模块 (K线图、报告打印)
    - stock_analyzer_main: 主模块 (整合所有功能)

快速开始:
    from stock_analyzer_project import analyze_stock, analyze_index
    
    # 分析个股
    result = analyze_stock("300750")
    
    # 分析大盘
    result = analyze_index("000001")
"""

from .indicators import (
    IndicatorCalculator, 
    SignalGenerator, 
    calculate_indicators, 
    generate_analysis
)
from .indicator_engine import INDICATOR_SPECS


def __getattr__(name):
    """Load optional data and visualization dependencies only when requested."""
    if name in {"DataFetcher", "fetch_stock_data"}:
        from . import data_fetcher
        return getattr(data_fetcher, name)
    if name in {"ChartVisualizer", "ReportPrinter", "visualize", "print_report"}:
        from . import visualizer
        return getattr(visualizer, name)
    if name in {
        "StockAnalyzer",
        "analyze_stocks",
        "analyze_index",
        "analyze_stock",
        "print_summary",
    }:
        from . import stock_analyzer_main
        return getattr(stock_analyzer_main, name)
    raise AttributeError(name)

__version__ = "1.0.0"
__author__ = "Evian Yang"

__all__ = [
    # 数据获取
    'DataFetcher',
    'fetch_stock_data',
    
    # 指标计算
    'IndicatorCalculator',
    'SignalGenerator', 
    'calculate_indicators',
    'generate_analysis',
    'INDICATOR_SPECS',
    
    # 可视化
    'ChartVisualizer',
    'ReportPrinter',
    'visualize',
    'print_report',
    
    # 主模块
    'StockAnalyzer',
    'analyze_stocks',
    'analyze_index',
    'analyze_stock',
    'print_summary',
]

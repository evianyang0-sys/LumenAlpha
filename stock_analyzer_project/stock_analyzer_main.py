#!/usr/bin/env python3
"""
股票分析器主模块 (Stock Analyzer Main Module)

整合数据获取、指标计算、信号生成、可视化的完整分析流程
提供命令行界面和编程接口
"""

import argparse
import sys
import pandas as pd

try:
    from .data_fetcher import DataFetcher, fetch_stock_data
    from .indicators import (
        IndicatorCalculator,
        SignalGenerator,
        calculate_indicators,
        generate_analysis,
    )
    from .visualizer import ChartVisualizer, ReportPrinter, visualize, print_report
    from .backtest import (
        run_backtest,
        print_backtest_report,
        get_significant_signals,
        SignalDetector,
    )
    from .reporting import save_backtest_report, save_daily_report
except ImportError:
    from data_fetcher import DataFetcher, fetch_stock_data
    from indicators import (
        IndicatorCalculator,
        SignalGenerator,
        calculate_indicators,
        generate_analysis,
    )
    from visualizer import ChartVisualizer, ReportPrinter, visualize, print_report
    from backtest import (
        run_backtest,
        print_backtest_report,
        get_significant_signals,
        SignalDetector,
    )
    from reporting import save_backtest_report, save_daily_report


class StockAnalyzer:
    """股票/指数综合分析器
    
    整合数据获取、技术指标计算、买卖信号生成、可视化展示的完整流程
    
    属性:
        code: 股票代码
        name: 股票名称
        is_index: 是否为大盘指数
        df: 原始K线数据
        df_indicators: 带指标的数据
        source: 数据源
        score: 综合评分
        rating: 评级
        signals: 信号列表
        outlook: 市场展望
    """
    
    # 大盘指数代码映射 (数字代码 -> (baostock代码, 中文名称))
    INDICES = {
        '000001': ('sh.000001', '上证指数'),
        '399006': ('sz.399006', '创业板指'),
    }
    
    # 个股名称映射 (代码 -> 名称)
    STOCK_NAMES = {
        '301308': '江波龙',
        '603986': '兆易创新',
        '000021': '深科技',
        '002837': '英维克',
        '300153': '科泰电源',
        '601138': '工业富联',
        '301413': '安培龙',
        '605488': '福莱新材',
        '300476': '胜宏科技',
        '002463': '沪电股份',
        '300308': '中际旭创',
        '300394': '天孚通信',
        '300502': '新易盛',
        '605179': '一鸣食品',
        '002714': '牧原股份',
        '300058': '蓝色光标',
        '600986': '浙文互联',
        '002342': '巨力索具',
        '002149': '西部材料',
        '300915': '凯龙高科',
        '603667': '五洲新春',
        '002009': '天奇股份',
        '300450': '先导智能',
        '300750': '宁德时代',
        '002961': '瑞达期货',
        '300803': '指南针',
        '600030': '中信证券',
        '002865': '钧达股份',
        '002506': '协鑫集成',
        '300846': '首都在线',
        '002015': '协鑫能科',
        '600519': '贵州茅台',
        '601318': '中国平安',
        '600036': '招商银行',
        '601398': '工商银行',
        '002594': '比亚迪',
        '300059': '东方财富',
        '300015': '爱尔眼科',
    }
    
    # 个股板块映射 (代码 -> 板块)
    STOCK_SECTORS = {
        '301308': '储存芯片',
        '603986': '储存芯片',
        '000021': '储存芯片',
        '002837': '液冷',
        '300153': '液冷',
        '601138': '消费电子',
        '301413': '消费电子',
        '605488': '消费电子',
        '300476': 'PCB',
        '002463': 'PCB',
        '300308': '光模块',
        '300394': '光模块',
        '300502': '光模块',
        '605179': '食品消费',
        '002714': '食品消费',
        '300058': '传媒',
        '600986': '传媒',
        '002342': '商业航天',
        '002149': '商业航天',
        '300915': '机器人',
        '603667': '机器人',
        '002009': '机器人',
        '300450': '新能源电池',
        '300750': '新能源电池',
        '002961': '证券',
        '300803': '证券',
        '600030': '证券',
        '002865': '光伏',
        '002506': '光伏',
        '300846': '算力',
        '002015': '算力',
        '600519': '白酒',
        '601318': '保险',
        '600036': '银行',
        '601398': '银行',
        '002594': '新能源汽车',
        '300059': '证券',
        '300015': '医疗',
    }
    
    def __init__(self, code: str, is_index: bool = False):
        """
        初始化分析器
        
        参数:
            code: 股票代码 (如 300750, 000001)
            is_index: 是否为大盘指数 (bool)
        """
        self.code = code
        self.is_index = is_index
        
        # 确定名称
        if is_index:
            self.name = self.INDICES.get(code, (None, code))[1]
        else:
            # 优先使用映射表中的名称，否则使用代码
            self.name = self.STOCK_NAMES.get(code, code)
        
        # 确定板块
        self.sector = self.STOCK_SECTORS.get(code, '')
        
        self.df = None
        self.df_indicators = None
        self.source = None
        self.score = None
        self.rating = None
        self.signals = None
        self.outlook = None
    
    def fetch_data(self):
        """获取K线数据
        
        返回:
            bool: 是否成功获取数据
        """
        fetcher = DataFetcher(self.code, self.is_index)
        if fetcher.fetch():
            self.df = fetcher.df
            self.source = fetcher.source
            
            if not self.df.empty:
                # 过滤当前股票数据
                self.df = self.df[self.df['代码'] == self.code]
                self.df = self.df.sort_values('日期').reset_index(drop=True)
                return True
        return False
    
    def calculate_indicators(self):
        """计算技术指标"""
        if self.df is None or self.df.empty:
            return False
        
        self.df_indicators = IndicatorCalculator.calculate_all(self.df)
        return True
    
    def generate_signals(self):
        """生成买卖信号"""
        if self.df_indicators is None:
            return False
        
        signal_gen = SignalGenerator(self.df_indicators)
        self.score, self.rating, self.signals = signal_gen.calculate_score()
        self.outlook = signal_gen.get_outlook()
        return True
    
    def analyze(self):
        """执行完整分析流程
        
        流程: 获取数据 -> 计算指标 -> 生成信号
        
        返回:
            bool: 是否成功完成分析
        """
        # 1. 获取数据
        if not self.fetch_data():
            return False
        
        # 2. 计算指标
        if not self.calculate_indicators():
            return False
        
        # 3. 生成信号
        if not self.generate_signals():
            return False
        
        return True
    
    def get_result(self):
        """获取分析结果
        
        返回:
            dict: 完整的分析结果
        """
        if self.df_indicators is None or len(self.df_indicators) < 2:
            return None
        
        curr = self.df_indicators.iloc[-1]
        prev = self.df_indicators.iloc[-2]
        
        return {
            '代码': self.code,
            '名称': self.name,
            '板块': self.sector,
            '日期': str(curr['日期'])[:10],
            '收盘': curr['收盘'],
            '涨跌': curr['收盘'] - prev['收盘'] if pd.notna(prev['收盘']) else 0,
            '开盘': curr['开盘'],
            '最高': curr['最高'],
            '最低': curr['最低'],
            '成交量': curr['成交量'],
            'MA5': curr.get('MA5'),
            'MA10': curr.get('MA10'),
            'MA20': curr.get('MA20'),
            'AO': curr.get('AO'),
            'BBD': curr.get('BBD'),
            'DIF': curr.get('DIF'),
            'DEA': curr.get('DEA'),
            'MACD': curr.get('MACD'),
            'RSI': curr.get('RSI'),
            '得分': self.score,
            '评级': self.rating,
            '信号': ', '.join([s['name'] for s in self.signals]) if self.signals else '无',
            '数据源': self.source,
            'outlook': self.outlook,
            'signals': self.signals,
            'df': self.df_indicators
        }
    
    def print_report(self):
        """打印分析报告"""
        if self.df_indicators is None:
            print(f"❌ {self.code} - 分析失败")
            return
        
        ReportPrinter.print_detail_report(
            self.df_indicators,
            self.code,
            self.name,
            self.source,
            self.score,
            self.rating,
            self.signals,
            self.outlook
        )
    
    def plot_chart(self):
        """绘制K线图"""
        if self.df_indicators is None:
            return
        
        ChartVisualizer.plot_kline_with_indicators(
            self.df_indicators,
            self.code,
            self.name
        )


def analyze_stocks(
    codes,
    is_index=False,
    show_detail=False,
    show_chart=False,
    show_backtest=False,
    export_reports=False,
):
    """
    便捷函数: 分析多只股票/指数
    
    参数:
        codes: 股票代码列表 (逗号分隔的字符串或列表)
        is_index: 是否为大盘指数
        show_detail: 是否显示详细报告
        show_chart: 是否显示K线图
        show_backtest: 是否运行回测
    
    返回:
        list: 分析结果列表
    """
    # 解析代码列表
    if isinstance(codes, str):
        code_list = [c.strip() for c in codes.split(',') if c.strip()]
    else:
        code_list = codes
    
    results = []
    
    print(f"\n{'='*60}")
    if is_index:
        print(f"📈 正在分析 {len(code_list)} 个大盘指数...")
    else:
        print(f"📊 正在分析 {len(code_list)} 只个股...")
    print(f"{'='*60}")
    
    for code in code_list:
        print(f"\n>>> 处理: {code}")
        
        analyzer = StockAnalyzer(code, is_index=is_index)
        
        if analyzer.analyze():
            result = analyzer.get_result()
            results.append(result)
            
            print(f"  ✅ {code} - 得分: {result['得分']:.1f} - {result['数据源']}")
            
            # 显示详细报告
            if show_detail:
                analyzer.print_report()
            
            # 显示图表 (带信号标注)
            if show_chart:
                if show_backtest:
                    ChartVisualizer.plot_with_signals(
                        analyzer.df_indicators, 
                        analyzer.code, 
                        analyzer.name
                    )
                else:
                    analyzer.plot_chart()
            
            # 运行回测
            if show_backtest and analyzer.df_indicators is not None:
                print(f"\n  🔍 正在回测 {analyzer.code}...")
                bt_results = run_backtest(analyzer.df_indicators)
                print_backtest_report(bt_results)
                if export_reports:
                    report_path = save_backtest_report(
                        bt_results,
                        code=analyzer.code,
                        name=analyzer.name,
                        source=analyzer.source,
                    )
                    print(f"  📄 回测报告: {report_path}")
                
                # 获取显著信号
                sig_signals = get_significant_signals(bt_results)
                if sig_signals:
                    print(f"\n  ⭐ 显著信号 (胜率>50%):")
                    for sig in sig_signals[:10]:
                        cat = sig.get('category', '短线')
                        sig_type = sig.get('signal_type', 'buy')
                        type_icon = "📈" if sig_type == 'buy' else "📉"
                        type_label = "买入" if sig_type == 'buy' else "卖出"
                        print(f"    - {type_icon}[{cat}/{type_label}] {sig['signal']} {sig['period']}: 胜率 {sig['win_rate']:.1f}% ({sig['count']}个样本)")
        else:
            print(f"  ❌ {code} - 数据获取失败")
    
    return results


def analyze_index(index_code):
    """便捷函数: 分析单个大盘指数
    
    参数:
        index_code: 指数代码 (如 '000001')
    
    返回:
        dict: 分析结果
    """
    results = analyze_stocks(index_code, is_index=True, show_detail=True)
    return results[0] if results else None


def analyze_stock(stock_code):
    """便捷函数: 分析单只股票
    
    参数:
        stock_code: 股票代码 (如 '300750')
    
    返回:
        dict: 分析结果
    """
    results = analyze_stocks(stock_code, is_index=False)
    return results[0] if results else None


def print_summary(results, sort_by_score=False):
    """打印汇总表格
    
    参数:
        results: 分析结果列表
        sort_by_score: 是否按得分排序
    """
    if not results:
        return
    
    # 排序
    if sort_by_score:
        results = sorted(results, key=lambda x: x.get('得分', 0), reverse=True)
    
    # 打印表格
    ReportPrinter.print_summary_table(results)


def main():
    """主函数 - 命令行入口"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description='A股量化分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 分析个股
  python stock_analyzer_main.py --codes 300750,600519
  python stock_analyzer_main.py --codes 300750 --sort
  
  # 分析大盘指数
  python stock_analyzer_main.py --indices 000001,399006
  python stock_analyzer_main.py --indices 000001 --detail
  
  # 显示图表
  python stock_analyzer_main.py --codes 300750 --chart
  
  # 回测分析
  python stock_analyzer_main.py --codes 300750 --backtest
  python stock_analyzer_main.py --codes 300750 --chart --backtest
        """
    )
    
    parser.add_argument('--codes', type=str, help='股票代码列表，逗号分隔，如: 300750,600519')
    parser.add_argument('--indices', type=str, help='大盘指数代码，如: 000001,399006')
    parser.add_argument('--detail', action='store_true', help='显示详细报告')
    parser.add_argument('--chart', action='store_true', help='显示K线图表')
    parser.add_argument('--sort', action='store_true', help='按得分排序')
    parser.add_argument('--backtest', action='store_true', help='运行回测分析')
    
    args = parser.parse_args()
    
    # 如果没有参数，显示帮助
    if not (args.codes or args.indices):
        parser.print_help()
        return
    
    results = []
    
    # 分析个股
    if args.codes:
        results.extend(analyze_stocks(args.codes, is_index=False, 
                                       show_detail=args.detail, 
                                       show_chart=args.chart,
                                       show_backtest=args.backtest,
                                       export_reports=True))
    
    # 分析大盘指数
    if args.indices:
        results.extend(analyze_stocks(args.indices, is_index=True, 
                                      show_detail=args.detail, 
                                      show_chart=args.chart,
                                      show_backtest=args.backtest,
                                      export_reports=True))
    
    # 打印汇总表格 (仅当有结果且不是仅显示详情时)
    if results and not args.detail:
        print_summary(results, sort_by_score=args.sort)
    
    if results:
        report_path = save_daily_report(results)
        print(f"\n📄 天级报告: {report_path}")


if __name__ == "__main__":
    main()

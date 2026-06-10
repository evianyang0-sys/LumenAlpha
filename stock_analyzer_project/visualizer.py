#!/usr/bin/env python3
"""
可视化模块 (Visualization Module)

负责绘制K线图和技术指标图表
使用 Plotly 库生成交互式图表
"""

import pandas as pd
import numpy as np
try:
    from plotly.graph_objects import Candlestick
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    Candlestick = None
    make_subplots = None
    go = None
    PLOTLY_AVAILABLE = False


class ChartVisualizer:
    """图表可视化器
    
    使用 Plotly 生成交互式K线图和技术指标图表
    """
    
    @staticmethod
    def plot_kline_with_indicators(df, code, name, show=True):
        """绘制K线图和技术指标
        
        参数:
            df: 包含技术指标的 DataFrame
            code: 股票代码
            name: 股票名称
            show: 是否直接显示图表 (默认 True)
        
        返回:
            go.Figure: Plotly 图表对象
        """
        if not PLOTLY_AVAILABLE:
            raise RuntimeError("绘图需要安装 plotly")

        # 创建子图: K线、MACD、RSI
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(f'{name} ({code}) 价格走势', 'MACD', 'RSI'),
            row_heights=[0.5, 0.25, 0.25]
        )
        
        # ===== 第一层: K线 + 均线 =====
        
        # K线图
        fig.add_trace(
            Candlestick(
                x=df['日期'],
                open=df['开盘'],
                high=df['最高'],
                low=df['最低'],
                close=df['收盘'],
                name='K线',
                increasing_line_color='red',
                decreasing_line_color='green'
            ),
            row=1, col=1
        )
        
        # 均线
        if 'MA5' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['日期'], 
                    y=df['MA5'], 
                    name='MA5', 
                    line=dict(color='orange', width=1)
                ), 
                row=1, col=1
            )
        
        if 'MA10' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['日期'], 
                    y=df['MA10'], 
                    name='MA10', 
                    line=dict(color='blue', width=1)
                ), 
                row=1, col=1
            )
        
        if 'MA20' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['日期'], 
                    y=df['MA20'], 
                    name='MA20', 
                    line=dict(color='gray', width=1)
                ), 
                row=1, col=1
            )
        
        # ===== 第二层: MACD =====
        
        # MACD 柱状图
        if 'MACD' in df.columns:
            colors = ['red' if m >= 0 else 'green' for m in df['MACD']]
            fig.add_trace(
                go.Bar(
                    x=df['日期'], 
                    y=df['MACD'], 
                    name='MACD', 
                    marker_color=colors
                ),
                row=2, col=1
            )
        
        # DIF 线
        if 'DIF' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['日期'], 
                    y=df['DIF'], 
                    name='DIF', 
                    line=dict(color='orange', width=1)
                ),
                row=2, col=1
            )
        
        # DEA 线
        if 'DEA' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['日期'], 
                    y=df['DEA'], 
                    name='DEA', 
                    line=dict(color='blue', width=1)
                ),
                row=2, col=1
            )
        
        # ===== 第三层: RSI =====
        
        if 'RSI' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['日期'], 
                    y=df['RSI'], 
                    name='RSI', 
                    line=dict(color='purple', width=2)
                ),
                row=3, col=1
            )
            
            # 超买超卖线
            fig.add_hline(y=70, row=3, col=1, line_dash="dash", line_color="red", 
                         annotation_text="超买", annotation_position="top right")
            fig.add_hline(y=30, row=3, col=1, line_dash="dash", line_color="green",
                         annotation_text="超卖", annotation_position="bottom right")
        
        # 设置布局
        fig.update_layout(
            title=f'{name} 技术分析',
            xaxis_rangeslider_visible=False,  # 隐藏底部滑动条
            height=900,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        if show:
            fig.show()
        
        return fig
    
    @staticmethod
    def plot_with_signals(df, code, name, show=True):
        """绘制带信号的K线图
        
        在K线图上标注历史信号位置
        
        参数:
            df: 包含技术指标的 DataFrame
            code: 股票代码
            name: 股票名称
            show: 是否直接显示图表
        
        返回:
            go.Figure: Plotly 图表对象
        """
        try:
            from .backtest import SignalDetector
        except ImportError:
            from backtest import SignalDetector
        
        # 检测信号
        df_signals = SignalDetector.detect_all_signals(df)
        
        # 创建图表
        fig = ChartVisualizer.plot_kline_with_indicators(df_signals, code, name, show=False)
        
        # 获取最近的有信号的日期
        signal_columns = ['信号_底背离', '信号_动能金叉', '信号_MACD金叉', 
                         '信号_多头排列', '信号_BBD上零轴', '信号_RSI超卖']
        
        # 添加信号标注
        signal_colors = {
            '信号_底背离': 'green',
            '信号_动能金叉': 'blue', 
            '信号_MACD金叉': 'orange',
            '信号_多头排列': 'purple',
            '信号_BBD上零轴': 'cyan',
            '信号_RSI超卖': 'magenta'
        }
        
        for sig_col in signal_columns:
            if sig_col in df_signals.columns:
                signal_dates = df_signals[df_signals[sig_col] == True]['日期']
                
                if len(signal_dates) > 0:
                    # 获取信号对应的价格
                    for date in signal_dates:
                        idx = df_signals[df_signals['日期'] == date].index
                        if len(idx) > 0:
                            price = df_signals.loc[idx[0], '收盘']
                            
                            # 添加三角形标注
                            sig_name = sig_col.replace('信号_', '')
                            fig.add_trace(
                                go.Scatter(
                                    x=[date],
                                    y=[price],
                                    mode='markers+text',
                                    marker=dict(
                                        symbol='triangle-up',
                                        size=12,
                                        color=signal_colors.get(sig_col, 'red')
                                    ),
                                    text=[sig_name],
                                    textposition='top center',
                                    textfont=dict(size=8),
                                    name=sig_name,
                                    showlegend=False
                                ),
                                row=1, col=1
                            )
        
        if show:
            fig.show()
        
        return fig
    
    @staticmethod
    def plot_ao_indicator(df, name, show=True):
        """绘制 AO 动量指标图
        
        参数:
            df: 包含 AO 指标的 DataFrame
            name: 股票名称
            show: 是否直接显示图表
        
        返回:
            go.Figure: Plotly 图表对象
        """
        if not PLOTLY_AVAILABLE:
            raise RuntimeError("绘图需要安装 plotly")

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=(f'{name} 价格走势', 'AO 动量指标')
        )
        
        # 价格走势
        fig.add_trace(
            go.Scatter(
                x=df['日期'],
                y=df['收盘'],
                name='收盘价',
                line=dict(color='black', width=2)
            ),
            row=1, col=1
        )
        
        # AO 柱状图
        if 'AO' in df.columns:
            colors = ['red' if ao >= 0 else 'green' for ao in df['AO']]
            fig.add_trace(
                go.Bar(
                    x=df['日期'],
                    y=df['AO'],
                    name='AO',
                    marker_color=colors
                ),
                row=2, col=1
            )
        
        # 零轴线
        fig.add_hline(y=0, row=2, col=1, line_color='black', line_width=1)
        
        fig.update_layout(
            title=f'{name} AO 动量指标分析',
            height=600,
            showlegend=True
        )
        
        if show:
            fig.show()
        
        return fig
    
    @staticmethod
    def plot_volume(df, name, show=True):
        """绘制成交量图
        
        参数:
            df: 包含成交量的 DataFrame
            name: 股票名称
            show: 是否直接显示图表
        
        返回:
            go.Figure: Plotly 图表对象
        """
        if not PLOTLY_AVAILABLE:
            raise RuntimeError("绘图需要安装 plotly")

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=(f'{name} 价格走势', '成交量')
        )
        
        # K线
        fig.add_trace(
            Candlestick(
                x=df['日期'],
                open=df['开盘'],
                high=df['最高'],
                low=df['最低'],
                close=df['收盘'],
                name='K线'
            ),
            row=1, col=1
        )
        
        # 成交量柱状图
        if '成交量' in df.columns:
            # 根据涨跌设置颜色
            close = df['收盘'].values
            open_price = df['开盘'].values
            colors = ['red' if close[i] >= open_price[i] else 'green' 
                     for i in range(len(close))]
            
            fig.add_trace(
                go.Bar(
                    x=df['日期'],
                    y=df['成交量'],
                    name='成交量',
                    marker_color=colors
                ),
                row=2, col=1
            )
        
        # 成交量均线
        if 'VOL_MA5' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['日期'],
                    y=df['VOL_MA5'],
                    name='成交量MA5',
                    line=dict(color='blue', width=1)
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            title=f'{name} 成交量分析',
            xaxis_rangeslider_visible=False,
            height=600,
            showlegend=True
        )
        
        if show:
            fig.show()
        
        return fig


class ReportPrinter:
    """报告打印器
    
    负责在终端打印分析报告
    """
    
    @staticmethod
    def print_detail_report(df, code, name, source, score, rating, signals, outlook):
        """打印详细分析报告
        
        参数:
            df: 包含指标的数据
            code: 股票代码
            name: 股票名称
            source: 数据源
            score: 综合评分
            rating: 评级
            signals: 信号列表
            outlook: 市场展望
        """
        if df is None or len(df) < 2:
            print("数据不足，无法生成报告")
            return
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        print(f"\n{'='*60}")
        print(f"📈 {name} ({code}) 详细分析报告")
        print(f"{'='*60}")
        print(f"📅 分析日期: {curr['日期']}")
        print(f"💰 收盘价: {curr['收盘']:.2f}")
        print(f"📊 涨跌: {curr['收盘'] - prev['收盘']:+.2f}")
        print(f"📡 数据源: {source}")
        
        # 均线系统
        print(f"\n【均线系统】")
        ma_cols = [c for c in ['MA5', 'MA10', 'MA20'] if c in df.columns]
        ma_values = [f"{c}: {curr[c]:.2f}" for c in ma_cols if pd.notna(curr.get(c))]
        print(f"  {' | '.join(ma_values)}")
        
        # 动能指标
        print(f"\n【动能指标】")
        if 'AL' in df.columns:
            print(f"  AL: {curr['AL']:.2f}")
        if 'AO' in df.columns:
            print(f"  AO: {curr['AO']:.2f}")
        if 'BBD' in df.columns:
            print(f"  BBD: {curr['BBD']:.2f}")
        if '动能线' in df.columns:
            print(f"  动能线: {curr['动能线']:.2f}")
        if '动能辅线' in df.columns:
            print(f"  动能辅线: {curr['动能辅线']:.2f}")
        
        # MACD
        print(f"\n【MACD指标】")
        if 'DIF' in df.columns and 'DEA' in df.columns and 'MACD' in df.columns:
            macd_type = "红柱(多头)" if curr['MACD'] > 0 else "绿柱(空头)"
            print(f"  DIF: {curr['DIF']:.4f} | DEA: {curr['DEA']:.4f}")
            print(f"  MACD: {curr['MACD']:.4f} | {macd_type}")
        
        # RSI
        print(f"\n【RSI指标】")
        if 'RSI' in df.columns:
            rsi_zone = "超买区" if curr['RSI'] > 70 else "超卖区" if curr['RSI'] < 30 else "中性"
            print(f"  RSI(14): {curr['RSI']:.1f} | {rsi_zone}")
        
        # 成交量
        print(f"\n【成交量】")
        if '成交量' in df.columns:
            print(f"  成交量: {curr['成交量']:,.0f}")
        if 'VOL_MA5' in df.columns:
            print(f"  5日均量: {curr['VOL_MA5']:,.0f}")
        
        # 信号
        print(f"\n【交易信号】")
        if signals:
            combo_signals = [s for s in signals if s.get('is_combo')]
            single_signals = [s for s in signals if not s.get('is_combo')]
            
            if combo_signals:
                print(f"  🌟 【共振信号】(高胜率组合):")
                for s in combo_signals:
                    emoji = "🟢" if s['type'] == 'bullish' else "🔴"
                    win_rate = s.get('win_rate', 0)
                    print(f"    {emoji} {s['name']}: {s['description']} (历史胜率:{win_rate}%)")
            
            if single_signals:
                print(f"  📊 单项信号:")
                for s in single_signals:
                    emoji = "🟢" if s['type'] == 'bullish' else "🔴"
                    print(f"    {emoji} {s['name']}: {s['description']}")
        else:
            print("  无触发信号")
        
        # 总结
        print(f"\n{'='*60}")
        print(f"📊 综合判断: {outlook}")
        print(f"   得分: {score} | 评级: {rating}")
        signal_names = [s['name'] for s in signals]
        print(f"   信号: {', '.join(signal_names) if signal_names else '无'}")
        print(f"{'='*60}\n")
    
    @staticmethod
    def print_summary_table(results):
        """打印汇总表格
        
        参数:
            results: 分析结果列表，每项为 dict
        """
        if not results:
            return
        
        from tabulate import tabulate
        
        # 准备表格数据
        table_data = []
        for r in results:
            # 提取共振信号
            combo_signal = ''
            if 'signals' in r and r['signals']:
                combo_list = [s['name'] for s in r['signals'] if s.get('is_combo')]
                if combo_list:
                    combo_signal = '🌟' + ','.join(combo_list[:2])
            
            row = [
                r.get('代码', ''),
                r.get('名称', ''),
                r.get('板块', ''),
                str(r.get('日期', ''))[:10],
                f"{r.get('收盘', 0):.2f}",
                f"{r.get('涨跌', 0):+.2f}",
                f"{r.get('MA5', 0):.2f}" if pd.notna(r.get('MA5')) else '-',
                f"{r.get('MA10', 0):.2f}" if pd.notna(r.get('MA10')) else '-',
                f"{r.get('AO', 0):.2f}" if pd.notna(r.get('AO')) else '-',
                f"{r.get('BBD', 0):.2f}" if pd.notna(r.get('BBD')) else '-',
                f"{r.get('MACD', 0):.4f}" if pd.notna(r.get('MACD')) else '-',
                f"{r.get('RSI', 0):.1f}" if pd.notna(r.get('RSI')) else '-',
                r.get('得分', 0),
                r.get('评级', ''),
                combo_signal,
                r.get('数据源', '')
            ]
            table_data.append(row)
        
        headers = ['代码', '名称', '板块', '日期', '收盘', '涨跌', 'MA5', 'MA10', 'AO', 'BBD', 'MACD', 'RSI', '得分', '评级', '共振', '数据源']
        
        print("\n" + "="*130)
        print(tabulate(table_data, headers=headers, tablefmt='grid', numalign='right'))
        print("="*130)


def visualize(df, code, name, source=None, score=None, rating=None, signals=None, outlook=None):
    """便捷函数: 生成可视化图表
    
    参数:
        df: 包含指标的数据
        code: 股票代码
        name: 股票名称
        source: 数据源
        score: 综合评分
        rating: 评级
        signals: 信号列表
        outlook: 市场展望
    
    返回:
        go.Figure: Plotly 图表对象
    """
    return ChartVisualizer.plot_kline_with_indicators(df, code, name)


def print_report(df, code, name, source, score, rating, signals, outlook):
    """便捷函数: 打印分析报告
    
    参数:
        df: 包含指标的数据
        code: 股票代码
        name: 股票名称
        source: 数据源
        score: 综合评分
        rating: 评级
        signals: 信号列表
        outlook: 市场展望
    """
    ReportPrinter.print_detail_report(df, code, name, source, score, rating, signals, outlook)


if __name__ == "__main__":
    # 测试代码
    print("=== 测试可视化模块 ===")
    
    # 模拟数据
    import pandas as pd
    import numpy as np
    
    dates = pd.date_range('2025-01-01', periods=100)
    np.random.seed(42)
    
    close = 100 + np.cumsum(np.random.randn(100) * 2)
    high = close + np.random.rand(100) * 3
    low = close - np.random.rand(100) * 3
    open_price = close - np.random.randn(100)
    volume = np.random.randint(1000000, 10000000, 100)
    
    df = pd.DataFrame({
        '日期': dates,
        '开盘': open_price,
        '收盘': close,
        '最高': high,
        '最低': low,
        '成交量': volume
    })
    
    # 计算指标
    from indicators import calculate_indicators
    df = calculate_indicators(df)
    
    print("生成K线图...")
    fig = visualize(df, "000001", "测试股票")
    print("图表生成完成!")

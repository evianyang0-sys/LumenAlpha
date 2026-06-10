#!/usr/bin/env python3
"""
多指标共振回测脚本

研究多个指标同时发生时是否会提高胜率
"""

import pandas as pd
import numpy as np
import time

try:
    from .data_fetcher import DataFetcher
    from .indicators import IndicatorCalculator
    from .backtest import SignalDetector
except ImportError:
    from data_fetcher import DataFetcher
    from indicators import IndicatorCalculator
    from backtest import SignalDetector

# 回测目标
TARGETS = [
    {'code': '000001', 'name': '上证指数', 'is_index': True},
    {'code': '601138', 'name': '工业富联', 'is_index': False},
    {'code': '002463', 'name': '沪电股份', 'is_index': False},
]

# 短线回测周期
SHORT_TERM_DAYS = [1, 3, 5]
# 长线回测周期
LONG_TERM_DAYS = [5, 10, 20]

# 指标组合定义
INDICATOR_COMBOS = [
    # 短线组合
    {'name': 'RSI超卖 + KDJ超卖', 'signals': ['信号_RSI超卖', '信号_KDJ超卖'], 'category': '短线'},
    {'name': 'RSI严重超卖 + KDJ深度超卖', 'signals': ['信号_RSI严重超卖', '信号_KDJ深度超卖'], 'category': '短线'},
    {'name': 'MACD金叉 + RSI超卖', 'signals': ['信号_MACD金叉', '信号_RSI超卖'], 'category': '短线'},
    {'name': '动能金叉 + RSI超卖', 'signals': ['信号_动能金叉', '信号_RSI超卖'], 'category': '短线'},
    {'name': 'MACD金叉 + 动能金叉', 'signals': ['信号_MACD金叉', '信号_动能金叉'], 'category': '短线'},
    {'name': '底背离 + RSI超卖', 'signals': ['信号_底背离', '信号_RSI超卖'], 'category': '短线'},
    {'name': '底背离 + MACD金叉', 'signals': ['信号_底背离', '信号_MACD金叉'], 'category': '短线'},
    {'name': '多头排列 + MACD红柱', 'signals': ['信号_多头排列', '信号_MACD红柱'], 'category': '短线'},
    {'name': 'BBD上零轴 + MACD金叉', 'signals': ['信号_BBD上零轴', '信号_MACD金叉'], 'category': '短线'},
    {'name': 'RSI超卖 + MACD红柱', 'signals': ['信号_RSI超卖', '信号_MACD红柱'], 'category': '短线'},
    {'name': 'KDJ超卖 + CCI超卖', 'signals': ['信号_KDJ超卖', '信号_CCI超卖'], 'category': '短线'},
    {'name': 'KDJ金叉 + RSI超卖', 'signals': ['信号_KDJ金叉', '信号_RSI超卖'], 'category': '短线'},
    # 长线组合
    {'name': 'EMA多头排列 + KDJ金叉', 'signals': ['信号_EMA多头排列', '信号_KDJ金叉'], 'category': '长线'},
    {'name': '价格站上EMA200 + KDJ金叉', 'signals': ['信号_价格站上EMA200', '信号_KDJ金叉'], 'category': '长线'},
    {'name': 'VWAP上方 + EMA多头排列', 'signals': ['信号_VWAP上方', '信号_EMA多头排列'], 'category': '长线'},
    {'name': 'CCI超卖 + KDJ超卖', 'signals': ['信号_CCI超卖', '信号_KDJ超卖'], 'category': '长线'},
    {'name': 'CCI超卖 + EMA多头排列', 'signals': ['信号_CCI超卖', '信号_EMA多头排列'], 'category': '长线'},
    {'name': 'KDJ超卖 + EMA多头排列', 'signals': ['信号_KDJ超卖', '信号_EMA多头排列'], 'category': '长线'},
    {'name': '斐波那契底部 + CCI超卖', 'signals': ['信号_斐波那契底部', '信号_CCI超卖'], 'category': '长线'},
    {'name': '斐波那契底部 + KDJ超卖', 'signals': ['信号_斐波那契底部', '信号_KDJ超卖'], 'category': '长线'},
    {'name': 'VWAP上方 + 价格站上EMA200', 'signals': ['信号_VWAP上方', '信号_价格站上EMA200'], 'category': '长线'},
    {'name': 'KDJ金叉 + CCI超卖', 'signals': ['信号_KDJ金叉', '信号_CCI超卖'], 'category': '长线'},
    {'name': 'EMA金叉 + KDJ金叉', 'signals': ['信号_EMA金叉', '信号_KDJ金叉'], 'category': '长线'},
    {'name': 'CCI区域 + KDJ超卖', 'signals': ['信号_CCI区域', '信号_KDJ超卖'], 'category': '长线'},
]


def fetch_data_cached(code, is_index=False):
    """获取数据，带缓存"""
    cache_key = f"{code}_{is_index}"
    if hasattr(fetch_data_cached, 'cache'):
        if cache_key in fetch_data_cached.cache:
            print(f"  📡 使用缓存数据: {code}")
            return fetch_data_cached.cache[cache_key]
    else:
        fetch_data_cached.cache = {}
    
    print(f"  📡 正在获取数据: {code}...")
    fetcher = DataFetcher(code, is_index)
    if fetcher.fetch():
        df = fetcher.df
        if not df.empty:
            # 过滤当前股票数据
            df = df[df['代码'] == code]
            df = df.sort_values('日期').reset_index(drop=True)
            fetch_data_cached.cache[cache_key] = df
            print(f"  ✅ 获取成功，数据条数: {len(df)}")
            time.sleep(1)  # 控制请求频率
            return df
    
    return None


def calculate_combo_signal(df, signals):
    """计算组合信号 (AND逻辑)
    
    所有信号同时满足时返回True
    """
    if df is None or len(df) < 30:
        return df
    
    combo_col = f"组合_{'_'.join([s.replace('信号_', '') for s in signals])}"
    df = df.copy()
    df[combo_col] = True
    
    for signal in signals:
        if signal in df.columns:
            df[combo_col] = df[combo_col] & (df[signal] == True)
        else:
            df[combo_col] = False
    
    return df


def backtest_combo(df, combo_name, hold_days, signal_cols):
    """回测组合信号
    
    参数:
        df: 包含信号的DataFrame
        combo_name: 组合名称
        hold_days: 持有天数
        signal_cols: 信号列名列表
    
    返回:
        dict: 回测结果
    """
    # 创建组合信号
    df_combo = calculate_combo_signal(df.copy(), signal_cols)
    combo_col = f"组合_{'_'.join([s.replace('信号_', '') for s in signal_cols])}"
    
    if combo_col not in df_combo.columns:
        return None
    
    # 筛选有组合信号的日子
    signal_days = df_combo[df_combo[combo_col] == True].index
    
    if len(signal_days) == 0:
        return None
    
    # 计算持有期收益
    returns = []
    for idx in signal_days:
        idx_pos = df_combo.index.get_loc(idx)
        if idx_pos + hold_days < len(df_combo):
            future_price = df_combo.iloc[idx_pos + hold_days]['收盘']
            curr_price = df_combo.iloc[idx_pos]['收盘']
            ret = (future_price - curr_price) / curr_price * 100
            returns.append({
                'date': str(df_combo.iloc[idx_pos]['日期'])[:10],
                'price': curr_price,
                'future_price': future_price,
                'return_pct': ret
            })
    
    if not returns:
        return None
    
    returns_pct = [r['return_pct'] for r in returns]
    wins = sum(1 for r in returns_pct if r > 0)  # 买入信号：上涨算胜利
    
    return {
        'combo': combo_name,
        'days': hold_days,
        'count': len(returns),
        'win_rate': wins / len(returns) * 100,
        'avg_return': np.mean(returns_pct),
        'max_return': max(returns_pct),
        'min_return': min(returns_pct),
    }


def backtest_all_combos(df, category='短线'):
    """回测所有组合"""
    days_list = SHORT_TERM_DAYS if category == '短线' else LONG_TERM_DAYS
    
    results = []
    for combo in INDICATOR_COMBOS:
        if combo['category'] != category:
            continue
        
        for days in days_list:
            result = backtest_combo(df, combo['name'], days, combo['signals'])
            if result and result['count'] >= 3:
                results.append(result)
    
    # 按胜率排序
    results.sort(key=lambda x: x['win_rate'], reverse=True)
    return results


def print_combo_results(results, stock_name, category):
    """打印组合回测结果"""
    if not results:
        return
    
    print(f"\n{'='*80}")
    print(f"📊 {stock_name} - {category}指标组合回测结果")
    print(f"{'='*80}")
    print(f"{'组合名称':<30} {'周期':>6} {'样本':>6} {'胜率':>8} {'平均收益':>10}")
    print(f"{'-'*80}")
    
    for r in results:
        win_icon = "✅" if r['win_rate'] > 50 else "❌"
        print(f"{r['combo']:<30} {r['days']:>4}日 {r['count']:>6} "
              f"{win_icon}{r['win_rate']:>6.1f}% {r['avg_return']:>+8.2f}%")


def main():
    print("="*80)
    print("🚀 多指标共振回测分析")
    print("="*80)
    
    all_results = {}
    
    for target in TARGETS:
        code = target['code']
        name = target['name']
        is_index = target['is_index']
        
        print(f"\n{'='*80}")
        print(f"📈 正在分析: {name} ({code})")
        print("="*80)
        
        # 获取数据（只请求一次）
        df = fetch_data_cached(code, is_index)
        if df is None:
            print(f"  ❌ 数据获取失败: {code}")
            continue
        
        # 计算所有指标
        print(f"  🧮 计算技术指标...")
        df = IndicatorCalculator.calculate_all(df)
        
        # 检测所有信号
        print(f"  🔍 检测历史信号...")
        df = SignalDetector.detect_all_signals(df)
        
        print(f"  📊 数据总条数: {len(df)}")
        
        # 短线组合回测
        short_results = backtest_all_combos(df, '短线')
        print_combo_results(short_results[:10], name, '短线')
        
        # 长线组合回测
        long_results = backtest_all_combos(df, '长线')
        print_combo_results(long_results[:10], name, '长线')
        
        all_results[code] = {
            'name': name,
            'short': short_results,
            'long': long_results
        }
        
        # 打印最强的5个组合
        print(f"\n🏆 {name} 最强组合TOP5:")
        all_sorted = short_results + long_results
        all_sorted.sort(key=lambda x: x['win_rate'], reverse=True)
        for i, r in enumerate(all_sorted[:5], 1):
            print(f"  {i}. {r['combo']} ({r['days']}日): 胜率 {r['win_rate']:.1f}% ({r['count']}个样本)")
    
    # 跨股票统计：找出最有效的组合
    print("\n" + "="*80)
    print("🏆 跨股票统计 - 最有效的指标组合")
    print("="*80)
    
    combo_stats = {}
    for code, data in all_results.items():
        name = data['name']
        for r in data['short'] + data['long']:
            combo_name = r['combo']
            if combo_name not in combo_stats:
                combo_stats[combo_name] = {
                    'name': combo_name,
                    'total_count': 0,
                    'total_win': 0,
                    'avg_return': 0,
                    'stocks': []
                }
            combo_stats[combo_name]['total_count'] += r['count']
            combo_stats[combo_name]['total_win'] += int(r['count'] * r['win_rate'] / 100)
            combo_stats[combo_name]['avg_return'] += r['avg_return']
            combo_stats[combo_name]['stocks'].append(f"{name}({r['win_rate']:.0f}%)")
    
    # 计算平均胜率
    for combo_name, stats in combo_stats.items():
        if stats['total_count'] > 0:
            stats['win_rate'] = stats['total_win'] / stats['total_count'] * 100
            stats['avg_return'] /= len(stats['stocks'])
    
    # 按胜率排序
    sorted_combos = sorted(combo_stats.values(), key=lambda x: x['win_rate'], reverse=True)
    
    print(f"\n{'排名':>4} {'组合名称':<30} {'总样本':>8} {'综合胜率':>10} {'平均收益':>10}")
    print(f"{'-'*80}")
    for i, stats in enumerate(sorted_combos[:15], 1):
        win_icon = "✅" if stats['win_rate'] > 50 else "❌"
        print(f"{i:>4} {stats['name']:<30} {stats['total_count']:>6} "
              f"{win_icon}{stats['win_rate']:>6.1f}% {stats['avg_return']:>+8.2f}%")
        print(f"      涉及股票: {', '.join(stats['stocks'][:5])}")
    
    print("\n" + "="*80)
    print("✅ 多指标共振回测分析完成！")
    print("="*80)


if __name__ == "__main__":
    main()

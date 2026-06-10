#!/usr/bin/env python3
"""
回测模块 (Backtest Module)

对历史信号进行回测，计算胜率
检测信号出现后 N 日的涨跌概率

【短线指标回测周期】: 1日、3日、5日
【长线指标回测周期】: 5日、10日、20日
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

try:
    from .indicators import IndicatorCalculator
except ImportError:
    from indicators import IndicatorCalculator

SHORT_TERM_HOLD_DAYS = [1, 3, 5]  # 短线回测周期
LONG_TERM_HOLD_DAYS = [5, 10, 20]  # 长线回测周期

# 信号类型映射: 区分买入信号(看多)和卖出信号(看空)
# 买入信号: 上涨算胜利
# 卖出信号: 下跌算胜利
SIGNAL_TYPES = {
    # 短线买入信号
    '信号_底背离': 'buy',
    '信号_动能金叉': 'buy',
    '信号_MACD金叉': 'buy',
    '信号_MACD红柱': 'buy',
    '信号_多头排列': 'buy',
    '信号_BBD上零轴': 'buy',
    '信号_RSI超卖': 'buy',
    '信号_RSI严重超卖': 'buy',
    # 短线卖出信号
    '信号_空头排列': 'sell',
    # 长线买入信号
    '信号_KDJ金叉': 'buy',
    '信号_KDJ深度超卖': 'buy',
    '信号_KDJ超卖': 'buy',
    '信号_CCI超卖': 'buy',
    '信号_CCI区域': 'buy',
    '信号_EMA金叉': 'buy',
    '信号_EMA多头排列': 'buy',
    '信号_价格站上EMA200': 'buy',
    '信号_VWAP上方': 'buy',
    '信号_斐波那契底部': 'buy',
    # 长线卖出信号
    '信号_KDJ死叉': 'sell',
    '信号_EMA死叉': 'sell',
    '信号_EMA空头排列': 'sell',
    '信号_价格跌破EMA200': 'sell',
    '信号_VWAP下方': 'sell',
    '信号_斐波那契顶部': 'sell',
}


class SignalDetector:
    """历史信号检测器
    
    在历史数据中检测各种买卖信号 (短线 + 长线)
    """
    
    @staticmethod
    def detect_all_signals(df):
        """检测所有历史信号
        
        【短线信号】:
            - 底背离、动能金叉、MACD金叉、多头排列、BBD上零轴、RSI超卖
        
        【长线信号】:
            - KDJ金叉、KDJ超卖、CCI超卖、EMA金叉、EMA多头排列、VWAP位置
        
        参数:
            df: 包含技术指标的 DataFrame
        
        返回:
            DataFrame: 带有信号标记的数据
        """
        if df is None or len(df) < 30:
            return df
        
        df = df.copy()
        
        # ==================== 短线信号 ====================
        df['信号_底背离'] = False
        df['信号_动能金叉'] = False
        df['信号_MACD金叉'] = False
        df['信号_多头排列'] = False
        df['信号_BBD上零轴'] = False
        df['信号_RSI超卖'] = False
        df['信号_RSI严重超卖'] = False
        df['信号_MACD红柱'] = False
        df['信号_空头排列'] = False
        
        # ==================== 长线信号 ====================
        df['信号_KDJ金叉'] = False
        df['信号_KDJ深度超卖'] = False
        df['信号_KDJ超卖'] = False
        df['信号_KDJ死叉'] = False
        df['信号_CCI超卖'] = False
        df['信号_CCI区域'] = False
        df['信号_EMA金叉'] = False
        df['信号_EMA死叉'] = False
        df['信号_EMA多头排列'] = False
        df['信号_EMA空头排列'] = False
        df['信号_价格站上EMA200'] = False
        df['信号_价格跌破EMA200'] = False
        df['信号_VWAP上方'] = False
        df['信号_VWAP下方'] = False
        df['信号_斐波那契底部'] = False
        df['信号_斐波那契顶部'] = False
        
        for i in range(20, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i-1]
            
            # ==================== 短线信号检测 ====================
            
            # 底背离: 20日内最低价，且 BBD 没有创新低
            if i >= 20:
                min_price_20 = df['收盘'].iloc[i-20:i].min()
                min_bbd_20 = df['BBD'].iloc[i-20:i].min()
                
                if pd.notna(curr.get('BBD')) and pd.notna(min_bbd_20):
                    if curr['收盘'] == min_price_20 and curr['BBD'] > min_bbd_20:
                        df.loc[df.index[i], '信号_底背离'] = True
            
            # 动能金叉
            if pd.notna(curr.get('动能线')) and pd.notna(prev.get('动能线')):
                if curr['动能线'] > curr['动能辅线'] and prev['动能线'] <= prev['动能辅线']:
                    df.loc[df.index[i], '信号_动能金叉'] = True
            
            # MACD金叉
            if pd.notna(curr.get('DIF')) and pd.notna(prev.get('DIF')):
                if curr['DIF'] > curr['DEA'] and prev['DIF'] <= prev['DEA']:
                    df.loc[df.index[i], '信号_MACD金叉'] = True
            
            # MACD红柱
            if pd.notna(curr.get('MACD')) and pd.notna(prev.get('MACD')):
                if curr['MACD'] > 0 and curr['MACD'] > prev['MACD']:
                    df.loc[df.index[i], '信号_MACD红柱'] = True
            
            # 多头排列
            if pd.notna(curr.get('MA5')) and pd.notna(curr.get('MA10')):
                if curr['MA5'] > curr['MA10'] and curr['收盘'] > curr['MA5']:
                    df.loc[df.index[i], '信号_多头排列'] = True
                elif curr['MA5'] < curr['MA10'] and curr['收盘'] < curr['MA5']:
                    df.loc[df.index[i], '信号_空头排列'] = True
            
            # BBD上零轴
            if pd.notna(curr.get('BBD')) and pd.notna(prev.get('BBD')):
                if curr['BBD'] > 0 and prev['BBD'] <= 0:
                    df.loc[df.index[i], '信号_BBD上零轴'] = True
            
            # RSI超卖
            if pd.notna(curr.get('RSI')):
                if curr['RSI'] < 30:
                    df.loc[df.index[i], '信号_RSI超卖'] = True
                if curr['RSI'] < 20:
                    df.loc[df.index[i], '信号_RSI严重超卖'] = True
            
            # ==================== 长线信号检测 ====================
            
            # KDJ金叉/死叉
            if pd.notna(curr.get('K')) and pd.notna(curr.get('D')):
                prev_k = prev['K']
                prev_d = prev['D']
                
                if curr['K'] > curr['D'] and prev_k <= prev_d:
                    if curr['K'] < 30 and curr['D'] < 30:
                        df.loc[df.index[i], '信号_KDJ金叉'] = True
                
                elif curr['K'] < curr['D'] and prev_k >= prev_d:
                    if curr['K'] > 70 and curr['D'] > 70:
                        df.loc[df.index[i], '信号_KDJ死叉'] = True
            
            # KDJ超卖
            if pd.notna(curr.get('K')) and pd.notna(curr.get('D')):
                if curr['K'] < 20 and curr['D'] < 20:
                    df.loc[df.index[i], '信号_KDJ深度超卖'] = True
                elif curr['K'] < 30:
                    df.loc[df.index[i], '信号_KDJ超卖'] = True
            
            # CCI超卖
            if pd.notna(curr.get('CCI')):
                if curr['CCI'] < -100:
                    df.loc[df.index[i], '信号_CCI超卖'] = True
                elif curr['CCI'] < -50:
                    df.loc[df.index[i], '信号_CCI区域'] = True
            
            # EMA金叉/死叉
            if pd.notna(curr.get('EMA20')) and pd.notna(curr.get('EMA50')):
                prev_ema20 = prev['EMA20']
                prev_ema50 = prev['EMA50']
                
                if prev_ema20 < prev_ema50 and curr['EMA20'] > curr['EMA50']:
                    df.loc[df.index[i], '信号_EMA金叉'] = True
                elif prev_ema20 > prev_ema50 and curr['EMA20'] < curr['EMA50']:
                    df.loc[df.index[i], '信号_EMA死叉'] = True
            
            # EMA多头/空头排列
            if pd.notna(curr.get('EMA20')) and pd.notna(curr.get('EMA50')) and pd.notna(curr.get('EMA200')):
                if curr['EMA20'] > curr['EMA50'] > curr['EMA200']:
                    df.loc[df.index[i], '信号_EMA多头排列'] = True
                elif curr['EMA20'] < curr['EMA50'] < curr['EMA200']:
                    df.loc[df.index[i], '信号_EMA空头排列'] = True
            
            # 价格与EMA200关系
            if pd.notna(curr.get('EMA200')):
                if curr['收盘'] > curr['EMA200']:
                    df.loc[df.index[i], '信号_价格站上EMA200'] = True
                else:
                    df.loc[df.index[i], '信号_价格跌破EMA200'] = True
            
            # VWAP位置
            if pd.notna(curr.get('VWAP')):
                if curr['收盘'] > curr['VWAP']:
                    df.loc[df.index[i], '信号_VWAP上方'] = True
                else:
                    df.loc[df.index[i], '信号_VWAP下方'] = True
            
            # 斐波那契区域
            if pd.notna(curr.get('FIB_0382')) and pd.notna(curr.get('FIB_0618')):
                if curr['收盘'] < curr['FIB_0382']:
                    df.loc[df.index[i], '信号_斐波那契底部'] = True
                elif curr['收盘'] > curr['FIB_0618']:
                    df.loc[df.index[i], '信号_斐波那契顶部'] = True
        
        return df
        
        return df


class Backtester:
    """回测器
    
    计算信号出现后的涨跌幅和胜率
    """
    
    def __init__(self, df):
        """
        初始化回测器
        
        参数:
            df: 包含技术指标和信号标记的 DataFrame
        """
        self.df = df
    
    def calculate_returns(self, days):
        """计算 N 日收益率
        
        参数:
            days: 持有天数
        
        返回:
            Series: 收益率序列
        """
        if len(self.df) <= days:
            return pd.Series([np.nan] * len(self.df), index=self.df.index)
        
        future_prices = self.df['收盘'].shift(-days)
        returns = (future_prices - self.df['收盘']) / self.df['收盘'] * 100
        return returns
    
    def backtest_signal(self, signal_name, hold_days):
        """回测单个信号
        
        参数:
            signal_name: 信号名称 (如 '信号_底背离')
            hold_days: 持有天数
        
        返回:
            dict: 回测结果
        """
        if signal_name not in self.df.columns:
            return None
        
        # 筛选有信号的日子
        signal_days = self.df[self.df[signal_name] == True].index
        
        if len(signal_days) == 0:
            return {
                'signal': signal_name,
                'days': hold_days,
                'count': 0,
                'win_rate': 0.0,
                'avg_return': 0.0,
                'max_return': 0.0,
                'min_return': 0.0,
                'details': []
            }
        
        # 计算持有期收益
        returns = []
        for idx in signal_days:
            idx_pos = self.df.index.get_loc(idx)
            if idx_pos + hold_days < len(self.df):
                future_price = self.df.iloc[idx_pos + hold_days]['收盘']
                curr_price = self.df.iloc[idx_pos]['收盘']
                ret = (future_price - curr_price) / curr_price * 100
                returns.append({
                    'date': str(self.df.iloc[idx_pos]['日期'])[:10],
                    'price': curr_price,
                    'future_price': future_price,
                    'return_pct': ret
                })
        
        if not returns:
            return {
                'signal': signal_name,
                'days': hold_days,
                'count': 0,
                'win_rate': 0.0,
                'avg_return': 0.0,
                'max_return': 0.0,
                'min_return': 0.0,
                'details': []
            }
        
        returns_pct = [r['return_pct'] for r in returns]
        
        # 根据信号类型判断胜利
        # 买入信号: 上涨算胜利
        # 卖出信号: 下跌算胜利
        signal_type = SIGNAL_TYPES.get(signal_name, 'buy')
        
        if signal_type == 'buy':
            wins = sum(1 for r in returns_pct if r > 0)  # 买入信号：上涨算赢
        else:
            wins = sum(1 for r in returns_pct if r < 0)  # 卖出信号：下跌算赢
        
        return {
            'signal': signal_name.replace('信号_', ''),
            'days': hold_days,
            'count': len(returns),
            'win_rate': wins / len(returns) * 100,
            'avg_return': np.mean(returns_pct),
            'max_return': max(returns_pct),
            'min_return': min(returns_pct),
            'signal_type': signal_type,
            'details': returns[:10]
        }
    
    def backtest_all(self):
        """回测所有信号
        
        短线信号使用周期: 1日、3日、5日
        长线信号使用周期: 5日、10日、20日
        
        返回:
            dict: 所有回测结果
        """
        results = {}
        
        # 短线信号
        short_term_signals = [
            '信号_底背离',
            '信号_动能金叉', 
            '信号_MACD金叉',
            '信号_MACD红柱',
            '信号_多头排列',
            '信号_空头排列',
            '信号_BBD上零轴',
            '信号_RSI超卖',
            '信号_RSI严重超卖'
        ]
        
        # 长线信号
        long_term_signals = [
            '信号_KDJ金叉',
            '信号_KDJ深度超卖',
            '信号_KDJ超卖',
            '信号_KDJ死叉',
            '信号_CCI超卖',
            '信号_CCI区域',
            '信号_EMA金叉',
            '信号_EMA死叉',
            '信号_EMA多头排列',
            '信号_EMA空头排列',
            '信号_价格站上EMA200',
            '信号_价格跌破EMA200',
            '信号_VWAP上方',
            '信号_VWAP下方',
            '信号_斐波那契底部',
            '信号_斐波那契顶部'
        ]
        
        # 回测短线信号
        for signal in short_term_signals:
            if signal in self.df.columns:
                results[signal] = {}
                for days in SHORT_TERM_HOLD_DAYS:
                    result = self.backtest_signal(signal, days)
                    if result:
                        result['category'] = '短线'
                        results[signal][f'{days}日'] = result
        
        # 回测长线信号
        for signal in long_term_signals:
            if signal in self.df.columns:
                results[signal] = {}
                for days in LONG_TERM_HOLD_DAYS:
                    result = self.backtest_signal(signal, days)
                    if result:
                        result['category'] = '长线'
                        results[signal][f'{days}日'] = result
        
        return results


def run_backtest(df):
    """
    便捷函数: 运行回测
    
    短线信号使用周期: 1日、3日、5日
    长线信号使用周期: 5日、10日、20日
    
    参数:
        df: 包含技术指标的 DataFrame
    
    返回:
        dict: 回测结果
    """
    # 检测信号
    df_with_signals = SignalDetector.detect_all_signals(df)
    
    # 回测
    backtester = Backtester(df_with_signals)
    results = backtester.backtest_all()
    
    return results


def print_backtest_report(results):
    """打印回测报告
    
    参数:
        results: 回测结果
    """
    print("\n" + "="*70)
    print("📊 信号回测报告 - 胜率统计")
    print("买入信号: 上涨算胜利 | 卖出信号: 下跌算胜利")
    print("="*70)
    
    # 区分短线和长线信号
    short_term_results = {}
    long_term_results = {}
    
    for signal_name, days_results in results.items():
        for period, result in days_results.items():
            if result.get('category') == '长线':
                long_term_results[signal_name] = days_results
            else:
                short_term_results[signal_name] = days_results
    
    # 打印短线信号
    if short_term_results:
        print("\n【短线信号】(回测周期: 1日、3日、5日)")
        print("-" * 60)
        for signal_name, days_results in short_term_results.items():
            signal_display = signal_name.replace('信号_', '')
            signal_type = '买入' if days_results.get(list(days_results.keys())[0], {}).get('signal_type', 'buy') == 'buy' else '卖出'
            
            for period, result in days_results.items():
                if result['count'] > 0:
                    win_icon = "✅" if result['win_rate'] > 50 else "❌"
                    type_icon = "📈" if result['signal_type'] == 'buy' else "📉"
                    print(f"  {type_icon}[{signal_type}] {signal_display} {period}: "
                          f"样本{result['count']}个, 胜率{win_icon}{result['win_rate']:.1f}%, "
                          f"平均{result['avg_return']:+.2f}%")
    
    # 打印长线信号
    if long_term_results:
        print("\n【长线信号】(回测周期: 5日、10日、20日)")
        print("-" * 60)
        for signal_name, days_results in long_term_results.items():
            signal_display = signal_name.replace('信号_', '')
            signal_type = '买入' if days_results.get(list(days_results.keys())[0], {}).get('signal_type', 'buy') == 'buy' else '卖出'
            
            for period, result in days_results.items():
                if result['count'] > 0:
                    win_icon = "✅" if result['win_rate'] > 50 else "❌"
                    type_icon = "📈" if result['signal_type'] == 'buy' else "📉"
                    print(f"  {type_icon}[{signal_type}] {signal_display} {period}: "
                          f"样本{result['count']}个, 胜率{win_icon}{result['win_rate']:.1f}%, "
                          f"平均{result['avg_return']:+.2f}%")
    
    print("\n" + "="*70)


def get_significant_signals(results, min_win_rate=50):
    """获取显著信号
    
    参数:
        results: 回测结果
        min_win_rate: 最低胜率阈值
    
    返回:
        list: 显著信号列表 (按胜率排序)
    """
    significant = []
    
    for signal_name, days_results in results.items():
        signal_display = signal_name.replace('信号_', '')
        
        for period, result in days_results.items():
            if result['count'] >= 5 and result['win_rate'] >= min_win_rate:
                significant.append({
                    'signal': signal_display,
                    'period': period,
                    'win_rate': result['win_rate'],
                    'avg_return': result['avg_return'],
                    'count': result['count'],
                    'category': result.get('category', '短线'),
                    'signal_type': result.get('signal_type', 'buy')
                })
    
    # 按胜率排序
    significant.sort(key=lambda x: x['win_rate'], reverse=True)
    
    return significant


# ==================== 综合回测扩展 ====================

CACHE_FILE = os.path.join(os.path.dirname(__file__), 'index_data_cache.pkl')

def save_index_cache(data_dict):
    """保存指数数据缓存"""
    import pickle
    try:
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(data_dict, f)
        print(f"✅ 数据已缓存到 {CACHE_FILE}")
    except Exception as e:
        print(f"缓存保存失败: {e}")

def load_index_cache():
    """加载指数数据缓存"""
    import pickle
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"缓存加载失败: {e}")
    return None


def get_index_data(code, days=300):
    """获取指数数据，优先使用缓存"""
    import baostock as bs
    
    cache = load_index_cache()
    if cache is not None and code in cache:
        df = cache[code]
        print(f"📂 使用缓存数据: {code}, {len(df)}条")
        return df
    
    if code == '931865':
        return get_index_data_akshare(code, days)
    
    try:
        bs.login()
        if code == '000001':
            bs_code = 'sh.000001'
        elif code == '399006':
            bs_code = 'sz.399006'
        else:
            bs_code = f'sh.{code}'
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - pd.Timedelta(days=days+50)).strftime("%Y-%m-%d")
        
        rs = bs.query_history_k_data_plus(
            bs_code, "date,code,open,high,low,close,volume",
            start_date=start_date, end_date=end_date, frequency="d", adjustflag="3"
        )
        
        data_list = []
        while rs.error_code == '0' and rs.next():
            data_list.append(rs.get_row_data())
        
        bs.logout()
        
        if data_list:
            df = pd.DataFrame(data_list, columns=['日期','代码','开盘','最高','最低','收盘','成交量'])
            df['代码'] = df['代码'].str.replace('sh.', '').str.replace('sz.', '')
            target_code = bs_code.replace('sh.', '').replace('sz.', '')
            df = df[df['代码'] == target_code]
            for col in ['开盘','最高','最低','收盘','成交量']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.dropna().sort_values('日期').reset_index(drop=True)
            result = df if len(df) > 50 else None
            
            if result is not None:
                cache = {} if cache is None else cache
                cache[code] = result
                save_index_cache(cache)
            
            return result
    except Exception as e:
        print(f"获取数据失败: {e}")
    return None


def get_index_data_akshare(code, days=300):
    """从akshare获取指数数据 (用于半导体等特殊指数)"""
    import warnings
    warnings.filterwarnings('ignore')
    
    try:
        import akshare as ak
        if code == '931865':
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+60)).strftime('%Y%m%d')
            print(f"   正在从akshare获取半导体指数数据...")
            df = ak.index_zh_a_hist(symbol="931865", period="daily", 
                                   start_date=start_date, end_date=end_date)
            print(f"   获取到 {len(df) if df is not None else 0} 条数据")
            if df is not None and len(df) > 0:
                df = df.rename(columns={
                    '日期': '日期', '开盘': '开盘', '收盘': '收盘', 
                    '最高': '最高', '最低': '最低', '成交量': '成交量'
                })
                df = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']]
                for col in ['开盘', '收盘', '最高', '最低', '成交量']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.dropna().sort_values('日期').reset_index(drop=True)
                return df if len(df) > 50 else None
    except Exception as e:
        print(f"akshare获取失败: {e}")
    return None


def calculate_basic_indicators(df):
    """使用项目唯一指标引擎计算基础技术指标。"""
    df = IndicatorCalculator.calculate_all(df)
    close = df['收盘'].astype(float)
    for d in [1, 3, 5, 10, 20]:
        df[f'未来收益_{d}d'] = close.shift(-d) / close - 1
    
    return df


# 去重后的信号列表
UNIFIED_SIGNALS = [
    'RSI超卖', 'MACD金叉', 'MACD红柱', '多头排列', '底背离',
    'KDJ金叉', 'KDJ超卖', 'CCI超卖', 'EMA金叉', 'EMA多头排列',
    '价格站上EMA200', 'VWAP上方', '斐波那契底部',
    '突破20日新高', '均线发散', '量价齐升',
    '资金连续净流入', '高换手率流入',
    '早晨之星', '突破盘整',
    'RSI极度超卖', '黄金坑',
]

# 推荐的信号组合
COMBO_2WAY = [
    ['MACD金叉', 'RSI超卖'], ['MACD金叉', '多头排列'], ['MACD金叉', 'CCI超卖'],
    ['MACD金叉', 'KDJ超卖'], ['MACD金叉', 'EMA多头排列'], ['MACD金叉', 'VWAP上方'],
    ['底背离', 'RSI超卖'], ['底背离', 'CCI超卖'], ['底背离', 'KDJ超卖'],
    ['KDJ金叉', 'RSI超卖'], ['KDJ金叉', 'CCI超卖'], ['KDJ金叉', 'MACD红柱'],
    ['KDJ金叉', 'VWAP上方'], ['KDJ金叉', 'EMA多头排列'],
    ['EMA金叉', 'RSI超卖'], ['EMA金叉', 'KDJ超卖'], ['EMA金叉', 'CCI超卖'],
    ['EMA多头排列', 'KDJ超卖'], ['EMA多头排列', 'CCI超卖'], ['EMA多头排列', 'RSI超卖'],
    ['突破20日新高', '量价齐升'], ['突破20日新高', 'MACD红柱'],
    ['RSI极度超卖', 'KDJ超卖'], ['RSI极度超卖', 'CCI超卖'], ['RSI极度超卖', '黄金坑'],
    ['多头排列', 'RSI超卖'], ['多头排列', 'CCI超卖'], ['多头排列', 'KDJ超卖'],
    ['CCI超卖', 'KDJ超卖'], ['CCI超卖', 'RSI超卖'],
    ['价格站上EMA200', '量价齐升'], ['价格站上EMA200', 'MACD红柱'],
    ['VWAP上方', 'RSI超卖'], ['VWAP上方', 'KDJ超卖'],
]

COMBO_3WAY = [
    ['MACD金叉', 'RSI超卖', '量价齐升'],
    ['MACD金叉', 'RSI超卖', 'CCI超卖'],
    ['KDJ金叉', 'RSI超卖', 'EMA多头排列'],
    ['KDJ金叉', 'CCI超卖', 'MACD红柱'],
    ['底背离', 'RSI超卖', 'KDJ超卖'],
    ['突破20日新高', '量价齐升', '资金连续净流入'],
    ['RSI极度超卖', 'KDJ超卖', '黄金坑'],
    ['EMA多头排列', 'KDJ超卖', 'CCI超卖'],
]

SHORT_TERM_SIGNALS = [
    'RSI超卖', 'RSI极度超卖', 'MACD金叉', 'MACD红柱',
    'KDJ金叉', 'KDJ超卖', 'CCI超卖', 'EMA金叉',
    '量价齐升', '资金连续净流入', '高换手率流入',
    '黄金坑',
]

LONG_TERM_SIGNALS = [
    '多头排列', 'EMA多头排列', '价格站上EMA200', 'VWAP上方',
    '突破20日新高', '均线发散', '底背离', '突破盘整',
    '早晨之星',
]


def detect_unified_signal(df, signal_name):
    """检测统一信号"""
    if df is None or len(df) < 30:
        return df
    
    df = df.copy()
    sig_col = f'信号_{signal_name}'
    df[sig_col] = False
    prev = df.shift(1)
    
    for i in range(1, len(df)):
        row, p = df.iloc[i], prev.iloc[i]
        
        if signal_name == 'RSI超卖' and row['RSI'] < 30:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'RSI极度超卖' and row['RSI'] < 15:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'MACD金叉' and row['MACD'] > row['MACD_SIGNAL'] and p['MACD'] <= p['MACD_SIGNAL']:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'MACD红柱' and row['MACD_HIST'] > 0:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == '多头排列' and row['MA5'] > row['MA10'] > row['MA20']:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'KDJ金叉' and row['K'] > row['D'] and p['K'] <= p['D'] and row['K'] < 80:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'KDJ超卖' and row['K'] < 20:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'CCI超卖' and row['CCI'] < -100:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'EMA金叉' and row['EMA20'] > row['EMA50'] and p['EMA20'] <= p['EMA50']:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'EMA多头排列' and row['EMA20'] > row['EMA50'] > row['EMA200']:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == '价格站上EMA200' and row['收盘'] > row['EMA200'] and p['收盘'] <= p['EMA200']:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == 'VWAP上方' and row['收盘'] > row['VWAP']:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == '突破20日新高' and i >= 20:
            high_20 = df.iloc[max(0,i-20):i]['收盘'].max()
            if row['收盘'] > high_20 and row['成交量'] > row['VOL_MA5'] * 1.3:
                df.loc[df.index[i], sig_col] = True
        elif signal_name == '均线发散' and row['MA5'] > row['MA10'] > row['MA20'] and row['MA5'] > row['MA20'] * 1.05:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == '量价齐升' and row['收盘'] > p['收盘'] and row['成交量'] > row['VOL_MA5']:
            df.loc[df.index[i], sig_col] = True
        elif signal_name == '资金连续净流入' and i >= 3:
            if row['收盘'] > p['收盘'] and p['收盘'] > prev.iloc[i-1]['收盘'] and prev.iloc[i-1]['收盘'] > prev.iloc[i-2]['收盘']:
                df.loc[df.index[i], sig_col] = True
        elif signal_name == '高换手率流入':
            vol_ratio = row['成交量'] / row['VOL_MA20'] if row['VOL_MA20'] > 0 else 0
            if vol_ratio > 1.5 and row['收盘'] > p['收盘']:
                df.loc[df.index[i], sig_col] = True
        elif signal_name == '黄金坑' and i >= 30:
            low_30 = df.iloc[max(0,i-30):i]['最低'].min()
            if abs(row['收盘'] - low_30) / low_30 < 0.05 and row['成交量'] < row['VOL_MA5'] * 0.7:
                df.loc[df.index[i], sig_col] = True
        elif signal_name == '底背离' and i >= 10:
            price_low = df.iloc[max(0,i-10):i]['收盘'].min()
            if row['收盘'] == price_low and row['RSI'] > df.iloc[max(0,i-10):i]['RSI'].min() + 5:
                df.loc[df.index[i], sig_col] = True
    
    return df


def backtest_unified_single(df, signal_name, signal_type='all'):
    """单信号回测
    
    Args:
        df: 数据
        signal_name: 信号名称
        signal_type: 'short' 短线(1,3,5日), 'long' 长线(5,10,20日), 'all' 全部
    """
    df = detect_unified_signal(df, signal_name)
    sig_col = f'信号_{signal_name}'
    
    if sig_col not in df.columns:
        return []
    
    rows = df[df[sig_col] == True]
    if len(rows) == 0:
        return []
    
    if signal_type == 'short':
        periods = [1, 3, 5]
    elif signal_type == 'long':
        periods = [5, 10, 20]
    else:
        periods = [1, 3, 5, 10, 20]
    
    results = []
    for days in periods:
        future = f'未来收益_{days}d'
        if future not in df.columns:
            continue
        returns = rows[future].dropna()
        if len(returns) == 0:
            continue
        results.append({
            'signal': signal_name,
            'signal_type': '短线' if days <= 5 else '长线',
            'days': days,
            'count': len(returns),
            'avg_return': returns.mean() * 100,
            'win_rate': (returns > 0).sum() / len(returns) * 100
        })
    return results


def backtest_unified_combo(df, combo, signal_type='all'):
    """组合信号回测
    
    Args:
        df: 数据
        combo: 信号组合列表
        signal_type: 'short' 短线(1,3,5日), 'long' 长线(5,10,20日), 'all' 全部
    """
    for sig in combo:
        df = detect_unified_signal(df, sig)
    
    combo_col = f"组合_{'_'.join(combo)}"
    df[combo_col] = True
    for sig in combo:
        sig_col = f'信号_{sig}'
        if sig_col in df.columns:
            df[combo_col] = df[combo_col] & df[sig_col]
        else:
            df[combo_col] = False
    
    rows = df[df[combo_col] == True]
    if len(rows) < 3:
        return []
    
    if signal_type == 'short':
        periods = [1, 3, 5]
    elif signal_type == 'long':
        periods = [5, 10, 20]
    else:
        periods = [1, 3, 5, 10, 20]
    
    results = []
    for days in periods:
        future = f'未来收益_{days}d'
        if future not in df.columns:
            continue
        returns = rows[future].dropna()
        if len(returns) == 0:
            continue
        results.append({
            'combo': ' + '.join(combo),
            'signal_type': '短线' if days <= 5 else '长线',
            'days': days,
            'count': len(returns),
            'avg_return': returns.mean() * 100,
            'win_rate': (returns > 0).sum() / len(returns) * 100
        })
    return results


def run_unified_backtest():
    """运行统一回测"""
    indices = [('000001','上证指数'), ('399006','创业板指')]
    
    all_results = {'single': [], 'combo2': [], 'combo3': []}
    
    for code, name in indices:
        print(f"\n{'='*50}")
        print(f"📊 回测: {name}")
        
        try:
            df = get_index_data(code, 365)
        except Exception as e:
            print(f"❌ 获取数据异常: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        if df is None:
            print(f"❌ 数据获取失败")
            continue
        
        print(f"✅ 数据: {len(df)}条, 时间范围: {df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}")
        df = calculate_basic_indicators(df)
        
        print("🔄 短线信号回测 (1,3,5日)...")
        for sig in SHORT_TERM_SIGNALS:
            for r in backtest_unified_single(df, sig, 'short'):
                r['index'] = name
                all_results['single'].append(r)
        
        print("🔄 长线信号回测 (5,10,20日)...")
        for sig in LONG_TERM_SIGNALS:
            for r in backtest_unified_single(df, sig, 'long'):
                r['index'] = name
                all_results['single'].append(r)
        
        print("🔄 双信号组合回测 (短线)...")
        for combo in COMBO_2WAY:
            for r in backtest_unified_combo(df, combo, 'short'):
                r['index'] = name
                all_results['combo2'].append(r)
        
        print("🔄 双信号组合回测 (长线)...")
        for combo in COMBO_2WAY:
            for r in backtest_unified_combo(df, combo, 'long'):
                r['index'] = name
                all_results['combo2'].append(r)
        
        print("🔄 三信号组合回测...")
        for combo in COMBO_3WAY:
            for r in backtest_unified_combo(df, combo, 'long'):
                r['index'] = name
                all_results['combo3'].append(r)
        
        print(f"   单信号: {len(all_results.get('single', []))} 条, 双信号: {len(all_results.get('combo2', []))} 条, 三信号: {len(all_results.get('combo3', []))} 条")
    
    return all_results


def print_best_results(results):
    """打印最优结果"""
    print("\n" + "="*80)
    print("🏆 一年期回测结果汇总")
    print("="*80)
    
    df_single = pd.DataFrame(results['single'])
    df_combo2 = pd.DataFrame(results['combo2'])
    df_combo3 = pd.DataFrame(results['combo3'])
    
    # 短线信号 TOP10 (1,3,5日)
    if not df_single.empty:
        short_df = df_single[df_single['signal_type'] == '短线']
        if not short_df.empty:
            short_avg = short_df.groupby('signal')['avg_return'].mean().sort_values(ascending=False)
            print("\n📈 【短线信号 TOP10】(1,3,5日平均收益)")
            print("-"*70)
            for sig, avg_ret in short_avg.head(10).items():
                sig_data = short_df[short_df['signal'] == sig]
                total_count = sig_data['count'].sum()
                avg_win = sig_data['win_rate'].mean()
                print(f"  {sig:15s} | 总次数:{total_count:4d} | 平均收益:{avg_ret:+6.2f}% | 平均胜率:{avg_win:5.1f}%")
    
    # 长线信号 TOP10 (5,10,20日)
    if not df_single.empty:
        long_df = df_single[df_single['signal_type'] == '长线']
        if not long_df.empty:
            long_avg = long_df.groupby('signal')['avg_return'].mean().sort_values(ascending=False)
            print("\n📈 【长线信号 TOP10】(5,10,20日平均收益)")
            print("-"*70)
            for sig, avg_ret in long_avg.head(10).items():
                sig_data = long_df[long_df['signal'] == sig]
                total_count = sig_data['count'].sum()
                avg_win = sig_data['win_rate'].mean()
                print(f"  {sig:15s} | 总次数:{total_count:4d} | 平均收益:{avg_ret:+6.2f}% | 平均胜率:{avg_win:5.1f}%")
    
    # 短线双信号组合 TOP10
    if not df_combo2.empty:
        short_combo = df_combo2[df_combo2['signal_type'] == '短线']
        if not short_combo.empty:
            short_combo_avg = short_combo.groupby('combo')['avg_return'].mean().sort_values(ascending=False)
            print("\n📈 【短线双信号组合 TOP10】(1,3,5日平均收益)")
            print("-"*70)
            for combo, avg_ret in short_combo_avg.head(10).items():
                combo_data = short_combo[short_combo['combo'] == combo]
                total_count = combo_data['count'].sum()
                avg_win = combo_data['win_rate'].mean()
                print(f"  {combo:35s} | 次数:{total_count:3d} | 收益:{avg_ret:+6.2f}% | 胜率:{avg_win:5.1f}%")
    
    # 长线双信号组合 TOP10
    if not df_combo2.empty:
        long_combo = df_combo2[df_combo2['signal_type'] == '长线']
        if not long_combo.empty:
            long_combo_avg = long_combo.groupby('combo')['avg_return'].mean().sort_values(ascending=False)
            print("\n📈 【长线双信号组合 TOP10】(5,10,20日平均收益)")
            print("-"*70)
            for combo, avg_ret in long_combo_avg.head(10).items():
                combo_data = long_combo[long_combo['combo'] == combo]
                total_count = combo_data['count'].sum()
                avg_win = combo_data['win_rate'].mean()
                print(f"  {combo:35s} | 次数:{total_count:3d} | 收益:{avg_ret:+6.2f}% | 胜率:{avg_win:5.1f}%")
    
    # 三信号组合
    if not df_combo3.empty:
        combo3_avg = df_combo3.groupby('combo')['avg_return'].mean().sort_values(ascending=False)
        print("\n📈 【三信号组合 TOP10】(5,10,20日平均收益)")
        print("-"*70)
        for combo, avg_ret in combo3_avg.head(10).items():
            combo_data = df_combo3[df_combo3['combo'] == combo]
            total_count = combo_data['count'].sum()
            avg_win = combo_data['win_rate'].mean()
            print(f"  {combo:40s} | 次数:{total_count:3d} | 收益:{avg_ret:+6.2f}% | 胜率:{avg_win:5.1f}%")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    print("🔄 开始一年期回测...")
    print("指数: 上证指数、创业板指")
    print("短线信号回测周期: 1,3,5日")
    print("长线信号回测周期: 5,10,20日")
    results = run_unified_backtest()
    print_best_results(results)

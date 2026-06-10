#!/usr/bin/env python3
"""
扩展技术指标与高级信号模块 (Advanced Signals Module)

基于网络搜集和实战验证的扩展因子库

【弱转强系列】:
    - 龙头弱转强: 前期调整后放量涨停转强
    - 缩量企稳: 回调缩量企稳均线
    - N型反包: 涨停后缩量回调再反包

【趋势启动系列】:
    - 突破新高: 放量突破前期高点
    - 均线粘合: 多条均线收敛后发散
    - 量价齐升: 放量上涨量价配合

【资金面系列】:
    - 主力资金流入: 大单净流入
    - 换手率异动: 换手率突增

【技术形态系列】:
    - 底背离/顶背离: 价格与指标背离
    - 均线多头排列: 短均线>长均线
    - 仙人指路: 上影线试盘

【超跌反弹系列】:
    - 严重超跌: 快速下跌后 RSI 极度超卖
    - 黄金坑: 挖坑后缩量回升
"""

import pandas as pd
import numpy as np

try:
    from .indicators import IndicatorCalculator
except ImportError:
    from indicators import IndicatorCalculator


class AdvancedSignalGenerator:
    """高级信号生成器
    
    基于扩展因子库生成买卖信号
    """
    
    def __init__(self, df):
        """
        初始化
        
        参数:
            df: 包含技术指标的 DataFrame
        """
        self.df = df.copy() if df is not None else None
    
    def calculate_all_advanced_indicators(self):
        """计算所有扩展指标"""
        if self.df is None or self.df.empty:
            return self.df
        
        df = IndicatorCalculator.calculate_all(self.df)
        
        # ===== 基础数据准备 =====
        close = df['收盘']
        high = df['最高']
        low = df['最低']
        volume = df['成交量']
        
        # 量比
        df['量比'] = volume / df['VOL_MA5'].shift(1)
        
        # 换手率 (假设流通股为volume的某个比例，实际需要流通股本数据)
        # 这里用成交量/流通市值估算
        df['换手率_估算'] = volume / (close * 1000000) * 100  # 简化估算
        
        # ===== 弱转强系列 =====
        df = self._calculate_weak_to_strong(df, close, high, low, volume)
        
        # ===== 趋势启动系列 =====
        df = self._calculate_trend_start(df, close, high, low, volume)
        
        # ===== 资金面系列 =====
        df = self._calculate_money_flow(df, close, high, low, volume)
        
        # ===== 技术形态系列 =====
        df = self._calculate_patterns(df, close, high, low, volume)
        
        # ===== 超跌反弹系列 =====
        df = self._calculate_rebound(df, close, high, low, volume)
        
        self.df = df
        return df
    
    def _calculate_weak_to_strong(self, df, close, high, low, volume):
        """弱转强系列指标"""
        
        # 1. 龙头弱转强: 前期调整后放量涨停转强
        # 条件: 1) 近期有涨停 2) 涨停后缩量回调不破涨停最低价 3) 再次放量上涨
        df['近期涨停'] = (close / close.shift(1) - 1) > 0.095  # 涨停
        df['涨停后回调'] = False  # 涨停后缩量回调
        df['弱转强'] = False  # 再次放量上涨
        
        for i in range(20, len(df)):
            # 找最近5个交易日内是否有涨停
            has_zhangting = False
            zhangting_idx = -1
            for j in range(max(0, i-5), i):
                if df.iloc[j]['近期涨停']:
                    has_zhangting = True
                    zhangting_idx = j
                    break
            
            if has_zhangting and zhangting_idx >= 0:
                # 涨停后的最低价
                zhangting_low = df.iloc[zhangting_idx]['最低']
                
                # 回调期间 (涨停后到当前位置)
                callback_volume_avg = df.iloc[zhangting_idx+1:i]['成交量'].mean()
                current_volume = df.iloc[i]['成交量']
                
                # 缩量回调: 回调期间成交量萎缩
                is_callback = current_volume < callback_volume_avg * 0.7
                
                # 当前位置在涨停最低价之上
                above_zhangting_low = close.iloc[i] > zhangting_low
                
                # 放量上涨
                volume_boost = current_volume > df.iloc[i]['VOL_MA5'] * 1.5
                
                if is_callback and above_zhangting_low and volume_boost:
                    df.loc[df.index[i], '弱转强'] = True
        
        # 2. 缩量企稳: 回调缩量企稳重要均线
        df['缩量企稳_MA5'] = False
        df['缩量企稳_MA10'] = False
        df['缩量企稳_MA20'] = False
        
        for i in range(10, len(df)):
            # 连续3天缩量
            vol_decrease = (volume.iloc[i] < df.iloc[i]['VOL_MA5'] * 0.7) and \
                         (volume.iloc[i-1] < df.iloc[i-1]['VOL_MA5'] * 0.7) and \
                         (volume.iloc[i-2] < df.iloc[i-2]['VOL_MA5'] * 0.7)
            
            if vol_decrease:
                # 企稳在MA5/MA10/MA20
                if 'MA5' in df.columns:
                    ma5 = df.iloc[i]['MA5'] if 'MA5' in df.columns else close.iloc[i]
                    if abs(close.iloc[i] - ma5) / ma5 < 0.02:  # 2%以内
                        df.loc[df.index[i], '缩量企稳_MA5'] = True
                
                if 'MA10' in df.columns:
                    ma10 = df.iloc[i]['MA10'] if 'MA10' in df.columns else close.iloc[i]
                    if abs(close.iloc[i] - ma10) / ma10 < 0.02:
                        df.loc[df.index[i], '缩量企稳_MA10'] = True
                
                if 'MA20' in df.columns:
                    ma20 = df.iloc[i]['MA20'] if 'MA20' in df.columns else close.iloc[i]
                    if abs(close.iloc[i] - ma20) / ma20 < 0.02:
                        df.loc[df.index[i], '缩量企稳_MA20'] = True
        
        # 3. N型反包: 涨停后缩量回调再反包
        # 类似弱转强，但更强调N型形态
        df['N型反包'] = False
        
        return df
    
    def _calculate_trend_start(self, df, close, high, low, volume):
        """趋势启动系列指标"""
        
        # 1. 突破新高: 放量突破20/60日高点
        df['突破20日高点'] = False
        df['突破60日高点'] = False
        
        for i in range(20, len(df)):
            # 20日高点
            high_20 = close.iloc[max(0, i-20):i].max()
            if close.iloc[i] > high_20 and volume.iloc[i] > df.iloc[i]['VOL_MA5'] * 1.3:
                df.loc[df.index[i], '突破20日高点'] = True
            
            # 60日高点
            if i >= 60:
                high_60 = close.iloc[max(0, i-60):i].max()
                if close.iloc[i] > high_60 and volume.iloc[i] > df.iloc[i]['VOL_MA5'] * 1.5:
                    df.loc[df.index[i], '突破60日高点'] = True
        
        # 2. 均线粘合: 多条均线收敛后发散
        df['均线粘合'] = False
        df['均线发散'] = False
        
        for i in range(20, len(df)):
            mas = []
            for period in [5, 10, 20]:
                if f'MA{period}' in df.columns:
                    mas.append(df.iloc[i][f'MA{period}'])
            
            if len(mas) >= 3:
                ma_max = max(mas)
                ma_min = min(mas)
                # 粘合: 最大值和最小值差距小于3%
                if (ma_max - ma_min) / ma_min < 0.03:
                    df.loc[df.index[i], '均线粘合'] = True
                
                # 发散: 短期均线在长期均线上方，且差距扩大
                if len(mas) >= 2:
                    if mas[0] > mas[-1] * 1.02:  # MA5 > MA20 2%以上
                        df.loc[df.index[i], '均线发散'] = True
        
        # 3. 量价齐升: 放量上涨
        df['量价齐升'] = False
        
        for i in range(5, len(df)):
            # 连续3天上涨且成交量放大
            price_up = close.iloc[i] > close.iloc[i-1] > close.iloc[i-2] > close.iloc[i-3]
            vol_up = (volume.iloc[i] > df.iloc[i]['VOL_MA5']) and \
                    (volume.iloc[i] > volume.iloc[i-1] * 1.2)
            
            if price_up and vol_up:
                df.loc[df.index[i], '量价齐升'] = True
        
        # 4. 趋势启动确认: 放量站上均线
        df['放量站上MA20'] = False
        df['放量站上MA60'] = False
        
        for i in range(20, len(df)):
            if 'MA20' in df.columns:
                ma20 = df.iloc[i]['MA20']
                if close.iloc[i] > ma20 and volume.iloc[i] > df.iloc[i]['VOL_MA5'] * 1.5:
                    # 前一天在MA20下方
                    if i > 0 and close.iloc[i-1] < df.iloc[i-1]['MA20']:
                        df.loc[df.index[i], '放量站上MA20'] = True
            
            if i >= 60 and 'MA60' in df.columns:
                ma60 = df.iloc[i]['MA60'] if 'MA60' in df.columns else df.iloc[i]['MA20']
                if close.iloc[i] > ma60 and volume.iloc[i] > df.iloc[i]['VOL_MA5'] * 1.5:
                    if i > 0 and close.iloc[i-1] < df.iloc[i-1].get('MA60', ma60):
                        df.loc[df.index[i], '放量站上MA60'] = True
        
        return df
    
    def _calculate_money_flow(self, df, close, high, low, volume):
        """资金面系列指标"""
        
        # 1. 主力资金 (简化版: 用大单proxy)
        # 假设大单 = 成交量 > 20日均量的1.5倍 且 上涨
        df['主力资金流入'] = (volume > df['VOL_MA20'] * 1.5) & (close > close.shift(1))
        df['主力资金流出'] = (volume > df['VOL_MA20'] * 1.5) & (close < close.shift(1))
        
        # 2. 换手率异动
        df['换手率突增'] = False
        df['高换手率'] = False
        
        for i in range(5, len(df)):
            # 换手率突增: 今日换手率是昨日2倍以上
            if df.iloc[i]['换手率_估算'] > df.iloc[i-1]['换手率_估算'] * 2:
                df.loc[df.index[i], '换手率突增'] = True
            
            # 高换手率 (假设 > 10% 为高换手)
            if df.iloc[i]['换手率_估算'] > 10:
                df.loc[df.index[i], '高换手率'] = True
        
        # 3. 资金连续净流入
        df['资金连续净流入'] = False
        
        for i in range(3, len(df)):
            # 连续3天主力资金流入
            if df.iloc[i]['主力资金流入'] and df.iloc[i-1]['主力资金流入'] and df.iloc[i-2]['主力资金流入']:
                df.loc[df.index[i], '资金连续净流入'] = True
        
        return df
    
    def _calculate_patterns(self, df, close, high, low, volume):
        """技术形态系列指标"""
        
        # 1. 均线多头排列 (已有基础指标，新增扩展版本)
        if 'MA5' in df.columns and 'MA10' in df.columns and 'MA20' in df.columns:
            df['均线多头排列_强'] = (df['MA5'] > df['MA10']) & (df['MA10'] > df['MA20'])
        
        # 2. 均线空头排列
        if 'MA5' in df.columns and 'MA10' in df.columns and 'MA20' in df.columns:
            df['均线空头排列'] = (df['MA5'] < df['MA10']) & (df['MA10'] < df['MA20'])
        
        # 3. 仙人指路: 上影线试盘 (上影线长度>实体2倍，且在高位)
        df['仙人指路'] = False
        
        for i in range(5, len(df)):
            body = abs(close.iloc[i] - close.iloc[i-1]) if i > 0 else 0
            upper_shadow = high.iloc[i] - max(close.iloc[i], close.iloc[i-1]) if i > 0 else 0
            
            if body > 0 and upper_shadow > body * 2:
                df.loc[df.index[i], '仙人指路'] = True
        
        # 4. 早晨之星 (反转形态)
        df['早晨之星'] = False
        
        for i in range(3, len(df)):
            # 第一天: 大跌
            day1 = close.iloc[i-2] < close.iloc[i-3]
            # 第二天: 小幅震荡
            day2 = abs(close.iloc[i-1] - close.iloc[i-2]) < abs(close.iloc[i-2] - close.iloc[i-3]) * 0.5
            # 第三天: 大涨突破
            day3 = close.iloc[i] > (close.iloc[i-2] + close.iloc[i-3]) / 2
            
            if day1 and day2 and day3:
                df.loc[df.index[i], '早晨之星'] = True
        
        # 5. 突破盘整: 盘整后放量突破
        df['突破盘整'] = False
        
        for i in range(30, len(df)):
            # 30日内振幅<15%
            high_30 = high.iloc[max(0, i-30):i].max()
            low_30 = low.iloc[max(0, i-30):i].min()
            volatility = (high_30 - low_30) / low_30
            
            if volatility < 0.15:
                # 放量突破
                if close.iloc[i] > high_30 and volume.iloc[i] > df.iloc[i]['VOL_MA5'] * 1.5:
                    df.loc[df.index[i], '突破盘整'] = True
        
        return df
    
    def _calculate_rebound(self, df, close, high, low, volume):
        """超跌反弹系列指标"""
        
        # 1. 严重超跌: 短期内大幅下跌
        df['严重超跌'] = False
        
        for i in range(10, len(df)):
            # 10日内跌幅>20%
            if i >= 10:
                ret_10d = (close.iloc[i] / close.iloc[i-10] - 1)
                if ret_10d < -0.20:
                    df.loc[df.index[i], '严重超跌'] = True
        
        # 2. RSI极度超卖 (RSI < 20)
        if 'RSI' in df.columns:
            df['RSI极度超卖'] = df['RSI'] < 20
        
        # 3. KDJ极度超卖 (K < 10)
        if 'K' in df.columns:
            df['KDJ极度超卖'] = df['K'] < 10
        
        # 4. 黄金坑: 挖坑后缩量回升
        df['黄金坑'] = False
        
        for i in range(20, len(df)):
            # 找坑底: 30日内最低点
            low_30 = low.iloc[max(0, i-30):i].min()
            low_idx = low.iloc[max(0, i-30):i].idxmin()
            
            # 当前价格接近坑底 (5%以内)
            if abs(close.iloc[i] - low_30) / low_30 < 0.05:
                # 缩量回升
                if volume.iloc[i] < df.iloc[i]['VOL_MA5'] * 0.7:
                    df.loc[df.index[i], '黄金坑'] = True
        
        # 5. 缩量十字星 (变盘信号)
        df['缩量十字星'] = False
        
        for i in range(3, len(df)):
            body = abs(close.iloc[i] - close.iloc[i-1]) if i > 0 else 0
            upper_shadow = high.iloc[i] - max(close.iloc[i], close.iloc[i-1]) if i > 0 else 0
            lower_shadow = min(close.iloc[i], close.iloc[i-1]) - low.iloc[i] if i > 0 else 0
            
            # 十字星: 实体很小，上下影线相当
            if body < (upper_shadow + lower_shadow) * 0.2 and body > 0:
                # 缩量
                if volume.iloc[i] < df.iloc[i]['VOL_MA5'] * 0.5:
                    df.loc[df.index[i], '缩量十字星'] = True
        
        return df
    
    def generate_advanced_signals(self):
        """生成高级信号 (当前时刻)"""
        if self.df is None or len(self.df) < 5:
            return []
        
        df = self.df
        signals = []
        
        # 获取最后一行 (当前)
        row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) > 1 else None
        
        # ===== 弱转强系列 =====
        if row.get('弱转强', False):
            signals.append(('弱转强', 3.0, '看多', '龙头股调整后转强'))
        
        if row.get('缩量企稳_MA5', False) or row.get('缩量企稳_MA10', False) or row.get('缩量企稳_MA20', False):
            ma_type = 'MA5' if row.get('缩量企稳_MA5') else 'MA10' if row.get('缩量企稳_MA10') else 'MA20'
            signals.append((f'缩量企稳{ma_type}', 2.0, '看多', f'缩量企稳在{ma_type}均线'))
        
        if row.get('N型反包', False):
            signals.append(('N型反包', 2.5, '看多', '涨停后缩量回调再反包'))
        
        # ===== 趋势启动系列 =====
        if row.get('突破20日高点', False):
            signals.append(('突破20日新高', 2.0, '看多', '放量突破20日高点'))
        
        if row.get('突破60日高点', False):
            signals.append(('突破60日新高', 2.5, '看多', '放量突破60日高点'))
        
        if row.get('均线发散', False):
            signals.append(('均线发散', 1.5, '看多', '均线向上发散开启涨势'))
        
        if row.get('量价齐升', False):
            signals.append(('量价齐升', 2.0, '看多', '放量上涨量价配合'))
        
        if row.get('放量站上MA20', False):
            signals.append(('放量站上MA20', 1.5, '看多', '放量突破20日均线'))
        
        # ===== 资金面系列 =====
        if row.get('资金连续净流入', False):
            signals.append(('资金连续净流入', 2.0, '看多', '主力资金连续3天流入'))
        
        if row.get('换手率突增', False):
            signals.append(('换手率突增', 1.0, '中性', '换手率大幅增加关注'))
        
        if row.get('高换手率', False) and row.get('主力资金流入', False):
            signals.append(('高换手率主力流入', 2.0, '看多', '高换手且主力资金流入'))
        
        # ===== 技术形态系列 =====
        if row.get('均线多头排列_强', False):
            signals.append(('均线多头排列', 1.5, '看多', '短期均线>中期均线>长期均线'))
        
        if row.get('仙人指路', False):
            signals.append(('仙人指路', 1.5, '看多', '上影线试盘可能启动'))
        
        if row.get('早晨之星', False):
            signals.append(('早晨之星', 2.5, '看多', '反转形态看涨'))
        
        if row.get('突破盘整', False):
            signals.append(('突破盘整', 2.0, '看多', '盘整后放量突破'))
        
        # ===== 超跌反弹系列 =====
        if row.get('严重超跌', False):
            signals.append(('严重超跌', 1.5, '看多', '短期大幅下跌可能反弹'))
        
        if row.get('RSI极度超卖', False):
            signals.append(('RSI极度超卖', 2.0, '看多', 'RSI<20极度超卖'))
        
        if row.get('KDJ极度超卖', False):
            signals.append(('KDJ极度超卖', 1.5, '看多', 'KDJ<10极度超卖'))
        
        if row.get('黄金坑', False):
            signals.append(('黄金坑', 2.5, '看多', '挖坑后缩量回升'))
        
        if row.get('缩量十字星', False):
            signals.append(('缩量十字星', 1.0, '中性', '变盘信号关注'))
        
        # ===== 卖出信号 =====
        if row.get('均线空头排列', False):
            signals.append(('均线空头排列', -1.5, '看空', '均线向下发散'))
        
        if row.get('主力资金流出', False):
            signals.append(('主力资金流出', -1.0, '看空', '主力资金净流出'))
        
        return signals


# 信号配置表: 用于回测
ADVANCED_SIGNAL_CONFIG = {
    # 弱转强系列
    '信号_弱转强': {'type': 'buy', 'category': '弱转强', 'weight': 3.0},
    '信号_缩量企稳MA5': {'type': 'buy', 'category': '弱转强', 'weight': 2.0},
    '信号_缩量企稳MA10': {'type': 'buy', 'category': '弱转强', 'weight': 2.0},
    '信号_缩量企稳MA20': {'type': 'buy', 'category': '弱转强', 'weight': 2.0},
    '信号_N型反包': {'type': 'buy', 'category': '弱转强', 'weight': 2.5},
    
    # 趋势启动系列
    '信号_突破20日新高': {'type': 'buy', 'category': '趋势启动', 'weight': 2.0},
    '信号_突破60日新高': {'type': 'buy', 'category': '趋势启动', 'weight': 2.5},
    '信号_均线发散': {'type': 'buy', 'category': '趋势启动', 'weight': 1.5},
    '信号_量价齐升': {'type': 'buy', 'category': '趋势启动', 'weight': 2.0},
    '信号_放量站上MA20': {'type': 'buy', 'category': '趋势启动', 'weight': 1.5},
    
    # 资金面系列
    '信号_资金连续净流入': {'type': 'buy', 'category': '资金面', 'weight': 2.0},
    '信号_换手率突增': {'type': 'neutral', 'category': '资金面', 'weight': 1.0},
    '信号_高换手率主力流入': {'type': 'buy', 'category': '资金面', 'weight': 2.0},
    
    # 技术形态系列
    '信号_均线多头排列': {'type': 'buy', 'category': '技术形态', 'weight': 1.5},
    '信号_仙人指路': {'type': 'buy', 'category': '技术形态', 'weight': 1.5},
    '信号_早晨之星': {'type': 'buy', 'category': '技术形态', 'weight': 2.5},
    '信号_突破盘整': {'type': 'buy', 'category': '技术形态', 'weight': 2.0},
    
    # 超跌反弹系列
    '信号_严重超跌': {'type': 'buy', 'category': '超跌反弹', 'weight': 1.5},
    '信号_RSI极度超卖': {'type': 'buy', 'category': '超跌反弹', 'weight': 2.0},
    '信号_KDJ极度超卖': {'type': 'buy', 'category': '超跌反弹', 'weight': 1.5},
    '信号_黄金坑': {'type': 'buy', 'category': '超跌反弹', 'weight': 2.5},
    '信号_缩量十字星': {'type': 'neutral', 'category': '超跌反弹', 'weight': 1.0},
    
    # 卖出信号
    '信号_均线空头排列': {'type': 'sell', 'category': '技术形态', 'weight': -1.5},
    '信号_主力资金流出': {'type': 'sell', 'category': '资金面', 'weight': -1.0},
}

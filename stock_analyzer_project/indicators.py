#!/usr/bin/env python3
"""
技术指标计算与买卖信号模块 (Indicators & Signals Module)

负责计算各种技术指标并生成买卖信号

【短线指标】(适用于短线/超短线交易):
    - MA5, MA10, MA20: 移动平均线
    - AO (Awesome Oscillator): 动量指标
    - BBD: 主力资金指标
    - MACD: 趋势指标
    - RSI: 相对强弱指标 (短线用)

【长线指标】(适用于中长线趋势交易):
    - EMA20, EMA50, EMA200: 指数移动平均线
    - KDJ: 随机指标
    - CCI: 顺势指标
    - ATR: 平均真实波幅
    - VWAP: 成交量加权平均价
    - 斐波那契区域
"""

import pandas as pd
import numpy as np

try:
    from .indicator_engine import CanonicalIndicatorEngine, INDICATOR_SPECS
except ImportError:
    from indicator_engine import CanonicalIndicatorEngine, INDICATOR_SPECS


class LegacyIndicatorCalculator:
    """技术指标计算器
    
    计算各种常用的技术分析指标
    """
    
    @staticmethod
    def calculate_all(df):
        """计算所有技术指标
        
        参数:
            df: 包含 OHLCV 数据的 DataFrame
                必需列: '收盘', '最高', '最低', '成交量'
        
        返回:
            DataFrame: 添加了所有技术指标的数据
        """
        if df is None or df.empty:
            return df
        
        df = df.copy()
        
        # 短线指标
        df = IndicatorCalculator.calculate_moving_averages(df)
        df = IndicatorCalculator.calculate_ao(df)
        df = IndicatorCalculator.calculate_macd(df)
        df = IndicatorCalculator.calculate_rsi(df)
        
        # 长线指标
        df = IndicatorCalculator.calculate_ema(df)
        df = IndicatorCalculator.calculate_kdj(df)
        df = IndicatorCalculator.calculate_cci(df)
        df = IndicatorCalculator.calculate_atr(df)
        df = IndicatorCalculator.calculate_vwap(df)
        df = IndicatorCalculator.calculate_fib_zone(df)
        
        return df
    
    # ==================== 移动平均线 ====================
    
    @staticmethod
    def calculate_moving_averages(df, periods=[5, 10, 20]):
        """计算移动平均线
        
        参数:
            df: DataFrame，需包含 '收盘' 列
            periods: 均线周期列表
        
        返回:
            DataFrame: 添加了 MA 均线
        """
        close = df['收盘']
        
        for period in periods:
            df[f'MA{period}'] = close.rolling(window=period).mean()
        
        # 成交量均线
        if '成交量' in df.columns:
            df['VOL_MA5'] = df['成交量'].rolling(window=5).mean()
        
        return df
    
    # ==================== AO (Awesome Oscillator) ====================
    
    @staticmethod
    def calculate_ao(df):
        """计算 AO (Awesome Oscillator) 动量指标
        
        AO 指标计算:
            1. AL = (最高价 + 最低价) / 2
            2. SMA_AL_5 = AL 的 5 日简单移动平均
            3. SMA_AL_13 = AL 的 13 日简单移动平均
            4. AO = SMA_AL_5 - SMA_AL_13
        
        参数:
            df: DataFrame，需包含 '最高', '最低', '收盘' 列
        
        返回:
            DataFrame: 添加了 AO 及其相关指标
        """
        high = df['最高']
        low = df['最低']
        close = df['收盘']
        
        # AL (典型价格) = (最高 + 最低 + 收盘) / 3
        df['AL'] = (close + low + high) / 3
        
        # SMA 移动平均
        df['SMA_AL_5'] = df['AL'].rolling(window=5).mean()
        df['SMA_AL_13'] = df['AL'].rolling(window=13).mean()
        
        # AO 动量指标
        df['AO'] = df['SMA_AL_5'] - df['SMA_AL_13']
        
        # BBD 主力资金指标 = (AO - AO的3日均线) * 100
        df['BBD'] = (df['AO'] - df['AO'].rolling(window=3).mean()) * 100
        
        # 动能线系列
        df['动能线'] = df['AO'] * 10
        df['动能辅线'] = df['AO'].ewm(span=5, adjust=False).mean() * 10
        
        return df
    
    # ==================== MACD ====================
    
    @staticmethod
    def calculate_macd(df, fast=12, slow=26, signal=9):
        """计算 MACD (Moving Average Convergence Divergence)
        
        MACD 指标计算:
            1. DIF = EMA(12) - EMA(26)
            2. DEA = EMA(9)
            3. MACD = (DIF - DEA) * 2
        
        参数:
            df: DataFrame，需包含 '收盘' 列
            fast: 快速 EMA 周期 (默认 12)
            slow: 慢速 EMA 周期 (默认 26)
            signal: 信号线周期 (默认 9)
        
        返回:
            DataFrame: 添加了 MACD 指标
        """
        close = df['收盘']
        
        # 计算 EMA
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        
        # DIF (MACD 线)
        df['DIF'] = ema_fast - ema_slow
        
        # DEA (信号线)
        df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()
        
        # MACD 柱状图
        df['MACD'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    
    # ==================== RSI ====================
    
    @staticmethod
    def calculate_rsi(df, period=14):
        """计算 RSI (Relative Strength Index)
        
        RSI 指标计算:
            1. 上涨平均值 = 上涨额度的 N 日移动平均
            2. 下跌平均值 = 下跌额度的 N 日移动平均
            3. RS = 上涨平均值 / 下跌平均值
            4. RSI = 100 - (100 / (1 + RS))
        
        参数:
            df: DataFrame，需包含 '收盘' 列
            period: RSI 周期 (默认 14)
        
        返回:
            DataFrame: 添加了 RSI 指标
        """
        close = df['收盘']
        
        # 计算价格变动
        delta = close.diff()
        
        # 分离上涨和下跌
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # 计算平均涨跌幅
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # 计算 RS 和 RSI
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    
    # ==================== 长线指标: EMA ====================
    
    @staticmethod
    def calculate_ema(df, periods=[20, 50, 200]):
        """计算指数移动平均线 (EMA)
        
        参数:
            df: DataFrame，需包含 '收盘' 列
            periods: EMA 周期列表
        
        返回:
            DataFrame: 添加了 EMA 均线
        """
        close = df['收盘']
        
        for period in periods:
            df[f'EMA{period}'] = close.ewm(span=period, adjust=False).mean()
        
        return df
    
    # ==================== 长线指标: KDJ ====================
    
    @staticmethod
    def calculate_kdj(df, n=9, m1=3, m2=3):
        """计算 KDJ 随机指标
        
        KDJ 指标计算:
            1. RSV = (收盘价 - N日内最低价) / (N日内最高价 - N日内最低价) * 100
            2. K = 2/3 * K_prev + 1/3 * RSV
            3. D = 2/3 * D_prev + 1/3 * K
            4. J = 3 * K - 2 * D
        
        参数:
            df: DataFrame，需包含 '最高', '最低', '收盘' 列
            n: RSV 周期 (默认 9)
            m1: K 平滑周期 (默认 3)
            m2: D 平滑周期 (默认 3)
        
        返回:
            DataFrame: 添加了 K, D, J 指标
        """
        high = df['最高']
        low = df['最低']
        close = df['收盘']
        
        lowest_low = low.rolling(window=n).min()
        highest_high = high.rolling(window=n).max()
        
        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        rsv = rsv.fillna(50)
        
        df['K'] = rsv.ewm(com=(m1-1)/3, adjust=False).mean()
        df['D'] = df['K'].ewm(com=(m2-1)/3, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        
        return df
    
    # ==================== 长线指标: CCI ====================
    
    @staticmethod
    def calculate_cci(df, period=14):
        """计算 CCI 顺势指标
        
        CCI 指标计算:
            1. TP = (最高价 + 最低价 + 收盘价) / 3
            2. SMA_TP = TP 的 N 日简单移动平均
            3. MAD = TP 与 SMA_TP 的平均绝对偏差
            4. CCI = (TP - SMA_TP) / (MAD * 0.015)
        
        参数:
            df: DataFrame，需包含 '最高', '最低', '收盘' 列
            period: CCI 周期 (默认 14)
        
        返回:
            DataFrame: 添加了 CCI 指标
        """
        high = df['最高']
        low = df['最低']
        close = df['收盘']
        
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        df['CCI'] = (tp - sma_tp) / (mad * 0.015)
        
        return df
    
    # ==================== 长线指标: ATR ====================
    
    @staticmethod
    def calculate_atr(df, period=14):
        """计算 ATR 平均真实波幅
        
        ATR 指标计算:
            1. TR = max(最高-最低, |最高-前收盘|, |最低-前收盘|)
            2. ATR = TR 的 N 日简单移动平均
        
        参数:
            df: DataFrame，需包含 '最高', '最低', '收盘' 列
            period: ATR 周期 (默认 14)
        
        返回:
            DataFrame: 添加了 ATR 指标
        """
        high = df['最高']
        low = df['最低']
        close = df['收盘']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(window=period).mean()
        
        return df
    
    # ==================== 长线指标: VWAP ====================
    
    @staticmethod
    def calculate_vwap(df):
        """计算 VWAP 成交量加权平均价
        
        VWAP = Σ(收盘价 * 成交量) / Σ成交量
        
        参数:
            df: DataFrame，需包含 '收盘', '成交量' 列
        
        返回:
            DataFrame: 添加了 VWAP 指标
        """
        close = df['收盘']
        volume = df['成交量']
        
        cumulative_tpv = (close * volume).cumsum()
        cumulative_vol = volume.cumsum()
        df['VWAP'] = cumulative_tpv / cumulative_vol
        
        return df
    
    # ==================== 长线指标: 斐波那契 ====================
    
    @staticmethod
    def calculate_fib_zone(df, period=21):
        """计算斐波那契回撤区域
        
        基于 N 日最高价和最低价计算支撑阻力位:
        - 0% (最高价)
        - 23.6%
        - 38.2%
        - 61.8%
        - 76.4%
        - 100% (最低价)
        
        参数:
            df: DataFrame，需包含 '最高', '最低' 列
            period: 计算周期 (默认 21)
        
        返回:
            DataFrame: 添加了斐波那契区域各价位
        """
        high = df['最高']
        low = df['最低']
        
        hl = high.rolling(window=period).max()
        ll = low.rolling(window=period).min()
        dist = hl - ll
        
        df['FIB_High'] = hl
        df['FIB_0236'] = hl - dist * 0.236
        df['FIB_0382'] = hl - dist * 0.382
        df['FIB_0618'] = hl - dist * 0.618
        df['FIB_0764'] = hl - dist * 0.764
        df['FIB_Low'] = ll
        
        return df


for _method_name in (
    "calculate_all",
    "calculate_moving_averages",
    "calculate_ao",
    "calculate_macd",
    "calculate_rsi",
    "calculate_ema",
    "calculate_kdj",
    "calculate_cci",
    "calculate_atr",
    "calculate_vwap",
    "calculate_fib_zone",
):
    setattr(
        LegacyIndicatorCalculator,
        _method_name,
        getattr(CanonicalIndicatorEngine, _method_name),
    )


class IndicatorCalculator(CanonicalIndicatorEngine):
    """项目统一技术指标入口；具体口径见 ``INDICATOR_SPECS``。"""


class SignalGenerator:
    """买卖信号生成器
    
    根据技术指标生成买卖信号并进行评分
    """
    
    def __init__(self, df):
        """
        初始化信号生成器
        
        参数:
            df: 包含技术指标的 DataFrame
        """
        self.df = df
    
    def generate_signals(self):
        """生成买卖信号
        
        【短线信号】(适用于短线/超短线交易):
            - 底背离: 价格创新低，BBD 没有创新低
            - 动能金叉: 动能线上穿动能辅线
            - MACD 金叉: DIF 上穿 DEA
            - 多头排列: MA5 > MA10 > MA20，且价格在 MA5 之上
            - RSI 超卖: RSI < 30
        
        【长线信号】(适用于中长线趋势交易):
            - KDJ 金叉: K 上穿 D，且在超卖区域
            - KDJ 超卖: K < 20, D < 20
            - CCI 超卖: CCI < -100
            - EMA 金叉: EMA20 上穿 EMA50
            - 多头趋势: 价格 > EMA200
            - VWAP 位置: 价格在 VWAP 上方
        
        返回:
            list: 信号列表 (每个信号包含 'name', 'type', 'score', 'description', 'category' 属性)
        """
        if self.df is None or len(self.df) < 2:
            return []
        
        signals = []
        curr = self.df.iloc[-1]  # 最新数据
        prev = self.df.iloc[-2]  # 前一天数据
        
        # ==================== 短线信号 ====================
        
        # ===== 底背离检测 =====
        # 条件: 20日内最低价，且 BBD 没有创新低
        if len(self.df) >= 20:
            min_price_20 = self.df['收盘'].iloc[-20:].min()
            min_bbd_20 = self.df['BBD'].iloc[-20:].min()
            
            if pd.notna(curr.get('BBD')) and pd.notna(min_bbd_20):
                if curr['收盘'] == min_price_20 and curr['BBD'] > min_bbd_20:
                    signals.append({
                        'name': '底背离',
                        'type': 'bullish',
                        'score': 2.5,
                        'category': '短线',
                        'description': '价格创新低但BBD未创新低，可能反转上涨'
                    })
        
        # ===== 动能金叉 =====
        if pd.notna(curr.get('动能线')) and pd.notna(prev.get('动能线')):
            if curr['动能线'] > curr['动能辅线'] and prev['动能线'] <= prev['动能辅线']:
                signals.append({
                    'name': '动能金叉',
                    'type': 'bullish',
                    'score': 2.0,
                    'category': '短线',
                    'description': '动能线上穿辅线，短期动量转强'
                })
        
        # ===== 强势区间 =====
        if pd.notna(curr.get('AO')) and pd.notna(curr.get('BBD')):
            if curr['AO'] > 0 and curr['BBD'] > 0:
                signals.append({
                    'name': '强势区间',
                    'type': 'bullish',
                    'score': 1.0,
                    'category': '短线',
                    'description': 'AO和BBD都为正，市场处于强势'
                })
        
        # ===== BBD 上零轴 =====
        if pd.notna(curr.get('BBD')) and pd.notna(prev.get('BBD')):
            if curr['BBD'] > 0 and prev['BBD'] <= 0:
                signals.append({
                    'name': 'BBD上零轴',
                    'type': 'bullish',
                    'score': 0.5,
                    'category': '短线',
                    'description': '主力资金开始净流入'
                })
        
        # ===== MACD 金叉 =====
        if pd.notna(curr.get('DIF')) and pd.notna(prev.get('DIF')):
            if curr['DIF'] > curr['DEA'] and prev['DIF'] <= prev['DEA']:
                signals.append({
                    'name': 'MACD金叉',
                    'type': 'bullish',
                    'score': 1.5,
                    'category': '短线',
                    'description': 'DIF上穿DEA，趋势转多'
                })
            elif pd.notna(curr.get('MACD')) and pd.notna(prev.get('MACD')):
                if curr['MACD'] > 0 and curr['MACD'] > prev['MACD']:
                    signals.append({
                        'name': 'MACD红柱',
                        'type': 'bullish',
                        'score': 0.5,
                        'category': '短线',
                        'description': 'MACD红柱放大，多头力量增强'
                    })
        
        # ===== 多头排列 =====
        if pd.notna(curr.get('MA5')) and pd.notna(curr.get('MA10')):
            if curr['MA5'] > curr['MA10'] and curr['收盘'] > curr['MA5']:
                signals.append({
                    'name': '多头排列',
                    'type': 'bullish',
                    'score': 1.0,
                    'category': '短线',
                    'description': '均线多头排列，短期趋势向上'
                })
            elif curr['MA5'] < curr['MA10'] and curr['收盘'] < curr['MA5']:
                signals.append({
                    'name': '空头排列',
                    'type': 'bearish',
                    'score': -1.0,
                    'category': '短线',
                    'description': '均线空头排列，短期趋势向下'
                })
        
        # ===== RSI 超买超卖 =====
        if pd.notna(curr.get('RSI')):
            if curr['RSI'] < 20:
                signals.append({
                    'name': 'RSI严重超卖',
                    'type': 'bullish',
                    'score': 1.0,
                    'category': '短线',
                    'description': 'RSI低于20，可能存在反弹机会'
                })
            elif curr['RSI'] < 30:
                signals.append({
                    'name': 'RSI超卖',
                    'type': 'bullish',
                    'score': 0.5,
                    'category': '短线',
                    'description': 'RSI低于30，存在超卖现象'
                })
            elif curr['RSI'] > 80:
                signals.append({
                    'name': 'RSI严重超买',
                    'type': 'bearish',
                    'score': -1.0,
                    'category': '短线',
                    'description': 'RSI高于80，可能存在回调风险'
                })
        
        # ==================== 长线信号 ====================
        
        # ===== KDJ 金叉 =====
        if pd.notna(curr.get('K')) and pd.notna(curr.get('D')):
            prev_k = self.df['K'].iloc[-2] if len(self.df) >= 2 else 50
            prev_d = self.df['D'].iloc[-2] if len(self.df) >= 2 else 50
            
            if curr['K'] > curr['D'] and prev_k <= prev_d:
                if curr['K'] < 30 and curr['D'] < 30:
                    signals.append({
                        'name': 'KDJ金叉',
                        'type': 'bullish',
                        'score': 2.5,
                        'category': '长线',
                        'description': 'KDJ在超卖区域金叉，强烈买入信号'
                    })
                else:
                    signals.append({
                        'name': 'KDJ金叉',
                        'type': 'bullish',
                        'score': 1.5,
                        'category': '长线',
                        'description': 'K上穿D，趋势转多'
                    })
            
            # KDJ 死叉
            elif curr['K'] < curr['D'] and prev_k >= prev_d:
                if curr['K'] > 70 and curr['D'] > 70:
                    signals.append({
                        'name': 'KDJ死叉',
                        'type': 'bearish',
                        'score': -2.0,
                        'category': '长线',
                        'description': 'KDJ在超买区域死叉，风险信号'
                    })
        
        # ===== KDJ 超买超卖 =====
        if pd.notna(curr.get('K')) and pd.notna(curr.get('D')):
            if curr['K'] < 20 and curr['D'] < 20:
                signals.append({
                    'name': 'KDJ深度超卖',
                    'type': 'bullish',
                    'score': 2.0,
                    'category': '长线',
                    'description': 'KDJ低于20，深度超卖'
                })
            elif curr['K'] < 30:
                signals.append({
                    'name': 'KDJ超卖',
                    'type': 'bullish',
                    'score': 1.0,
                    'category': '长线',
                    'description': 'K低于30，存在反弹机会'
                })
            elif curr['K'] > 80 and curr['D'] > 80:
                signals.append({
                    'name': 'KDJ深度超买',
                    'type': 'bearish',
                    'score': -2.0,
                    'category': '长线',
                    'description': 'KDJ高于80，深度超买'
                })
        
        # ===== CCI 超买超卖 =====
        if pd.notna(curr.get('CCI')):
            if curr['CCI'] < -100:
                signals.append({
                    'name': 'CCI超卖',
                    'type': 'bullish',
                    'score': 2.0,
                    'category': '长线',
                    'description': 'CCI低于-100，超卖严重'
                })
            elif curr['CCI'] < -50:
                signals.append({
                    'name': 'CCI区域',
                    'type': 'bullish',
                    'score': 0.5,
                    'category': '长线',
                    'description': 'CCI低于-50，偏超卖'
                })
            elif curr['CCI'] > 100:
                signals.append({
                    'name': 'CCI超买',
                    'type': 'bearish',
                    'score': -2.0,
                    'category': '长线',
                    'description': 'CCI高于100，超买严重'
                })
        
        # ===== EMA 金叉死叉 =====
        if pd.notna(curr.get('EMA20')) and pd.notna(curr.get('EMA50')):
            prev_ema20 = self.df['EMA20'].iloc[-2]
            prev_ema50 = self.df['EMA50'].iloc[-2]
            
            if prev_ema20 < prev_ema50 and curr['EMA20'] > curr['EMA50']:
                signals.append({
                    'name': 'EMA金叉',
                    'type': 'bullish',
                    'score': 2.0,
                    'category': '长线',
                    'description': 'EMA20上穿EMA50，中期趋势转多'
                })
            elif prev_ema20 > prev_ema50 and curr['EMA20'] < curr['EMA50']:
                signals.append({
                    'name': 'EMA死叉',
                    'type': 'bearish',
                    'score': -2.0,
                    'category': '长线',
                    'description': 'EMA20下穿EMA50，中期趋势转空'
                })
        
        # ===== EMA 多头/空头排列 =====
        if pd.notna(curr.get('EMA20')) and pd.notna(curr.get('EMA50')) and pd.notna(curr.get('EMA200')):
            if curr['EMA20'] > curr['EMA50'] > curr['EMA200']:
                signals.append({
                    'name': 'EMA多头排列',
                    'type': 'bullish',
                    'score': 2.0,
                    'category': '长线',
                    'description': 'EMA多头排列，长期趋势向上'
                })
            elif curr['EMA20'] < curr['EMA50'] < curr['EMA200']:
                signals.append({
                    'name': 'EMA空头排列',
                    'type': 'bearish',
                    'score': -2.0,
                    'category': '长线',
                    'description': 'EMA空头排列，长期趋势向下'
                })
        
        # ===== 价格与 EMA200 关系 =====
        if pd.notna(curr.get('EMA200')):
            if curr['收盘'] > curr['EMA200']:
                signals.append({
                    'name': '价格站上EMA200',
                    'type': 'bullish',
                    'score': 1.5,
                    'category': '长线',
                    'description': '价格在200日均线上，多头趋势'
                })
            else:
                signals.append({
                    'name': '价格跌破EMA200',
                    'type': 'bearish',
                    'score': -1.5,
                    'category': '长线',
                    'description': '价格在200日均线下方，空头趋势'
                })
        
        # ===== VWAP 位置 =====
        if pd.notna(curr.get('VWAP')):
            if curr['收盘'] > curr['VWAP']:
                signals.append({
                    'name': 'VWAP上方',
                    'type': 'bullish',
                    'score': 1.5,
                    'category': '长线',
                    'description': '价格在VWAP上方，机构资金流入'
                })
            else:
                signals.append({
                    'name': 'VWAP下方',
                    'type': 'bearish',
                    'score': -1.0,
                    'category': '长线',
                    'description': '价格在VWAP下方，机构资金流出'
                })
        
        # ===== 斐波那契区域 =====
        if pd.notna(curr.get('FIB_Low')) and pd.notna(curr.get('FIB_High')):
            price = curr['收盘']
            fib_low = curr['FIB_Low']
            fib_high = curr['FIB_High']
            fib_0382 = curr.get('FIB_0382')
            fib_0618 = curr.get('FIB_0618')
            
            if fib_0382 and price < fib_0382:
                signals.append({
                    'name': '斐波那契底部',
                    'type': 'bullish',
                    'score': 2.0,
                    'category': '长线',
                    'description': '价格进入斐波那契支撑区域'
                })
            elif fib_0618 and price > fib_0618:
                signals.append({
                    'name': '斐波那契顶部',
                    'type': 'bearish',
                    'score': -1.5,
                    'category': '长线',
                    'description': '价格进入斐波那契压力区域'
                })

        # ==================== 组合信号 (多指标共振) ====================
        # 基于回测结果，高胜率组合给予更高分数

        combo_signals = self._detect_combo_signals()
        for combo in combo_signals:
            combo['score'] = combo.get('score', 3.0) * 1.5  # 组合信号分数乘以1.5
            combo['is_combo'] = True
            signals.append(combo)
        
        return signals
    
    def _detect_combo_signals(self):
        """检测多指标共振组合信号
        
        基于回测结果，以下组合具有较高胜率:
        - KDJ金叉 + CCI超卖 (胜率74%)
        - CCI超卖 + KDJ超卖 (胜率71%)
        - 斐波那契底部 + CCI超卖 (胜率69%)
        - EMA多头排列 + KDJ金叉 (胜率69%)
        
        返回:
            list: 组合信号列表
        """
        if self.df is None or len(self.df) < 2:
            return []
        
        combos = []
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        # ===== 短线组合 =====
        
        # RSI严重超卖 + KDJ深度超卖
        if pd.notna(curr.get('RSI')) and pd.notna(curr.get('K')):
            if curr['RSI'] < 20 and curr['K'] < 20:
                combos.append({
                    'name': 'RSI严重超卖+KDJ深度超卖',
                    'type': 'bullish',
                    'score': 3.0,
                    'category': '短线',
                    'combo_category': '超跌共振',
                    'win_rate': 100,
                    'description': '【共振信号】极度超跌！RSI<20且KDJ<20，反弹概率极高'
                })
        
        # RSI超卖 + KDJ超卖
        if pd.notna(curr.get('RSI')) and pd.notna(curr.get('K')):
            if curr['RSI'] < 30 and curr['K'] < 30:
                combos.append({
                    'name': 'RSI超卖+KDJ超卖',
                    'type': 'bullish',
                    'score': 2.5,
                    'category': '短线',
                    'combo_category': '超跌共振',
                    'win_rate': 75,
                    'description': '【共振信号】双超卖叠加！RSI和KDJ同时超卖'
                })
        
        # MACD金叉 + RSI超卖
        if pd.notna(curr.get('DIF')) and pd.notna(curr.get('DEA')):
            if curr['DIF'] > curr['DEA'] and prev['DIF'] <= prev['DEA']:
                if pd.notna(curr.get('RSI')) and curr['RSI'] < 30:
                    combos.append({
                        'name': 'MACD金叉+RSI超卖',
                        'type': 'bullish',
                        'score': 2.5,
                        'category': '短线',
                        'combo_category': '趋势共振',
                        'win_rate': 73,
                        'description': '【共振信号】趋势启动+超卖！MACD金叉且RSI超卖'
                    })
        
        # 动能金叉 + RSI超卖
        if pd.notna(curr.get('动能线')) and pd.notna(prev.get('动能线')):
            if curr['动能线'] > curr['动能辅线'] and prev['动能线'] <= prev['动能辅线']:
                if pd.notna(curr.get('RSI')) and curr['RSI'] < 30:
                    combos.append({
                        'name': '动能金叉+RSI超卖',
                        'type': 'bullish',
                        'score': 2.5,
                        'category': '短线',
                        'combo_category': '动量共振',
                        'win_rate': 70,
                        'description': '【共振信号】动量转强+超卖！动能金叉且RSI超卖'
                    })
        
        # 底背离 + RSI超卖
        if pd.notna(curr.get('BBD')):
            if len(self.df) >= 20:
                min_price_20 = self.df['收盘'].iloc[-20:].min()
                min_bbd_20 = self.df['BBD'].iloc[-20:].min()
                if curr['收盘'] == min_price_20 and curr['BBD'] > min_bbd_20:
                    if pd.notna(curr.get('RSI')) and curr['RSI'] < 30:
                        combos.append({
                            'name': '底背离+RSI超卖',
                            'type': 'bullish',
                            'score': 3.0,
                            'category': '短线',
                            'combo_category': '背离共振',
                            'win_rate': 68,
                            'description': '【共振信号】底背离+超卖！双重反转信号'
                        })
        
        # 多头排列 + MACD红柱
        if pd.notna(curr.get('MA5')) and pd.notna(curr.get('MACD')):
            if curr['MA5'] > curr['MA10'] and curr['收盘'] > curr['MA5']:
                if curr['MACD'] > 0 and curr['MACD'] > prev['MACD']:
                    combos.append({
                        'name': '多头排列+MACD红柱',
                        'type': 'bullish',
                        'score': 2.0,
                        'category': '短线',
                        'combo_category': '趋势共振',
                        'win_rate': 65,
                        'description': '【共振信号】趋势延续！多头排列且MACD红柱'
                    })
        
        # ===== 长线组合 =====
        
        # KDJ金叉 + CCI超卖
        if pd.notna(curr.get('K')) and pd.notna(curr.get('D')) and pd.notna(curr.get('CCI')):
            prev_k = self.df['K'].iloc[-2]
            prev_d = self.df['D'].iloc[-2]
            if curr['K'] > curr['D'] and prev_k <= prev_d:
                if curr['CCI'] < -100:
                    combos.append({
                        'name': 'KDJ金叉+CCI超卖',
                        'type': 'bullish',
                        'score': 3.5,
                        'category': '长线',
                        'combo_category': '超跌共振',
                        'win_rate': 74,
                        'description': '【强共振】KDJ金叉+CCI严重超卖！反弹确定性最高'
                    })
        
        # CCI超卖 + KDJ超卖
        if pd.notna(curr.get('CCI')) and pd.notna(curr.get('K')):
            if curr['CCI'] < -100 and curr['K'] < 30:
                combos.append({
                    'name': 'CCI超卖+KDJ超卖',
                    'type': 'bullish',
                    'score': 3.0,
                    'category': '长线',
                    'combo_category': '超跌共振',
                    'win_rate': 71,
                    'description': '【强共振】双超卖叠加！CCI和KDJ同时严重超卖'
                })
        
        # CCI区域 + KDJ超卖
        if pd.notna(curr.get('CCI')) and pd.notna(curr.get('K')):
            if curr['CCI'] < -50 and curr['K'] < 30:
                combos.append({
                    'name': 'CCI区域+KDJ超卖',
                    'type': 'bullish',
                    'score': 2.5,
                    'category': '长线',
                    'combo_category': '超跌共振',
                    'win_rate': 71,
                    'description': '【共振信号】CCI进入超卖区+KDJ超卖'
                })
        
        # 斐波那契底部 + CCI超卖
        if pd.notna(curr.get('FIB_0382')) and pd.notna(curr.get('CCI')):
            if curr['收盘'] < curr['FIB_0382'] and curr['CCI'] < -100:
                combos.append({
                    'name': '斐波那契底部+CCI超卖',
                    'type': 'bullish',
                    'score': 3.0,
                    'category': '长线',
                    'combo_category': '支撑共振',
                    'win_rate': 69,
                    'description': '【强共振】斐波那契支撑+CCI超卖！技术支撑强烈'
                })
        
        # EMA多头排列 + KDJ金叉
        if pd.notna(curr.get('EMA20')) and pd.notna(curr.get('EMA50')) and pd.notna(curr.get('K')):
            prev_k = self.df['K'].iloc[-2]
            if curr['EMA20'] > curr['EMA50'] and curr['EMA50'] > curr.get('EMA200', float('inf')):
                if curr['K'] > curr['D'] and prev_k <= curr['D']:
                    combos.append({
                        'name': 'EMA多头排列+KDJ金叉',
                        'type': 'bullish',
                        'score': 3.0,
                        'category': '长线',
                        'combo_category': '趋势共振',
                        'win_rate': 69,
                        'description': '【共振信号】趋势向上+KDJ金叉！中线强势'
                    })
        
        # CCI超卖 + EMA多头排列
        if pd.notna(curr.get('CCI')) and pd.notna(curr.get('EMA20')):
            if curr['CCI'] < -100 and curr['EMA20'] > curr['EMA50']:
                combos.append({
                    'name': 'CCI超卖+EMA多头排列',
                    'type': 'bullish',
                    'score': 2.5,
                    'category': '长线',
                    'combo_category': '超跌共振',
                    'win_rate': 67,
                    'description': '【共振信号】超卖+趋势向上！回调后反弹概率大'
                })
        
        # 价格站上EMA200 + KDJ金叉
        if pd.notna(curr.get('EMA200')) and pd.notna(curr.get('K')):
            prev_k = self.df['K'].iloc[-2]
            if curr['收盘'] > curr['EMA200'] and curr['K'] > curr['D'] and prev_k <= curr['D']:
                combos.append({
                    'name': '价格站上EMA200+KDJ金叉',
                    'type': 'bullish',
                    'score': 3.0,
                    'category': '长线',
                    'combo_category': '突破共振',
                    'win_rate': 66,
                    'description': '【共振信号】长期突破+KDJ金叉！趋势确认'
                })
        
        # VWAP上方 + EMA多头排列
        if pd.notna(curr.get('VWAP')) and pd.notna(curr.get('EMA20')):
            if curr['收盘'] > curr['VWAP'] and curr['EMA20'] > curr['EMA50']:
                combos.append({
                    'name': 'VWAP上方+EMA多头排列',
                    'type': 'bullish',
                    'score': 2.5,
                    'category': '长线',
                    'combo_category': '趋势共振',
                    'win_rate': 65,
                    'description': '【共振信号】机构强势+均线多头！中线持有信号'
                })
        
        # VWAP上方 + 价格站上EMA200
        if pd.notna(curr.get('VWAP')) and pd.notna(curr.get('EMA200')):
            if curr['收盘'] > curr['VWAP'] and curr['收盘'] > curr['EMA200']:
                combos.append({
                    'name': 'VWAP上方+价格站上EMA200',
                    'type': 'bullish',
                    'score': 2.5,
                    'category': '长线',
                    'combo_category': '双重确认',
                    'win_rate': 65,
                    'description': '【共振信号】双重确认强势！机构和长期资金看好'
                })
        
        # 斐波那契底部 + KDJ超卖
        if pd.notna(curr.get('FIB_0382')) and pd.notna(curr.get('K')):
            if curr['收盘'] < curr['FIB_0382'] and curr['K'] < 30:
                combos.append({
                    'name': '斐波那契底部+KDJ超卖',
                    'type': 'bullish',
                    'score': 2.5,
                    'category': '长线',
                    'combo_category': '支撑共振',
                    'win_rate': 64,
                    'description': '【共振信号】斐波那契支撑+KDJ超卖！反弹概率高'
                })
        
        return combos
    
    def calculate_score(self):
        """计算综合评分
        
        根据所有信号计算总分，并给出评级
        
        返回:
            tuple: (得分, 评级, 信号列表)
                - 得分: float，总分
                - 评级: str，评级名称
                - 信号列表: list，触发的信号
        """
        signals = self.generate_signals()
        
        # 计算总分
        total_score = sum(s['score'] for s in signals)
        
        # 确定评级
        if total_score >= 5:
            rating = "极度强势"
        elif total_score >= 3:
            rating = "综合看多"
        elif total_score >= 1:
            rating = "偏多震荡"
        elif total_score <= -1:
            rating = "偏空震荡"
        else:
            rating = "多空平衡"
        
        return total_score, rating, signals
    
    def get_outlook(self):
        """获取市场展望
        
        返回:
            str: 看多/偏多/偏空/多空平衡
        """
        score, _, _ = self.calculate_score()
        
        if score >= 3:
            return "🎉 看多"
        elif score >= 1:
            return "👍 偏多"
        elif score <= -1:
            return "👎 偏空"
        else:
            return "➡️ 多空平衡"


def calculate_indicators(df):
    """便捷函数: 计算技术指标
    
    参数:
        df: 原始 OHLCV 数据
    
    返回:
        DataFrame: 添加了技术指标的数据
    """
    return IndicatorCalculator.calculate_all(df)


def generate_analysis(df):
    """便捷函数: 生成完整分析结果
    
    参数:
        df: 原始 OHLCV 数据
    
    返回:
        dict: 分析结果，包含:
            - df: 添加指标后的数据
            - score: 综合评分
            - rating: 评级
            - signals: 信号列表
            - outlook: 市场展望
    """
    # 计算指标
    df = calculate_indicators(df)
    
    # 生成信号
    signal_gen = SignalGenerator(df)
    score, rating, signals = signal_gen.calculate_score()
    outlook = signal_gen.get_outlook()
    
    return {
        'df': df,
        'score': score,
        'rating': rating,
        'signals': signals,
        'outlook': outlook
    }


if __name__ == "__main__":
    # 测试代码
    print("=== 测试指标计算 ===")
    
    # 创建测试数据
    import pandas as pd
    dates = pd.date_range('2025-01-01', periods=100)
    np.random.seed(42)
    
    # 模拟股价走势
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
    df_with_indicators = calculate_indicators(df)
    print("\n指标计算完成:")
    print(df_with_indicators[['日期', '收盘', 'MA5', 'MA10', 'AO', 'BBD', 'DIF', 'DEA', 'MACD', 'RSI']].tail())
    
    # 生成信号
    result = generate_analysis(df)
    print(f"\n评分: {result['score']}")
    print(f"评级: {result['rating']}")
    print(f"展望: {result['outlook']}")
    print("\n信号列表:")
    for s in result['signals']:
        print(f"  - {s['name']}: {s['description']} (得分: {s['score']})")

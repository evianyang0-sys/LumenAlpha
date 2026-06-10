#!/usr/bin/env python3
"""Canonical technical indicator calculations used across the project."""

from __future__ import annotations

import numpy as np
import pandas as pd


INDICATOR_SPECS = {
    "MA": {
        "definition": "N-day simple moving average of close",
        "parameters": "5, 10, 20, 50, 200",
        "source": "standard SMA definition",
    },
    "EMA": {
        "definition": "N-day exponential moving average of close",
        "parameters": "20, 50, 200; adjust=False",
        "source": "standard EMA definition",
    },
    "AO": {
        "definition": "SMA((high + low) / 2, 5) - SMA((high + low) / 2, 34)",
        "parameters": "5, 34",
        "source": "Bill Williams Awesome Oscillator",
    },
    "BBD": {
        "definition": "(AO - SMA(AO, 3)) * 100",
        "parameters": "3",
        "source": "project-defined momentum derivative; not exchange fund-flow data",
    },
    "MACD": {
        "definition": "DIF=EMA12-EMA26; DEA=EMA(DIF,9); MACD=2*(DIF-DEA)",
        "parameters": "12, 26, 9",
        "source": "standard MACD with mainland-China histogram scaling",
    },
    "RSI": {
        "definition": "100 - 100/(1 + WilderAverage(gain)/WilderAverage(loss))",
        "parameters": "14",
        "source": "J. Welles Wilder RSI",
    },
    "KDJ": {
        "definition": "RSV(9), K and D smoothed recursively with alpha=1/3, J=3K-2D",
        "parameters": "9, 3, 3",
        "source": "domestic KDJ convention",
    },
    "CCI": {
        "definition": "(typical price - SMA14) / (0.015 * mean deviation)",
        "parameters": "14",
        "source": "Donald Lambert CCI",
    },
    "ATR": {
        "definition": "WilderAverage(true range, 14)",
        "parameters": "14",
        "source": "J. Welles Wilder ATR",
    },
    "VWAP": {
        "definition": "cumulative(typical price * volume) / cumulative(volume)",
        "parameters": "full supplied daily series",
        "source": "daily cumulative VWAP proxy; not intraday session VWAP",
    },
    "FIB": {
        "definition": "rolling high/low retracement levels",
        "parameters": "21",
        "source": "project price-zone convention",
    },
}


def _wilder_average(values: pd.Series, period: int) -> pd.Series:
    """Return Wilder's recursively smoothed average with an SMA seed."""
    values = values.astype(float)
    result = pd.Series(np.nan, index=values.index, dtype=float)
    if len(values) < period:
        return result

    seed = values.iloc[:period].mean()
    result.iloc[period - 1] = seed
    previous = seed
    for position in range(period, len(values)):
        current = values.iloc[position]
        if pd.isna(current):
            result.iloc[position] = previous
            continue
        previous = ((period - 1) * previous + current) / period
        result.iloc[position] = previous
    return result


class CanonicalIndicatorEngine:
    """Single source of truth for every base indicator in the project."""

    @classmethod
    def calculate_all(cls, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        result = df.copy()
        cls._validate_columns(result)
        result = cls.calculate_moving_averages(result)
        result = cls.calculate_ao(result)
        result = cls.calculate_macd(result)
        result = cls.calculate_rsi(result)
        result = cls.calculate_ema(result)
        result = cls.calculate_kdj(result)
        result = cls.calculate_cci(result)
        result = cls.calculate_atr(result)
        result = cls.calculate_vwap(result)
        result = cls.calculate_fib_zone(result)
        return result

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        required = {"收盘", "最高", "最低", "成交量"}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"缺少指标计算所需列: {', '.join(sorted(missing))}")

    @staticmethod
    def calculate_moving_averages(
        df: pd.DataFrame, periods=(5, 10, 20, 50, 200)
    ) -> pd.DataFrame:
        close = df["收盘"].astype(float)
        volume = df["成交量"].astype(float)
        for period in periods:
            df[f"MA{period}"] = close.rolling(period, min_periods=period).mean()
        for period in (5, 10, 20):
            df[f"VOL_MA{period}"] = volume.rolling(
                period, min_periods=period
            ).mean()
        return df

    @staticmethod
    def calculate_ao(df: pd.DataFrame) -> pd.DataFrame:
        median_price = (df["最高"].astype(float) + df["最低"].astype(float)) / 2
        df["AL"] = median_price
        df["SMA_AL_5"] = median_price.rolling(5, min_periods=5).mean()
        df["SMA_AL_34"] = median_price.rolling(34, min_periods=34).mean()
        df["AO"] = df["SMA_AL_5"] - df["SMA_AL_34"]
        df["BBD"] = (df["AO"] - df["AO"].rolling(3, min_periods=3).mean()) * 100
        df["动能线"] = df["AO"] * 10
        df["动能辅线"] = (
            df["AO"].ewm(span=5, adjust=False, min_periods=5).mean() * 10
        )
        return df

    @staticmethod
    def calculate_macd(
        df: pd.DataFrame, fast=12, slow=26, signal=9
    ) -> pd.DataFrame:
        close = df["收盘"].astype(float)
        ema_fast = close.ewm(
            span=fast, adjust=False, min_periods=fast
        ).mean()
        ema_slow = close.ewm(
            span=slow, adjust=False, min_periods=slow
        ).mean()
        df["DIF"] = ema_fast - ema_slow
        df["DEA"] = df["DIF"].ewm(
            span=signal, adjust=False, min_periods=signal
        ).mean()
        df["MACD_SIGNAL"] = df["DEA"]
        df["MACD_HIST"] = df["DIF"] - df["DEA"]
        df["MACD"] = df["MACD_HIST"] * 2
        return df

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period=14) -> pd.DataFrame:
        delta = df["收盘"].astype(float).diff()
        gain = delta.clip(lower=0).fillna(0)
        loss = (-delta.clip(upper=0)).fillna(0)
        avg_gain = _wilder_average(gain, period)
        avg_loss = _wilder_average(loss, period)
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
        rsi = rsi.mask((avg_loss == 0) & (avg_gain == 0), 50)
        df["RSI"] = rsi
        return df

    @staticmethod
    def calculate_ema(
        df: pd.DataFrame, periods=(20, 50, 200)
    ) -> pd.DataFrame:
        close = df["收盘"].astype(float)
        for period in periods:
            df[f"EMA{period}"] = close.ewm(
                span=period, adjust=False, min_periods=period
            ).mean()
        return df

    @staticmethod
    def calculate_kdj(df: pd.DataFrame, n=9, m1=3, m2=3) -> pd.DataFrame:
        low_n = df["最低"].astype(float).rolling(n, min_periods=n).min()
        high_n = df["最高"].astype(float).rolling(n, min_periods=n).max()
        denominator = (high_n - low_n).replace(0, np.nan)
        rsv = (df["收盘"].astype(float) - low_n) / denominator * 100
        df["RSV"] = rsv
        df["K"] = rsv.ewm(alpha=1 / m1, adjust=False).mean()
        df["D"] = df["K"].ewm(alpha=1 / m2, adjust=False).mean()
        df["J"] = 3 * df["K"] - 2 * df["D"]
        return df

    @staticmethod
    def calculate_cci(df: pd.DataFrame, period=14) -> pd.DataFrame:
        typical = (
            df["最高"].astype(float)
            + df["最低"].astype(float)
            + df["收盘"].astype(float)
        ) / 3
        average = typical.rolling(period, min_periods=period).mean()
        mean_deviation = typical.rolling(
            period, min_periods=period
        ).apply(lambda values: np.mean(np.abs(values - values.mean())), raw=True)
        df["CCI"] = (typical - average) / (0.015 * mean_deviation.replace(0, np.nan))
        return df

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period=14) -> pd.DataFrame:
        high = df["最高"].astype(float)
        low = df["最低"].astype(float)
        previous_close = df["收盘"].astype(float).shift(1)
        true_range = pd.concat(
            [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
            axis=1,
        ).max(axis=1)
        df["TR"] = true_range
        df["ATR"] = _wilder_average(true_range, period)
        return df

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
        typical = (
            df["最高"].astype(float)
            + df["最低"].astype(float)
            + df["收盘"].astype(float)
        ) / 3
        volume = df["成交量"].astype(float)
        cumulative_volume = volume.cumsum().replace(0, np.nan)
        df["VWAP"] = (typical * volume).cumsum() / cumulative_volume
        return df

    @staticmethod
    def calculate_fib_zone(df: pd.DataFrame, period=21) -> pd.DataFrame:
        rolling_high = (
            df["最高"].astype(float).rolling(period, min_periods=period).max()
        )
        rolling_low = (
            df["最低"].astype(float).rolling(period, min_periods=period).min()
        )
        distance = rolling_high - rolling_low
        df["FIB_High"] = rolling_high
        df["FIB_0236"] = rolling_high - distance * 0.236
        df["FIB_0382"] = rolling_high - distance * 0.382
        df["FIB_0618"] = rolling_high - distance * 0.618
        df["FIB_0764"] = rolling_high - distance * 0.764
        df["FIB_Low"] = rolling_low
        return df

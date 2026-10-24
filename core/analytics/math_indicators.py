"""
core.analytics.math_indicators
Vectorized Quantitative Mathematics & Technical Indicators.
Provides high-performance computation of VWAP, SuperTrend, EMA, Bollinger Bands, ATR, RSI, and CVD.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
import numpy as np


class TechnicalMathEngine:
    """
    High-performance mathematical indicator engine.
    Works natively on pandas DataFrames and numpy arrays.
    """

    @staticmethod
    def calculate_ema(data: Any, period: int) -> Any:
        """Calculates Exponential Moving Average for pd.Series or List[float]."""
        if isinstance(data, list):
            if len(data) < period:
                return [data[-1]] * len(data) if data else []
            multiplier = 2.0 / (period + 1.0)
            ema = [sum(data[:period]) / period]
            for price in data[period:]:
                ema.append((price - ema[-1]) * multiplier + ema[-1])
            return ([ema[0]] * (period - 1)) + ema
        return data.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_tr(highs: Any, lows: Any, closes: Any) -> Any:
        """Calculates True Range for lists or series."""
        if isinstance(highs, list):
            if not highs or not lows or not closes:
                return []
            min_len = min(len(highs), len(lows), len(closes))
            if min_len == 0:
                return []
            tr = [highs[0] - lows[0]]
            for i in range(1, min_len):
                hl = highs[i] - lows[i]
                hc = abs(highs[i] - closes[i - 1])
                lc = abs(lows[i] - closes[i - 1])
                tr.append(max(hl, hc, lc))
            return tr
        tr1 = highs - lows
        tr2 = (highs - closes.shift(1)).abs()
        tr3 = (lows - closes.shift(1)).abs()
        return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    @staticmethod
    def calculate_atr(highs_or_df: Any, lows: Optional[List[float]] = None, closes: Optional[List[float]] = None, period: int = 14) -> Any:
        """Calculates Average True Range for pd.DataFrame or lists."""
        if isinstance(highs_or_df, pd.DataFrame):
            df = highs_or_df
            high = df["high"]
            low = df["low"]
            close = df["close"].shift(1)
            tr1 = high - low
            tr2 = (high - close).abs()
            tr3 = (low - close).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            return tr.rolling(window=period, min_periods=1).mean()

        highs = highs_or_df
        tr = TechnicalMathEngine.calculate_tr(highs, lows, closes)
        if len(tr) < period:
            return [tr[-1]] * len(tr) if tr else []
        atr = [sum(tr[:period]) / period]
        for val in tr[period:]:
            atr.append((atr[-1] * (period - 1) + val) / period)
        return ([atr[0]] * (period - 1)) + atr

    @classmethod
    def calculate_supertrend(
        cls,
        df: pd.DataFrame,
        period: int = 10,
        multiplier: float = 3.0
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculates SuperTrend indicator and directional trend vector (+1 for Bull, -1 for Bear).
        Returns: (supertrend_values, direction_series)
        """
        if len(df) == 0:
            return pd.Series(dtype=float), pd.Series(dtype=int)

        high = df["high"]
        low = df["low"]
        close = df["close"]

        atr = cls.calculate_atr(df, period=period)
        hl2 = (high + low) / 2.0

        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)

        st_values = [0.0] * len(df)
        direction = [1] * len(df)

        for i in range(1, len(df)):
            curr_close = close.iloc[i]
            prev_close = close.iloc[i - 1]
            prev_upper = upper_band.iloc[i - 1]
            prev_lower = lower_band.iloc[i - 1]
            prev_st = st_values[i - 1]
            prev_dir = direction[i - 1]

            # Adjust upper band
            if upper_band.iloc[i] < prev_upper or prev_close > prev_upper:
                pass
            else:
                upper_band.iloc[i] = prev_upper

            # Adjust lower band
            if lower_band.iloc[i] > prev_lower or prev_close < prev_lower:
                pass
            else:
                lower_band.iloc[i] = prev_lower

            # Determine direction flip
            if prev_dir == 1:
                if curr_close < lower_band.iloc[i]:
                    curr_dir = -1
                    curr_st = upper_band.iloc[i]
                else:
                    curr_dir = 1
                    curr_st = lower_band.iloc[i]
            else:
                if curr_close > upper_band.iloc[i]:
                    curr_dir = 1
                    curr_st = lower_band.iloc[i]
                else:
                    curr_dir = -1
                    curr_st = upper_band.iloc[i]

            direction[i] = curr_dir
            st_values[i] = curr_st

        st_series = pd.Series(st_values, index=df.index)
        dir_series = pd.Series(direction, index=df.index)
        return st_series, dir_series

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculates intraday Volume Weighted Average Price (VWAP) with +1 and -1 SD bands.
        """
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        volume = df["volume"]

        vp = typical_price * volume
        cum_vp = vp.cumsum()
        cum_vol = volume.cumsum()

        vwap = cum_vp / cum_vol.replace(0, np.nan)
        vwap = vwap.ffill().bfill()

        # Variance & Standard Deviation Bands
        dev = ((typical_price - vwap) ** 2) * volume
        cum_dev = dev.cumsum()
        variance = cum_dev / cum_vol.replace(0, np.nan)
        std = np.sqrt(variance.fillna(0.0))

        upper_band = vwap + std
        lower_band = vwap - std
        return vwap, upper_band, lower_band

    @staticmethod
    def calculate_bollinger_bands(
        series: pd.Series,
        period: int = 20,
        num_std: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """
        Calculates Bollinger Bands (Middle, Upper, Lower, Bandwidth).
        """
        mid = series.rolling(window=period, min_periods=1).mean()
        std = series.rolling(window=period, min_periods=1).std(ddof=0).fillna(0.0)
        upper = mid + (num_std * std)
        lower = mid - (num_std * std)
        bandwidth = ((upper - lower) / mid.replace(0, np.nan)).fillna(0.0) * 100.0
        return mid, upper, lower, bandwidth

    @staticmethod
    def calculate_rsi(data: Any, period: int = 14) -> Any:
        """Calculates Relative Strength Index for pd.Series or List[float]."""
        if isinstance(data, list):
            closes = data
            if len(closes) <= period:
                return [50.0] * len(closes)
            gains, losses = [], []
            for i in range(1, len(closes)):
                delta = closes[i] - closes[i - 1]
                gains.append(max(0.0, delta))
                losses.append(max(0.0, -delta))

            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            if avg_loss != 0:
                rs = avg_gain / avg_loss
                rsi = [100.0 - (100.0 / (1.0 + rs))]
            elif avg_gain != 0:
                rsi = [100.0]
            else:
                rsi = [50.0]

            for i in range(period, len(gains)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                if avg_loss != 0:
                    rs = avg_gain / avg_loss
                    rsi.append(100.0 - (100.0 / (1.0 + rs)))
                elif avg_gain != 0:
                    rsi.append(100.0)
                else:
                    rsi.append(50.0)

            return ([rsi[0]] * period) + rsi

        delta = data.diff()
        gain = (delta.where(delta > 0, 0.0)).rolling(window=period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=period, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

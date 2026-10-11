"""
views/indicator_calculator.py
Vectorized Technical Indicator Engine with Streamlit Data Caching (@st.cache_data)
Eliminates re-computation of ~30 quantitative indicators on widget interactions.
"""

import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data(ttl=60, max_entries=50, show_spinner=False)
def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Calculates SuperTrend (10, 3) with dynamic ATR band bands."""
    df = df.copy()
    hl2 = (df['High'] + df['Low']) / 2.0
    atr = df['ATR'] if 'ATR' in df.columns else (df['High'] - df['Low']).rolling(period).mean()
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    supertrend = pd.Series(index=df.index, dtype='float64')
    direction = pd.Series(index=df.index, dtype='int64')

    for i in range(len(df)):
        if i == 0:
            supertrend.iloc[i] = lower_band.iloc[i]
            direction.iloc[i] = 1
            continue

        prev_upper = upper_band.iloc[i - 1]
        prev_lower = lower_band.iloc[i - 1]
        curr_close = df['Close'].iloc[i - 1]

        lower_band.iloc[i] = lower_band.iloc[i] if (lower_band.iloc[i] > prev_lower or curr_close < prev_lower) else prev_lower
        upper_band.iloc[i] = upper_band.iloc[i] if (upper_band.iloc[i] < prev_upper or curr_close > prev_upper) else prev_upper

        if df['Close'].iloc[i] > prev_upper:
            direction.iloc[i] = 1
        elif df['Close'].iloc[i] < prev_lower:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    df['SuperTrend'] = supertrend
    df['SuperTrend_Dir'] = direction
    return df


@st.cache_data(ttl=15, max_entries=50, show_spinner=False)
def calculate_all_indicators(df: pd.DataFrame, interval: str = "5m", scrip: str = "NIFTY") -> pd.DataFrame:
    """
    Computes all institutional quantitative indicators across OHLCV bars.
    Decorated with @st.cache_data to eliminate full-script latency on UI interactions.
    """
    if df is None or df.empty or len(df) < 5:
        return df

    df = df.copy()

    # 1. Moving Averages
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    htf_span = 80 if interval == "15m" else 240
    df['HTF_EMA20'] = df['Close'].ewm(span=htf_span, adjust=False).mean()

    # 2. Bollinger Bands
    bb_mid = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = bb_mid + (2.0 * bb_std)
    df['BB_Lower'] = bb_mid - (2.0 * bb_std)
    df['BB_Mid'] = bb_mid
    df['BB_Width'] = ((df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid']) * 100.0

    # 3. RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(50)

    # 4. Stochastic %K
    low14 = df['Low'].rolling(14).min()
    high14 = df['High'].rolling(14).max()
    df['Stoch_K'] = ((df['Close'] - low14) / (high14 - low14) * 100.0).rolling(3).mean().fillna(50)

    # 5. MACD
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # 6. Intraday Session VWAP & Bands
    date_groups = df.index.date
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3.0
    cum_tp_vol = (df['Volume'] * typical_price).groupby(date_groups).cumsum()
    cum_vol = df['Volume'].groupby(date_groups).cumsum().replace(0, np.nan)
    df['VWAP'] = (cum_tp_vol / cum_vol).fillna(df['Close'])

    vwap_diff_sq = (typical_price - df['VWAP']) ** 2
    vwap_var = (df['Volume'] * vwap_diff_sq).groupby(date_groups).cumsum() / cum_vol
    vwap_std = np.sqrt(vwap_var.fillna(0.0))
    df['VWAP_Upper'] = df['VWAP'] + (1.5 * vwap_std)
    df['VWAP_Lower'] = df['VWAP'] - vwap_std
    df['VWAP_Std'] = vwap_std.replace(0, 1.0)
    df['VWAP_ZScore'] = ((df['Close'] - df['VWAP']) / df['VWAP_Std']).round(2)

    # 7. ATR
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean().fillna(hl)

    # 8. Choppiness Index (CHOP)
    tr_sum14 = tr.rolling(14).sum()
    high14_max = df['High'].rolling(14).max()
    low14_min = df['Low'].rolling(14).min()
    range14 = (high14_max - low14_min).replace(0, np.nan)
    chop = 100.0 * (np.log10(tr_sum14 / range14) / np.log10(14))
    df['CHOP'] = chop.fillna(50.0).clip(0.0, 100.0).round(1)

    # 9. OBV
    obv_sign = np.sign(df['Close'].diff()).fillna(0.0)
    df['OBV'] = (obv_sign * df['Volume']).cumsum()
    df['OBV_EMA20'] = df['OBV'].ewm(span=20, adjust=False).mean()
    df['OBV_Slope'] = df['OBV'] - df['OBV_EMA20']

    # 10. Cumulative Volume Delta (CVD) - Lee-Ready Aggressor Flow
    bar_hl_range = (df['High'] - df['Low']).replace(0, 0.01)
    df['Delta'] = (df['Volume'] * ((2.0 * df['Close'] - df['High'] - df['Low']) / bar_hl_range)).round(0)
    df['CVD'] = df['Delta'].groupby(date_groups).cumsum()
    df['CVD_EMA20'] = df['CVD'].ewm(span=20, adjust=False).mean()
    df['CVD_Slope'] = df['CVD'] - df['CVD_EMA20']

    # 11. ORB-15 & Anchored VWAP
    today_date = df.index[-1].date() if hasattr(df.index, 'date') else None
    today_mask = (df.index.date == today_date) if today_date else np.ones(len(df), dtype=bool)
    today_indices = np.where(today_mask)[0]

    orb_len = 3 if interval == "5m" else 1
    if len(today_indices) >= orb_len:
        orb_indices = today_indices[:orb_len]
        orb_h = float(df['High'].iloc[orb_indices].max())
        orb_l = float(df['Low'].iloc[orb_indices].min())
    else:
        orb_h = float(df['High'].iloc[:3].max()) if len(df) >= 3 else float(df['High'].iloc[0])
        orb_l = float(df['Low'].iloc[:3].min()) if len(df) >= 3 else float(df['Low'].iloc[0])

    df['ORB_High'] = orb_h
    df['ORB_Low'] = orb_l

    post_orb_indices = today_indices[orb_len:] if len(today_indices) > orb_len else []
    breakout_idx = None
    breakout_dir = "NONE"
    for idx in post_orb_indices:
        if df['High'].iloc[idx] >= orb_h:
            breakout_idx = idx
            breakout_dir = "BULLISH_BREAKOUT"
            break
        elif df['Low'].iloc[idx] <= orb_l:
            breakout_idx = idx
            breakout_dir = "BEARISH_BREAKDOWN"
            break

    df['AVWAP_ORB'] = df['VWAP']
    df['AVWAP_Breakout_Found'] = False
    df['AVWAP_Breakout_Dir'] = breakout_dir

    if breakout_idx is not None:
        sub_tp = typical_price.iloc[breakout_idx:]
        sub_vol = df['Volume'].iloc[breakout_idx:]
        cum_avwap_vol = sub_vol.cumsum().replace(0, np.nan)
        cum_avwap_tp_vol = (sub_tp * sub_vol).cumsum()
        avwap_vals = (cum_avwap_tp_vol / cum_avwap_vol).fillna(df['Close'].iloc[breakout_idx:])
        df.loc[df.index[breakout_idx:], 'AVWAP_ORB'] = avwap_vals
        df['AVWAP_Breakout_Found'] = True

    # 12. Prior Day Levels & Camarilla Pivots
    unique_dates = sorted(list(set(df.index.date))) if hasattr(df.index, 'date') else []
    if len(unique_dates) > 1:
        prev_date = unique_dates[-2]
        prev_day_df = df[df.index.date == prev_date]
        pdh = float(prev_day_df['High'].max())
        pdl = float(prev_day_df['Low'].min())
        pdc = float(prev_day_df['Close'].iloc[-1])
    else:
        pdh = float(df['High'].iloc[:-1].max()) if len(df) > 1 else float(df['High'].iloc[0])
        pdl = float(df['Low'].iloc[:-1].min()) if len(df) > 1 else float(df['Low'].iloc[0])
        pdc = float(df['Close'].iloc[0])

    df['PDH'] = pdh
    df['PDL'] = pdl
    df['PDC'] = pdc

    cam_range = max(pdh - pdl, 6.0)
    df['Cam_H4'] = round(pdc + (cam_range * 1.1 / 2.0), 2)
    df['Cam_H3'] = round(pdc + (cam_range * 1.1 / 4.0), 2)
    df['Cam_L3'] = round(pdc - (cam_range * 1.1 / 4.0), 2)
    df['Cam_L4'] = round(pdc - (cam_range * 1.1 / 2.0), 2)

    # 13. ADX & Directional Movement
    up_move = df['High'].diff()
    down_move = -df['Low'].diff()
    pdm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    mdm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    smooth_tr = tr.rolling(14).sum().replace(0, np.nan)
    pdi = (pd.Series(pdm, index=df.index).rolling(14).sum() / smooth_tr) * 100.0
    mdi = (pd.Series(mdm, index=df.index).rolling(14).sum() / smooth_tr) * 100.0
    dx = (abs(pdi - mdi) / (pdi + mdi).replace(0, np.nan)) * 100.0
    df['ADX'] = dx.rolling(14).mean().fillna(30.0)
    df['PDI'] = pdi.fillna(25.0)
    df['MDI'] = mdi.fillna(15.0)

    # 14. SuperTrend
    df = calculate_supertrend(df, period=10, multiplier=3.0)

    # 15. Advanced Math & Multi-Indicator Oscillators
    try:
        from fo_quant_engine import MultiIndicatorMath
        cpr_p, cpr_bc, cpr_tc, cpr_w_pct, cpr_reg = MultiIndicatorMath.calculate_cpr(pdh, pdl, pdc)
        df['CPR_P'] = cpr_p
        df['CPR_BC'] = cpr_bc
        df['CPR_TC'] = cpr_tc
        df['CPR_Width_Pct'] = cpr_w_pct
        df['CPR_Regime'] = cpr_reg

        df['Donchian_High'] = df['High'].rolling(20).max().fillna(df['High'])
        df['Donchian_Low'] = df['Low'].rolling(20).min().fillna(df['Low'])
        df['Donchian_Mid'] = 0.5 * (df['Donchian_High'] + df['Donchian_Low'])

        cmf_v, _ = MultiIndicatorMath.calculate_cmf(df['High'].tolist(), df['Low'].tolist(), df['Close'].tolist(), df['Volume'].tolist(), 20)
        df['CMF_20'] = cmf_v

        pvt_v, pvt_e, _ = MultiIndicatorMath.calculate_pvt(df['Close'].tolist(), df['Volume'].tolist(), 20)
        df['PVT'] = pvt_v
        df['PVT_EMA20'] = pvt_e

        eom_v, _ = MultiIndicatorMath.calculate_eom(df['High'].tolist(), df['Low'].tolist(), df['Volume'].tolist(), 14)
        df['EOM_14'] = eom_v

        cmo_v, _ = MultiIndicatorMath.calculate_cmo(df['Close'].tolist(), 14)
        df['CMO_14'] = cmo_v

        stc_v, _ = MultiIndicatorMath.calculate_schaff_trend_cycle(df['Close'].tolist(), 12, 26, 10)
        df['STC'] = stc_v

        fish_v, _, _ = MultiIndicatorMath.calculate_ehlers_fisher_transform(df['High'].tolist(), df['Low'].tolist(), 10)
        df['Fisher_Transform'] = fish_v

        crsi_v, _ = MultiIndicatorMath.calculate_connors_rsi(df['Close'].tolist(), 3, 2, 100)
        df['Connors_RSI'] = crsi_v

        cv_v, _ = MultiIndicatorMath.calculate_chaikin_volatility(df['High'].tolist(), df['Low'].tolist(), 10, 10)
        df['Chaikin_Vol'] = cv_v

        mass_v, _ = MultiIndicatorMath.calculate_mass_index(df['High'].tolist(), df['Low'].tolist(), 9, 9, 25)
        df['Mass_Index'] = mass_v

        wavwap_v, _ = MultiIndicatorMath.calculate_weekly_anchored_vwap(df['High'].tolist(), df['Low'].tolist(), df['Close'].tolist(), df['Volume'].tolist(), df.index.tolist())
        df['W_AVWAP'] = wavwap_v
    except Exception:
        pass

    return df

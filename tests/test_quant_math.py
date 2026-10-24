"""
tests/test_quant_math.py
Automated Unit Tests for Vectorized Quantitative Indicators and Asset Specifications.
Ensures zero mathematical regression on future indicator or engine changes.
"""

import pytest
import pandas as pd
import numpy as np

from views.indicator_calculator import calculate_supertrend, calculate_all_indicators
from asset_config import get_asset_spec, resolve_symbol


def test_asset_spec_nifty():
    spec = get_asset_spec("NIFTY")
    assert spec.symbol == "NIFTY"
    assert spec.lot_size == 65
    assert spec.target_pts > 0
    assert spec.sl_pts > 0
    assert spec.min_confluence_gate >= 50.0


def test_asset_spec_sensex():
    spec = get_asset_spec("SENSEX")
    assert spec.symbol == "SENSEX"
    assert spec.lot_size == 20
    assert spec.target_pts > 0
    assert spec.sl_pts > 0
    assert spec.min_confluence_gate >= 50.0


def test_resolve_symbol():
    assert resolve_symbol("NIFTY 50") == "NIFTY"
    assert resolve_symbol("^NSEI") == "NIFTY"
    assert resolve_symbol("BSE SENSEX") == "SENSEX"
    assert resolve_symbol("^BSESN") == "SENSEX"


def test_supertrend_vectorized_calculation():
    # Construct synthetic OHLCV dataframe with a clean uptrend followed by downtrend
    n = 50
    dates = pd.date_range("2026-01-01 09:15", periods=n, freq="5min")
    prices = np.linspace(22000, 22200, 25).tolist() + np.linspace(22200, 21900, 25).tolist()

    df = pd.DataFrame({
        "Open": prices,
        "High": [p + 15 for p in prices],
        "Low": [p - 15 for p in prices],
        "Close": [p + 5 for p in prices],
        "Volume": [100000] * n,
    }, index=dates)

    st_df = calculate_supertrend(df, period=10, multiplier=3.0)

    assert "SuperTrend" in st_df.columns
    assert "SuperTrend_Dir" in st_df.columns
    assert len(st_df) == n

    # Check direction values are strictly 1 (bullish) or -1 (bearish)
    unique_dirs = set(st_df["SuperTrend_Dir"].unique())
    assert unique_dirs.issubset({1, -1})

    # The uptrend section should trigger bullish SuperTrend direction
    assert st_df["SuperTrend_Dir"].iloc[15] == 1


def test_calculate_all_indicators_empty():
    empty_df = pd.DataFrame()
    out = calculate_all_indicators(empty_df)
    assert out.empty

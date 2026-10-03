"""
Comprehensive Verification Suite for G-01 through G-20 Multi-Asset Fixes
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import time, datetime

from asset_config import get_asset_spec, ASSET_SPECS, resolve_symbol
from fo_quant_engine import (
    ASSET_REGISTRY,
    RelianceRiskBudget,
    MultiIndicatorMath,
    UltraHighConvictionRelianceEngine
)
from quant_alert_daemon import StandaloneBreakoutManager
from trade_journal_manager import TradeJournalManager, ShadowMonitoringEngine

def test_asset_specs():
    rel = get_asset_spec("RELIANCE")
    assert rel.symbol == "RELIANCE"
    assert rel.lot_size == 500
    assert rel.target_pts == 10.0
    assert rel.sl_pts == 4.5
    assert rel.be_pts == 3.5
    assert rel.profit_lock_trigger == 5.5

    ada = get_asset_spec("ADANIENT")
    assert ada.symbol == "ADANIENT"
    assert ada.lot_size == 309
    assert ada.target_pts == 35.0
    assert ada.sl_pts == 15.0
    assert ada.be_pts == 12.0
    assert ada.profit_lock_trigger == 20.0
    print("PASS: AssetSpec registry matches verified specifications.")

def test_risk_budgets():
    rb_rel = RelianceRiskBudget.for_symbol("RELIANCE")
    assert rb_rel.lot_size == 500
    assert rb_rel.num_lots == 2
    assert rb_rel.target_pts == 10.0
    assert rb_rel.stop_loss_pts == 4.5
    assert rb_rel.total_quantity == 1000

    rb_ada = RelianceRiskBudget.for_symbol("ADANIENT")
    assert rb_ada.lot_size == 309
    assert rb_ada.num_lots == 2
    assert rb_ada.target_pts == 35.0
    assert rb_ada.stop_loss_pts == 15.0
    assert rb_ada.total_quantity == 618
    print("PASS: RelianceRiskBudget.for_symbol instantiates correct lot and risk values.")

def test_triple_barrier_scaling():
    # Test Reliance
    dyn_tgt_rel, dyn_sl_rel, regime_rel = MultiIndicatorMath.calculate_dynamic_triple_barrier_scaling(
        spot=1167.70,
        intraday_gk_rv=18.0,
        delta=0.52,
        horizon_minutes=45,
        base_target_pts=10.0,
        base_sl_pts=4.5,
        reward_risk_ratio=2.14
    )
    assert 6.0 <= dyn_tgt_rel <= 15.0, f"Unexpected Reliance target: {dyn_tgt_rel}"
    assert 2.5 <= dyn_sl_rel <= 6.5, f"Unexpected Reliance SL: {dyn_sl_rel}"

    # Test Adani (G-01 & G-02: MUST NOT BE CAPPED TO 10.0 and 6.0!)
    dyn_tgt_ada, dyn_sl_ada, regime_ada = MultiIndicatorMath.calculate_dynamic_triple_barrier_scaling(
        spot=2816.80,
        intraday_gk_rv=18.0,
        delta=0.52,
        horizon_minutes=45,
        base_target_pts=35.0,
        base_sl_pts=15.0,
        reward_risk_ratio=2.14
    )
    assert dyn_tgt_ada > 20.0, f"Adani target was truncated! Got {dyn_tgt_ada}"
    assert dyn_sl_ada > 8.0, f"Adani SL was truncated! Got {dyn_sl_ada}"
    print(f"PASS: Triple Barrier Scaling: Reliance ({dyn_tgt_rel}/{dyn_sl_rel}), Adani ({dyn_tgt_ada}/{dyn_sl_ada})")

def test_adapt_to_volatility():
    rb_ada = RelianceRiskBudget.for_symbol("ADANIENT")
    rb_ada.adapt_to_volatility(atr_15m=25.0, delta=0.52, india_vix=14.5)
    # G-03: Must not cap Adani to 12.5 and 5.5
    assert rb_ada.target_pts > 20.0, f"Adani target capped to {rb_ada.target_pts}"
    assert rb_ada.stop_loss_pts > 8.0, f"Adani SL capped to {rb_ada.stop_loss_pts}"
    print(f"PASS: adapt_to_volatility preserves Adani scale: target={rb_ada.target_pts}, sl={rb_ada.stop_loss_pts}")

def test_theta_acceleration_guard():
    is_safe, theta_rel, desc = MultiIndicatorMath.calculate_theta_acceleration_guard(
        current_time=time(11, 0),
        unrealized_pnl_pts=0.0,
        option_ltp=37.65,
        iv=0.21,
        dte=30,
        lot_size=500
    )
    is_safe_ada, theta_ada, desc_ada = MultiIndicatorMath.calculate_theta_acceleration_guard(
        current_time=time(11, 0),
        unrealized_pnl_pts=0.0,
        option_ltp=84.60,
        iv=0.28,
        dte=30,
        lot_size=309
    )
    assert theta_rel > 0 and theta_ada > 0
    print(f"PASS: Theta acceleration guard: Reliance ₹{theta_rel}/hr, Adani ₹{theta_ada}/hr")

def test_kelly_sizing():
    full_k, half_k, lots, risk_cap, status, cvar = MultiIndicatorMath.calculate_conditional_kelly(
        win_rate=90.0,
        reward_risk_ratio=2.14,
        capital=85000.0,
        trade_pnls=[1500, -1000, 2000, 1800, -800],
        lot_size=309,
        atr=25.0,
        symbol="ADANIENT"
    )
    assert lots >= 1
    assert risk_cap > 0
    print(f"PASS: Kelly sizing for Adani: lots={lots}, risk_cap=₹{risk_cap}")

def test_standalone_breakout_symbol_scoping():
    level_rel = StandaloneBreakoutManager.get_or_set_trigger(1170, "CE", 37.65, buffer_pts=1.20, symbol="RELIANCE")
    level_ada = StandaloneBreakoutManager.get_or_set_trigger(2850, "CE", 84.60, buffer_pts=3.50, symbol="ADANIENT")
    assert level_rel == 38.85
    assert level_ada == 88.10
    print(f"PASS: Breakout trigger pinning scoped: REL={level_rel}, ADA={level_ada}")

if __name__ == "__main__":
    print("=" * 60)
    print("Running Verification Suite...")
    print("=" * 60)
    test_asset_specs()
    test_risk_budgets()
    test_triple_barrier_scaling()
    test_adapt_to_volatility()
    test_theta_acceleration_guard()
    test_kelly_sizing()
    test_standalone_breakout_symbol_scoping()
    print("=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! 🚀")
    print("=" * 60)

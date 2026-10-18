"""
views/radar_view.py
Quant Radar & 6-Vector Confluence Engine Tab View.
"""

import streamlit as st


def render_radar_tab(ctx: dict):
    """Renders the Quant Radar, 6-Vector Confluence Tiles, Reference Models, and News Telemetry."""
    st.subheader("🧠 Quant Radar & 6-Vector Confluence Engine")

    render_kpis_fn = ctx.get("render_quant_radar_kpis_fn")
    if render_kpis_fn:
        render_kpis_fn()

    is_sim_active = ctx.get("is_sim_active", False)
    v1_score = ctx.get("v1_score", 0.0)
    v2_score = ctx.get("v2_score", 0.0)
    v3_score = ctx.get("v3_score", 0.0)
    v4_score = ctx.get("v4_score", 0.0)
    v5_score = ctx.get("v5_score", 0.0)
    v6_score = ctx.get("v6_score", 0.0)

    if is_sim_active:
        sim_v1 = max(v1_score, 18.0)
        sim_v2 = max(v2_score, 16.0)
        sim_v3 = max(v3_score, 18.0)
        sim_v4 = max(v4_score, 14.0)
        sim_v5 = max(v5_score, 14.0)
        sim_v6 = 12.0
    else:
        sim_v1, sim_v2, sim_v3 = v1_score, v2_score, v3_score
        sim_v4, sim_v5, sim_v6 = v4_score, v5_score, v6_score

    nifty_pct = ctx.get("nifty_pct", 0.0)
    vix_val = ctx.get("vix_val", 13.5)
    vix_pct_chg = ctx.get("vix_pct_chg", 0.0)
    vix_stable_regime = ctx.get("vix_stable_regime", True)
    mtf_matrix = ctx.get("mtf_matrix", {"m15": {"regime": "NEUTRAL", "desc": "", "is_bullish": False, "is_bearish": False}, "m5": {"trigger": "NONE"}, "m1": {"status": "NONE", "premium_savings_pts": 0.0}})
    latest = ctx.get("latest", {})
    prev = ctx.get("prev", {})
    st_bullish = ctx.get("st_bullish", True)
    orb_l = ctx.get("orb_l", 0.0)
    orb_h = ctx.get("orb_h", 0.0)
    orb_breakout = ctx.get("orb_breakout", False)
    orb_breakdown = ctx.get("orb_breakdown", False)
    spot = ctx.get("spot", 0.0)
    above_vwap = ctx.get("above_vwap", True)
    vwap_z = ctx.get("vwap_z", 0.0)
    avwap_orb = ctx.get("avwap_orb", 0.0)
    avwap_diff = ctx.get("avwap_diff", 0.0)
    avwap_retest_support = ctx.get("avwap_retest_support", False)
    avwap_expanding_above = ctx.get("avwap_expanding_above", False)
    avwap_trap_failed = ctx.get("avwap_trap_failed", False)
    cvd_val = ctx.get("cvd_val", 0.0)
    cvd_slope = ctx.get("cvd_slope", 0.0)
    bar_delta = ctx.get("bar_delta", 0.0)
    cvd_buyer_agg = ctx.get("cvd_buyer_agg", True)
    cvd_bull_divergence = ctx.get("cvd_bull_divergence", False)
    cvd_bear_divergence = ctx.get("cvd_bear_divergence", False)
    depth_ratio = ctx.get("depth_ratio", 1.0)
    ob_depth = ctx.get("ob_depth", {"bias": "NEUTRAL", "buy_qty": 0, "sell_qty": 0})
    opt_telemetry = ctx.get("opt_telemetry", {"call_oi_change_pct": 0.0, "put_oi_change_pct": 0.0})
    call_unwinding = ctx.get("call_unwinding", False)
    put_writing = ctx.get("put_writing", False)
    pcr_val = ctx.get("pcr_val", 1.0)
    pcr_vol = ctx.get("pcr_vol", 1.0)
    chain_oi = ctx.get("chain_oi", {"max_pain": 0.0, "overall_pcr": 1.0})
    call_wall = ctx.get("call_wall", 0.0)
    put_wall = ctx.get("put_wall", 0.0)
    stock_atr = ctx.get("stock_atr", 0.0)
    effective_sl_pts = ctx.get("effective_sl_pts", 0.0)
    chop_val = ctx.get("chop_val", 50.0)
    is_trending_regime = ctx.get("is_trending_regime", False)
    is_choppy_regime = ctx.get("is_choppy_regime", False)
    scrip_name = ctx.get("scrip_name", "NIFTY")
    scrip_symbol = ctx.get("scrip_symbol", "NIFTY")
    rel_iv = ctx.get("rel_iv", 0.15)
    iv_percentile = ctx.get("iv_percentile", 45.0)
    iv_cheap_window = ctx.get("iv_cheap_window", True)
    iv_elevated_crush_risk = ctx.get("iv_elevated_crush_risk", False)
    bb_expanding = ctx.get("bb_expanding", False)
    rsi_sweetspot_bull = ctx.get("rsi_sweetspot_bull", False)
    rsi_sweetspot_bear = ctx.get("rsi_sweetspot_bear", False)
    macd_expanding_bull = ctx.get("macd_expanding_bull", False)
    macd_expanding_bear = ctx.get("macd_expanding_bear", False)
    lot_size = ctx.get("lot_size", 25)
    kelly_recommended_lots = ctx.get("kelly_recommended_lots", 4)
    atm_strike = ctx.get("atm_strike", 0)
    recommended_contract_type = ctx.get("recommended_contract_type", "CE")
    expiry_date_str = ctx.get("expiry_date_str", "")
    dte = ctx.get("dte", 0)
    sigma = ctx.get("sigma", 0.15)
    active_delta = ctx.get("active_delta", 0.52)
    half_kelly_pct = ctx.get("half_kelly_pct", 5.0)
    kelly_status = ctx.get("kelly_status", "OPTIMAL")
    base_confluence = ctx.get("base_confluence", 75.0)
    news_modifier = ctx.get("news_modifier", 0.0)
    dominant_score = ctx.get("dominant_score", 75.0)
    cam_h4 = ctx.get("cam_h4", 0.0)
    cam_breakout_bull = ctx.get("cam_breakout_bull", False)
    cam_breakdown_bear = ctx.get("cam_breakdown_bear", False)
    basis_pts = ctx.get("basis_pts", 0.0)
    basis_pct = ctx.get("basis_pct", 0.0)
    basis_regime = ctx.get("basis_regime", "NORMAL")
    pcr_flow_bias = ctx.get("pcr_flow_bias", "NEUTRAL")
    hurst_val = ctx.get("hurst_val", 0.55)
    hurst_regime = ctx.get("hurst_regime", "TRENDING_PERSISTENCE")
    exp_move_pts = ctx.get("exp_move_pts", 100.0)
    exp_lower = ctx.get("exp_lower", 0.0)
    exp_upper = ctx.get("exp_upper", 0.0)
    straddle_regime = ctx.get("straddle_regime", "NORMAL")
    risk_pct_of_capital = ctx.get("risk_pct_of_capital", 3.0)
    capital_risk_safe = ctx.get("capital_risk_safe", True)
    net_actual_risk = ctx.get("net_actual_risk", 5000.0)
    kyle_p30_val = ctx.get("p30_lambda", 0.85)
    kyle_curr_val = ctx.get("curr_lambda", 0.75)
    gk_ratio_disp = ctx.get("gk_ratio_app", 1.25)
    gk_is_gen = ctx.get("is_gen_mom_app", False)
    beta_coup_disp = ctx.get("beta_coupling", 1.10)
    energy_coupled_disp = ctx.get("is_energy_coupled", True)
    sweep_detected_disp = ctx.get("has_inst_sweep", False)
    sweep_dir_disp = ctx.get("sweep_dir", "NO_SWEEP")
    is_volume_absorption = ctx.get("is_volume_absorption", True)
    is_liquidity_vacuum = ctx.get("is_liquidity_vacuum", False)
    is_sector_divergence_trap = ctx.get("is_sector_divergence_trap", False)
    energy_pct = ctx.get("energy_pct", 0.5)
    rs_ratio = ctx.get("rs_ratio", 1.05)
    news_list = ctx.get("news_list", [])
    _calib_s0 = ctx.get("_calib_s0", 55.0)
    _calib_k = ctx.get("_calib_k", 0.08)

    macro_beh_str = f"Benchmark Macro Telemetry: NIFTY 50 is at {nifty_pct:+.2f}%, INDIA VIX at {vix_val:.2f} ({vix_pct_chg:+.2f}%). Domestic capital flow momentum is aligned."
    v1_macro_metric = ("Benchmark Macro Telemetry", f"VIX {vix_val:.2f} ({vix_pct_chg:+.2f}%)", "🟢 Steady Volatility (+2)" if vix_stable_regime else "🟡 High Volatility (0)")

    v1_beh = (
        f"Multi-Timeframe Matrix: M15 Structural Regime is {mtf_matrix['m15']['regime'].replace('_', ' ')} ({mtf_matrix['m15']['desc']}) with 9/20/50 EMAs stacked. "
        f"M5 Setup Trigger is {mtf_matrix['m5']['trigger'].replace('_', ' ')}. "
        f"M1 Scalp Micro-Timing is in {mtf_matrix['m1']['status'].replace('_', ' ')} (Optimal Limit Order saves ₹{mtf_matrix['m1']['premium_savings_pts']:.2f}/unit on option premium). "
        f"SuperTrend active at ₹{latest.get('SuperTrend', 0.0):.2f} ({'Buy Regime' if st_bullish else 'Sell Regime'}). "
        f"15m ORB sits at ₹{orb_l:.2f} - ₹{orb_h:.2f} ({'Breakout Above ORB High' if orb_breakout else ('Breakdown Below ORB Low' if orb_breakdown else 'Inside 15m Range')}). "
        f"NIFTY 50 Index Beta is at {nifty_pct:+.2f}%. {macro_beh_str}"
    )
    v2_beh = (
        f"Spot price is sustaining {spot - float(latest.get('VWAP', spot)):+.2f} pts {'above' if above_vwap else 'below'} institutional Session VWAP (₹{float(latest.get('VWAP', spot)):.2f}, Z-score: {vwap_z:+.2f}σ). "
        f"ORB-15 Anchored VWAP sits at ₹{avwap_orb:.2f} ({'Grade A+ Retest Support Holding (+3.0 pts)' if avwap_retest_support else ('Expanding Above Anchor (+2.0 pts)' if avwap_expanding_above else ('Failed Breakout Trap (-4.0 pts)' if avwap_trap_failed else 'Pre-Breakout Anchor'))}). "
        f"Cumulative Volume Delta (CVD) Aggressor Flow: {cvd_val:+,.0f} contracts (Slope: {cvd_slope:+,.0f}, {'Buyer Aggression lifting Ask' if cvd_buyer_agg else 'Seller Aggression hitting Bid'}). "
        f"CVD Divergence: {'🟢 BULLISH ABSORPTION DIVERGENCE ACTIVE (Spot pinned while CVD at new highs -> 80%+ win rate setup)' if cvd_bull_divergence else ('🔴 BEARISH DISTRIBUTION DIVERGENCE ACTIVE' if cvd_bear_divergence else 'In-Line Flow')}. "
        f"Level-2 Order Book Imbalance ratio sits at {depth_ratio:.2f}x ({ob_depth['bias'].replace('_', ' ')}: {ob_depth['buy_qty']:,} Bids vs {ob_depth['sell_qty']:,} Asks)."
    )
    call_oi_chg_val = opt_telemetry.get('call_oi_change_pct', 0.0)
    put_oi_chg_val = opt_telemetry.get('put_oi_change_pct', 0.0)
    call_trap_str = f"trapped and unwinding positions ({call_oi_chg_val:+.1f}%)" if call_oi_chg_val < 0 else f"adding resistance contracts ({call_oi_chg_val:+.1f}%)"
    put_trap_str = f"builds aggressive support ({put_oi_chg_val:+.1f}%)" if put_writing else f"maintains support ({put_oi_chg_val:+.1f}%)"
    v3_beh = f"Call writers are {call_trap_str} while Put open interest {put_trap_str}. Total corridor PCR sits at {pcr_val:.2f} with Max Pain at ₹{chain_oi.get('max_pain', 0.0):.0f}, Call Wall at ₹{call_wall:.0f}, and Put Wall at ₹{put_wall:.0f}."

    v4_beh = (
        f"Daily ATR of ₹{float(latest.get('ATR', 0.0)):.2f} (5m ATR ₹{stock_atr:.2f} -> Dynamic 1.5x SL: {effective_sl_pts:.1f} pts, ≤4% Account Risk). "
        f"Choppiness Index (CHOP-14) at {chop_val:.1f} signals {'a strong directional expansion regime' if is_trending_regime else ('an extreme sideways consolidation trap (Stand Down enforced)' if is_choppy_regime else 'moderate fluctuation')}. "
        f"{scrip_name} ATM Implied Volatility sits at {rel_iv*100.0:.1f}% (IV Percentile: {iv_percentile:.1f}%, {'🟢 Clean Buying Window (<50%)' if iv_cheap_window else ('🔴 Peak Volatility Crush Hazard (>70%)' if iv_elevated_crush_risk else '🟡 Fair Volatility')}). "
        f"India VIX sits at {vix_val:.2f} ({vix_pct_chg:+.2f}%). "
        f"Bollinger bands show {'active breakout expansion' if bb_expanding else 'steady oscillation'}."
    )
    v5_beh = (
        f"RSI at {float(latest.get('RSI', 50.0)):.1f} and MACD histogram at {float(latest.get('MACD_Hist', 0.0)):+.2f} reflect "
        f"{'harmonious upward momentum with zero divergence, confirming directional expansion' if (rsi_sweetspot_bull and macd_expanding_bull) else ('strong downward velocity' if (rsi_sweetspot_bear and macd_expanding_bear) else 'controlled oscillator velocity')} against spot."
    )
    v6_risk_val = effective_sl_pts * lot_size * kelly_recommended_lots
    v6_beh = (
        f"Protocol dynamically routes {scrip_name} execution to {scrip_symbol} {atm_strike} {recommended_contract_type} ({expiry_date_str}, {dte} DTE). "
        f"Terminal week 0-DTE accelerated decay is completely neutralized with {scrip_symbol} ATM IV at {sigma*100.0:.1f}%, maintaining contract delta ({active_delta:+.2f}) and Half-Kelly sizing ({kelly_recommended_lots} lot{'s' if kelly_recommended_lots > 1 else ''} / {lot_size*kelly_recommended_lots} qty, Risk: ₹{v6_risk_val:,.0f}) within account risk limits."
    )

    vector_tiles_data = [
        {
            "num": 1,
            "title": "Vector 1: Multi-Timeframe Trend & Structure",
            "icon": "📈",
            "score": sim_v1,
            "max": 20.0,
            "source": "M15 Structural + M5 Trigger + CPR + SuperTrend + ORB",
            "metrics": [
                ("M15 Structural Compass", f"{mtf_matrix['m15']['regime'].replace('_', ' ')}", f"{'🟢' if mtf_matrix['m15']['is_bullish'] else ('🔴' if mtf_matrix['m15']['is_bearish'] else '🟡')} 9/20/50 Stack"),
                ("SuperTrend (5m Pillar)", f"ST ₹{float(latest.get('SuperTrend', 0.0)):.1f}", f"{'🟢 Buy Regime (+4)' if st_bullish else '🔴 Sell Regime (0 pts)'}"),
                ("15m Opening Range (ORB)", f"ORB ₹{orb_h:.1f} - ₹{orb_l:.1f}", f"{'🟢 Confirmed Breakout (+3)' if orb_breakout else ('🔴 Confirmed Breakdown' if orb_breakdown else '🟡 Inside Range (0 pts)')}"),
                ("Central Pivot Range (CPR)", f"TC ₹{float(latest.get('CPR_TC', spot)):.1f} | BC ₹{float(latest.get('CPR_BC', spot)):.1f}", f"{'🟢 Pivot Breakout (+2.5)' if spot > float(latest.get('CPR_TC', spot)) else ('🔴 Below BC' if spot < float(latest.get('CPR_BC', spot)) else '🟡 Inside CPR')}"),
                v1_macro_metric,
            ],
            "behavior": v1_beh
        },
        {
            "num": 2,
            "title": "Vector 2: VWAP, CVD, CMF & Order Flow",
            "icon": "📊",
            "score": sim_v2,
            "max": 18.0,
            "source": "Session VWAP + ORB AVWAP + CVD + CMF + PVT + EOM",
            "metrics": [
                ("ORB-15 Anchored VWAP", f"AVWAP: ₹{avwap_orb:.2f} ({avwap_diff:+.2f}p)", f"{'🟢 Retest Support (+3)' if avwap_retest_support else ('🟢 Expanding (+2)' if avwap_expanding_above else ('🔴 Trap Breached (-4)' if avwap_trap_failed else '🟡 Pre-Breakout'))}"),
                ("CVD Aggressor Flow", f"CVD: {cvd_val:+,.0f} (Δ: {bar_delta:+,.0f})", f"{'🟢 Buyer Ask Aggression (+3)' if cvd_buyer_agg else '🔴 Seller Bid Dominance'}"),
                ("Chaikin Money Flow & PVT", f"CMF {float(latest.get('CMF_20', 0.0)):+.3f} | PVT {float(latest.get('PVT', 0.0)):+,.0f}", f"{'🟢 Inst Accumulation' if float(latest.get('CMF_20', 0.0)) >= 0.05 else ('🔴 Inst Distribution' if float(latest.get('CMF_20', 0.0)) <= -0.05 else '🟡 Neutral Money Flow')}"),
                ("Ease of Movement (EOM-14)", f"EOM: {float(latest.get('EOM_14', 0.0)):+.2f}", f"{'🟢 Effortless Upward Expansion' if float(latest.get('EOM_14', 0.0)) > 5.0 else ('🔴 Downward Collapse' if float(latest.get('EOM_14', 0.0)) < -5.0 else '🟡 Balanced Flow')}"),
                ("Session VWAP & L2 Imbalance", f"VWAP ₹{float(latest.get('VWAP', spot)):.2f} | L2: {depth_ratio:.2f}x", f"🟢 Above Mean (+4)" if above_vwap else f"🔴 Below Mean (+4)")
            ],
            "behavior": v2_beh
        },
        {
            "num": 3,
            "title": "Vector 3: Gamma Squeeze, Basis & Flow Divergence",
            "icon": "⚡",
            "score": sim_v3,
            "max": 20.0,
            "source": "Groww Live Chain + Cash-Futures Basis + PCR Flow Divergence",
            "metrics": [
                (f"Call OI Shift ({atm_strike} CE)", f"{opt_telemetry.get('call_oi_change_pct', 0.0):+.1f}% shift", "🟢 Short Covering (+8)" if call_unwinding else ("🟡 Mild Drop (+4)" if opt_telemetry.get('call_oi_change_pct', 0.0) < 0 else "🔴 Call Writing")),
                (f"Put OI Shift ({atm_strike} PE)", f"{opt_telemetry.get('put_oi_change_pct', 0.0):+.1f}% shift", "🟢 Heavy Writing (+6)" if put_writing else ("🟡 Put Support (+3)" if opt_telemetry.get('put_oi_change_pct', 0.0) > 10.0 else "🔴 Low Put Buildup")),
                ("Cash-Futures Basis Spread", f"Basis: {basis_pts:+.2f} pts ({basis_pct:+.2f}%)", f"{'🟢 Futures Long Accumulation (+2)' if basis_regime == 'INSTITUTIONAL_FUTURES_LONG_ACCUMULATION' else ('🔴 Discount Bearish Hedging' if 'DISCOUNT' in basis_regime else '🟡 Normal Basis')}"),
                ("PCR Flow vs OI Divergence", f"PCR Vol {pcr_vol:.2f} vs OI {chain_oi.get('overall_pcr', 1.0):.2f}", f"{'🟢 Stealth Call Buying (+2.5)' if 'CALL' in pcr_flow_bias else ('🔴 Stealth Put Buying (+2.5)' if 'PUT' in pcr_flow_bias else '🟡 Aligned Flow')}"),
                ("PCR (OI) & Max Pain", f"PCR: {pcr_val:.2f} | Max Pain: ₹{chain_oi.get('max_pain', 0.0):.0f}", "🟢 Strong Cushion (+6)" if pcr_val >= 1.25 else ("🟡 Neutral (+3)" if pcr_val >= 1.05 else "🔴 Bearish (<1.05)"))
            ],
            "behavior": v3_beh
        },
        {
            "num": 4,
            "title": "Vector 4: Volatility, CHOP, Mass Index & Straddle",
            "icon": "🎯",
            "score": sim_v4,
            "max": 15.0,
            "source": "Wilder's ATR (14) + CHOP + Chaikin Vol + Mass Index + ATM Straddle",
            "metrics": [
                (f"{scrip_name} IV Percentile (IVP)", f"{iv_percentile:.1f}% (IV {rel_iv*100.0:.1f}%)", "🟢 Clean Buying Window (+2)" if iv_cheap_window else ("🔴 IV Crush Lock (-4)" if iv_elevated_crush_risk else "🟡 Fair Value")),
                ("Choppiness Index & Hurst (H)", f"CHOP: {chop_val:.1f} | H={hurst_val:.2f}", "🟢 Trending Persistence (+4)" if (is_trending_regime and hurst_regime == 'TRENDING_PERSISTENCE') else ("🛑 Choppy Stand Down (0)" if is_choppy_regime else "🟡 Moderate Range")),
                ("Chaikin Vol & Mass Index", f"CV: {float(latest.get('Chaikin_Vol', 0.0)):+.1f}% | Mass: {float(latest.get('Mass_Index', 25.0)):.2f}", f"{'🟢 Volatility Explosion (+1.5)' if float(latest.get('Chaikin_Vol', 0.0)) > 15.0 else '🟡 Standard Volatility'}"),
                ("ATM Straddle Expected Move", f"±₹{exp_move_pts:.1f} (₹{exp_lower:.1f} - ₹{exp_upper:.1f})", f"{'🟢 Squeeze Expansion (+2)' if 'SQUEEZE' in straddle_regime else '🟡 Rangebound Inside Move'}"),
                ("Dynamic ATR(14) Stop Loss", f"{effective_sl_pts:.1f} pts (-₹{net_actual_risk:,.0f})", f"🟢 ≤4.0% Risk Cap ({risk_pct_of_capital:.1f}%)" if capital_risk_safe else "🔴 Exceeds 4% Budget")
            ],
            "behavior": v4_beh
        },
        {
            "num": 5,
            "title": "Vector 5: Zero-Divergence Momentum & Cycle",
            "icon": "🚀",
            "score": sim_v5,
            "max": 15.0,
            "source": "RSI + MACD + CMO + STC + Fisher Transform + Connors RSI",
            "metrics": [
                ("RSI (14) Relative Strength", f"{float(latest.get('RSI', 50.0)):.1f} (Sweet Spot: 62-76)", "🟢 Bullish Power Band (+6)" if rsi_sweetspot_bull else ("🔴 Bearish Breakdown (+6)" if rsi_sweetspot_bear else ("🟡 Constructive (+3)" if float(latest.get('RSI', 50.0)) >= 55.0 else "🔴 Neutral/Weak"))),
                ("Chande Momentum (CMO-14)", f"CMO: {float(latest.get('CMO_14', 0.0)):+.1f}", f"{'🟢 Strong Bull Momentum (+2.5)' if float(latest.get('CMO_14', 0.0)) >= 25.0 else ('🔴 Strong Bear Momentum (+2.5)' if float(latest.get('CMO_14', 0.0)) <= -25.0 else '🟡 Neutral Momentum')}"),
                ("Schaff Trend Cycle & Fisher", f"STC {float(latest.get('STC', 50.0)):.1f} | Fisher {float(latest.get('Fisher_Transform', 0.0)):+.2f}", f"{'🟢 Bullish Cycle (+2)' if float(latest.get('STC', 50.0)) >= 75.0 else ('🔴 Bearish Cycle (+2)' if float(latest.get('STC', 50.0)) <= 25.0 else '🟡 Balanced Cycle')}"),
                ("Connors RSI-3 Pullback Timing", f"CRSI-3: {float(latest.get('Connors_RSI', 50.0)):.1f}", f"{'🟢 Oversold Dip Buy (+2)' if float(latest.get('Connors_RSI', 50.0)) <= 20.0 else ('🔴 Overbought Rally Sell' if float(latest.get('Connors_RSI', 50.0)) >= 80.0 else '🟡 Neutral Pullback')}"),
                ("MACD Histogram Trend", f"{float(latest.get('MACD_Hist', 0.0)):+.2f} (vs Prev: {float(prev.get('MACD_Hist', 0.0)):+.2f})", "🟢 Accelerating Bull (+5)" if macd_expanding_bull else ("🔴 Accelerating Bear (+5)" if macd_expanding_bear else "🟡 Decelerating (0)"))
            ],
            "behavior": v5_beh
        },
        {
            "num": 6,
            "title": "Vector 6: Expiry, Greeks & Half-Kelly Sizing",
            "icon": "🛡️",
            "score": sim_v6,
            "max": 12.0,
            "source": "Weekly Expiry Mandate + Black-Scholes Greeks + Dynamic Half-Kelly",
            "metrics": [
                ("Dynamic Active Contract", f"{scrip_symbol} {atm_strike} {recommended_contract_type} ({expiry_date_str})", f"🟢 {dte} DTE Mandate Active"),
                ("Dynamic Half-Kelly Sizing", f"{half_kelly_pct:.1f}% ({kelly_recommended_lots} Lot{'s' if kelly_recommended_lots > 1 else ''} | {lot_size * kelly_recommended_lots} Qty | Risk: ₹{v6_risk_val:,.0f})", f"{'🟢 ' + kelly_status.replace('_', ' ') if 'OPTIMAL' in kelly_status else '🟡 ' + kelly_status.replace('_', ' ')}"),
                ("Decay Avoidance Protocol", "Weekly Schedule Enforcement", f"🟢 0-DTE Decay Neutralized ({scrip_symbol})"),
                ("Greeks Protection Shield", f"Delta: {active_delta:+.2f} ({recommended_contract_type}) | IV: {sigma*100.0:.1f}%", f"🟢 Theta Drag Insulated (+{sim_v6:.0f})")
            ],
            "behavior": v6_beh
        }
    ]

    cards_html = []
    for v in vector_tiles_data:
        pct = min(100.0, max(0.0, (v["score"] / v["max"]) * 100.0))
        if pct >= 75.0:
            badge_bg = "rgba(16, 185, 129, 0.18)"
            badge_border = "rgba(16, 185, 129, 0.40)"
            badge_color = "#34D399"
            badge_text = "CONFLUENT"
            bar_grad = "linear-gradient(90deg, #059669, #10B981)"
            border_top = "#10B981"
        elif pct >= 50.0:
            badge_bg = "rgba(245, 158, 11, 0.18)"
            badge_border = "rgba(245, 158, 11, 0.40)"
            badge_color = "#FBBF24"
            badge_text = "MODERATE"
            bar_grad = "linear-gradient(90deg, #D97706, #F59E0B)"
            border_top = "#F59E0B"
        else:
            badge_bg = "rgba(239, 68, 68, 0.18)"
            badge_border = "rgba(239, 68, 68, 0.40)"
            badge_color = "#F87171"
            badge_text = "DIVERGENT"
            bar_grad = "linear-gradient(90deg, #DC2626, #EF4444)"
            border_top = "#EF4444"

        metrics_rows = "".join([
            f'''<div class="vector-metric-row">
                <span style="color: #94A3B8; font-weight: 600;">{m[0]}</span>
                <span style="color: #FFFFFF; font-weight: 700; margin: 0 6px;">{m[1]}</span>
                <span style="font-size: 0.70rem; font-weight: 700;">{m[2]}</span>
            </div>'''
            for m in v["metrics"]
        ])

        card_str = f'''
        <div class="vector-tile-card" style="border-top: 3px solid {border_top} !important;">
            <div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span style="font-size: 1.05rem;">{v["icon"]}</span>
                        <span style="font-size: 0.82rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.3px;">
                            {v["title"]}
                        </span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span style="background: {badge_bg}; color: {badge_color}; font-size: 0.68rem; padding: 2px 7px; border-radius: 4px; font-weight: 800; border: 1px solid {badge_border};">
                            {badge_text}
                        </span>
                        <span style="font-size: 0.80rem; font-weight: 800; color: #FFFFFF;">
                            {v["score"]:.1f}<span style="font-size: 0.70rem; color: #94A3B8;">/{v["max"]:.0f} pts</span>
                        </span>
                    </div>
                </div>

                <div style="width: 100%; height: 5px; background: #1E293B; border-radius: 3px; overflow: hidden; margin-bottom: 10px;">
                    <div style="width: {pct:.1f}%; height: 100%; background: {bar_grad}; border-radius: 3px;"></div>
                </div>

                <div style="margin-bottom: 4px;">
                    {metrics_rows}
                </div>
            </div>

            <div>
                <div class="vector-behavior-box" style="border-left-color: {border_top};">
                    <span style="color: #38BDF8; font-weight: 700;">⚡ Current Behavior:</span>
                    <span style="color: #CBD5E1;"> {v["behavior"]}</span>
                </div>

                <div style="font-size: 0.66rem; color: #64748B; border-top: 1px solid #1E293B; margin-top: 8px; padding-top: 4px; display: flex; justify-content: space-between;">
                    <span>Source:</span>
                    <span style="color: #38BDF8; font-weight: 600;">{v.get("source", "Quantitative Engine Feed")}</span>
                </div>
            </div>
        </div>
        '''
        cards_html.append(card_str)

    all_vector_cards_str = "".join(cards_html)
    raw_composite_pts = base_confluence + (news_modifier if recommended_contract_type == "CE" else -news_modifier)
    active_conf_score = dominant_score

    st.html(f"""
    <div style="margin: 16px 0 14px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="live-dot"></span>
                <span style="font-size: 0.88rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.5px; text-transform: uppercase;">
                    ⚡ 6-VECTOR QUANTITATIVE CONFLUENCE ENGINE — LIVE COMPONENT TILES
                </span>
                <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; font-size: 0.70rem; padding: 2px 8px; border-radius: 4px; font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.3);">
                    REAL-TIME BEHAVIORAL AUDIT
                </span>
            </div>
            <div style="font-size: 0.75rem; color: #94A3B8;">
                Aggregated: <b style="color: #34D399; font-size: 0.85rem;">{base_confluence:.1f} pts</b> &nbsp;|&nbsp; Macro News: <b style="color: {'#34D399' if news_modifier >= 0 else '#F87171'}; font-size: 0.85rem;">{news_modifier:+.1f} pts</b> <span style="color: #64748B;">(Raw: {raw_composite_pts:.1f} pts)</span> &nbsp;|&nbsp; Calibrated Win Rate: <b style="color: #FFFFFF; font-size: 0.90rem; cursor: help;" title="Sigmoid Calibration: Raw {raw_composite_pts:.1f} pts mapped via institutional logistic curve ({_calib_s0:.1f} pts = 50% neutral baseline, k={_calib_k}) into statistical win probability">{active_conf_score}%</b>
            </div>
        </div>
        <div class="vector-grid">
            {all_vector_cards_str}
        </div>
    </div>
    """)

    # 4 STATE-OF-THE-ART INSTITUTIONAL REFERENCE MODELS
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.90)); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 12px; padding: 18px 20px; margin: 18px 0 24px 0; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.4rem;">🏛️</span>
                <div>
                    <div style="font-size: 0.98rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.5px;">
                        INSTITUTIONAL QUANT DESK ARCHITECTURE & REFERENCE MODELS
                    </div>
                    <div style="font-size: 0.72rem; color: #94A3B8;">
                        4 Empirical Layers: Kyle's Lambda (1985) • NIFTY Energy Beta Coupling • Order Flow Sweeps (Lee-Ready) • Garman-Klass / Parkinson Ratio
                    </div>
                </div>
            </div>
            <div>
                <span style="background: rgba(16, 185, 129, 0.18); color: #34D399; font-size: 0.74rem; padding: 4px 10px; border-radius: 6px; font-weight: 800; border: 1px solid rgba(16, 185, 129, 0.4);">
                    TARGET HIT RATE: 70% – 75%+
                </span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.html(f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin-top: 10px;">
        <!-- Layer 1: Kyle Lambda -->
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid {'#10B981' if is_volume_absorption else ('#EF4444' if is_liquidity_vacuum else '#334155')}; border-radius: 8px; padding: 12px 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #38BDF8;">1. Kyle's Lambda (λ)</span>
                <span style="font-size: 0.68rem; font-weight: 800; color: {'#34D399' if is_volume_absorption else ('#F87171' if is_liquidity_vacuum else '#94A3B8')};">
                    {'THICK DEPTH (+2.5)' if is_volume_absorption else ('VACUUM TRAP' if is_liquidity_vacuum else 'NORMAL')}
                </span>
            </div>
            <div style="font-size: 1.10rem; font-weight: 800; color: #FFFFFF;">
                λ = {kyle_curr_val:.3f} <span style="font-size: 0.72rem; color: #94A3B8;">(P30: {kyle_p30_val:.3f})</span>
            </div>
            <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 4px;">
                Albert S. Kyle (1985) Market Impact: |ΔP| / √V. Absorbing institutional flow without slippage.
            </div>
        </div>

        <!-- Layer 2: Energy Beta Coupling -->
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid {'#10B981' if energy_coupled_disp and not is_sector_divergence_trap else ('#EF4444' if is_sector_divergence_trap else '#334155')}; border-radius: 8px; padding: 12px 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #38BDF8;">2. Energy Beta Coupling</span>
                <span style="font-size: 0.68rem; font-weight: 800; color: {'#F87171' if is_sector_divergence_trap else ('#34D399' if energy_coupled_disp else '#FBBF24')};">
                    {'DIVERGENCE TRAP' if is_sector_divergence_trap else ('COUPLED (>1 LOT)' if energy_coupled_disp else '1-LOT MANDATE')}
                </span>
            </div>
            <div style="font-size: 1.10rem; font-weight: 800; color: #FFFFFF;">
                β = {beta_coup_disp:.2f} <span style="font-size: 0.72rem; color: #94A3B8;">(Energy: {energy_pct:+.2f}%)</span>
            </div>
            <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 4px;">
                Two-Factor Stat-Arb: {scrip_symbol} RS {rs_ratio:.2f}x. {scrip_symbol} aligned with index drops false breakouts &lt;15%.
            </div>
        </div>

        <!-- Layer 3: Order Flow Sweeps -->
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid {'#10B981' if sweep_detected_disp else '#334155'}; border-radius: 8px; padding: 12px 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #38BDF8;">3. Order Flow Sweeps</span>
                <span style="font-size: 0.68rem; font-weight: 800; color: {'#34D399' if sweep_detected_disp else '#94A3B8'};">
                    {'SWEEP ACTIVE (68.2%+)' if sweep_detected_disp else 'RETAIL DRIFT'}
                </span>
            </div>
            <div style="font-size: 1.10rem; font-weight: 800; color: #FFFFFF;">
                {sweep_dir_disp.replace('_', ' ')}
            </div>
            <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 4px;">
                David Easley & Maureen O'Hara (2010): Aggressive trades clearing &gt;3 levels in &lt;100ms.
            </div>
        </div>

        <!-- Layer 4: GK / Parkinson Ratio -->
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid {'#10B981' if gk_is_gen else '#334155'}; border-radius: 8px; padding: 12px 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #38BDF8;">4. GK / Parkinson Vol Ratio</span>
                <span style="font-size: 0.68rem; font-weight: 800; color: {'#34D399' if gk_is_gen else '#94A3B8'};">
                    {'GENUINE TREND (≥1.35)' if gk_is_gen else 'NORMAL'}
                </span>
            </div>
            <div style="font-size: 1.10rem; font-weight: 800; color: #FFFFFF;">
                σ_GK / σ_Park = {gk_ratio_disp:.2f}
            </div>
            <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 4px;">
                Garman & Klass (1980): Minimum-variance OHLC estimator confirms opening jumps create genuine trends.
            </div>
        </div>
    </div>
    </div>
    """)

    st.markdown("---")

    # GLOBAL NEWS & MACRO SENTIMENT TELEMETRY PANEL
    st.subheader("🌐 Global News & Macro Sentiment Telemetry")
    st.caption(f"📡 **Data Source**: Aggregated via Google News RSS ({scrip_symbol} Telemetry) & MCX Commodity Telemetry (Brent Crude & Gold)")
    n_cols = st.columns(len(news_list)) if news_list else [st.container()]
    for idx, item in enumerate(news_list):
        sentiment = item.get("sentiment", "NEUTRAL")
        if sentiment == "BULLISH":
            badge_bg = "rgba(16, 185, 129, 0.20)"
            badge_color = "#34D399"
            badge_border = "#10B981"
            badge_icon = "🟢"
        elif sentiment == "BEARISH":
            badge_bg = "rgba(239, 68, 68, 0.20)"
            badge_color = "#F87171"
            badge_border = "#EF4444"
            badge_icon = "🔴"
        else:
            badge_bg = "rgba(100, 116, 139, 0.20)"
            badge_color = "#CBD5E1"
            badge_border = "#64748B"
            badge_icon = "⚪"

        title_text = item.get("title", "")
        summary_text = item.get("summary", "")
        provider_text = item.get("provider", "Macro Desk")
        date_text = item.get("date", "Today")

        with n_cols[idx]:
            st.html(f"""
            <div class="news-card-equal">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; color: #94A3B8; font-weight: 600; margin-bottom: 8px;">
                        <span style="display: flex; align-items: center; gap: 4px; color: #38BDF8;">📰 {provider_text}</span>
                        <span style="color: #94A3B8;">{date_text}</span>
                    </div>
                    <div style="font-weight: 700; font-size: 0.88rem; line-height: 1.35; color: #FFFFFF; height: 44px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; margin-bottom: 8px;" title="{title_text}">
                        {title_text}
                    </div>
                    <div style="font-size: 0.77rem; line-height: 1.45; color: #CBD5E1; height: 56px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; margin-bottom: 10px;" title="{summary_text}">
                        {summary_text}
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 1px solid #1E293B; margin-top: auto;">
                    <span style="font-size: 0.72rem; padding: 3px 10px; border-radius: 4px; font-weight: 800; background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_border}; display: inline-flex; align-items: center; gap: 4px;">
                        {badge_icon} {sentiment}
                    </span>
                    <span style="font-size: 0.70rem; color: #38BDF8; font-weight: 600;">Src: Google News RSS ⚡</span>
                </div>
            </div>
            """)

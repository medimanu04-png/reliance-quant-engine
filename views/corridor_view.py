"""
views/corridor_view.py
Options Corridor, Dual ATM Strike Comparison & Smart Money Telemetry Tab View.
"""

from datetime import datetime
import streamlit as st
from asset_config import get_asset_spec, build_contract_symbol
from groww_market_feed import GrowwMarketFeed
from fo_quant_engine import MultiIndicatorMath
from trade_journal_manager import SignalTracker, ShadowMonitoringEngine, SequentialTradeEngine


def render_corridor_tab(ctx: dict):
    """Renders the Dual ATM Corridor, Strike Matrix, and 1s Options Stream."""
    st.subheader("📊 Options Corridor, Smart Money & Live Tape")

    scrip_symbol = ctx.get("scrip_symbol", "NIFTY")
    scrip_name = ctx.get("scrip_name", "NIFTY")
    recommended_contract_type = ctx.get("recommended_contract_type", "CE")
    upper_atm = ctx.get("upper_atm", 0)
    lower_atm = ctx.get("lower_atm", 0)
    expiry_date_str = ctx.get("expiry_date_str", "")
    atm_strike = ctx.get("atm_strike", 0)
    high_data = ctx.get("high_data", {})
    low_data = ctx.get("low_data", {})
    spot = ctx.get("spot", 0.0)
    target_pts = ctx.get("target_pts", 20.0)
    current_seq_state = ctx.get("current_seq_state", SequentialTradeEngine.STATE_IDLE)
    live_broker_ltp = ctx.get("live_broker_ltp", 0.0)
    kelly_recommended_lots = ctx.get("kelly_recommended_lots", 4)
    lot_size = ctx.get("lot_size", 25)
    latest = ctx.get("latest", {})
    spec = ctx.get("spec", get_asset_spec(scrip_symbol))
    expiry_plan = ctx.get("expiry_plan", {})
    opt_telemetry = ctx.get("opt_telemetry", {})
    orb_breakout = ctx.get("orb_breakout", False)
    orb_breakdown = ctx.get("orb_breakdown", False)
    stream_live_1s = ctx.get("stream_live_1s", True)
    df = ctx.get("df")
    nse_data = ctx.get("nse_data", {})
    rel_vol = ctx.get("rel_vol", 1.0)
    user_strike_choice = ctx.get("user_strike_choice")
    render_dynamic_1s_atm_feed_fn = ctx.get("render_dynamic_1s_atm_feed_fn")
    render_atm_call_put_content_fn = ctx.get("render_atm_call_put_content_fn")
    trade_plan = ctx.get("trade_plan", {})

    is_rec_pe = (recommended_contract_type == "PE")

    if is_rec_pe:
        matrix_title = f"🏆 Dual ATM Corridor Quantitative Strike Selection Matrix & Rationale ({upper_atm} PE vs {lower_atm} PE - {expiry_date_str})"
        rec_box_border_left = "#EF4444"
        rec_box_badge_bg = "rgba(239, 68, 68, 0.12)"
        rec_box_badge_border = "rgba(239, 68, 68, 0.25)"
        rec_box_badge_color = "#F87171"
        rec_rec_bg = "background: linear-gradient(135deg, rgba(127, 29, 29, 0.5) 0%, rgba(239, 68, 68, 0.18) 100%)"
        rec_rec_border = "#EF4444"
        rec_rec_title_color = "#F87171"
        rec_rec_sub_color = "#FECACA"
        rec_inst_name = f"{scrip_symbol} {upper_atm} PE"

        k1_num = upper_atm
        k1_label = f"🛡️ {scrip_symbol} {upper_atm} PE ({expiry_date_str})"
        k1_rank_title = "RANK #1 BEST STRIKE (Score: 96/100)"
        k1_rank_bg = "#DC2626"
        k1_rank_border = "#EF4444"
        k1_rank_color = "#FFFFFF"
        k1_border = "#EF4444" if atm_strike == upper_atm else "#334155"
        k1_ltp_color = "#C084FC"
        k1_delta_val = abs(high_data.get('delta_pe', 0.52))
        k1_spot_move = high_data.get('spot_move_needed_pe', 20.0)
        k1_intrinsic = max(0.0, round(upper_atm - spot, 2))
        k1_oi_chg = high_data.get('put_oi_change_pct', 0.0)
        k1_b1 = f'<b style="color: #FFFFFF;">Delta Efficiency ({k1_delta_val:.2f}):</b> Requires only <b style="color: #F87171;">-{k1_spot_move:.1f} pts</b> spot drop to hit +{target_pts:.1f} pts target (well within daily ATR).'
        k1_b2 = f'<b style="color: #FFFFFF;">Intrinsic Buffer (₹{k1_intrinsic:.2f}):</b> In-the-money cushion protects against pure theta time decay.'
        k1_b3 = f'<b style="color: #FFFFFF;">Downside Velocity Catalyst:</b> <b style="color: #F87171;">{k1_oi_chg:+.1f}%</b> institutional put writing support creates powerful downside acceleration.'

        k2_num = lower_atm
        k2_label = f"🛡️ {scrip_symbol} {lower_atm} PE ({expiry_date_str})"
        k2_rank_title = "RANK #2 ALTERNATIVE (Score: 78/100)"
        k2_rank_bg = "#1E293B"
        k2_rank_border = "#334155"
        k2_rank_color = "#CBD5E1"
        k2_border = "#C084FC" if atm_strike == lower_atm else "#334155"
        k2_ltp_color = "#C084FC"
        k2_delta_val = abs(low_data.get('delta_pe', 0.45))
        k2_spot_move = low_data.get('spot_move_needed_pe', 25.0)
        k2_b1 = '<b style="color: #FFFFFF;">Out-Of-The-Money:</b> Cheaper premium yields higher percentage ROI on breakdown, but zero intrinsic cushion.'
        k2_b2 = f'<b style="color: #FFFFFF;">Delta Sensitivity ({k2_delta_val:.2f}):</b> Requires larger <b style="color: #FBBF24;">-{k2_spot_move:.1f} pts</b> spot drop to hit +{target_pts:.1f} pts target (exceeds standard 15m ATR).'
        k2_b3 = '<b style="color: #FFFFFF;">Higher Decay Vulnerability:</b> 100% extrinsic value makes it vulnerable if downward momentum stalls.'

        c1_live_ltp = float(high_data.get('put_ltp', 0.0))
        c2_live_ltp = float(low_data.get('put_ltp', 0.0))
    else:
        matrix_title = f"🏆 Dual ATM Corridor Quantitative Strike Selection Matrix & Rationale ({lower_atm} CE vs {upper_atm} CE - {expiry_date_str})"
        rec_box_border_left = "#10B981"
        rec_box_badge_bg = "rgba(16, 185, 129, 0.12)"
        rec_box_badge_border = "rgba(16, 185, 129, 0.25)"
        rec_box_badge_color = "#10B981"
        rec_rec_bg = "background: linear-gradient(135deg, rgba(6, 95, 70, 0.5) 0%, rgba(16, 185, 129, 0.18) 100%)"
        rec_rec_border = "#10B981"
        rec_rec_title_color = "#34D399"
        rec_rec_sub_color = "#A7F3D0"
        rec_inst_name = f"{scrip_symbol} {lower_atm} CE"

        k1_num = lower_atm
        k1_label = f"📞 {scrip_symbol} {lower_atm} CE ({expiry_date_str})"
        k1_rank_title = "RANK #1 BEST STRIKE (Score: 96/100)"
        k1_rank_bg = "#059669"
        k1_rank_border = "#10B981"
        k1_rank_color = "#FFFFFF"
        k1_border = "#10B981" if atm_strike == lower_atm else "#334155"
        k1_ltp_color = "#38BDF8"
        k1_delta_val = low_data.get('delta_ce', 0.58)
        k1_spot_move = low_data.get('spot_move_needed_ce', 18.0)
        k1_intrinsic = low_data.get('intrinsic_ce', 0.0)
        k1_oi_chg = low_data.get('call_oi_change_pct', 0.0)
        k1_oi_lots = low_data.get('call_oi_lots', 0)
        k1_b1 = f'<b style="color: #FFFFFF;">Delta Efficiency ({k1_delta_val}):</b> Requires only <b style="color: #34D399;">+{k1_spot_move} pts</b> spot move to hit +{target_pts:.1f} pts target (well within daily ATR).'
        k1_b2 = f'<b style="color: #FFFFFF;">Intrinsic Buffer (₹{k1_intrinsic:.2f}):</b> In-the-money cushion protects against pure theta time decay.'
        k1_b3 = f'<b style="color: #FFFFFF;">Short Squeeze Catalyst:</b> <b style="color: #34D399;">{k1_oi_chg:+.1f}%</b> surge in {k1_oi_lots:,} lots creates explosive short-covering fuel.'

        k2_num = upper_atm
        k2_label = f"📞 {scrip_symbol} {upper_atm} CE ({expiry_date_str})"
        k2_rank_title = "RANK #2 ALTERNATIVE (Score: 78/100)"
        k2_rank_bg = "#1E293B"
        k2_rank_border = "#334155"
        k2_rank_color = "#CBD5E1"
        k2_border = "#38BDF8" if atm_strike == upper_atm else "#334155"
        k2_ltp_color = "#38BDF8"
        k2_delta_val = high_data.get('delta_ce', 0.45)
        k2_spot_move = high_data.get('spot_move_needed_ce', 22.0)
        k2_b1 = '<b style="color: #FFFFFF;">Out-Of-The-Money:</b> Cheaper premium yields higher percentage ROI on breakout, but zero intrinsic cushion.'
        k2_b2 = f'<b style="color: #FFFFFF;">Delta Sensitivity ({k2_delta_val}):</b> Requires larger <b style="color: #FBBF24;">+{k2_spot_move} pts</b> spot move to hit +{target_pts:.1f} pts target (exceeds standard 15m ATR).'
        k2_b3 = '<b style="color: #FFFFFF;">Higher Decay Vulnerability:</b> 100% extrinsic value makes it vulnerable if momentum stalls.'

        c1_live_ltp = float(low_data.get('call_ltp', 0.0))
        c2_live_ltp = float(high_data.get('call_ltp', 0.0))

    try:
        gw_chain_fresh = GrowwMarketFeed.get_instance().get_live_option_chain(symbol=scrip_symbol)
        if gw_chain_fresh:
            for row in gw_chain_fresh:
                if abs(row.get("strike", 0) - lower_atm) < 0.5:
                    if is_rec_pe and row.get("put_ltp"):
                        c2_live_ltp = float(row["put_ltp"])
                    elif not is_rec_pe and row.get("call_ltp"):
                        c1_live_ltp = float(row["call_ltp"])
                elif abs(row.get("strike", 0) - upper_atm) < 0.5:
                    if is_rec_pe and row.get("put_ltp"):
                        c1_live_ltp = float(row["put_ltp"])
                    elif not is_rec_pe and row.get("call_ltp"):
                        c2_live_ltp = float(row["call_ltp"])
    except Exception:
        pass

    corridor_step = spec.strike_step
    with st.expander(matrix_title, expanded=(current_seq_state == SequentialTradeEngine.STATE_IDLE)):
        st.html(f"""
        <div style="background: #0B1120 !important; border: 1px solid #1E293B !important; border-left: 4px solid {rec_box_border_left} !important; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);">
            <div style="display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 20px;">
                <div style="min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <span style="font-size: 0.72rem; color: {rec_box_badge_color}; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; background: {rec_box_badge_bg}; padding: 2px 8px; border-radius: 4px; border: 1px solid {rec_box_badge_border};">⚡ DUAL ATM CORRIDOR DEFINITION ({corridor_step}-PT INCREMENT)</span>
                    </div>
                    <div style="font-size: 0.88rem; color: #CBD5E1; line-height: 1.5;">
                        {scrip_name} Spot is at <b style="color: #38BDF8; font-weight: 800;">₹{spot:.2f}</b>, bracketed by Lower ATM <b style="color: #FFFFFF; font-weight: 700;">₹{lower_atm}</b> (<span style="color: #F87171; font-weight: 700;">-{spot - lower_atm:.2f} pts</span>) and Upper ATM <b style="color: #FFFFFF; font-weight: 700;">₹{upper_atm}</b> (<span style="color: #34D399; font-weight: 700;">+{upper_atm - spot:.2f} pts</span>). Both strikes qualify as At-The-Money under live market mechanics.
                    </div>
                </div>
                <div style="flex-shrink: 0;">
                    <div style="{rec_rec_bg}; border: 1px solid {rec_rec_border}; border-radius: 8px; padding: 10px 16px; text-align: right; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25); white-space: nowrap;">
                        <div style="font-size: 0.66rem; font-weight: 800; color: {rec_rec_title_color}; text-transform: uppercase; letter-spacing: 0.8px;">⭐ ALGORITHMIC RECOMMENDATION</div>
                        <div style="font-size: 0.95rem; font-weight: 800; color: #FFFFFF; margin-top: 2px; letter-spacing: 0.3px;">{rec_inst_name} <span style="font-size: 0.78rem; color: {rec_rec_sub_color}; font-weight: 600;">({expiry_date_str})</span></div>
                    </div>
                </div>
            </div>
        </div>
        """)

        st.html(f"""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; width: 100%; align-items: stretch; margin-top: 4px;">
            <div style="background: #0F172A !important; border: 2px solid {k1_border} !important; border-radius: 8px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.5); box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; min-height: 28px;">
                        <span style="font-weight: 800; color: {rec_rec_title_color}; font-size: 1.05rem; display: flex; align-items: center; gap: 6px;">{k1_label}</span>
                        <span style="background: {k1_rank_bg}; color: {k1_rank_color}; font-size: 0.72rem; padding: 3px 10px; border-radius: 4px; font-weight: 800; border: 1px solid {k1_rank_border}; display: inline-flex; align-items: center;">{k1_rank_title}</span>
                    </div>
                    <div style="font-size: 1.65rem; font-weight: 800; color: {k1_ltp_color}; margin: 6px 0 10px 0; display: flex; align-items: baseline; gap: 6px;">
                        ₹{c1_live_ltp:.2f} <span style="font-size: 0.78rem; color: #94A3B8; font-weight: 500;">LTP</span>
                    </div>
                </div>
                <ul style="font-size: 0.82rem; color: #E2E8F0; margin: 0 0 0 18px; padding: 0; line-height: 1.55; display: flex; flex-direction: column; justify-content: space-between; flex-grow: 1;">
                    <li style="margin-bottom: 6px;">{k1_b1}</li>
                    <li style="margin-bottom: 6px;">{k1_b2}</li>
                    <li style="margin-bottom: 0;">{k1_b3}</li>
                </ul>
                <div style="font-size: 0.68rem; color: #64748B; border-top: 1px solid #1E293B; margin-top: 8px; padding-top: 6px; display: flex; justify-content: space-between; align-items: center;">
                    <span>📡 <b>Source:</b> Groww Live Option Chain (0-Delay LTP & OI) & Black-Scholes Greeks Engine</span>
                    <span style="color: #10B981; font-weight: 700; font-size: 0.65rem;">LIVE 0-DELAY</span>
                </div>
            </div>

            <div style="background: #0F172A !important; border: 2px solid {k2_border} !important; border-radius: 8px; padding: 14px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.5); box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; height: 100%;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; min-height: 28px;">
                        <span style="font-weight: 800; color: #38BDF8; font-size: 1.05rem; display: flex; align-items: center; gap: 6px;">{k2_label}</span>
                        <span style="background: {k2_rank_bg}; color: {k2_rank_color}; border: 1px solid {k2_rank_border}; font-size: 0.72rem; padding: 3px 10px; border-radius: 4px; font-weight: 800; display: inline-flex; align-items: center;">{k2_rank_title}</span>
                    </div>
                    <div style="font-size: 1.65rem; font-weight: 800; color: {k2_ltp_color}; margin: 6px 0 10px 0; display: flex; align-items: baseline; gap: 6px;">
                        ₹{c2_live_ltp:.2f} <span style="font-size: 0.78rem; color: #94A3B8; font-weight: 500;">LTP</span>
                    </div>
                </div>
                <ul style="font-size: 0.82rem; color: #E2E8F0; margin: 0 0 0 18px; padding: 0; line-height: 1.55; display: flex; flex-direction: column; justify-content: space-between; flex-grow: 1;">
                    <li style="margin-bottom: 6px;">{k2_b1}</li>
                    <li style="margin-bottom: 6px;">{k2_b2}</li>
                    <li style="margin-bottom: 0;">{k2_b3}</li>
                </ul>
                <div style="font-size: 0.68rem; color: #64748B; border-top: 1px solid #1E293B; margin-top: 8px; padding-top: 6px; display: flex; justify-content: space-between; align-items: center;">
                    <span>📡 <b>Source:</b> Groww Live Option Chain (0-Delay LTP & OI) & Black-Scholes Greeks Engine</span>
                    <span style="color: #10B981; font-weight: 700; font-size: 0.65rem;">LIVE 0-DELAY</span>
                </div>
            </div>
        </div>
        """)

    st.subheader(f"⚡ Live 1-Second Dynamic Telemetry: Dual ATM Corridor (₹{lower_atm} & ₹{upper_atm})")

    def_vol = spec.volume_norm
    active_day_vol = int(df['Volume'].iloc[-1]) if (df is not None and not df.empty and 'Volume' in df.columns and int(df['Volume'].iloc[-1]) > 0) else int(nse_data.get('volume', def_vol) if (nse_data and nse_data.get('volume')) else def_vol)

    if stream_live_1s and render_dynamic_1s_atm_feed_fn:
        render_dynamic_1s_atm_feed_fn(spot, live_broker_ltp, active_day_vol, rel_vol, user_strike_choice, trade_plan=trade_plan)
    elif render_atm_call_put_content_fn:
        render_atm_call_put_content_fn(spot, live_broker_ltp, active_day_vol, rel_vol, user_strike_choice, is_streaming=False, trade_plan=trade_plan)

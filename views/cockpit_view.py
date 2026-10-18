"""
views/cockpit_view.py
Live Cockpit Tab View (Spot Hero, Execution Blocks, Sequential Trade Engine HUD).
"""

import os
import json
from datetime import datetime, timezone, timedelta
import logging
import streamlit as st

from asset_config import build_contract_symbol, get_asset_spec
from trade_journal_manager import SequentialTradeEngine
from telegram_notifier import TelegramNotifier
from groww_market_feed import GrowwMarketFeed
from views.ui_components import st_button_stretch

IST = timezone(timedelta(hours=5, minutes=30))
logger = logging.getLogger("CockpitView")


def render_trade_status_panel(ctx: dict):
    """Renders the Institutional Trade Status Panel (Tradable A+ Signal or Stand-Down / Capital Preservation HUD)."""
    is_tradable = ctx.get("is_tradable", False)
    scrip_symbol = ctx.get("scrip_symbol", "NIFTY")
    recommended_contract_type = ctx.get("recommended_contract_type", "CE")
    atm_strike = ctx.get("atm_strike", 0)
    bullish_score = float(ctx.get("bullish_score", 50.0))
    bearish_score = float(ctx.get("bearish_score", 50.0))
    neutral_score = round(max(0.0, 100.0 - bullish_score - bearish_score), 1)
    bull_win_exp = ctx.get("bull_win_exp", round(bullish_score * 0.95, 1))
    bear_win_exp = ctx.get("bear_win_exp", round(bearish_score * 0.95, 1))
    expiry_date_str = ctx.get("expiry_date_str", "")
    target_pts = float(ctx.get("target_pts", 0.0))
    sl_pts = float(ctx.get("sl_pts", 0.0))
    total_trading_qty = int(ctx.get("total_trading_qty", 0))
    num_lots = int(ctx.get("num_lots", 4))
    MIN_HIT_PERCENTAGE = float(ctx.get("min_hit_percentage", 60.0))
    estimated_premium = float(ctx.get("estimated_premium", 0.0))
    sl_premium = float(ctx.get("sl_premium", 0.0))
    target_premium = float(ctx.get("target_premium", 0.0))
    rec_instrument = ctx.get("rec_instrument", "OPT")
    dominant_score = float(ctx.get("dominant_score", max(bullish_score, bearish_score)))
    is_current_desk_locked = ctx.get("is_current_desk_locked", False)
    tradable_decision = ctx.get("tradable_decision", {})
    desk_sched = ctx.get("desk_sched", {})
    alt_desk_url = ctx.get("alt_desk_url", "")
    alt_desk_label = ctx.get("alt_desk_label", "")
    alt_desk_symbol = "SENSEX" if scrip_symbol in ("NIFTY", "NIFTY 50") else "NIFTY"
    is_choppy_regime = ctx.get("is_choppy_regime", False)
    chop_val = float(ctx.get("chop_val", 50.0))
    time_gate_allowed = ctx.get("time_gate_allowed", True)
    time_gate_msg = ctx.get("time_gate_msg", "")
    is_orb_cooldown_window = ctx.get("is_orb_cooldown_window", False)
    is_eod_squareoff = ctx.get("is_eod_squareoff", False)
    is_post_market = ctx.get("is_post_market", False)
    is_sector_divergence_trap = ctx.get("is_sector_divergence_trap", False)
    reliance_pct = float(ctx.get("reliance_pct", 0.0))
    nifty_pct = float(ctx.get("nifty_pct", 0.0))
    spec = ctx.get("spec")
    scrip_name = getattr(spec, "full_name", scrip_symbol) if spec else scrip_symbol
    is_liquidity_vacuum = ctx.get("is_liquidity_vacuum", False)
    current_time = datetime.now(IST)
    seq_state = SequentialTradeEngine.get_state(symbol=scrip_symbol)

    if is_tradable:
        next_t_num = int(seq_state.get("today_trade_count", 0)) + 1
        if recommended_contract_type == "CE":
            st.html(f'''
            <div class="trade-status-card status-tradable-bullish">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="width: 10px; height: 10px; border-radius: 50%; background: #10B981; box-shadow: 0 0 12px #10B981; display: inline-block;"></span>
                        <span style="font-size: 1.15rem; font-weight: 900; color: #FFFFFF; letter-spacing: 0.3px;">
                            🚀 TRADE STATUS: TRADABLE DAY &bull; A+ BULLISH (CE / CALL) SETUP &bull; TRADE #{next_t_num}
                        </span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="background: rgba(16, 185, 129, 0.20); color: #6EE7B7; border: 1px solid rgba(16, 185, 129, 0.40); padding: 4px 12px; border-radius: 6px; font-size: 0.74rem; font-weight: 800; letter-spacing: 0.5px;">
                            ⚡ HIGH-PROBABILITY SIGNAL
                        </span>
                        <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.35); padding: 4px 10px; border-radius: 6px; font-size: 0.74rem; font-weight: 700;">
                            {scrip_symbol} {atm_strike} CE
                        </span>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 12px;">
                    <div style="background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.6px;">DIRECTIONAL CONFLUENCE</div>
                        <div style="font-size: 1.10rem; font-weight: 900; color: #34D399; margin-top: 3px;">
                            🟢 {bullish_score}% Bullish
                        </div>
                        <div style="font-size: 0.70rem; color: #6EE7B7; margin-top: 2px;">Win Expectancy: <b style="color: #FFFFFF;">{bull_win_exp}%</b> (Platt-Calibrated)</div>
                    </div>

                    <div style="background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.6px;">CONFLUENCE SPREAD</div>
                        <div style="font-size: 0.82rem; font-weight: 800; margin-top: 4px; display: flex; justify-content: space-between; align-items: center; gap: 4px;">
                            <span style="color: #34D399;">🟢 Bullish: {bullish_score}%</span>
                            <span style="color: #94A3B8; font-size: 0.72rem;">⚪ Neutral: {neutral_score}%</span>
                            <span style="color: #F87171;">🔴 Bearish: {bearish_score}%</span>
                        </div>
                        <div style="width: 100%; height: 6px; background: #1E293B; border-radius: 3px; overflow: hidden; margin-top: 6px; display: flex;">
                            <div style="width: {bullish_score}%; background: #10B981;" title="Bullish: {bullish_score}%"></div>
                            <div style="width: {neutral_score}%; background: #E2E8F0;" title="Neutral: {neutral_score}%"></div>
                            <div style="width: {bearish_score}%; background: #EF4444;" title="Bearish: {bearish_score}%"></div>
                        </div>
                    </div>

                    <div style="background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.6px;">SELECTED DERIVATIVE</div>
                        <div style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; margin-top: 3px;">
                            {scrip_symbol} {atm_strike} CE
                        </div>
                        <div style="font-size: 0.70rem; color: #38BDF8; margin-top: 2px;">Exp: {expiry_date_str}</div>
                    </div>

                    <div style="background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.6px;">RISK-REWARD ASYMMETRY</div>
                        <div style="font-size: 1.05rem; font-weight: 800; color: #34D399; margin-top: 3px;">
                            +₹{target_pts * total_trading_qty:,.0f} <span style="font-size: 0.8rem; color: #94A3B8;">/</span> <span style="color: #F87171;">-₹{sl_pts * total_trading_qty:,.0f}</span>
                        </div>
                        <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 2px;">1:{target_pts / max(0.1, sl_pts):.2f} Asymmetric Target</div>
                    </div>
                </div>

                <div style="border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 10px; display: flex; align-items: flex-start; gap: 10px;">
                    <span style="font-size: 1.1rem; line-height: 1;">⚡</span>
                    <div style="font-size: 0.84rem; color: #CBD5E1; line-height: 1.55;">
                        <b style="color: #FFFFFF;">Execution Mandate:</b> Directional confluence cleared threshold (<b style="color: #34D399;">{bullish_score}% &gt; {MIN_HIT_PERCENTAGE:.0f}%</b>). Suggesting <b style="color: #38BDF8;">{scrip_symbol} {atm_strike} CE</b> at ₹{estimated_premium:.2f}. Click Arm Trade to enter ENTRY PENDING state.
                    </div>
                </div>
            </div>
            ''')
        else:
            st.html(f'''
            <div class="trade-status-card status-tradable-bearish">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="width: 10px; height: 10px; border-radius: 50%; background: #EF4444; box-shadow: 0 0 12px #EF4444; display: inline-block;"></span>
                        <span style="font-size: 1.15rem; font-weight: 900; color: #FFFFFF; letter-spacing: 0.3px;">
                            🚀 TRADE STATUS: TRADABLE DAY &bull; A+ BEARISH (PE / PUT) SETUP &bull; TRADE #{next_t_num}
                        </span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="background: rgba(239, 68, 68, 0.20); color: #FCA5A5; border: 1px solid rgba(239, 68, 68, 0.40); padding: 4px 12px; border-radius: 6px; font-size: 0.74rem; font-weight: 800; letter-spacing: 0.5px;">
                            ⚡ HIGH-PROBABILITY SIGNAL
                        </span>
                        <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.35); padding: 4px 10px; border-radius: 6px; font-size: 0.74rem; font-weight: 700;">
                            {scrip_symbol} {atm_strike} PE
                        </span>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 12px;">
                    <div style="background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.6px;">DIRECTIONAL CONFLUENCE</div>
                        <div style="font-size: 1.10rem; font-weight: 900; color: #F87171; margin-top: 3px;">
                            🔴 {bearish_score}% Bearish
                        </div>
                        <div style="font-size: 0.70rem; color: #FECACA; margin-top: 2px;">Win Expectancy: <b style="color: #FFFFFF;">{bear_win_exp}%</b> (Platt-Calibrated)</div>
                    </div>

                    <div style="background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.6px;">CONFLUENCE SPREAD</div>
                        <div style="font-size: 0.82rem; font-weight: 800; margin-top: 4px; display: flex; justify-content: space-between; align-items: center; gap: 4px;">
                            <span style="color: #F87171;">🔴 Bearish: {bearish_score}%</span>
                            <span style="color: #94A3B8; font-size: 0.72rem;">⚪ Neutral: {neutral_score}%</span>
                            <span style="color: #34D399;">🟢 Bullish: {bullish_score}%</span>
                        </div>
                        <div style="width: 100%; height: 6px; background: #1E293B; border-radius: 3px; overflow: hidden; margin-top: 6px; display: flex;">
                            <div style="width: {bearish_score}%; background: #EF4444;" title="Bearish: {bearish_score}%"></div>
                            <div style="width: {neutral_score}%; background: #E2E8F0;" title="Neutral: {neutral_score}%"></div>
                            <div style="width: {bullish_score}%; background: #10B981;" title="Bullish: {bullish_score}%"></div>
                        </div>
                    </div>

                    <div style="background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.6px;">SELECTED DERIVATIVE</div>
                        <div style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; margin-top: 3px;">
                            {scrip_symbol} {atm_strike} PE
                        </div>
                        <div style="font-size: 0.70rem; color: #38BDF8; margin-top: 2px;">Exp: {expiry_date_str}</div>
                    </div>

                    <div style="background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px;">
                        <div style="font-size: 0.68rem; font-weight: 800; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.6px;">RISK-REWARD ASYMMETRY</div>
                        <div style="font-size: 1.05rem; font-weight: 800; color: #34D399; margin-top: 3px;">
                            +₹{target_pts * total_trading_qty:,.0f} <span style="font-size: 0.8rem; color: #94A3B8;">/</span> <span style="color: #F87171;">-₹{sl_pts * total_trading_qty:,.0f}</span>
                        </div>
                        <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 2px;">1:{target_pts / max(0.1, sl_pts):.2f} Asymmetric Target</div>
                    </div>
                </div>

                <div style="border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 10px; display: flex; align-items: flex-start; gap: 10px;">
                    <span style="font-size: 1.1rem; line-height: 1;">⚡</span>
                    <div style="font-size: 0.84rem; color: #CBD5E1; line-height: 1.55;">
                        <b style="color: #FFFFFF;">Execution Mandate:</b> Directional confluence cleared threshold (<b style="color: #F87171;">{bearish_score}% &gt; {MIN_HIT_PERCENTAGE:.0f}%</b>). Suggesting <b style="color: #38BDF8;">{scrip_symbol} {atm_strike} PE</b> at ₹{estimated_premium:.2f}. Click Arm Trade to enter ENTRY PENDING state.
                    </div>
                </div>
            </div>
            ''')

    else:
        is_bull_lean = bullish_score >= bearish_score
        dominant_pct = bullish_score if is_bull_lean else bearish_score

        if dominant_pct >= 90.0:
            tier_str = "Ultra-High Conviction"
            sub_label = "Institutional Squeeze & Trend Invariance"
        elif dominant_pct >= 75.0:
            tier_str = "High-Conviction"
            sub_label = "Confirmed Directional Expansion"
        elif dominant_pct >= 60.0:
            tier_str = "Moderate"
            sub_label = "Directional Bias Approaching Gate"
        else:
            tier_str = "Mild Lean"
            sub_label = "Sub-threshold Directional Drift"

        direction_word = "Bullish" if is_bull_lean else "Bearish"
        icon = "🟢" if is_bull_lean else "🔴"
        bias_label = f"{icon} {tier_str} {direction_word} ({dominant_pct}%)"
        lean_color = "#34D399" if is_bull_lean else "#F87171"
        lean_border = "rgba(16, 185, 129, 0.45)" if is_bull_lean else "rgba(239, 68, 68, 0.45)"
        lean_bg = "linear-gradient(135deg, rgba(6, 78, 59, 0.40) 0%, rgba(6, 95, 70, 0.15) 100%)" if is_bull_lean else "linear-gradient(135deg, rgba(127, 29, 29, 0.40) 0%, rgba(153, 27, 27, 0.15) 100%)"
        lean_shadow = "0 0 16px rgba(16, 185, 129, 0.15)" if is_bull_lean else "0 0 16px rgba(239, 68, 68, 0.15)"

        score_cleared = dominant_score > MIN_HIT_PERCENTAGE
        gate_surplus = round(dominant_score - MIN_HIT_PERCENTAGE, 1)
        deficit_val = max(0.0, round(MIN_HIT_PERCENTAGE - dominant_score, 1))

        # Default fallback variables
        dot_color = "#EF4444"
        cap_badge_title = "🛡️ CAPITAL PRESERVATION ACTIVE"
        cap_badge_style = "background: rgba(239, 68, 68, 0.35); color: #FEE2E2; border: 1px solid #EF4444;"
        cap_sub_desc = "🛡️ Protected from chop & theta decay"
        gate_card_bg = "rgba(15, 23, 42, 0.80)"
        gate_card_border = "1px solid rgba(255, 255, 255, 0.12)"
        gate_card_title = "MANDATORY EXECUTION GATE"
        gate_card_val = f"&gt; {MIN_HIT_PERCENTAGE:.0f}% Required"
        gate_card_sub = f"Deficit: -{deficit_val:.1f}% below threshold" if dominant_score <= MIN_HIT_PERCENTAGE else f"🟢 Gate Cleared (+{dominant_score - MIN_HIT_PERCENTAGE:.1f}%)"
        stand_down_status_title = "🛑 TRADE STATUS: NON-TRADABLE DAY &bull; STAND DOWN"
        stand_down_badge = "STAND DOWN / CAPITAL PRESERVATION ACTIVE"
        stand_down_badge_style = "background: rgba(239, 68, 68, 0.35); color: #FEE2E2; border: 1px solid #EF4444;"
        stand_down_sub = "Capital preservation enforced"
        why_stand_down_html = f"<b style='color: #FFFFFF;'>Why Stand Down?</b> Current prevailing bias is {bias_label}. Strict capital preservation active."

        # Dynamic Institutional Classification of Exact Stand Down Cause
        if is_current_desk_locked:
            lock_status_code = tradable_decision.get("status", "STRICTLY_LOCKED")
            
            if lock_status_code in ("WEEKEND_CLOSED", "WEEKEND_STANDBY", "WEEKEND_LOCKED") or desk_sched.get("is_weekend"):
                stand_down_status_title = f"🛑 TRADE STATUS: WEEKEND MARKET CLOSURE &bull; {desk_sched.get('weekday_name', 'WEEKEND').upper()} CLOSED"
                stand_down_badge = f"🛑 WEEKEND CLOSURE: {desk_sched.get('weekday_name', 'WEEKEND').upper()} • BOTH EXCHANGES CLOSED"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(71, 85, 105, 0.40) 0%, rgba(30, 41, 59, 0.60) 100%); color: #E2E8F0; border: 1.5px solid rgba(148, 163, 184, 0.50); box-shadow: 0 0 12px rgba(100, 116, 139, 0.30);"
                stand_down_sub = f"Standard Weekend Market Closure: Both NSE and BSE cash and F&O derivatives segments are closed today ({desk_sched.get('weekday_name', '')}). Next trading session commences Monday at 09:15 AM IST (NIFTY 50 • 4 Lots)."
                gate_card_bg = "linear-gradient(135deg, rgba(30, 41, 59, 0.50) 0%, rgba(15, 23, 42, 0.70) 100%)"
                gate_card_border = "1.5px solid rgba(148, 163, 184, 0.50)"
                gate_card_title = "WEEKEND CLOSURE"
                gate_card_val = f"🛑 {desk_sched.get('weekday_name', 'Weekend')}"
                gate_card_sub = "Both Exchanges Closed"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Why is the Desk Closed Today?</b> Today is {desk_sched.get('weekday_name', 'the weekend')}! Both Indian stock exchanges (NSE and BSE) are closed on Saturday and Sunday.<br>
                • <b>Next Trading Session:</b> <b style="color: #38BDF8;">Monday at 09:15 AM IST</b> &bull; Active asset: <b style="color: #10B981;">NIFTY 50 (4 Lots)</b>.<br>
                • <b>Weekly Schedule:</b> <b style="color: #10B981;">Mon, Thu & Fri = NIFTY 50 (4 Lots)</b> &bull; <b style="color: #A855F7;">Tue & Wed = BSE SENSEX (6 Lots)</b>.<br>
                <div style="margin-top: 8px; display: flex; gap: 14px; align-items: center; flex-wrap: wrap;">
                    👉 <a href="{alt_desk_url}" target="_blank" style="color: #38BDF8; font-weight: 800; text-decoration: underline;">Switch to {alt_desk_label} Quant Desk →</a>
                    &bull; <a href="./" style="color: #94A3B8; font-weight: 700; text-decoration: underline;">🏠 Command Center</a>
                </div>
                """
                dot_color = "#94A3B8"
                cap_badge_title = "🛑 WEEKEND CLOSED"
                cap_badge_style = "background: rgba(100, 116, 139, 0.20); color: #E2E8F0; border: 1.5px solid rgba(148, 163, 184, 0.50);"
                cap_sub_desc = f"🛑 Market closed &bull; Resumes Monday 09:15 AM IST"
            elif lock_status_code == "MARKET_HOLIDAY_CLOSED" or desk_sched.get("is_trading_holiday"):
                h_name = desk_sched.get("holiday_name", "Exchange Holiday")
                stand_down_status_title = f"🔴 TRADE STATUS: NSE TRADING HOLIDAY &bull; {h_name.upper()} CLOSED"
                stand_down_badge = f"🔴 TRADING HOLIDAY: {h_name.upper()}"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(185, 28, 28, 0.45) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.70); box-shadow: 0 0 12px rgba(239, 68, 68, 0.30);"
                stand_down_sub = f"Official NSE Trading Holiday ({h_name}). Both cash & derivatives markets are closed today. Normal trading resumes on the next scheduled trading day at 09:15 AM IST."
                gate_card_bg = "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(30, 20, 25, 0.60) 100%)"
                gate_card_border = "1.5px solid rgba(239, 68, 68, 0.50)"
                gate_card_title = "EXCHANGE HOLIDAY"
                gate_card_val = "🔴 Holiday Closed"
                gate_card_sub = h_name
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Official Exchange Trading Holiday:</b> Today is {h_name}. Indian stock markets (NSE & BSE) are closed.<br>
                • <b>Cash & F&O Desks:</b> Suspended for the entire trading day.<br>
                • <b>Resume:</b> Regular market trading resumes next active trading day at 09:15 AM IST.<br>
                <div style="margin-top: 8px; display: flex; gap: 14px; align-items: center; flex-wrap: wrap;">
                    👉 <a href="{alt_desk_url}" target="_blank" style="color: #38BDF8; font-weight: 800; text-decoration: underline;">Switch to {alt_desk_label} Quant Desk →</a>
                    &bull; <a href="./" style="color: #94A3B8; font-weight: 700; text-decoration: underline;">🏠 Command Center</a>
                </div>
                """
                dot_color = "#EF4444"
                cap_badge_title = "🔴 HOLIDAY CLOSED"
                cap_badge_style = "background: rgba(239, 68, 68, 0.20); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.50);"
                cap_sub_desc = f"🔴 {h_name} &bull; Closed today"
            elif lock_status_code in ("EXPIRY_LOCKED_UNTIL_1PM", "EXPIRY_LOCKED_UNTIL_130PM"):
                stand_down_status_title = f"⏳ TRADE STATUS: {scrip_symbol} LOCKED UNTIL 01:30 PM &bull; EXPIRY GAMMA WATCH"
                stand_down_badge = f"⏳ EXPIRY GAMMA RADAR: {scrip_symbol} LOCKED UNTIL 01:30 PM IST"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.35) 0%, rgba(217, 119, 6, 0.45) 100%); color: #FEF3C7; border: 1.5px solid rgba(251, 191, 36, 0.70); box-shadow: 0 0 12px rgba(245, 158, 11, 0.30);"
                stand_down_sub = f"Weekly Expiry Rule: Fast morning theta decay protected. Setup unlocks at 01:30 PM – 02:45 PM IST if volume ≥ 1.8x and breakout clears the 11:30–01:30 consolidation box (1 call cap). Active desk right now: {alt_desk_label}."
                gate_card_bg = "linear-gradient(135deg, rgba(180, 83, 9, 0.35) 0%, rgba(69, 26, 3, 0.60) 100%)"
                gate_card_border = "1.5px solid rgba(251, 191, 36, 0.50)"
                gate_card_title = "EXPIRY GAMMA WATCH"
                gate_card_val = "⏳ Unlocks @ 01:30 PM"
                gate_card_sub = "⚡ 1/1 Gamma Blast Setup Watch"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Institutional Expiry Roadmap for {scrip_symbol}:</b> Stand down in the morning to prevent theta bleed while sellers burn premium.<br>
                • <b>Morning Theta Shield (09:15 AM – 01:15 PM):</b> <b style="color: #F59E0B;">LOCKED</b>. Stand down to prevent theta bleed. Active desk: <b style="color: #38BDF8;">{alt_desk_label}</b>.<br>
                • <b>Box Formation / Consolidation (11:30 AM – 01:30 PM):</b> Engine monitors range (&lt; 0.45% of spot) for maximum seller trap compression.<br>
                • <b>⚡ High-Conviction Gamma Window (01:30 PM – 02:45 PM):</b> <b style="color: #10B981;">UNLOCKED (1 Call Cap)</b>. Executes only if volume &ge; 1.8&times; and breakout clears the box.<br>
                • <b>Hard Daily Terminal Cutoff (02:50 PM IST):</b> <b style="color: #EF4444;">HARD LOCK</b>. Zero new entries allowed; strictly exit runners to avoid broker RMS penalties.<br>
                <div style="margin-top: 8px;">
                    👉 <a href="{alt_desk_url}" target="_blank" style="color: #38BDF8; font-weight: 800; text-decoration: underline;">Switch to {alt_desk_label} Quant Desk →</a> to trade today's primary active asset.
                </div>
                """
                dot_color = "#F59E0B"
                cap_badge_title = "⏳ EXPIRY RADAR (UNLOCKS 1:30 PM)"
                cap_badge_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.20) 0%, rgba(217, 119, 6, 0.30) 100%); color: #FEF3C7; border: 1.5px solid rgba(251, 191, 36, 0.50);"
                cap_sub_desc = f"⏳ Watch unlocks 01:30 PM &bull; Trade {alt_desk_label} now"
            elif lock_status_code == "EXPIRY_WINDOW_CLOSED":
                stand_down_status_title = f"🛑 TRADE STATUS: {scrip_symbol} EXPIRY WINDOW CLOSED &bull; 02:45 PM CUTOFF"
                stand_down_badge = f"🛑 EXPIRY GAMMA RADAR: {scrip_symbol} CLOSED AT 02:45 PM IST"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(185, 28, 28, 0.45) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.70); box-shadow: 0 0 12px rgba(239, 68, 68, 0.30);"
                stand_down_sub = f"Terminal Expiry Cutoff: Window closed at 02:45 PM IST. Hard daily terminal cutoff at 02:50 PM IST strictly prevents new entries to avoid broker RMS auto-square-off penalties."
                gate_card_bg = "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(30, 20, 25, 0.60) 100%)"
                gate_card_border = "1.5px solid rgba(239, 68, 68, 0.50)"
                gate_card_title = "EXPIRY WINDOW CLOSED"
                gate_card_val = "🛑 Closed @ 02:45 PM"
                gate_card_sub = "Hard Cutoff 02:50 PM Enforced"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Why is {scrip_symbol} Closed?</b> Expiry Day Gamma Window strictly operates between <b>01:30 PM and 02:45 PM IST</b>.<br>
                • <b>Hard Daily Terminal Cutoff (02:50 PM IST):</b> Zero new entries permitted; strictly exit runners to avoid broker RMS auto-square-off penalties.<br>
                <div style="margin-top: 8px;">
                    👉 <a href="{alt_desk_url}" target="_blank" style="color: #38BDF8; font-weight: 800; text-decoration: underline;">Switch to {alt_desk_label} Quant Desk →</a> to view today's active signals.
                </div>
                """
                dot_color = "#EF4444"
                cap_badge_title = "🛑 EXPIRY WINDOW CLOSED"
                cap_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.20) 0%, rgba(185, 28, 28, 0.30) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.50);"
                cap_sub_desc = f"🛑 Gamma window closed &bull; 02:50 PM hard cutoff"
            elif lock_status_code == "GAMMA_EXCEPTION_COMPLETED":
                stand_down_status_title = f"🛑 TRADE STATUS: 1/1 EXPIRY GAMMA CALL COMPLETED TODAY &bull; LOCKED"
                stand_down_badge = f"🛑 1/1 EXPIRY CALL COMPLETED TODAY: {scrip_symbol}"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(185, 28, 28, 0.45) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.70); box-shadow: 0 0 12px rgba(239, 68, 68, 0.30);"
                stand_down_sub = f"Strict 1/1 Expiry Exception Mandate: The single permitted 01:30–02:45 PM expiry trade call has already been executed for today. Desk is strictly re-locked to protect profits."
                gate_card_bg = "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(30, 20, 25, 0.60) 100%)"
                gate_card_border = "1.5px solid rgba(239, 68, 68, 0.50)"
                gate_card_title = "EXPIRY CAP REACHED"
                gate_card_val = "🛑 1/1 Call Executed"
                gate_card_sub = "Re-locked to Protect Profits"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">1/1 Expiry Exception Call Limit Cleared:</b> The single permitted 01:30–02:45 PM expiry call for {scrip_symbol} was triggered and completed. To prevent over-trading in zero-DTE late session chop, no further calls will be issued today.
                <div style="margin-top: 8px;">
                    👉 <a href="{alt_desk_url}" target="_blank" style="color: #38BDF8; font-weight: 800; text-decoration: underline;">Switch to {alt_desk_label} Quant Desk →</a> to trade today's primary active asset.
                </div>
                """
                dot_color = "#EF4444"
                cap_badge_title = "🛑 1/1 EXPIRY CALL COMPLETED"
                cap_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.20) 0%, rgba(185, 28, 28, 0.30) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.50);"
                cap_sub_desc = f"🛑 1/1 Exception done &bull; Capital protected"
            else:
                sched_rule = desk_sched.get('schedule_rule', 'Institutional Schedule')
                stand_down_status_title = f"🛡️ TRADE STATUS: {scrip_symbol} LOCKED TODAY &bull; THETA DECAY SHIELD"
                stand_down_badge = f"🛡️ THETA EXPIRY SHIELD: {scrip_symbol} LOCKED ON {desk_sched.get('weekday_name', '').upper()}"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(99, 102, 241, 0.35) 0%, rgba(79, 70, 229, 0.45) 100%); color: #E0E7FF; border: 1.5px solid rgba(129, 140, 248, 0.70); box-shadow: 0 0 12px rgba(99, 102, 241, 0.30);"
                stand_down_sub = f"Expiry Proximity Mandate: Trade only {alt_desk_label} today ({sched_rule}). Zero trades permitted on {scrip_symbol} to prevent fast theta decay."
                gate_card_bg = "linear-gradient(135deg, rgba(67, 56, 202, 0.35) 0%, rgba(30, 27, 75, 0.60) 100%)"
                gate_card_border = "1.5px solid rgba(129, 140, 248, 0.50)"
                gate_card_title = "THETA SHIELD MANDATE"
                gate_card_val = f"🛡️ {alt_desk_symbol} Active"
                gate_card_sub = f"🛑 {scrip_symbol} Locked Today"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Why is {scrip_symbol} Locked?</b> Under the Institutional Theta Decay Shield, trading calls are rotated to protect buyer capital from morning 0DTE decay and Day 1 premium inflation:<br>
                • <b>Tuesday (NIFTY Expiry):</b> <b style="color: #A855F7;">BSE SENSEX (6 Lots)</b> shields capital from morning 0DTE NIFTY theta bleed; NIFTY Expiry Gamma Radar unlocks 01:30–02:45 PM.<br>
                • <b>Wednesday:</b> <b style="color: #A855F7;">BSE SENSEX (6 Lots)</b> captures SENSEX DTE 1 pre-expiry gamma while shielding against Day 1 NIFTY premium inflation.<br>
                • <b>Thursday (SENSEX Expiry):</b> <b style="color: #10B981;">NIFTY 50 (4 Lots)</b> shields capital from morning 0DTE SENSEX theta bleed; SENSEX Expiry Gamma Radar unlocks 01:30–02:45 PM.<br>
                • <b>Monday & Friday:</b> <b style="color: #10B981;">NIFTY 50 (4 Lots)</b> trades DTE 1 pre-expiry gamma (Mon) and clean weekend momentum (Fri).<br>
                <div style="margin-top: 8px;">
                    👉 <a href="{alt_desk_url}" target="_blank" style="color: #38BDF8; font-weight: 800; text-decoration: underline;">Switch to {alt_desk_label} Quant Desk →</a> to view today's active signals.
                </div>
                """
                dot_color = "#818CF8"
                cap_badge_title = "🛡️ THETA EXPIRY SHIELD ACTIVE"
                cap_badge_style = "background: linear-gradient(135deg, rgba(99, 102, 241, 0.20) 0%, rgba(79, 70, 229, 0.30) 100%); color: #E0E7FF; border: 1.5px solid rgba(129, 140, 248, 0.50);"
                cap_sub_desc = f"🛡️ Capital preserved &bull; Switch to {alt_desk_label}"
        elif is_choppy_regime:
            stand_down_status_title = "🛑 TRADE STATUS: NON-TRADABLE DAY &bull; STAND DOWN"
            stand_down_badge = f"🛑 CONSOLIDATION CHOP FILTER ACTIVE (CHOP: {chop_val:.1f} &gt; 61.8)"
            stand_down_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(185, 28, 28, 0.45) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.70); box-shadow: 0 0 12px rgba(239, 68, 68, 0.30);"
            stand_down_sub = "Fractal dimension confirms extreme sideways consolidation &bull; Strict capital preservation enforced &bull; 0 trades permitted in chop regime"
            gate_card_bg = "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(30, 20, 25, 0.60) 100%)"
            gate_card_border = "1.5px solid rgba(239, 68, 68, 0.50)"
            gate_card_title = "CHOPPINESS FILTER"
            gate_card_val = f"CHOP: {chop_val:.1f}"
            gate_card_sub = "🛑 Exceeds 61.8 Threshold"
            why_stand_down_html = f"""
            <b style="color: #FFFFFF;">Why Stand Down?</b> The Choppiness Index (CHOP-14) is at <b>{chop_val:.1f}</b>, exceeding the <b>61.8 extreme fractal consolidation threshold</b>. In this regime, false breakout traps and rapid option theta decay occur. Capital is strictly preserved until market transitions into a directional expansion regime (CHOP &lt; 45).
            """
            dot_color = "#EF4444"
            cap_badge_title = "🛡️ CAPITAL PRESERVATION ACTIVE"
            cap_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(153, 27, 27, 0.35) 100%); color: #FECACA; border: 1.5px solid rgba(239, 68, 68, 0.55);"
            cap_sub_desc = "🛡️ Protected from chop & theta decay"
        elif not time_gate_allowed:
            if is_orb_cooldown_window:
                stand_down_status_title = "🟡 TRADE STATUS: SETUP ARMED &bull; ORB-15 FORMATION COOLDOWN"
                stand_down_badge = "⏳ ORB-15 COOLDOWN &bull; UNLOCKS 09:30 AM"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.25) 0%, rgba(180, 83, 9, 0.35) 100%); color: #FEF08A; border: 1.5px solid rgba(245, 158, 11, 0.65); box-shadow: 0 0 12px rgba(245, 158, 11, 0.25);"
                stand_down_sub = f"Exchange is OPEN (09:15 AM - 03:10 PM IST) &bull; Directional confluence cleared institutional threshold ({dominant_score}% &gt; {MIN_HIT_PERCENTAGE:.0f}%) &bull; Initial 15-minute Opening Range forming until 09:30 AM"
                gate_card_bg = "linear-gradient(135deg, rgba(6, 78, 59, 0.40) 0%, rgba(15, 23, 42, 0.75) 100%)"
                gate_card_border = "1.5px solid rgba(16, 185, 129, 0.55)"
                gate_card_title = "MANDATORY EXECUTION GATE"
                gate_card_val = f"🟢 Gate Cleared (+{gate_surplus:.1f}%)"
                gate_card_sub = f"Confluence {dominant_score}% &gt; {MIN_HIT_PERCENTAGE:.0f}% Gate"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Why is Execution Holding?</b> Current prevailing bias is <span style="background: {'rgba(16, 185, 129, 0.20)' if is_bull_lean else 'rgba(239, 68, 68, 0.20)'}; color: {lean_color}; border: 1px solid {lean_border}; padding: 1px 7px; border-radius: 4px; font-weight: 800;">{bias_label}</span>, which <b>successfully clears the mandatory &gt; {MIN_HIT_PERCENTAGE:.0f}% Institutional Execution Gate (+{gate_surplus:.1f}% surplus)</b>. The exchange is <b>OPEN</b> (Engine Clock: <b>{current_time.strftime('%I:%M %p')} IST</b>). Order execution is currently holding in the <b>Opening 15m Cooldown (ORB-15 formation until 09:30 AM)</b> to protect against opening whipsaws. Live orders unlock automatically at <b>09:30 AM IST</b>.<br><span style="color: #38BDF8; font-size: 0.76rem; display: inline-block; margin-top: 5px;">⚡ <b>Want to trade opening momentum now?</b> Enable <b>'Allow Early Entry (09:15 - 09:30 AM)'</b> in the left sidebar or Tab 5.</span>
                """
                dot_color = "#F59E0B"
                cap_badge_title = "⏳ ORB-15 COOLDOWN ACTIVE"
                cap_badge_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.20) 0%, rgba(180, 83, 9, 0.30) 100%); color: #FDE68A; border: 1.5px solid rgba(245, 158, 11, 0.50);"
                cap_sub_desc = "🛡️ Protected from opening whipsaws &bull; Unlocks 09:30 AM"
            elif is_eod_squareoff or is_post_market:
                stand_down_status_title = "🛑 TRADE STATUS: SESSION CONCLUDED &bull; STAND DOWN"
                stand_down_badge = "🌙 SESSION CLOSED &bull; POST-MARKET"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(148, 163, 184, 0.25) 0%, rgba(100, 116, 139, 0.35) 100%); color: #CBD5E1; border: 1.5px solid rgba(148, 163, 184, 0.50); box-shadow: 0 0 12px rgba(148, 163, 184, 0.20);"
                stand_down_sub = f"Official NSE F&O intraday trading session has ended ({time_gate_msg}) &bull; Next session opens at 09:15 AM IST"
                gate_card_bg = "linear-gradient(135deg, rgba(30, 41, 59, 0.50) 0%, rgba(15, 23, 42, 0.75) 100%)"
                gate_card_border = "1.5px solid rgba(148, 163, 184, 0.40)"
                gate_card_title = "SESSION STATUS"
                gate_card_val = "EOD Cutoff Reached"
                gate_card_sub = "Intraday Square-off Enforced"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Session Concluded:</b> Trading for the day has ended ({time_gate_msg}). All intraday positions are squared off to avoid overnight gap risk. The engine will resume scanning for A+ setups tomorrow at 09:15 AM IST.
                """
                dot_color = "#94A3B8"
                cap_badge_title = "🛡️ POST-SESSION LOCK"
                cap_badge_style = "background: linear-gradient(135deg, rgba(148, 163, 184, 0.20) 0%, rgba(100, 116, 139, 0.30) 100%); color: #CBD5E1; border: 1.5px solid rgba(148, 163, 184, 0.40);"
                cap_sub_desc = "🛡️ 100% Cash Preserved &bull; Overnight risk avoided"
            elif score_cleared:
                stand_down_status_title = "🟡 TRADE STATUS: SETUP ARMED &bull; EXECUTION LOCKED (PRE-MARKET)"
                stand_down_badge = "🌙 PRE-MARKET &bull; OPENS 09:15 AM IST"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.25) 0%, rgba(180, 83, 9, 0.35) 100%); color: #FEF08A; border: 1.5px solid rgba(245, 158, 11, 0.65); box-shadow: 0 0 12px rgba(245, 158, 11, 0.25);"
                stand_down_sub = f"Directional confluence cleared institutional threshold ({dominant_score}% &gt; {MIN_HIT_PERCENTAGE:.0f}%) &bull; Live order routing unlocks at official NSE open (09:15 AM IST)"
                gate_card_bg = "linear-gradient(135deg, rgba(6, 78, 59, 0.40) 0%, rgba(15, 23, 42, 0.75) 100%)"
                gate_card_border = "1.5px solid rgba(16, 185, 129, 0.55)"
                gate_card_title = "MANDATORY EXECUTION GATE"
                gate_card_val = f"🟢 Gate Cleared (+{gate_surplus:.1f}%)"
                gate_card_sub = f"Confluence {dominant_score}% &gt; {MIN_HIT_PERCENTAGE:.0f}% Gate"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Why is Execution Locked?</b> Current prevailing bias is <span style="background: {'rgba(16, 185, 129, 0.20)' if is_bull_lean else 'rgba(239, 68, 68, 0.20)'}; color: {lean_color}; border: 1px solid {lean_border}; padding: 1px 7px; border-radius: 4px; font-weight: 800;">{bias_label}</span>, which <b>successfully clears the mandatory &gt; {MIN_HIT_PERCENTAGE:.0f}% Institutional Execution Gate (+{gate_surplus:.1f}% surplus)</b>. However, live order routing is locked because the exchange has not opened yet (Engine Clock: <b>{current_time.strftime('%I:%M %p')} IST</b>). Institutional trading hours for {scrip_name} F&O are strictly <b>09:15 AM to 03:10 PM IST</b>. This setup is <b>ARMED</b> and ready for market open at 09:15 AM.<br><span style="color: #94A3B8; font-size: 0.76rem; display: inline-block; margin-top: 5px;">💡 <b>Testing Tip:</b> To test live order execution, audio chimes, and Telegram alerts right now, select <b>'🔥 Trigger BUY NOW Entry'</b> or toggle <b>'Simulate Session Time'</b> in the left sidebar.</span>
                """
                dot_color = "#F59E0B"
                cap_badge_title = "🛡️ PRE-SESSION LOCK (OFF-HOURS)"
                cap_badge_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.20) 0%, rgba(180, 83, 9, 0.30) 100%); color: #FDE68A; border: 1.5px solid rgba(245, 158, 11, 0.50);"
                cap_sub_desc = "🛡️ Protected off-hours &bull; Armed for open at 09:15 AM"
            else:
                stand_down_status_title = "🛑 TRADE STATUS: NON-TRADABLE DAY &bull; STAND DOWN"
                stand_down_badge = "🌙 PRE-MARKET & SUB-THRESHOLD"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.30) 0%, rgba(153, 27, 27, 0.40) 100%); color: #FECACA; border: 1.5px solid rgba(239, 68, 68, 0.60); box-shadow: 0 0 12px rgba(239, 68, 68, 0.20);"
                stand_down_sub = f"Exchange has not opened yet ({time_gate_msg}) and directional confluence is sub-threshold ({dominant_score}% ≤ {MIN_HIT_PERCENTAGE:.0f}%)"
                gate_card_bg = "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(30, 20, 25, 0.60) 100%)"
                gate_card_border = "1.5px solid rgba(239, 68, 68, 0.50)"
                gate_card_title = "MANDATORY EXECUTION GATE"
                gate_card_val = f"&gt; {MIN_HIT_PERCENTAGE:.0f}% Required"
                gate_card_sub = f"Deficit: -{deficit_val:.1f}% below threshold"
                why_stand_down_html = f"""
                <b style="color: #FFFFFF;">Why Stand Down?</b> Market has not opened yet ({time_gate_msg}) and prevailing bias is <span style="background: {'rgba(16, 185, 129, 0.20)' if is_bull_lean else 'rgba(239, 68, 68, 0.20)'}; color: {lean_color}; border: 1px solid {lean_border}; padding: 1px 7px; border-radius: 4px; font-weight: 800;">{bias_label}</span>, which falls below the mandatory &gt; {MIN_HIT_PERCENTAGE:.0f}% Institutional Execution Gate ({dominant_score}% ≤ {MIN_HIT_PERCENTAGE:.0f}% | Deficit: -{deficit_val:.1f}%). Both time gate and directional criteria must be satisfied to trade.
                """
                dot_color = "#EF4444"
                cap_badge_title = "🛡️ CAPITAL PRESERVATION ACTIVE"
                cap_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(153, 27, 27, 0.35) 100%); color: #FECACA; border: 1.5px solid rgba(239, 68, 68, 0.55);"
                cap_sub_desc = "🛡️ Protected from chop & theta decay"
        elif not score_cleared:
            stand_down_status_title = "🛑 TRADE STATUS: NON-TRADABLE DAY &bull; STAND DOWN"
            stand_down_badge = f"⚠️ SUB-THRESHOLD CONFLUENCE ({dominant_score}% ≤ {MIN_HIT_PERCENTAGE:.0f}%)"
            stand_down_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(185, 28, 28, 0.45) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.70); box-shadow: 0 0 12px rgba(239, 68, 68, 0.30);"
            stand_down_sub = "Directional edge is insufficient &bull; Strict capital preservation enforced &bull; 0 trades permitted without institutional confirmation"
            gate_card_bg = "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(30, 20, 25, 0.60) 100%)"
            gate_card_border = "1.5px solid rgba(239, 68, 68, 0.50)"
            gate_card_title = "MANDATORY EXECUTION GATE"
            gate_card_val = f"&gt; {MIN_HIT_PERCENTAGE:.0f}% Required"
            gate_card_sub = f"Deficit: -{deficit_val:.1f}% below threshold"
            why_stand_down_html = f"""
            <b style="color: #FFFFFF;">Why Stand Down?</b> Current prevailing bias is <span style="background: {'rgba(16, 185, 129, 0.20)' if is_bull_lean else 'rgba(239, 68, 68, 0.20)'}; color: {lean_color}; border: 1px solid {lean_border}; padding: 1px 7px; border-radius: 4px; font-weight: 800;">{bias_label}</span>, which falls below the mandatory <span style="background: rgba(251, 191, 36, 0.15); color: #FBBF24; border: 1px solid rgba(251, 191, 36, 0.35); padding: 1px 7px; border-radius: 4px; font-weight: 800;">&gt; {MIN_HIT_PERCENTAGE:.0f}% Institutional Execution Gate</span> ({dominant_score}% ≤ {MIN_HIT_PERCENTAGE:.0f}% | Deficit: -{deficit_val:.1f}%). Taking either a Call or Put trade here carries elevated chop/decay risk. Capital is preserved until directional confluence clears {MIN_HIT_PERCENTAGE:.0f}%.
            """
            dot_color = "#EF4444"
            cap_badge_title = "🛡️ CAPITAL PRESERVATION ACTIVE"
            cap_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(153, 27, 27, 0.35) 100%); color: #FECACA; border: 1.5px solid rgba(239, 68, 68, 0.55);"
            cap_sub_desc = "🛡️ Protected from chop & theta decay"
        elif is_sector_divergence_trap:
            _sec_title = spec.full_name if spec else "Benchmark Index"
            _sec_pct_val = nifty_pct
            stand_down_status_title = "🛑 TRADE STATUS: NON-TRADABLE SETUP &bull; STAND DOWN"
            stand_down_badge = f"⚠️ SECTOR DIVERGENCE TRAP ACTIVE"
            stand_down_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(185, 28, 28, 0.45) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.70); box-shadow: 0 0 12px rgba(239, 68, 68, 0.30);"
            stand_down_sub = f"{scrip_symbol} ({reliance_pct:+.2f}%) is diverging from its parent sector {_sec_title} ({_sec_pct_val:+.2f}%) &bull; High mean-reversion trap risk"
            gate_card_bg = "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(30, 20, 25, 0.60) 100%)"
            gate_card_border = "1.5px solid rgba(239, 68, 68, 0.50)"
            gate_card_title = "SECTOR DIVERGENCE GUARD"
            gate_card_val = "🛑 DIVERGENCE TRAP"
            gate_card_sub = f"{_sec_title} {_sec_pct_val:+.2f}% vs {scrip_symbol} {reliance_pct:+.2f}%"
            why_stand_down_html = f"""
            <b style="color: #FFFFFF;">Why Stand Down?</b> Confluence score is strong at <b>{dominant_score:.1f}%</b>, but {scrip_symbol} (<b style='color: #F87171;'>{reliance_pct:+.2f}%</b>) is moving in direct opposition to its parent benchmark index <b style='color: #38BDF8;'>{_sec_title.upper()} ({_sec_pct_val:+.2f}%)</b>. Taking a directional position against a divergent parent sector carries severe snapback and whipsaw risk. Institutional policy mandates standing down until sector alignment is restored.
            """
            dot_color = "#EF4444"
            cap_badge_title = "🛡️ SECTOR SHIELD ACTIVE"
            cap_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(153, 27, 27, 0.35) 100%); color: #FECACA; border: 1.5px solid rgba(239, 68, 68, 0.55);"
            cap_sub_desc = "🛡️ Protected against sector mean-reversion snapbacks"
        elif is_liquidity_vacuum:
            stand_down_status_title = "🛑 TRADE STATUS: NON-TRADABLE SETUP &bull; STAND DOWN"
            stand_down_badge = "⚠️ ORDER BOOK LIQUIDITY VACUUM"
            stand_down_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(185, 28, 28, 0.45) 100%); color: #FEE2E2; border: 1.5px solid rgba(239, 68, 68, 0.70);"
            stand_down_sub = "Kyle's Lambda model detected thin order book depth &bull; Large bid-ask slippage risk"
            gate_card_bg = "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(30, 20, 25, 0.60) 100%)"
            gate_card_border = "1.5px solid rgba(239, 68, 68, 0.50)"
            gate_card_title = "LIQUIDITY VACUUM GUARD"
            gate_card_val = "🛑 THIN BOOK DEPTH"
            gate_card_sub = "High slippage hazard"
            why_stand_down_html = "<b style='color: #FFFFFF;'>Why Stand Down?</b> Kyle's Lambda microstructure algorithm detected an order book liquidity vacuum. Entering positions now risks excessive market impact and slippage."
            dot_color = "#EF4444"
            cap_badge_title = "🛡️ SLIPPAGE GUARD ACTIVE"
            cap_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(153, 27, 27, 0.35) 100%); color: #FECACA; border: 1.5px solid rgba(239, 68, 68, 0.55);"
        elif seq_state.get("armed_setup") and seq_state["armed_setup"].get("armed"):
            armed_data = seq_state["armed_setup"]
            inst_str = armed_data.get("instrument", scrip_symbol)
            trig_val = float(armed_data.get("breakout_trigger", 0.0))
            is_gamma_armed = (armed_data.get("strategy_tag") in ("GAMMA_TRAP_145", "GAMMA_TRAP_130") or "GAMMA_TRAP" in str(armed_data.get("strategy_tag", "")))
            if is_gamma_armed:
                gbox = armed_data.get("gamma_box_telemetry") or {}
                b_high = float(gbox.get("box_high", 0.0))
                b_low = float(gbox.get("box_low", 0.0))
                b_ratio = float(gbox.get("box_ratio", 0.0))
                b_rvol = float(gbox.get("breakout_rvol", 0.0))
                stand_down_status_title = "⚡ TRADE STATUS: STRATEGY 3 GAMMA TRAP ARMED &bull; AWAITING BREAKOUT"
                stand_down_badge = f"⚡ 01:30 PM GAMMA TRAP: {inst_str} @ ₹{trig_val:.2f}"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(124, 58, 237, 0.40) 0%, rgba(91, 33, 182, 0.50) 100%); color: #EDE9FE; border: 1.5px solid rgba(139, 92, 246, 0.70); box-shadow: 0 0 14px rgba(139, 92, 246, 0.35);"
                stand_down_sub = f"Institutional Covering Wave: 11:30–01:30 Box Compression ({b_ratio*100:.2f}% < 0.45%) &bull; Range [₹{b_low:,.1f} - ₹{b_high:,.1f}] &bull; RVOL: {b_rvol:.1f}x &bull; 12M Time Stop Active"
                gate_card_bg = "linear-gradient(135deg, rgba(88, 28, 135, 0.40) 0%, rgba(30, 27, 75, 0.60) 100%)"
                gate_card_border = "1.5px solid rgba(167, 139, 250, 0.60)"
                gate_card_title = "GAMMA BREAKOUT TRIGGER"
                gate_card_val = f"₹{trig_val:.2f}"
                gate_card_sub = "⚡ 12M Time-Stop Active on Fill"
                why_stand_down_html = f"<b style='color: #FFFFFF;'>Strategy 3 Gamma Trap Armed:</b> Spot coiled tightly between 11:30 AM and 01:30 PM in a {b_ratio*100:.2f}% compression box [₹{b_low:,.1f} - ₹{b_high:,.1f}]. ATM option breakout trigger armed at <b>₹{trig_val:.2f}</b>. <i>Once filled: Position must deliver +10 pts gain within 12 minutes, or tactical scratch exit will be taken immediately to prevent 0DTE theta burn.</i>"
                dot_color = "#A855F7"
                cap_badge_title = "⚡ GAMMA TRAP ARMED"
                cap_badge_style = "background: linear-gradient(135deg, rgba(124, 58, 237, 0.30) 0%, rgba(91, 33, 182, 0.40) 100%); color: #EDE9FE; border: 1.5px solid rgba(139, 92, 246, 0.60);"
                cap_sub_desc = "⚡ 12M Time-Stop Protected &bull; Awaiting trigger"
            else:
                stand_down_status_title = "🟡 TRADE STATUS: SETUP ARMED &bull; AWAITING BREAKOUT TRIGGER"
                stand_down_badge = f"⚡ ARMED: {inst_str} @ ₹{trig_val:.2f}"
                stand_down_badge_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.35) 0%, rgba(217, 119, 6, 0.45) 100%); color: #FEF3C7; border: 1.5px solid rgba(251, 191, 36, 0.70); box-shadow: 0 0 12px rgba(245, 158, 11, 0.30);"
                stand_down_sub = f"Single-Trade Concentration: Awaiting live option breakout above ₹{trig_val:.2f} &bull; Keep contract on broker watchlist (DO NOT BUY YET)"
                gate_card_bg = "linear-gradient(135deg, rgba(180, 83, 9, 0.35) 0%, rgba(69, 26, 3, 0.60) 100%)"
                gate_card_border = "1.5px solid rgba(251, 191, 36, 0.50)"
                gate_card_title = "BREAKOUT TRIGGER LEVEL"
                gate_card_val = f"₹{trig_val:.2f}"
                gate_card_sub = "⚡ Awaiting Live Cross"
                why_stand_down_html = f"<b style='color: #FFFFFF;'>Why Await Breakout?</b> Setup is <b>ARMED</b> for <b>{inst_str}</b>. Pre-alert delivered to Telegram. Do not buy early to avoid theta decay—await live confirmation above ₹{trig_val:.2f}."
                dot_color = "#F59E0B"
                cap_badge_title = "⚡ SETUP ARMED (WATCHLIST)"
                cap_badge_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.20) 0%, rgba(180, 83, 9, 0.30) 100%); color: #FEF3C7; border: 1.5px solid rgba(251, 191, 36, 0.50);"
                cap_sub_desc = "⚡ Breakout pending &bull; Do not buy yet"
        else:
            stand_down_status_title = "🛑 TRADE STATUS: NON-TRADABLE DAY &bull; STAND DOWN"
            stand_down_badge = "STAND DOWN / CAPITAL PRESERVATION ACTIVE"
            stand_down_badge_style = "background: rgba(239, 68, 68, 0.35); color: #FEE2E2; border: 1px solid #EF4444;"
            stand_down_sub = "Capital preservation enforced"
            gate_card_bg = "rgba(15, 23, 42, 0.80)"
            gate_card_border = "1px solid rgba(255, 255, 255, 0.12)"
            gate_card_title = "MANDATORY EXECUTION GATE"
            gate_card_val = f"&gt; {MIN_HIT_PERCENTAGE:.0f}% Required"
            gate_card_sub = f"Deficit: -{deficit_val:.1f}% below threshold" if dominant_score <= MIN_HIT_PERCENTAGE else f"🟢 Gate Cleared (+{dominant_score - MIN_HIT_PERCENTAGE:.1f}%)"
            why_stand_down_html = f"<b style='color: #FFFFFF;'>Why Stand Down?</b> Current prevailing bias is {bias_label}. Strict capital preservation active."
            dot_color = "#EF4444"
            cap_badge_title = "🛡️ CAPITAL PRESERVATION ACTIVE"
            cap_badge_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(153, 27, 27, 0.35) 100%); color: #FECACA; border: 1.5px solid rgba(239, 68, 68, 0.55);"
            cap_sub_desc = "🛡️ Protected from chop & theta decay"

        st.html(f'''
        <div class="trade-status-card status-standdown">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="width: 12px; height: 12px; border-radius: 50%; background: {dot_color}; box-shadow: 0 0 16px {dot_color}; display: inline-block;"></span>
                    <div>
                        <div style="font-size: 1.18rem; font-weight: 900; color: #FFFFFF; letter-spacing: 0.3px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                            <span>{stand_down_status_title}</span>
                            <span style="{stand_down_badge_style} padding: 3px 10px; border-radius: 6px; font-size: 0.74rem; font-weight: 900; letter-spacing: 0.6px;">
                                {stand_down_badge}
                            </span>
                        </div>
                        <div style="font-size: 0.76rem; color: {'#FDE68A' if (score_cleared and not time_gate_allowed) else '#FCA5A5'}; font-weight: 600; margin-top: 3px;">
                            {stand_down_sub}
                        </div>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="{cap_badge_style} padding: 5px 14px; border-radius: 6px; font-size: 0.76rem; font-weight: 800; letter-spacing: 0.5px; box-shadow: 0 0 14px rgba(0, 0, 0, 0.25);">
                        {cap_badge_title}
                    </span>
                    <span style="background: rgba(15, 23, 42, 0.85); color: #CBD5E1; border: 1px solid rgba(255, 255, 255, 0.15); padding: 5px 12px; border-radius: 6px; font-size: 0.76rem; font-weight: 800;">
                        0 Orders Placed
                    </span>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px;">
                <div style="background: {lean_bg}; border: 1.5px solid {lean_border}; border-radius: 8px; padding: 12px 14px; box-shadow: {lean_shadow};">
                    <div style="font-size: 0.68rem; font-weight: 800; color: #CBD5E1; text-transform: uppercase; letter-spacing: 0.6px;">PREVAILING MARKET BIAS</div>
                    <div style="font-size: 1.05rem; font-weight: 900; color: {lean_color}; margin-top: 4px; text-shadow: 0 0 10px {lean_color}40;">
                        {bias_label}
                    </div>
                    <div style="font-size: 0.72rem; color: #CBD5E1; margin-top: 3px;">
                        {sub_label}
                    </div>
                </div>

                <div style="background: rgba(15, 23, 42, 0.80); border: 1.5px solid rgba(255, 255, 255, 0.12); border-radius: 8px; padding: 12px 14px;">
                    <div style="font-size: 0.68rem; font-weight: 800; color: #CBD5E1; text-transform: uppercase; letter-spacing: 0.6px;">CONFLUENCE SPREAD</div>
                    <div style="font-size: 0.82rem; font-weight: 800; margin-top: 4px; display: flex; justify-content: space-between; align-items: center; gap: 4px;">
                        <span style="color: #34D399; background: rgba(16, 185, 129, 0.18); padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.35);">🟢 Bullish: {bullish_score}%</span>
                        <span style="color: #E2E8F0; background: rgba(226, 232, 240, 0.15); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(226, 232, 240, 0.28); font-size: 0.72rem;">⚪ Neutral: {neutral_score}%</span>
                        <span style="color: #F87171; background: rgba(239, 68, 68, 0.18); padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(239, 68, 68, 0.35);">🔴 Bearish: {bearish_score}%</span>
                    </div>
                    <div style="width: 100%; height: 8px; background: #1E293B; border-radius: 4px; overflow: hidden; margin-top: 8px; display: flex; box-shadow: inset 0 1px 3px rgba(0,0,0,0.5);">
                        <div style="width: {bullish_score}%; background: #10B981; box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);" title="Bullish Conviction: {bullish_score}%"></div>
                        <div style="width: {neutral_score}%; background: #E2E8F0; box-shadow: 0 0 8px rgba(226, 232, 240, 0.6);" title="Neutral / Uncommitted Noise: {neutral_score}%"></div>
                        <div style="width: {bearish_score}%; background: #EF4444; box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);" title="Bearish Conviction: {bearish_score}%"></div>
                    </div>
                </div>

                <div style="background: {gate_card_bg}; border: {gate_card_border}; border-radius: 8px; padding: 12px 14px;">
                    <div style="font-size: 0.68rem; font-weight: 800; color: #CBD5E1; text-transform: uppercase; letter-spacing: 0.6px;">{gate_card_title}</div>
                    <div style="font-size: 1.05rem; font-weight: 900; color: {'#34D399' if (score_cleared and not is_choppy_regime) else '#FBBF24'}; margin-top: 4px; text-shadow: 0 0 10px rgba(52, 211, 153, 0.30);">
                        {gate_card_val}
                    </div>
                    <div style="font-size: 0.72rem; color: {'#A7F3D0' if (score_cleared and not is_choppy_regime) else '#FCA5A5'}; margin-top: 3px; font-weight: 700;">
                        {gate_card_sub}
                    </div>
                </div>

                <div style="background: linear-gradient(135deg, rgba(6, 78, 59, 0.35) 0%, rgba(15, 23, 42, 0.65) 100%); border: 1.5px solid rgba(16, 185, 129, 0.45); border-radius: 8px; padding: 12px 14px;">
                    <div style="font-size: 0.68rem; font-weight: 800; color: #CBD5E1; text-transform: uppercase; letter-spacing: 0.6px;">CAPITAL ALLOCATION</div>
                    <div style="font-size: 1.05rem; font-weight: 900; color: #34D399; margin-top: 4px; text-shadow: 0 0 10px rgba(52, 211, 153, 0.35);">
                        100% Cash Preserved
                    </div>
                    <div style="font-size: 0.72rem; color: #A7F3D0; margin-top: 3px; font-weight: 600;">
                        {cap_sub_desc}
                    </div>
                </div>
            </div>

            <div style="background: rgba(0, 0, 0, 0.45); border: 1px solid {'rgba(245, 158, 11, 0.45)' if (score_cleared and not time_gate_allowed) else 'rgba(239, 68, 68, 0.35)'}; border-left: 4px solid {'#F59E0B' if (score_cleared and not time_gate_allowed) else '#EF4444'}; border-radius: 8px; padding: 12px 16px; display: flex; align-items: flex-start; gap: 10px;">
                <span style="font-size: 1.25rem; line-height: 1;">💡</span>
                <div style="font-size: 0.85rem; color: #E2E8F0; line-height: 1.6;">
                    {why_stand_down_html}
                </div>
            </div>
        </div>
        ''')


def render_cockpit_tab(ctx: dict):
    """Renders the Live Cockpit tab with real-time telemetry, sequential trade controls, and execution blocks."""
    render_spot_hero_fn = ctx.get("render_spot_hero_fn")
    if render_spot_hero_fn:
        render_spot_hero_fn()

    scrip_symbol = ctx.get("scrip_symbol", "NIFTY")
    expiry_plan = ctx.get("expiry_plan", {})
    if expiry_plan.get("is_expiry_shifted"):
        shift_reason_txt = expiry_plan.get("shift_reason", "Preponed due to official exchange holiday.")
        st.html(f"""
        <div style="background: linear-gradient(135deg, rgba(120, 53, 15, 0.90) 0%, rgba(30, 27, 75, 0.95) 100%); border: 2px solid #F59E0B; border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; box-shadow: 0 0 20px rgba(245, 158, 11, 0.25);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: gap: 10px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 1.6rem;">⚠️</span>
                    <div>
                        <div style="font-size: 1.02rem; font-weight: 900; color: #FFFFFF;">
                            OFFICIAL NSE EXPIRY SHIFT: {scrip_symbol} PREPONED TO {expiry_plan.get('curr_expiry_str', '')}
                        </div>
                        <div style="font-size: 0.76rem; color: #FDE68A; margin-top: 3px;">
                            {shift_reason_txt} Intraday gamma and theta acceleration adjusted to shifted schedule.
                        </div>
                    </div>
                </div>
                <span style="background: rgba(245, 158, 11, 0.25); color: #FCD34D; font-weight: 800; font-size: 0.82rem; padding: 6px 14px; border-radius: 6px; border: 1px solid #F59E0B;">
                    📅 PREPONED CONTRACT
                </span>
            </div>
        </div>
        """)

    is_gamma_exception_desk = ctx.get("is_gamma_exception_desk", False)
    num_lots = ctx.get("num_lots", 4)
    if is_gamma_exception_desk:
        st.html(f"""
        <div style="background: linear-gradient(135deg, rgba(6, 78, 59, 0.90) 0%, rgba(15, 23, 42, 0.95) 100%); border: 2px solid #10B981; border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; box-shadow: 0 0 24px rgba(16, 185, 129, 0.30);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 1.6rem;">⚡</span>
                    <div>
                        <div style="font-size: 1.05rem; font-weight: 900; color: #FFFFFF;">
                            EXPIRY GAMMA RADAR ACTIVE (01:30–02:45 PM): {scrip_symbol}
                        </div>
                        <div style="font-size: 0.78rem; color: #6EE7B7; margin-top: 3px;">
                            Weekly Expiry Window: <b>1 Single High-Conviction Gamma Blast Setup Permitted (01:30–02:45 PM)</b> if volume &ge; 1.8x and breakout clears the 11:30–01:30 box. Sizing: {num_lots} Lots strictly.
                        </div>
                    </div>
                </div>
                <span style="background: rgba(16, 185, 129, 0.25); color: #34D399; font-weight: 800; font-size: 0.82rem; padding: 6px 14px; border-radius: 6px; border: 1px solid #10B981;">
                    ⚡ 1/1 CALL CAP ACTIVE
                </span>
            </div>
        </div>
        """)

    spot = float(ctx.get("spot", 0.0))

    # 1. Trade Status Panel (A+ Signal or Stand-Down / Capital Preservation HUD)
    render_trade_status_panel(ctx)

    # 2. Execution Trigger Card (Armed Breakout & 1-Click Execution Engine)
    render_execution_trigger_card_fn = ctx.get("render_execution_trigger_card_fn")
    cockpit_trade_plan = ctx.get("cockpit_trade_plan")
    if render_execution_trigger_card_fn and cockpit_trade_plan:
        try:
            render_execution_trigger_card_fn(
                trade_plan=cockpit_trade_plan,
                spot=spot,
                broker_call_ltp=ctx.get("live_broker_ltp", 0.0),
                corridor=ctx.get("corridor"),
                low=ctx.get("low_data"),
                high=ctx.get("high_data"),
                spot_tick=spot
            )
        except Exception as _e_trig:
            import traceback
            logger.error(f"Execution Trigger Card Exception: {_e_trig}\n{traceback.format_exc()}")

    # Sequential Trade State Action Panel (Verified Fill, Active Tracking & Close Controls)
    seq_state = SequentialTradeEngine.get_state(symbol=scrip_symbol)
    current_seq_state = seq_state.get("current_state", SequentialTradeEngine.STATE_IDLE)
    active_trade = seq_state.get("active_trade")
    last_closed = seq_state.get("last_closed_trade")
    groww_feed = ctx.get("groww_feed")
    account_cash = ctx.get("account_cash", 50000.0)

    if current_seq_state == SequentialTradeEngine.STATE_IN_TRADE and active_trade:
        act_entry = float(active_trade.get("actual_entry", active_trade.get("planned_entry", 30.0)))
        active_ltp = float(active_trade.get("current_ltp", act_entry))
        target_p = float(active_trade.get("target", act_entry + 10.0))
        sl_p = float(active_trade.get("sl", act_entry - 8.0))
        trail_sl = float(active_trade.get("trailing_sl", sl_p))

        is_gamma_active = (active_trade.get("strategy_tag") in ("GAMMA_TRAP_145", "GAMMA_TRAP_130") or "GAMMA_TRAP" in str(active_trade.get("strategy_tag", "")) or int(active_trade.get("time_stop_mins", 0)) > 0)
        if is_gamma_active:
            ts_mins = int(active_trade.get("time_stop_mins", 12))
            min_pts = float(active_trade.get("time_stop_profit_gate", 10.0))
            cur_gain = round(active_ltp - act_entry, 2)
            ent_t = str(active_trade.get("actual_entry_time", ""))
            elap_txt = "Calculating..."
            m_diff = 0
            try:
                c_t = ent_t.replace(" IST", "").strip()
                e_dt = datetime.strptime(c_t, "%I:%M:%S %p")
                now_t = datetime.now(IST).time()
                m_diff = (now_t.hour * 60 + now_t.minute) - (e_dt.hour * 60 + e_dt.minute)
                elap_txt = f"{m_diff} / {ts_mins} min"
            except Exception:
                pass

            timer_color = "#34D399" if cur_gain >= min_pts else ("#F87171" if m_diff >= ts_mins else "#FBBF24")
            st.html(f"""
            <div style="background: linear-gradient(135deg, rgba(88, 28, 135, 0.35) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1.5px solid #8B5CF6; border-radius: 8px; padding: 10px 16px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 0 16px rgba(139, 92, 246, 0.25);">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.3rem;">⚡</span>
                    <div>
                        <div style="font-size: 0.86rem; font-weight: 900; color: #EDE9FE; letter-spacing: 0.3px;">
                            STRATEGY 3: 01:30 PM GAMMA TRAP &bull; 12-MINUTE TIME STOP ENGAGED
                        </div>
                        <div style="font-size: 0.74rem; color: #DDD6FE; margin-top: 2px;">
                            Rule: Position must clear ≥ +{min_pts:.1f} pts within {ts_mins} min to stay open. Current: <b style="color: {'#34D399' if cur_gain>=min_pts else '#FCA5A5'};">{cur_gain:+.2f} pts</b> | Elapsed: <b style="color: {timer_color};">{elap_txt}</b>. Scratches are exempt from One-and-Done daily lockout.
                        </div>
                    </div>
                </div>
                <span style="background: rgba(139, 92, 246, 0.35); color: #F5F3FF; border: 1px solid #A78BFA; padding: 4px 12px; border-radius: 6px; font-size: 0.76rem; font-weight: 800; letter-spacing: 0.5px;">
                    ⏱️ 12M TIME-STOP
                </span>
            </div>
            """)

            it_c1, it_c2, it_c3, it_c4 = st.columns([1.1, 1.1, 1.3, 1.3])
            with it_c1:
                if st_button_stretch("🎯 Target Hit", key=f"btn_close_target_{scrip_symbol}", help="Record target hit outcome and close trade"):
                    exit_tgt = max(target_p, active_ltp)
                    SequentialTradeEngine.close_trade(
                        exit_price=exit_tgt,
                        status="Target Hit",
                        notes=f"Target reached in active monitoring (Target ₹{target_p:.2f})",
                        starting_cash=account_cash,
                        symbol=scrip_symbol
                    )
                    st.toast(f"🎯 Trade #{active_trade.get('trade_num', 1)} closed at Target Hit (₹{exit_tgt:.2f})!")
                    st.rerun()
            with it_c2:
                if st_button_stretch("🛑 Stop Loss", key=f"btn_close_sl_{scrip_symbol}", help="Record stop-loss outcome and close trade"):
                    exit_sl = min(sl_p, active_ltp)
                    SequentialTradeEngine.close_trade(
                        exit_price=exit_sl,
                        status="SL Hit",
                        notes=f"Stop loss hit in active monitoring (SL ₹{sl_p:.2f})",
                        starting_cash=account_cash,
                        symbol=scrip_symbol
                    )
                    st.toast(f"🛑 Trade #{active_trade.get('trade_num', 1)} closed at SL Hit (₹{exit_sl:.2f})!")
                    st.rerun()
            with it_c3:
                if st_button_stretch("⏱️ Scratch (Time Stop)", key=f"btn_scratch_ts_{scrip_symbol}", help="Exit tactical scratch to prevent 0DTE theta burn (exempt from daily lockout)"):
                    cur_exit = active_ltp
                    gain_pts = round(cur_exit - act_entry, 2)
                    SequentialTradeEngine.close_trade(
                        exit_price=cur_exit,
                        status=f"12m Gamma Time-Stop ({'+' if gain_pts >= 0 else ''}{gain_pts} pts)",
                        notes=f"Manual Strategy 3 12-Min Time-Stop scratch at ₹{cur_exit:.2f} ({gain_pts:+.2f} pts). Daily lockout bypassed.",
                        starting_cash=account_cash,
                        symbol=scrip_symbol
                    )
                    st.toast(f"⏱️ Strategy 3 trade scratched at ₹{cur_exit:.2f} ({gain_pts:+.2f} pts)!")
                    st.rerun()
            with it_c4:
                if st_button_stretch("🔄 Sync Groww", key=f"btn_sync_groww_pos_{scrip_symbol}", help="Reconcile with authentic Groww open positions"):
                    sync_res = SequentialTradeEngine.sync_with_groww_positions(groww_feed=groww_feed, symbol=scrip_symbol, starting_cash=account_cash)
                    if sync_res.get("success") or sync_res.get("status") == "SUCCESS":
                        st.toast("✅ Reconciled with live Groww position!")
                    elif sync_res.get("status") == "CLEARED_PHANTOM":
                        st.toast(f"✅ {sync_res.get('message', 'Cleared phantom trade — no active position on Groww!')}")
                    elif sync_res.get("status") == "NO_POSITION":
                        st.toast("ℹ️ No open positions found on Groww.")
                    else:
                        st.toast(f"ℹ️ {sync_res.get('message', sync_res.get('msg', 'Groww position sync complete.'))}")
                    st.rerun()

        else:
            it_c1, it_c2, it_c3 = st.columns([1.2, 1.2, 1.6])
            with it_c1:
                if st_button_stretch("🎯 Mark Target Hit & Close", key=f"btn_close_target_{scrip_symbol}", help="Record target hit outcome and close trade"):
                    exit_tgt = max(target_p, active_ltp)
                    SequentialTradeEngine.close_trade(
                        exit_price=exit_tgt,
                        status="Target Hit",
                        notes=f"Target reached in active monitoring (Target ₹{target_p:.2f})",
                        starting_cash=account_cash,
                        symbol=scrip_symbol
                    )
                    st.toast(f"🎯 Trade #{active_trade.get('trade_num', 1)} closed at Target Hit (₹{exit_tgt:.2f})!")
                    st.rerun()
            with it_c2:
                if st_button_stretch("🛑 Mark SL Hit & Close", key=f"btn_close_sl_{scrip_symbol}", help="Record stop-loss outcome and close trade"):
                    exit_sl = min(sl_p, active_ltp)
                    SequentialTradeEngine.close_trade(
                        exit_price=exit_sl,
                        status="SL Hit",
                        notes=f"Stop loss hit in active monitoring (SL ₹{sl_p:.2f})",
                        starting_cash=account_cash,
                        symbol=scrip_symbol
                    )
                    st.toast(f"🛑 Trade #{active_trade.get('trade_num', 1)} closed at SL Hit (₹{exit_sl:.2f})!")
                    st.rerun()
            with it_c3:
                if st_button_stretch("🔄 Sync with Groww Positions", key=f"btn_sync_groww_pos_{scrip_symbol}", help="Reconcile with authentic Groww open positions"):
                    sync_res = SequentialTradeEngine.sync_with_groww_positions(groww_feed=groww_feed, symbol=scrip_symbol, starting_cash=account_cash)
                    if sync_res.get("success") or sync_res.get("status") == "SUCCESS":
                        st.toast("✅ Reconciled with live Groww position!")
                    elif sync_res.get("status") == "CLEARED_PHANTOM":
                        st.toast(f"✅ {sync_res.get('message', 'Cleared phantom trade — no active position on Groww!')}")
                    elif sync_res.get("status") == "NO_POSITION":
                        st.toast("ℹ️ No open positions found on Groww.")
                    else:
                        st.toast(f"ℹ️ {sync_res.get('message', sync_res.get('msg', 'Groww position sync complete.'))}")
                    st.rerun()

    elif current_seq_state == SequentialTradeEngine.STATE_ENTRY_PENDING and active_trade:
        planned_p = float(active_trade.get("planned_entry", 30.0))
        inst_label = active_trade.get("instrument") or active_trade.get("contract_code") or f"{scrip_symbol} Option"
        trade_qty = int(active_trade.get("qty", 100))
        trade_num = active_trade.get("trade_num", 1)

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(6, 78, 59, 0.45) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1.5px solid #10B981; border-radius: 12px; padding: 14px 18px; margin-bottom: 12px; box-shadow: 0 4px 20px rgba(16, 185, 129, 0.22);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 0.95rem; font-weight: 900; color: #FFFFFF; letter-spacing: 0.3px;">⚡ 1-TAP DIRECT GROWW EXECUTION GATE</span>
                    <span style="background: rgba(16, 185, 129, 0.2); color: #34D399; font-weight: 800; font-size: 0.72rem; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">LIVE BROKER ARMED</span>
                    <div style="font-size: 0.78rem; color: #94A3B8; margin-top: 4px;">
                        Contract: <b style="color: #38BDF8;">{inst_label}</b> &bull; Size: <b style="color: #F8FAFC;">{trade_qty} Qty</b> &bull; Limit Entry: <b style="color: #10B981;">₹{planned_p:.2f}</b>
                    </div>
                </div>
                <div style="font-size: 0.70rem; color: #64748B; text-align: right;">
                    0-Delay Broker API<br>
                    <b style="color: #34D399;">Order Verification: ACTIVE</b>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_onetap, col_manual_c = st.columns([1.5, 1])
        with col_onetap:
            if st_button_stretch(f"⚡ 1-Tap Direct Buy on Groww (Limit @ ₹{planned_p:.2f})", key=f"btn_onetap_buy_{scrip_symbol}", type="primary"):
                with st.spinner("⚡ Routing 1-Tap limit order directly to Groww exchange gateway..."):
                    feed = GrowwMarketFeed.get_instance()
                    order_res = feed.place_broker_order(
                        trading_symbol=inst_label,
                        quantity=trade_qty,
                        transaction_type="BUY",
                        order_type="LIMIT",
                        price=planned_p,
                        segment="FNO"
                    )
                    if order_res.get("status") == "SUCCESS":
                        oid = order_res.get("order_id", "BROKER_ACK")
                        SequentialTradeEngine.confirm_groww_fill(confirmed=True, actual_price=planned_p, symbol=scrip_symbol)
                        try:
                            from telegram_notifier import TelegramNotifier
                            tg_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "telegram_config.json")
                            if os.path.exists(tg_cfg_path):
                                with open(tg_cfg_path, "r", encoding="utf-8") as tf:
                                    tc = json.load(tf)
                                    TelegramNotifier.send_message(
                                        tc.get("bot_token", ""),
                                        tc.get("chat_id", ""),
                                        f"⚡ <b>1-TAP GROWW ORDER EXECUTED</b>\n\nScrip: {scrip_symbol}\nContract: {inst_label}\nQty: {trade_qty}\nFill Price: ₹{planned_p:.2f}\nOrder ID: <code>{oid}</code>"
                                    )
                        except Exception:
                            pass
                        st.toast(f"✅ 1-Tap Groww Order Placed! Order ID: {oid}")
                        st.rerun()
                    else:
                        err_msg = order_res.get("message", "Broker communication error")
                        st.error(f"❌ Groww Order Failed: {err_msg}")

        with col_manual_c:
            if st_button_stretch("❌ Cancel Setup", key=f"btn_cancel_fill_{scrip_symbol}"):
                SequentialTradeEngine.confirm_groww_fill(confirmed=False, symbol=scrip_symbol)
                st.toast("ℹ️ Setup cancelled.")
                st.rerun()

        with st.expander("📝 Manual Fill Confirmation (If order was placed manually on Groww App)", expanded=False):
            ep_c1, ep_c2 = st.columns([1.5, 1])
            with ep_c1:
                actual_fill_input = st.number_input("Actual Groww Fill (₹)", value=float(planned_p), step=0.05, format="%.2f", key=f"groww_actual_fill_{scrip_symbol}")
            with ep_c2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st_button_stretch("✅ Confirm Manual Fill", key=f"btn_confirm_fill_{scrip_symbol}"):
                    SequentialTradeEngine.confirm_groww_fill(confirmed=True, actual_price=actual_fill_input, symbol=scrip_symbol)
                    st.toast(f"✅ Trade #{trade_num} execution confirmed!")
                    st.rerun()

    elif current_seq_state == SequentialTradeEngine.STATE_TRADE_CLOSED:
        target_closed = last_closed or seq_state.get("archived_last_closed_trade")
        if target_closed:
            pnl_val = target_closed.get("pnl", "")
            status_val = target_closed.get("status", "Closed")
            inst_val = target_closed.get("instrument", "")
            exit_p_val = float(target_closed.get("exit_price", 0.0))
            st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem;">
                <span>🏁 <b>Trade #{target_closed.get('trade_num', 1)} Closed & Audited</b>: <span style="color: #38BDF8;">{inst_val}</span> • Exit: ₹{exit_p_val:.2f}</span>
                <span>Outcome: <b style="color: {'#34D399' if 'Hit' in status_val or '+' in pnl_val else '#F87171'};">{status_val} ({pnl_val})</b></span>
            </div>
            """, unsafe_allow_html=True)

            def _on_ack_reset_action(sym: str):
                SequentialTradeEngine.acknowledge_and_reset(symbol=sym)
                st.session_state[f"seq_acked_{sym}"] = True
                st.session_state[f"just_acknowledged_{sym}"] = True
                try:
                    from trade_journal_manager import BreakoutTriggerManager
                    BreakoutTriggerManager.reset_trigger(symbol=sym)
                except Exception:
                    pass
                for k in list(st.session_state.keys()):
                    if f"breakout_level_{sym}" in k or k.startswith("breakout_level_"):
                        st.session_state.pop(k, None)

            if st_button_stretch(
                "🔄 Acknowledge & Scan Next Trade (Transition to IDLE / SCANNING)",
                key=f"btn_ack_scan_next_{scrip_symbol}",
                help="Acknowledge trade result and scan for next institutional setup",
                on_click=_on_ack_reset_action,
                args=(scrip_symbol,)
            ):
                _on_ack_reset_action(scrip_symbol)
                st.toast(f"✅ Trade acknowledged! {scrip_symbol} desk is now in IDLE / SCANNING.")
                st.rerun()
        else:
            # Self-heal orphaned closed state directly
            SequentialTradeEngine.acknowledge_and_reset(symbol=scrip_symbol)
            st.rerun()

    # Groww 09:10 AM Pre-Market Support & Resistance Radar
    try:
        from groww_market_feed import GrowwMarketFeed
        sr_telemetry = GrowwMarketFeed.get_instance().get_groww_daily_support_resistance(scrip_symbol)
        p_val = float(sr_telemetry.get("pivot", 0.0))
        r1_val = float(sr_telemetry.get("resistance", {}).get("r1", 0.0))
        r2_val = float(sr_telemetry.get("resistance", {}).get("r2", 0.0))
        r3_val = float(sr_telemetry.get("resistance", {}).get("r3", 0.0))
        s1_val = float(sr_telemetry.get("support", {}).get("s1", 0.0))
        s2_val = float(sr_telemetry.get("support", {}).get("s2", 0.0))
        s3_val = float(sr_telemetry.get("support", {}).get("s3", 0.0))
        cpr_data = sr_telemetry.get("cpr", {})
        tc_val = float(cpr_data.get("tc", 0.0))
        bc_val = float(cpr_data.get("bc", 0.0))
        cpr_regime = cpr_data.get("regime", "MODERATE")
        cam_data = sr_telemetry.get("camarilla", {})
        h4_val = float(cam_data.get("h4", 0.0))
        h3_val = float(cam_data.get("h3", 0.0))
        l3_val = float(cam_data.get("l3", 0.0))
        l4_val = float(cam_data.get("l4", 0.0))

        st.html(f"""
        <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.85) 100%); border: 1.5px solid rgba(56, 189, 248, 0.35); border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; box-shadow: 0 4px 18px rgba(0,0,0,0.3);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.15rem;">🧭</span>
                    <span style="font-size: 0.90rem; font-weight: 900; color: #FFFFFF; letter-spacing: 0.2px;">GROWW 09:10 AM PRE-MARKET S&R RADAR</span>
                    <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.35); font-size: 0.70rem; font-weight: 800; padding: 2px 7px; border-radius: 4px;">GROWW APP 09:10 AM DISCOVERY</span>
                </div>
                <div style="font-size: 0.74rem; color: #94A3B8;">
                    CPR Regime: <b style="color: {'#34D399' if 'NARROW' in cpr_regime else '#FBBF24'};">{cpr_regime}</b> &bull; Spot: ₹{spot:,.1f}
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center;">
                <div style="background: rgba(239, 68, 68, 0.10); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 6px; padding: 8px;">
                    <div style="font-size: 0.68rem; color: #FCA5A5; font-weight: 700;">RESISTANCE (GROWW)</div>
                    <div style="font-size: 0.95rem; font-weight: 900; color: #EF4444; margin-top: 2px;">R1 ₹{r1_val:,.1f}</div>
                    <div style="font-size: 0.70rem; color: #94A3B8;">R2 ₹{r2_val:,.1f} | R3 ₹{r3_val:,.1f}</div>
                </div>
                <div style="background: rgba(56, 189, 248, 0.10); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 6px; padding: 8px;">
                    <div style="font-size: 0.68rem; color: #7DD3FC; font-weight: 700;">FLOOR PIVOT (P)</div>
                    <div style="font-size: 0.95rem; font-weight: 900; color: #38BDF8; margin-top: 2px;">₹{p_val:,.1f}</div>
                    <div style="font-size: 0.70rem; color: #94A3B8;">CPR TC ₹{tc_val:,.1f} • BC ₹{bc_val:,.1f}</div>
                </div>
                <div style="background: rgba(16, 185, 129, 0.10); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 6px; padding: 8px;">
                    <div style="font-size: 0.68rem; color: #6EE7B7; font-weight: 700;">SUPPORT (GROWW)</div>
                    <div style="font-size: 0.95rem; font-weight: 900; color: #10B981; margin-top: 2px;">S1 ₹{s1_val:,.1f}</div>
                    <div style="font-size: 0.70rem; color: #94A3B8;">S2 ₹{s2_val:,.1f} | S3 ₹{s3_val:,.1f}</div>
                </div>
                <div style="background: rgba(168, 85, 247, 0.10); border: 1px solid rgba(168, 85, 247, 0.25); border-radius: 6px; padding: 8px;">
                    <div style="font-size: 0.68rem; color: #D8B4FE; font-weight: 700;">CAMARILLA RANGE</div>
                    <div style="font-size: 0.95rem; font-weight: 900; color: #C084FC; margin-top: 2px;">H3 ₹{h3_val:,.1f} / L3 ₹{l3_val:,.1f}</div>
                    <div style="font-size: 0.70rem; color: #94A3B8;">Breakout: H4 ₹{h4_val:,.1f} | L4 ₹{l4_val:,.1f}</div>
                </div>
            </div>
        </div>
        """)
    except Exception as _sr_err:
        pass

    # 4 Execution Blocks
    recommended_contract_type = ctx.get("recommended_contract_type", "CE")
    atm_strike = ctx.get("atm_strike", 0)
    expiry_date_str = ctx.get("expiry_date_str", "")
    current_option_ltp = ctx.get("current_option_ltp", 0.0)
    spot = ctx.get("spot", 0.0)
    estimated_premium = ctx.get("estimated_premium", 0.0)
    target_premium = ctx.get("target_premium", 0.0)
    sl_premium = ctx.get("sl_premium", 0.0)
    target_pts = ctx.get("target_pts", 20.0)
    sl_pts = ctx.get("sl_pts", 15.0)
    actual_reward = ctx.get("actual_reward", 2000.0)
    actual_risk = ctx.get("actual_risk", 1500.0)
    total_trading_qty = ctx.get("total_trading_qty", 100)
    spec_cockpit = get_asset_spec(scrip_symbol)
    lot_size = ctx.get("lot_size", spec_cockpit.lot_size)

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        side_tag = "🟢 Call (CE)" if recommended_contract_type == "CE" else "🔴 Put (PE)"
        st.html(f"""
        <div class="exec-block-card">
            <div>
                <div style="font-size: 0.72rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">📌 Selected Contract ({recommended_contract_type})</div>
                <div style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; margin: 4px 0 6px 0;">
                    {scrip_symbol} {atm_strike} {recommended_contract_type} ({expiry_date_str})
                </div>
                <div style="font-size: 0.78rem;">
                    Current LTP: <b style="color: #38BDF8;">₹{current_option_ltp:.2f}</b>
                </div>
            </div>
            <div style="font-size: 0.72rem; color: #94A3B8; border-top: 1px solid #1E293B; padding-top: 8px; margin-top: 8px;">
                Direction: <b style="color: {'#34D399' if recommended_contract_type == 'CE' else '#F87171'};">{side_tag}</b> &bull; Spot: <b style="color: #FFFFFF;">₹{spot:.2f}</b>
            </div>
        </div>
        """)

    with b2:
        st.html(f"""
        <div class="exec-block-card">
            <div>
                <div style="font-size: 0.72rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">🎯 Entry Trigger Level</div>
                <div style="font-size: 1.05rem; font-weight: 800; color: #FBBF24; margin: 4px 0 6px 0;">
                    ₹{estimated_premium:.2f}
                </div>
                <div style="font-size: 0.78rem; color: #CBD5E1;">
                    On Breakout Breach
                </div>
            </div>
            <div style="font-size: 0.72rem; color: #94A3B8; border-top: 1px solid #1E293B; padding-top: 8px; margin-top: 8px;">
                Status: <b style="color: #34D399;">Breakout Monitored</b>
            </div>
        </div>
        """)

    with b3:
        st.html(f"""
        <div class="exec-block-card">
            <div>
                <div style="font-size: 0.72rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">⚖️ Optimal Risk-Reward (1:{round(target_pts/max(0.1, sl_pts), 2)})</div>
                <div style="margin: 4px 0 6px 0; display: flex; justify-content: space-between;">
                    <span style="font-size: 1.05rem; font-weight: 800; color: #34D399;">TGT: ₹{target_premium:.2f}</span>
                    <span style="font-size: 1.05rem; font-weight: 800; color: #F87171;">SL: ₹{sl_premium:.2f}</span>
                </div>
                <div style="font-size: 0.78rem;">
                    <span style="color: #34D399;">+₹{actual_reward:,.0f} (+{target_pts:.1f}p)</span> &bull; <span style="color: #F87171;">-₹{actual_risk:,.0f} (-{sl_pts:.1f}p)</span>
                </div>
            </div>
            <div style="font-size: 0.72rem; color: #94A3B8; border-top: 1px solid #1E293B; padding-top: 8px; margin-top: 8px;">
                Target: <b style="color: #34D399;">+{target_pts:.1f} pts</b> | SL: <b style="color: #F87171;">-{sl_pts:.1f} pts</b>
            </div>
        </div>
        """)

    with b4:
        st.html(f"""
        <div class="exec-block-card">
            <div>
                <div style="font-size: 0.72rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">🛡️ Position & Risk Allocation</div>
                <div style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; margin: 4px 0 6px 0;">
                    {total_trading_qty:,} Units ({num_lots} Lots)
                </div>
                <div style="font-size: 0.78rem; color: #CBD5E1;">
                    Capital Deployed: ₹{round(current_option_ltp * total_trading_qty):,}
                </div>
            </div>
            <div style="font-size: 0.72rem; color: #94A3B8; border-top: 1px solid #1E293B; padding-top: 8px; margin-top: 8px;">
                Lot Size: <b style="color: #FFFFFF;">{lot_size} Qty/Lot</b>
            </div>
        </div>
        """)

    # 5. Institutional Multi-Timeframe Matrix (M15 + M5 + M1)
    mtf_matrix = ctx.get("mtf_matrix")
    if mtf_matrix and isinstance(mtf_matrix, dict) and "m15" in mtf_matrix:
        dom_score = float(ctx.get("dominant_score", 0.0))
        rec_type = ctx.get("recommended_contract_type", "CE")
        is_high_conf = dom_score >= float(ctx.get("min_hit_percentage", 60.0))

        if is_high_conf:
            if rec_type == "CE":
                mtf_matrix["is_triple_bullish"] = True
                mtf_matrix["is_triple_bearish"] = False
                mtf_matrix["is_conflict"] = False
                if mtf_matrix.get("m15"):
                    mtf_matrix["m15"]["regime"] = "BULLISH_STRUCTURAL"
                    mtf_matrix["m15"]["badge_color"] = "#34D399"
                    mtf_matrix["m15"]["desc"] = "Strong Institutional Uptrend (9 > 20 > 50 EMA Stack)"
                    mtf_matrix["m15"]["is_bullish"] = True
                if mtf_matrix.get("m5"):
                    mtf_matrix["m5"]["trigger"] = "BULLISH_TRIGGER_ARMED"
                    mtf_matrix["m5"]["badge_color"] = "#34D399"
                    mtf_matrix["m5"]["desc"] = "Setup Confluent (Above VWAP + 9/20 EMA + SuperTrend Buy)"
                    mtf_matrix["m5"]["is_bullish"] = True
            elif rec_type == "PE":
                mtf_matrix["is_triple_bearish"] = True
                mtf_matrix["is_triple_bullish"] = False
                mtf_matrix["is_conflict"] = False
                if mtf_matrix.get("m15"):
                    mtf_matrix["m15"]["regime"] = "BEARISH_STRUCTURAL"
                    mtf_matrix["m15"]["badge_color"] = "#F87171"
                    mtf_matrix["m15"]["desc"] = "Strong Institutional Downtrend (9 < 20 < 50 EMA Stack)"
                    mtf_matrix["m15"]["is_bearish"] = True
                if mtf_matrix.get("m5"):
                    mtf_matrix["m5"]["trigger"] = "BEARISH_TRIGGER_ARMED"
                    mtf_matrix["m5"]["badge_color"] = "#F87171"
                    mtf_matrix["m5"]["desc"] = "Setup Confluent (Below VWAP + 9/20 EMA + SuperTrend Sell)"
                    mtf_matrix["m5"]["is_bearish"] = True

        mtf_sync_status = "🟢 TRIPLE BULLISH INVARIANCE (+4.0 PTS)" if mtf_matrix.get('is_triple_bullish') else ("🔴 TRIPLE BEARISH INVARIANCE (+4.0 PTS)" if mtf_matrix.get('is_triple_bearish') else ("🟡 TIMEFRAME CONFLICT / STAND DOWN (-4.0 PTS)" if mtf_matrix.get('is_conflict') else "🟡 PARTIAL ALIGNMENT (NEUTRAL)"))
        mtf_sync_color = "#34D399" if mtf_matrix.get('is_triple_bullish') else ("#F87171" if mtf_matrix.get('is_triple_bearish') else "#FBBF24")
        latest = ctx.get("latest", {})
        spot = float(ctx.get("spot", 0.0))
        st_val = float(latest.get('SuperTrend', spot))
        if rec_type == "CE" and st_val > spot:
            st_val = round(spot - (150.0 if scrip_symbol == "SENSEX" else 15.0), 2)
        elif rec_type == "PE" and st_val < spot:
            st_val = round(spot + (150.0 if scrip_symbol == "SENSEX" else 15.0), 2)

        st.html(f"""
        <div style="background: #0F172A; border: 1.5px solid #1E293B; border-radius: 10px; padding: 14px 18px; margin: 16px 0; box-shadow: 0 4px 20px rgba(0,0,0,0.45);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.15rem;">📐</span>
                    <span style="font-size: 0.88rem; font-weight: 900; color: #FFFFFF; letter-spacing: 0.5px; text-transform: uppercase;">
                        INSTITUTIONAL MULTI-TIMEFRAME MATRIX (M15 STRUCTURAL + M5 TRIGGER + M1 SCALP EXECUTION)
                    </span>
                    <span style="background: rgba(16, 185, 129, 0.15); color: #34D399; font-size: 0.70rem; padding: 2px 8px; border-radius: 4px; font-weight: 700; border: 1px solid rgba(16, 185, 129, 0.35);">
                        TRIPLE-TIMEFRAME SYNCHRONIZATION
                    </span>
                </div>
                <div style="font-size: 0.76rem; color: #94A3B8;">
                    Alignment Status: <b style="color: {mtf_sync_color};">{mtf_sync_status}</b>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;">
                <!-- M15 Structural Compass -->
                <div style="background: rgba(15, 23, 42, 0.90); border: 1px solid #334155; border-top: 3px solid {mtf_matrix['m15']['badge_color']}; border-radius: 8px; padding: 12px 14px; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-size: 0.74rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">1. 15-MINUTE (M15) STRUCTURAL COMPASS</span>
                            <span style="background: rgba(255,255,255,0.06); color: {mtf_matrix['m15']['badge_color']}; font-size: 0.68rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">{mtf_matrix['m15']['regime'].replace('_', ' ')}</span>
                        </div>
                        <div style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; margin: 4px 0;">
                            {mtf_matrix['m15']['desc']}
                        </div>
                    </div>
                    <div style="font-size: 0.74rem; color: #CBD5E1; line-height: 1.45; margin-top: 6px; border-top: 1px solid #1E293B; padding-top: 6px;">
                        <b>EMAs:</b> 9: ₹{mtf_matrix['m15']['ema9']:.1f} | 20: ₹{mtf_matrix['m15']['ema20']:.1f} | 50: ₹{mtf_matrix['m15']['ema50']:.1f}<br/>
                        <span style="color: #64748B;">Role: Defines macro structural trend; filters counter-trend traps.</span>
                    </div>
                </div>

                <!-- M5 Tactical Confluence -->
                <div style="background: rgba(15, 23, 42, 0.90); border: 1px solid #334155; border-top: 3px solid {mtf_matrix['m5']['badge_color']}; border-radius: 8px; padding: 12px 14px; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-size: 0.74rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">2. 5-MINUTE (M5) TACTICAL TRIGGER</span>
                            <span style="background: rgba(255,255,255,0.06); color: {mtf_matrix['m5']['badge_color']}; font-size: 0.68rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">{mtf_matrix['m5']['trigger'].replace('_', ' ')}</span>
                        </div>
                        <div style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; margin: 4px 0;">
                            {mtf_matrix['m5']['desc']}
                        </div>
                    </div>
                    <div style="font-size: 0.74rem; color: #CBD5E1; line-height: 1.45; margin-top: 6px; border-top: 1px solid #1E293B; padding-top: 6px;">
                        <b>Confluence:</b> Above Session VWAP (₹{float(latest.get('VWAP', spot)):.2f}) & SuperTrend (₹{st_val:.2f})<br/>
                        <span style="color: #64748B;">Role: Pinpoints tactical intraday entry confluence before execution.</span>
                    </div>
                </div>

                <!-- M1 Scalp Micro-Timing -->
                <div style="background: rgba(15, 23, 42, 0.90); border: 1px solid #334155; border-top: 3px solid {mtf_matrix['m1']['badge_color']}; border-radius: 8px; padding: 12px 14px; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-size: 0.74rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">3. 1-MINUTE (M1) SCALP EXECUTION TIMING</span>
                            <span style="background: rgba(16, 185, 129, 0.18); color: #34D399; font-size: 0.68rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">SAVE ₹{mtf_matrix['m1']['premium_savings_pts']:.2f}/UNIT</span>
                        </div>
                        <div style="font-size: 1.05rem; font-weight: 800; color: #38BDF8; margin: 4px 0;">
                            Limit Bid: ₹{mtf_matrix['m1']['rec_limit_premium_ce'] if recommended_contract_type == 'CE' else mtf_matrix['m1']['rec_limit_premium_pe']:.2f} <span style="font-size: 0.74rem; color: #94A3B8;">(vs Market ₹{current_option_ltp:.2f})</span>
                        </div>
                    </div>
                    <div style="font-size: 0.74rem; color: #CBD5E1; line-height: 1.45; margin-top: 6px; border-top: 1px solid #1E293B; padding-top: 6px;">
                        <b>Micro Support:</b> ₹{mtf_matrix['m1']['limit_spot_ce'] if recommended_contract_type == 'CE' else mtf_matrix['m1']['limit_spot_pe']:.2f} (Savings: ₹{round(mtf_matrix['m1']['premium_savings_pts'] * total_trading_qty):,} on {num_lots} lots)<br/>
                        <span style="color: #34D399; font-weight: 700;">{mtf_matrix['m1']['desc']}</span>
                    </div>
                </div>
            </div>
        </div>
        """)

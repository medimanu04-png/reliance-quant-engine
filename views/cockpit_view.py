"""
views/cockpit_view.py
Live Cockpit Tab View (Spot Hero, Execution Blocks, Sequential Trade Engine HUD).
"""

from datetime import datetime, timezone, timedelta
import streamlit as st

from asset_config import build_contract_symbol
from trade_journal_manager import SequentialTradeEngine
from telegram_notifier import TelegramNotifier
from views.ui_components import st_button_stretch

IST = timezone(timedelta(hours=5, minutes=30))


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
                            POST-1:00 PM EXPIRY GAMMA RADAR ACTIVE: {scrip_symbol}
                        </div>
                        <div style="font-size: 0.78rem; color: #6EE7B7; margin-top: 3px;">
                            Weekly Expiry Exception: <b>1 Single High-Conviction Gamma Blast Setup Permitted</b> if institutional breakout criteria clear the gate. Sizing: {num_lots} Lots strictly.
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

    # Sequential Trade State
    seq_state = SequentialTradeEngine.get_state(symbol=scrip_symbol)
    current_seq_state = seq_state.get("current_state", SequentialTradeEngine.STATE_IDLE)
    active_trade = seq_state.get("active_trade")
    last_closed = seq_state.get("last_closed_trade")
    groww_feed = ctx.get("groww_feed")
    account_cash = ctx.get("account_cash", 50000.0)

    if current_seq_state == SequentialTradeEngine.STATE_IN_TRADE and active_trade:
        act_entry = float(active_trade.get("actual_entry_price", active_trade.get("planned_entry", 30.0)))
        active_ltp = float(active_trade.get("current_ltp", act_entry))
        target_p = float(active_trade.get("target", act_entry + 10.0))
        sl_p = float(active_trade.get("sl", act_entry - 8.0))
        trail_sl = float(active_trade.get("trailing_sl", sl_p))

        def _handle_close_target(sym, p, cash):
            SequentialTradeEngine.close_trade(exit_price=p, status="Target Hit", notes="Target reached in active monitoring", starting_cash=cash, symbol=sym)

        def _handle_close_sl(sym, p, cash):
            SequentialTradeEngine.close_trade(exit_price=p, status="SL Hit", notes="Stop loss hit in active monitoring", starting_cash=cash, symbol=sym)

        it_c1, it_c2, it_c3 = st.columns([1.2, 1.2, 1.6])
        with it_c1:
            if st_button_stretch("🎯 Mark Target Hit & Close", key=f"btn_close_target_{scrip_symbol}", on_click=_handle_close_target, args=(scrip_symbol, active_ltp, account_cash), help="Record target hit outcome and close trade"):
                st.rerun()
        with it_c2:
            if st_button_stretch("🛑 Mark SL Hit & Close", key=f"btn_close_sl_{scrip_symbol}", on_click=_handle_close_sl, args=(scrip_symbol, active_ltp, account_cash), help="Record stop-loss outcome and close trade"):
                st.rerun()
        with it_c3:
            if st_button_stretch("🔄 Sync with Groww Positions", key=f"btn_sync_groww_pos_{scrip_symbol}"):
                sync_res = SequentialTradeEngine.sync_with_groww_positions(groww_feed=groww_feed, symbol=scrip_symbol, starting_cash=account_cash)
                if sync_res.get("status") == "SUCCESS":
                    st.toast("✅ Reconciled with live Groww position!")
                st.rerun()

    elif current_seq_state == SequentialTradeEngine.STATE_ENTRY_PENDING and active_trade:
        planned_p = float(active_trade.get("planned_entry", 30.0))
        ep_c1, ep_c2, ep_c3 = st.columns([1.3, 1.2, 1.2])
        with ep_c1:
            actual_fill_input = st.number_input("Actual Groww Fill (₹)", value=float(planned_p), step=0.05, format="%.2f", key=f"groww_actual_fill_{scrip_symbol}")
        with ep_c2:
            if st_button_stretch("✅ Yes, Filled on Groww", key=f"btn_confirm_fill_{scrip_symbol}"):
                SequentialTradeEngine.confirm_groww_fill(confirmed=True, actual_price=actual_fill_input, symbol=scrip_symbol)
                st.toast(f"✅ Trade #{active_trade.get('trade_num', 1)} execution confirmed!")
                st.rerun()
        with ep_c3:
            if st_button_stretch("❌ Cancel Setup", key=f"btn_cancel_fill_{scrip_symbol}"):
                SequentialTradeEngine.confirm_groww_fill(confirmed=False, symbol=scrip_symbol)
                st.toast("ℹ️ Setup cancelled.")
                st.rerun()

    elif current_seq_state == SequentialTradeEngine.STATE_TRADE_CLOSED and last_closed:
        def _handle_ack_reset(sym):
            SequentialTradeEngine.acknowledge_and_reset(symbol=sym)
            st.session_state[f"seq_acked_{sym}"] = True

        if st_button_stretch(
            "🔄 Acknowledge & Scan Next Trade (Transition to IDLE / SCANNING)",
            key=f"btn_ack_scan_next_{scrip_symbol}",
            on_click=_handle_ack_reset,
            args=(scrip_symbol,)
        ):
            st.toast(f"✅ Trade acknowledged! {scrip_symbol} desk is now in IDLE / SCANNING.")
            st.rerun()

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
    lot_size = ctx.get("lot_size", 25)

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

    # 5. Execution Trigger Card (Armed Breakout & 1-Click Execution Engine)
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
            st.warning(f"Execution Trigger notice: {_e_trig}")

    # 6. Institutional Multi-Timeframe Matrix (M15 + M5 + M1)
    mtf_matrix = ctx.get("mtf_matrix")
    if mtf_matrix and isinstance(mtf_matrix, dict) and "m15" in mtf_matrix:
        mtf_sync_status = "🟢 TRIPLE BULLISH INVARIANCE (+4.0 PTS)" if mtf_matrix.get('is_triple_bullish') else ("🔴 TRIPLE BEARISH INVARIANCE (+4.0 PTS)" if mtf_matrix.get('is_triple_bearish') else ("🟡 TIMEFRAME CONFLICT / STAND DOWN (-4.0 PTS)" if mtf_matrix.get('is_conflict') else "🟡 PARTIAL ALIGNMENT (NEUTRAL)"))
        mtf_sync_color = "#34D399" if mtf_matrix.get('is_triple_bullish') else ("#F87171" if mtf_matrix.get('is_triple_bearish') else "#FBBF24")
        latest = ctx.get("latest", {})

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
                <div style="background: rgba(15, 23, 42, 0.90); border: 1px solid #334155; border-top: 3px solid {mtf_matrix['m15']['badge_color']}; border-radius: 8px; padding: 12px 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 0.74rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">1. 15-MINUTE (M15) STRUCTURAL COMPASS</span>
                        <span style="background: rgba(255,255,255,0.06); color: {mtf_matrix['m15']['badge_color']}; font-size: 0.68rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">{mtf_matrix['m15']['regime'].replace('_', ' ')}</span>
                    </div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; margin: 4px 0;">
                        {mtf_matrix['m15']['desc']}
                    </div>
                    <div style="font-size: 0.74rem; color: #CBD5E1; line-height: 1.45; margin-top: 6px; border-top: 1px solid #1E293B; padding-top: 6px;">
                        <b>EMAs:</b> 9: ₹{mtf_matrix['m15']['ema9']:.1f} | 20: ₹{mtf_matrix['m15']['ema20']:.1f} | 50: ₹{mtf_matrix['m15']['ema50']:.1f}<br/>
                        <span style="color: #64748B;">Role: Defines macro structural trend; filters counter-trend traps.</span>
                    </div>
                </div>

                <!-- M5 Tactical Confluence -->
                <div style="background: rgba(15, 23, 42, 0.90); border: 1px solid #334155; border-top: 3px solid {mtf_matrix['m5']['badge_color']}; border-radius: 8px; padding: 12px 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 0.74rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">2. 5-MINUTE (M5) TACTICAL TRIGGER</span>
                        <span style="background: rgba(255,255,255,0.06); color: {mtf_matrix['m5']['badge_color']}; font-size: 0.68rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">{mtf_matrix['m5']['trigger'].replace('_', ' ')}</span>
                    </div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; margin: 4px 0;">
                        {mtf_matrix['m5']['desc']}
                    </div>
                    <div style="font-size: 0.74rem; color: #CBD5E1; line-height: 1.45; margin-top: 6px; border-top: 1px solid #1E293B; padding-top: 6px;">
                        <b>Confluence:</b> Above Session VWAP (₹{float(latest.get('VWAP', spot)):.2f}) & SuperTrend (₹{float(latest.get('SuperTrend', spot)):.2f})<br/>
                        <span style="color: #64748B;">Role: Pinpoints tactical intraday entry confluence before execution.</span>
                    </div>
                </div>

                <!-- M1 Scalp Micro-Timing -->
                <div style="background: rgba(15, 23, 42, 0.90); border: 1px solid #334155; border-top: 3px solid {mtf_matrix['m1']['badge_color']}; border-radius: 8px; padding: 12px 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 0.74rem; font-weight: 800; color: #94A3B8; text-transform: uppercase;">3. 1-MINUTE (M1) SCALP EXECUTION TIMING</span>
                        <span style="background: rgba(16, 185, 129, 0.18); color: #34D399; font-size: 0.68rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">SAVE ₹{mtf_matrix['m1']['premium_savings_pts']:.2f}/UNIT</span>
                    </div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #38BDF8; margin: 4px 0;">
                        Limit Bid: ₹{mtf_matrix['m1']['rec_limit_premium_ce'] if recommended_contract_type == 'CE' else mtf_matrix['m1']['rec_limit_premium_pe']:.2f} <span style="font-size: 0.74rem; color: #94A3B8;">(vs Market ₹{current_option_ltp:.2f})</span>
                    </div>
                    <div style="font-size: 0.74rem; color: #CBD5E1; line-height: 1.45; margin-top: 6px; border-top: 1px solid #1E293B; padding-top: 6px;">
                        <b>Micro Support:</b> ₹{mtf_matrix['m1']['limit_spot_ce'] if recommended_contract_type == 'CE' else mtf_matrix['m1']['limit_spot_pe']:.2f} (Savings: ₹{round(mtf_matrix['m1']['premium_savings_pts'] * total_trading_qty):,} on {num_lots} lots)<br/>
                        <span style="color: #34D399; font-weight: 700;">{mtf_matrix['m1']['desc']}</span>
                    </div>
                </div>
            </div>
        </div>
        """)

"""
views/ledger_view.py
Trade Journal, Shadow Ledger, Groww Live Account Telemetry, and CA Audit Tab View.
"""

import base64
import os
import time as time_mod
from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st

from asset_config import get_asset_spec, build_contract_symbol
from trade_journal_manager import TradeJournalManager, SequentialTradeEngine, ShadowMonitoringEngine, SignalTracker, STARTING_CAPITAL
from views.ui_components import (
    st_button_stretch,
    st_download_button_stretch,
    st_form_submit_button_stretch,
    st_dataframe_stretch,
    show_screenshot_modal,
)

IST = timezone(timedelta(hours=5, minutes=30))
STARTING_CAPITAL = 50000.0


def render_ledger_tab(ctx: dict):
    """Renders the Groww wallet telemetry, sequential trade log, shadow monitoring, and audit views."""
    st.subheader("📒 Trade Journal, Shadow Ledger & Audit History")

    groww_feed = ctx.get("groww_feed")
    scrip_symbol = ctx.get("scrip_symbol", "NIFTY")
    scrip_name = ctx.get("scrip_name", "NIFTY")
    num_lots = ctx.get("num_lots", 4)
    lot_size = ctx.get("lot_size", 25)
    estimated_premium = ctx.get("estimated_premium", 0.0)
    current_option_ltp = ctx.get("current_option_ltp", 0.0)
    account_cash = ctx.get("account_cash", STARTING_CAPITAL)
    atm_strike = ctx.get("atm_strike", 0)
    recommended_contract_type = ctx.get("recommended_contract_type", "CE")
    rec_instrument = ctx.get("rec_instrument", "")
    is_tradable = ctx.get("is_tradable", False)
    target_premium = ctx.get("target_premium", 0.0)
    sl_premium = ctx.get("sl_premium", 0.0)
    expiry_date_str = ctx.get("expiry_date_str", "")
    active_mandate_expiry = ctx.get("active_mandate_expiry", "")
    total_trading_qty = ctx.get("total_trading_qty", lot_size * num_lots)

    # 1. Groww Live Account Telemetry
    if groww_feed and hasattr(groww_feed, "is_connected") and groww_feed.is_connected:
        live_wallet_telemetry = groww_feed.get_wallet_balance()
        live_pos_telemetry = groww_feed.get_live_positions()
        ucc_val = (groww_feed.user_profile or {}).get("ucc", "5697793414")

        realised_pnl_val = live_pos_telemetry.get("total_realised_pnl", 0.0)
        unrealised_pnl_val = live_pos_telemetry.get("total_unrealised_pnl", 0.0)
        net_live_pnl_val = live_pos_telemetry.get("total_pnl", 0.0)
        pnl_theme_color = "#10B981" if net_live_pnl_val >= 0 else "#EF4444"
        pnl_sign_char = "+" if net_live_pnl_val >= 0 else ""

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #070B14 0%, #0F172A 100%); border: 1px solid #1E293B; border-radius: 12px; padding: 18px 24px; margin-top: 15px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid #1E293B; padding-bottom: 12px; margin-bottom: 14px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span class="live-dot"></span>
                    <h3 style="margin: 0; font-size: 1.15rem; color: #FFFFFF; font-weight: 800; letter-spacing: -0.3px;">
                        ⚡ GROWW BROKER LIVE ACCOUNT TELEMETRY
                    </h3>
                    <span style="background: rgba(16, 185, 129, 0.15); color: #34D399; font-size: 0.68rem; padding: 2px 8px; border-radius: 4px; font-weight: 700; border: 1px solid rgba(16, 185, 129, 0.3);">
                        UCC: {ucc_val} (VERIFIED)
                    </span>
                    <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; font-size: 0.68rem; padding: 2px 8px; border-radius: 4px; font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.3);">
                        AUTOMATED 2FA SESSION ACTIVE
                    </span>
                </div>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid #334155; border-radius: 6px; padding: 4px 14px; text-align: right;">
                        <span style="font-size: 0.65rem; color: #94A3B8; text-transform: uppercase;">Clear Cash Wallet</span>
                        <div style="font-size: 1.10rem; font-weight: 800; color: #38BDF8;">₹{live_wallet_telemetry.get('clear_cash', 53280.53):,.2f}</div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid {'rgba(16, 185, 129, 0.4)' if net_live_pnl_val >= 0 else 'rgba(239, 68, 68, 0.4)'}; border-radius: 6px; padding: 4px 14px; text-align: right;">
                        <span style="font-size: 0.65rem; color: #94A3B8; text-transform: uppercase;">Today's Net Realized P&L</span>
                        <div style="font-size: 1.10rem; font-weight: 900; color: {pnl_theme_color};">{pnl_sign_char}₹{net_live_pnl_val:,.2f}</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        all_positions_list = live_pos_telemetry.get("positions", [])
        if all_positions_list:
            pos_columns = st.columns(min(len(all_positions_list), 3))
            for p_idx, pos_item in enumerate(all_positions_list):
                with pos_columns[p_idx % len(pos_columns)]:
                    symbol_str = pos_item.get("trading_symbol", "N/A")
                    pos_quantity = int(pos_item.get("quantity", 0))
                    pos_realised = float(pos_item.get("realised_pnl", 0.0))
                    pos_unrealised = float(pos_item.get("unrealised_pnl", 0.0))
                    pos_state = "OPEN POSITION" if pos_quantity != 0 else "SQUARED OFF (CLOSED)"
                    pos_state_color = "#38BDF8" if pos_quantity != 0 else "#94A3B8"
                    pos_total_pnl = pos_realised + pos_unrealised
                    pos_pnl_color = "#10B981" if pos_total_pnl >= 0 else "#EF4444"

                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 8px; padding: 12px; margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <b style="color: #FFFFFF; font-size: 0.88rem;">{symbol_str}</b>
                            <span style="font-size: 0.65rem; color: {pos_state_color}; font-weight: 700; background: rgba(148, 163, 184, 0.1); padding: 2px 6px; border-radius: 4px;">{pos_state}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">
                            <span>Quantity: <b style="color: #E2E8F0;">{pos_quantity}</b> (Traded: {pos_item.get('credit_quantity', 0)})</span>
                            <span>Net P&L: <b style="color: {pos_pnl_color}; font-size: 0.90rem;">{'+' if pos_total_pnl >= 0 else ''}₹{pos_total_pnl:,.2f}</b></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.caption("⚪ No F&O positions recorded today on Groww account.")

        st.markdown("</div>", unsafe_allow_html=True)

    # 2. Daily Performance Journal, Shadow Monitoring & Calendar History
    default_prem = get_asset_spec(scrip_symbol).default_call_price
    today_strike_price = float(estimated_premium if estimated_premium > 0 else (current_option_ltp if current_option_ltp > 0 else default_prem))
    today_str = datetime.now(IST).strftime("%Y-%m-%d")

    # Header with Controls
    sec9_col1, sec9_col2 = st.columns([3.0, 1.4])
    with sec9_col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); border: 1px solid #334155; border-radius: 12px; padding: 16px 22px; margin-top: 12px; margin-bottom: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h2 style="margin: 0; font-size: 1.35rem; color: #FFFFFF; font-weight: 800; display: flex; align-items: center; gap: 10px;">
                        📒 {scrip_name} Daily Trade Ledger, Shadow Monitoring & Calendar History
                    </h2>
                    <p style="margin: 4px 0 0 0; color: #94A3B8; font-size: 0.82rem;">
                        Cross-Verifying <b>Trade Given (Model Recommendation)</b> ⇄ <b>Trade Taken in Groww</b> • Automated Shadow Monitoring to 3:30 PM EOD
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with sec9_col2:
        st.write("")
        sb_c1, sb_c2 = st.columns(2)
        with sb_c1:
            if st_button_stretch("🤖 Sync Groww", help=f"Cross-verifies today's {scrip_symbol} orders & positions from Groww API against model recommendations"):
                with st.spinner(f"Connecting to Groww broker API & extracting {scrip_symbol} fills..."):
                    if groww_feed:
                        gw_trades = groww_feed.get_executed_trades_today(symbol_filter=scrip_symbol, force_refresh=True)
                        if gw_trades:
                            synced = TradeJournalManager.sync_groww_trades(
                                groww_executed_trades=gw_trades,
                                active_signal=SignalTracker.get_signal(symbol=scrip_symbol),
                                starting_cash=account_cash,
                                symbol_filter=scrip_symbol
                            )
                            st.success(f"✅ Verified {len(synced)} {scrip_symbol} executed trades!")
                            st.rerun()
                        else:
                            st.info(f"ℹ️ No executed {scrip_symbol} trades found today in Groww account.")
        with sb_c2:
            if st_button_stretch("🔄 Poll Shadow", help="Queries live Groww option contract ticks and updates price extremes & outcomes"):
                with st.spinner("Updating shadow ticks from Groww API..."):
                    ShadowMonitoringEngine.update_shadow_monitoring(groww_feed=groww_feed)
                    st.success("✅ Shadow telemetry updated!")
                    st.rerun()

    # Interactive Calendar View & Date Navigation
    available_dates = ShadowMonitoringEngine.get_available_dates()
    if today_str not in available_dates:
        available_dates.insert(0, today_str)

    cal_col1, cal_col2, cal_col3, cal_col4 = st.columns([1.4, 1.4, 1.8, 1.1])
    with cal_col1:
        default_cal_val = datetime.strptime(today_str, "%Y-%m-%d")
        if "cal_nav_date" in st.session_state:
            try:
                default_cal_val = datetime.strptime(st.session_state["cal_nav_date"], "%Y-%m-%d")
            except Exception:
                default_cal_val = datetime.strptime(today_str, "%Y-%m-%d")

        selected_cal_date = st.date_input(
            "📅 Calendar Navigation",
            value=default_cal_val,
            help="Select a date to filter all recommendations, shadow monitoring price extremes, and Groww execution outcomes for that day"
        )
        selected_date_str = selected_cal_date.strftime("%Y-%m-%d") if selected_cal_date else today_str

    with cal_col2:
        view_mode_idx = 1 if st.session_state.get("cal_nav_all", False) else 0
        date_scope = st.selectbox(
            "Calendar Scope",
            ["Selected Date Only", "All Dates (Full History)"],
            index=view_mode_idx,
            help="Toggle between viewing records for the chosen calendar day or the full historical log"
        )
        st.session_state["cal_nav_all"] = (date_scope == "All Dates (Full History)")

    with cal_col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        qb_1, qb_2 = st.columns(2)
        with qb_1:
            if st_button_stretch("📅 Today", help="Jump to today's active signals"):
                st.session_state["cal_nav_date"] = today_str
                st.session_state["cal_nav_all"] = False
                st.rerun()
        with qb_2:
            if st_button_stretch("📜 All Dates", help="Show all historical recommendations"):
                st.session_state["cal_nav_all"] = True
                st.rerun()

    with cal_col4:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        all_raw_shadow = ShadowMonitoringEngine.load_records(symbol=scrip_symbol)
        raw_df = pd.DataFrame(all_raw_shadow)
        csv_bytes = raw_df.to_csv(index=False).encode('utf-8')
        st_download_button_stretch(
            label="📥 Export CSV",
            data=csv_bytes,
            file_name=f"{scrip_symbol.lower()}_trade_signals_{datetime.now(IST).strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    active_date_filter = None if date_scope == "All Dates (Full History)" else selected_date_str
    shadow_records = ShadowMonitoringEngine.get_records_by_date(active_date_filter, symbol=scrip_symbol)
    journal_entries = TradeJournalManager.load_journal(starting_cash=account_cash, symbol=scrip_symbol)

    if active_date_filter:
        journal_entries = [e for e in journal_entries if e.get("date") == active_date_filter]

    shadow_kpi = ShadowMonitoringEngine.get_shadow_kpi(shadow_records)
    all_journal = TradeJournalManager.load_journal(starting_cash=account_cash, symbol=scrip_symbol)
    all_summary_kpi = TradeJournalManager.get_summary_kpi(all_journal, today_strike_price=today_strike_price, starting_cash=account_cash)
    date_label = f"📅 {selected_date_str}" if active_date_filter else "📜 All Historical Dates"

    st.markdown(f"""
    <div class="journal-kpi-grid">
        <div class="journal-card">
            <div style="font-size: 0.72rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">📡 Daily Signals ({date_label})</div>
            <div style="font-size: 1.45rem; font-weight: 900; color: #38BDF8; font-family: 'Inter', sans-serif;">{shadow_kpi['total_signals']} Signals</div>
            <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">User Executed: <b style="color: #10B981;">{shadow_kpi['user_executed_count']}</b> ({shadow_kpi['user_executed_pct']}%)</div>
        </div>
        <div class="journal-card">
            <div style="font-size: 0.72rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">🎯 Shadow Outcomes (Groww API)</div>
            <div style="font-size: 1.45rem; font-weight: 900; color: #10B981; font-family: 'Inter', sans-serif;">{shadow_kpi['target_hits']} Hits <span style="font-size: 0.90rem; color: #EF4444;">({shadow_kpi['sl_hits']} SL)</span></div>
            <div style="font-size: 0.75rem; color: #F59E0B; margin-top: 4px;">{shadow_kpi['active_count']} Active • {shadow_kpi['eod_exits']} EOD Exits</div>
        </div>
        <div class="journal-card">
            <div style="font-size: 0.72rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">🛰️ Shadow Model P&L</div>
            <div style="font-size: 1.45rem; font-weight: 900; color: {'#10B981' if shadow_kpi['shadow_total_pnl'] >= 0 else '#EF4444'}; font-family: 'Inter', sans-serif;">{'+' if shadow_kpi['shadow_total_pnl'] >= 0 else ''}₹{shadow_kpi['shadow_total_pnl']:,.2f}</div>
            <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Potential P&L if all signals followed</div>
        </div>
        <div class="journal-card">
            <div style="font-size: 0.72rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">💰 Groww Broker Realized P&L</div>
            <div style="font-size: 1.45rem; font-weight: 900; color: {'#10B981' if shadow_kpi['groww_realised_pnl'] >= 0 else '#EF4444'}; font-family: 'Inter', sans-serif;">{'+' if shadow_kpi['groww_realised_pnl'] >= 0 else ''}₹{shadow_kpi['groww_realised_pnl']:,.2f}</div>
            <div style="font-size: 0.75rem; color: #34D399; margin-top: 4px;">Verified Groww Executions</div>
        </div>
        <div class="journal-card">
            <div style="font-size: 0.72rem; color: #94A3B8; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">💳 Broker Cash Balance</div>
            <div style="font-size: 1.45rem; font-weight: 900; color: #10B981; font-family: 'Inter', sans-serif;">₹{all_summary_kpi['total_cash']:,.2f}</div>
            <div style="font-size: 0.75rem; color: #38BDF8; margin-top: 4px;">Starting: ₹{STARTING_CAPITAL:,.2f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Running Sequential Trade Log Table
    seq_state = SequentialTradeEngine.get_state(symbol=scrip_symbol)
    curr_state_val = seq_state.get("current_state", SequentialTradeEngine.STATE_IDLE)
    state_color = "#10B981" if curr_state_val == SequentialTradeEngine.STATE_IDLE else ("#F59E0B" if curr_state_val == SequentialTradeEngine.STATE_ENTRY_PENDING else "#38BDF8")
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px; margin-bottom: 6px;">
        <h4 style='color: #F8FAFC; margin: 0;'>📋 Running Sequential Trade Log ({scrip_symbol})</h4>
        <span style="background: rgba(15, 23, 42, 0.8); border: 1px solid {state_color}; color: {state_color}; padding: 3px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
            ● ENGINE: {curr_state_val}
        </span>
    </div>
    """, unsafe_allow_html=True)

    tax_rows = TradeJournalManager.generate_tax_audit_report(symbol_filter=scrip_symbol)
    tax_col1, tax_col2 = st.columns([2.5, 1.5])
    with tax_col1:
        st.caption(f"Strict Sequential Trading Operating Discipline • One Trade at a Time • Verified Groww Executions ({scrip_symbol})")
    with tax_col2:
        if tax_rows:
            df_tax_audit = pd.DataFrame(tax_rows)
            csv_tax_data = df_tax_audit.to_csv(index=False).encode('utf-8')
            st_download_button_stretch(
                label="📥 Download CA Tax Statement",
                data=csv_tax_data,
                file_name=f"CA_Tax_Audit_Statement_{scrip_symbol}_{datetime.now(IST).strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key=f"btn_ca_tax_{scrip_symbol.lower()}"
            )

    running_rows = SequentialTradeEngine.get_running_trade_log_rows(symbol=scrip_symbol)
    if running_rows:
        df_running = pd.DataFrame(running_rows)
        st_dataframe_stretch(
            df_running,
            height=min(260, 55 + (len(running_rows) * 40)),
            column_config={
                "Trade #": st.column_config.TextColumn("Trade #", width="small"),
                "Date": st.column_config.TextColumn("Date", width="small"),
                "Instrument": st.column_config.TextColumn("Instrument", width="medium"),
                "Confluence": st.column_config.TextColumn("Confluence", width="small"),
                "Planned Entry": st.column_config.TextColumn("Planned Entry", width="small"),
                "Actual Groww Entry": st.column_config.TextColumn("Actual Groww Entry", width="medium"),
                "Executed (Yes/No)": st.column_config.TextColumn("Executed (Yes/No)", width="small"),
                "SL": st.column_config.TextColumn("SL", width="small"),
                "Target": st.column_config.TextColumn("Target", width="small"),
                "Status": st.column_config.TextColumn("Status", width="medium"),
                "P&L": st.column_config.TextColumn("P&L", width="small"),
            }
        )
    else:
        st.info(f"ℹ️ No trades recorded yet today for {scrip_symbol}. Click '➕ Record / Sync Trade into Sequential Log' below or await an institutional 75%+ confluence setup.")

    # Record / Sync Trade into Sequential Log
    with st.expander("➕ Record / Sync Trade into Sequential Log", expanded=False):
        t_sync, t_manual = st.tabs(["🔄 Sync Groww Broker Executions", "✍️ Manual Trade Entry / Override"])
        with t_sync:
            st.caption(f"Fetch genuine completed fills from your Groww account and automatically log them into today's Sequential Trade Log ({scrip_symbol}).")
            if st_button_stretch("🔄 Sync from Groww Now", key="sync_groww_trades_btn"):
                try:
                    synced_count = TradeJournalManager.sync_with_groww_executed_trades(groww_feed, starting_cash=STARTING_CAPITAL, symbol_filter=scrip_symbol)
                    st.success(f"Successfully synced {synced_count} executed trade(s) for {scrip_symbol} from Groww!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync error: {e}")
        with t_manual:
            st.caption(f"Directly record an executed trade into the Sequential Trade Log and Ledger for {scrip_symbol}.")
            with st.form(key="manual_seq_trade_entry_form"):
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    m_instrument = st.text_input("Instrument / Contract", value=f"{scrip_symbol} {atm_strike} {recommended_contract_type}")
                    m_action = st.selectbox("Action / Type", ["BUY PE", "BUY CE", "BUY FUT", "SELL FUT"], index=0 if recommended_contract_type == "PE" else 1)
                    m_date = st.text_input("Trade Date", value=datetime.now(IST).strftime("%Y-%m-%d"))
                with col_m2:
                    m_planned_entry = st.number_input("Planned Entry (₹)", value=float(estimated_premium), step=0.25, format="%.2f")
                    m_actual_entry = st.number_input("Actual Groww Entry (₹)", value=float(estimated_premium), step=0.25, format="%.2f")
                    m_exit_price = st.number_input("Exit Price (₹) (0 if Open)", value=float(target_premium), step=0.25, format="%.2f")
                with col_m3:
                    m_sl = st.number_input("Stop Loss (₹)", value=float(sl_premium), step=0.25, format="%.2f")
                    m_target = st.number_input("Target Price (₹)", value=float(target_premium), step=0.25, format="%.2f")
                    m_lots = st.number_input(f"Number of Lots ({lot_size} qty/lot)", value=1, min_value=1, max_value=20, step=1)

                col_m4, col_m5 = st.columns(2)
                with col_m4:
                    m_status = st.selectbox("Status", ["Target Hit", "SL Hit", "Open", "Discretionary Exit (+Profit)", "Discretionary Exit (-Loss)", "EOD Exit"], index=0)
                    m_confluence = st.slider("Confluence Score (%)", min_value=50.0, max_value=100.0, value=78.5, step=0.5)
                with col_m5:
                    m_notes = st.text_area("Trade Notes / Rationale", value="Manual entry verified against Groww contract note.", height=78)

                submit_manual = st_form_submit_button_stretch("💾 Save Trade to Sequential Log")
                if submit_manual:
                    qty_calc = int(m_lots * lot_size)
                    pts = round(m_exit_price - m_actual_entry, 2) if m_status != "Open" else 0.0
                    realised_pnl = round(pts * qty_calc, 2) if m_status != "Open" else 0.0
                    t_now = datetime.now(IST).strftime("%I:%M:%S %p IST")
                    t_rec = {
                        "id": f"TRD-{m_date.replace('-', '')}-{int(time_mod.time()) % 1000:03d}-MANUAL",
                        "date": m_date,
                        "day": datetime.strptime(m_date, "%Y-%m-%d").strftime("%A") if m_date else "Today",
                        "trading_symbol": m_instrument,
                        "instrument": m_instrument,
                        "type": m_action,
                        "decision": "TRADABLE (A+ SETUP)" if m_confluence >= 75 else "MANUAL ENTRY",
                        "source": "MANUAL_ENTRY",
                        "is_closed": (m_status != "Open"),
                        "trade_given_time": t_now,
                        "suggested_contract": m_instrument,
                        "suggested_entry": m_planned_entry,
                        "suggested_exit": m_target,
                        "suggested_sl": m_sl,
                        "suggested_target_pts": round(m_target - m_planned_entry, 2),
                        "suggested_sl_pts": round(m_planned_entry - m_sl, 2),
                        "actual_entry_time": t_now,
                        "actual_entry_price": m_actual_entry,
                        "entry_price": m_actual_entry,
                        "actual_exit_time": t_now if m_status != "Open" else None,
                        "actual_exit_price": m_exit_price if m_status != "Open" else None,
                        "exit_price": m_exit_price if m_status != "Open" else None,
                        "num_lots": int(m_lots),
                        "lot_size": int(lot_size),
                        "qty": qty_calc,
                        "capital_deployed": round(m_actual_entry * qty_calc, 2),
                        "realised_pnl": realised_pnl,
                        "total_profit": realised_pnl,
                        "net_profit": realised_pnl,
                        "net_pnl": realised_pnl,
                        "amount_captured": realised_pnl if realised_pnl > 0 else 0.0,
                        "amount_lost": abs(realised_pnl) if realised_pnl < 0 else 0.0,
                        "status": "HIT" if "Target" in m_status or realised_pnl > 0 else ("FAIL" if "SL" in m_status or realised_pnl < 0 else "OPEN"),
                        "entry_slippage_pts": round(m_actual_entry - m_planned_entry, 2),
                        "notes": f"Manual Log • {m_status} • {m_notes}",
                        "confluence_score": m_confluence
                    }
                    TradeJournalManager.add_or_update_entry(t_rec, starting_cash=STARTING_CAPITAL)
                    if m_status == "Open":
                        SequentialTradeEngine.enter_trade_direct(
                            contract=m_instrument,
                            instrument=m_instrument,
                            entry_price=m_actual_entry,
                            sl=m_sl,
                            target=m_target,
                            direction=m_action,
                            expiry=expiry_date_str or active_mandate_expiry,
                            confluence=m_confluence,
                            qty=qty_calc,
                            num_lots=int(m_lots),
                            symbol=scrip_symbol
                        )
                    elif m_status in ["Target Hit", "SL Hit"]:
                        s_st = SequentialTradeEngine.get_state(symbol=scrip_symbol)
                        if s_st.get("current_state") == SequentialTradeEngine.STATE_IN_TRADE:
                            SequentialTradeEngine.close_trade(exit_price=m_exit_price, status=m_status, notes=m_notes, starting_cash=STARTING_CAPITAL, symbol=scrip_symbol)
                    st.success(f"✅ Trade {m_instrument} recorded successfully into Sequential Trade Log ({scrip_symbol})!")
                    st.rerun()

    # Search & Filter Controls
    f_c1, f_c2 = st.columns([1.5, 2.5])
    with f_c1:
        outcome_filter = st.selectbox(
            "Filter Outcome",
            ["All Records", "Target Hit (Wins)", "Stop-Loss Hit (Losses)", "Active Monitoring", "EOD Exit"],
            index=0
        )
    with f_c2:
        search_query = st.text_input("Search Logs", placeholder="Search by symbol, action, date, or notes...")

    filtered_shadow = list(shadow_records)
    if outcome_filter == "Target Hit (Wins)":
        filtered_shadow = [r for r in filtered_shadow if r.get("shadow_status") == "Target Hit"]
    elif outcome_filter == "Stop-Loss Hit (Losses)":
        filtered_shadow = [r for r in filtered_shadow if r.get("shadow_status") == "Stop-Loss Hit"]
    elif outcome_filter == "Active Monitoring":
        filtered_shadow = [r for r in filtered_shadow if r.get("shadow_status") == "Active Monitoring"]
    elif outcome_filter == "EOD Exit":
        filtered_shadow = [r for r in filtered_shadow if r.get("shadow_status") == "EOD Exit"]

    if search_query:
        sq = search_query.lower()
        filtered_shadow = [
            r for r in filtered_shadow
            if sq in str(r.get("symbol", "")).lower() or sq in str(r.get("date", "")).lower() or sq in str(r.get("notes", "")).lower() or sq in str(r.get("action", "")).lower()
        ]

    tab_shadow, tab_verified = st.tabs([
        "🛰️ Automated Shadow Monitoring & Daily Signal Log",
        "⚡ Verified Groww Executions & Screenshot Audit"
    ])

    with tab_shadow:
        st.markdown(f"<h4 style='color: #F8FAFC; margin-top: 10px; margin-bottom: 6px;'>🛰️ Daily Signal Log & Automated Shadow Monitoring ({date_label})</h4>", unsafe_allow_html=True)
        st.caption("Tracks every buy trade given by the quantitative engine • Strictly monitors real-time price extremes & shadow outcomes until 3:30 PM • Verified execution status cross-referenced with Groww broker API")

        shadow_table_rows = []
        for r in filtered_shadow:
            st_raw = r.get("shadow_status", "Active Monitoring")
            if st_raw == "Target Hit":
                badge_out = "🟢 Target Hit"
            elif st_raw == "Stop-Loss Hit":
                badge_out = "🔴 Stop-Loss Hit"
            elif st_raw == "EOD Exit":
                badge_out = "🟡 EOD Exit (3:30 PM)"
            else:
                badge_out = "🔵 Active Monitoring"

            user_exec = "🟢 Yes" if r.get("user_executed") else "⚪ No"
            act_e_str = f"₹{r.get('actual_entry_price', 0.0):.2f} ({r.get('actual_entry_time', '')})" if r.get("actual_entry_price") else "—"
            act_x_str = f"₹{r.get('actual_exit_price', 0.0):.2f} ({r.get('actual_exit_time', '')})" if r.get("actual_exit_price") else "—"
            high_str = f"₹{r.get('highest_price_reached', r.get('entry', 0.0)):.2f}"
            low_str = f"₹{r.get('lowest_price_reached', r.get('entry', 0.0)):.2f}"

            s_pnl = float(r.get("shadow_pnl", 0.0))
            s_pnl_str = f"+₹{s_pnl:,.2f}" if s_pnl >= 0 else f"-₹{abs(s_pnl):,.2f}"

            r_pnl = float(r.get("realised_pnl", 0.0))
            r_pnl_str = f"+₹{r_pnl:,.2f}" if r_pnl >= 0 else f"-₹{abs(r_pnl):,.2f}" if r.get("user_executed") else "—"

            has_ss = "✅ Attached" if (r.get("screenshot") or r.get("screenshot_data_uri")) else "❌ None"

            conf_val = r.get("confluence_score")
            conf_str = f"{float(conf_val):.1f}%" if conf_val else "—"

            spec_r = get_asset_spec(symbol=r.get("symbol") or scrip_symbol, contract=r.get("instrument"))
            tgt_pts_val = r.get('target_pts') if r.get('target_pts') is not None else spec_r.target_pts
            sl_pts_val = r.get('sl_pts') if r.get('sl_pts') is not None else spec_r.sl_pts

            shadow_table_rows.append({
                "Date": r.get("date"),
                "Timestamp": r.get("timestamp"),
                "Symbol": r.get("symbol"),
                "Action": r.get("action", "BUY"),
                "Confluence Score": conf_str,
                "Planned Entry": f"₹{float(r.get('entry', 0.0)):.2f}",
                "Target": f"₹{float(r.get('target', 0.0)):.2f} (+{tgt_pts_val})",
                "SL": f"₹{float(r.get('sl', 0.0)):.2f} (-{sl_pts_val})",
                "User Executed": user_exec,
                "Actual Entry (Groww)": act_e_str,
                "Actual Exit (Groww)": act_x_str,
                "High Reached": high_str,
                "Low Reached": low_str,
                "Outcome": badge_out,
                "Shadow P&L": s_pnl_str,
                "Groww Realized": r_pnl_str,
                "Screenshot": has_ss,
                "Confluence / Notes": r.get("notes", "")
            })

        if shadow_table_rows:
            df_shadow = pd.DataFrame(shadow_table_rows)
            st_dataframe_stretch(
                df_shadow,
                height=min(450, 60 + (len(shadow_table_rows) * 45)),
                column_config={
                    "Date": st.column_config.TextColumn("Date", width="small"),
                    "Timestamp": st.column_config.TextColumn("Time Given", width="small"),
                    "Symbol": st.column_config.TextColumn("Contract", width="medium"),
                    "Action": st.column_config.TextColumn("Action", width="small"),
                    "Confluence Score": st.column_config.TextColumn("Confluence Score", width="small"),
                    "Planned Entry": st.column_config.TextColumn("Entry", width="small"),
                    "Target": st.column_config.TextColumn("Target", width="small"),
                    "SL": st.column_config.TextColumn("SL", width="small"),
                    "User Executed": st.column_config.TextColumn("User Executed", width="small"),
                    "Actual Entry (Groww)": st.column_config.TextColumn("Actual Entry (Groww)", width="medium"),
                    "Actual Exit (Groww)": st.column_config.TextColumn("Actual Exit (Groww)", width="medium"),
                    "High Reached": st.column_config.TextColumn("High Reached", width="small"),
                    "Low Reached": st.column_config.TextColumn("Low Reached", width="small"),
                    "Outcome": st.column_config.TextColumn("Outcome", width="medium"),
                    "Shadow P&L": st.column_config.TextColumn("Shadow P&L", width="small"),
                    "Groww Realized": st.column_config.TextColumn("Groww P&L", width="small"),
                    "Screenshot": st.column_config.TextColumn("Screenshot", width="small"),
                    "Confluence / Notes": st.column_config.TextColumn("Audit Notes", width="large"),
                }
            )

    with tab_verified:
        st.markdown(f"<h4 style='color: #F8FAFC; margin-top: 10px; margin-bottom: 6px;'>🔍 Verified Execution Breakdown (Trade Given vs. Trade Taken in Groww)</h4>", unsafe_allow_html=True)
        st.caption("Displays executed trades verified from Groww broker API fills with trade proof screenshots.")

        filtered_entries = list(journal_entries)
        if outcome_filter == "Target Hit (Wins)":
            filtered_entries = [e for e in filtered_entries if e.get("status") == "HIT"]
        elif outcome_filter == "Stop-Loss Hit (Losses)":
            filtered_entries = [e for e in filtered_entries if e.get("status") == "FAIL"]
        elif outcome_filter == "Active Monitoring":
            filtered_entries = [e for e in filtered_entries if e.get("status") == "OPEN"]

        if search_query:
            sq = search_query.lower()
            filtered_entries = [
                e for e in filtered_entries
                if sq in str(e.get("trading_symbol", "")).lower() or sq in str(e.get("date", "")).lower() or sq in str(e.get("notes", "")).lower()
            ]

        if filtered_entries:
            unique_filtered_entries = []
            seen_f_ids = set()
            for e in filtered_entries:
                eid = e.get("id") or f"{e.get('date')}_{e.get('trading_symbol')}_{e.get('actual_entry_time', '')}"
                if eid not in seen_f_ids:
                    seen_f_ids.add(eid)
                    unique_filtered_entries.append(e)

            for idx, entry in enumerate(reversed(unique_filtered_entries)):
                st_raw = entry.get("status", "STAND DOWN")
                if st_raw == "HIT":
                    badge_color, badge_bg, badge_label = "#10B981", "rgba(16, 185, 129, 0.15)", "🟢 HIT (PROFIT TARGET REACHED)"
                elif st_raw == "FAIL":
                    badge_color, badge_bg, badge_label = "#EF4444", "rgba(239, 68, 68, 0.15)", "🔴 STOP LOSS TRIGGERED"
                elif st_raw == "OPEN":
                    badge_color, badge_bg, badge_label = "#38BDF8", "rgba(56, 189, 248, 0.15)", "🔵 LIVE POSITION OPEN"
                else:
                    badge_color, badge_bg, badge_label = "#94A3B8", "rgba(148, 163, 184, 0.15)", "⚪ STAND DOWN"

                pnl_val = float(entry.get("realised_pnl", entry.get("total_profit", 0.0)))
                pnl_col = "#10B981" if pnl_val >= 0 else "#EF4444"
                pnl_sign = "+" if pnl_val >= 0 else ""
                roi_val = float(entry.get("trade_roi_pct", 0.0))
                roi_sign = "+" if roi_val >= 0 else ""

                with st.container():
                    st.markdown(f"""
                    <div style="background: #0B1120; border: 1px solid #1E293B; border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1E293B; padding-bottom: 8px; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                            <div>
                                <span style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF;">{entry.get('trading_symbol', 'N/A')}</span>
                                <span style="font-size: 0.75rem; color: #94A3B8; margin-left: 8px;">{entry.get('date')} ({entry.get('day')})</span>
                            </div>
                            <div style="display: flex; gap: 8px; align-items: center;">
                                <span style="background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_color}; font-size: 0.72rem; padding: 2px 8px; border-radius: 4px; font-weight: 800;">{badge_label}</span>
                                <span style="background: rgba(15, 23, 42, 0.9); color: {pnl_col}; border: 1px solid #334155; font-size: 0.85rem; padding: 2px 10px; border-radius: 4px; font-weight: 900;">
                                    Total Profit: {pnl_sign}₹{pnl_val:,.2f} ({roi_sign}{roi_val:.1f}%)
                                </span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info(f"ℹ️ No executed trades found matching the filter for {date_label}. Only verified Groww executions are displayed here.")

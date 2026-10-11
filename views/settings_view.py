"""
views/settings_view.py
Risk Policy, Sizing Parameters, 9-Scenario Simulation Hub, and API Settings Tab View.
"""

from datetime import datetime
import streamlit as st
from views.ui_components import st_button_stretch
from telegram_notifier import TelegramNotifier
from trade_journal_manager import BreakoutTriggerManager


def render_settings_tab(
    scrip_symbol: str,
    scrip_name: str,
    lot_size: int,
    scrip_lots_count: int,
    spec,
    scrip_target_pts: float,
    scrip_sl_pts: float,
    scrip_min_gate: float,
    lower_atm: int,
    upper_atm: int,
    expiry_date_str: str,
    dte: int,
    recommended_contract_type: str,
    atm_strike: int,
    groww_feed,
    time_gate_msg: str = "",
    is_sim_active: bool = False
):
    """Renders the settings, risk policy, scenario simulator, and broker/telegram integrations tab."""
    st.subheader("⚙️ Risk Policy, Config & Simulation Hub")
    st.caption("Central desk management: Risk parameters, policy safeguards, 9-scenario simulation hub, and API connectivity.")

    col_cfg_left, col_cfg_right = st.columns(2)

    with col_cfg_left:
        st.markdown(f"### 🎯 Risk & Position Sizing Parameters ({scrip_symbol})")
        c_lots = st.number_input(
            f"Number of Lots ({scrip_symbol}: {lot_size} Qty/Lot)",
            min_value=1,
            max_value=10,
            value=int(st.session_state.get(f"num_lots_{scrip_symbol}", scrip_lots_count)),
            key=f"ui_num_lots_{scrip_symbol}"
        )
        st.session_state[f"num_lots_{scrip_symbol}"] = c_lots
        st.session_state["num_lots"] = c_lots

        target_max = round(spec.target_pts * 2.5, 1)
        target_step = 1.0 if spec.target_pts >= 20.0 else 0.5
        c_target = st.number_input(
            f"Target Points (pts) — {scrip_symbol}",
            min_value=1.0,
            max_value=target_max,
            value=float(st.session_state.get(f"target_pts_{scrip_symbol}", scrip_target_pts)),
            step=target_step,
            key=f"ui_target_pts_{scrip_symbol}"
        )
        st.session_state[f"target_pts_{scrip_symbol}"] = c_target
        st.session_state["target_pts"] = c_target

        sl_max = round(spec.sl_pts * 2.5, 1)
        sl_step = 1.0 if spec.sl_pts >= 15.0 else 0.5
        c_sl = st.number_input(
            f"Stop Loss Reference Cap (pts) — {scrip_symbol}",
            min_value=1.0,
            max_value=sl_max,
            value=float(st.session_state.get(f"sl_pts_{scrip_symbol}", scrip_sl_pts)),
            step=sl_step,
            key=f"ui_sl_pts_{scrip_symbol}"
        )
        st.session_state[f"sl_pts_{scrip_symbol}"] = c_sl
        st.session_state["sl_pts"] = c_sl

        c_gate = st.slider(
            f"Directional Gate Threshold (%) — {scrip_symbol}",
            min_value=60.0,
            max_value=95.0,
            value=float(st.session_state.get(f"min_hit_{scrip_symbol}", scrip_min_gate)),
            step=0.5,
            key=f"ui_min_hit_{scrip_symbol}"
        )
        st.session_state[f"min_hit_{scrip_symbol}"] = c_gate
        st.session_state["MIN_HIT_PERCENTAGE"] = c_gate

        c_max_sl = st.number_input(
            f"Max Daily Stop Losses Before Auto-Lock — {scrip_symbol}",
            min_value=1,
            max_value=5,
            value=int(st.session_state.get(f"max_daily_sl_allowed_{scrip_symbol}", 1)),
            key=f"ui_max_sl_{scrip_symbol}"
        )
        st.session_state[f"max_daily_sl_allowed_{scrip_symbol}"] = c_max_sl
        st.session_state["max_daily_sl_allowed"] = c_max_sl

        col_sl_stat, col_sl_rst = st.columns([2, 1])
        with col_sl_stat:
            st.caption(f"🛡️ Daily SL Hits ({scrip_symbol}): **{st.session_state.get(f'session_sl_count_{scrip_symbol}', 0)} / {c_max_sl}**")
        with col_sl_rst:
            if st.button("Reset SL Hits", key=f"ui_rst_sl_cnt_btn_{scrip_symbol}"):
                st.session_state[f"session_sl_count_{scrip_symbol}"] = 0
                st.session_state["session_sl_count"] = 0
                st.rerun()

        macro_gate_desc = "Benchmark Liquidity & Volatility Gate Active"

        st.html(f"""
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px; padding: 10px 14px; margin: 10px 0; font-size: 0.74rem; color: #CBD5E1; line-height: 1.5;">
            🛡️ <b>Capital-Preserving Institutional Model ({scrip_symbol}):</b><br>
            Sizing: <b>{c_lots} Lot{'s' if c_lots > 1 else ''} ({c_lots * lot_size} Qty)</b> | Risk Cap: <b>~₹{c_sl * c_lots * lot_size:,.0f} (&le; 4.0% Account Cash)</b><br>
            Dynamic Stop Loss: <b>1.5× 5m ATR (-{c_sl:.1f} pts Max)</b> | Target: <b>+{c_target:.1f} pts</b><br>
            IV Filter: <b>IVP &lt; 50% Clean Window</b> (Crush Lock if &gt;70%)<br>
            Macro Gate: <b>{macro_gate_desc}</b>
        </div>
        """)

        st.markdown(f"### 🔒 Policy Safeguards & Market Timing ({scrip_symbol})")
        st.success(f"✅ **STRIKE**: Dual ATM Corridor ({scrip_symbol} {lower_atm} & {upper_atm})")
        st.success(f"✅ **EXPIRY**: Current Week Weekly Expiry ({expiry_date_str}, {dte} DTE)")

        c_early_entry = st.checkbox(
            f"⚡ Allow Early Entry (09:15 - 09:30 AM Opening Window) — {scrip_symbol}",
            value=st.session_state.get("allow_orb_early_entry", True),
            key=f"ui_early_entry_cb_{scrip_symbol}",
            help="When enabled, allows trade execution during the 09:15-09:30 AM opening range breakout formation when confluence exceeds institutional threshold."
        )
        st.session_state["allow_orb_early_entry"] = c_early_entry

        strike_options = ["Auto-Detect Best Strike", f"Lower ATM (₹{lower_atm})", f"Upper ATM (₹{upper_atm})"]
        pref_val = st.session_state.get(f"strike_selection_pref_{scrip_symbol}", st.session_state.get("strike_selection_pref", "Auto-Detect Best Strike"))
        idx_pref = 0
        if "Lower ATM" in pref_val:
            idx_pref = 1
        elif "Upper ATM" in pref_val:
            idx_pref = 2
        c_strike_pref = st.radio(
            f"Dual ATM Strike Preference — {scrip_symbol}",
            strike_options,
            index=idx_pref,
            key=f"ui_strike_pref_{scrip_symbol}"
        )
        if "Lower ATM" in c_strike_pref:
            st.session_state["strike_selection_pref"] = "Lower ATM"
            st.session_state[f"strike_selection_pref_{scrip_symbol}"] = "Lower ATM"
        elif "Upper ATM" in c_strike_pref:
            st.session_state["strike_selection_pref"] = "Upper ATM"
            st.session_state[f"strike_selection_pref_{scrip_symbol}"] = "Upper ATM"
        else:
            st.session_state["strike_selection_pref"] = "Auto-Detect Best Strike"
            st.session_state[f"strike_selection_pref_{scrip_symbol}"] = "Auto-Detect Best Strike"

        c_broker_ltp = st.number_input(
            f"Broker Option Premium Sync — {scrip_symbol} (0.0 = Auto Feed)",
            value=float(st.session_state.get(f"live_broker_ltp_{scrip_symbol}", 0.0)),
            step=0.05,
            key=f"ui_broker_ltp_{scrip_symbol}"
        )
        st.session_state[f"live_broker_ltp_{scrip_symbol}"] = c_broker_ltp
        st.session_state["live_broker_ltp"] = c_broker_ltp

        c_override = st.number_input(
            f"Breakout Buy Trigger Control — {scrip_symbol} (0.0 = Auto Pin)",
            value=float(st.session_state.get(f"custom_trigger_override_{scrip_symbol}", 0.0)),
            step=0.1,
            key=f"ui_trigger_override_{scrip_symbol}"
        )
        st.session_state[f"custom_trigger_override_{scrip_symbol}"] = c_override
        st.session_state["custom_trigger_override"] = c_override
        if st_button_stretch(f"🔄 Re-pin Trigger to Current Market ({scrip_symbol})", key=f"ui_repin_btn_{scrip_symbol}"):
            BreakoutTriggerManager.reset_trigger(atm_strike, recommended_contract_type, symbol=scrip_symbol)
            st.session_state[f"custom_trigger_override_{scrip_symbol}"] = 0.0
            st.session_state["custom_trigger_override"] = 0.0
            st.success(f"Trigger re-pinned for {scrip_symbol}!")
            st.rerun()

    with col_cfg_right:
        st.markdown(f"### ⚡ Real-Time Scenario Simulation Hub (9 Mock Events — {scrip_symbol})")
        st.caption(f"Select and force-trigger any scenario calibrated to {scrip_name} ({lot_size} Qty/Lot, Target +{c_target:.1f}p, SL -{c_sl:.1f}p).")

        sim_grid1, sim_grid2, sim_grid3 = st.columns(3)
        with sim_grid1:
            if st_button_stretch("🟡 1. ARMED", key="btn_sim_1"):
                st.session_state["sim_scenario"] = "1. Setup ARMED"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()
            if st_button_stretch("🎯 4. Target Hit", key="btn_sim_4"):
                st.session_state["sim_scenario"] = "4. Target Hit"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()
            if st_button_stretch("🔒 7. Auto-Square", key="btn_sim_7"):
                st.session_state["sim_scenario"] = "7. Auto-Square-Off"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()

        with sim_grid2:
            if st_button_stretch("🟢 2. BUY CALL", key="btn_sim_2"):
                st.session_state["sim_scenario"] = "2. Trade Entry Confirmed — BUY CALL"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()
            if st_button_stretch("🛑 5. Stop Loss", key="btn_sim_5"):
                st.session_state["sim_scenario"] = "5. Stop Loss Hit"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()
            if st_button_stretch("🛡️ 8. Chop Lock", key="btn_sim_8"):
                st.session_state["sim_scenario"] = "8. Choppiness Stand Down"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()

        with sim_grid3:
            if st_button_stretch("🔴 3. BUY PUT", key="btn_sim_3"):
                st.session_state["sim_scenario"] = "3. Trade Entry Confirmed — BUY PUT"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()
            if st_button_stretch("⚡ 6. Trailing SL", key="btn_sim_6"):
                st.session_state["sim_scenario"] = "6. Trailing SL"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()
            if st_button_stretch("🚨 9. Drawdown", key="btn_sim_9"):
                st.session_state["sim_scenario"] = "9. Max Daily Drawdown"
                st.session_state["sim_force_fire"] = True
                st.session_state["sim_run_id"] = str(int(datetime.now().timestamp()))
                st.rerun()

        col_fa1, col_fa2 = st.columns(2)
        with col_fa1:
            if st_button_stretch("🔄 Reset Alert Triggers", key="ui_sim_reset_btn"):
                for k in list(st.session_state.keys()):
                    if k.startswith("tg_sent_"):
                        st.session_state[k] = False
                st.session_state["sim_force_fire"] = False
                st.success("Alert triggers re-armed!")
        with col_fa2:
            if st_button_stretch("🛑 Exit Simulation Mode", key="ui_sim_exit_btn"):
                st.session_state["sim_scenario"] = "🟢 Live Market Flow"
                st.session_state["sim_force_fire"] = False
                st.rerun()

        if is_sim_active:
            st.info(f"⚡ **Active Simulation ({scrip_symbol})**: `{st.session_state.get('sim_scenario')}`")

        st.markdown("---")
        st.markdown("### 🕒 Session Clock Simulation & Broker/Telegram APIs")
        c_sim_time = st.checkbox("Simulate Session Time", value=st.session_state.get("simulated_time_mode", False), key="ui_sim_time_cb")
        st.session_state["simulated_time_mode"] = c_sim_time
        if c_sim_time:
            c_hour = st.slider("Hour (IST)", 9, 15, value=st.session_state.get("sim_hour", 10), key="ui_sim_hour")
            c_min = st.slider("Minute", 0, 59, value=st.session_state.get("sim_min", 15), key="ui_sim_min")
            st.session_state["sim_hour"] = c_hour
            st.session_state["sim_min"] = c_min
            st.info(f"🕒 Simulated Clock: **{c_hour:02d}:{c_min:02d} IST** • Phase: **{time_gate_msg}**")

        with st.expander("🔑 Groww API Authentication", expanded=False):
            with st.form("groww_tab_auth_form", clear_on_submit=False):
                api_key_in = st.text_input("API Key / Access Token", value=groww_feed.saved_api_key if hasattr(groww_feed, "saved_api_key") else "", type="password")
                totp_in = st.text_input("TOTP / Secret Key", type="password")
                submitted = st.form_submit_button("🔐 Authenticate")
                if submitted:
                    if api_key_in and api_key_in.strip():
                        conn_res = groww_feed.connect(api_key=api_key_in.strip(), totp=totp_in.strip() if totp_in else None)
                        if conn_res.get("status") == "SUCCESS":
                            st.success("Connected!")
                            st.rerun()
                        else:
                            st.error(conn_res.get("message", "Auth failed"))

        with st.expander("📲 Telegram Alerts Configuration", expanded=False):
            tg_cfg_tab = TelegramNotifier.load_config()
            tg_bot_token_in = st.text_input("Telegram Bot Token", value=tg_cfg_tab.get("bot_token", TelegramNotifier.DEFAULT_BOT_TOKEN), key="ui_tg_token")
            tg_chat_id_in = st.text_area("Telegram Chat ID(s)", value=tg_cfg_tab.get("chat_id", TelegramNotifier.DEFAULT_CHAT_ID), key="ui_tg_chat")
            tg_en_in = st.checkbox("Enable Entry Alerts", value=tg_cfg_tab.get("enabled", True), key="ui_tg_en")
            col_tg1, col_tg2 = st.columns(2)
            with col_tg1:
                if st_button_stretch("💾 Save Telegram Config", key="ui_save_tg"):
                    TelegramNotifier.save_config(tg_bot_token_in, tg_chat_id_in, tg_en_in)
                    st.success("Saved!")
            with col_tg2:
                if st_button_stretch("🧪 Test Broadcast", key="ui_test_tg"):
                    ok, msg = TelegramNotifier.send_test_alert(tg_bot_token_in, TelegramNotifier.parse_chat_ids(tg_chat_id_in))
                    if ok:
                        st.success(f"Sent: {msg}")
                    else:
                        st.error(f"Error: {msg}")

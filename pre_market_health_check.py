"""
Pre-Market 09:00 AM IST System Health Check & Operational Readiness Engine
========================================================================
Automated Daily Diagnostic Engine for Manoj Quant Trading System:
1. Validates Groww API token validity, user profile & available margin funds.
2. Performs Telegram bot handshake and test ping.
3. Resolves today's active benchmark index assignment (NIFTY vs SENSEX)
   and verifies the official NSE holiday calendar.
4. Auto-dispatches pre-market briefing alert at 09:00 AM IST.
"""

import os
import json
import time
import logging
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, Any, Optional, Tuple

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except Exception:
    from datetime import timezone
    IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEALTH_STATE_FILE = os.path.join(BASE_DIR, "pre_market_health_check_state.json")


class PreMarketHealthCheckEngine:
    """Automated Pre-Market 09:00 AM IST System Diagnostic Engine."""

    @classmethod
    def get_state(cls) -> Dict[str, Any]:
        """Loads persistent diagnostic state from disk."""
        if os.path.exists(HEALTH_STATE_FILE):
            try:
                with open(HEALTH_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.debug(f"Error loading health check state: {e}")
        return {
            "last_run_date": "",
            "last_run_time": "",
            "telegram_dispatched_date": "",
            "last_diagnostic": None
        }

    @classmethod
    def save_state(cls, state: Dict[str, Any]) -> None:
        """Persists health check state to disk."""
        try:
            with open(HEALTH_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist health check state: {e}")

    @classmethod
    def check_market_calendar_status(cls, now_dt: Optional[datetime] = None) -> Dict[str, Any]:
        """Validates today's trading calendar, holiday status, and daily index mandate."""
        if now_dt is None:
            now_dt = datetime.now(IST)

        from nse_calendar import nse_calendar
        from asset_config import get_daily_asset_schedule

        cal_stat = nse_calendar.is_market_open_today(now_dt)
        sched = get_daily_asset_schedule(now_dt)

        is_trading_day = not cal_stat.get("is_holiday", False) and not cal_stat.get("is_weekend", False)
        holiday_desc = cal_stat.get("holiday_name") or (
            f"Weekend Market Closure ({sched.get('weekday_name', 'Weekend')})"
            if cal_stat.get("is_weekend") else None
        )

        return {
            "is_trading_day": is_trading_day,
            "session_status": cal_stat.get("status", "UNKNOWN"),
            "session_label": cal_stat.get("status_label", "Session Status"),
            "holiday_name": holiday_desc,
            "weekday_name": sched.get("weekday_name", ""),
            "active_symbol": sched.get("active_symbol", "MARKET_CLOSED"),
            "active_lots": sched.get("active_lots", 0),
            "locked_symbol": sched.get("locked_symbol", "MARKET_CLOSED"),
            "schedule_label": sched.get("schedule_label", ""),
            "schedule_rule": sched.get("schedule_rule", "")
        }

    @classmethod
    def check_groww_status(cls) -> Dict[str, Any]:
        """Validates Groww broker API connectivity, access token, and available cash."""
        t_start = time.time()
        try:
            from groww_market_feed import GrowwMarketFeed
            feed = GrowwMarketFeed.get_instance()
            is_conn = feed.is_connected
            profile = feed.user_profile if is_conn else None

            latency_ms = round((time.time() - t_start) * 1000.0, 1)

            if is_conn and profile:
                user_name = profile.get("name") or profile.get("user_name") or "Verified Trader"
                user_email = profile.get("email") or ""
                wallet = feed.get_wallet_balance()
                cash_avail = wallet.get("net_available", 0.0)
                margin_avail = wallet.get("margin_available", cash_avail)
                return {
                    "status": "ONLINE",
                    "badge": "🟢 CONNECTED",
                    "latency_ms": latency_ms,
                    "user_name": user_name,
                    "user_email": user_email,
                    "cash_available": cash_avail,
                    "margin_available": margin_avail,
                    "message": f"Connected as {user_name} • Available Funds: ₹{cash_avail:,.2f}"
                }
            else:
                cfg_file = os.path.join(BASE_DIR, "groww_config.json")
                has_cfg = os.path.exists(cfg_file)
                err_msg = feed.last_error or "Token expired or not authenticated"
                return {
                    "status": "OFFLINE",
                    "badge": "🔴 DISCONNECTED",
                    "latency_ms": latency_ms,
                    "has_config": has_cfg,
                    "error": err_msg,
                    "message": "Groww API token requires renewal. Please enter valid token in sidebar."
                }
        except Exception as e:
            return {
                "status": "ERROR",
                "badge": "🔴 ERROR",
                "latency_ms": round((time.time() - t_start) * 1000.0, 1),
                "error": str(e),
                "message": f"Broker check exception: {e}"
            }

    @classmethod
    def check_telegram_status(cls) -> Dict[str, Any]:
        """Validates Telegram bot handshake and push notification latency."""
        t_start = time.time()
        try:
            from telegram_notifier import TelegramNotifier
            cfg = TelegramNotifier.load_config()
            token = cfg.get("bot_token", TelegramNotifier.DEFAULT_BOT_TOKEN)
            chat = cfg.get("chat_id", TelegramNotifier.DEFAULT_CHAT_ID)
            enabled = cfg.get("enabled", True)

            if not enabled:
                return {
                    "status": "DISABLED",
                    "badge": "⚪ MUTED",
                    "latency_ms": 0.0,
                    "message": "Telegram push notifications disabled in settings."
                }

            if not token or not chat:
                return {
                    "status": "OFFLINE",
                    "badge": "🔴 UNCONFIGURED",
                    "latency_ms": 0.0,
                    "message": "Telegram bot token or chat ID missing in configuration."
                }

            # Test connection handshake
            ok, bot_name = TelegramNotifier.test_bot_handshake(token)
            latency_ms = round((time.time() - t_start) * 1000.0, 1)

            if ok:
                return {
                    "status": "ONLINE",
                    "badge": "🟢 CONNECTED",
                    "latency_ms": latency_ms,
                    "bot_name": bot_name,
                    "message": f"Connected to {bot_name} ({latency_ms}ms response)"
                }
            else:
                return {
                    "status": "WARNING",
                    "badge": "🟡 HANDSHAKE ERROR",
                    "latency_ms": latency_ms,
                    "error": bot_name,
                    "message": f"Telegram handshake failed: {bot_name}"
                }
        except Exception as e:
            return {
                "status": "ERROR",
                "badge": "🔴 ERROR",
                "latency_ms": round((time.time() - t_start) * 1000.0, 1),
                "error": str(e),
                "message": f"Telegram check error: {e}"
            }

    @classmethod
    def run_diagnostics(cls, send_telegram: bool = False, force: bool = False) -> Dict[str, Any]:
        """
        Runs comprehensive 09:00 AM IST pre-market diagnostics.
        Validates Groww broker feed, Telegram handshake, and active daily index schedule.
        """
        now = datetime.now(IST)
        today_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%I:%M:%S %p IST")

        # 1. Calendar & Asset Schedule Check
        cal_res = cls.check_market_calendar_status(now)

        # 2. Groww Broker Feed Check
        gw_res = cls.check_groww_status()

        # 3. Telegram Handshake Check
        tg_res = cls.check_telegram_status()

        # Determine overall readiness
        all_online = (gw_res.get("status") == "ONLINE") and (tg_res.get("status") in ("ONLINE", "DISABLED"))
        if not cal_res.get("is_trading_day"):
            readiness_code = "MARKET_CLOSED"
            readiness_badge = "🛑 EXCHANGE CLOSED"
            readiness_desc = f"Exchange Closed: {cal_res.get('holiday_name', 'Holiday / Weekend')}"
            combat_ready = False
        elif all_online:
            readiness_code = "COMBAT_READY"
            readiness_badge = "🟢 100% COMBAT READY"
            readiness_desc = f"All systems operational. Ready for 09:15 AM Open ({cal_res.get('schedule_label', '')})."
            combat_ready = True
        else:
            readiness_code = "ACTION_REQUIRED"
            readiness_badge = "🟡 ACTION REQUIRED"
            issues = []
            if gw_res.get("status") != "ONLINE":
                issues.append("Groww Token Inactive")
            if tg_res.get("status") not in ("ONLINE", "DISABLED"):
                issues.append("Telegram Handshake Pending")
            readiness_desc = " • ".join(issues)
            combat_ready = False

        diagnostic = {
            "check_date": today_str,
            "check_time": time_str,
            "readiness_code": readiness_code,
            "readiness_badge": readiness_badge,
            "readiness_desc": readiness_desc,
            "combat_ready": combat_ready,
            "calendar": cal_res,
            "groww": gw_res,
            "telegram": tg_res
        }

        # Auto-dispatch logic:
        # If time is 09:00 AM or later on a trading day, and hasn't yet been dispatched today
        state = cls.get_state()
        state["last_run_date"] = today_str
        state["last_run_time"] = time_str
        state["last_diagnostic"] = diagnostic

        is_post_9am = (now.hour > 9) or (now.hour == 9 and now.minute >= 0)
        has_dispatched_today = (state.get("telegram_dispatched_date") == today_str)

        should_dispatch = force or send_telegram or (is_post_9am and not has_dispatched_today and cal_res.get("is_trading_day"))

        if should_dispatch and tg_res.get("status") == "ONLINE":
            briefing_text = cls.format_telegram_briefing(diagnostic)
            try:
                from telegram_notifier import TelegramNotifier
                cfg = TelegramNotifier.load_config()
                tok = cfg.get("bot_token", TelegramNotifier.DEFAULT_BOT_TOKEN)
                chat = cfg.get("chat_id", TelegramNotifier.DEFAULT_CHAT_ID)
                TelegramNotifier.send_message(tok, chat, briefing_text)
                state["telegram_dispatched_date"] = today_str
                diagnostic["telegram_dispatched"] = True
            except Exception as e:
                logger.warning(f"Failed to dispatch 09:00 AM pre-market Telegram health check: {e}")
                diagnostic["telegram_dispatched"] = False
        else:
            diagnostic["telegram_dispatched"] = has_dispatched_today

        cls.save_state(state)
        return diagnostic

    @classmethod
    def format_telegram_briefing(cls, diag: Dict[str, Any]) -> str:
        """Formats an executive institutional pre-market readiness dispatch for Telegram."""
        cal = diag.get("calendar", {})
        gw = diag.get("groww", {})
        tg = diag.get("telegram", {})
        badge = diag.get("readiness_badge", "")

        msg = (
            f"⚡ *MANOJ QUANT ENGINE — 09:00 AM PRE-MARKET HEALTH CHECK*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Date:* {diag.get('check_date')} | *Time:* {diag.get('check_time')}\n"
            f"🎯 *System Status:* {badge}\n\n"
            f"📊 *DAILY MANDATE & EXCHANGE SCHEDULE*\n"
            f"• *Active Index:* `{cal.get('active_symbol', 'N/A')}` ({cal.get('active_lots', 0)} Lots)\n"
            f"• *Rule:* {cal.get('schedule_rule', 'Standard Weekly Schedule')}\n"
        )

        if not cal.get("is_trading_day"):
            msg += f"• *Market Note:* 🛑 {cal.get('holiday_name', 'Exchange Closed Today')}\n"
        else:
            msg += f"• *Session:* 🟢 Normal Session • Opens at 09:15 AM IST\n"

        msg += (
            f"\n🔌 *BROKER & NOTIFICATION TELEMETRY*\n"
            f"• *Groww API:* {gw.get('badge', 'N/A')} ({gw.get('latency_ms', 0)}ms)\n"
            f"  _{gw.get('message', '')}_\n"
            f"• *Telegram Alert Gateway:* {tg.get('badge', 'N/A')} ({tg.get('latency_ms', 0)}ms)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        if diag.get("combat_ready"):
            msg += f"🚀 *VERDICT:* Ready for market open at 09:15 AM IST. Good luck!"
        elif not cal.get("is_trading_day"):
            msg += f"🛑 *VERDICT:* Exchange closed today. Desks suspended."
        else:
            msg += f"⚠️ *VERDICT:* Attention required on broker/alert connection before 09:15 AM."

        return msg

    @classmethod
    def render_diagnostic_card(cls, container: Any = None, compact: bool = False, key_prefix: str = ""):
        """
        Renders an interactive, glassmorphic Pre-Market Diagnostic Card in Streamlit.
        Supports both full wide-banner mode (homepage) and compact card mode (sidebar/desk).
        """
        import streamlit as st
        ctx = container if container is not None else st
        k_pfx = f"{key_prefix}_" if key_prefix else ""

        state = cls.get_state()
        diag = state.get("last_diagnostic")
        today_str = datetime.now(IST).strftime("%Y-%m-%d")

        if not diag or state.get("last_run_date") != today_str:
            diag = cls.run_diagnostics()

        gw = diag.get("groww", {})
        tg = diag.get("telegram", {})
        cal = diag.get("calendar", {})
        ready_code = diag.get("readiness_code", "UNKNOWN")
        badge = diag.get("readiness_badge", "DIAGNOSTIC ACTIVE")

        bg_border = (
            "rgba(16, 185, 129, 0.45)" if ready_code == "COMBAT_READY" else (
                "rgba(100, 116, 139, 0.40)" if ready_code == "MARKET_CLOSED" else "rgba(245, 158, 11, 0.45)"
            )
        )
        bg_gradient = (
            "linear-gradient(135deg, rgba(6, 78, 59, 0.35) 0%, rgba(15, 23, 42, 0.70) 100%)" if ready_code == "COMBAT_READY" else (
                "linear-gradient(135deg, rgba(30, 41, 59, 0.45) 0%, rgba(15, 23, 42, 0.70) 100%)" if ready_code == "MARKET_CLOSED" else
                "linear-gradient(135deg, rgba(120, 53, 15, 0.35) 0%, rgba(15, 23, 42, 0.70) 100%)"
            )
        )

        if compact:
            with ctx.container():
                st.html(f"""
                <div style="background: {bg_gradient}; border: 1.5px solid {bg_border}; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; box-shadow: 0 4px 14px rgba(0,0,0,0.35);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 0.82rem; font-weight: 800; color: #FFFFFF;">🩺 09:00 AM HEALTH CHECK</span>
                        <span style="font-size: 0.70rem; font-weight: 800; color: {'#34D399' if ready_code == 'COMBAT_READY' else ('#94A3B8' if ready_code == 'MARKET_CLOSED' else '#FCD34D')};">{badge}</span>
                    </div>
                    <div style="font-size: 0.70rem; color: #94A3B8; margin-bottom: 6px; line-height: 1.4;">
                        {diag.get('readiness_desc', '')}
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 4px; font-size: 0.70rem; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 6px;">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="color: #94A3B8;">Groww Broker:</span>
                            <span style="font-weight: 700; color: {'#34D399' if gw.get('status') == 'ONLINE' else '#F87171'};">{gw.get('badge')} ({gw.get('latency_ms', 0)}ms)</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span style="color: #94A3B8;">Telegram Bot:</span>
                            <span style="font-weight: 700; color: {'#34D399' if tg.get('status') == 'ONLINE' else ('#94A3B8' if tg.get('status') == 'DISABLED' else '#F87171')};">{tg.get('badge')}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span style="color: #94A3B8;">Active Asset:</span>
                            <span style="font-weight: 700; color: #38BDF8;">{cal.get('active_symbol', 'N/A')} ({cal.get('active_lots', 0)} Lots)</span>
                        </div>
                    </div>
                </div>
                """)
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔄 Check", key=f"{k_pfx}btn_compact_diag", width="stretch", help="Re-run pre-market diagnostic checks now"):
                        cls.run_diagnostics(force=True)
                        st.toast("✅ Pre-market system diagnostics executed!")
                        st.rerun()
                with col_btn2:
                    if st.button("📲 Ping", key=f"{k_pfx}btn_compact_tg", width="stretch", help="Dispatch pre-market briefing alert to Telegram"):
                        cls.run_diagnostics(send_telegram=True, force=True)
                        st.toast("📲 Pre-market briefing dispatched to Telegram!")
                        st.rerun()
            return

        with ctx.container():
            st.html(f"""
            <div style="background: {bg_gradient}; border: 1.5px solid {bg_border}; border-radius: 10px; padding: 12px 18px; margin-bottom: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 1.25rem;">🩺</span>
                        <div>
                            <div style="font-size: 0.86rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.3px;">
                                PRE-MARKET 09:00 AM HEALTH CHECK &bull; <span style="color: {'#34D399' if ready_code == 'COMBAT_READY' else ('#E2E8F0' if ready_code == 'MARKET_CLOSED' else '#FCD34D')};">{badge}</span>
                            </div>
                            <div style="font-size: 0.73rem; color: #94A3B8; margin-top: 2px;">
                                {diag.get('readiness_desc', '')} &bull; Checked: <b style="color: #CBD5E1;">{diag.get('check_time', '')}</b>
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                        <span style="background: rgba(0,0,0,0.3); border: 1px solid #334155; padding: 3px 8px; border-radius: 6px; font-size: 0.72rem; color: #E2E8F0;">
                            🔌 Groww: <b style="color: {'#34D399' if gw.get('status') == 'ONLINE' else '#F87171'};">{gw.get('badge')}</b>
                        </span>
                        <span style="background: rgba(0,0,0,0.3); border: 1px solid #334155; padding: 3px 8px; border-radius: 6px; font-size: 0.72rem; color: #E2E8F0;">
                            📡 Telegram: <b style="color: {'#34D399' if tg.get('status') == 'ONLINE' else ('#94A3B8' if tg.get('status') == 'DISABLED' else '#F87171')};">{tg.get('badge')}</b>
                        </span>
                        <span style="background: rgba(0,0,0,0.3); border: 1px solid #334155; padding: 3px 8px; border-radius: 6px; font-size: 0.72rem; color: #E2E8F0;">
                            🎯 Active: <b style="color: #38BDF8;">{cal.get('active_symbol', 'N/A')}</b> ({cal.get('active_lots', 0)} Lots)
                        </span>
                    </div>
                </div>
            </div>
            """)

            with st.expander("🔍 Pre-Market Health Check Telemetry & Diagnostic Controls", expanded=False):
                col_d1, col_d2 = st.columns([3, 1.2])
                with col_d1:
                    st.markdown(f"""
                    • **Broker API Telemetry:** {gw.get('message', '')}  
                    • **Telegram Gateway:** {tg.get('message', '')}  
                    • **Mandate Schedule Rule:** {cal.get('schedule_rule', '')}  
                    • **09:00 AM Dispatch Status:** {'✅ Briefing Dispatched to Telegram' if diag.get('telegram_dispatched') else '⏳ Awaiting / Manual Dispatch'}
                    """)
                with col_d2:
                    if st.button("🔄 Run Diagnostics Now", key=f"{k_pfx}btn_run_diag_now", width="stretch"):
                        cls.run_diagnostics(force=True)
                        st.toast("✅ Pre-market system diagnostics executed successfully!")
                        st.rerun()
                    if st.button("📲 Send Briefing to Telegram", key=f"{k_pfx}btn_send_diag_tg", width="stretch"):
                        cls.run_diagnostics(send_telegram=True, force=True)
                        st.toast("📲 Pre-market briefing dispatched to Telegram!")
                        st.rerun()

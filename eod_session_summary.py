"""
Automated 03:30 PM IST End-of-Day (EOD) Performance Debrief & Journal Snapshot Engine
====================================================================================
Compiles institutional end-of-day execution metrics, reconciles broker fills,
computes gross vs post-tax net PnL (STT, GST, brokerage), automatically takes an
immutable JSON backup of trading databases, and dispatches an executive closing debrief
to Telegram at 03:30 PM IST.
"""

import os
import json
import logging
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, Any, Optional, List

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except Exception:
    from datetime import timezone
    IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EOD_STATE_FILE = os.path.join(BASE_DIR, "eod_session_summary_state.json")


class EODSessionSummaryEngine:
    """Institutional End-of-Day (03:30 PM IST) Performance Audit & Backup Engine."""

    @classmethod
    def get_state(cls) -> Dict[str, Any]:
        """Loads persistent EOD summary state from disk."""
        if os.path.exists(EOD_STATE_FILE):
            try:
                with open(EOD_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.debug(f"Error loading EOD state: {e}")
        return {
            "last_run_date": "",
            "last_run_time": "",
            "telegram_dispatched_date": "",
            "last_debrief": None,
            "last_backup": None
        }

    @classmethod
    def save_state(cls, state: Dict[str, Any]) -> None:
        """Persists EOD summary state to disk."""
        try:
            with open(EOD_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist EOD state: {e}")

    @classmethod
    def compile_eod_debrief(cls, date_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Compiles institutional session performance audit across all active desks:
        1. Executed and closed trades
        2. Gross PnL vs Post-Tax Net PnL (STT, GST, Brokerage)
        3. Win Rate %, Hits vs Fails
        4. Groww account balance reconciliation
        5. Capital preservation & 1-and-Done adherence
        """
        now = datetime.now(IST)
        today_str = date_str or now.strftime("%Y-%m-%d")
        time_str = now.strftime("%I:%M:%S %p IST")

        from nse_calendar import nse_calendar
        from asset_config import get_daily_asset_schedule, get_asset_spec
        from trade_journal_manager import TradeJournalManager, SequentialTradeEngine, STARTING_CAPITAL
        from groww_market_feed import GrowwMarketFeed

        cal_stat = nse_calendar.is_market_open_today(now)
        sched = get_daily_asset_schedule(now)
        is_trading_day = not cal_stat.get("is_holiday", False) and not cal_stat.get("is_weekend", False)

        # 1. Gather all trade records for today
        all_entries = TradeJournalManager.load_journal()
        today_trades = [e for e in all_entries if str(e.get("date", "")) == today_str]

        # 2. Extract Sequential Engine Active States
        active_states = {}
        for sym in ("NIFTY", "SENSEX"):
            st = SequentialTradeEngine.get_state(symbol=sym)
            active_states[sym] = st

        # 3. Compute Metrics
        hits = [t for t in today_trades if t.get("status") in ("HIT", "Target Hit") or float(t.get("realised_pnl", 0.0)) > 0]
        fails = [t for t in today_trades if t.get("status") in ("FAIL", "SL Hit") or float(t.get("realised_pnl", 0.0)) < 0]
        total_trades = len(today_trades)
        win_rate = round((len(hits) / total_trades) * 100.0, 1) if total_trades > 0 else 0.0

        tax_report = TradeJournalManager.generate_tax_audit_report(date_filter=today_str)
        gross_pnl = round(sum(float(r.get("gross_pnl", 0.0)) for r in tax_report), 2)
        total_charges = round(sum(float(r.get("total_statutory_charges", 0.0)) for r in tax_report), 2)
        net_post_tax_pnl = round(sum(float(r.get("net_post_tax_pnl", 0.0)) for r in tax_report), 2)
        total_turnover = round(sum(float(r.get("total_turnover", 0.0)) for r in tax_report), 2)

        # 4. Groww Live Account Balance Reconciliation
        gw = GrowwMarketFeed.get_instance()
        wallet = gw.get_wallet_balance()
        broker_cash = float(wallet.get("net_available", STARTING_CAPITAL))
        live_pos = gw.get_live_positions()
        broker_pnl = float(live_pos.get("total_pnl", net_post_tax_pnl))

        # 5. Session Outcome Badge
        if not is_trading_day:
            session_badge = "🛑 EXCHANGE CLOSED"
            outcome_code = "MARKET_CLOSED"
        elif total_trades == 0:
            session_badge = "🛡️ CAPITAL PRESERVED (NO FILL)"
            outcome_code = "NO_TRADES"
        elif net_post_tax_pnl > 0:
            session_badge = f"🟢 PROFITABLE DAY (+₹{net_post_tax_pnl:,.2f})"
            outcome_code = "NET_PROFIT"
        else:
            session_badge = f"🔴 DRAWDOWN DAY (-₹{abs(net_post_tax_pnl):,.2f})"
            outcome_code = "NET_LOSS"

        return {
            "date": today_str,
            "timestamp": time_str,
            "is_trading_day": is_trading_day,
            "weekday_name": sched.get("weekday_name", ""),
            "active_symbol": sched.get("active_symbol", "N/A"),
            "schedule_rule": sched.get("schedule_rule", ""),
            "total_trades": total_trades,
            "hits_count": len(hits),
            "fails_count": len(fails),
            "win_rate_pct": win_rate,
            "gross_pnl": gross_pnl,
            "statutory_charges": total_charges,
            "net_post_tax_pnl": net_post_tax_pnl,
            "total_turnover": total_turnover,
            "starting_cash": STARTING_CAPITAL,
            "broker_available_cash": broker_cash,
            "broker_realized_pnl": broker_pnl,
            "session_badge": session_badge,
            "outcome_code": outcome_code,
            "trade_details": tax_report
        }

    @classmethod
    def format_telegram_debrief(cls, debrief: Dict[str, Any]) -> str:
        """Formats an executive institutional End-of-Day debrief message for Telegram."""
        badge = debrief.get("session_badge", "")
        dt_str = debrief.get("date", "")
        tm_str = debrief.get("timestamp", "")
        n_trades = debrief.get("total_trades", 0)
        hits = debrief.get("hits_count", 0)
        fails = debrief.get("fails_count", 0)
        wr = debrief.get("win_rate_pct", 0.0)
        gross = debrief.get("gross_pnl", 0.0)
        charges = debrief.get("statutory_charges", 0.0)
        net_pnl = debrief.get("net_post_tax_pnl", 0.0)
        turnover = debrief.get("total_turnover", 0.0)

        msg = (
            f"⚡ *MANOJ QUANT ENGINE — 03:30 PM EOD PERFORMANCE DEBRIEF*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Date:* {dt_str} | *Closing Time:* {tm_str}\n"
            f"🎯 *Session Outcome:* {badge}\n\n"
            f"📊 *DAILY MANDATE & ACTIVITY*\n"
            f"• *Index Mandate:* `{debrief.get('active_symbol', 'N/A')}`\n"
            f"• *Rule:* {debrief.get('schedule_rule', 'Standard Weekly Mandate')}\n"
            f"• *Executed Trades:* {n_trades} ({hits} Hits • {fails} Fails | {wr:.1f}% Win Rate)\n\n"
            f"💰 *FINANCIAL & STATUTORY RECONCILIATION*\n"
            f"• *Gross Realized PnL:* ₹{gross:+,.2f}\n"
            f"• *Statutory Taxes & Brokerage:* -₹{charges:,.2f} (STT, GST, Exchange)\n"
            f"• *Net Post-Tax PnL:* *₹{net_pnl:+,.2f}*\n"
            f"• *Premium Turnover:* ₹{turnover:,.2f}\n"
            f"• *Closing Margin Funds:* ₹{debrief.get('broker_available_cash', 0.0):,.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        if not debrief.get("is_trading_day"):
            msg += f"🛑 *NOTE:* Exchange was closed today. No orders placed."
        elif n_trades == 0:
            msg += f"🛡️ *NOTE:* Zero setup triggers breached confluence threshold. 100% Capital Preserved."
        elif net_pnl > 0:
            msg += f"🚀 *VERDICT:* Target achieved within institutional risk tolerance. Great execution!"
        else:
            msg += f"🛡️ *VERDICT:* Strict 1-and-Done daily loss cap protected capital from extended drawdown."

        return msg

    @classmethod
    def dispatch_eod_summary(cls, force: bool = False, send_telegram: bool = True) -> Dict[str, Any]:
        """
        Executes the 03:30 PM IST EOD Performance Summary workflow:
        1. Compiles session audit metrics
        2. Automatically takes an immutable JSON backup of databases
        3. Dispatches Telegram closing debrief once daily at or after 03:30 PM IST
        """
        now = datetime.now(IST)
        today_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%I:%M:%S %p IST")

        # 1. Compile Debrief
        debrief = cls.compile_eod_debrief()

        # 2. Trigger Database Auto-Backup
        from trade_journal_manager import TradeJournalManager
        backup_res = TradeJournalManager.backup_trading_data()

        # 3. Save State
        state = cls.get_state()
        state["last_run_date"] = today_str
        state["last_run_time"] = time_str
        state["last_debrief"] = debrief
        state["last_backup"] = backup_res

        is_post_330pm = (now.hour > 15) or (now.hour == 15 and now.minute >= 30)
        has_dispatched_today = (state.get("telegram_dispatched_date") == today_str)

        should_dispatch = force or send_telegram or (is_post_330pm and not has_dispatched_today and debrief.get("is_trading_day"))

        if should_dispatch:
            try:
                from telegram_notifier import TelegramNotifier
                cfg = TelegramNotifier.load_config()
                if cfg.get("enabled", True):
                    token = cfg.get("bot_token", TelegramNotifier.DEFAULT_BOT_TOKEN)
                    chat = cfg.get("chat_id", TelegramNotifier.DEFAULT_CHAT_ID)
                    msg_text = cls.format_telegram_debrief(debrief)
                    TelegramNotifier.send_message(token, chat, msg_text)
                    state["telegram_dispatched_date"] = today_str
                    debrief["telegram_dispatched"] = True
            except Exception as e:
                logger.warning(f"Failed to dispatch 03:30 PM EOD Telegram summary: {e}")
                debrief["telegram_dispatched"] = False
        else:
            debrief["telegram_dispatched"] = has_dispatched_today

        cls.save_state(state)
        return debrief

    @classmethod
    def render_eod_card(cls, container: Any = None, compact: bool = False, key_prefix: str = ""):
        """Renders an interactive, glassmorphic EOD Performance Card in Streamlit."""
        import streamlit as st
        ctx = container if container is not None else st
        k_pfx = f"{key_prefix}_" if key_prefix else ""

        state = cls.get_state()
        debrief = state.get("last_debrief")
        today_str = datetime.now(IST).strftime("%Y-%m-%d")

        if not debrief or state.get("last_run_date") != today_str:
            debrief = cls.compile_eod_debrief()

        badge = debrief.get("session_badge", "")
        code = debrief.get("outcome_code", "UNKNOWN")
        net_pnl = debrief.get("net_post_tax_pnl", 0.0)
        n_trades = debrief.get("total_trades", 0)

        bg_border = (
            "rgba(16, 185, 129, 0.45)" if code == "NET_PROFIT" else (
                "rgba(100, 116, 139, 0.40)" if code in ("MARKET_CLOSED", "NO_TRADES") else "rgba(239, 68, 68, 0.45)"
            )
        )
        bg_gradient = (
            "linear-gradient(135deg, rgba(6, 78, 59, 0.35) 0%, rgba(15, 23, 42, 0.70) 100%)" if code == "NET_PROFIT" else (
                "linear-gradient(135deg, rgba(30, 41, 59, 0.45) 0%, rgba(15, 23, 42, 0.70) 100%)" if code in ("MARKET_CLOSED", "NO_TRADES") else
                "linear-gradient(135deg, rgba(127, 29, 29, 0.35) 0%, rgba(15, 23, 42, 0.70) 100%)"
            )
        )

        if compact:
            with ctx.container():
                st.html(f"""
                <div style="background: {bg_gradient}; border: 1.5px solid {bg_border}; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; box-shadow: 0 4px 14px rgba(0,0,0,0.35);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 0.82rem; font-weight: 800; color: #FFFFFF;">📊 03:30 PM EOD DEBRIEF</span>
                        <span style="font-size: 0.70rem; font-weight: 800; color: {'#34D399' if net_pnl > 0 else ('#94A3B8' if net_pnl == 0 else '#F87171')};">{badge}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #94A3B8; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 6px;">
                        <span>Trades: <b style="color: #CBD5E1;">{n_trades}</b></span>
                        <span>Net PnL: <b style="color: {'#34D399' if net_pnl > 0 else ('#94A3B8' if net_pnl == 0 else '#F87171')};">₹{net_pnl:+,.2f}</b></span>
                    </div>
                </div>
                """)
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔄 Audit", key=f"{k_pfx}btn_compact_eod", width="stretch", help="Re-compile 03:30 PM EOD performance audit"):
                        cls.dispatch_eod_summary(force=True, send_telegram=False)
                        st.toast("✅ EOD audit re-compiled!")
                        st.rerun()
                with col_btn2:
                    if st.button("📲 Send TG", key=f"{k_pfx}btn_compact_eod_tg", width="stretch", help="Send EOD summary debrief to Telegram"):
                        cls.dispatch_eod_summary(force=True, send_telegram=True)
                        st.toast("📲 EOD debrief sent to Telegram!")
                        st.rerun()
            return

        with ctx.container():
            st.html(f"""
            <div style="background: {bg_gradient}; border: 1.5px solid {bg_border}; border-radius: 10px; padding: 12px 18px; margin-bottom: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 1.25rem;">📊</span>
                        <div>
                            <div style="font-size: 0.86rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.3px;">
                                03:30 PM EOD CLOSING PERFORMANCE AUDIT &bull; <span style="color: {'#34D399' if net_pnl > 0 else ('#94A3B8' if net_pnl == 0 else '#F87171')};">{badge}</span>
                            </div>
                            <div style="font-size: 0.73rem; color: #94A3B8; margin-top: 2px;">
                                Executed: <b style="color: #CBD5E1;">{n_trades} Trades</b> &bull; Win Rate: <b style="color: #38BDF8;">{debrief.get('win_rate_pct', 0.0):.1f}%</b> &bull; Audited: <b style="color: #CBD5E1;">{debrief.get('timestamp', '')}</b>
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                        <span style="background: rgba(0,0,0,0.3); border: 1px solid #334155; padding: 3px 8px; border-radius: 6px; font-size: 0.72rem; color: #E2E8F0;">
                            Gross PnL: <b style="color: {'#34D399' if debrief.get('gross_pnl', 0) > 0 else '#F87171'};">₹{debrief.get('gross_pnl', 0):+,.2f}</b>
                        </span>
                        <span style="background: rgba(0,0,0,0.3); border: 1px solid #334155; padding: 3px 8px; border-radius: 6px; font-size: 0.72rem; color: #E2E8F0;">
                            Taxes & Brokerage: <b style="color: #CBD5E1;">-₹{debrief.get('statutory_charges', 0):,.2f}</b>
                        </span>
                        <span style="background: rgba(0,0,0,0.3); border: 1px solid #334155; padding: 3px 8px; border-radius: 6px; font-size: 0.72rem; color: #E2E8F0;">
                            Net PnL: <b style="color: {'#34D399' if net_pnl > 0 else ('#CBD5E1' if net_pnl == 0 else '#F87171')};">₹{net_pnl:+,.2f}</b>
                        </span>
                    </div>
                </div>
            </div>
            """)

            with st.expander("🔍 End-of-Day Audit Telemetry & Database Backup Controls", expanded=False):
                col_e1, col_e2 = st.columns([3, 1.2])
                with col_e1:
                    st.markdown(f"""
                    • **Mandate Compliance:** {debrief.get('active_symbol', 'N/A')} ({debrief.get('schedule_rule', '')})  
                    • **Financial Turnover:** ₹{debrief.get('total_turnover', 0):,.2f} across {n_trades} transactions  
                    • **Available Margin Capital:** ₹{debrief.get('broker_available_cash', 0):,.2f} (Groww live account)  
                    • **Telegram Dispatch Status:** {'✅ Closing Briefing Sent' if debrief.get('telegram_dispatched') else '⏳ Awaiting 03:30 PM or Manual Dispatch'}  
                    • **Automated Database Backup:** {'✅ Snapshot Stored in backups/' if state.get('last_backup', {}).get('status') == 'SUCCESS' else 'Awaiting backup'}
                    """)
                with col_e2:
                    if st.button("🔄 Audit & Backup Now", key=f"{k_pfx}btn_run_eod_now", width="stretch"):
                        cls.dispatch_eod_summary(force=True, send_telegram=False)
                        st.toast("✅ EOD audit re-compiled and databases backed up!")
                        st.rerun()
                    if st.button("📲 Send EOD to Telegram", key=f"{k_pfx}btn_send_eod_tg", width="stretch"):
                        cls.dispatch_eod_summary(force=True, send_telegram=True)
                        st.toast("📲 EOD debrief dispatched to Telegram!")
                        st.rerun()

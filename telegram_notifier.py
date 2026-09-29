"""
Telegram Trade Alert Module for RELIANCE Quantitative Intraday Engine
======================================================================
Provides zero-delay instant push notifications to Telegram when
trade entry triggers are confirmed, targets are hit, or SLs are reached.

Supports MULTI-USER BROADCAST & INTERACTIVE INLINE BUTTONS:
- Multiple individual Telegram users (comma/space/newline separated Chat IDs)
- Telegram Groups (Chat IDs starting with - or -100...)
- Telegram Channels (Chat IDs or @channel usernames)
- Interactive Action Buttons (Green BUY NOW on Groww, Yellow View Chain, Red Exit)
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Union
try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except Exception:
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))

try:
    import requests
except ImportError:
    requests = None
import urllib.request
import urllib.parse


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "telegram_config.json")
ALERT_LOG_FILE = os.path.join(os.path.dirname(__file__), "telegram_alert_log.json")


class TelegramNotifier:
    """Handles Telegram Bot communication and trade alerts for single or multiple users/groups."""

    ALERT_LOG_FILE = ALERT_LOG_FILE
    _alert_cache: Dict[str, float] = {}
    _alert_cache_loaded: bool = False

    @classmethod
    def load_alert_log(cls) -> Dict[str, float]:
        """Loads persistent alert dispatch records from disk, auto-pruning records older than 24 hours."""
        now = time.time()
        records: Dict[str, float] = {}
        if os.path.exists(ALERT_LOG_FILE):
            try:
                with open(ALERT_LOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        records = {str(k): float(v) for k, v in data.items() if (now - float(v)) < 86400}
            except Exception:
                records = {}
        cls._alert_cache = records
        cls._alert_cache_loaded = True
        return records

    @classmethod
    def save_alert_log(cls, records: Dict[str, float]) -> None:
        """Saves persistent alert dispatch records to disk."""
        try:
            with open(ALERT_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception:
            pass

    @classmethod
    def is_alert_sent(cls, alert_key: str, cooldown_seconds: int = 14400) -> bool:
        """
        Checks if an alert key has already been dispatched today / within cooldown.
        Survives browser tab refreshes, Streamlit reruns, and multi-session instances.
        """
        if not cls._alert_cache_loaded:
            cls.load_alert_log()
        now = time.time()
        last_ts = cls._alert_cache.get(alert_key)
        if last_ts is None:
            return False
        return (now - last_ts) < cooldown_seconds

    @classmethod
    def record_alert_sent(cls, alert_key: str) -> None:
        """
        Records that an alert key has been successfully dispatched.
        Persists to both memory cache and disk immediately.
        """
        if not cls._alert_cache_loaded:
            cls.load_alert_log()
        now = time.time()
        cls._alert_cache[alert_key] = now
        cls.save_alert_log(cls._alert_cache)

    @classmethod
    def clear_alert_log(cls) -> None:
        """Clears all logged alert keys (useful for manual reset or daily purge)."""
        cls._alert_cache = {}
        cls._alert_cache_loaded = True
        try:
            if os.path.exists(ALERT_LOG_FILE):
                os.remove(ALERT_LOG_FILE)
        except Exception:
            pass

    @staticmethod
    def parse_chat_ids(chat_ids_input: Any) -> List[str]:
        """
        Parses comma, semicolon, space, or newline-separated Chat IDs / Channel usernames.
        Returns a list of unique, cleaned chat ID strings.
        Supports:
          - Individual users: e.g. "1227818587"
          - Groups / Supergroups: e.g. "-100123456789", "-456789123"
          - Public Channels: e.g. "@reliance_trade_alerts"
        """
        if not chat_ids_input:
            return []

        if isinstance(chat_ids_input, list):
            raw_list = chat_ids_input
        elif isinstance(chat_ids_input, str):
            # Normalize common delimiters to commas
            cleaned = chat_ids_input.replace("\n", ",").replace(";", ",").replace(" ", ",")
            raw_list = cleaned.split(",")
        else:
            raw_list = [str(chat_ids_input)]

        unique_ids = []
        for item in raw_list:
            cid = str(item).strip()
            # Strip "ID:" prefix if present (e.g. "ID: -1004390764314")
            if cid.upper().startswith("ID:"):
                cid = cid[3:].strip()
            elif cid.upper().startswith("ID"):
                cid = cid[2:].strip()
            # Auto-correct Group / Supergroup IDs missing leading minus '-'
            if cid.isdigit() and len(cid) >= 12 and cid.startswith("100"):
                cid = f"-{cid}"
            elif cid.isdigit() and len(cid) >= 12:
                cid = f"-{cid}"
            if cid and cid not in unique_ids:
                unique_ids.append(cid)
        return unique_ids

    DEFAULT_BOT_TOKEN = "8575235859:AAEcIQX_k-MfdvKXvHTm38no-AcC0xC_QUk"
    DEFAULT_CHAT_ID = "-1004390764314"

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """Loads saved Telegram credentials and preferences with official hard-coded defaults."""
        config = {
            "bot_token": cls.DEFAULT_BOT_TOKEN,
            "chat_id": cls.DEFAULT_CHAT_ID,
            "enabled": True,
            "sound_alerts": True
        }

        # 1. Check Streamlit Secrets (for Streamlit Cloud deployment)
        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                if "telegram" in st.secrets:
                    config.update(dict(st.secrets["telegram"]))
                for k in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "bot_token", "chat_id"]:
                    if k in st.secrets:
                        norm_key = k.lower().replace("telegram_", "")
                        config[norm_key] = str(st.secrets[k]).strip()
        except Exception:
            pass

        # 2. Check environment variables
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            config["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"].strip()
        if os.environ.get("TELEGRAM_CHAT_ID"):
            config["chat_id"] = os.environ["TELEGRAM_CHAT_ID"].strip()

        # 3. Check local CONFIG_FILE if exists
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("bot_token"):
                        config["bot_token"] = data["bot_token"].strip()
                    if data.get("chat_id"):
                        if isinstance(data["chat_id"], list):
                            config["chat_id"] = ", ".join(data["chat_id"])
                        else:
                            config["chat_id"] = str(data["chat_id"]).strip()
                    if "enabled" in data:
                        config["enabled"] = bool(data["enabled"])
            except Exception:
                pass

        return config

    @staticmethod
    def save_config(bot_token: str, chat_id: Union[str, List[str]], enabled: bool = True, sound_alerts: bool = True) -> bool:
        """Saves Telegram credentials to local config."""
        try:
            if isinstance(chat_id, list):
                cid_str = ", ".join(chat_id)
            else:
                cid_str = str(chat_id).strip()

            data = {
                "bot_token": bot_token.strip(),
                "chat_id": cid_str,
                "enabled": enabled,
                "sound_alerts": sound_alerts
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    @classmethod
    def send_single_message(cls, bot_token: str, chat_id: str, html_message: str, reply_markup: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Sends an HTML formatted message to a single Telegram Chat ID.
        Supports optional reply_markup for Telegram inline action buttons.
        Returns (success: bool, status_message: str).
        """
        token = bot_token.strip()
        cid = str(chat_id).strip()

        if not token or not cid:
            return False, "Bot Token and Chat ID are required."

        def _do_send(target_id: str):
            api_url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": target_id,
                "text": html_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup

            if requests is not None:
                resp = requests.post(api_url, json=payload, timeout=8)
                res_json = resp.json()
                if resp.status_code == 200 and res_json.get("ok"):
                    return True, "Delivered"
                else:
                    return False, res_json.get("description", resp.text)
            else:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=8) as response:
                    res_json = json.loads(response.read().decode("utf-8"))
                    if res_json.get("ok"):
                        return True, "Delivered"
                    else:
                        return False, res_json.get("description", "")

        try:
            ok, desc = _do_send(cid)
            if not ok and "chat not found" in desc.lower():
                if not cid.startswith("-") and cid.isdigit():
                    for alt_id in [f"-{cid}", f"-100{cid}"]:
                        ok_alt, _ = _do_send(alt_id)
                        if ok_alt:
                            return True, "Delivered"
            if ok:
                return True, "Delivered"
            else:
                return False, f"Telegram API Error ({cid}): {desc}"
        except Exception as e:
            return False, f"Network error ({cid}): {str(e)}"

    @classmethod
    def send_broadcast(cls, bot_token: str, chat_ids_input: Any, html_message: str, reply_markup: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Broadcasts an HTML formatted alert to multiple Telegram users, groups, or channels.
        Returns (success: bool, status_summary: str).
        """
        chat_ids = cls.parse_chat_ids(chat_ids_input)
        if not chat_ids:
            return False, "No valid Telegram Chat IDs provided."

        token = bot_token.strip()
        if not token:
            return False, "Telegram Bot Token is required."

        successes = []
        failures = []

        for cid in chat_ids:
            ok, msg = cls.send_single_message(token, cid, html_message, reply_markup=reply_markup)
            if ok:
                successes.append(cid)
            else:
                failures.append(f"{cid} ({msg})")

        total = len(chat_ids)
        if len(successes) == total:
            summary = f"Delivered to all {total} recipient(s) ({', '.join(successes)})"
            return True, summary
        elif len(successes) > 0:
            summary = f"Delivered to {len(successes)}/{total} recipient(s). Failed on: {'; '.join(failures)}"
            return True, summary
        else:
            summary = f"Failed to deliver to all {total} recipient(s): {'; '.join(failures)}"
            return False, summary

    @classmethod
    def send_message(cls, bot_token: str, chat_id: Union[str, List[str]], html_message: str, reply_markup: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Universal entry point: automatically supports both single user or multiple comma-separated users/groups.
        """
        return cls.send_broadcast(bot_token, chat_id, html_message, reply_markup=reply_markup)

    # =========================================================================
    # INLINE KEYBOARD ACTION BUTTONS FOR TELEGRAM (GREEN / YELLOW / RED)
    # =========================================================================
    @staticmethod
    def get_entry_ce_buttons(contract: str = "") -> Dict[str, Any]:
        """Green action buttons for CALL (CE) Trade Entry confirmation."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🟢 BUY CALL (CE) ON GROWW", "url": "https://groww.in/options/reliance-industries-ltd"},
                    {"text": "📊 OPEN RELIANCE LIVE CHART", "url": "https://groww.in/stocks/reliance-industries-ltd"}
                ]
            ]
        }

    @staticmethod
    def get_entry_pe_buttons(contract: str = "") -> Dict[str, Any]:
        """Red/Crimson action buttons for PUT (PE) Trade Entry confirmation."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🔴 BUY PUT (PE) ON GROWW", "url": "https://groww.in/options/reliance-industries-ltd"},
                    {"text": "📊 OPEN RELIANCE LIVE CHART", "url": "https://groww.in/stocks/reliance-industries-ltd"}
                ]
            ]
        }

    @staticmethod
    def get_armed_buttons(contract: str = "") -> Dict[str, Any]:
        """Yellow warning buttons for ARMED state pre-alert."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🟡 VIEW OPTION CHAIN (GROWW)", "url": "https://groww.in/options/reliance-industries-ltd"},
                    {"text": "📊 RELIANCE LIVE QUOTE", "url": "https://groww.in/stocks/reliance-industries-ltd"}
                ]
            ]
        }

    @staticmethod
    def get_target_hit_buttons() -> Dict[str, Any]:
        """Green profit celebration buttons for Target Hit."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🎯 BOOK FULL PROFIT ON GROWW", "url": "https://groww.in/options/reliance-industries-ltd"},
                    {"text": "📈 VIEW POSITIONS", "url": "https://groww.in/stocks/reliance-industries-ltd"}
                ]
            ]
        }

    @staticmethod
    def get_stop_loss_buttons() -> Dict[str, Any]:
        """Red capital preservation buttons for Stop Loss."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🛑 EXIT POSITION NOW (GROWW)", "url": "https://groww.in/options/reliance-industries-ltd"}
                ]
            ]
        }

    @staticmethod
    def get_trailing_sl_buttons() -> Dict[str, Any]:
        """Amber/Cyan buttons for Trailing Stop Loss to Cost."""
        return {
            "inline_keyboard": [
                [
                    {"text": "⚡ MODIFY SL ON GROWW", "url": "https://groww.in/options/reliance-industries-ltd"}
                ]
            ]
        }

    @staticmethod
    def get_auto_sq_buttons() -> Dict[str, Any]:
        """Purple urgency buttons for EOD Auto-Square-Off."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🔒 SQUARE-OFF ON GROWW (03:05 PM)", "url": "https://groww.in/options/reliance-industries-ltd"}
                ]
            ]
        }

    @staticmethod
    def get_chop_buttons() -> Dict[str, Any]:
        """Neutral observation buttons for Choppiness Stand Down."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🛡️ VIEW SPOT CHART (GROWW)", "url": "https://groww.in/stocks/reliance-industries-ltd"}
                ]
            ]
        }

    @staticmethod
    def get_circuit_breaker_buttons() -> Dict[str, Any]:
        """Burgundy/Red lock buttons for Circuit Breaker Daily Limit alert."""
        return {
            "inline_keyboard": [
                [
                    {"text": "🚨 OBSERVE SPOT ON GROWW", "url": "https://groww.in/stocks/reliance-industries-ltd"},
                    {"text": "📊 VIEW GROWW POSITIONS", "url": "https://groww.in/options/reliance-industries-ltd"}
                ]
            ]
        }

    @classmethod
    def send_test_alert(cls, bot_token: str, chat_ids_input: Any) -> Tuple[bool, str]:
        """Sends a verification test alert to confirm bot configuration across all recipients."""
        chat_ids = cls.parse_chat_ids(chat_ids_input)
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST | %d-%b-%Y")
        recipients_str = ", ".join(chat_ids) if chat_ids else "None"
        msg = f"""
⚡ <b>RELIANCE QUANTITATIVE ENGINE — TELEGRAM BROADCAST CONNECTED</b> ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>Status:</b> Notification Broadcast Active
⏰ <b>Time:</b> {now_str}
👥 <b>Recipients ({len(chat_ids)}):</b> <code>{recipients_str}</code>
🤖 <b>Multi-User Integration:</b> Zero-Delay Push Alerts Verified

📡 You will receive instant notifications whenever:
• 🟡 <b>Setup is Armed</b> (Approaching Breakout Level)
• 🚀 <b>Entry Trigger Confirmed</b> (LTP Breaches Breakout)
• 🎯 <b>Target is Reached</b> (+10.0 pts | +₹10,000)
• 🛑 <b>Stop Loss is Hit</b> (-9.0 pts | -₹9,000)
• ⚡ <b>Trailing SL Activated</b> (Move SL to Cost)
• 🔒 <b>End of Day Auto-Square-Off</b> (03:05 PM IST)
• 🛡️ <b>Consolidation Chop Warning</b> (CHOP > 61.8)

<i>You can now minimize the browser without worrying about missing trade execution!</i>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "⚡ OPEN GROWW RELIANCE F&O", "url": "https://groww.in/options/reliance-industries-ltd"}
                ]
            ]
        }
        return cls.send_broadcast(bot_token, chat_ids, msg, reply_markup=buttons)

    # =========================================================================
    # ALL LIVE MARKET SCENARIO ALERT FORMATTERS
    # =========================================================================
    @classmethod
    def format_entry_alert(
        cls,
        contract: str,
        direction: str,
        entry_price: float,
        target_pts: float,
        sl_pts: float,
        num_lots: int,
        lot_size: int,
        win_prob: float,
        spot: float,
        rationale: str = ""
    ) -> str:
        """Formats an institutional grade entry alert for Telegram (supports both CE and PE)."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        target_price = round(entry_price + target_pts, 2)
        sl_price = round(entry_price - sl_pts, 2)
        potential_gain = round(total_qty * target_pts)
        potential_loss = round(total_qty * sl_pts)

        is_call = ("BULLISH" in direction.upper() or "CE" in direction.upper())
        dir_icon = "🟢" if is_call else "🔴"
        action = "BUY CALL (CE)" if is_call else "BUY PUT (PE)"

        quant_block = f"""
🔬 <b>Institutional Quantitative Telemetry:</b>
{rationale}
━━━━━━━━━━━━━━━━━━━━━━━━━━""" if rationale else ""

        msg = f"""
🚀 <b>TRADE ENTRY CONFIRMED — {action}</b> 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>Contract:</b> <code>{contract}</code>
⚡ <b>Order Type:</b> <b>LIMIT ORDER ONLY @ ₹{entry_price:.2f}</b>
⚠️ <b>Slippage Warning:</b> <i>DO NOT USE MARKET BUY (Prevents ₹500–₹1,500 spread drag)</i>
{dir_icon} <b>Direction:</b> {direction}
📊 <b>Statistical Win Rate:</b> <b>{win_prob:.1f}%</b> (Execution Gate >60%)

💰 <b>Entry Limit Price:</b> <b>₹{entry_price:.2f}</b>
🎯 <b>Profit Target:</b> <b>₹{target_price:.2f}</b> (+{target_pts:.1f} pts | +₹{potential_gain:,})
🛑 <b>Stop Loss:</b> <b>₹{sl_price:.2f}</b> (-{sl_pts:.1f} pts | -₹{potential_loss:,})
📦 <b>Position Sizing:</b> {num_lots} Lot ({total_qty:,} Units) — Strict 1-Lot Capital Preservation
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━{quant_block}
💡 <b>Institutional Execution Checklist:</b>
1. Place <b>LIMIT BUY</b> order at <b>₹{entry_price:.2f}</b> on Groww / broker
2. Verify Bid-Ask Spread on Groww is ≤ ₹0.25 (Stand down if spread > ₹0.35)
3. Set GTT / Stop-loss order at <b>₹{sl_price:.2f}</b>
4. Set profit target order at <b>₹{target_price:.2f}</b>
5. Mandatory auto square-off at <b>03:05 PM IST</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return msg

    @classmethod
    def format_daily_circuit_breaker_alert(cls, reason: str, spot: float) -> str:
        """Formats an alert when the 1-loss daily circuit breaker activates."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        return f"""
🛑 <b>DAILY LOSS CIRCUIT BREAKER ACTIVATED</b> 🛑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ <b>Capital Preservation Rule:</b> <b>ONE-AND-DONE MANDATE</b>
⏰ <b>Time:</b> {now_str}
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⚠️ <b>Trigger:</b> {reason}

🔒 <b>Engine Decision:</b> <b>ALL NEW ENTRIES LOCKED FOR TODAY</b>
• Zero further orders will be initiated.
• Prevents emotional revenge trading and drawdown compounding.
• Account capital remains safely preserved for tomorrow's market.
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_armed_alert(
        cls,
        contract: str,
        direction: str,
        current_ltp: float,
        breakout_trigger: float,
        distance_pts: float,
        target_pts: float,
        sl_pts: float,
        num_lots: int,
        lot_size: int,
        win_prob: float,
        spot: float,
        rationale: str = ""
    ) -> str:
        """Formats an institutional grade ARMED PRE-ALERT for Telegram (Preparing for Breakout, DO NOT BUY YET)."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        potential_gain = round(total_qty * target_pts)
        potential_loss = round(total_qty * sl_pts)
        target_price = round(breakout_trigger + target_pts, 2)
        sl_price = max(0.05, round(breakout_trigger - sl_pts, 2))

        is_call = ("BULLISH" in direction.upper() or "CE" in direction.upper())
        dir_icon = "🟢" if is_call else "🔴"
        bias_label = "BULLISH CALL (CE)" if is_call else "BEARISH PUT (PE)"
        dist_pct = (distance_pts / current_ltp * 100.0) if current_ltp > 0 else 0.0

        msg = f"""
🟡 <b>SETUP ARMED — PREPARING FOR BREAKOUT ENTRY</b> 🟡
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>ACTION:</b> <b>DO NOT BUY YET — GET READY ON BROKER!</b>
📌 <b>Contract to Watch:</b> <code>{contract}</code>
{dir_icon} <b>Directional Bias:</b> {bias_label}
📊 <b>Statistical Confluence:</b> <b>{win_prob:.1f}%</b> (Execution Gate >60%)

💰 <b>Current Live LTP:</b> <b>₹{current_ltp:.2f}</b>
⚡ <b>Breakout Trigger Level:</b> <b>₹{breakout_trigger:.2f}</b>
📏 <b>Distance to Trigger:</b> <b>{distance_pts:.2f} pts away</b> ({dist_pct:.1f}% from entry)

🎯 <b>Planned Target:</b> ₹{target_price:.2f} (+{target_pts:.1f} pts | +₹{potential_gain:,})
🛑 <b>Planned Stop Loss:</b> ₹{sl_price:.2f} (-{sl_pts:.1f} pts | -₹{potential_loss:,})
📦 <b>Planned Sizing:</b> {num_lots} Lots ({total_qty:,} Units)
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 <b>Action Plan While Armed:</b>
1. Open your <b>Groww / Zerodha</b> terminal
2. Add <b>{contract}</b> to your active watchlist
3. Keep the Order Placement window ready
4. <b>WAIT</b> for the final <b>🚀 BUY NOW</b> confirmation push alert before placing your order!
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return msg

    @classmethod
    def format_target_hit_alert(
        cls,
        contract: str,
        entry_price: float = 37.65,
        exit_price: float = 47.65,
        profit_pts: float = 10.0,
        direction: str = "BULLISH (CALL / CE)",
        total_pnl: Optional[float] = None,
        num_lots: int = 1,
        lot_size: int = 250,
        spot: float = 1226.40,
        **kwargs
    ) -> str:
        """Formats a TARGET HIT celebration alert for Telegram."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        target_pts = profit_pts or kwargs.get("target_pts", 10.0)
        realized_pnl = total_pnl if total_pnl is not None else round(total_qty * target_pts)
        dir_icon = "🟢" if "CE" in direction.upper() or "BULLISH" in direction.upper() else "🔴"
        return f"""
🎯 <b>PROFIT TARGET HIT — FULL PROFIT BOOKED</b> 🎯
━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 <b>RESULT:</b> <b>PROFIT TARGET HIT (+{target_pts:.1f} PTS)</b>
📌 <b>Contract:</b> <code>{contract}</code>
{dir_icon} <b>Direction:</b> {direction}
💰 <b>Net Realized Profit:</b> <b>+₹{realized_pnl:,.2f}</b>

💵 <b>Entry Price:</b> ₹{entry_price:.2f}
🏁 <b>Exit Price (Target):</b> <b>₹{exit_price:.2f}</b> (+{target_pts:.1f} pts)
📦 <b>Position Sized:</b> {num_lots} Lots ({total_qty:,} Units)
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Execution Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>Post-Trade Mandate:</b>
1. Full {total_qty:,} quantity squared off at target ₹{exit_price:.2f}
2. Profit +₹{realized_pnl:,} locked in trading capital
3. Stand down for the session — Daily Profit Target achieved!
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_stop_loss_alert(
        cls,
        contract: str,
        entry_price: float = 37.65,
        sl_price: float = 28.65,
        loss_pts: float = 9.0,
        direction: str = "BULLISH (CALL / CE)",
        total_loss: Optional[float] = None,
        num_lots: int = 1,
        lot_size: int = 250,
        spot: float = 1226.40,
        **kwargs
    ) -> str:
        """Formats a STOP LOSS risk preservation alert for Telegram."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        stop_pts = loss_pts or kwargs.get("sl_pts", 9.0)
        sl_exit_price = sl_price or kwargs.get("sl_exit_price", max(0.05, round(entry_price - stop_pts, 2)))
        capital_loss = total_loss if total_loss is not None else round(total_qty * stop_pts)
        dir_icon = "🟢" if "CE" in direction.upper() or "BULLISH" in direction.upper() else "🔴"
        return f"""
🛑 <b>STOP LOSS HIT — CAPITAL PRESERVATION EXIT</b> 🛑
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ <b>RESULT:</b> <b>STOP LOSS TRIGGERED (-{stop_pts:.1f} PTS)</b>
📌 <b>Contract:</b> <code>{contract}</code>
{dir_icon} <b>Direction:</b> {direction}
⚠️ <b>Preserved Capital Risk:</b> <b>-₹{capital_loss:,.2f}</b>

💵 <b>Entry Price:</b> ₹{entry_price:.2f}
🛑 <b>SL Exit Price:</b> <b>₹{sl_exit_price:.2f}</b> (-{stop_pts:.1f} pts)
📦 <b>Position Sized:</b> {num_lots} Lots ({total_qty:,} Units)
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Exit Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 <b>Risk Discipline Protocol:</b>
1. Position exited strictly at predetermined stop level ₹{sl_exit_price:.2f}
2. Maximum capital risk limited strictly to ₹{capital_loss:,}
3. 0 revenge trading — wait for fresh A+ institutional confluence
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_trailing_sl_alert(
        cls,
        contract: str,
        current_ltp: float = 42.65,
        trailing_sl: float = 37.65,
        secured_pts: float = 5.0,
        direction: str = "BULLISH (CALL / CE)",
        secured_pnl: Optional[float] = None,
        entry_price: Optional[float] = None,
        num_lots: int = 1,
        lot_size: int = 250,
        spot: float = 1226.40,
        **kwargs
    ) -> str:
        """Formats a TRAILING STOP LOSS alert (Move SL to Cost) for Telegram."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        locked_pts = secured_pts or kwargs.get("locked_pts", 5.0)
        orig_entry = entry_price if entry_price is not None else trailing_sl
        new_sl = trailing_sl
        locked_pnl = secured_pnl if secured_pnl is not None else round(total_qty * locked_pts)
        dir_icon = "🟢" if "CE" in direction.upper() or "BULLISH" in direction.upper() else "🔴"
        return f"""
⚡ <b>TRAILING STOP LOSS — RISK-FREE TRADE SECURED</b> ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ <b>STATUS:</b> <b>SL MOVED TO COST (0 RISK ACTIVE)</b>
📌 <b>Contract:</b> <code>{contract}</code>
{dir_icon} <b>Direction:</b> {direction}
📈 <b>Running Move:</b> <b>+{locked_pts:.1f} pts in profit (+₹{locked_pnl:,})</b>

💵 <b>Original Entry:</b> ₹{orig_entry:.2f}
⚡ <b>Current Option LTP:</b> <b>₹{current_ltp:.2f}</b>
🔒 <b>New Trailing SL:</b> <b>₹{new_sl:.2f} (Entry Price / Cost)</b>
📦 <b>Position Sizing:</b> {num_lots} Lots ({total_qty:,} Units)
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>Trade Management:</b>
1. Modify pending SL order to cost (₹{new_sl:.2f}) on Groww / broker
2. Trade is now 100% RISK-FREE — Zero capital loss possible!
3. Trail remaining quantity toward target!
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_breakeven_alert(
        cls,
        contract: str,
        current_ltp: float,
        entry_price: float,
        num_lots: int = 1,
        lot_size: int = 250,
        spot: float = 1226.40,
        **kwargs
    ) -> str:
        """Formats a BREAKEVEN ALERT (+3.5 pts reached, SL moved to Cost) for Telegram."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        be_sl = round(entry_price + 0.10, 2)
        gain_pts = round(current_ltp - entry_price, 2)
        gain_rs = round(gain_pts * total_qty)
        return f"""
🛡️ <b>BREAKEVEN ESCALATOR ACTIVATED — RISK-FREE TRADE</b> 🛡️
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>STATUS:</b> <b>MOVE STOP-LOSS TO ENTRY / COST (0 RISK ACTIVE)</b>
📌 <b>Contract:</b> <code>{contract}</code>
📈 <b>Running Move:</b> <b>+{gain_pts:.2f} pts in profit (+₹{gain_rs:,})</b>

💵 <b>Original Entry:</b> ₹{entry_price:.2f}
⚡ <b>Current Option LTP:</b> <b>₹{current_ltp:.2f}</b>
🔒 <b>New Trailing Stop-Loss:</b> <b>₹{be_sl:.2f} (Entry Price / Cost)</b>
📦 <b>Position Sizing:</b> {num_lots} Lot ({total_qty:,} Units)
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>Mandatory Trade Management:</b>
1. Open your <b>Groww / Broker</b> Orders tab immediately
2. Modify your pending SL order trigger from initial SL to <b>₹{be_sl:.2f}</b>
3. Your trade is now <b>100% RISK-FREE</b> — No loss of capital possible!
4. Let the position run towards final target!
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_profit_lock_alert(
        cls,
        contract: str,
        current_ltp: float,
        entry_price: float,
        num_lots: int = 1,
        lot_size: int = 250,
        spot: float = 1226.40,
        **kwargs
    ) -> str:
        """Formats a PROFIT LOCK ALERT (+5.5 pts reached, lock +3.0 pts profit) for Telegram."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        lock_sl = round(entry_price + 3.0, 2)
        locked_pnl = round(3.0 * total_qty)
        gain_pts = round(current_ltp - entry_price, 2)
        return f"""
🔒 <b>PROFIT LOCK ESCALATOR ACTIVATED (+3.0 PTS GUARANTEED)</b> 🔒
━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 <b>STATUS:</b> <b>GUARANTEED PROFIT LOCKED IN CAPITAL</b>
📌 <b>Contract:</b> <code>{contract}</code>
📈 <b>Running Move:</b> <b>+{gain_pts:.2f} pts in profit</b>

💵 <b>Original Entry:</b> ₹{entry_price:.2f}
⚡ <b>Current Option LTP:</b> <b>₹{current_ltp:.2f}</b>
🔒 <b>New Locked SL:</b> <b>₹{lock_sl:.2f} (+3.0 pts guaranteed profit)</b>
💰 <b>Guaranteed Minimum Profit:</b> <b>+₹{locked_pnl:,.2f}</b>
📦 <b>Position Sizing:</b> {num_lots} Lot ({total_qty:,} Units)
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>Action Required:</b>
1. Modify your pending SL order on Groww to <b>₹{lock_sl:.2f}</b>
2. Even on an instant market reversal, you walk away with +₹{locked_pnl:,} profit!
3. Target limit remains active for full profit exit!
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_auto_square_off_alert(
        cls,
        contract: str,
        current_ltp: float = 37.65,
        reason: str = "Mandatory intraday EOD cut-off before broker auto-square-off charges at 03:15 PM",
        num_lots: int = 1,
        lot_size: int = 250,
        spot: float = 1226.40,
        **kwargs
    ) -> str:
        """Formats an AUTO-SQUARE-OFF EOD CUTOFF alert for Telegram."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        return f"""
🔒 <b>INTRADAY AUTO-SQUARE-OFF MANDATE (03:05 PM IST)</b> 🔒
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>ACTION REQUIRED:</b> <b>CLOSE ALL OPEN F&O POSITIONS IMMEDIATELY</b>
📌 <b>Contract:</b> <code>{contract}</code>
⏰ <b>Session Time:</b> <b>03:05 PM IST (EOD Cutoff)</b>
⚡ <b>Current Option LTP:</b> ₹{current_ltp:.2f}
📦 <b>Quantity:</b> {num_lots} Lots ({total_qty:,} Units)
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 <b>Mandatory EOD Protocol:</b>
1. Square off all intraday MIS/Normal positions before 03:10 PM broker auto-square-off
2. Avoid overnight gap-down / gap-up carrying risk
3. Reason: {reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_chop_standdown_alert(
        cls,
        spot: float = 1226.40,
        chop_val: float = 64.8,
        reason: str = "Fractal Choppiness Index (CHOP 64.8 > 61.8 Threshold)",
        corridor_str: str = "",
        **kwargs
    ) -> str:
        """Formats a CHOPPINESS STAND DOWN warning alert for Telegram."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        return f"""
🛡️ <b>CHOPPINESS REGIME DETECTED — STAND DOWN ENFORCED</b> 🛡️
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 <b>RULE:</b> <b>0 TRADES PERMITTED IN SIDEWAYS CHOP</b>
📊 <b>Wilder's Choppiness Index (CHOP-14):</b> <b>{chop_val:.1f}</b> (&gt; 61.8 Threshold)
📍 <b>Reliance Spot:</b> ₹{spot:.2f} {f'({corridor_str})' if corridor_str else ''}
⏰ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>Risk Assessment:</b>
• Fractal consolidation indicates strong institutional absorption with no directional breakout
• Option buying in CHOP &gt; 61.8 suffers severe theta decay and false whipsaws
• Strict capital preservation active — engine stands down until CHOP &lt; 45
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_circuit_breaker_alert(
        cls,
        sl_count: int = 2,
        max_allowed: int = 2,
        capital_preserved: float = 73643.72,
        spot: float = 1226.40,
        account_name: str = "Teja",
        **kwargs
    ) -> str:
        """Formats a MAX DAILY DRAWDOWN CIRCUIT BREAKER LOCK alert for Telegram."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        return f"""
🚨 <b>MAX DAILY DRAWDOWN REACHED — SESSION LOCKED</b> 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 <b>DAILY RISK GATE:</b> <b>CIRCUIT BREAKER TRIPPED</b>
📊 <b>Consecutive Stop Losses Hit:</b> <b>{sl_count} / {max_allowed} Max Allowed</b>
💰 <b>Protected Account Capital:</b> ₹{capital_preserved:,.2f}
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Trigger Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 <b>Institutional Execution Mandate:</b>
• Daily drawdown threshold reached — order generation automatically disabled.
• Zero new trades permitted for the remainder of today's trading session.
• Strict capital preservation protocol active: survive to trade another day.
• Stance: <b>STAND DOWN & NO REVENGE TRADING</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @classmethod
    def format_theta_stagnation_alert(
        cls,
        contract: str,
        entry_price: float,
        current_ltp: float,
        elapsed_minutes: int,
        unrealized_pnl: float,
        spot: float
    ) -> str:
        """Formats a THETA STAGNATION TIME-STOP alert for Telegram (45-minute stagnation rule)."""
        now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
        decay_pts = round(entry_price - current_ltp, 2)
        return f"""
⏳ <b>THETA STAGNATION SHIELD TRIGGERED (TIME-STOP)</b> ⏳
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>ACTION:</b> <b>CONSIDER EARLY EXIT / STAND DOWN</b>
📌 <b>Contract:</b> <code>{contract}</code>
⏱️ <b>Time in Trade:</b> <b>{elapsed_minutes} Minutes</b> (Threshold: 45 Mins)
💰 <b>Entry Price:</b> ₹{entry_price:.2f} | <b>Current LTP:</b> ₹{current_ltp:.2f}
📉 <b>Theta Decay Drag:</b> -{decay_pts:.2f} pts (Unrealized P&L: -₹{abs(unrealized_pnl):,.0f})
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 <b>Institutional Mandate:</b>
• Price action has consolidated sideways for {elapsed_minutes} minutes without directional impulse.
• Holding naked options through prolonged stagnation leads to guaranteed theta bleed.
• Rule: Exit position at current market price to prevent further time decay.
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


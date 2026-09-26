"""
Telegram Trade Alert Module for RELIANCE Quantitative Intraday Engine
======================================================================
Provides zero-delay instant push notifications to Telegram when
trade entry triggers are confirmed, targets are hit, or SLs are reached.

Supports MULTI-USER BROADCAST:
- Multiple individual Telegram users (comma/space/newline separated Chat IDs)
- Telegram Groups (Chat IDs starting with - or -100...)
- Telegram Channels (Chat IDs or @channel usernames)
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Union
try:
    import requests
except ImportError:
    requests = None
import urllib.request
import urllib.parse


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "telegram_config.json")


class TelegramNotifier:
    """Handles Telegram Bot communication and trade alerts for single or multiple users/groups."""

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
            # Auto-correct Group / Supergroup IDs missing leading minus '-'
            # Telegram supergroup/channel IDs start with 100... and are 12+ digits
            if cid.isdigit() and len(cid) >= 12 and cid.startswith("100"):
                cid = f"-{cid}"
            elif cid.isdigit() and len(cid) >= 12:
                cid = f"-{cid}"
            if cid and cid not in unique_ids:
                unique_ids.append(cid)
        return unique_ids

    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Loads saved Telegram credentials and preferences."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Normalize chat_id to string
                    if "chat_id" in data and isinstance(data["chat_id"], list):
                        data["chat_id"] = ", ".join(data["chat_id"])
                    return data
            except Exception:
                pass
        return {
            "bot_token": "",
            "chat_id": "",
            "enabled": True,
            "sound_alerts": True
        }

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
    def send_single_message(cls, bot_token: str, chat_id: str, html_message: str) -> Tuple[bool, str]:
        """
        Sends an HTML formatted message to a single Telegram Chat ID.
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
                # If user entered a group ID without minus sign (e.g. 1004390764314)
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
    def send_broadcast(cls, bot_token: str, chat_ids_input: Any, html_message: str) -> Tuple[bool, str]:
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
            ok, msg = cls.send_single_message(token, cid, html_message)
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
    def send_message(cls, bot_token: str, chat_id: Union[str, List[str]], html_message: str) -> Tuple[bool, str]:
        """
        Universal entry point: automatically supports both single user or multiple comma-separated users/groups.
        """
        return cls.send_broadcast(bot_token, chat_id, html_message)

    @classmethod
    def send_test_alert(cls, bot_token: str, chat_ids_input: Any) -> Tuple[bool, str]:
        """Sends a verification test alert to confirm bot configuration across all recipients."""
        chat_ids = cls.parse_chat_ids(chat_ids_input)
        now_str = datetime.now().strftime("%I:%M:%S %p IST | %d-%b-%Y")
        recipients_str = ", ".join(chat_ids) if chat_ids else "None"
        msg = f"""
⚡ <b>RELIANCE QUANTITATIVE ENGINE — TELEGRAM BROADCAST CONNECTED</b> ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ <b>Status:</b> Notification Broadcast Active
⏰ <b>Time:</b> {now_str}
👥 <b>Recipients ({len(chat_ids)}):</b> <code>{recipients_str}</code>
🤖 <b>Multi-User Integration:</b> Zero-Delay Push Alerts Verified

📡 You will receive instant notifications whenever:
• 🔥 <b>Entry Trigger is Confirmed</b> (LTP breaches Breakout Level)
• 🎯 <b>Target is Reached</b> (+10.0 pts | +₹10,000)
• 🛑 <b>Stop Loss is Hit</b> (-9.0 pts | -₹9,000)
• 🔒 <b>End of Day Auto-Square-Off</b> alert

<i>You can now minimize the browser without worrying about missing the trade entry!</i>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return cls.send_broadcast(bot_token, chat_ids, msg)

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
        """Formats an institutional grade entry alert for Telegram."""
        now_str = datetime.now().strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        target_price = round(entry_price + target_pts, 2)
        sl_price = round(entry_price - sl_pts, 2)
        potential_gain = round(total_qty * target_pts)
        potential_loss = round(total_qty * sl_pts)

        dir_icon = "🟢" if "BULLISH" in direction.upper() or "CE" in direction.upper() else "🔴"
        action = "BUY CALL (CE)" if "BULLISH" in direction.upper() or "CE" in direction.upper() else "BUY PUT (PE)"

        msg = f"""
🚀 <b>TRADE ENTRY CONFIRMED — {action}</b> 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>Contract:</b> <code>{contract}</code>
⚡ <b>Action:</b> <b>BUY NOW AT MARKET</b>
{dir_icon} <b>Direction:</b> {direction}
📊 <b>Statistical Win Rate:</b> <b>{win_prob:.1f}%</b> (Optimal Gate ≥65%)

💰 <b>Entry Trigger:</b> <b>₹{entry_price:.2f}</b>
🎯 <b>Profit Target:</b> <b>₹{target_price:.2f}</b> (+{target_pts:.1f} pts | +₹{potential_gain:,})
🛑 <b>Stop Loss:</b> <b>₹{sl_price:.2f}</b> (-{sl_pts:.1f} pts | -₹{potential_loss:,})
📦 <b>Position Sizing:</b> {num_lots} Lots ({total_qty:,} Units)
📍 <b>Reliance Spot:</b> ₹{spot:.2f}
⏰ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>Execution Checklist:</b>
1. Place Market/Limit order for <b>{contract}</b> on Groww/broker
2. Set GTT/Stop-loss at ₹{sl_price:.2f}
3. Book profit target at ₹{target_price:.2f}
4. Hard square-off rule at 03:05 PM IST
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return msg

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
        now_str = datetime.now().strftime("%I:%M:%S %p IST")
        total_qty = num_lots * lot_size
        potential_gain = round(total_qty * target_pts)
        potential_loss = round(total_qty * sl_pts)
        target_price = round(breakout_trigger + target_pts, 2)
        sl_price = max(0.05, round(breakout_trigger - sl_pts, 2))

        dir_icon = "🟢" if "BULLISH" in direction.upper() or "CE" in direction.upper() else "🔴"
        bias_label = "BULLISH CALL (CE)" if "BULLISH" in direction.upper() or "CE" in direction.upper() else "BEARISH PUT (PE)"
        dist_pct = (distance_pts / current_ltp * 100.0) if current_ltp > 0 else 0.0

        msg = f"""
🟡 <b>SETUP ARMED — PREPARING FOR BREAKOUT ENTRY</b> 🟡
━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>ACTION:</b> <b>DO NOT BUY YET — GET READY ON BROKER!</b>
📌 <b>Contract to Watch:</b> <code>{contract}</code>
{dir_icon} <b>Directional Bias:</b> {bias_label}
📊 <b>Statistical Confluence:</b> <b>{win_prob:.1f}%</b> (Optimal Gate ≥65%)

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

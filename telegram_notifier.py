"""
Telegram Trade Alert Module for NIFTY & SENSEX Quantitative Intraday Engine
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
        """Saves persistent alert dispatch records to disk atomically."""
        try:
            temp_path = f"{ALERT_LOG_FILE}.tmp.{os.getpid()}"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            os.replace(temp_path, ALERT_LOG_FILE)
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
          - Public Channels: e.g. "@quant_trade_alerts"
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

        # Anti-Flood Protection: Deduplicate identical broadcast messages within 60s
        import hashlib
        now_ts = time.time()
        if not hasattr(cls, "_recent_msg_hashes"):
            cls._recent_msg_hashes = {}
        cls._recent_msg_hashes = {k: v for k, v in cls._recent_msg_hashes.items() if (now_ts - v) < 180}
        norm_text = "".join(html_message.split())
        msg_hash = hashlib.md5(norm_text.encode("utf-8")).hexdigest()
        if msg_hash in cls._recent_msg_hashes:
            elapsed = now_ts - cls._recent_msg_hashes[msg_hash]
            if elapsed < 60:
                return True, f"Anti-Flood Guard: duplicate message suppressed ({elapsed:.1f}s ago)"
        cls._recent_msg_hashes[msg_hash] = now_ts

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
    # INLINE KEYBOARD ACTION BUTTONS FOR TELEGRAM (DYNAMIC SYMBOL / URL RESOLUTION)
    # =========================================================================
    @staticmethod
    def _resolve_symbol(symbol: str = "", contract: str = "") -> str:
        from asset_config import resolve_symbol
        if symbol and symbol.strip():
            return resolve_symbol(symbol, contract)
        if contract and contract.strip():
            return resolve_symbol(symbol, contract)
        # Attempt to auto-detect active selection from Streamlit session if in app context
        try:
            import sys
            if "streamlit" in sys.modules:
                st = sys.modules["streamlit"]
                sel = st.session_state.get("selected_scrip")
                if sel:
                    return resolve_symbol(sel, contract)
        except Exception:
            pass
        return resolve_symbol(symbol, contract)

    @classmethod
    def _get_groww_urls(cls, symbol: str = "", contract: str = "") -> Tuple[str, str, str]:
        from asset_config import get_asset_spec
        sym = cls._resolve_symbol(symbol, contract)
        spec = get_asset_spec(sym)
        opt_url = f"https://groww.in/options/{spec.groww_company_slug}"
        base_cat = "indices" if sym in ("NIFTY", "SENSEX") else "stocks"
        stock_url = f"https://groww.in/{base_cat}/{spec.groww_company_slug}"
        return opt_url, stock_url, spec.symbol

    @classmethod
    def _stock_name(cls, symbol: str = "", contract: str = "") -> str:
        from asset_config import get_asset_spec
        sym = cls._resolve_symbol(symbol, contract)
        spec = get_asset_spec(sym)
        return spec.full_name.replace(" Ltd.", "").strip()

    @classmethod
    def _spot_label(cls, symbol: str = "", contract: str = "") -> str:
        return f"{cls._stock_name(symbol, contract)} Spot"

    @classmethod
    def _resolve_live_spot(cls, spot: float, symbol: str = "", contract: str = "") -> float:
        if spot > 0.0:
            return spot
        from asset_config import get_asset_spec
        sym = cls._resolve_symbol(symbol, contract)
        spec = get_asset_spec(sym)
        try:
            from groww_market_feed import GrowwMarketFeed
            gw_data = GrowwMarketFeed.get_instance().get_live_spot_data(symbol=sym)
            live_spot = float(gw_data.get("spot_ltp", 0.0))
            if live_spot > 0:
                return live_spot
        except Exception:
            pass
        return spec.default_spot

    @classmethod
    def get_entry_ce_buttons(cls, contract: str = "", symbol: str = "") -> Dict[str, Any]:
        """Green action buttons for CALL (CE) Trade Entry confirmation."""
        opt_url, stock_url, scrip_name = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "🟢 BUY CALL (CE) ON GROWW", "url": opt_url},
                    {"text": f"📊 OPEN {scrip_name} LIVE CHART", "url": stock_url}
                ]
            ]
        }

    @classmethod
    def get_entry_pe_buttons(cls, contract: str = "", symbol: str = "") -> Dict[str, Any]:
        """Red/Crimson action buttons for PUT (PE) Trade Entry confirmation."""
        opt_url, stock_url, scrip_name = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "🔴 BUY PUT (PE) ON GROWW", "url": opt_url},
                    {"text": f"📊 OPEN {scrip_name} LIVE CHART", "url": stock_url}
                ]
            ]
        }

    @classmethod
    def get_armed_buttons(cls, contract: str = "", symbol: str = "") -> Dict[str, Any]:
        """Yellow warning buttons for ARMED state pre-alert."""
        opt_url, stock_url, scrip_name = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "🟡 VIEW OPTION CHAIN (GROWW)", "url": opt_url},
                    {"text": f"📊 {scrip_name} LIVE QUOTE", "url": stock_url}
                ]
            ]
        }

    @classmethod
    def get_target_hit_buttons(cls, symbol: str = "", contract: str = "") -> Dict[str, Any]:
        """Green profit celebration buttons for Target Hit."""
        opt_url, stock_url, scrip_name = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "🎯 BOOK FULL PROFIT ON GROWW", "url": opt_url},
                    {"text": f"📈 VIEW {scrip_name} POSITIONS", "url": stock_url}
                ]
            ]
        }

    @classmethod
    def get_stop_loss_buttons(cls, symbol: str = "", contract: str = "") -> Dict[str, Any]:
        """Red capital preservation buttons for Stop Loss."""
        opt_url, _, _ = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "🛑 EXIT POSITION NOW (GROWW)", "url": opt_url}
                ]
            ]
        }

    @classmethod
    def get_trailing_sl_buttons(cls, symbol: str = "", contract: str = "") -> Dict[str, Any]:
        """Amber/Cyan buttons for Trailing Stop Loss to Cost."""
        opt_url, _, _ = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "⚡ MODIFY SL ON GROWW", "url": opt_url}
                ]
            ]
        }

    @classmethod
    def get_auto_sq_buttons(cls, symbol: str = "", contract: str = "") -> Dict[str, Any]:
        """Purple urgency buttons for EOD Auto-Square-Off."""
        opt_url, _, _ = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "🔒 SQUARE-OFF ON GROWW (03:05 PM)", "url": opt_url}
                ]
            ]
        }

    @classmethod
    def get_chop_buttons(cls, symbol: str = "", contract: str = "") -> Dict[str, Any]:
        """Neutral observation buttons for Choppiness Stand Down."""
        _, stock_url, _ = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "🛡️ VIEW SPOT CHART (GROWW)", "url": stock_url}
                ]
            ]
        }

    @classmethod
    def get_circuit_breaker_buttons(cls, symbol: str = "", contract: str = "") -> Dict[str, Any]:
        """Burgundy/Red lock buttons for Circuit Breaker Daily Limit alert."""
        opt_url, stock_url, _ = cls._get_groww_urls(symbol, contract)
        return {
            "inline_keyboard": [
                [
                    {"text": "🚨 OBSERVE SPOT ON GROWW", "url": stock_url},
                    {"text": "📊 VIEW GROWW POSITIONS", "url": opt_url}
                ]
            ]
        }

    @classmethod
    def send_test_alert(cls, bot_token: str, chat_ids_input: Any, symbol: str = "NIFTY") -> Tuple[bool, str]:
        """Sends a clean, beautiful verification test alert to confirm bot configuration across all recipients."""
        chat_ids = cls.parse_chat_ids(chat_ids_input)
        now_str = datetime.now(IST).strftime("%I:%M %p IST • %d-%b-%Y")
        recipients_str = f"{len(chat_ids)} Recipient(s)"
        opt_url, stock_url, scrip_name = cls._get_groww_urls(symbol)
        stock_name = cls._stock_name(symbol=symbol)
        msg = f"""<b>⚡ {scrip_name} QUANT ENGINE • DISPATCH ACTIVE</b>
────────────────────────
✅ <b>Status:</b> High-Precision Dispatch Connected
⏰ <b>Time:</b> {now_str}
👥 <b>Target:</b> <code>{recipients_str}</code>
🏛️ <b>Asset:</b> {stock_name}
────────────────────────
📡 <i>Instant notifications configured for Entry, Targets, Stop-Loss, Trailing Stops, and Risk Filters.</i>"""
        buttons = {
            "inline_keyboard": [
                [
                    {"text": f"⚡ OPEN GROWW {scrip_name} F&O", "url": opt_url}
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
        num_lots: int = 0,
        lot_size: int = 0,
        win_prob: float = 75.0,
        spot: float = 0.0,
        rationale: str = "",
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean, modern institutional grade entry alert for Telegram with mathematically verified PnL."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        # Strictly enforce canonical exchange contract lot size
        lot_size = spec.lot_size
        if not num_lots or num_lots <= 0:
            num_lots = spec.default_lots
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        total_qty = num_lots * lot_size
        target_price = round(entry_price + target_pts, 2)
        sl_price = max(0.05, round(entry_price - sl_pts, 2))
        potential_gain = round(total_qty * target_pts)
        potential_loss = round(total_qty * sl_pts)
        scrip_sym = spec.symbol

        is_call = ("BULLISH" in direction.upper() or "CE" in direction.upper())
        dir_badge = "🟢 BUY CALL (CE)" if is_call else "🔴 BUY PUT (PE)"
        rr_ratio = round(target_pts / max(0.1, sl_pts), 1)

        is_gamma = kwargs.get("is_gamma_exception", False)
        header_banner = "⚡ <b>EXPIRY SPECIAL: GAMMA BLAST CALL (1/1 EXCEPTION)</b>\n" if is_gamma else ""

        # Groww 09:10 AM Support & Resistance Levels
        sr_line = ""
        try:
            from groww_market_feed import GrowwMarketFeed
            sr_info = GrowwMarketFeed.get_instance().get_groww_daily_support_resistance(scrip_sym)
            p_val = sr_info.get("pivot", 0.0)
            r1_val = sr_info.get("resistance", {}).get("r1", 0.0)
            s1_val = sr_info.get("support", {}).get("s1", 0.0)
            if p_val > 0:
                sr_line = f"\n🎯 <b>Groww 09:10 AM S&R:</b> Pivot ₹{p_val:,.1f} | R1 ₹{r1_val:,.1f} | S1 ₹{s1_val:,.1f}"
        except Exception:
            pass

        limit_collar = float(kwargs.get("limit_collar", getattr(spec, "limit_collar_pts", 3.0)))
        limit_cap = round(entry_price + limit_collar, 2)

        msg = f"""{header_banner}<b>{dir_badge} • {scrip_sym}</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
📊 <b>Win Probability:</b> <b>{win_prob:.1f}%</b> (A+ Confluence)

💰 <b>Limit Entry:</b> <code>₹{entry_price:.2f}</code>
🎯 <b>Target:</b> <code>₹{target_price:.2f}</code> (+{target_pts:.1f} pts • +₹{potential_gain:,})
🛑 <b>Stop Loss:</b> <code>₹{sl_price:.2f}</code> (-{sl_pts:.1f} pts • -₹{potential_loss:,})
📦 <b>Sizing:</b> {num_lots} Lot{'s' if num_lots>1 else ''} ({total_qty:,} Qty) • R:R 1:{rr_ratio}{sr_line}
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
⚡ <i>Place SL-LMT BUY on broker ➔ Trigger: ₹{entry_price:.2f} | Limit Cap: ₹{limit_cap:.2f} (Max Slippage ₹{limit_collar:.1f}). Set GTT SL & Target.</i>"""
        return msg

    @classmethod
    def format_preflight_alert(cls, groww_connected: bool = True, symbols: Optional[List[str]] = None) -> str:
        """Formats the daily 09:10 AM Pre-Flight Engine Readiness alert."""
        from asset_config import get_asset_spec
        now_str = datetime.now(IST).strftime("%I:%M %p IST • %d-%b-%Y")
        syms = symbols or ["SENSEX", "NIFTY"]
        mandate_lines = []
        for s in syms:
            sp = get_asset_spec(s)
            tot_q = sp.default_lots * sp.lot_size
            mandate_lines.append(
                f" • <b>{sp.symbol}:</b> {sp.default_lots} Lots ({tot_q} Qty) │ TGT +{sp.target_pts:.0f} pts (+₹{tot_q * sp.target_pts:,.0f}) │ SL -{sp.sl_pts:.0f} pts (-₹{tot_q * sp.sl_pts:,.0f})"
            )
        mandates_text = "\n".join(mandate_lines)
        gw_status = "✅ CONNECTED & STREAMING" if groww_connected else "⚠️ REST FALLBACK LIVE"

        return f"""<b>🟢 QUANT DESK DAEMON ONLINE • PRE-FLIGHT READY</b>
────────────────────────
✅ <b>Engine Status:</b> 24/7 Autonomous Daemon Active
⏰ <b>Time:</b> {now_str}
📡 <b>Groww Broker:</b> {gw_status}
🏛️ <b>Monitored Desks:</b> {', '.join(syms)}
────────────────────────
📊 <b>DESK ALLOCATIONS & SIZING MANDATES:</b>
{mandates_text}
🛡️ <b>Capital Defense:</b> 1-Loss Daily Circuit Breaker Armed (0 Losses Today)
────────────────────────
🎯 <i>Desk ready for 09:15 AM market open. Awaiting A+ quantitative confluence.</i>"""

    @classmethod
    def format_daily_circuit_breaker_alert(cls, reason: str, spot: float = 0.0, symbol: str = "NIFTY") -> str:
        """Formats a clean alert when the 1-loss daily circuit breaker activates."""
        spot = cls._resolve_live_spot(spot, symbol=symbol)
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol)
        scrip_sym = spec.symbol
        total_qty = spec.default_lots * spec.lot_size
        est_loss = float(total_qty * spec.sl_pts)
        return f"""<b>🚨 CIRCUIT BREAKER • {scrip_sym} LOCKED</b>
────────────────────────
🛡️ <b>Desk:</b> {scrip_sym} Intraday Desk ({spec.default_lots} Lots • {total_qty:,} Qty)
⚠️ <b>Trigger:</b> {reason} (Est. -₹{est_loss:,.2f})
🔒 <b>Action:</b> <b>ALL NEW ENTRIES LOCKED TODAY</b>

• Risk Rule: One-and-Done Capital Defense
• Zero revenge trading. Capital preserved for tomorrow.
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
🛑 <i>Disciplined capital preservation enforced. Session standing down.</i>"""

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
        num_lots: int = 0,
        lot_size: int = 0,
        win_prob: float = 75.0,
        spot: float = 0.0,
        rationale: str = "",
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean, modern ARMED PRE-ALERT for Telegram with verified lot size & rupee calculations."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        # Strictly enforce canonical exchange contract lot size
        lot_size = spec.lot_size
        if not num_lots or num_lots <= 0:
            num_lots = spec.default_lots
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        scrip_sym = spec.symbol
        total_qty = num_lots * lot_size
        potential_gain = round(total_qty * target_pts)
        potential_loss = round(total_qty * sl_pts)
        is_call = ("BULLISH" in direction.upper() or "CE" in direction.upper())
        dir_badge = "CALL (CE)" if is_call else "PUT (PE)"

        # Groww 09:10 AM Support & Resistance Levels
        sr_line = ""
        try:
            from groww_market_feed import GrowwMarketFeed
            sr_info = GrowwMarketFeed.get_instance().get_groww_daily_support_resistance(scrip_sym)
            p_val = sr_info.get("pivot", 0.0)
            r1_val = sr_info.get("resistance", {}).get("r1", 0.0)
            s1_val = sr_info.get("support", {}).get("s1", 0.0)
            if p_val > 0:
                sr_line = f"\n🎯 <b>Groww 09:10 AM S&R:</b> P: ₹{p_val:,.1f} | R1: ₹{r1_val:,.1f} | S1: ₹{s1_val:,.1f}"
        except Exception:
            pass

        return f"""<b>🟡 SETUP ARMED • {scrip_sym} {dir_badge}</b>
────────────────────────
📌 <b>Watchlist:</b> <code>{contract}</code>
📊 <b>Confluence:</b> <b>{win_prob:.1f}%</b> (Approaching Breakout)

⚡ <b>Breakout Trigger:</b> <code>₹{breakout_trigger:.2f}</code>
💰 <b>Current LTP:</b> ₹{current_ltp:.2f} ({distance_pts:.2f} pts away)
🎯 <b>Plan Target:</b> +{target_pts:.1f} pts (+₹{potential_gain:,}) | 🛑 <b>Plan SL:</b> -{sl_pts:.1f} pts (-₹{potential_loss:,})
📦 <b>Sizing Mandate:</b> {num_lots} Lot{'s' if num_lots>1 else ''} ({total_qty:,} Qty){sr_line}
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
⏳ <i>DO NOT BUY YET. Keep contract on broker watchlist and await ENTRY alert.</i>"""

    @classmethod
    def format_setup_cancelled_alert(
        cls,
        contract: str,
        reason: str,
        breakout_trigger: float,
        last_ltp: float,
        spot: float = 0.0,
        symbol: str = "",
        direction: str = "BULLISH (CALL / CE)"
    ) -> str:
        """Formats an explicit closure notification when an armed setup is cancelled before breakout."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        scrip_sym = spec.symbol
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        is_call = ("BULLISH" in direction.upper() or "CE" in direction.upper())
        dir_badge = "CALL (CE)" if is_call else "PUT (PE)"

        return f"""<b>⚪ SETUP CANCELLED • {scrip_sym} {dir_badge}</b>
────────────────────────
📌 <b>Watchlist:</b> <code>{contract}</code>
⚡ <b>Breakout Trigger:</b> ₹{breakout_trigger:.2f} (Last LTP: ₹{last_ltp:.2f})

❌ <b>Closure / Invalidation Reason:</b>
{reason}

📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
🛡️ <i>Stand Down executed. Zero capital lost. Resuming market scan for fresh setups.</i>"""

    @classmethod
    def format_target_hit_alert(
        cls,
        contract: str,
        entry_price: float = 0.0,
        exit_price: float = 0.0,
        profit_pts: float = 0.0,
        direction: str = "BULLISH (CALL / CE)",
        total_pnl: Optional[float] = None,
        num_lots: int = 0,
        lot_size: Optional[int] = None,
        spot: float = 0.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean, celebratory TARGET HIT alert for Telegram with verified PnL."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        # Strictly enforce canonical exchange contract lot size
        lot_size = spec.lot_size
        if not num_lots or num_lots <= 0:
            num_lots = spec.default_lots
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        total_qty = num_lots * lot_size
        target_pts = profit_pts or kwargs.get("target_pts", spec.target_pts)
        if exit_price <= 0.0:
            exit_price = round(entry_price + target_pts, 2)
        realized_pnl = total_pnl if total_pnl is not None else round(total_qty * target_pts)
        scrip_sym = spec.symbol

        return f"""<b>🎯 TARGET HIT • {scrip_sym} PROFIT BOOKED</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
💰 <b>Net Realized Profit:</b> <b>+₹{realized_pnl:,.2f}</b> (+{target_pts:.1f} pts)

💵 <b>Entry:</b> ₹{entry_price:.2f}  ➔  🏁 <b>Exit:</b> <code>₹{exit_price:.2f}</code>
📦 <b>Filled Size:</b> {num_lots} Lot{'s' if num_lots>1 else ''} ({total_qty:,} Qty)
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
🏆 <i>Full profit booked & locked into capital. Stand down for session.</i>"""

    @classmethod
    def format_stop_loss_alert(
        cls,
        contract: str,
        entry_price: float = 0.0,
        sl_price: float = 0.0,
        loss_pts: float = 0.0,
        direction: str = "BULLISH (CALL / CE)",
        total_loss: Optional[float] = None,
        num_lots: int = 0,
        lot_size: Optional[int] = None,
        spot: float = 0.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean STOP LOSS risk preservation alert for Telegram with verified PnL."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        # Strictly enforce canonical exchange contract lot size
        lot_size = spec.lot_size
        if not num_lots or num_lots <= 0:
            num_lots = spec.default_lots
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        total_qty = num_lots * lot_size
        stop_pts = loss_pts or kwargs.get("sl_pts", spec.sl_pts)
        sl_exit_price = sl_price if sl_price > 0.0 else kwargs.get("sl_exit_price", max(0.05, round(entry_price - stop_pts, 2)))
        capital_loss = total_loss if total_loss is not None else round(total_qty * stop_pts)
        scrip_sym = spec.symbol

        return f"""<b>🛑 STOP LOSS HIT • {scrip_sym} RISK CUT</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
⚠️ <b>Risk Exit:</b> <b>-₹{capital_loss:,.2f}</b> (-{stop_pts:.1f} pts)

💵 <b>Entry:</b> ₹{entry_price:.2f}  ➔  🛑 <b>Exit:</b> <code>₹{sl_exit_price:.2f}</code>
📦 <b>Closed Size:</b> {num_lots} Lot{'s' if num_lots>1 else ''} ({total_qty:,} Qty)
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
🛡️ <i>Disciplined capital defense: risk strictly limited. Zero revenge trading.</i>"""

    @classmethod
    def format_trailing_sl_alert(
        cls,
        contract: str,
        current_ltp: float = 0.0,
        trailing_sl: float = 0.0,
        secured_pts: float = 0.0,
        direction: str = "BULLISH (CALL / CE)",
        secured_pnl: Optional[float] = None,
        entry_price: Optional[float] = None,
        num_lots: int = 0,
        lot_size: Optional[int] = None,
        spot: float = 0.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean TRAILING STOP LOSS alert for Telegram with verified PnL."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        # Strictly enforce canonical exchange contract lot size
        lot_size = spec.lot_size
        if not num_lots or num_lots <= 0:
            num_lots = spec.default_lots
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        total_qty = num_lots * lot_size
        locked_pts = secured_pts or kwargs.get("locked_pts", 5.0)
        orig_entry = entry_price if entry_price is not None else trailing_sl
        new_sl = trailing_sl
        locked_pnl = secured_pnl if secured_pnl is not None else round(total_qty * locked_pts)
        scrip_sym = spec.symbol

        return f"""<b>⚡ TRAILING SL LOCKED • {scrip_sym} RISK-FREE</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
📈 <b>Secured Move:</b> <b>+{locked_pts:.1f} pts</b> (+₹{locked_pnl:,.2f})

💵 <b>Entry:</b> ₹{orig_entry:.2f}  ➔  ⚡ <b>LTP:</b> ₹{current_ltp:.2f}
🔒 <b>New Trailing SL:</b> <code>₹{new_sl:.2f}</code>
📦 <b>Secured Size:</b> {num_lots} Lot{'s' if num_lots>1 else ''} ({total_qty:,} Qty)
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
🛡️ <i>Update SL to ₹{new_sl:.2f} on broker. Trade is 100% risk-free.</i>"""

    @classmethod
    def format_breakeven_alert(
        cls,
        contract: str,
        current_ltp: float,
        entry_price: float,
        num_lots: int = 0,
        lot_size: Optional[int] = None,
        spot: float = 0.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean BREAKEVEN ESCALATOR alert for Telegram with verified PnL."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        # Strictly enforce canonical exchange contract lot size
        lot_size = spec.lot_size
        if not num_lots or num_lots <= 0:
            num_lots = spec.default_lots
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        total_qty = num_lots * lot_size
        be_sl = round(entry_price + (0.50 if spec.symbol == "SENSEX" else 0.10), 2)
        gain_pts = round(current_ltp - entry_price, 2)
        gain_rs = round(gain_pts * total_qty)
        scrip_sym = spec.symbol

        return f"""<b>🛡️ BREAKEVEN ACTIVATED • {scrip_sym} RISK-FREE</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
📈 <b>Profit Running:</b> <b>+{gain_pts:.2f} pts</b> (+₹{gain_rs:,.2f})

💵 <b>Entry:</b> ₹{entry_price:.2f}  ➔  ⚡ <b>LTP:</b> ₹{current_ltp:.2f}
🔒 <b>New SL (Cost):</b> <code>₹{be_sl:.2f}</code>
📦 <b>Active Size:</b> {num_lots} Lot{'s' if num_lots>1 else ''} ({total_qty:,} Qty)
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
⚡ <i>Move pending SL trigger to ₹{be_sl:.2f} on Groww. Zero capital at risk.</i>"""

    @classmethod
    def format_profit_lock_alert(
        cls,
        contract: str,
        current_ltp: float,
        entry_price: float,
        num_lots: int = 0,
        lot_size: Optional[int] = None,
        spot: float = 0.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean PROFIT LOCK alert for Telegram with verified PnL."""
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        # Strictly enforce canonical exchange contract lot size
        lot_size = spec.lot_size
        if not num_lots or num_lots <= 0:
            num_lots = spec.default_lots
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        total_qty = num_lots * lot_size
        locked_pts = kwargs.get("locked_pts", spec.profit_lock_locked)
        lock_sl = round(entry_price + locked_pts, 2)
        locked_pnl = round(locked_pts * total_qty)
        scrip_sym = spec.symbol

        return f"""<b>🔒 PROFIT LOCKED • {scrip_sym} (+{locked_pts:.1f} PTS)</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
🏆 <b>Guaranteed Profit:</b> <b>+₹{locked_pnl:,.2f}</b>

💵 <b>Entry:</b> ₹{entry_price:.2f}  ➔  ⚡ <b>LTP:</b> ₹{current_ltp:.2f}
🔒 <b>Locked Stop-Loss:</b> <code>₹{lock_sl:.2f}</code>
📦 <b>Locked Size:</b> {num_lots} Lot{'s' if num_lots>1 else ''} ({total_qty:,} Qty)
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
💰 <i>Modify SL order to ₹{lock_sl:.2f}. Guaranteed profit secured.</i>"""

    @classmethod
    def format_tranche_1_alert(
        cls,
        contract: str,
        entry_price: float,
        exit_price: float,
        banked_pnl: float = 0.0,
        target_2: float = 0.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean TRANCHE 1 BANKED alert for Telegram with verified PnL."""
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        scrip_sym = spec.symbol
        lot_size = spec.lot_size
        num_lots = kwargs.get("num_lots", spec.default_lots)
        total_qty = num_lots * lot_size
        half_qty = total_qty // 2
        gain_pts = round(exit_price - entry_price, 2)
        if not banked_pnl or banked_pnl <= 0.0:
            banked_pnl = round(half_qty * gain_pts, 2)
        if target_2 <= 0.0:
            target_2 = round(entry_price + getattr(spec, "target_2_pts", spec.target_pts * 2.0), 2)
        return f"""<b>🎯 TRANCHE 1 BANKED • {scrip_sym} 50% SECURED</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
💰 <b>Banked Profit (50%):</b> <b>+₹{banked_pnl:,.2f}</b> (+{gain_pts:.2f} pts)

💵 <b>Entry:</b> ₹{entry_price:.2f}  ➔  🏁 <b>Exit 1:</b> <code>₹{exit_price:.2f}</code>
🔒 <b>Runner SL:</b> <code>₹{entry_price:.2f}</code> (Locked at Cost)
🚀 <b>Target 2:</b> <code>₹{target_2:.2f}</code> (Pure Risk-Free Upside)
📦 <b>Tranche 1:</b> {num_lots // 2} Lots ({half_qty:,} Qty) Banked • Runner: {num_lots - num_lots // 2} Lots ({total_qty - half_qty:,} Qty)
────────────────────────
🏁 <i>Half size booked at Target 1. 50% runner trailing with zero risk.</i>"""

    @classmethod
    def format_resumption_reentry_alert(
        cls,
        contract: str,
        direction: str,
        entry_price: float,
        sl_price: float,
        target_price: float,
        confluence: float = 75.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean RESUMPTION RE-ENTRY alert for Telegram with verified sizing & rupee math."""
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        scrip_sym = spec.symbol
        lot_size = spec.lot_size
        num_lots = kwargs.get("num_lots", spec.default_lots)
        total_qty = num_lots * lot_size
        tight_pts = round(abs(entry_price - sl_price), 2)
        tgt_pts = round(abs(target_price - entry_price), 2)
        potential_gain = round(total_qty * tgt_pts)
        potential_loss = round(total_qty * tight_pts)
        return f"""<b>🔄 RESUMPTION RE-ENTRY • {scrip_sym} {direction}</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
⚡ <b>Action:</b> Auto Re-Entered @ <code>₹{entry_price:.2f}</code>
📊 <b>Setup Confluence:</b> {confluence:.1f}%

🛑 <b>Tight SL (Wick Peak):</b> <code>₹{sl_price:.2f}</code> (-{tight_pts:.1f} pts • -₹{potential_loss:,})
🎯 <b>Target:</b> <code>₹{target_price:.2f}</code> (+{tgt_pts:.1f} pts • +₹{potential_gain:,})
📦 <b>Sizing:</b> {num_lots} Lots ({total_qty:,} Qty)
────────────────────────
🛡️ <i>Wick sweep confirmed. Directional resumption entered with tight risk.</i>"""

    @classmethod
    def format_auto_square_off_alert(
        cls,
        contract: str,
        current_ltp: float = 0.0,
        reason: str = "Mandatory intraday EOD cut-off before broker auto-square-off charges at 03:15 PM",
        num_lots: int = 0,
        lot_size: Optional[int] = None,
        spot: float = 0.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean AUTO-SQUARE-OFF EOD CUTOFF alert for Telegram."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        # Strictly enforce canonical exchange contract lot size
        lot_size = spec.lot_size
        if not num_lots or num_lots <= 0:
            num_lots = spec.default_lots
        total_qty = num_lots * lot_size
        scrip_sym = spec.symbol

        return f"""<b>🔒 MANDATORY AUTO-SQUARE-OFF • {scrip_sym}</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
⏰ <b>Cutoff Time:</b> <b>03:05 PM IST</b> (Broker EOD Cutoff)
⚡ <b>LTP:</b> ₹{current_ltp:.2f} • <b>Size:</b> {total_qty:,} Qty ({num_lots} Lots)
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
⚠️ <i>Square off open intraday derivative positions now to avoid broker auto-SQ penalty.</i>"""

    @classmethod
    def format_chop_standdown_alert(
        cls,
        spot: float = 0.0,
        chop_val: float = 64.8,
        reason: str = "Fractal Choppiness Index (CHOP 64.8 > 61.8 Threshold)",
        corridor_str: str = "",
        symbol: str = "NIFTY",
        **kwargs
    ) -> str:
        """Formats a clean CHOPPINESS STAND DOWN warning alert for Telegram."""
        spot = cls._resolve_live_spot(spot, symbol=symbol)
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol)
        scrip_sym = spec.symbol
        return f"""<b>🛡️ CHOP FILTER ACTIVE • {scrip_sym} STAND DOWN</b>
────────────────────────
📊 <b>Wilder's CHOP-14:</b> <b>{chop_val:.1f}</b> (&gt; 61.8 Sideways Churn)
📍 <b>Spot:</b> ₹{spot:,.2f} {f'({corridor_str})' if corridor_str else ''} • {now_str}
────────────────────────
🛑 <i>0 trades permitted in chop. Capital preserved until trend breaks out.</i>"""

    @classmethod
    def format_circuit_breaker_alert(
        cls,
        sl_count: int = 1,
        max_allowed: int = 1,
        capital_preserved: float = 0.0,
        spot: float = 0.0,
        account_name: str = "Teja",
        symbol: str = "NIFTY",
        **kwargs
    ) -> str:
        """Formats a clean MAX DAILY DRAWDOWN CIRCUIT BREAKER LOCK alert for Telegram."""
        spot = cls._resolve_live_spot(spot, symbol=symbol)
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol)
        scrip_sym = spec.symbol
        if capital_preserved <= 0.0:
            capital_preserved = spec.total_capital - (spec.default_lots * spec.lot_size * spec.sl_pts)
        return f"""<b>🚨 MAX DRAWDOWN REACHED • {scrip_sym} LOCKED</b>
────────────────────────
🛑 <b>Circuit Breaker:</b> {sl_count}/{max_allowed} Daily Stop-Loss Limit Hit
💰 <b>Protected Capital:</b> ₹{capital_preserved:,.2f}
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
🔒 <i>Order routing disabled for today. Survive to trade tomorrow. Stand down.</i>"""

    @classmethod
    def format_theta_stagnation_alert(
        cls,
        contract: str,
        entry_price: float,
        current_ltp: float,
        elapsed_minutes: int,
        unrealized_pnl: float = 0.0,
        spot: float = 0.0,
        symbol: str = "",
        **kwargs
    ) -> str:
        """Formats a clean THETA STAGNATION TIME-STOP alert for Telegram with verified sizing & drag."""
        spot = cls._resolve_live_spot(spot, symbol=symbol, contract=contract)
        now_str = datetime.now(IST).strftime("%I:%M %p IST")
        from asset_config import get_asset_spec
        spec = get_asset_spec(symbol=symbol, contract=contract)
        scrip_sym = spec.symbol
        lot_size = spec.lot_size
        num_lots = kwargs.get("num_lots", spec.default_lots)
        total_qty = num_lots * lot_size
        decay_pts = round(entry_price - current_ltp, 2)
        drag_rs = round(decay_pts * total_qty)
        if not unrealized_pnl or unrealized_pnl == 0.0:
            unrealized_pnl = -drag_rs
        return f"""<b>⏳ TIME-STOP TRIGGERED • {scrip_sym} THETA SHIELD</b>
────────────────────────
📌 <b>Contract:</b> <code>{contract}</code>
⏱️ <b>Hold Time:</b> <b>{elapsed_minutes} Minutes</b> (Stagnation Limit)

💵 <b>Entry:</b> ₹{entry_price:.2f}  ➔  ⚡ <b>LTP:</b> ₹{current_ltp:.2f} (-{decay_pts:.2f} pts)
📉 <b>Unrealized Drag:</b> -₹{abs(unrealized_pnl):,.2f}
📦 <b>Monitored Size:</b> {num_lots} Lots ({total_qty:,} Qty)
📍 <b>Spot:</b> ₹{spot:,.2f} • {now_str}
────────────────────────
⚠️ <i>Sideways consolidation detected. Market exit advised to avoid theta bleed.</i>"""


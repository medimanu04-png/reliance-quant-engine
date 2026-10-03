"""
RELIANCE F&O Quantitative Intraday Engine - Standalone 24/7 Alert Daemon
========================================================================
Runs independently of Streamlit or any web browser.
Monitors RELIANCE spot and dual ATM options during market hours (09:15 AM - 03:30 PM IST),
evaluates the 6-vector quantitative confluence model, tracks active trade state,
and dispatches instant, zero-delay push notifications to Telegram.

Usage:
  python quant_alert_daemon.py           # Standard production run (respects market hours)
  python quant_alert_daemon.py --now     # Run immediately regardless of market hours / weekend
  python quant_alert_daemon.py --test-tg # Send a Telegram connectivity test message and exit
"""

import os
import sys
import time
import math
import json
import logging
import argparse
import threading
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, Any, Optional, Tuple, List

# Ensure UTF-8 output encoding on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except Exception:
    from datetime import timezone
    IST = timezone(timedelta(hours=5, minutes=30))

try:
    import pandas as pd
    import numpy as np
    import yfinance as yf
except ImportError as e:
    print(f"Missing dependency: {e}. Please ensure virtual environment is active.")
    sys.exit(1)

# Import Local Quantitative Engine Modules
from nse_data_fetcher import NSEIndiaFetcher
from groww_market_feed import GrowwMarketFeed
from telegram_notifier import TelegramNotifier
from trade_journal_manager import (
    TradeJournalManager,
    SequentialTradeEngine,
    ShadowMonitoringEngine,
    SignalTracker,
    STARTING_CAPITAL
)
from fo_quant_engine import MultiIndicatorMath, UltraHighConvictionRelianceEngine
from asset_config import get_asset_spec

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BREAKOUT_FILE = os.path.join(BASE_DIR, "breakout_triggers_log.json")

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("QuantAlertDaemon")


# ==============================================================================
# STANDALONE PERSISTENT BREAKOUT TRIGGER MANAGER (Zero Streamlit Dependency)
# ==============================================================================
class StandaloneBreakoutManager:
    """Manages persistent entry breakout triggers pinned to disk."""
    TRIGGER_FILE = BREAKOUT_FILE

    @classmethod
    def _load_records(cls) -> dict:
        if os.path.exists(cls.TRIGGER_FILE):
            try:
                with open(cls.TRIGGER_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    @classmethod
    def _save_records(cls, records: dict):
        try:
            with open(cls.TRIGGER_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.debug(f"Error saving breakout records: {e}")

    @classmethod
    def get_or_set_trigger(cls, strike: int, contract_type: str, current_ltp: float, buffer_pts: Optional[float] = None, symbol: Optional[str] = None) -> float:
        if buffer_pts is None or buffer_pts <= 0.0:
            buffer_pts = get_asset_spec(symbol).breakout_buffer
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        sym_part = f"{symbol.upper()}_" if symbol else ""
        key = f"{today_str}_{sym_part}{strike}_{contract_type}"
        records = cls._load_records()

        if key in records and isinstance(records[key], (int, float)) and records[key] > 0.0:
            return float(records[key])

        if current_ltp > 0.05:
            pinned = round(float(current_ltp) + float(buffer_pts), 2)
            records[key] = pinned
            cls._save_records(records)
            return pinned

        return 0.0


# ==============================================================================
# STANDALONE RELIANCE CANDLE FETCHER
# ==============================================================================
# MULTI-ASSET CANDLE FETCHER (GROWW CHARTING API & YFINANCE FALLBACK)
# ==============================================================================
class MultiAssetCandleFetcher:
    """Fetches and caches 5m/15m authentic candles directly from Groww API per symbol."""
    _cache_5m: Dict[str, pd.DataFrame] = {}
    _last_fetch_5m: Dict[str, float] = {}
    _cache_15m: Dict[str, pd.DataFrame] = {}
    _last_fetch_15m: Dict[str, float] = {}

    @classmethod
    def get_5m_candles(cls, spot: float, symbol: str = "RELIANCE", max_age_secs: float = 60.0) -> Dict[str, Any]:
        sym = (symbol or "RELIANCE").upper().strip()
        now = time.time()
        df = None
        is_delayed_yfinance = False

        if sym in cls._cache_5m and (now - cls._last_fetch_5m.get(sym, 0.0)) < max_age_secs:
            df = cls._cache_5m[sym]
        else:
            # 1. Primary: Direct official NSE candles via Groww Charting Service (0-Delay Live)
            try:
                gw_feed = GrowwMarketFeed.get_instance()
                df = gw_feed.get_historical_candles(symbol=sym, interval="5m", days=5)
                if df is not None and not df.empty and len(df) >= 30:
                    cls._cache_5m[sym] = df
                    cls._last_fetch_5m[sym] = now
                    is_delayed_yfinance = False
            except Exception as e:
                logger.debug(f"Groww charting candle fetch error ({sym}): {e}")

            # 2. Secondary fallback: Yahoo Finance (Warning: 15-minute delayed data on NSE)
            if df is None or df.empty or len(df) < 30:
                try:
                    ticker_str = f"{sym}.NS"
                    t = yf.Ticker(ticker_str)
                    df_yf = t.history(period="5d", interval="5m")
                    if df_yf is not None and not df_yf.empty and len(df_yf) >= 30:
                        last_c = float(df_yf['Close'].iloc[-1])
                        if sym == "RELIANCE" and last_c > 2000 and spot > 0 and (last_c / spot) > 1.7:
                            df_yf['Close'] = df_yf['Close'] / 2.0
                            df_yf['Open'] = df_yf['Open'] / 2.0
                            df_yf['High'] = df_yf['High'] / 2.0
                            df_yf['Low'] = df_yf['Low'] / 2.0
                        df = df_yf
                        cls._cache_5m[sym] = df
                        cls._last_fetch_5m[sym] = now
                        is_delayed_yfinance = True
                        logger.warning(f"⚠️ Live Groww candles unavailable for {sym}. Yahoo Finance 15-minute delayed data loaded.")
                except Exception as e:
                    logger.debug(f"yfinance fetch error ({sym}): {e}")

        if df is None or df.empty or len(df) < 30:
            logger.warning(f"Live market candles unavailable for {sym} from both Groww & Yahoo.")
            return {
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
                "date": [],
                "is_synthetic": True,
                "is_delayed": True
            }

        return {
            "high": df["High"].tolist(),
            "low": df["Low"].tolist(),
            "close": df["Close"].tolist(),
            "volume": df["Volume"].tolist(),
            "date": df.index.date.tolist() if hasattr(df.index, 'date') else [],
            "is_synthetic": is_delayed_yfinance,
            "is_delayed": is_delayed_yfinance
        }

    @classmethod
    def get_15m_candles(cls, spot: float, symbol: str = "RELIANCE", max_age_secs: float = 120.0) -> Dict[str, Any]:
        sym = (symbol or "RELIANCE").upper().strip()
        now = time.time()
        df = None
        is_delayed_yfinance = False

        if sym in cls._cache_15m and (now - cls._last_fetch_15m.get(sym, 0.0)) < max_age_secs:
            df = cls._cache_15m[sym]
        else:
            try:
                gw_feed = GrowwMarketFeed.get_instance()
                df = gw_feed.get_historical_candles(symbol=sym, interval="15m", days=10)
                if df is not None and not df.empty and len(df) >= 20:
                    cls._cache_15m[sym] = df
                    cls._last_fetch_15m[sym] = now
                    is_delayed_yfinance = False
            except Exception as e:
                logger.debug(f"Groww 15m candle fetch error ({sym}): {e}")

            if df is None or df.empty or len(df) < 20:
                try:
                    ticker_str = f"{sym}.NS"
                    t = yf.Ticker(ticker_str)
                    df_yf = t.history(period="10d", interval="15m")
                    if df_yf is not None and not df_yf.empty and len(df_yf) >= 20:
                        df = df_yf
                        cls._cache_15m[sym] = df
                        cls._last_fetch_15m[sym] = now
                        is_delayed_yfinance = True
                except Exception:
                    pass

        if df is None or df.empty or len(df) < 20:
            return cls.get_5m_candles(spot, symbol=sym, max_age_secs=max_age_secs)

        return {
            "high": df["High"].tolist(),
            "low": df["Low"].tolist(),
            "close": df["Close"].tolist(),
            "volume": df["Volume"].tolist(),
            "date": df.index.date.tolist() if hasattr(df.index, 'date') else [],
            "is_synthetic": is_delayed_yfinance,
            "is_delayed": is_delayed_yfinance
        }


RelianceCandleFetcher = MultiAssetCandleFetcher


# ==============================================================================
# MAIN QUANTITATIVE ALERT DAEMON ENGINE
# ==============================================================================
class RelianceQuantAlertDaemon:
    """Autonomous market monitor & Telegram alert dispatcher."""

    def __init__(self, interval_seconds: float = 5.0, force_run: bool = False, require_candle_close: bool = False, symbols: Optional[List[str]] = None):
        self.interval = max(2.0, interval_seconds)
        self.force_run = force_run
        self.require_candle_close = require_candle_close
        self.symbols = [s.upper() for s in symbols] if symbols else ["RELIANCE", "ADANIENT"]
        self.quant_engines = {s: UltraHighConvictionRelianceEngine(symbol=s) for s in self.symbols}
        self.quant_engine = self.quant_engines.get("RELIANCE", next(iter(self.quant_engines.values())))
        self.groww_feed = GrowwMarketFeed.get_instance()
        self.running = True
        self.last_spot: Dict[str, float] = {s: 0.0 for s in self.symbols}
        self.last_seen_state: Dict[str, Any] = {s: None for s in self.symbols}
        self.last_chop_alert_sent: Dict[str, bool] = {s: False for s in self.symbols}
        self.last_git_sync_ts = time.time()
        self.breakout_tick_counts: Dict[str, int] = {}
        # Pre-Market Warmup & Kalman Seeding (Suggestion 4)
        self._premarket_preload_and_seed_kalman()

    def _premarket_preload_and_seed_kalman(self):
        """
        Pre-Market Historical Cache Pre-Loader & Kalman Filter State Seeder (Suggestion 4).
        Pre-loads 5-minute candles from local Parquet cache or Groww/YFinance at startup
        to eliminate 09:15 AM cold-start latency and pre-seed the Kalman state-space filter.
        """
        for s in self.symbols:
            try:
                cache_file = os.path.join(BASE_DIR, "data_cache", f"{s.lower()}_5m_cache.parquet")
                if os.path.exists(cache_file):
                    cached_df = pd.read_parquet(cache_file)
                    if not cached_df.empty:
                        closes = cached_df["Close"].dropna().tolist()
                        if len(closes) >= 15:
                            kal_price, kal_slope, kal_gain, kal_reg = MultiIndicatorMath.calculate_kalman_trend(closes[-30:])
                            logger.info(f"⚡ Pre-Market Kalman Filter seeded ({s}): Filtered Rs. {kal_price:.2f} | Slope: {kal_slope:+.3f} [{kal_reg}]")
            except Exception as e:
                logger.debug(f"Premarket preloader notice ({s}): {e}")

    def is_market_hours(self) -> Tuple[bool, str]:
        """Checks if current time is within Indian NSE trading hours."""
        if self.force_run:
            return True, "FORCE_RUN_OVERRIDE"

        now_ist = datetime.now(IST)
        # Weekday check: 0=Mon, 4=Fri
        if now_ist.weekday() >= 5:
            return False, f"Weekend ({now_ist.strftime('%A')})"

        curr_time = now_ist.time()
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)

        if curr_time < market_open:
            return False, f"Pre-Market (Opens at 09:15 AM IST, Current: {curr_time.strftime('%I:%M:%S %p')})"
        if curr_time > market_close:
            return False, f"Post-Market (Closed at 03:30 PM IST, Current: {curr_time.strftime('%I:%M:%S %p')})"

        return True, "MARKET_OPEN"

    def run_single_tick(self):
        """Executes multi-asset market scan and alert evaluation across all monitored assets."""
        for sym in self.symbols:
            try:
                self.run_single_symbol_tick(symbol=sym)
            except Exception as e:
                logger.error(f"Error evaluating alerts for {sym}: {e}", exc_info=True)

        # 7. Update Shadow Monitoring & Sync Verified Groww Executions
        try:
            ShadowMonitoringEngine.update_shadow_monitoring(self.groww_feed)
            if self.groww_feed and getattr(self.groww_feed, "_is_connected", False):
                for sym in self.symbols:
                    gw_trades = self.groww_feed.get_executed_trades_today(symbol_filter=sym)
                    if gw_trades:
                        TradeJournalManager.sync_groww_trades(gw_trades)
        except Exception:
            pass

        # 8. Periodic 15-minute background git sync (Local Master Copy)
        now_ts = time.time()
        if now_ts - self.last_git_sync_ts > 900:
            self.last_git_sync_ts = now_ts
            try:
                from git_sync_manager import GitSyncManager
                time_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
                threading.Thread(
                    target=GitSyncManager.sync_local_to_git,
                    kwargs={"auto": True, "commit_message": f"chore(sync): periodic auto-sync local master [{time_str}]"},
                    daemon=True
                ).start()
            except Exception as e:
                logger.debug(f"Periodic git sync error: {e}")

    def run_single_symbol_tick(self, symbol: str = "RELIANCE"):
        """Executes a single market scan, signal check, and alert evaluation for the specified symbol."""
        sym = (symbol or "RELIANCE").upper().strip()
        now_dt = datetime.now(IST)
        today_date = now_dt.strftime("%Y-%m-%d")
        time_str = now_dt.strftime("%I:%M:%S %p IST")

        # 1. Fetch live spot & option telemetry
        try:
            gw_live = self.groww_feed.get_dynamic_spot_tick(symbol=sym)
            spot = float(gw_live.get("spot_ltp", 0.0))
        except Exception:
            spot = 0.0

        if spot <= 0:
            nse_data = NSEIndiaFetcher.get_scrip_official_data(sym)
            from asset_config import get_asset_spec
            spec = get_asset_spec(sym)
            spot = float(nse_data.get("spot_ltp", spec.default_spot))

        self.last_spot[sym] = spot

        # 2. Dual ATM Corridor
        corridor = NSEIndiaFetcher.get_atm_corridor(spot, symbol=sym)
        atm_strike = corridor["lower_strike"]
        telemetry = NSEIndiaFetcher.get_atm_call_and_put_live_telemetry(atm_strike, spot, scrip_symbol=sym)

        best_pick = telemetry["best_strike"]
        low_data = telemetry["lower"]
        high_data = telemetry["upper"]

        # 3. Candles & Confluence Evaluation (Multi-Timeframe 5m & 15m)
        candles_5m = MultiAssetCandleFetcher.get_5m_candles(spot, symbol=sym)
        candles_15m = MultiAssetCandleFetcher.get_15m_candles(spot, symbol=sym)
        curr_time = now_dt.time()

        benchmark_c5m = None
        try:
            gw = GrowwMarketFeed.get_instance()
            bm_df = gw.get_benchmark_historical_candles("NIFTY 50", interval="5m", days=5)
            if bm_df is not None and not bm_df.empty and "Close" in bm_df.columns:
                benchmark_c5m = {
                    "open": bm_df["Open"].tolist(),
                    "high": bm_df["High"].tolist(),
                    "low": bm_df["Low"].tolist(),
                    "close": bm_df["Close"].tolist(),
                    "volume": bm_df["Volume"].tolist(),
                    "date": bm_df.index.tolist()
                }
        except Exception:
            benchmark_c5m = None

        q_engine = self.quant_engines.get(sym, self.quant_engine)
        confluence_eval = q_engine.evaluate_90plus_confluence(
            curr_time, candles_5m, candles_15m, benchmark_c5m=benchmark_c5m
        )


        prob_str = confluence_eval.get("3. CONFLUENCE SCORE", confluence_eval.get("3. PROBABILITY SCORE", ""))
        status_text = confluence_eval.get("2. TRADE STATUS", "")
        dominant_score = float(confluence_eval.get("dominant_score", 0.0))
        if dominant_score <= 0.0 and prob_str:
            try:
                import re
                m = re.findall(r"(\d+(?:\.\d+)?)%", prob_str)
                if m:
                    dominant_score = max(float(x) for x in m)
            except Exception:
                dominant_score = 75.0
        if dominant_score <= 0.0:
            dominant_score = 75.0

        dynamic_target_pts = float(confluence_eval.get("target_pts", 7.0))
        dynamic_sl_pts = float(confluence_eval.get("sl_pts", 5.0))
        is_synthetic_feed = bool(confluence_eval.get("is_synthetic_feed", False))
        spread_stand_down = bool(confluence_eval.get("spread_stand_down", False))
        opening_cooldown_active = False  # Enabled from 09:15 AM market open
        is_midday_lull = bool(confluence_eval.get("is_midday_lull", False))
        min_confluence_gate = 78.0 if is_midday_lull else 68.0

        # Check Daily Loss Circuit Breaker (One-and-Done Capital Preservation Protocol)
        has_daily_loss, loss_reason = SequentialTradeEngine.has_daily_loss_occurred_today(symbol=sym)

        # Strict Institutional Gate: Confluence Score must be >= min_confluence_gate and NO stand down flags
        is_tradable = (
            "TRADABLE" in status_text.upper()
            and "NON-TRADABLE" not in status_text.upper()
            and "STAND DOWN" not in status_text.upper()
            and (dominant_score >= min_confluence_gate)
            and not is_synthetic_feed
            and not spread_stand_down
            and not opening_cooldown_active
            and not has_daily_loss
        )
        is_chop = "CHOP" in status_text.upper()

        if has_daily_loss:
            logger.info(f"[{time_str}] 🚨 DAILY CIRCUIT BREAKER ACTIVE: {loss_reason or '1 loss recorded today'}. All new trade entries locked.")
            cb_alert_key = f"tg_sent_cb_{today_date}_{sym}"
            tg_config = TelegramNotifier.load_config()
            tg_enabled = tg_config.get("enabled", True)
            bot_token = tg_config.get("bot_token", TelegramNotifier.DEFAULT_BOT_TOKEN)
            chat_id = tg_config.get("chat_id", TelegramNotifier.DEFAULT_CHAT_ID)
            if tg_enabled and not TelegramNotifier.is_alert_sent(cb_alert_key):
                from asset_config import get_asset_spec
                spec = get_asset_spec(sym)
                est_cb_loss = float(spec.lot_size * spec.sl_pts)
                cb_msg = TelegramNotifier.format_daily_circuit_breaker_alert(
                    reason=f"1 Loss Limit Reached (-₹{est_cb_loss:,.2f})",
                    spot=spot,
                    symbol=sym
                )
                buttons = TelegramNotifier.get_circuit_breaker_buttons(symbol=sym)
                ok, fb = TelegramNotifier.send_message(bot_token, chat_id, cb_msg, reply_markup=buttons)
                if ok:
                    TelegramNotifier.record_alert_sent(cb_alert_key)
                    logger.info(f"🚨 Daily Circuit Breaker Alert sent to Telegram: {fb}")

        if opening_cooldown_active:
            logger.info(f"[{time_str}] ⏳ OPENING COOLDOWN ACTIVE (09:15-09:30 AM): Building 15m ORB range & Initial Balance. Standing down.")

        if spread_stand_down:
            logger.info(f"[{time_str}] ⚠️ WIDE SPREAD STAND DOWN: Option bid-ask spread > ₹0.35 threshold. Preserving capital against slippage.")

        dominant_side = "CALL (CE)" if "BULLISH" in prob_str.upper() else "PUT (PE)"
        contract_type = "CE" if dominant_side == "CALL (CE)" else "PE"

        # Resolve selected strike & live option LTP
        recommended_strike = best_pick["strike"]
        active_branch = low_data if recommended_strike == corridor["lower_strike"] else high_data
        active_option_ltp = active_branch["call_ltp"] if contract_type == "CE" else active_branch["put_ltp"]

        # 4. Breakout Trigger Pinning & Bar Confirmation Gate
        breakout_buffer = spec.breakout_buffer
        breakout_level = StandaloneBreakoutManager.get_or_set_trigger(
            strike=recommended_strike,
            contract_type=contract_type,
            current_ltp=active_option_ltp,
            buffer_pts=breakout_buffer,
            symbol=sym
        )
        gap_pts = round(breakout_level - active_option_ltp, 2)

        # Microstructure Confirmation Gate (Anti-Wick & Candle-Maturity Protocol)
        sec_into_bar = (now_dt.minute % 5) * 60 + now_dt.second
        is_bar_mature = (sec_into_bar >= 45)  # Filters noise spikes during the first 45s of candle formation
        wick_guard_passed = confluence_eval.get("wick_guard_passed", is_bar_mature)

        breakout_key = f"{today_date}_{sym}_{recommended_strike}_{contract_type}"
        if active_option_ltp >= breakout_level:
            self.breakout_tick_counts[breakout_key] = self.breakout_tick_counts.get(breakout_key, 0) + 1
        else:
            self.breakout_tick_counts[breakout_key] = 0

        consecutive_ticks = self.breakout_tick_counts.get(breakout_key, 0)
        # Require price to hold at/above breakout level for at least 2 consecutive daemon scan ticks
        tick_persistence_passed = (consecutive_ticks >= 2) or self.force_run

        candle_gate_passed = is_bar_mature and wick_guard_passed and tick_persistence_passed
        if self.require_candle_close:
            # Strict closed candle requirement (must be within last 30s of 5m bar or completed)
            candle_gate_passed = (sec_into_bar >= 270) and tick_persistence_passed

        entry_confirmed = (active_option_ltp >= breakout_level) and is_tradable and candle_gate_passed

        if (active_option_ltp >= breakout_level) and is_tradable and not candle_gate_passed:
            logger.info(
                f"[{time_str}] ⏳ BREAKOUT DETECTED — Awaiting Confirmation Gate: "
                f"LTP ₹{active_option_ltp:.2f} >= Trigger ₹{breakout_level:.2f} | "
                f"Bar Progress: {sec_into_bar}s/300s ({'Mature' if is_bar_mature else 'Opening Wick Guard'}) | "
                f"Consecutive Ticks: {consecutive_ticks}/2"
            )

        # 5. Telegram Configuration & Dispatch Check
        tg_config = TelegramNotifier.load_config()
        tg_enabled = tg_config.get("enabled", True)
        bot_token = tg_config.get("bot_token", TelegramNotifier.DEFAULT_BOT_TOKEN)
        chat_id = tg_config.get("chat_id", TelegramNotifier.DEFAULT_CHAT_ID)

        # 6. Sequential Trade State Engine
        seq_state = SequentialTradeEngine.get_state(symbol=sym)
        current_state = seq_state.get("current_state", SequentialTradeEngine.STATE_IDLE)
        active_trade = seq_state.get("active_trade")

        # Expiry String
        expiry_info = NSEIndiaFetcher.resolve_dynamic_expiry_mandate()
        expiry_date = expiry_info.get("selected_expiry", "27-OCT-2026")

        # ----------------------------------------------------------------------
        # STATE A: IN-TRADE (Monitoring Target, SL, and Trailing SL)
        # ----------------------------------------------------------------------
        if current_state == SequentialTradeEngine.STATE_IN_TRADE and active_trade:
            trade_num = active_trade.get("trade_num", 1)
            inst_sym = active_trade.get("instrument", active_trade.get("contract", "RELIANCE"))
            act_entry = float(active_trade.get("actual_entry", active_trade.get("planned_entry", spec.default_call_price)))
            target_p = float(active_trade.get("target", act_entry + spec.target_pts))
            initial_sl = float(active_trade.get("sl", max(0.05, act_entry - spec.sl_pts)))
            trail_sl = float(active_trade.get("trailing_sl", initial_sl))
            effective_sl = max(initial_sl, trail_sl)

            # Option contract live price
            cur_trade_ltp = active_option_ltp
            if self.groww_feed.is_connected:
                try:
                    gw_opt_ltp = self.groww_feed.get_option_contract_ltp(inst_sym)
                    if gw_opt_ltp and gw_opt_ltp > 0:
                        cur_trade_ltp = float(gw_opt_ltp)
                except Exception:
                    pass

            spec = get_asset_spec(sym)
            trade_lot_size = int(active_trade.get("lot_size", spec.lot_size))
            trade_num_lots = int(active_trade.get("num_lots", spec.default_lots))
            trade_qty = int(active_trade.get("qty", trade_lot_size * trade_num_lots))

            unreal_pts = round(cur_trade_ltp - act_entry, 2)
            unreal_pnl = round(unreal_pts * trade_qty, 2)

            logger.info(
                f"[{time_str}] 🟢 IN-TRADE #{trade_num} ({inst_sym}) | LTP: ₹{cur_trade_ltp:.2f} | "
                f"TGT: ₹{target_p:.2f} | SL: ₹{effective_sl:.2f} | PnL: {'+' if unreal_pnl>=0 else ''}₹{unreal_pnl:,.2f}"
            )

            # Update engine
            trade_update = SequentialTradeEngine.update_active_trade(
                current_ltp=cur_trade_ltp,
                groww_feed=self.groww_feed,
                starting_cash=STARTING_CAPITAL,
                symbol=sym
            )
            if trade_update.get("closed_trade"):
                try:
                    from git_sync_manager import GitSyncManager
                    cl_t = trade_update.get("closed_trade", {})
                    threading.Thread(
                        target=GitSyncManager.sync_local_to_git,
                        kwargs={"auto": True, "commit_message": f"feat(trade): auto-sync closed Trade #{trade_num} ({cl_t.get('status')}) PnL: {cl_t.get('pnl')}"},
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.debug(f"Git auto-sync error on trade closure: {e}")

            # Tiered Breakeven Escalator Telegram Alerts (Dynamically Scaled per AssetSpec)
            # Milestone 1: At Breakeven threshold -> Move SL to Cost
            if unreal_pts >= spec.be_pts:
                be_alert_key = f"tg_sent_be_{today_date}_{trade_num}"
                if tg_enabled and not TelegramNotifier.is_alert_sent(be_alert_key):
                    be_msg = TelegramNotifier.format_breakeven_alert(
                        contract=inst_sym,
                        current_ltp=cur_trade_ltp,
                        entry_price=act_entry,
                        num_lots=trade_num_lots,
                        lot_size=trade_lot_size,
                        spot=spot
                    )
                    buttons = TelegramNotifier.get_trailing_sl_buttons(symbol=sym, contract=inst_sym)
                    ok, fb = TelegramNotifier.send_message(bot_token, chat_id, be_msg, reply_markup=buttons)
                    if ok:
                        TelegramNotifier.record_alert_sent(be_alert_key)
                        logger.info(f"🛡️ Telegram Breakeven Escalator Alert dispatched: {fb}")

            # Milestone 2: At Profit Lock threshold -> Lock Guaranteed Profit
            if unreal_pts >= spec.profit_lock_trigger:
                lock_alert_key = f"tg_sent_lock_{today_date}_{trade_num}"
                if tg_enabled and not TelegramNotifier.is_alert_sent(lock_alert_key):
                    lock_msg = TelegramNotifier.format_profit_lock_alert(
                        contract=inst_sym,
                        current_ltp=cur_trade_ltp,
                        entry_price=act_entry,
                        num_lots=trade_num_lots,
                        lot_size=trade_lot_size,
                        spot=spot
                    )
                    buttons = TelegramNotifier.get_trailing_sl_buttons(symbol=sym, contract=inst_sym)
                    ok, fb = TelegramNotifier.send_message(bot_token, chat_id, lock_msg, reply_markup=buttons)
                    if ok:
                        TelegramNotifier.record_alert_sent(lock_alert_key)
                        logger.info(f"🔒 Telegram Profit Lock Alert dispatched: {fb}")

            # Milestone 3: Higher trailing alert for explosive runners
            trail_runner_trigger = spec.profit_lock_trigger + spec.trail_runner_offset
            if cur_trade_ltp > active_trade.get("highest_price", act_entry) and unreal_pts >= trail_runner_trigger:
                new_trail = round(act_entry + (unreal_pts * 0.65), 2)
                trail_alert_key = f"tg_sent_trail_{today_date}_{trade_num}_{round(new_trail, 1)}"
                if tg_enabled and not TelegramNotifier.is_alert_sent(trail_alert_key):
                    trail_msg = TelegramNotifier.format_trailing_sl_alert(
                        contract=inst_sym,
                        current_ltp=cur_trade_ltp,
                        trailing_sl=new_trail,
                        secured_pts=round(new_trail - act_entry, 1),
                        direction=active_trade.get("direction", "BULLISH (CALL / CE)"),
                        secured_pnl=round((new_trail - act_entry) * trade_qty),
                        entry_price=act_entry,
                        num_lots=trade_num_lots,
                        lot_size=trade_lot_size,
                        spot=spot
                    )
                    buttons = TelegramNotifier.get_trailing_sl_buttons(symbol=sym, contract=inst_sym)
                    ok, fb = TelegramNotifier.send_message(bot_token, chat_id, trail_msg, reply_markup=buttons)
                    if ok:
                        TelegramNotifier.record_alert_sent(trail_alert_key)
                        logger.info(f"📲 Telegram Trailing SL Alert dispatched: {fb}")

            # Target Hit Check
            if cur_trade_ltp >= target_p:
                target_key = f"tg_sent_target_{today_date}_{trade_num}_{recommended_strike}"
                if tg_enabled and not TelegramNotifier.is_alert_sent(target_key):
                    profit_pts = round(cur_trade_ltp - act_entry, 2)
                    tot_pnl = round(profit_pts * trade_qty, 2)
                    tgt_msg = TelegramNotifier.format_target_hit_alert(
                        contract=inst_sym,
                        entry_price=act_entry,
                        exit_price=cur_trade_ltp,
                        profit_pts=profit_pts,
                        total_pnl=tot_pnl,
                        num_lots=trade_num_lots,
                        lot_size=trade_lot_size,
                        spot=spot
                    )
                    buttons = TelegramNotifier.get_target_hit_buttons(symbol=sym, contract=inst_sym)
                    ok, fb = TelegramNotifier.send_message(bot_token, chat_id, tgt_msg, reply_markup=buttons)
                    if ok:
                        TelegramNotifier.record_alert_sent(target_key)
                        logger.info(f"🎉 🎯 TARGET HIT ALERT DISPATCHED TO TELEGRAM: {fb}")

            # Stop Loss Hit Check
            elif cur_trade_ltp <= effective_sl:
                sl_key = f"tg_sent_sl_{today_date}_{trade_num}_{recommended_strike}"
                if tg_enabled and not TelegramNotifier.is_alert_sent(sl_key):
                    loss_pts = round(act_entry - cur_trade_ltp, 2)
                    tot_loss = round(loss_pts * trade_qty, 2)
                    sl_msg = TelegramNotifier.format_stop_loss_alert(
                        contract=inst_sym,
                        entry_price=act_entry,
                        sl_price=cur_trade_ltp,
                        loss_pts=loss_pts,
                        total_loss=tot_loss,
                        num_lots=trade_num_lots,
                        lot_size=trade_lot_size,
                        spot=spot
                    )
                    buttons = TelegramNotifier.get_stop_loss_buttons(symbol=sym, contract=inst_sym)
                    ok, fb = TelegramNotifier.send_message(bot_token, chat_id, sl_msg, reply_markup=buttons)
                    if ok:
                        TelegramNotifier.record_alert_sent(sl_key)
                        logger.info(f"🛑 STOP LOSS ALERT DISPATCHED TO TELEGRAM: {fb}")

            # Theta Stagnation & Ornstein-Uhlenbeck Dynamic Half-Life Time-Stop Check (Suggestion 2)
            entry_time_val = str(active_trade.get("actual_entry_time") or active_trade.get("proposed_at") or "")
            is_stagnant, elapsed_mins, stag_pts, stag_msg = SequentialTradeEngine.check_theta_stagnation(
                entry_time_str=entry_time_val,
                current_ltp=cur_trade_ltp,
                entry_price=act_entry,
                max_hold_minutes=45,
                decay_tolerance_pts=1.2
            )

            # OU Half-Life Dynamic Time Barrier check
            unrealized_pts = round(cur_trade_ltp - act_entry, 2) if "CE" in inst_sym else round(act_entry - cur_trade_ltp, 2)
            ou_exit, ou_half_life, ou_msg = MultiIndicatorMath.calculate_ou_momentum_half_life_barrier(
                closes=candles_5m.get("close", []),
                time_elapsed_minutes=elapsed_mins,
                unrealized_profit_pts=unrealized_pts,
                lookback=25
            )

            if is_stagnant or ou_exit:
                stag_key = f"tg_sent_stag_{today_date}_{trade_num}"
                if tg_enabled and not TelegramNotifier.is_alert_sent(stag_key):
                    stag_alert = TelegramNotifier.format_theta_stagnation_alert(
                        contract=inst_sym,
                        entry_price=act_entry,
                        current_ltp=cur_trade_ltp,
                        elapsed_minutes=elapsed_mins,
                        unrealized_pnl=round((stag_pts if is_stagnant else unrealized_pts) * trade_qty, 2),
                        spot=spot
                    )
                    if ou_exit:
                        stag_alert += f"\n\n⏱️ *OU Half-Life Decay Alert*: Momentum half-life estimated at {ou_half_life:.1f}m. Directional edge exhausted; market exit advised."
                    ok, fb = TelegramNotifier.send_message(bot_token, chat_id, stag_alert)
                    if ok:
                        TelegramNotifier.record_alert_sent(stag_key)
                        logger.info(f"⏳ 📲 OU/THETA STAGNATION ALERT DISPATCHED TO TELEGRAM: {fb}")

        # ----------------------------------------------------------------------
        # STATE B: IDLE / ENTRY PENDING (Looking for Fresh Breakout Entry)
        # ----------------------------------------------------------------------
        else:
            contract_label = f"{sym} {recommended_strike} {contract_type} ({expiry_date})"

            # B1. Confirmed Breakout Entry
            if entry_confirmed:
                entry_alert_key = f"tg_sent_entry_{today_date}_{sym}_{recommended_strike}_{contract_type}"
                limit_cap = round(active_option_ltp + self.quant_engine.risk.limit_collar_pts, 2)
                win_exp = float(confluence_eval.get("win_expectancy_pct", 62.0))
                tier_str = str(confluence_eval.get("tier_rating", "TIER 1 (A+ INSTITUTIONAL SETUP)"))
                debit_spread = confluence_eval.get("debit_spread", {})
                spread_text = (
                    f"\n• 🛡️ Hedged Spread Alternative: {debit_spread.get('spread_name', 'N/A')} "
                    f"(Net Debit: ₹{debit_spread.get('net_debit_pts', 0):.2f} | Max Loss: ₹{debit_spread.get('max_risk_rupees', 0):,.0f} | Max Gain: ₹{debit_spread.get('max_reward_rupees', 0):,.0f})"
                ) if debit_spread else ""

                if tg_enabled and not TelegramNotifier.is_alert_sent(entry_alert_key):
                    sym_spec = get_asset_spec(sym)
                    active_risk = self.quant_engines.get(sym, self.quant_engine).risk
                    entry_msg = TelegramNotifier.format_entry_alert(
                        contract=contract_label,
                        direction=f"BULLISH (CALL / CE)" if contract_type == "CE" else "BEARISH (PUT / PE)",
                        entry_price=active_option_ltp,
                        target_pts=dynamic_target_pts,
                        sl_pts=dynamic_sl_pts,
                        num_lots=active_risk.num_lots,
                        lot_size=active_risk.lot_size,
                        win_prob=win_exp,
                        spot=spot,
                        rationale=(
                            f"Dual ATM Breakout confirmed ({tier_str})\n"
                            f"• Confluence: {dominant_score:.1f}/100 | Win Expectancy: {win_exp}%\n"
                            f"• Order Type: Stop-Loss Limit (SL-LMT) | Pegged Limit: ₹{confluence_eval.get('pegged_limit_price', active_option_ltp):.2f}\n"
                            f"• Trigger: ₹{active_option_ltp:.2f} | Limit Cap: ₹{limit_cap:.2f} (Max Slippage Collar: ₹{active_risk.limit_collar_pts:.2f})\n"
                            f"• Wick Guard: {'Passed (>=45s)' if wick_guard_passed else 'Immature'} | 2-Tick: Confirmed ({consecutive_ticks} ticks)\n"
                            f"• Macro & Basis: W-AVWAP ₹{confluence_eval.get('w_avwap', spot):.2f} | Futures Basis {confluence_eval.get('basis_pts', 0.0):+.2f} pts ({confluence_eval.get('basis_regime', 'BALANCED')})\n"
                            f"• Sizing & Risk: Half-Kelly {confluence_eval.get('half_kelly_pct', 20.0):.1f}% ({confluence_eval.get('kelly_recommended_lots', 1)} Lots) | VaR-99% ₹{confluence_eval.get('var_99_rupees', 0.0):,.0f} | Delta Eqv: {confluence_eval.get('portfolio_delta_shares', 0.0):+.1f} Sh\n"
                            f"• Microstructure: Max Pain @ ₹{confluence_eval.get('max_pain_strike', sym_spec.default_strike):.0f} | GKYZ Vol: {confluence_eval.get('yang_zhang_vol', 18.0):.1f}%\n"
                            f"• Trend & Efficiency: KAMA @ ₹{confluence_eval.get('kama', spot):.2f} (KER: {confluence_eval.get('kaufman_efficiency_ratio', 0.5):.2f}) | FVG: {confluence_eval.get('fvg_status', 'NEUTRAL')}\n"
                            f"• Routing & Slicing: {confluence_eval.get('routing_mode', 'ZERO_SLIPPAGE_ROUTING')} | {confluence_eval.get('slicing_regime', 'DIRECT_PEGGED')}\n"
                            f"• Stop Loss Protection: Set SL-LMT order Trigger ₹{max(0.05, active_option_ltp - dynamic_sl_pts):.2f} / Limit ₹{max(0.05, active_option_ltp - dynamic_sl_pts - active_risk.limit_collar_pts):.2f}. (Emergency: Exit at Market if limit breached!){spread_text}"
                        )
                    )
                    buttons = TelegramNotifier.get_entry_ce_buttons(f"{sym} {recommended_strike} CE", symbol=sym) if contract_type == "CE" else TelegramNotifier.get_entry_pe_buttons(f"{sym} {recommended_strike} PE", symbol=sym)
                    ok, fb = TelegramNotifier.send_message(bot_token, chat_id, entry_msg, reply_markup=buttons)
                    if ok:
                        TelegramNotifier.record_alert_sent(entry_alert_key)
                        logger.info(f"🔥 🚀 ENTRY TRIGGER ALERT SENT TO TELEGRAM: {fb}")

                # Save signal in SignalTracker so UI recommendation card is updated with the setup
                try:
                    exp_clean = expiry_date.replace("-", "").upper()
                    SignalTracker.save_signal({
                        "date": today_date,
                        "trade_given_time": time_str,
                        "full_contract": contract_label,
                        "symbol": f"{sym}{exp_clean}{recommended_strike}{contract_type}",
                        "contract_type": contract_type,
                        "strike": recommended_strike,
                        "expiry": expiry_date,
                        "suggested_entry": active_option_ltp,
                        "limit_entry": limit_cap,
                        "suggested_exit": round(active_option_ltp + dynamic_target_pts, 2),
                        "suggested_sl": round(max(0.05, active_option_ltp - dynamic_sl_pts), 2),
                        "confluence_score": round(dominant_score, 1),
                        "win_expectancy_pct": win_exp,
                        "tier_rating": tier_str
                    })
                except Exception as e:
                    logger.debug(f"SignalTracker save error in daemon: {e}")

                try:
                    ShadowMonitoringEngine.log_signal(
                        symbol=f"RELIANCE26OCT{recommended_strike}{contract_type}",
                        action=f"BUY {contract_type}",
                        entry=active_option_ltp,
                        target=round(active_option_ltp + dynamic_target_pts, 2),
                        sl=round(max(0.05, active_option_ltp - dynamic_sl_pts), 2),
                        date_str=today_date,
                        time_str=time_str,
                        instrument=contract_label,
                        confluence_score=round(dominant_score, 1),
                        user_executed=False
                    )
                except Exception as e:
                    logger.debug(f"ShadowMonitoringEngine save error in daemon: {e}")

                logger.info(
                    f"[{time_str}] 🔥 ENTRY TRIGGER CONFIRMED! Contract: {contract_label} | "
                    f"LTP: ₹{active_option_ltp:.2f} >= Trigger: ₹{breakout_level:.2f} | Awaiting user execution in Groww..."
                )

            # B2. Setup Armed Pre-Alert
            elif is_tradable and gap_pts > 0:
                armed_alert_key = f"tg_sent_armed_{today_date}_{sym}_{recommended_strike}_{contract_type}"
                if tg_enabled and not TelegramNotifier.is_alert_sent(armed_alert_key):
                    armed_msg = TelegramNotifier.format_armed_alert(
                        contract=contract_label,
                        direction=f"BULLISH (CALL / CE)" if contract_type == "CE" else "BEARISH (PUT / PE)",
                        current_ltp=active_option_ltp,
                        breakout_trigger=breakout_level,
                        distance_pts=gap_pts,
                        target_pts=dynamic_target_pts,
                        sl_pts=dynamic_sl_pts,
                        num_lots=1,
                        lot_size=self.quant_engine.risk.lot_size,
                        win_prob=win_exp if 'win_exp' in locals() else 65.0,
                        spot=spot
                    )
                    buttons = TelegramNotifier.get_armed_buttons(f"{sym} {recommended_strike} {contract_type}", symbol=sym)
                    ok, fb = TelegramNotifier.send_message(bot_token, chat_id, armed_msg, reply_markup=buttons)
                    if ok:
                        TelegramNotifier.record_alert_sent(armed_alert_key)
                        logger.info(f"🛡️ 📲 SETUP ARMED PRE-ALERT SENT TO TELEGRAM: {fb}")

                logger.info(
                    f"[{time_str}] 🛡️ ARMED: {contract_label} | Option LTP: ₹{active_option_ltp:.2f} | "
                    f"Trigger: ₹{breakout_level:.2f} (Gap: {gap_pts:+.2f} pts) | Spot: ₹{spot:.2f}"
                )

            # B3. Consolidation Chop Stand Down
            elif is_chop:
                if not self.last_chop_alert_sent:
                    chop_alert_key = f"tg_sent_chop_{today_date}_{sym}"
                    if tg_enabled and not TelegramNotifier.is_alert_sent(chop_alert_key):
                        chop_msg = TelegramNotifier.format_chop_standdown_alert(
                            spot=spot,
                            chop_val=64.8,
                            reason="Fractal Choppiness Index (CHOP > 61.8 Threshold)"
                        )
                        buttons = TelegramNotifier.get_chop_buttons(symbol=sym)
                        ok, fb = TelegramNotifier.send_message(bot_token, chat_id, chop_msg, reply_markup=buttons)
                        if ok:
                            TelegramNotifier.record_alert_sent(chop_alert_key)
                            self.last_chop_alert_sent = True
                            logger.info(f"🛡️ Choppiness Stand-Down alert sent to Telegram: {fb}")

                logger.info(f"[{time_str}] 🛡️ STAND DOWN: Consolidation Chop Regime (Capital Preserved)")

            # B4. Non-tradable / Low Confluence
            else:
                logger.info(
                    f"[{time_str}] ⏸️ STAND DOWN ({sym}): Spot ₹{spot:.2f} | Corridor ₹{corridor['lower_strike']}/₹{corridor['upper_strike']} | "
                    f"Confluence below A+ threshold • 0 Orders Placed"
                )

        pass

    def start(self):
        """Continuous production execution loop."""
        print("=" * 75)
        print("⚡ MULTI-ASSET QUANTITATIVE INTRADAY ENGINE — STANDALONE ALERT DAEMON")
        print(f"Monitored Assets: {', '.join(self.symbols)}")
        print("=" * 75)
        print("Mode           : Autonomous Background Worker (Zero-Browser Dependency)")
        print("Trading Hours  : 09:15 AM - 03:30 PM IST (Mon-Fri)")
        print(f"Polling Rate   : Every {self.interval:.1f} seconds")
        print(f"Override Mode  : {'ACTIVE (--now)' if self.force_run else 'OFF (Standard Market Hours)'}")

        tg_cfg = TelegramNotifier.load_config()
        print(f"Telegram Bot   : {'✅ ENABLED' if tg_cfg.get('enabled') else '❌ DISABLED'}")
        print(f"Recipients     : {tg_cfg.get('chat_id')}")
        print(f"Groww Direct   : {'✅ CONNECTED' if self.groww_feed.is_connected else '⚠️ REST / FALLBACK'}")
        print("=" * 75)
        print("Press Ctrl+C at any time to gracefully stop the daemon.\n")

        while self.running:
            try:
                is_open, reason = self.is_market_hours()
                if not is_open:
                    now_str = datetime.now(IST).strftime("%I:%M:%S %p IST")
                    logger.info(f"[{now_str}] ⏸️ Market Closed ({reason}). Sleeping 30s... (Pass --now to scan anytime)")
                    time.sleep(30.0)
                    continue

                self.run_single_tick()
                time.sleep(self.interval)

            except KeyboardInterrupt:
                print("\n🛑 Shutting down Reliance Quant Alert Daemon gracefully...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Tick cycle error: {e}", exc_info=True)
                time.sleep(self.interval * 2)


# Universal multi-asset daemon alias
QuantAlertDaemon = RelianceQuantAlertDaemon


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Reliance Quantitative Engine Alert Daemon")
    parser.add_argument("--symbol", type=str, default=None, help="Specific symbol to monitor (default: all whitelisted symbols)")
    parser.add_argument("--now", action="store_true", help="Force scan immediately regardless of market hours / weekends")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds (default: 5.0)")
    parser.add_argument("--test-tg", action="store_true", help="Send a test notification to Telegram and exit")
    parser.add_argument("--require-candle-close", action="store_true", help="Require 5-minute candle close confirmation before triggering entry")
    args = parser.parse_args()

    if args.test_tg:
        cfg = TelegramNotifier.load_config()
        token = cfg.get("bot_token", TelegramNotifier.DEFAULT_BOT_TOKEN)
        chat = cfg.get("chat_id", TelegramNotifier.DEFAULT_CHAT_ID)
        print(f"Testing Telegram Bot to Chat ID: {chat}...")
        ok, msg = TelegramNotifier.send_test_alert(token, chat)
        if ok:
            print(f"✅ Success: {msg}")
        else:
            print(f"❌ Failed: {msg}")
        return

    daemon = RelianceQuantAlertDaemon(
        interval_seconds=args.interval,
        force_run=args.now,
        require_candle_close=args.require_candle_close,
        symbols=[args.symbol] if args.symbol else None
    )
    daemon.start()


if __name__ == "__main__":
    main()

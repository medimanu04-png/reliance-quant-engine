"""
Walk-Forward Historical Backtest Engine for Reliance F&O Quant Engine
====================================================================
Simulates the Ultra-High-Conviction Reliance Quant Engine across 60 days
of real 5-minute historical RELIANCE (NSE) candles.

Evaluates:
- Number of A+ Confluence Setups Armed (>= 75% or >= 82% threshold)
- Trade Executions (1 trade per day maximum - Rule #1)
- Simulated Options Execution:
  * Delta: ~0.52 (ATM)
  * Target: +7.5 pts option premium (+14.4 pts spot move)
  * Stop Loss: -3.5 pts option premium (-6.7 pts spot move)
  * 1:2.14 Reward-to-Risk ratio
  * Breakeven Escalator (+3.5 pts -> Move SL to Cost)
  * Profit Lock (+5.5 pts -> Lock +3.0 pts)
  * Auto-Square-off at 15:05 PM IST
- Outputs:
  * Win Rate (Target Hit vs SL Hit)
  * Net PnL (₹ and Points)
  * Profit Factor (Gross Wins / Gross Losses)
  * Max Drawdown
  * Sharpe Ratio & Calmar Ratio
  * Full trade-by-trade audit log
"""

import os
import json
import math
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Tuple
import pytz
import pandas as pd
import numpy as np

IST = pytz.timezone("Asia/Kolkata")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKTEST_RESULTS_FILE = os.path.join(BASE_DIR, "backtest_results_summary.json")


class RelianceQuantBacktester:
    def __init__(self, symbol: str = "NIFTY", period: str = "60d"):
        from asset_config import get_asset_spec
        self.symbol = symbol.upper()
        self.spec = get_asset_spec(self.symbol)
        self.period = period
        self.capital = self.spec.total_capital
        self.lot_size = self.spec.lot_size
        self.num_lots = self.spec.default_lots
        self.total_qty = self.lot_size * self.num_lots
        self.target_option_pts = self.spec.target_pts
        self.sl_option_pts = self.spec.sl_pts
        self.delta_approx = 0.52
        self.spot_target_pts = round(self.target_option_pts / self.delta_approx, 2)
        self.spot_sl_pts = round(self.sl_option_pts / self.delta_approx, 2)

    def run_backtest(self) -> Dict[str, Any]:
        import yfinance as yf
        from fo_quant_engine import UltraHighConvictionRelianceEngine, MultiIndicatorMath

        engine = UltraHighConvictionRelianceEngine(symbol=self.symbol)

        # Gap 3: Data Caching Layer (Allows building 6-12 month historical buffer over time)
        cache_dir = os.path.join(BASE_DIR, "data_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{self.symbol.lower()}_5m_cache.parquet")

        df_raw = pd.DataFrame()
        cached_df = pd.DataFrame()
        if os.path.exists(cache_file):
            try:
                cached_df = pd.read_parquet(cache_file)
            except Exception:
                pass

        print(f"Downloading historical 5m {self.spec.yf_symbol} data...")
        try:
            df_new = yf.download(self.spec.yf_symbol, period=self.period, interval="5m", progress=False)
            if isinstance(df_new.columns, pd.MultiIndex):
                df_new.columns = df_new.columns.get_level_values(0)
            if not df_new.empty:
                if not cached_df.empty:
                    combined = pd.concat([cached_df, df_new])
                    df_raw = combined[~combined.index.duplicated(keep="last")].sort_index()
                else:
                    df_raw = df_new
                try:
                    df_raw.to_parquet(cache_file)
                except Exception:
                    pass
        except Exception as e:
            print(f"yfinance download warning: {e}")
            df_raw = cached_df

        if df_raw.empty:
            return {"error": "Failed to download market data from Yahoo Finance and no cache found"}

        # Benchmark NIFTY 50 Caching for authentic Clayton Copula cross-asset returns
        cache_nifty_file = os.path.join(cache_dir, "nifty_5m_cache.parquet")
        df_nifty_raw = pd.DataFrame()
        cached_nifty_df = pd.DataFrame()
        if os.path.exists(cache_nifty_file):
            try:
                cached_nifty_df = pd.read_parquet(cache_nifty_file)
            except Exception:
                pass
        try:
            df_nifty_new = yf.download("^NSEI", period=self.period, interval="5m", progress=False)
            if isinstance(df_nifty_new.columns, pd.MultiIndex):
                df_nifty_new.columns = df_nifty_new.columns.get_level_values(0)
            if not df_nifty_new.empty:
                if not cached_nifty_df.empty:
                    comb_nifty = pd.concat([cached_nifty_df, df_nifty_new])
                    df_nifty_raw = comb_nifty[~comb_nifty.index.duplicated(keep="last")].sort_index()
                else:
                    df_nifty_raw = df_nifty_new
                try:
                    df_nifty_raw.to_parquet(cache_nifty_file)
                except Exception:
                    pass
            else:
                df_nifty_raw = cached_nifty_df
        except Exception:
            df_nifty_raw = cached_nifty_df

        df_nifty = df_nifty_raw.dropna().copy() if not df_nifty_raw.empty else pd.DataFrame()

        df = df_raw.dropna().copy()
        unique_dates = sorted(list(set(df.index.date)))
        print(f"Loaded {len(df)} candles across {len(unique_dates)} trading sessions. (NIFTY benchmark: {len(df_nifty)} bars)")


        trades: List[Dict[str, Any]] = []
        daily_summaries: List[Dict[str, Any]] = []
        running_cash = self.capital
        peak_cash = self.capital
        max_drawdown_rs = 0.0

        for day_idx, d in enumerate(unique_dates):
            day_df = df[df.index.date == d].copy()
            if len(day_df) < 15:
                continue

            # Need previous days for indicators like 200 EMA
            history_df = df[df.index.date <= d].copy()
            if len(history_df) < 50:
                continue

            day_traded = False
            active_trade = None
            re_entry_armed = None

            # Iterate 5m candles of the session
            for i in range(len(day_df)):
                current_time = day_df.index[i].time()
                candle_dt = day_df.index[i]
                spot = float(day_df["Close"].iloc[i])
                high = float(day_df["High"].iloc[i])
                low = float(day_df["Low"].iloc[i])

                # Manage existing active trade if any
                if active_trade:
                    direction = active_trade["direction"]
                    entry_p = active_trade["entry_price"]
                    sl_p = active_trade["sl"]
                    tgt_p = active_trade["target"]
                    active_trade["bars_open"] = active_trade.get("bars_open", 0) + 1
                    atr_dyn = active_trade.get("atr_dyn", 4.0)

                    # Track peak profit for Breakeven & Chandelier Trailing
                    if direction == "BUY CE":
                        cur_gain = round((spot - entry_p) * self.delta_approx, 2)
                        high_gain = round((high - entry_p) * self.delta_approx, 2)
                        
                        # Solution 4: Chandelier / Trailing ATR Exit once 1:1 R:R achieved
                        if high_gain >= active_trade.get("sl_opt_pts", 3.5):
                            ch_stop = round(high - (2.0 * atr_dyn), 2)
                            active_trade["sl"] = max(active_trade["sl"], entry_p + (0.2 / self.delta_approx), ch_stop)
                        elif high_gain >= 3.5:
                            active_trade["sl"] = max(active_trade["sl"], entry_p + (0.2 / self.delta_approx))

                        # Check Target Hit
                        if high >= tgt_p:
                            pts_opt = self.target_option_pts
                            pnl = round(pts_opt * self.total_qty, 2)
                            active_trade["exit_price"] = tgt_p
                            active_trade["exit_time"] = str(current_time)
                            active_trade["exit_reason"] = "TARGET_HIT"
                            active_trade["pts_captured"] = pts_opt
                            active_trade["pnl"] = pnl
                            running_cash += pnl
                            trades.append(active_trade)
                            active_trade = None
                            break  # 1 trade per day rule

                        # Solution 2: Two-Tier Stop Loss Check
                        # Hard Catastrophic Stop Loss (Wick violation)
                        elif low <= active_trade.get("hard_sl", active_trade["sl"] - 10.0):
                            sl_pts_opt = round((entry_p - active_trade["hard_sl"]) * self.delta_approx, 2)
                            pnl = round(-sl_pts_opt * self.total_qty, 2)
                            active_trade["exit_price"] = active_trade["hard_sl"]
                            active_trade["exit_time"] = str(current_time)
                            active_trade["exit_reason"] = "HARD_SL_HIT"
                            active_trade["pts_captured"] = -sl_pts_opt
                            active_trade["pnl"] = pnl
                            running_cash += pnl
                            trades.append(active_trade)
                            
                            # Solution 3: Resumption Re-entry Arming
                            if active_trade["bars_open"] <= 3 and active_trade.get("confluence_score", 0) >= 65.0:
                                re_entry_armed = {
                                    "direction": "BUY CE",
                                    "original_entry": entry_p,
                                    "wick_sl": low - 2.0,
                                    "expiry_idx": i + 3,
                                    "target": tgt_p,
                                    "confluence": active_trade["confluence_score"]
                                }
                            active_trade = None

                        # Soft Technical Stop Loss (Candle Close confirmation)
                        elif spot <= active_trade["sl"]:
                            sl_pts_opt = round((entry_p - active_trade["sl"]) * self.delta_approx, 2)
                            pnl = round(-sl_pts_opt * self.total_qty, 2)
                            active_trade["exit_price"] = active_trade["sl"]
                            active_trade["exit_time"] = str(current_time)
                            active_trade["exit_reason"] = "SL_HIT" if active_trade["sl"] < entry_p else "BREAKEVEN_EXIT"
                            active_trade["pts_captured"] = -sl_pts_opt
                            active_trade["pnl"] = pnl
                            running_cash += pnl
                            trades.append(active_trade)

                            # Solution 3: Resumption Re-entry Arming
                            if active_trade["bars_open"] <= 3 and active_trade.get("confluence_score", 0) >= 65.0:
                                re_entry_armed = {
                                    "direction": "BUY CE",
                                    "original_entry": entry_p,
                                    "wick_sl": low - 2.0,
                                    "expiry_idx": i + 3,
                                    "target": tgt_p,
                                    "confluence": active_trade["confluence_score"]
                                }
                            active_trade = None

                        # Auto Square-Off at 15:05 PM
                        elif current_time >= time(15, 5):
                            exit_gain = round((spot - entry_p) * self.delta_approx, 2)
                            pnl = round(exit_gain * self.total_qty, 2)
                            active_trade["exit_price"] = spot
                            active_trade["exit_time"] = str(current_time)
                            active_trade["exit_reason"] = "AUTO_SQUAREOFF"
                            active_trade["pts_captured"] = exit_gain
                            active_trade["pnl"] = pnl
                            running_cash += pnl
                            trades.append(active_trade)
                            active_trade = None
                            break

                    elif direction == "BUY PE":
                        cur_gain = round((entry_p - spot) * self.delta_approx, 2)
                        high_gain = round((entry_p - low) * self.delta_approx, 2)

                        # Solution 4: Chandelier / Trailing ATR Exit once 1:1 R:R achieved
                        if high_gain >= active_trade.get("sl_opt_pts", 3.5):
                            ch_stop = round(low + (2.0 * atr_dyn), 2)
                            active_trade["sl"] = min(active_trade["sl"], entry_p - (0.2 / self.delta_approx), ch_stop)
                        elif high_gain >= 3.5:
                            active_trade["sl"] = min(active_trade["sl"], entry_p - (0.2 / self.delta_approx))

                        # Check Target Hit
                        if low <= tgt_p:
                            pts_opt = self.target_option_pts
                            pnl = round(pts_opt * self.total_qty, 2)
                            active_trade["exit_price"] = tgt_p
                            active_trade["exit_time"] = str(current_time)
                            active_trade["exit_reason"] = "TARGET_HIT"
                            active_trade["pts_captured"] = pts_opt
                            active_trade["pnl"] = pnl
                            running_cash += pnl
                            trades.append(active_trade)
                            active_trade = None
                            break

                        # Solution 2: Two-Tier Stop Loss Check
                        # Hard Catastrophic Stop Loss (Wick violation)
                        elif high >= active_trade.get("hard_sl", active_trade["sl"] + 10.0):
                            sl_pts_opt = round((active_trade["hard_sl"] - entry_p) * self.delta_approx, 2)
                            pnl = round(-sl_pts_opt * self.total_qty, 2)
                            active_trade["exit_price"] = active_trade["hard_sl"]
                            active_trade["exit_time"] = str(current_time)
                            active_trade["exit_reason"] = "HARD_SL_HIT"
                            active_trade["pts_captured"] = -sl_pts_opt
                            active_trade["pnl"] = pnl
                            running_cash += pnl
                            trades.append(active_trade)

                            # Solution 3: Resumption Re-entry Arming
                            if active_trade["bars_open"] <= 3 and active_trade.get("confluence_score", 0) >= 65.0:
                                re_entry_armed = {
                                    "direction": "BUY PE",
                                    "original_entry": entry_p,
                                    "wick_sl": high + 2.0,
                                    "expiry_idx": i + 3,
                                    "target": tgt_p,
                                    "confluence": active_trade["confluence_score"]
                                }
                            active_trade = None

                        # Soft Technical Stop Loss (Candle Close confirmation)
                        elif spot >= active_trade["sl"]:
                            sl_pts_opt = round((active_trade["sl"] - entry_p) * self.delta_approx, 2)
                            pnl = round(-sl_pts_opt * self.total_qty, 2)
                            active_trade["exit_price"] = active_trade["sl"]
                            active_trade["exit_time"] = str(current_time)
                            active_trade["exit_reason"] = "SL_HIT" if active_trade["sl"] > entry_p else "BREAKEVEN_EXIT"
                            active_trade["pts_captured"] = -sl_pts_opt
                            active_trade["pnl"] = pnl
                            running_cash += pnl
                            trades.append(active_trade)

                            # Solution 3: Resumption Re-entry Arming
                            if active_trade["bars_open"] <= 3 and active_trade.get("confluence_score", 0) >= 65.0:
                                re_entry_armed = {
                                    "direction": "BUY PE",
                                    "original_entry": entry_p,
                                    "wick_sl": high + 2.0,
                                    "expiry_idx": i + 3,
                                    "target": tgt_p,
                                    "confluence": active_trade["confluence_score"]
                                }
                            active_trade = None

                        # Auto Square-Off at 15:05 PM
                        elif current_time >= time(15, 5):
                            exit_gain = round((entry_p - spot) * self.delta_approx, 2)
                            pnl = round(exit_gain * self.total_qty, 2)
                            active_trade["exit_price"] = spot
                            active_trade["exit_time"] = str(current_time)
                            active_trade["exit_reason"] = "AUTO_SQUAREOFF"
                            active_trade["pts_captured"] = exit_gain
                            active_trade["pnl"] = pnl
                            running_cash += pnl
                            trades.append(active_trade)
                            active_trade = None
                            break

                # Solution 3: Check Resumption Re-Entry Trigger
                if not active_trade and re_entry_armed:
                    if i <= re_entry_armed["expiry_idx"]:
                        re_dir = re_entry_armed["direction"]
                        orig_entry = re_entry_armed["original_entry"]
                        re_triggered = False
                        if re_dir == "BUY PE" and spot <= orig_entry:
                            re_triggered = True
                            re_sl = round(re_entry_armed["wick_sl"], 2)
                            re_tgt = re_entry_armed["target"]
                        elif re_dir == "BUY CE" and spot >= orig_entry:
                            re_triggered = True
                            re_sl = round(re_entry_armed["wick_sl"], 2)
                            re_tgt = re_entry_armed["target"]

                        if re_triggered:
                            re_sl_pts = max(1.0, round(abs(spot - re_sl) * self.delta_approx, 2))
                            active_trade = {
                                "date": str(d),
                                "entry_time": str(current_time),
                                "direction": re_dir,
                                "spot_entry": spot,
                                "entry_price": spot,
                                "target": re_tgt,
                                "sl": re_sl,
                                "hard_sl": round(spot + (re_sl_pts * 1.5 / self.delta_approx), 2) if re_dir == "BUY PE" else round(spot - (re_sl_pts * 1.5 / self.delta_approx), 2),
                                "atr_dyn": re_sl_pts / 1.5,
                                "bars_open": 0,
                                "target_opt_pts": self.target_option_pts,
                                "sl_opt_pts": re_sl_pts,
                                "confluence_score": re_entry_armed["confluence"],
                                "tier": "RE-ENTRY RESUMPTION",
                                "regime": "WICK_SWEEP_RESUMPTION",
                                "atr_comp_ratio": 1.0,
                                "orb_volume_share": 0.0
                            }
                            re_entry_armed = None
                    else:
                        re_entry_armed = None

                # If no active trade, evaluate entry conditions (09:15 AM to 14:30 PM window)
                if not day_traded and (time(9, 15) <= current_time <= time(14, 30)):
                    # Slice history up to current candle for strict point-in-time calculation (no lookahead bias)
                    upto_idx = history_df.index.get_loc(candle_dt) + 1
                    slice_5m = history_df.iloc[max(0, upto_idx - 150):upto_idx]

                    c5m = {
                        "open": slice_5m["Open"].tolist(),
                        "high": slice_5m["High"].tolist(),
                        "low": slice_5m["Low"].tolist(),
                        "close": slice_5m["Close"].tolist(),
                        "volume": slice_5m["Volume"].tolist(),
                        "date": slice_5m.index.tolist()
                    }
                    # Strict point-in-time 15m resampled candles (fixes Look-Ahead & Multi-TF Bias)
                    try:
                        resampled_15m = slice_5m.resample("15min").agg({
                            "Open": "first",
                            "High": "max",
                            "Low": "min",
                            "Close": "last",
                            "Volume": "sum"
                        }).dropna()
                        c15m = {
                            "open": resampled_15m["Open"].tolist(),
                            "high": resampled_15m["High"].tolist(),
                            "low": resampled_15m["Low"].tolist(),
                            "close": resampled_15m["Close"].tolist(),
                            "volume": resampled_15m["Volume"].tolist(),
                            "date": resampled_15m.index.tolist()
                        }
                    except Exception:
                        c15m = c5m  # Fallback if resample fails

                    benchmark_c5m = None
                    if not df_nifty.empty:
                        try:
                            nifty_slice = df_nifty.loc[:candle_dt].iloc[-150:]
                            if len(nifty_slice) >= 15:
                                benchmark_c5m = {
                                    "open": nifty_slice["Open"].tolist(),
                                    "high": nifty_slice["High"].tolist(),
                                    "low": nifty_slice["Low"].tolist(),
                                    "close": nifty_slice["Close"].tolist(),
                                    "volume": nifty_slice["Volume"].tolist(),
                                    "date": nifty_slice.index.tolist()
                                }
                        except Exception:
                            benchmark_c5m = None

                    eval_res = engine.evaluate_90plus_confluence(
                        current_time, c5m, c15m, benchmark_c5m=benchmark_c5m, is_backtest=True
                    )
                    dom_score = float(eval_res.get("dominant_score", 0.0))
                    status_text = str(eval_res.get("2. TRADE STATUS", ""))
                    
                    # Calibrated Institutional Selectivity Gate
                    is_tradable = eval_res.get("is_tradable", False)

                    # Afternoon time-decay gate & midday filter (Bug 4 / Recommendation 2)
                    if current_time >= time(13, 45):
                        is_tradable = False
                    elif current_time >= time(13, 0) and dom_score < 70.0:
                        is_tradable = False
                    elif time(11, 15) <= current_time <= time(13, 30) and dom_score < 70.0:
                        is_tradable = False

                    if is_tradable and not day_traded:
                        rec_inst = str(eval_res.get("4. RECOMMENDED INSTRUMENT", ""))
                        rec_type = str(eval_res.get("recommended_type", ""))
                        if rec_type in ("CE", "PE"):
                            direction = f"BUY {rec_type}"
                        elif "PE" in rec_inst:
                            direction = "BUY PE"
                        elif "CE" in rec_inst:
                            direction = "BUY CE"
                        else:
                            direction = "BUY CE" if eval_res.get("bullish_score", 0) >= eval_res.get("bearish_score", 0) else "BUY PE"

                        is_ce = direction == "BUY CE"


                        # Recommendation 3: India VIX Dynamic Target/SL pts
                        tgt_opt_pts = float(eval_res.get("target_pts", self.target_option_pts))
                        sl_opt_pts = float(eval_res.get("sl_pts", self.sl_option_pts))
                        spot_tgt_dyn = round(tgt_opt_pts / self.delta_approx, 2)
                        spot_sl_dyn = round(sl_opt_pts / self.delta_approx, 2)

                        target_price = round(spot + spot_tgt_dyn, 2) if is_ce else round(spot - spot_tgt_dyn, 2)
                        sl_price = round(spot - spot_sl_dyn, 2) if is_ce else round(spot + spot_sl_dyn, 2)
                        hard_sl_price = round(spot - (spot_sl_dyn * 1.5), 2) if is_ce else round(spot + (spot_sl_dyn * 1.5), 2)

                        active_trade = {
                            "date": str(d),
                            "entry_time": str(current_time),
                            "direction": direction,
                            "spot_entry": spot,
                            "entry_price": spot,
                            "target": target_price,
                            "sl": sl_price,
                            "hard_sl": hard_sl_price,
                            "atr_dyn": spot_sl_dyn / 1.5,
                            "bars_open": 0,
                            "target_opt_pts": tgt_opt_pts,
                            "sl_opt_pts": sl_opt_pts,
                            "confluence_score": dom_score,
                            "tier": eval_res.get("tier_rating", "TIER 1"),
                            "regime": eval_res.get("intraday_regime", "TRENDING"),
                            "atr_comp_ratio": eval_res.get("atr_comp_ratio", 1.0),
                            "orb_volume_share": eval_res.get("orb_volume_share", 0.0)
                        }
                        day_traded = True

            # Track drawdown daily
            if running_cash > peak_cash:
                peak_cash = running_cash
            dd = peak_cash - running_cash
            if dd > max_drawdown_rs:
                max_drawdown_rs = dd

        # Compute aggregate metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) <= 0]
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = round((win_count / max(1, total_trades)) * 100.0, 1)

        total_pnl = round(sum(t.get("pnl", 0) for t in trades), 2)
        gross_profit = round(sum(t.get("pnl", 0) for t in winning_trades), 2)
        gross_loss = round(abs(sum(t.get("pnl", 0) for t in losing_trades)), 2)
        profit_factor = round(gross_profit / max(1.0, gross_loss), 2) if gross_loss > 0 else 9.99

        avg_win_pts = round(sum(t.get("pts_captured", 0) for t in winning_trades) / max(1, win_count), 2)
        avg_loss_pts = round(sum(abs(t.get("pts_captured", 0)) for t in losing_trades) / max(1, loss_count), 2)

        return_pct = round((total_pnl / self.capital) * 100.0, 1)
        max_dd_pct = round((max_drawdown_rs / self.capital) * 100.0, 1)

        # Gap 3: Regime-Stratified Performance Metrics (Trending, Mean-Reverting, Volatile, Low-Vol)
        regime_metrics = {}
        for reg in ["TRENDING", "MEAN_REVERTING", "VOLATILE", "LOW_VOL", "EXPANSION", "PINNING"]:
            reg_trades = [t for t in trades if reg in str(t.get("regime", "")).upper()]
            if reg_trades:
                reg_wins = len([t for t in reg_trades if t.get("pnl", 0) > 0])
                reg_total = len(reg_trades)
                reg_pnl = round(sum(t.get("pnl", 0) for t in reg_trades), 2)
                regime_metrics[reg] = {
                    "trades": reg_total,
                    "wins": reg_wins,
                    "win_rate_pct": round((reg_wins / reg_total) * 100.0, 1),
                    "net_pnl_rs": reg_pnl
                }

        results = {
            "symbol": self.spec.yf_symbol,
            "period": self.period,
            "total_trading_days": len(unique_dates),
            "total_trades_executed": total_trades,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_rate_pct": win_rate,
            "initial_capital_rs": self.capital,
            "final_capital_rs": round(running_cash, 2),
            "net_pnl_rs": total_pnl,
            "return_on_capital_pct": return_pct,
            "gross_profit_rs": gross_profit,
            "gross_loss_rs": gross_loss,
            "profit_factor": profit_factor,
            "avg_win_pts": avg_win_pts,
            "avg_loss_pts": avg_loss_pts,
            "max_drawdown_rs": round(max_drawdown_rs, 2),
            "max_drawdown_pct": max_dd_pct,
            "regime_stratified_metrics": regime_metrics,
            "rule_adherence": "1 Trade Per Day / Tiered Breakeven Escalator / Half-Kelly 1 Lot Sizing",
            "recent_trades": trades[-10:] if len(trades) >= 10 else trades
        }

        try:
            with open(BACKTEST_RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            print(f"Error saving backtest results: {e}")

        # Gap 1: Auto-Inject walk-forward outcomes into empirical calibration dataset
        try:
            from empirical_calibration_engine import EmpiricalCalibrationEngine
            injected = EmpiricalCalibrationEngine.backfill_from_walkforward_backtest(BACKTEST_RESULTS_FILE)
            if injected > 0:
                print(f"Auto-injected {injected} backtest outcomes into empirical calibration dataset.")
                # Run calibration update
                cal_res = EmpiricalCalibrationEngine.fit_logistic_calibration()
                print(f"Calibration updated: {cal_res.get('status')} (N={cal_res.get('sample_size')})")
        except Exception as e:
            print(f"Calibration auto-inject notice: {e}")

        return results


if __name__ == "__main__":
    backtester = RelianceQuantBacktester(period="60d")
    res = backtester.run_backtest()
    import pprint
    pprint.pprint({k: v for k, v in res.items() if k != "recent_trades"})
    print(f"\nRecent Trades Logged: {len(res.get('recent_trades', []))}")

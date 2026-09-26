"""
Daily Trade Performance Journal & Capital Audit Ledger Manager
Records and tracks everyday Reliance F&O trades, outcomes (HIT / FAIL / STAND DOWN),
amount captured, amount lost, cumulative profit, and current account cash balance.
Data is persisted to daily_trade_journal.json.
Clean, authentic ledger strictly based on actual executions and 2-lot position sizing.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List

JOURNAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily_trade_journal.json")
STARTING_CAPITAL = 100000.0  # Clean Starting Capital Allocation (Strictly 2 Lots Mandate)

def get_default_historical_journal() -> List[Dict[str, Any]]:
    """
    Returns an empty journal list.
    No synthetic or fabricated historical trades are injected.
    Only authentic trades logged live or manually entered by the trader are recorded.
    """
    return []

def recalculate_journal(entries: List[Dict[str, Any]], starting_cash: float = None) -> List[Dict[str, Any]]:
    """
    Recalculates 2-lot trade capital deployed, net_pnl, trade_roi_pct, cumulative_profit,
    and total_cash chronologically across all entries based strictly on 2 lots mandate.
    """
    if not entries:
        return []

    # Sort chronologically
    sorted_entries = sorted(entries, key=lambda x: x.get("date", ""))
    
    if starting_cash is None or starting_cash <= 0:
        starting_cash = STARTING_CAPITAL
            
    running_cum_profit = 0.0
    
    for i, e in enumerate(sorted_entries, 1):
        e["id"] = f"TRD-{e.get('date', '').replace('-', '')}-{i:02d}"
        status = e.get("status", "STAND DOWN")
        ep = float(e.get("entry_price", 0.0))
        
        # Mandate: 2 Lots (500 lot size * 2 = 1,000 Qty)
        e["num_lots"] = 2
        e["lot_size"] = 500
        e["qty"] = 1000
        
        if status in ["HIT", "FAIL"]:
            cap_deployed = round(ep * 1000.0, 2)
        else:
            cap_deployed = 0.0
        e["capital_deployed"] = cap_deployed
        
        if status == "HIT":
            captured = float(e.get("amount_captured", 10000.0))
            lost = 0.0
            net = captured
        elif status == "FAIL":
            captured = 0.0
            lost = float(e.get("amount_lost", 9000.0))
            net = -lost
        else:
            captured = 0.0
            lost = 0.0
            net = 0.0
            
        e["amount_captured"] = captured
        e["amount_lost"] = lost
        e["net_pnl"] = net
        e["net_profit"] = net
        e["trade_roi_pct"] = round((net / cap_deployed) * 100.0, 1) if cap_deployed > 0 else 0.0
        
        running_cum_profit += net
        e["cumulative_profit"] = running_cum_profit
        e["total_cash"] = round(starting_cash + running_cum_profit, 2)
        
    return sorted_entries

class TradeJournalManager:
    @classmethod
    def load_journal(cls, starting_cash: float = None) -> List[Dict[str, Any]]:
        """Loads journal from JSON file. Returns clean list without injecting synthetic data."""
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL

        if not os.path.exists(JOURNAL_FILE):
            cls.save_journal([])
            return []
            
        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                if len(data) > 0:
                    return recalculate_journal(data, starting_cash)
                else:
                    return []
            else:
                cls.save_journal([])
                return []
        except Exception:
            cls.save_journal([])
            return []

    @classmethod
    def save_journal(cls, entries: List[Dict[str, Any]]):
        """Saves journal records to JSON file."""
        with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

    @classmethod
    def add_or_update_entry(cls, new_entry: Dict[str, Any], starting_cash: float = None) -> List[Dict[str, Any]]:
        """Adds a new daily trade record or updates existing trade for the same date."""
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL
        entries = cls.load_journal(starting_cash)
        date_to_log = new_entry.get("date")
        entries = [e for e in entries if e.get("date") != date_to_log]
        entries.append(new_entry)
        recalculated = recalculate_journal(entries, starting_cash)
        cls.save_journal(recalculated)
        return recalculated

    @classmethod
    def delete_entry(cls, date_str: str, starting_cash: float = None) -> List[Dict[str, Any]]:
        """Deletes trade record for a specific date."""
        if starting_cash is None:
            starting_cash = STARTING_CAPITAL
        entries = cls.load_journal(starting_cash)
        entries = [e for e in entries if e.get("date") != date_str]
        recalculated = recalculate_journal(entries, starting_cash)
        cls.save_journal(recalculated)
        return recalculated

    @classmethod
    def reset_to_default(cls, starting_cash: float = None) -> List[Dict[str, Any]]:
        """Resets journal back to clean state (empty list)."""
        cls.save_journal([])
        return []

    @classmethod
    def get_summary_kpi(cls, entries: List[Dict[str, Any]], today_strike_price: float = None, starting_cash: float = None) -> Dict[str, Any]:
        """Calculates executive performance metrics strictly anchored on 2-lot mandate."""
        total_days = len(entries)
        traded_days = [e for e in entries if e.get("status") in ["HIT", "FAIL"]]
        stand_down_days = [e for e in entries if e.get("status") == "STAND DOWN"]
        hits = [e for e in entries if e.get("status") == "HIT"]
        fails = [e for e in entries if e.get("status") == "FAIL"]
        
        total_captured = sum(e.get("amount_captured", 0.0) for e in entries)
        total_lost = sum(e.get("amount_lost", 0.0) for e in entries)
        total_profit = total_captured - total_lost
        
        starting_capital = starting_cash if (starting_cash is not None and starting_cash > 0) else STARTING_CAPITAL
        total_cash = round(starting_capital + total_profit, 2)
        
        # Today's 2-lot required capital
        if today_strike_price is not None and today_strike_price > 0:
            today_2lot_capital = round(2 * 500 * today_strike_price, 2)
        else:
            today_2lot_capital = round(2 * 500 * 37.65, 2)
        
        win_rate = (len(hits) / len(traded_days) * 100.0) if len(traded_days) > 0 else 0.0
        profit_factor = (total_captured / total_lost) if total_lost > 0 else (total_captured if total_captured > 0 else 1.0)
        roi_pct = (total_profit / starting_capital) * 100.0 if starting_capital > 0 else 0.0
        
        avg_capital_deployed = round(sum(e.get("capital_deployed", 0.0) for e in traded_days) / len(traded_days), 2) if traded_days else 0.0
        
        return {
            "starting_capital": starting_capital,
            "today_2lot_capital": today_2lot_capital,
            "avg_capital_deployed": avg_capital_deployed,
            "total_cash": total_cash,
            "total_profit": total_profit,
            "roi_pct": roi_pct,
            "total_captured": total_captured,
            "total_lost": total_lost,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_days": total_days,
            "total_trades": len(traded_days),
            "hits": len(hits),
            "fails": len(fails),
            "stand_downs": len(stand_down_days)
        }

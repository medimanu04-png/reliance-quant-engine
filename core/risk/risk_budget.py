"""
core.risk.risk_budget
Institutional Risk Budgeting, Stop-Loss Governance, and Resumption Re-entry Watchdog.
Calibrated specifically to Indian F&O Index (Nifty, Sensex) and Stock contracts.
"""

from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from asset_config import get_asset_spec, resolve_symbol

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))


class RelianceRiskBudget:
    """Institutional Risk Budgeting and Capital Protection Engine."""
    total_capital: float = 100000.0
    lot_size: int = 65   # NSE standard lot size (65 NIFTY, 20 SENSEX)
    num_lots: int = 2    # Standard 2 lots mandate
    target_pts: float = 50.0  # Optimal Intraday Target
    stop_loss_pts: float = 36.0  # Optimal Stop Loss
    limit_collar_pts: float = 1.50  # Institutional Stop-Limit execution collar
    estimated_tax_per_lot: float = 45.0  # Estimated statutory charges
    daily_sl_cap_rupees: float = 6000.0  # Strict 1-and-Done Cap for 2 lots
    max_daily_sl_trades: int = 1  # 1-and-Done Rule (ceases immediately if 1 SL is hit)
    min_confluence_gate: float = 80.0  # Institutional Confluence Gate Threshold (> 80%)

    @classmethod
    def for_symbol(cls, symbol: str = "NIFTY", spot: float = 0.0) -> "RelianceRiskBudget":
        """Instantiates risk budget calibrated specifically to the active scrip from canonical AssetSpec."""
        rb = cls()
        spec = get_asset_spec(symbol)
        rb.total_capital = spec.total_capital
        rb.lot_size = spec.lot_size
        rb.num_lots = spec.default_lots
        rb.target_pts = spec.target_pts
        rb.stop_loss_pts = spec.sl_pts
        rb.limit_collar_pts = spec.limit_collar_pts
        rb.estimated_tax_per_lot = spec.estimated_tax_per_lot
        rb.daily_sl_cap_rupees = spec.daily_sl_cap_rupees
        rb.max_daily_sl_trades = 1
        rb.min_confluence_gate = getattr(spec, "min_confluence_gate", 80.0)
        return rb

    def check_daily_sl_cap(self, daily_realized_loss: float = 0.0, daily_sl_count: int = 0) -> Tuple[bool, str]:
        """
        1-and-Done Daily SL Cap Enforcement.
        If 1 trade hits SL or cumulative daily loss >= daily_sl_cap_rupees, lockout execution for the session.
        """
        if daily_sl_count >= self.max_daily_sl_trades:
            return False, f"1-AND-DONE SL LOCKOUT ACTIVE: {daily_sl_count} SL hit today. Trading suspended to eliminate tilt & preserve capital."
        if daily_realized_loss >= self.daily_sl_cap_rupees:
            return False, f"DAILY LOSS CAP EXCEEDED: Loss Rs. {daily_realized_loss:.2f} >= Cap Rs. {self.daily_sl_cap_rupees:.2f}. Execution locked."
        return True, "CAPITAL_RISK_BUDGET_AVAILABLE"

    @staticmethod
    def calculate_tiered_escalator_sl(
        current_ltp: float,
        entry_price: float,
        initial_sl: float,
        symbol: Optional[str] = None,
        target_pts: Optional[float] = None
    ) -> Tuple[float, str, str]:
        """
        Tiered Trailing Breakeven Escalator Protocol:
        Dynamically adapts thresholds for RELIANCE vs ADANI ENTERPRISES vs NIFTY via AssetSpec.
        """
        spec = get_asset_spec(symbol=symbol)
        profit_pts = round(current_ltp - entry_price, 2)

        t1_thresh = spec.escalator_t1_thresh
        t2_thresh = spec.escalator_t2_thresh
        t1_lock = spec.escalator_t1_lock
        t2_lock = spec.escalator_t2_lock

        if profit_pts >= t2_thresh:
            current_sl = round(entry_price + t2_lock, 2)
            tier_status = f"TIER_2_PROFIT_LOCK (+{t2_thresh:.1f} pts hit -> SL locked at +{t2_lock:.2f} pts)"
            action = "LOCK_PROFIT_TRAILING"
        elif profit_pts >= t1_thresh:
            current_sl = round(entry_price + t1_lock, 2)
            tier_status = f"TIER_1_BREAKEVEN (+{t1_thresh:.1f} pts hit -> SL moved to Cost +{t1_lock:.2f} pts)"
            action = "MOVE_SL_TO_COST_RISK_FREE"
        else:
            current_sl = initial_sl
            tier_status = f"TIER_0_INITIAL_PROTECTION (Profit {profit_pts:+.2f} pts < +{t1_thresh:.1f} pts trigger)"
            action = "MAINTAIN_INITIAL_STOP_LOSS"
        return current_sl, tier_status, action

    def adapt_to_volatility(self, atr_15m: float, delta: float = 0.52, india_vix: float = 14.5):
        """
        Dynamically adapts target and stop-loss points using India VIX Elasticity Multiplier.
        Reference: CBOE Implied Move Dynamics.
        """
        safe_vix = max(8.0, min(35.0, india_vix if india_vix else 14.5))
        vix_ratio = safe_vix / 14.0
        
        target_elasticity = (vix_ratio ** 0.65)
        sl_elasticity = (vix_ratio ** 0.50)
        
        nominal_tgt = self.target_pts if self.target_pts > 0 else 10.0
        nominal_sl = self.stop_loss_pts if self.stop_loss_pts > 0 else 4.5

        base_tgt = nominal_tgt * target_elasticity
        base_sl = nominal_sl * sl_elasticity
        
        if atr_15m and atr_15m > 0:
            eff_delta = max(0.35, min(0.70, delta if delta else 0.52))
            atr_move = atr_15m * eff_delta
            base_tgt = (base_tgt * 0.60) + (atr_move * 1.5 * 0.40)
            base_sl = (base_sl * 0.60) + (atr_move * 0.75 * 0.40)
            
        min_sl = round(nominal_sl * 0.55, 1)
        max_sl = round(nominal_sl * 1.45, 1)
        dynamic_sl = round(min(max_sl, max(min_sl, base_sl)), 1)

        min_tgt = round(nominal_tgt * 0.65, 1)
        max_tgt = round(nominal_tgt * 1.55, 1)
        dynamic_tgt = round(min(max_tgt, max(min_tgt, max(dynamic_sl * 2.05, base_tgt))), 1)
        
        self.stop_loss_pts = dynamic_sl
        self.target_pts = dynamic_tgt

    @property
    def total_quantity(self) -> int:
        return self.lot_size * self.num_lots

    @property
    def max_risk_rupees(self) -> float:
        return self.total_quantity * self.stop_loss_pts

    @property
    def target_reward_rupees(self) -> float:
        return self.total_quantity * self.target_pts

    @property
    def net_target_reward_rupees(self) -> float:
        return max(0.0, self.target_reward_rupees - (self.estimated_tax_per_lot * self.num_lots))

    @property
    def net_max_risk_rupees(self) -> float:
        return self.max_risk_rupees + (self.estimated_tax_per_lot * self.num_lots)


@dataclass
class ReEntryCandidate:
    symbol: str
    contract: str
    direction: str
    confluence: float
    original_entry_spot: float
    original_entry_opt: float
    wick_extreme_spot: float
    wick_extreme_opt: float
    sl_pts: float
    hard_sl_spot: float
    armed_time: datetime
    expiry_time: datetime
    is_active: bool = True


class ResumptionReEntryWatchdog:
    """
    Institutional Resumption Re-Entry Watchdog.
    Prevents missing massive intraday trend extensions after an initial wick stop-out.
    """
    _candidates: Dict[str, ReEntryCandidate] = {}

    @classmethod
    def arm_candidate(
        cls,
        symbol: str,
        contract: str,
        direction: str,
        confluence: float,
        entry_spot: float,
        entry_opt: float,
        exit_spot: float,
        exit_opt: float,
        wick_extreme_spot: float,
        trade_duration_mins: float = 5.0,
        min_confidence: float = 65.0,
        window_minutes: int = 15
    ) -> Optional[ReEntryCandidate]:
        if confluence < min_confidence or trade_duration_mins > 15.0:
            return None
        
        now = datetime.now(IST)
        expiry = now + timedelta(minutes=window_minutes)
        spec = get_asset_spec(symbol=symbol, contract=contract)
        
        is_put = "PE" in direction.upper() or "PUT" in direction.upper()
        if is_put:
            tight_sl_dist = max(spec.sl_pts * 0.5, round(abs(wick_extreme_spot - entry_spot) + spec.structural_buffer_pts, 2))
            hard_sl = entry_spot + (tight_sl_dist * 1.5)
        else:
            tight_sl_dist = max(spec.sl_pts * 0.5, round(abs(entry_spot - wick_extreme_spot) + spec.structural_buffer_pts, 2))
            hard_sl = entry_spot - (tight_sl_dist * 1.5)

        candidate = ReEntryCandidate(
            symbol=spec.symbol,
            contract=contract,
            direction=direction,
            confluence=confluence,
            original_entry_spot=entry_spot,
            original_entry_opt=entry_opt,
            wick_extreme_spot=wick_extreme_spot,
            wick_extreme_opt=exit_opt,
            sl_pts=tight_sl_dist,
            hard_sl_spot=hard_sl,
            armed_time=now,
            expiry_time=expiry,
            is_active=True
        )
        cls._candidates[spec.symbol] = candidate
        return candidate

    @classmethod
    def evaluate_re_entry(
        cls,
        symbol: str,
        current_spot: float,
        trend_aligned: bool = True
    ) -> Tuple[bool, Optional[ReEntryCandidate], str]:
        sym = resolve_symbol(symbol)
        candidate = cls._candidates.get(sym)
        if not candidate or not candidate.is_active:
            return False, None, "NO_ACTIVE_RE_ENTRY_CANDIDATE"

        now = datetime.now(IST)
        if now > candidate.expiry_time:
            candidate.is_active = False
            return False, None, "RE_ENTRY_WINDOW_EXPIRED"

        if not trend_aligned:
            return False, None, "TREND_NOT_ALIGNED"

        is_put = "PE" in candidate.direction.upper() or "PUT" in candidate.direction.upper()
        if is_put:
            if current_spot <= candidate.original_entry_spot:
                candidate.is_active = False
                return True, candidate, f"BEARISH_RESUMPTION: Spot ₹{current_spot:.2f} <= Entry ₹{candidate.original_entry_spot:.2f}. Wick Sweep Confirmed!"
        else:
            if current_spot >= candidate.original_entry_spot:
                candidate.is_active = False
                return True, candidate, f"BULLISH_RESUMPTION: Spot ₹{current_spot:.2f} >= Entry ₹{candidate.original_entry_spot:.2f}. Wick Sweep Confirmed!"

        return False, candidate, "WAITING_FOR_RESUMPTION_TRIGGER"


# Legacy Aliases
RiskBudget = RelianceRiskBudget
AssetRiskBudget = RelianceRiskBudget
FOQuantRiskBudget = RelianceRiskBudget

"""
Canonical Multi-Asset Quantitative Trading Registry
Single Source of Truth for NIFTY 50 and BSE SENSEX specifications,
lot sizes, risk boundaries, price steps, and broker endpoints.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

@dataclass(frozen=True)
class AssetSpec:
    symbol: str                    # Standard ticker symbol: "NIFTY" | "SENSEX"
    display_name: str              # User-facing desk title
    full_name: str                 # Corporate entity name
    yf_symbol: str                 # Yahoo Finance query symbol: "^NSEI" | "^BSESN"
    lot_size: int                  # F&O Market Lot Size: 65 (NIFTY) | 20 (SENSEX)
    default_lots: int              # Standard trading lot count: 2
    target_pts: float              # Quantitative profit target (points)
    target_2_pts: float            # Option 1 Multi-Tranche Runner Target 2 (points)
    sl_pts: float                  # Quantitative stop-loss (points)
    be_pts: float                  # Breakeven threshold (points to move SL to cost)
    profit_lock_trigger: float     # Points gained to activate guaranteed profit lock
    profit_lock_locked: float      # Guaranteed profit points locked in capital
    strike_step: int               # Option chain strike interval: 50 (NIFTY) | 100 (SENSEX)
    default_spot: float            # Baseline spot price: 22450.0 (NIFTY) | 72000.0 (SENSEX)
    default_strike: int            # Baseline ATM strike: 22450 (NIFTY) | 72000 (SENSEX)
    default_call_price: float      # Baseline ATM Call premium: 135.0 (NIFTY) | 420.0 (SENSEX)
    default_put_price: float       # Baseline ATM Put premium: 125.0 (NIFTY) | 390.0 (SENSEX)
    groww_company_slug: str        # Groww web slug: "nifty" | "sp-bse-sensex"
    volume_norm: int               # Average daily volume benchmark
    daily_sl_cap_rupees: float     # Maximum 1-day capital risk cap for 1 lot
    tape_quantities: Tuple[int, ...] # Order tape simulated fill sizes (lot multiples)
    beta: float = 1.00             # Benchmark beta
    limit_collar_pts: float = 1.50 # Execution limit collar points
    estimated_tax_per_lot: float = 45.0 # Estimated STT/turnover tax per lot
    parent_sector: str = "BENCHMARK INDEX" # Parent sectoral index
    total_capital: float = 100000.0 # Default allocated capital
    breakout_buffer: float = 3.0  # Intraday breakout trigger buffer (points)
    trail_runner_offset: float = 3.0 # Runner trailing offset beyond profit lock (points)
    bsm_sigma: float = 0.135       # Benchmark baseline IV for Black-Scholes fallback
    has_crude_coupling: bool = False # Flag for Brent Crude correlation weighting
    fallback_call_vol: int = 250000  # Fallback market call volume
    fallback_put_vol: int = 220000   # Fallback market put volume
    fallback_call_oi: int = 1800000  # Fallback ATM call open interest
    fallback_put_oi: int = 1600000   # Fallback ATM put open interest
    spread_threshold: float = 0.03 # Maximum tolerable bid-ask spread fraction
    max_pain_gamma_divisor: float = 50.0 # Gamma proxy divisor scaling
    jitter_range: Tuple[float, float] = (-0.30, 0.40) # Synthetic tick noise boundaries
    escalator_t1_thresh: float = 25.0 # Tier 1 Breakeven profit trigger threshold
    escalator_t2_thresh: float = 36.0 # Tier 2 Profit Lock trigger threshold
    escalator_t1_lock: float = 1.0  # Tier 1 Stop Loss lock amount
    escalator_t2_lock: float = 20.0  # Tier 2 Stop Loss lock amount
    min_confluence_gate: float = 72.0 # Institutional Directional Confluence Gate Threshold (%)
    hard_sl_multiplier: float = 2.5   # Catastrophic broker hard SL multiplier (x ATR)
    atr_multiplier_sl: float = 1.5    # Technical soft SL multiplier (x 5m ATR)
    structural_buffer_pts: float = 5.0 # Structural swing high/low buffer points
    chandelier_period: int = 10       # Chandelier Exit ATR period
    chandelier_mult: float = 2.0      # Chandelier Exit ATR multiplier
    re_entry_window_mins: int = 15    # Resumption Re-entry observation window (minutes)
    re_entry_min_confidence: float = 65.0 # Minimum setup confidence for auto-re-entry

    def calculate_dynamic_sl(
        self,
        direction: str,
        entry_spot: float,
        atr_5m: float,
        swing_extreme: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Volatility-Adjusted Structural Dynamic Stop-Loss Calculation.
        Formula: SL Distance = max(Structural Swing High/Low + 5 pts, 1.5 * ATR_14(5m))
        Returns dictionary with soft_sl_pts, soft_sl_spot, and hard_sl_spot.
        """
        atr_val = max(1.0, float(atr_5m if atr_5m and atr_5m > 0 else (self.sl_pts / self.atr_multiplier_sl)))
        vol_sl_dist = round(self.atr_multiplier_sl * atr_val, 2)
        dir_upper = str(direction).upper()
        is_put = "PE" in dir_upper or "PUT" in dir_upper or "SHORT" in dir_upper

        if is_put:
            # Bearish PUT: Stop Loss is ABOVE entry (Swing High + 5 pts)
            if swing_extreme and swing_extreme > entry_spot:
                struct_sl_dist = round((swing_extreme + self.structural_buffer_pts) - entry_spot, 2)
            else:
                struct_sl_dist = vol_sl_dist
            
            soft_sl_pts = max(struct_sl_dist, vol_sl_dist, self.sl_pts)
            soft_sl_spot = round(entry_spot + soft_sl_pts, 2)
            hard_sl_pts = max(round(soft_sl_pts * 1.5, 2), round(self.hard_sl_multiplier * atr_val, 2))
            hard_sl_spot = round(entry_spot + hard_sl_pts, 2)
        else:
            # Bullish CALL: Stop Loss is BELOW entry (Swing Low - 5 pts)
            if swing_extreme and swing_extreme < entry_spot:
                struct_sl_dist = round(entry_spot - (swing_extreme - self.structural_buffer_pts), 2)
            else:
                struct_sl_dist = vol_sl_dist
                
            soft_sl_pts = max(struct_sl_dist, vol_sl_dist, self.sl_pts)
            soft_sl_spot = round(entry_spot - soft_sl_pts, 2)
            hard_sl_pts = max(round(soft_sl_pts * 1.5, 2), round(self.hard_sl_multiplier * atr_val, 2))
            hard_sl_spot = round(entry_spot - hard_sl_pts, 2)

        return {
            "soft_sl_pts": round(soft_sl_pts, 2),
            "soft_sl_spot": soft_sl_spot,
            "hard_sl_pts": round(hard_sl_pts, 2),
            "hard_sl_spot": hard_sl_spot,
            "atr_5m": round(atr_val, 2)
        }

    def calculate_position_size(
        self,
        max_risk_rupees: float,
        sl_pts: float,
        delta: float = 0.50
    ) -> int:
        """
        Dynamic Position Sizing Adjustment.
        Scales down lots for wider ATR stops so that monetary risk (Qty * SL * Delta) <= max_risk_rupees.
        """
        if max_risk_rupees <= 0 or sl_pts <= 0 or self.lot_size <= 0:
            return self.default_lots
        eff_delta = max(0.20, min(1.0, float(delta if delta else 0.50)))
        per_lot_risk = sl_pts * self.lot_size * eff_delta
        if per_lot_risk <= 0:
            return self.default_lots
        calculated_lots = int(max_risk_rupees // per_lot_risk)
        return max(1, calculated_lots)

    def calculate_daily_sr_zones(
        self,
        spot: Optional[float] = None,
        high: Optional[float] = None,
        low: Optional[float] = None,
        prev_close: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculates 3 Dynamic Resistance Zones and 3 Dynamic Support Zones for the active trading day.
        """
        curr_spot = float(spot if spot and spot > 0 else self.default_spot)
        h = float(high if high and high > 0 else (curr_spot * 1.006))
        l = float(low if low and low > 0 else (curr_spot * 0.994))
        c = float(prev_close if prev_close and prev_close > 0 else curr_spot)
        
        # Ensure high >= low
        if h <= l:
            h = curr_spot * 1.006
            l = curr_spot * 0.994

        rng = round(h - l, 2)
        p = round((h + l + c) / 3.0, 2)
        bc = round((h + l) / 2.0, 2)
        tc = round((p - bc) + p, 2)
        cpr_top = max(tc, bc)
        cpr_bottom = min(tc, bc)
        cpr_width_pct = round(abs(tc - bc) / p * 100.0, 3) if p > 0 else 0.20

        # Primary Pivot Levels
        r1 = round(2.0 * p - l, 2)
        s1 = round(2.0 * p - h, 2)
        r2 = round(p + rng, 2)
        s2 = round(p - rng, 2)
        r3 = round(r1 + rng, 2)
        s3 = round(s1 - rng, 2)

        # Buffer width for zones (0.15% for R1/S1, 0.20% for R2/S2, 0.25% for R3/S3)
        buf_r1 = max(0.5, round(r1 * 0.0015, 2))
        buf_s1 = max(0.5, round(s1 * 0.0015, 2))
        buf_r2 = max(0.8, round(r2 * 0.0020, 2))
        buf_s2 = max(0.8, round(s2 * 0.0020, 2))
        buf_r3 = max(1.0, round(r3 * 0.0025, 2))
        buf_s3 = max(1.0, round(s3 * 0.0025, 2))

        def make_zone(name: str, level: float, buf: float, is_res: bool, role: str) -> Dict[str, Any]:
            dist_pts = round(level - curr_spot, 2)
            dist_pct = round((dist_pts / curr_spot) * 100.0, 2)
            z_low = round(level - buf, 2)
            z_high = round(level + buf, 2)
            is_testing = (z_low <= curr_spot <= z_high)
            
            if is_testing:
                status = "⚠️ TESTING ZONE"
            elif is_res:
                status = f"🔴 SUPPLY BARRIER (+{dist_pts:.1f} pts)" if dist_pts > 0 else "🟢 BREACHED ABOVE"
            else:
                status = f"🟢 DEMAND FLOOR ({dist_pts:.1f} pts)" if dist_pts < 0 else "🔴 BREACHED BELOW"

            return {
                "name": name,
                "level": level,
                "zone_low": z_low,
                "zone_high": z_high,
                "buffer": buf,
                "dist_pts": dist_pts,
                "dist_pct": dist_pct,
                "status": status,
                "is_testing": is_testing,
                "role": role
            }

        return {
            "symbol": self.symbol,
            "spot": curr_spot,
            "high": round(h, 2),
            "low": round(l, 2),
            "prev_close": round(c, 2),
            "range": rng,
            "pivot": p,
            "cpr": {
                "pivot": p,
                "bc": bc,
                "tc": tc,
                "top": cpr_top,
                "bottom": cpr_bottom,
                "width_pct": cpr_width_pct,
                "regime": "NARROW (TRENDING BREAKOUT)" if cpr_width_pct <= 0.15 else ("WIDE (RANGE CHOP)" if cpr_width_pct >= 0.28 else "NORMAL CPR")
            },
            "resistance_zones": {
                "r3": make_zone("R3", r3, buf_r3, True, "Extreme Extension / Exhaustion Reversal"),
                "r2": make_zone("R2", r2, buf_r2, True, "Major Structural Ceiling / Breakout Target"),
                "r1": make_zone("R1", r1, buf_r1, True, "Immediate Supply / Pullback Resistance")
            },
            "support_zones": {
                "s1": make_zone("S1", s1, buf_s1, False, "Immediate Demand / Pullback Floor"),
                "s2": make_zone("S2", s2, buf_s2, False, "Major Value Area Low / Structural Floor"),
                "s3": make_zone("S3", s3, buf_s3, False, "Capitulation Floor / Extreme Demand")
            }
        }


ASSET_SPECS: Dict[str, AssetSpec] = {
    "NIFTY": AssetSpec(
        symbol="NIFTY",
        display_name="NIFTY 50 QUANT DESK",
        full_name="Nifty 50 Index (NSE)",
        yf_symbol="^NSEI",
        lot_size=65,
        default_lots=2,
        target_pts=50.0,
        target_2_pts=110.0,
        sl_pts=36.0,
        be_pts=25.0,
        profit_lock_trigger=36.0,
        profit_lock_locked=20.0,
        min_confluence_gate=72.0,
        strike_step=50,
        default_spot=22450.0,
        default_strike=22450,
        default_call_price=135.0,
        default_put_price=125.0,
        groww_company_slug="nifty",
        volume_norm=15000000,
        daily_sl_cap_rupees=6000.0,
        tape_quantities=(65, 130, 195, 260),
        beta=1.00,
        limit_collar_pts=1.50,
        estimated_tax_per_lot=45.0,
        parent_sector="BENCHMARK INDEX",
        total_capital=100000.0,
        breakout_buffer=3.0,
        trail_runner_offset=3.0,
        bsm_sigma=0.135,
        has_crude_coupling=False,
        fallback_call_vol=250000,
        fallback_put_vol=220000,
        fallback_call_oi=1800000,
        fallback_put_oi=1600000,
        spread_threshold=0.03,
        max_pain_gamma_divisor=50.0,
        jitter_range=(-0.30, 0.40),
        escalator_t1_thresh=25.0,
        escalator_t2_thresh=36.0,
        escalator_t1_lock=1.0,
        escalator_t2_lock=20.0,
        hard_sl_multiplier=2.5,
        atr_multiplier_sl=1.5,
        structural_buffer_pts=5.0
    ),
    "SENSEX": AssetSpec(
        symbol="SENSEX",
        display_name="BSE SENSEX QUANT DESK",
        full_name="BSE SENSEX 30 Index",
        yf_symbol="^BSESN",
        lot_size=20,
        default_lots=2,
        target_pts=120.0,
        target_2_pts=280.0,
        sl_pts=60.0,
        be_pts=60.0,
        profit_lock_trigger=95.0,
        profit_lock_locked=50.0,
        min_confluence_gate=72.0,
        strike_step=100,
        default_spot=72000.0,
        default_strike=72000,
        default_call_price=420.0,
        default_put_price=390.0,
        groww_company_slug="sp-bse-sensex",
        volume_norm=8000000,
        daily_sl_cap_rupees=3000.0,
        tape_quantities=(20, 40, 60, 80),
        beta=1.00,
        limit_collar_pts=5.0,
        estimated_tax_per_lot=55.0,
        parent_sector="BENCHMARK INDEX",
        total_capital=120000.0,
        breakout_buffer=10.0,
        trail_runner_offset=10.0,
        bsm_sigma=0.132,
        has_crude_coupling=False,
        fallback_call_vol=120000,
        fallback_put_vol=110000,
        fallback_call_oi=950000,
        fallback_put_oi=880000,
        spread_threshold=0.03,
        max_pain_gamma_divisor=100.0,
        jitter_range=(-0.80, 1.20),
        escalator_t1_thresh=60.0,
        escalator_t2_thresh=95.0,
        escalator_t1_lock=2.0,
        escalator_t2_lock=50.0
    )
}

def resolve_symbol(symbol: Optional[str] = None, contract: Optional[str] = None) -> str:
    """Canonical resolver mapping any variant name to standard 'NIFTY' or 'SENSEX'."""
    text = f"{symbol or ''} {contract or ''}".upper()
    if "SENSEX" in text or "BSESN" in text:
        return "SENSEX"
    return "NIFTY"

def get_asset_spec(symbol: Optional[str] = None, contract: Optional[str] = None) -> AssetSpec:
    """Returns the immutable AssetSpec configuration for the given symbol or contract."""
    sym = resolve_symbol(symbol, contract)
    return ASSET_SPECS[sym]

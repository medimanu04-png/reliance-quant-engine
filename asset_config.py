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

    def get_vix_scaled_targets(self, india_vix: Optional[float] = None) -> Dict[str, Any]:
        """
        Dynamic India VIX Volatility Scalar for Target & Stop-Loss Boundaries.
        Baseline Indian market volatility benchmark: VIX = 13.5.
        Scalar = sqrt(clamp(VIX, 9.0, 28.0) / 13.5), bounded in [0.80, 1.35].
        - High Volatility (VIX > 16.5): Expands Target & SL distances (+15% to +35%)
          to prevent premature stopouts during wide volatility swings.
        - Low Volatility (VIX < 11.5): Tightens Target & SL distances (-10% to -20%)
          to avoid unrealistic targets during compressed regimes.
        """
        import math
        vix = float(india_vix) if india_vix and india_vix > 0 else 13.5
        vix_clamped = max(9.0, min(28.0, vix))
        vix_scalar = max(0.80, min(1.35, math.sqrt(vix_clamped / 13.5)))

        return {
            "vix": round(vix, 2),
            "vix_scalar": round(vix_scalar, 3),
            "regime": "HIGH_VOLATILITY" if vix >= 16.5 else ("LOW_VOLATILITY" if vix <= 11.5 else "NORMAL_VOLATILITY"),
            "regime_badge": "⚡ HIGH VOLATILITY" if vix >= 16.5 else ("🧊 LOW VOLATILITY" if vix <= 11.5 else "⚖️ NORMAL VOLATILITY"),
            "target_pts": round(self.target_pts * vix_scalar, 1),
            "target_2_pts": round(self.target_2_pts * vix_scalar, 1),
            "sl_pts": round(self.sl_pts * vix_scalar, 1),
            "be_pts": round(self.be_pts * vix_scalar, 1),
            "breakout_buffer": round(self.breakout_buffer * vix_scalar, 2),
            "profit_lock_trigger": round(self.profit_lock_trigger * vix_scalar, 1),
            "profit_lock_locked": round(self.profit_lock_locked * vix_scalar, 1)
        }

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
        default_lots=4,
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
        daily_sl_cap_rupees=12000.0,
        tape_quantities=(65, 130, 195, 260),
        beta=1.00,
        limit_collar_pts=1.50,
        estimated_tax_per_lot=45.0,
        parent_sector="BENCHMARK INDEX",
        total_capital=150000.0,
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
        default_lots=6,
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
        daily_sl_cap_rupees=9000.0,
        tape_quantities=(20, 40, 60, 80, 100, 120),
        beta=1.00,
        limit_collar_pts=5.0,
        estimated_tax_per_lot=55.0,
        parent_sector="BENCHMARK INDEX",
        total_capital=150000.0,
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


def format_contract_code(expiry_date_str: Optional[str] = None, ref_dt: Optional[Any] = None) -> str:
    """
    Parses any valid expiry date string or falls back to ref_dt/current IST time,
    returning a standardized 5-character contract month code (e.g. '26OCT', '26NOV').
    Eliminates brittle hardcoded month codes across the application.
    """
    from datetime import datetime
    try:
        import pytz
        IST = pytz.timezone("Asia/Kolkata")
    except Exception:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))

    if expiry_date_str:
        cleaned = str(expiry_date_str).strip().split()[0].replace("/", "-").replace(" ", "-")
        for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d%b%Y", "%b-%d-%Y", "%d%B%Y"):
            for val in (cleaned, cleaned.title(), cleaned.upper()):
                try:
                    dt = datetime.strptime(val, fmt)
                    return dt.strftime("%y%b").upper()
                except Exception:
                    pass
    if ref_dt is not None:
        try:
            return ref_dt.strftime("%y%b").upper()
        except Exception:
            pass
    return datetime.now(IST).strftime("%y%b").upper()


def build_contract_symbol(
    symbol: str,
    expiry_date_str: Optional[str] = None,
    strike: Optional[Any] = None,
    contract_type: Optional[str] = None
) -> str:
    """
    Constructs a standardized trading contract symbol (e.g. NIFTY26OCT25000CE or SENSEX26OCT72000PE).
    Safely eliminates brittle hardcoding of month/year codes.
    """
    sym = resolve_symbol(symbol)
    exp_code = format_contract_code(expiry_date_str)
    stk_str = str(strike).strip() if strike else ""
    ctype = str(contract_type).strip().upper() if contract_type else ""
    if stk_str and ctype:
        return f"{sym}{exp_code}{stk_str}{ctype}"
    return f"{sym}{exp_code}"


def get_daily_asset_schedule(now_dt: Optional[Any] = None) -> Dict[str, Any]:
    """
    Weekly Theta Decay Shield & Day 1 Premium Shield Trading Schedule:
    - Tuesday & Wednesday: SENSEX ONLY (6 Lots)
      * Tuesday: SENSEX active (NIFTY Expiry Gamma Radar unlocks post-1:00 PM)
      * Wednesday: SENSEX active (NIFTY Locked to shield against Day 1 inflated premiums)
    - Monday, Thursday & Friday: NIFTY ONLY (4 Lots)
      * Monday: NIFTY active (DTE 1 before Tuesday expiry - cheap premiums, high gamma)
      * Thursday: NIFTY active (SENSEX Expiry Gamma Radar unlocks post-1:00 PM)
      * Friday: NIFTY active (Standard trading window)
    """
    from datetime import datetime
    try:
        import pytz
        IST = pytz.timezone("Asia/Kolkata")
    except Exception:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))

    if now_dt is None:
        now_dt = datetime.now(IST)
    weekday = now_dt.weekday()  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_name = weekday_names[weekday] if 0 <= weekday < 7 else "Weekday"

    from datetime import time
    t_curr = now_dt.time() if hasattr(now_dt, "time") else time(10, 0)

    # 0. Check Weekend Closure (Saturday & Sunday are ALWAYS Exchange Holidays / Closed)
    if weekday in (5, 6):
        return {
            "weekday": weekday,
            "weekday_name": day_name,
            "is_weekday": False,
            "is_trading_holiday": True,
            "is_weekend": True,
            "holiday_name": f"Weekend Market Closure ({day_name})",
            "active_symbol": "MARKET_CLOSED",
            "locked_symbol": "MARKET_CLOSED",
            "schedule_label": f"🛑 Weekend Market Closure: {day_name} (Exchange Closed)",
            "schedule_desc": f"Standard weekend market closure ({day_name}). Next regular trading session: Monday 09:15 AM IST (NIFTY 50 • 4 Lots).",
            "schedule_rule": "Saturday & Sunday: Markets Closed • Next Session: Monday NIFTY 50 (4 Lots)",
            "is_nifty_allowed": False,
            "is_sensex_allowed": False,
            "active_lots": 0,
            "mandate_lots": 0,
            "locked_lots": 0,
            "gamma_exception_symbol": None,
            "is_post_1pm_window": False,
            "is_gamma_exception_active": False,
            "next_session_day": "Monday",
            "next_session_symbol": "NIFTY",
            "next_session_lots": 4
        }

    # Check Official NSE Holiday Calendar First
    from nse_calendar import nse_calendar
    holiday_info = nse_calendar.get_holiday_details(now_dt)
    if holiday_info is not None:
        h_name = holiday_info.get("description", "Exchange Holiday")
        return {
            "weekday": weekday,
            "weekday_name": day_name,
            "is_weekday": weekday < 5,
            "is_trading_holiday": True,
            "is_weekend": False,
            "holiday_name": h_name,
            "active_symbol": "MARKET_CLOSED",
            "locked_symbol": "MARKET_CLOSED",
            "schedule_label": f"🔴 NSE Trading Holiday: {h_name} (Market Closed)",
            "schedule_desc": f"Official NSE Trading Holiday ({h_name}). Cash & F&O segments closed today.",
            "schedule_rule": f"NSE Calendar Mandate: All trading desks suspended for {h_name}.",
            "is_nifty_allowed": False,
            "is_sensex_allowed": False,
            "active_lots": 0,
            "mandate_lots": 0,
            "locked_lots": 0,
            "gamma_exception_symbol": None,
            "is_post_1pm_window": False,
            "is_gamma_exception_active": False
        }

    # Expiry Exception Mapping:
    # - Tuesday (weekday == 1): NIFTY weekly expiry -> Gamma exception symbol = "NIFTY"
    # - Thursday (weekday == 3): SENSEX weekly expiry -> Gamma exception symbol = "SENSEX"
    gamma_exception_symbol = None
    if weekday == 1:
        gamma_exception_symbol = "NIFTY"
    elif weekday == 3:
        gamma_exception_symbol = "SENSEX"

    # Post-1:00 PM IST Gamma Blast Window (13:00 to 15:15 IST)
    gamma_window_start = time(13, 0)
    gamma_window_end = time(15, 15)
    is_post_1pm_window = (gamma_window_start <= t_curr <= gamma_window_end)
    is_gamma_exception_active = (gamma_exception_symbol is not None and is_post_1pm_window)

    if weekday in (1, 2):
        active_symbol = "SENSEX"
        locked_symbol = "NIFTY"
        schedule_label = f"{day_name} Mandate: BSE SENSEX Active (6 Lots)"
        if weekday == 1:
            schedule_label += " • NIFTY Expiry Gamma Radar Unlocks Post-1:00 PM"
        elif weekday == 2:
            schedule_label += " • Day 1 NIFTY Premium Shield (Avoid High Extrinsic Value)"
        active_lots = 6
        locked_lots = 4
    elif weekday in (0, 3, 4):
        active_symbol = "NIFTY"
        locked_symbol = "SENSEX"
        schedule_label = f"{day_name} Mandate: NIFTY 50 Active (4 Lots)"
        if weekday == 0:
            schedule_label += " • DTE 1 Pre-Expiry Prime Gamma & Affordable Premiums"
        elif weekday == 3:
            schedule_label += " • SENSEX Expiry Gamma Radar Unlocks Post-1:00 PM"
        active_lots = 4
        locked_lots = 6
    else:
        active_symbol = "NIFTY"
        locked_symbol = "SENSEX"
        schedule_label = "Weekend Mode: Market Closed (Next Session: Monday NIFTY 50 Mandate)"
        active_lots = 4
        locked_lots = 6

    schedule_rule = "Tue & Wed: SENSEX (6 Lots) | Mon, Thu & Fri: NIFTY (4 Lots) • Post-1 PM Expiry Gamma Blast Exception (1 Call Cap)"

    return {
        "weekday": weekday,
        "weekday_name": day_name,
        "is_weekday": weekday < 5,
        "active_symbol": active_symbol,
        "locked_symbol": locked_symbol,
        "schedule_label": schedule_label,
        "schedule_desc": schedule_label,
        "schedule_rule": schedule_rule,
        "is_nifty_allowed": (active_symbol == "NIFTY"),
        "is_sensex_allowed": (active_symbol == "SENSEX"),
        "active_lots": active_lots,
        "mandate_lots": active_lots,
        "locked_lots": locked_lots,
        "gamma_exception_symbol": gamma_exception_symbol,
        "is_post_1pm_window": is_post_1pm_window,
        "is_gamma_exception_active": is_gamma_exception_active
    }


def is_asset_tradable_now(symbol: str, now_dt: Optional[Any] = None, exception_call_used: bool = False) -> Dict[str, Any]:
    """
    Evaluates whether an asset is authorized for trade calls right now,
    incorporating the weekly schedule and the Post-1:00 PM Expiry Gamma Blast Exception.
    """
    sched = get_daily_asset_schedule(now_dt)
    target_sym = str(symbol).upper()

    if sched.get("is_trading_holiday"):
        if sched.get("is_weekend"):
            is_mon_active = (target_sym == "NIFTY")
            return {
                "can_trade": False,
                "tradable": False,
                "status": "WEEKEND_CLOSED",
                "reason": (
                    f"Exchange is closed for the weekend ({sched['weekday_name']}). Next active trading session: Monday ({target_sym} • 4 Lots)."
                    if is_mon_active
                    else f"Exchange is closed for the weekend ({sched['weekday_name']}). SENSEX desk opens Tuesday & Wednesday (6 Lots)."
                ),
                "badge_label": "🛑 WEEKEND CLOSED (NEXT: MON)" if is_mon_active else "🛑 WEEKEND CLOSED (TUE/WED DESK)",
                "mandate_lots": 0,
                "is_gamma_exception": False
            }
        h_name = sched.get("holiday_name", "Exchange Holiday")
        return {
            "can_trade": False,
            "tradable": False,
            "status": "MARKET_HOLIDAY_CLOSED",
            "reason": f"Official NSE Trading Holiday ({h_name}). Cash & F&O derivatives desks are closed today.",
            "badge_label": f"🔴 HOLIDAY CLOSED ({h_name.upper()})",
            "mandate_lots": 0,
            "is_gamma_exception": False
        }

    if target_sym == sched["active_symbol"]:
        return {
            "can_trade": True,
            "tradable": True,
            "status": "ACTIVE_PRIMARY",
            "reason": f"Primary active asset today on {sched['weekday_name']}.",
            "badge_label": f"🟢 ACTIVE TODAY ({sched['active_lots']} LOTS)",
            "mandate_lots": sched["active_lots"],
            "is_gamma_exception": False
        }

    # Locked Asset Evaluation
    if target_sym == sched["locked_symbol"]:
        if target_sym == sched["gamma_exception_symbol"]:
            if sched["is_gamma_exception_active"]:
                if exception_call_used:
                    return {
                        "can_trade": False,
                        "tradable": False,
                        "status": "GAMMA_EXCEPTION_COMPLETED",
                        "reason": f"1/1 Expiry Gamma Blast call already completed for {target_sym} today.",
                        "badge_label": "🛑 1/1 EXPIRY CALL COMPLETED",
                        "mandate_lots": sched["locked_lots"],
                        "is_gamma_exception": True
                    }
                else:
                    return {
                        "can_trade": True,
                        "tradable": True,
                        "status": "GAMMA_EXCEPTION_ACTIVE",
                        "reason": f"Post-1:00 PM Expiry Gamma Blast window active for {target_sym} (1 exception call permitted).",
                        "badge_label": "⚡ EXPIRY GAMMA RADAR ACTIVE (1 CALL CAP)",
                        "mandate_lots": sched["locked_lots"],
                        "is_gamma_exception": True
                    }
            else:
                return {
                    "can_trade": False,
                    "tradable": False,
                    "status": "EXPIRY_LOCKED_UNTIL_1PM",
                    "reason": f"{target_sym} is locked until 01:00 PM IST (Expiry Gamma Blast radar unlocks post-1:00 PM).",
                    "badge_label": "⏳ LOCKED UNTIL 01:00 PM (EXPIRY WATCH)",
                    "mandate_lots": sched["locked_lots"],
                    "is_gamma_exception": False
                }
        else:
            is_wed_nifty = (sched["weekday"] == 2 and target_sym == "NIFTY")
            return {
                "can_trade": False,
                "tradable": False,
                "status": "STRICTLY_LOCKED",
                "reason": (
                    f"{target_sym} is strictly locked today to shield against Day 1 premium inflation (fresh weekly cycle)."
                    if is_wed_nifty
                    else f"{target_sym} is strictly locked today to avoid near-expiry theta bleed."
                ),
                "badge_label": "🔒 LOCKED (DAY 1 PREMIUM SHIELD)" if is_wed_nifty else "🔒 LOCKED (THETA SHIELD)",
                "mandate_lots": sched["locked_lots"],
                "is_gamma_exception": False
            }

    return {
        "can_trade": True,
        "tradable": True,
        "status": "ACTIVE",
        "reason": "Standard asset.",
        "badge_label": "🟢 TRADABLE",
        "mandate_lots": 4 if target_sym == "NIFTY" else 6,
        "is_gamma_exception": False
    }


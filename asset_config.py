"""
Canonical Multi-Asset Quantitative Trading Registry
Single Source of Truth for RELIANCE and ADANI ENTERPRISES specifications,
lot sizes, risk boundaries, price steps, and broker endpoints.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

@dataclass(frozen=True)
class AssetSpec:
    symbol: str                    # Standard ticker symbol: "RELIANCE" | "ADANIENT"
    display_name: str              # User-facing desk title
    full_name: str                 # Corporate entity name
    yf_symbol: str                 # Yahoo Finance query symbol: "RELIANCE.NS" | "ADANIENT.NS"
    lot_size: int                  # F&O Market Lot Size: 500 (Reliance) | 309 (Adani)
    default_lots: int              # Standard trading lot count: 2
    target_pts: float              # Quantitative profit target (points)
    sl_pts: float                  # Quantitative stop-loss (points)
    be_pts: float                  # Breakeven threshold (points to move SL to cost)
    profit_lock_trigger: float     # Points gained to activate guaranteed profit lock
    profit_lock_locked: float      # Guaranteed profit points locked in capital
    strike_step: int               # Option chain strike interval: 10 (Reliance) | 50 (Adani)
    default_spot: float            # Verified baseline spot price: 1167.70 (Reliance) | 2816.80 (Adani)
    default_strike: int            # Baseline ATM strike: 1170 (Reliance) | 2850 (Adani)
    default_call_price: float      # Baseline ATM Call premium: 37.65 (Reliance) | 84.60 (Adani)
    default_put_price: float       # Baseline ATM Put premium: 23.10 (Reliance) | 110.45 (Adani)
    groww_company_slug: str        # Groww web slug: "reliance-industries-ltd" | "adani-enterprises-ltd"
    volume_norm: int               # Average daily volume benchmark
    daily_sl_cap_rupees: float     # Maximum 1-day capital risk cap for 1 lot
    tape_quantities: Tuple[int, ...] # Order tape simulated fill sizes (lot multiples)
    beta: float = 1.15             # Benchmark/NIFTY beta
    limit_collar_pts: float = 0.65 # Execution limit collar points
    estimated_tax_per_lot: float = 65.0 # Estimated STT/turnover tax per lot
    parent_sector: str = "NIFTY ENERGY" # Parent sectoral index
    total_capital: float = 73643.72 # Default allocated capital
    breakout_buffer: float = 1.20  # Intraday breakout trigger buffer (points)
    trail_runner_offset: float = 1.0 # Runner trailing offset beyond profit lock (points)
    bsm_sigma: float = 0.212       # Benchmark baseline IV for Black-Scholes fallback
    has_crude_coupling: bool = True # Flag for Brent Crude correlation weighting
    fallback_call_vol: int = 98500  # Fallback market call volume
    fallback_put_vol: int = 84200   # Fallback market put volume
    fallback_call_oi: int = 450000  # Fallback ATM call open interest
    fallback_put_oi: int = 380000   # Fallback ATM put open interest
    spread_threshold: float = 0.04 # Maximum tolerable bid-ask spread fraction
    max_pain_gamma_divisor: float = 15.0 # Gamma proxy divisor scaling
    jitter_range: Tuple[float, float] = (-0.15, 0.20) # Synthetic tick noise boundaries
    escalator_t1_thresh: float = 3.0 # Tier 1 Breakeven profit trigger threshold
    escalator_t2_thresh: float = 5.0 # Tier 2 Profit Lock trigger threshold
    escalator_t1_lock: float = 0.10  # Tier 1 Stop Loss lock amount
    escalator_t2_lock: float = 2.50  # Tier 2 Stop Loss lock amount
    min_confluence_gate: float = 68.0 # Institutional Directional Confluence Gate Threshold (%)

ASSET_SPECS: Dict[str, AssetSpec] = {
    "RELIANCE": AssetSpec(
        symbol="RELIANCE",
        display_name="RELIANCE QUANT DESK",
        full_name="Reliance Industries Ltd.",
        yf_symbol="RELIANCE.NS",
        lot_size=500,
        default_lots=2,
        target_pts=7.0,
        sl_pts=5.0,
        be_pts=3.5,
        profit_lock_trigger=5.0,
        profit_lock_locked=2.5,
        min_confluence_gate=69.0,
        strike_step=10,
        default_spot=1167.70,
        default_strike=1170,
        default_call_price=37.65,
        default_put_price=23.10,
        groww_company_slug="reliance-industries-ltd",
        volume_norm=4725000,
        daily_sl_cap_rupees=5000.0,
        tape_quantities=(500, 1000, 1500, 2000),
        beta=1.15,
        limit_collar_pts=0.65,
        estimated_tax_per_lot=65.0,
        parent_sector="NIFTY ENERGY",
        total_capital=73643.72,
        breakout_buffer=1.20,
        trail_runner_offset=1.0,
        bsm_sigma=0.212,
        has_crude_coupling=True,
        fallback_call_vol=98500,
        fallback_put_vol=84200,
        fallback_call_oi=450000,
        fallback_put_oi=380000,
        spread_threshold=0.04,
        max_pain_gamma_divisor=15.0,
        jitter_range=(-0.15, 0.20),
        escalator_t1_thresh=3.0,
        escalator_t2_thresh=5.0,
        escalator_t1_lock=0.10,
        escalator_t2_lock=2.50
    ),
    "ADANIENT": AssetSpec(
        symbol="ADANIENT",
        display_name="ADANI ENTERPRISES QUANT DESK",
        full_name="Adani Enterprises Ltd.",
        yf_symbol="ADANIENT.NS",
        lot_size=309,
        default_lots=2,
        target_pts=35.0,
        sl_pts=15.0,
        be_pts=12.0,
        profit_lock_trigger=20.0,
        profit_lock_locked=12.0,
        min_confluence_gate=72.0,
        strike_step=50,
        default_spot=2816.80,
        default_strike=2850,
        default_call_price=84.60,
        default_put_price=110.45,
        groww_company_slug="adani-enterprises-ltd",
        volume_norm=1850000,
        daily_sl_cap_rupees=9500.0,
        tape_quantities=(309, 618, 927, 1236),
        beta=1.65,
        limit_collar_pts=1.80,
        estimated_tax_per_lot=85.0,
        parent_sector="NIFTY 50",
        total_capital=85000.0,
        breakout_buffer=3.50,
        trail_runner_offset=5.0,
        bsm_sigma=0.355,
        has_crude_coupling=False,
        fallback_call_vol=2770,
        fallback_put_vol=5075,
        fallback_call_oi=22500,
        fallback_put_oi=19000,
        spread_threshold=0.10,
        max_pain_gamma_divisor=50.0,
        jitter_range=(-0.45, 0.55),
        escalator_t1_thresh=15.0,
        escalator_t2_thresh=25.0,
        escalator_t1_lock=0.50,
        escalator_t2_lock=12.0
    ),
    "NIFTY": AssetSpec(
        symbol="NIFTY",
        display_name="NIFTY 50 QUANT DESK",
        full_name="Nifty 50 Index (NSE)",
        yf_symbol="^NSEI",
        lot_size=25,
        default_lots=2,
        target_pts=35.0,
        sl_pts=18.0,
        be_pts=18.0,
        profit_lock_trigger=28.0,
        profit_lock_locked=15.0,
        min_confluence_gate=72.0,
        strike_step=50,
        default_spot=25250.0,
        default_strike=25250,
        default_call_price=135.0,
        default_put_price=125.0,
        groww_company_slug="nifty-50",
        volume_norm=15000000,
        daily_sl_cap_rupees=2500.0,
        tape_quantities=(25, 50, 75, 100),
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
        escalator_t1_thresh=18.0,
        escalator_t2_thresh=28.0,
        escalator_t1_lock=0.50,
        escalator_t2_lock=15.0
    ),
    "SENSEX": AssetSpec(
        symbol="SENSEX",
        display_name="BSE SENSEX QUANT DESK",
        full_name="BSE SENSEX 30 Index",
        yf_symbol="^BSESN",
        lot_size=10,
        default_lots=2,
        target_pts=120.0,
        sl_pts=60.0,
        be_pts=60.0,
        profit_lock_trigger=95.0,
        profit_lock_locked=50.0,
        min_confluence_gate=72.0,
        strike_step=100,
        default_spot=82500.0,
        default_strike=82500,
        default_call_price=420.0,
        default_put_price=390.0,
        groww_company_slug="bse-sensex",
        volume_norm=8000000,
        daily_sl_cap_rupees=3000.0,
        tape_quantities=(10, 20, 30, 40),
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
    """Canonical resolver mapping any variant name to standard 'RELIANCE', 'ADANIENT', 'NIFTY', or 'SENSEX'."""
    text = f"{symbol or ''} {contract or ''}".upper()
    if "SENSEX" in text or "BSESN" in text:
        return "SENSEX"
    if "NIFTY" in text or "NSEI" in text:
        return "NIFTY"
    if "ADANI" in text:
        return "ADANIENT"
    return "RELIANCE"

def get_asset_spec(symbol: Optional[str] = None, contract: Optional[str] = None) -> AssetSpec:
    """Returns the immutable AssetSpec configuration for the given symbol or contract."""
    sym = resolve_symbol(symbol, contract)
    return ASSET_SPECS[sym]

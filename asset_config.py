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

ASSET_SPECS: Dict[str, AssetSpec] = {
    "RELIANCE": AssetSpec(
        symbol="RELIANCE",
        display_name="RELIANCE QUANT DESK",
        full_name="Reliance Industries Ltd.",
        yf_symbol="RELIANCE.NS",
        lot_size=500,
        default_lots=2,
        target_pts=10.0,
        sl_pts=4.5,
        be_pts=3.5,
        profit_lock_trigger=5.5,
        profit_lock_locked=3.0,
        strike_step=10,
        default_spot=1167.70,
        default_strike=1170,
        default_call_price=37.65,
        default_put_price=23.10,
        groww_company_slug="reliance-industries-ltd",
        volume_norm=4725000,
        daily_sl_cap_rupees=5000.0,
        tape_quantities=(500, 1000, 1500, 2000)
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
        strike_step=50,
        default_spot=2816.80,
        default_strike=2850,
        default_call_price=84.60,
        default_put_price=110.45,
        groww_company_slug="adani-enterprises-ltd",
        volume_norm=1850000,
        daily_sl_cap_rupees=9500.0,
        tape_quantities=(309, 618, 927, 1236)
    )
}

def resolve_symbol(symbol: Optional[str] = None, contract: Optional[str] = None) -> str:
    """Canonical resolver mapping any variant name to standard 'RELIANCE' or 'ADANIENT'."""
    text = f"{symbol or ''} {contract or ''}".upper()
    if "ADANI" in text:
        return "ADANIENT"
    return "RELIANCE"

def get_asset_spec(symbol: Optional[str] = None, contract: Optional[str] = None) -> AssetSpec:
    """Returns the immutable AssetSpec configuration for the given symbol or contract."""
    sym = resolve_symbol(symbol, contract)
    return ASSET_SPECS[sym]

"""
core.risk.cost_engine
Institutional Indian F&O Statutory Tax and Transaction Cost Engine.
Calculates STT (Budget 2024 revision), exchange charges, SEBI turnover fees, stamp duty, brokerage, and GST.
"""

from typing import Dict, Any


class IndianFOTransactionCostEngine:
    """
    Institutional Transaction Cost & Statutory Tax Engine for Indian F&O.
    Accurately computes post-tax net PnL, points drag, and statutory deductions:
    - Brokerage: ₹20/order flat (Groww / Zerodha / AngelOne) = ₹40 round-trip
    - STT (Securities Transaction Tax): 0.10% on option sell premium turnover (Budget 2024 revised)
    - Exchange Turnover Charges: 0.050% on total premium turnover (NSE)
    - SEBI Turnover Charges: ₹10 per crore (0.000001) on total turnover
    - Stamp Duty: 0.003% on buy premium turnover
    - GST: 18% on (Brokerage + Exchange turnover charges + SEBI charges)
    """
    BROKERAGE_PER_ORDER = 20.0
    EXCHANGE_TURNOVER_PCT = 0.00050   # 0.05% on option premium turnover
    SEBI_CHARGES_PCT = 0.000001       # ₹10 per crore
    STAMP_DUTY_BUY_PCT = 0.00003      # 0.003% on buy turnover
    STT_SELL_PCT = 0.00100            # 0.10% on sell turnover (Budget 2024)
    GST_PCT = 0.18                    # 18% on brokerage & exchange fees

    @classmethod
    def calculate_round_trip(cls, buy_premium: float, sell_premium: float, qty: int) -> Dict[str, Any]:
        """Calculates precise statutory deductions and net post-tax PnL for an F&O option trade."""
        qty = max(1, int(qty))
        buy_turnover = float(buy_premium) * qty
        sell_turnover = float(sell_premium) * qty
        total_turnover = buy_turnover + sell_turnover

        brokerage = cls.BROKERAGE_PER_ORDER * 2.0
        exchange_charges = total_turnover * cls.EXCHANGE_TURNOVER_PCT
        sebi_charges = total_turnover * cls.SEBI_CHARGES_PCT
        stamp_duty = buy_turnover * cls.STAMP_DUTY_BUY_PCT
        stt = sell_turnover * cls.STT_SELL_PCT
        gst = (brokerage + exchange_charges + sebi_charges) * cls.GST_PCT

        total_taxes_and_charges = brokerage + exchange_charges + sebi_charges + stamp_duty + stt + gst
        gross_pnl = sell_turnover - buy_turnover
        net_pnl = gross_pnl - total_taxes_and_charges
        pts_drag = total_taxes_and_charges / qty if qty > 0 else 0.0
        gross_pts = (sell_premium - buy_premium)
        net_pts = gross_pts - pts_drag

        return {
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "total_charges": round(total_taxes_and_charges, 2),
            "points_drag": round(pts_drag, 2),
            "gross_pts": round(gross_pts, 2),
            "net_pts": round(net_pts, 2),
            "stt": round(stt, 2),
            "exchange_charges": round(exchange_charges, 2),
            "brokerage": round(brokerage, 2),
            "gst": round(gst, 2),
            "stamp_duty": round(stamp_duty, 2)
        }

"""
core.analytics.options_greeks
Institutional Options Greeks, Pricing & Volatility Surface Modeling.
Calculates Black-Scholes theoretical pricing, Greeks (Delta, Gamma, Vega, Theta, Rho),
Implied Volatility (IV) solver, Put-Call Ratio (PCR), and Max Pain.
"""

import math
from typing import Dict, Any, List, Optional, Tuple


def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


class OptionsGreeksCalculator:
    """
    High-performance analytical options Greeks engine.
    Computes Delta, Gamma, Vega, Theta, Rho, and Implied Volatility.
    """
    DEFAULT_RISK_FREE_RATE = 0.065  # 6.5% RBI repo rate baseline

    @classmethod
    def calculate_d1_d2(
        cls,
        spot: float,
        strike: float,
        time_to_exp_years: float,
        iv: float,
        r: float = DEFAULT_RISK_FREE_RATE
    ) -> Tuple[float, float]:
        """Calculates Black-Scholes d1 and d2 parameters."""
        if spot <= 0 or strike <= 0 or time_to_exp_years <= 0 or iv <= 0:
            return 0.0, 0.0
        numerator = math.log(spot / strike) + (r + 0.5 * iv * iv) * time_to_exp_years
        denominator = iv * math.sqrt(time_to_exp_years)
        d1 = numerator / denominator
        d2 = d1 - denominator
        return d1, d2

    @classmethod
    def calculate_greeks(
        cls,
        spot: float,
        strike: float,
        time_to_exp_days: float,
        iv_percent: float,
        option_type: str = "CE",
        r: float = DEFAULT_RISK_FREE_RATE
    ) -> Dict[str, float]:
        """
        Calculates complete Greeks profile for a contract.
        Returns: delta, gamma, theta_per_day, vega_per_pct, rho, and theoretical_price.
        """
        is_call = option_type.upper() in ["CE", "CALL"]
        T = max(1e-5, time_to_exp_days / 365.25)
        sigma = max(0.01, iv_percent / 100.0)
        spot = max(0.01, spot)
        strike = max(0.01, strike)

        d1, d2 = cls.calculate_d1_d2(spot, strike, T, sigma, r)
        sqrt_T = math.sqrt(T)
        pdf_d1 = norm_pdf(d1)
        discount = math.exp(-r * T)

        # 1. Delta
        delta = norm_cdf(d1) if is_call else (norm_cdf(d1) - 1.0)

        # 2. Gamma (identical for Call and Put)
        gamma = pdf_d1 / (spot * sigma * sqrt_T) if (spot * sigma * sqrt_T) > 0 else 0.0

        # 3. Vega (per 1% IV move)
        vega = (spot * sqrt_T * pdf_d1) / 100.0

        # 4. Theta (daily decay)
        first_term = -(spot * pdf_d1 * sigma) / (2.0 * sqrt_T)
        if is_call:
            second_term = -r * strike * discount * norm_cdf(d2)
            theta_annual = first_term + second_term
        else:
            second_term = r * strike * discount * norm_cdf(-d2)
            theta_annual = first_term + second_term
        theta_daily = theta_annual / 365.25

        # 5. Theoretical Price
        if is_call:
            price = (spot * norm_cdf(d1)) - (strike * discount * norm_cdf(d2))
        else:
            price = (strike * discount * norm_cdf(-d2)) - (spot * norm_cdf(-d1))

        # 6. Rho
        if is_call:
            rho = (strike * T * discount * norm_cdf(d2)) / 100.0
        else:
            rho = (-strike * T * discount * norm_cdf(-d2)) / 100.0

        return {
            "theoretical_price": max(0.0, round(price, 2)),
            "delta": round(delta, 4),
            "gamma": round(gamma, 6),
            "theta": round(theta_daily, 2),
            "vega": round(vega, 2),
            "rho": round(rho, 4),
            "iv": round(iv_percent, 2)
        }

    @classmethod
    def calculate_max_pain(cls, strikes: List[float], ce_oi: List[int], pe_oi: List[int]) -> float:
        """
        Calculates institutional Max Pain strike where option writers have minimal payout.
        """
        if not strikes or len(strikes) != len(ce_oi) or len(strikes) != len(pe_oi):
            return 0.0

        min_total_loss = float("inf")
        max_pain_strike = strikes[0]

        for test_strike in strikes:
            total_loss = 0.0
            for i, strike in enumerate(strikes):
                # Call writer loss if spot settles at test_strike
                if test_strike > strike:
                    total_loss += (test_strike - strike) * ce_oi[i]
                # Put writer loss if spot settles at test_strike
                if test_strike < strike:
                    total_loss += (strike - test_strike) * pe_oi[i]

            if total_loss < min_total_loss:
                min_total_loss = total_loss
                max_pain_strike = test_strike

        return float(max_pain_strike)

    @classmethod
    def calculate_pcr(cls, ce_oi_total: float, pe_oi_total: float) -> Tuple[float, str]:
        """
        Computes Put-Call Ratio and market sentiment regime.
        """
        if ce_oi_total <= 0:
            return 1.0, "NEUTRAL"
        pcr = round(pe_oi_total / ce_oi_total, 3)
        if pcr >= 1.35:
            sentiment = "OVERBOUGHT_BULLISH_EXHAUSTION"
        elif pcr >= 1.05:
            sentiment = "BULLISH_ACCUMULATION"
        elif pcr <= 0.65:
            sentiment = "OVERSOLD_BEARISH_EXHAUSTION"
        elif pcr <= 0.85:
            sentiment = "BEARISH_DISTRIBUTION"
        else:
            sentiment = "BALANCED_NEUTRAL"
        return pcr, sentiment

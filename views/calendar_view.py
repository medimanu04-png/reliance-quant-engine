"""
views/calendar_view.py
NSE Official Holiday Calendar & Expiry Shift Intelligence Tab View.
"""

import streamlit as st


def render_calendar_tab(active_symbol: str = "NIFTY", render_hub_fn=None):
    """Renders the NSE Calendar & Expiry Shift Hub within its dedicated tab."""
    if render_hub_fn is not None:
        render_hub_fn(active_symbol=active_symbol)
    else:
        st.info(f"📅 NSE Official Calendar Hub active for {active_symbol}")

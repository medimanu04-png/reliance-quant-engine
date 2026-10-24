"""
views/calendar_view.py
NSE Official Holiday Calendar & Expiry Shift Intelligence Hub.
Provides live connection telemetry, today's market status, expiry shift radars,
and official holiday master schedules.
"""

from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st

from nse_calendar import nse_calendar
from asset_config import resolve_symbol
from views.ui_components import st_button_stretch, st_dataframe_stretch

IST = timezone(timedelta(hours=5, minutes=30))


def render_nse_calendar_hub(active_symbol: str = "NIFTY"):
    """
    Renders the Official NSE Holiday Calendar & Expiry Shift Intelligence Hub.
    Provides live connection telemetry, today's market status, expiry shift radars,
    and official holiday master schedules.
    """
    now = datetime.now(IST)
    telemetry = nse_calendar.get_calendar_status_telemetry()
    mkt = telemetry["market_status"]
    next_h = telemetry["next_holiday"]
    cur_sym = resolve_symbol(active_symbol)

    # Header Bar with Live Sync Button
    c_head1, c_head2 = st.columns([3.2, 0.8])
    with c_head1:
        st.html(f"""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
            <span style="font-size: 1.4rem;">📅</span>
            <div>
                <span style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.3px;">
                    NSE OFFICIAL HOLIDAY & EXPIRY SHIFT CALENDAR
                </span>
                <div style="font-size: 0.72rem; color: #94A3B8;">
                    Live Synchronized with <b style="color: #38BDF8;">NSE India Master Portal</b> (api/holiday-master) &bull; Source: <span style="color: #34D399; font-weight: 700;">{telemetry['sync_source']}</span> &bull; {telemetry['total_holidays']} Holidays Indexed
                </div>
            </div>
        </div>
        """)
    with c_head2:
        if st_button_stretch("🔄 Sync NSE API", key="btn_sync_nse_cal"):
            with st.spinner("Connecting to NSE India official API..."):
                res = nse_calendar.sync_with_nse(force=True)
                if res.get("success"):
                    st.toast(f"✅ NSE Calendar Synced: {res.get('holiday_count')} holidays updated!")
                else:
                    st.toast(f"⚠️ NSE API notice: {res.get('message')}")
                st.rerun()

    # 4 Quick Metrics Tiles
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        st.html(f"""
        <div style="background: #0F172A; border: 1px solid #1E293B; border-radius: 8px; padding: 10px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; text-transform: uppercase;">TODAY'S MARKET SESSION</div>
            <div style="font-size: 0.95rem; font-weight: 800; color: {mkt['badge_color']}; margin-top: 3px;">{mkt['status_label']}</div>
            <div style="font-size: 0.68rem; color: #94A3B8; margin-top: 2px;">{telemetry['today_str']} ({telemetry['today_weekday']})</div>
        </div>
        """)
    with t2:
        next_title = next_h['tradingDate'] if next_h else "None"
        next_sub = f"{next_h['description']} (in {next_h['days_left']}d)" if next_h else "No upcoming holidays"
        st.html(f"""
        <div style="background: #0F172A; border: 1px solid #1E293B; border-radius: 8px; padding: 10px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; text-transform: uppercase;">NEXT EXCHANGE HOLIDAY</div>
            <div style="font-size: 0.95rem; font-weight: 800; color: #FCD34D; margin-top: 3px;">{next_title}</div>
            <div style="font-size: 0.68rem; color: #94A3B8; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{next_sub}</div>
        </div>
        """)
    with t3:
        act_nifty = telemetry["active_nifty_expiry"]
        n_nom_day = act_nifty.get("nominal_weekday", "Tuesday")[:3].upper()
        n_shift_badge = '<span style="color: #F87171; font-weight: 800;">⚠️ PREPONED</span>' if act_nifty['is_shifted'] else f'<span style="color: #34D399; font-weight: 800;">STANDARD {n_nom_day}</span>'
        st.html(f"""
        <div style="background: #0F172A; border: 1px solid #1E293B; border-radius: 8px; padding: 10px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; text-transform: uppercase;">NIFTY 50 EXPIRY</div>
            <div style="font-size: 0.95rem; font-weight: 800; color: #38BDF8; margin-top: 3px;">{act_nifty['actual_str']}</div>
            <div style="font-size: 0.68rem; color: #94A3B8; margin-top: 2px;">{act_nifty['actual_weekday']} &bull; {n_shift_badge}</div>
        </div>
        """)
    with t4:
        act_sensex = telemetry["active_sensex_expiry"]
        s_nom_day = act_sensex.get("nominal_weekday", "Thursday")[:3].upper()
        s_shift_badge = '<span style="color: #F87171; font-weight: 800;">⚠️ PREPONED</span>' if act_sensex['is_shifted'] else f'<span style="color: #C084FC; font-weight: 800;">STANDARD {s_nom_day}</span>'
        st.html(f"""
        <div style="background: #0F172A; border: 1px solid #1E293B; border-radius: 8px; padding: 10px 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; text-transform: uppercase;">BSE SENSEX EXPIRY</div>
            <div style="font-size: 0.95rem; font-weight: 800; color: #C084FC; margin-top: 3px;">{act_sensex['actual_str']}</div>
            <div style="font-size: 0.68rem; color: #94A3B8; margin-top: 2px;">{act_sensex['actual_weekday']} &bull; {s_shift_badge}</div>
        </div>
        """)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Expiry Shift Radar & Collision Audit Section
    st.html("""
    <div style="background: linear-gradient(90deg, rgba(30, 27, 75, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%); border: 1px solid rgba(129, 140, 248, 0.35); border-radius: 8px; padding: 10px 16px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.1rem;">⚡</span>
                <span style="font-size: 0.86rem; font-weight: 800; color: #FFFFFF;">
                    EXPIRY SHIFT RADAR (SEBI / NSE MANDATE COLLISION AUDIT)
                </span>
            </div>
            <span style="font-size: 0.70rem; color: #94A3B8;">
                Rules: When an expiry falls on an exchange holiday, contracts <b style="color: #FCD34D;">automatically prepone</b> to the preceding trading day.
            </span>
        </div>
    </div>
    """)

    year_shifts = nse_calendar.scan_all_expiry_shifts_for_year(now.year)
    shift_col1, shift_col2 = st.columns(2)
    with shift_col1:
        st.markdown(f"**⚡ NIFTY 50 Weekly Expiry Shifts ({len(year_shifts['NIFTY_WEEKLY_SHIFTS'])})**")
        for s in year_shifts["NIFTY_WEEKLY_SHIFTS"]:
            st.html(f"""
            <div style="background: #0F172A; border-left: 3px solid #F59E0B; border-top: 1px solid #1E293B; border-right: 1px solid #1E293B; border-bottom: 1px solid #1E293B; border-radius: 6px; padding: 8px 12px; margin-bottom: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.78rem; font-weight: 800; color: #38BDF8;">
                        Nominal: <del style="color: #94A3B8;">{s['nominal_str']} ({s['nominal_weekday']})</del>
                    </span>
                    <span style="background: rgba(245, 158, 11, 0.2); color: #FCD34D; border: 1px solid rgba(245, 158, 11, 0.4); font-size: 0.65rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">
                        PREPONED &bull; {s['actual_str']} ({s['actual_weekday']})
                    </span>
                </div>
                <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 3px;">
                    Reason: <b>{', '.join(s['holiday_triggers'])}</b>
                </div>
            </div>
            """)

    with shift_col2:
        st.markdown(f"**⚡ BSE SENSEX Weekly Expiry Shifts ({len(year_shifts['SENSEX_WEEKLY_SHIFTS'])})**")
        for s in year_shifts["SENSEX_WEEKLY_SHIFTS"]:
            st.html(f"""
            <div style="background: #0F172A; border-left: 3px solid #A855F7; border-top: 1px solid #1E293B; border-right: 1px solid #1E293B; border-bottom: 1px solid #1E293B; border-radius: 6px; padding: 8px 12px; margin-bottom: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.78rem; font-weight: 800; color: #C084FC;">
                        Nominal: <del style="color: #94A3B8;">{s['nominal_str']} ({s['nominal_weekday']})</del>
                    </span>
                    <span style="background: rgba(168, 85, 247, 0.2); color: #D8B4FE; border: 1px solid rgba(168, 85, 247, 0.4); font-size: 0.65rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">
                        PREPONED &bull; {s['actual_str']} ({s['actual_weekday']})
                    </span>
                </div>
                <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 3px;">
                    Reason: <b>{', '.join(s['holiday_triggers'])}</b>
                </div>
            </div>
            """)

    if year_shifts.get("MONTHLY_STOCK_SHIFTS"):
        st.markdown(f"**⚡ Equity Stock Monthly Expiry Shifts ({len(year_shifts['MONTHLY_STOCK_SHIFTS'])}) (Last Tuesday Mandate)**")
        for s in year_shifts["MONTHLY_STOCK_SHIFTS"]:
            st.html(f"""
            <div style="background: #0F172A; border-left: 3px solid #10B981; border-top: 1px solid #1E293B; border-right: 1px solid #1E293B; border-bottom: 1px solid #1E293B; border-radius: 6px; padding: 8px 12px; margin-bottom: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.78rem; font-weight: 800; color: #34D399;">
                        Nominal: <del style="color: #94A3B8;">{s['nominal_str']} ({s['nominal_weekday']})</del>
                    </span>
                    <span style="background: rgba(168, 85, 129, 0.2); color: #6EE7B7; border: 1px solid rgba(16, 185, 129, 0.4); font-size: 0.65rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">
                        PREPONED &bull; {s['actual_str']} ({s['actual_weekday']})
                    </span>
                </div>
                <div style="font-size: 0.70rem; color: #CBD5E1; margin-top: 3px;">
                    Reason: <b>{', '.join(s['holiday_triggers'])}</b>
                </div>
            </div>
            """)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Master NSE Trading Holidays Table
    st.markdown("### 📋 Official NSE Trading Holidays Schedule")
    hol_year_filter = st.radio("Select Calendar Year:", ["2026 (Active)", "2025", "2024", "All Indexed Years"], horizontal=True, key="sel_cal_year_filter")
    y_target = 2026 if "2026" in hol_year_filter else (2025 if "2025" in hol_year_filter else (2024 if "2024" in hol_year_filter else None))
    holidays_display = nse_calendar.get_all_holidays(year=y_target)

    rows = []
    today_d = now.date()
    for h in holidays_display:
        h_d = h["date"]
        diff = (h_d - today_d).days
        if diff == 0:
            status_tag = "🔴 TODAY (MARKET CLOSED)"
        elif diff > 0:
            status_tag = f"⏳ In {diff} days"
        else:
            status_tag = f"Completed ({abs(diff)}d ago)"

        rows.append({
            "Trading Date": h["tradingDate"],
            "Weekday": h["weekDay"],
            "Holiday Description": h["description"],
            "Status": status_tag
        })

    df_hol = pd.DataFrame(rows)
    st_dataframe_stretch(df_hol, hide_index=True)


def render_calendar_tab(active_symbol: str = "NIFTY", render_hub_fn=None):
    """Renders the NSE Calendar & Expiry Shift Hub within its dedicated tab."""
    fn = render_hub_fn or render_nse_calendar_hub
    fn(active_symbol=active_symbol)

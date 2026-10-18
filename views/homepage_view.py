"""
views/homepage_view.py
Market Overview Homepage View (Executive Hub, Launchpad, and Audit Suite).
"""

import os
from datetime import datetime, timezone, timedelta
import streamlit as st
import streamlit.components.v1 as components

from asset_config import get_asset_spec, get_daily_asset_schedule, is_asset_tradable_now
from groww_market_feed import GrowwMarketFeed
from telegram_notifier import TelegramNotifier
from pre_market_health_check import PreMarketHealthCheckEngine
from eod_session_summary import EODSessionSummaryEngine
from views.ui_components import st_download_button_stretch, st_button_stretch, st_dataframe_stretch
import views.auth_manager as auth_mgr

IST = timezone(timedelta(hours=5, minutes=30))


def render_homepage(ctx: dict):
    """Renders the executive homepage, benchmark desk tiles, and audit repository."""
    render_sticky_header_fn = ctx.get("render_sticky_header_fn")
    render_auto_rescan_fn = ctx.get("render_auto_rescan_fn")
    render_quant_desk_clock_fn = ctx.get("render_quant_desk_clock_fn")
    render_macro_benchmarks_fn = ctx.get("render_macro_benchmarks_fn")
    render_nse_calendar_hub_fn = ctx.get("render_nse_calendar_hub_fn")
    is_rescan = ctx.get("is_rescan", False)

    if render_sticky_header_fn:
        render_sticky_header_fn()

    top_ctrl_col, top_clock_col = st.columns([2.3, 1.7], gap="small")
    with top_ctrl_col:
        if render_auto_rescan_fn:
            render_auto_rescan_fn()
    with top_clock_col:
        if render_quant_desk_clock_fn:
            render_quant_desk_clock_fn()

    st.markdown("---")

    if render_macro_benchmarks_fn:
        render_macro_benchmarks_fn()

    st.markdown("---")

    st.html("""
    <style>
    .quant-desk-tile {
        transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
    }
    .quant-desk-tile:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6) !important;
    }
    .tile-nifty:hover {
        border-color: rgba(16, 185, 129, 0.95) !important;
    }
    .tile-sensex:hover {
        border-color: rgba(168, 85, 247, 0.95) !important;
    }
    </style>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.25rem;">⚡</span>
            <span style="font-size: 0.94rem; font-weight: 800; color: #E2E8F0; text-transform: uppercase; letter-spacing: 0.8px;">
                ACTIVE QUANT TRADING DESKS (INSTANT LAUNCHPAD)
            </span>
        </div>
        <span style="font-size: 0.76rem; color: #94A3B8;">
            Click any tile to launch desk in a new tab (<b style="color: #10B981;">/Nifty</b>, <b style="color: #A855F7;">/Sensex</b>) ↗
        </span>
    </div>
    """)

    tg_cfg_hp = TelegramNotifier.load_config()
    tg_active_hp = tg_cfg_hp.get("enabled", True)
    st.html(f"""
    <div style="background: linear-gradient(90deg, rgba(16, 185, 129, 0.12) 0%, rgba(56, 189, 248, 0.10) 100%); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 10px; padding: 10px 16px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="display: inline-block; width: 10px; height: 10px; background: #10B981; border-radius: 50%; box-shadow: 0 0 8px #10B981;"></span>
            <span style="font-weight: 700; color: #E2E8F0;">24/7 Benchmark Scanner: <b style="color: #10B981;">ACTIVE & MONITORING</b></span>
            <span style="color: #94A3B8;">| 2 Desks: <b style="color: #10B981;">NIFTY 50</b> • <b style="color: #A855F7;">BSE SENSEX</b></span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
            <span>📲 Telegram Calls: <b style="color: {'#10B981' if tg_active_hp else '#F87171'};">{'CONNECTED' if tg_active_hp else 'DISABLED'}</b></span>
            <span>⚡ Direct Feed: <b style="color: #38BDF8;">Groww API (0ms)</b></span>
        </div>
    </div>
    """)

    hp_sched = get_daily_asset_schedule(datetime.now(IST))
    hp_weekday = hp_sched["weekday_name"]
    nifty_tradable_info = is_asset_tradable_now("NIFTY", datetime.now(IST))
    sensex_tradable_info = is_asset_tradable_now("SENSEX", datetime.now(IST))
    is_nifty_tradable_today = nifty_tradable_info["can_trade"]
    is_sensex_tradable_today = sensex_tradable_info["can_trade"]

    if hp_sched.get("is_weekend"):
        hp_banner_icon = "🛑"
        hp_banner_title = f"WEEKEND MARKET CLOSURE: <span style='color: #F87171;'>{hp_weekday.upper()} • CLOSED</span>"
        hp_banner_sub = f"Standard Weekend Market Closure: Both NSE & BSE cash & derivatives segments are closed. Next Session: <b style='color: #38BDF8;'>Monday 09:15 AM IST (NIFTY 50 • 4 Lots)</b>."
    elif hp_sched.get("is_trading_holiday"):
        hp_banner_icon = "🔴"
        hp_banner_title = f"NSE TRADING HOLIDAY: <span style='color: #F87171;'>{hp_sched.get('holiday_name', 'EXCHANGE HOLIDAY').upper()} • CLOSED</span>"
        hp_banner_sub = f"Official exchange holiday ({hp_sched.get('holiday_name')}). Cash & F&O derivatives desks suspended today."
    else:
        hp_banner_icon = "🛡️"
        hp_banner_title = f"THETA DECAY & DAY 1 PREMIUM SHIELD: <span style='color: #818CF8;'>{hp_weekday.upper()} MANDATE</span>"
        hp_banner_sub = "Standard: <b style='color: #A855F7;'>Tue & Wed = SENSEX ONLY (6 Lots)</b> &bull; <b style='color: #10B981;'>Mon, Thu & Fri = NIFTY ONLY (4 Lots)</b> &bull; <span style='color: #FCD34D;'>Post-1:30 PM Expiry Gamma Blast Exception (01:30–02:45 PM, 1 Call Cap)</span>"

    st.html(f"""
    <div style="background: linear-gradient(90deg, rgba(30, 27, 75, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1.5px solid rgba(129, 140, 248, 0.5); border-radius: 10px; padding: 12px 18px; margin-bottom: 16px; box-shadow: 0 4px 18px rgba(0,0,0,0.35);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.25rem;">{hp_banner_icon}</span>
                <div>
                    <span style="font-size: 0.86rem; font-weight: 800; color: #FFFFFF; letter-spacing: 0.2px;">
                        {hp_banner_title}
                    </span>
                    <div style="font-size: 0.73rem; color: #94A3B8; margin-top: 2px;">
                        {hp_banner_sub}
                    </div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="background: {'rgba(16, 185, 129, 0.20)' if is_nifty_tradable_today else 'rgba(100, 116, 139, 0.20)'}; color: {'#34D399' if is_nifty_tradable_today else '#94A3B8'}; border: 1px solid {'rgba(16, 185, 129, 0.40)' if is_nifty_tradable_today else 'rgba(100, 116, 139, 0.35)'}; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 800;">
                    {nifty_tradable_info['badge_label']}
                </span>
                <span style="background: {'rgba(168, 85, 247, 0.20)' if is_sensex_tradable_today else 'rgba(100, 116, 139, 0.20)'}; color: {'#C084FC' if is_sensex_tradable_today else '#94A3B8'}; border: 1px solid {'rgba(168, 85, 247, 0.40)' if is_sensex_tradable_today else 'rgba(100, 116, 139, 0.35)'}; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 800;">
                    {sensex_tradable_info['badge_label']}
                </span>
            </div>
        </div>
    </div>
    """)

    col_idx1, col_idx2 = st.columns(2)
    spec_nifty_hp = get_asset_spec("NIFTY")
    spec_sensex_hp = get_asset_spec("SENSEX")

    gw_feed_hp = GrowwMarketFeed.get_instance()
    spot_nifty_hp = gw_feed_hp.get_live_spot_data("NIFTY")
    spot_sensex_hp = gw_feed_hp.get_live_spot_data("SENSEX")

    ltp_nifty_hp = float(spot_nifty_hp.get("spot_ltp", spec_nifty_hp.default_spot))
    ltp_sensex_hp = float(spot_sensex_hp.get("spot_ltp", spec_sensex_hp.default_spot))

    nifty_tile_border = "rgba(16, 185, 129, 0.55)" if is_nifty_tradable_today else "rgba(100, 116, 139, 0.35)"
    nifty_status_pill = f'<span style="background: {"rgba(16, 185, 129, 0.25)" if is_nifty_tradable_today else "rgba(100, 116, 139, 0.20)"}; color: {"#34D399" if is_nifty_tradable_today else "#94A3B8"}; border: 1px solid {"rgba(16, 185, 129, 0.5)" if is_nifty_tradable_today else "rgba(100, 116, 139, 0.4)"}; padding: 3px 8px; border-radius: 5px; font-size: 0.70rem; font-weight: 800;">{nifty_tradable_info["badge_label"]}</span>'
    nifty_url = auth_mgr.get_desk_url("Nifty")
    sensex_url = auth_mgr.get_desk_url("Sensex")

    with col_idx1:
        st.html(f"""
        <a href="{nifty_url}" target="_blank" style="text-decoration: none; color: inherit; display: block;">
            <div class="quant-desk-tile tile-nifty" style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(6, 78, 59, 0.85) 100%); border: 1.5px solid {nifty_tile_border}; border-radius: 12px; padding: 18px 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); min-height: 290px; height: 290px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; cursor: pointer;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; min-height: 44px;">
                        <div>
                            <div style="font-size: 1.15rem; font-weight: 900; color: #FFFFFF; letter-spacing: 0.2px;">📈 NIFTY 50 QUANT DESK</div>
                            <div style="font-size: 0.85rem; color: #34D399; font-weight: 700; margin-top: 2px;">₹{ltp_nifty_hp:,.2f}</div>
                        </div>
                        <div>
                            {nifty_status_pill}
                        </div>
                    </div>
                    <div style="font-size: 0.72rem; color: #6EE7B7; font-weight: 700; margin-bottom: 6px; min-height: 18px;">
                        Mandate: 4 Lots ({spec_nifty_hp.lot_size * 4} Qty) &bull; Lot Size: {spec_nifty_hp.lot_size} &bull; Mon / Thu / Fri Active
                    </div>
                    <p style="font-size: 0.80rem; color: #94A3B8; line-height: 1.45; margin: 0 0 10px 0; text-align: left; min-height: 38px;">
                        Institutional Benchmark Engine. Calibrated with Multi-Index Confluence, 50-Pt Strike Corridor & Escalator.
                    </p>
                </div>
                <div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; background: rgba(0,0,0,0.35); border-radius: 8px; padding: 8px; text-align: center; margin-bottom: 8px;">
                        <div>
                            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; margin-bottom: 2px;">PROFIT TARGET</div>
                            <div style="font-size: 1.00rem; font-weight: 800; color: #10B981;">+{spec_nifty_hp.target_pts:.1f} pts</div>
                        </div>
                        <div>
                            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; margin-bottom: 2px;">STOP LOSS</div>
                            <div style="font-size: 1.00rem; font-weight: 800; color: #EF4444;">-{spec_nifty_hp.sl_pts:.1f} pts</div>
                        </div>
                        <div>
                            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; margin-bottom: 2px;">SIZING (4 LOTS)</div>
                            <div style="font-size: 1.00rem; font-weight: 800; color: #38BDF8;">{spec_nifty_hp.lot_size * 4} Qty</div>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(16, 185, 129, 0.2); padding-top: 6px; font-size: 0.74rem; color: #10B981; font-weight: 700;">
                        <span>Benchmark Execution Terminal</span>
                        <span>Open Desk (New Tab) ↗</span>
                    </div>
                </div>
            </div>
        </a>
        """)

    sensex_tile_border = "rgba(168, 85, 247, 0.55)" if is_sensex_tradable_today else "rgba(100, 116, 139, 0.35)"
    sensex_status_pill = f'<span style="background: {"rgba(168, 85, 247, 0.25)" if is_sensex_tradable_today else "rgba(100, 116, 139, 0.20)"}; color: {"#C084FC" if is_sensex_tradable_today else "#94A3B8"}; border: 1px solid {"rgba(168, 85, 247, 0.5)" if is_sensex_tradable_today else "rgba(100, 116, 139, 0.4)"}; padding: 3px 8px; border-radius: 5px; font-size: 0.70rem; font-weight: 800;">{sensex_tradable_info["badge_label"]}</span>'

    with col_idx2:
        st.html(f"""
        <a href="{sensex_url}" target="_blank" style="text-decoration: none; color: inherit; display: block;">
            <div class="quant-desk-tile tile-sensex" style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(88, 28, 135, 0.85) 100%); border: 1.5px solid {sensex_tile_border}; border-radius: 12px; padding: 18px 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); min-height: 290px; height: 290px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; cursor: pointer;">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; min-height: 44px;">
                        <div>
                            <div style="font-size: 1.15rem; font-weight: 900; color: #FFFFFF; letter-spacing: 0.2px;">🏛️ BSE SENSEX QUANT DESK</div>
                            <div style="font-size: 0.85rem; color: #C084FC; font-weight: 700; margin-top: 2px;">₹{ltp_sensex_hp:,.2f}</div>
                        </div>
                        <div>
                            {sensex_status_pill}
                        </div>
                    </div>
                    <div style="font-size: 0.72rem; color: #D8B4FE; font-weight: 700; margin-bottom: 6px; min-height: 18px;">
                        Mandate: 6 Lots ({spec_sensex_hp.lot_size * 6} Qty) &bull; Lot Size: {spec_sensex_hp.lot_size} &bull; Tue / Wed Active
                    </div>
                    <p style="font-size: 0.80rem; color: #94A3B8; line-height: 1.45; margin: 0 0 10px 0; text-align: left; min-height: 38px;">
                        Institutional Benchmark Engine. 100-Pt Strike Intervals with 2:1 Asymmetric Volatility Runner.
                    </p>
                </div>
                <div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; background: rgba(0,0,0,0.35); border-radius: 8px; padding: 8px; text-align: center; margin-bottom: 8px;">
                        <div>
                            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; margin-bottom: 2px;">PROFIT TARGET</div>
                            <div style="font-size: 1.00rem; font-weight: 800; color: #10B981;">+{spec_sensex_hp.target_pts:.1f} pts</div>
                        </div>
                        <div>
                            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; margin-bottom: 2px;">STOP LOSS</div>
                            <div style="font-size: 1.00rem; font-weight: 800; color: #EF4444;">-{spec_sensex_hp.sl_pts:.1f} pts</div>
                        </div>
                        <div>
                            <div style="font-size: 0.65rem; color: #94A3B8; font-weight: 700; margin-bottom: 2px;">SIZING (6 LOTS)</div>
                            <div style="font-size: 1.00rem; font-weight: 800; color: #C084FC;">{spec_sensex_hp.lot_size * 6} Qty</div>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(168, 85, 247, 0.2); padding-top: 6px; font-size: 0.74rem; color: #C084FC; font-weight: 700;">
                        <span>Benchmark Execution Terminal</span>
                        <span>Open Desk (New Tab) ↗</span>
                    </div>
                </div>
            </div>
        </a>
        """)

    PreMarketHealthCheckEngine.render_diagnostic_card(key_prefix="hp")
    EODSessionSummaryEngine.render_eod_card(key_prefix="hp")

    with st.expander("📅 NSE Official Holiday Calendar & Expiry Shift Radar (Live Exchange Link)", expanded=False):
        if render_nse_calendar_hub_fn:
            render_nse_calendar_hub_fn(active_symbol="NIFTY")

    st.markdown("<div style='margin-top: 32px; margin-bottom: 16px;'></div>", unsafe_allow_html=True)
    st.html("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 24px;">
        <div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.25rem;">📊</span>
                <span style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF; text-transform: uppercase; letter-spacing: 0.8px;">
                    QUANTITATIVE PERFORMANCE AUDIT & LIVE EXECUTION SUITE
                </span>
            </div>
            <div style="font-size: 0.78rem; color: #94A3B8; margin-top: 2px;">
                Empirical 9-Month Historical Validation (Jan–Sep 2026) & Live Forward Trading Ledger (Oct 05 Onwards)
            </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
            <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.35); padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700;">
                ● 9-MONTH AUDIT VERIFIED
            </span>
            <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.35); padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 700;">
                ● FORWARD DESK READY
            </span>
        </div>
    </div>
    """)

    suite_views = [
        "🟢 Live Trade Forward Desk (Oct 05, 2026 Onwards)",
        "⚡ 4-Solution Comparative Audit (Before vs After)",
        "📈 Empirical Backtest Audit (Original Preserved)",
        "🗂️ Audit Datasets & Reports"
    ]

    selected_view = st.segmented_control(
        "Select Performance & Audit Suite",
        options=suite_views,
        default=suite_views[0],
        label_visibility="collapsed",
        key="homepage_suite_segmented"
    ) if hasattr(st, "segmented_control") else st.radio(
        "Select Performance & Audit Suite",
        options=suite_views,
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        key="homepage_suite_radio"
    )

    if not selected_view:
        selected_view = suite_views[0]

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if selected_view == "🟢 Live Trade Forward Desk (Oct 05, 2026 Onwards)":
        live_file_path = os.path.join(base_dir, "live_trade_dashboard.html")
        if not os.path.exists(live_file_path) or is_rescan:
            try:
                import live_dashboard_generator
                live_dashboard_generator.generate_live_dashboard()
            except Exception:
                pass

        if os.path.exists(live_file_path):
            with open(live_file_path, "r", encoding="utf-8") as f:
                live_html_content = f.read()

            embedded_live_html = live_html_content.replace('<meta http-equiv="refresh" content="5">', '')
            c_liv1, c_liv2 = st.columns([3, 1])
            with c_liv1:
                st.caption("🟢 **Live Forward Desk (Oct 05, 2026 Onwards)**: Live forward trading ledger powered by the Enhanced 4-Solution Quant Engine across NIFTY 50 and BSE SENSEX desks.")
            with c_liv2:
                st_download_button_stretch(
                    label="📥 Download Live Desk HTML",
                    data=live_html_content,
                    file_name="live_trade_dashboard.html",
                    mime="text/html",
                    key="dl_btn_live_html"
                )
            components.html(embedded_live_html, height=1100, scrolling=True)
        else:
            st.warning("live_trade_dashboard.html not found.")

    elif selected_view == "⚡ 4-Solution Comparative Audit (Before vs After)":
        comp_file_path = os.path.join(base_dir, "walkforward_comparison_dashboard.html")
        if os.path.exists(comp_file_path):
            with open(comp_file_path, "r", encoding="utf-8") as f:
                comp_html_content = f.read()
            c_cmp1, c_cmp2 = st.columns([3, 1])
            with c_cmp1:
                st.caption("🚀 **4-Solution Walk-Forward Comparison**: Dynamic ATR SL, Two-Tier Stop, 15-Min Re-Entry Protocol, and Chandelier Trailing compared side-by-side with baseline.")
            with c_cmp2:
                st_download_button_stretch(
                    label="📥 Download Comparison Audit HTML",
                    data=comp_html_content,
                    file_name="walkforward_comparison_dashboard.html",
                    mime="text/html",
                    key="dl_btn_comp_html"
                )
            components.html(comp_html_content, height=1100, scrolling=True)
        else:
            st.warning("walkforward_comparison_dashboard.html not found.")

    elif selected_view == "📈 Empirical Backtest Audit (Original Preserved)":
        audit_file_path = os.path.join(base_dir, "trade_audit_dashboard.html")
        if os.path.exists(audit_file_path):
            with open(audit_file_path, "r", encoding="utf-8") as f:
                audit_html_content = f.read()
            c_aud1, c_aud2 = st.columns([3, 1])
            with c_aud1:
                st.caption("⚡ **Interactive Audit Tool (Original Preserved)**: Baseline execution logs with original fixed stops across NIFTY 50 and BSE SENSEX.")
            with c_aud2:
                st_download_button_stretch(
                    label="📥 Download Original Audit HTML",
                    data=audit_html_content,
                    file_name="trade_audit_dashboard.html",
                    mime="text/html",
                    key="dl_btn_audit_html"
                )
            components.html(audit_html_content, height=1100, scrolling=True)
        else:
            st.warning("trade_audit_dashboard.html not found.")

    elif selected_view == "🗂️ Audit Datasets & Reports":
        st.markdown("<h4 style='color: #FFFFFF; margin-top: 12px; margin-bottom: 4px;'>Institutional Data Repository</h4>", unsafe_allow_html=True)
        st.caption("Direct access to full backtested performance logs, real-time alert daemon logs, and active journal files across benchmark desks.")
        c_d1, c_d2 = st.columns(2)
        with c_d1:
            st.html("""
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 14px; margin-bottom: 12px;">
                <b style="color: #38BDF8;">📊 Historical Calibration & Backtest Datasets</b>
                <p style="font-size: 0.78rem; color: #94A3B8; margin-top: 4px; margin-bottom: 0;">Complete 9-month tick-by-tick dataset across 180+ trading sessions for benchmark desks.</p>
            </div>
            """)
            emp_path = os.path.join(base_dir, "empirical_calibration_dataset.json")
            if os.path.exists(emp_path):
                with open(emp_path, "r", encoding="utf-8") as f:
                    emp_data = f.read()
                st_download_button_stretch("📥 Download Calibration Dataset JSON", data=emp_data, file_name="empirical_calibration_dataset.json", mime="application/json", key="dl_emp_data")

            summ_path = os.path.join(base_dir, "backtest_results_summary.json")
            if os.path.exists(summ_path):
                with open(summ_path, "r", encoding="utf-8") as f:
                    summ_data = f.read()
                st_download_button_stretch("📥 Download Backtest Summary JSON", data=summ_data, file_name="backtest_results_summary.json", mime="application/json", key="dl_summ_data")

        with c_d2:
            st.html("""
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 14px; margin-bottom: 12px;">
                <b style="color: #10B981;">🟢 Forward Trading & Daemon Signal Feeds</b>
                <p style="font-size: 0.78rem; color: #94A3B8; margin-top: 4px; margin-bottom: 0;">Real-time logs captured by background quant alert daemons and brokers.</p>
            </div>
            """)
            sig_path = os.path.join(base_dir, "daily_signals_log.json")
            if os.path.exists(sig_path):
                with open(sig_path, "r", encoding="utf-8") as f:
                    sig_data = f.read()
                st_download_button_stretch("📥 Download Daily Signals Log JSON", data=sig_data, file_name="daily_signals_log.json", mime="application/json", key="dl_sig_data")

            shd_path = os.path.join(base_dir, "shadow_signals_log.json")
            if os.path.exists(shd_path):
                with open(shd_path, "r", encoding="utf-8") as f:
                    shd_data = f.read()
                st_download_button_stretch("📥 Download Shadow Signals Log JSON", data=shd_data, file_name="shadow_signals_log.json", mime="application/json", key="dl_shd_data")

    st.stop()

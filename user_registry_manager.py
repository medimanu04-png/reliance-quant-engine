"""
user_registry_manager.py
Institutional User Registration & Administrator Approval Registry.
Provides multi-tenant user access management for the Manoj Quant Engine:
1. Self-service mobile registration with cellular SMS OTP verification.
2. Strict administrator approval gatekeeping (Pending -> Approved -> Revoked).
3. Admin dashboard for reviewing, approving, revoking, or deleting users.
4. Real-time Telegram alerts to Super Admin upon new registration submissions.
"""

import os
import json
from datetime import datetime, timedelta
import streamlit as st
from views.ui_components import st_button_stretch, st_form_submit_button_stretch

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except Exception:
    try:
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")
    except Exception:
        from datetime import timezone
        IST = timezone(timedelta(hours=5, minutes=30))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTERED_USERS_FILE = os.path.join(BASE_DIR, "registered_users.json")
TELEGRAM_CONFIG_FILE = os.path.join(BASE_DIR, "telegram_config.json")
SUPER_ADMIN_MOBILE = "8328580784"


def _clean_mobile(mobile_raw: str) -> str:
    """Extracts clean 10-digit mobile number."""
    digits = "".join([c for c in str(mobile_raw) if c.isdigit()])
    return digits[-10:] if len(digits) >= 10 else digits


def load_users() -> dict[str, dict]:
    """Loads all registered users from JSON file."""
    users = {}
    if os.path.exists(REGISTERED_USERS_FILE):
        try:
            with open(REGISTERED_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    users = data.get("users", {})
        except Exception:
            users = {}

    return users



def save_users(users: dict) -> bool:
    """Saves user registry to disk atomically."""
    try:
        data = {
            "version": "1.0",
            "last_updated": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST"),
            "users": users
        }
        temp_file = REGISTERED_USERS_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, REGISTERED_USERS_FILE)
        return True
    except Exception as e:
        print(f"[UserRegistryManager] Save failed: {e}")
        return False


def get_user(mobile_raw: str) -> dict | None:
    """Retrieves user record by mobile number."""
    clean = _clean_mobile(mobile_raw)
    users = load_users()
    return users.get(clean)


def check_mobile_status(mobile_raw: str) -> tuple[str, str, dict | None]:
    """
    Checks if a mobile number is eligible to log in.
    Returns: (status, user_friendly_message, user_record)
    Status can be: 'APPROVED', 'PENDING_APPROVAL', 'REVOKED', 'UNREGISTERED'
    """
    clean = _clean_mobile(mobile_raw)
    if not clean or len(clean) != 10:
        return "INVALID", "Please enter a valid 10-digit mobile number.", None

    users = load_users()
    user = users.get(clean)

    if not user:
        return (
            "UNREGISTERED",
            f"Mobile number +91 {clean} is not registered. Please click 'Register New Account' below to sign up.",
            None
        )

    status = str(user.get("status", "PENDING_APPROVAL")).upper()
    name = user.get("name", "Trader")

    if status == "APPROVED":
        return "APPROVED", f"Welcome back, {name}! Verification OTP dispatched.", user
    elif status == "PENDING_APPROVAL":
        return (
            "PENDING_APPROVAL",
            f"Registration Pending: Account for {name} (+91 {clean}) is awaiting Administrator approval. You can log in once approved by Admin (Manoj).",
            user
        )
    elif status == "REVOKED":
        return (
            "REVOKED",
            f"Access Revoked: Account for {name} (+91 {clean}) has been suspended by Administrator. Contact admin to reactivate.",
            user
        )
    else:
        return "PENDING_APPROVAL", f"Account status '{status}' is not authorized to log in.", user


def register_user(mobile_raw: str = None, name: str = "", country_code: str = "+91", mobile: str = None) -> tuple[bool, str]:
    """
    Registers a new user after mobile OTP verification.
    Sets initial status to 'PENDING_APPROVAL' and dispatches Telegram alert to Admin.
    """
    raw = mobile_raw if mobile_raw is not None else (mobile or "")
    clean = _clean_mobile(raw)
    if len(clean) != 10:
        return False, "Invalid mobile number. Must be 10 digits."

    clean_name = (name or "").strip() or f"Trader {clean[-4:]}"
    cc = country_code if country_code.startswith("+") else f"+{country_code}"

    users = load_users()
    existing = users.get(clean)

    now_str = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")

    if existing:
        current_status = existing.get("status", "PENDING_APPROVAL")
        if current_status == "APPROVED":
            return False, f"Mobile +91 {clean} is already registered and APPROVED. Please log in directly."
        elif current_status == "PENDING_APPROVAL":
            return True, f"Registration for +91 {clean} is already pending administrator approval. Please wait for Admin (Manoj) to approve."
        elif current_status == "REVOKED":
            # Re-apply
            existing["status"] = "PENDING_APPROVAL"
            existing["name"] = clean_name
            existing["reregistered_at"] = now_str
            save_users(users)
            _notify_admin_new_registration(clean, clean_name, is_reapply=True)
            return True, f"Re-application submitted! Your account is now pending administrator review."

    # New registration
    users[clean] = {
        "mobile": clean,
        "country_code": cc,
        "name": clean_name,
        "role": "trader",
        "status": "PENDING_APPROVAL",
        "registered_at": now_str,
        "approved_at": None,
        "approved_by": None,
        "last_login": None
    }
    save_users(users)
    _notify_admin_new_registration(clean, clean_name, is_reapply=False)

    return True, f"Registration submitted successfully! Your account is pending administrator approval."


def approve_user(mobile_raw: str, approved_by: str = "admin") -> tuple[bool, str]:
    """Approves a user registration, granting quant desk access."""
    clean = _clean_mobile(mobile_raw)
    users = load_users()
    if clean not in users:
        return False, f"User +91 {clean} not found in registry."

    user = users[clean]
    user["status"] = "APPROVED"
    user["approved_at"] = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
    user["approved_by"] = approved_by
    save_users(users)

    # Dispatch audit alert
    _notify_admin_user_status_change(clean, user.get("name", "Trader"), "APPROVED", approved_by)
    return True, f"User {user.get('name', 'Trader')} (+91 {clean}) is now APPROVED."


def revoke_user(mobile_raw: str, revoked_by: str = "admin") -> tuple[bool, str]:
    """Suspends / unregisters a user, blocking all future logins."""
    clean = _clean_mobile(mobile_raw)
    users = load_users()
    if clean not in users:
        return False, f"User +91 {clean} not found in registry."

    user = users[clean]
    user["status"] = "REVOKED"
    user["revoked_at"] = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
    user["revoked_by"] = revoked_by
    save_users(users)

    _notify_admin_user_status_change(clean, user.get("name", "Trader"), "REVOKED", revoked_by)
    return True, f"User {user.get('name', 'Trader')} (+91 {clean}) has been UNREGISTERED / REVOKED."


def delete_user(mobile_raw: str) -> tuple[bool, str]:
    """Permanently deletes a user from registry."""
    clean = _clean_mobile(mobile_raw)
    users = load_users()
    if clean not in users:
        return False, f"User +91 {clean} not found in registry."

    user_name = users[clean].get("name", "Trader")
    del users[clean]
    save_users(users)
    return True, f"User {user_name} (+91 {clean}) permanently deleted from registry."


def reject_user(mobile_raw: str, rejected_by: str = "admin") -> tuple[bool, str]:
    """Rejects a pending registration request and removes it from the queue."""
    clean = _clean_mobile(mobile_raw)
    users = load_users()
    if clean not in users:
        return False, f"User +91 {clean} not found in registry."

    user_name = users[clean].get("name", "Trader")
    del users[clean]
    save_users(users)
    _notify_admin_user_status_change(clean, user_name, "REJECTED_AND_REMOVED", rejected_by)
    return True, f"Registration for {user_name} (+91 {clean}) rejected and removed from registry."


def record_user_login(mobile_raw: str):
    """Updates last login timestamp for user."""
    clean = _clean_mobile(mobile_raw)
    users = load_users()
    if clean in users:
        users[clean]["last_login"] = datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
        save_users(users)


def get_user_stats() -> dict:
    """Computes aggregate user metrics for admin dashboard."""
    users = load_users()
    total = len(users)
    approved = sum(1 for u in users.values() if u.get("status") == "APPROVED")
    pending = sum(1 for u in users.values() if u.get("status") == "PENDING_APPROVAL")
    revoked = sum(1 for u in users.values() if u.get("status") == "REVOKED")
    return {
        "total": total,
        "approved": approved,
        "pending": pending,
        "revoked": revoked
    }


def is_admin_user(user_identifier: str = None) -> bool:
    """
    Determines if current user is the dedicated Administrator.
    Strictly restricted to the 'admin' master account.
    All other accounts (including 'manoj' and '8328580784') operate as normal traders.
    """
    ident = str(user_identifier or st.session_state.get("auth_user", "")).strip().lower()
    return ident == "admin"



def _notify_admin_new_registration(mobile: str, name: str, is_reapply: bool = False):
    """Dispatches Telegram notification to Manoj when a new user registers and awaits approval."""
    try:
        if not os.path.exists(TELEGRAM_CONFIG_FILE):
            return
        with open(TELEGRAM_CONFIG_FILE, "r", encoding="utf-8") as f:
            tg_cfg = json.load(f)
        bot_token = tg_cfg.get("bot_token", "").strip()
        chat_id = tg_cfg.get("chat_id", "").strip()
        if not bot_token or not chat_id:
            return

        reapply_tag = "RE-APPLICATION" if is_reapply else "NEW REGISTRATION"
        msg = f"""
🔔 <b>MANOJ QUANT ENGINE // {reapply_tag}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Trader Name:</b> <code>{name}</code>
📱 <b>Mobile Number:</b> <code>+91 {mobile}</code>
🕒 <b>Registered:</b> {datetime.now(IST).strftime('%I:%M:%S %p IST, %d %b %Y')}
⏳ <b>Status:</b> <b>PENDING APPROVAL</b>

⚠️ <i>This user cannot log in until you approve them via your Admin credentials in the terminal.</i>
"""
        from telegram_notifier import TelegramNotifier
        TelegramNotifier.send_message(bot_token, chat_id, msg, is_manual_test=True)
    except Exception:
        pass


def _notify_admin_user_status_change(mobile: str, name: str, new_status: str, operator: str):
    """Dispatches Telegram audit message on status change."""
    try:
        if not os.path.exists(TELEGRAM_CONFIG_FILE):
            return
        with open(TELEGRAM_CONFIG_FILE, "r", encoding="utf-8") as f:
            tg_cfg = json.load(f)
        bot_token = tg_cfg.get("bot_token", "").strip()
        chat_id = tg_cfg.get("chat_id", "").strip()
        if not bot_token or not chat_id:
            return

        icon = "✅" if new_status == "APPROVED" else "⛔"
        msg = f"""
🛡️ <b>MANOJ QUANT TERMINAL // USER ACCESS AUDIT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{icon} <b>User Status Updated:</b> <b>{new_status}</b>
👤 <b>Trader Name:</b> <code>{name}</code>
📱 <b>Mobile Number:</b> <code>+91 {mobile}</code>
👨‍💼 <b>Processed By:</b> <code>{operator}</code>
🕒 <b>Timestamp:</b> {datetime.now(IST).strftime('%I:%M:%S %p IST, %d %b %Y')}
"""
        from telegram_notifier import TelegramNotifier
        TelegramNotifier.send_message(bot_token, chat_id, msg, is_manual_test=True)
    except Exception:
        pass


def render_user_management_panel():
    """
    Renders an institutional User Management & Registration Approval Panel for Admin.
    Includes metric cards, filter tabs (Pending, Approved, All), and approve/revoke/delete actions.
    """
    if not is_admin_user():
        st.error("⛔ Access Denied: Administrator credentials required to manage registered users.")
        return

    stats = get_user_stats()

    st.markdown("### 👥 Registered Users & Registration Approvals")
    st.caption("Institutional User Access Control: Review pending mobile registrations, grant trading access, or unregister accounts.")

    # KPI Metric Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Registered", stats["total"])
    with c2:
        st.metric("✅ Approved Active", stats["approved"])
    with c3:
        st.metric("⏳ Pending Approval", stats["pending"], delta="Action Required" if stats["pending"] > 0 else None)
    with c4:
        st.metric("⛔ Revoked / Blocked", stats["revoked"])

    st.markdown("---")

    users = load_users()
    admin_op = str(st.session_state.get("auth_user", "admin"))

    tab_pending, tab_approved, tab_all = st.tabs([
        f"⏳ Pending Approvals ({stats['pending']})",
        f"✅ Approved Traders ({stats['approved']})",
        f"📋 All Records ({stats['total']})"
    ])

    def _render_user_card(mobile: str, u: dict, key_prefix: str):
        status = str(u.get("status", "PENDING_APPROVAL")).upper()
        name = u.get("name", "Trader")
        reg_time = u.get("registered_at", "--")
        last_login = u.get("last_login", "Never")
        role = str(u.get("role", "trader")).upper()
        is_super = (mobile == SUPER_ADMIN_MOBILE)

        if status == "APPROVED":
            status_badge = '<span style="background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid #10B981; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 800;">APPROVED</span>'
            border_color = "rgba(16, 185, 129, 0.35)"
        elif status == "PENDING_APPROVAL":
            status_badge = '<span style="background: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid #F59E0B; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 800;">PENDING APPROVAL</span>'
            border_color = "rgba(245, 158, 11, 0.45)"
        else:
            status_badge = '<span style="background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid #EF4444; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 800;">REVOKED</span>'
            border_color = "rgba(239, 68, 68, 0.35)"

        role_badge = f'<span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; font-size: 0.68rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">{role}</span>'

        st.html(f"""
        <div style="background: rgba(15, 23, 42, 0.7); border: 1.5px solid {border_color}; border-radius: 10px; padding: 12px 16px; margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.05rem; font-weight: 800; color: #FFFFFF;">👤 {name}</span>
                    {role_badge}
                    {status_badge}
                </div>
                <div style="font-size: 0.95rem; font-weight: 800; color: #38BDF8;">
                    📱 +91 {mobile}
                </div>
            </div>
            <div style="font-size: 0.74rem; color: #94A3B8; margin-top: 6px; display: flex; justify-content: space-between;">
                <span>📅 Registered: <b style="color: #E2E8F0;">{reg_time}</b></span>
                <span>⏱️ Last Login: <b style="color: #E2E8F0;">{last_login}</b></span>
            </div>
        </div>
        """)

        # Action Buttons
        col_act1, col_act2, col_act3, col_spacer = st.columns([1.2, 1.4, 1.0, 2.4])

        with col_act1:
            if status != "APPROVED":
                if st_button_stretch("✅ Approve", key=f"{key_prefix}_app_{mobile}", type="primary"):
                    ok, msg = approve_user(mobile, approved_by=admin_op)
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        with col_act2:
            if status == "APPROVED":
                if st_button_stretch("⛔ Unregister / Revoke", key=f"{key_prefix}_rev_{mobile}"):
                    ok, msg = revoke_user(mobile, revoked_by=admin_op)
                    if ok:
                        st.warning(f"⚠️ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        with col_act3:
            if st_button_stretch("🗑️ Delete", key=f"{key_prefix}_del_{mobile}"):
                ok, msg = delete_user(mobile)
                if ok:
                    st.toast(f"User +91 {mobile} deleted")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    with tab_pending:
        pending_list = [item for item in users.items() if item[1].get("status") == "PENDING_APPROVAL"]
        if not pending_list:
            st.info("🎉 No pending registration requests. All registered users are processed.")
        else:
            st.warning(f"⚠️ {len(pending_list)} user(s) awaiting your approval:")
            for mobile, u in pending_list:
                _render_user_card(mobile, u, key_prefix="pend")

    with tab_approved:
        approved_list = [item for item in users.items() if item[1].get("status") == "APPROVED"]
        if not approved_list:
            st.info("No approved users found.")
        else:
            for mobile, u in approved_list:
                _render_user_card(mobile, u, key_prefix="appr")

    with tab_all:
        for mobile, u in users.items():
            _render_user_card(mobile, u, key_prefix="all")


def render_dedicated_admin_portal():
    """
    Renders dedicated, full-page Administrator Console.
    This page is shown strictly when logged in via 'admin' credentials.
    It provides complete controls to view registered users, approve, reject, unregister, or remove users.
    Completely decoupled from the regular quant trading desk.
    """
    from views.auth_manager import logout_user

    st.markdown("""
    <style>
    /* Center and constrain admin portal container across all viewports */
    .main .block-container,
    [data-testid="block-container"],
    .stMainBlockContainer,
    section.main > div.block-container {
        max-width: 1120px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding-top: 1.8rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }

    /* Tab Bar Container Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background-color: rgba(15, 23, 42, 0.70) !important;
        padding: 6px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        margin-bottom: 18px !important;
    }

    .stTabs [data-baseweb="tab"] {
        height: 40px !important;
        background-color: transparent !important;
        border-radius: 8px !important;
        color: #94A3B8 !important;
        font-size: 0.84rem !important;
        font-weight: 700 !important;
        padding: 0 16px !important;
    }

    .stTabs [aria-selected="true"] {
        background-color: rgba(56, 189, 248, 0.18) !important;
        color: #38BDF8 !important;
        border-bottom: 2px solid #38BDF8 !important;
    }

    /* Search input field */
    [data-testid="stTextInput"] div[data-baseweb="input"] {
        background: rgba(15, 23, 42, 0.75) !important;
        border: 1px solid rgba(56, 189, 248, 0.28) !important;
        border-radius: 10px !important;
    }

    /* Button alignment */
    [data-testid="stButton"] button {
        border-radius: 10px !important;
        font-weight: 800 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Top Header Bar with Vertical Centering
    col_th1, col_th2 = st.columns([4.2, 1.2], vertical_alignment="center")
    with col_th1:
        st.html("""
        <div style="display: flex; align-items: center; gap: 14px;">
            <div style="font-size: 2.2rem; background: rgba(56, 189, 248, 0.12); border: 1.5px solid rgba(56, 189, 248, 0.35); border-radius: 14px; width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">👑</div>
            <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
                    <span style="background: rgba(56, 189, 248, 0.18); border: 1px solid rgba(56, 189, 248, 0.45); color: #38BDF8; font-size: 0.68rem; font-weight: 800; padding: 2px 8px; border-radius: 6px; letter-spacing: 0.8px; text-transform: uppercase;">
                        ADMINISTRATOR CONSOLE
                    </span>
                    <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); color: #34D399; font-size: 0.68rem; font-weight: 700; padding: 2px 8px; border-radius: 6px;">
                        OPERATOR ID: ADMIN
                    </span>
                </div>
                <h1 style="margin: 0; font-size: 1.65rem; font-weight: 900; color: #FFFFFF; letter-spacing: -0.4px; line-height: 1.2;">
                    User Access &amp; Registration Approval Center
                </h1>
                <div style="font-size: 0.82rem; color: #94A3B8; margin-top: 3px;">
                    Review pending mobile registrations, approve or reject trader access, and unregister accounts.
                </div>
            </div>
        </div>
        """)
    with col_th2:
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        if st_button_stretch("🔒 Exit & Logout", key="btn_admin_portal_logout", help="Log out of Administrator Console"):
            logout_user()

    st.markdown("<div style='border-bottom: 1px solid rgba(56, 189, 248, 0.20); margin: 18px 0 22px 0;'></div>", unsafe_allow_html=True)

    stats = get_user_stats()

    # KPI Metric Cards Grid
    pending_border = "rgba(245, 158, 11, 0.50)" if stats["pending"] > 0 else "rgba(56, 189, 248, 0.25)"
    pending_num_color = "#FBBF24" if stats["pending"] > 0 else "#94A3B8"
    pending_sub = f"⚠️ {stats['pending']} Awaiting Decision" if stats["pending"] > 0 else "🎉 No Action Required"
    pending_sub_color = "#F59E0B" if stats["pending"] > 0 else "#64748B"

    st.html(f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 22px;">
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 12px; padding: 16px 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <div style="font-size: 0.76rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px;">
                👥 Total Registered
            </div>
            <div style="font-size: 1.95rem; font-weight: 900; color: #FFFFFF; margin-top: 4px; line-height: 1.1;">
                {stats['total']}
            </div>
            <div style="font-size: 0.70rem; color: #64748B; margin-top: 4px;">All records in registry</div>
        </div>
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 12px; padding: 16px 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <div style="font-size: 0.76rem; font-weight: 700; color: #34D399; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px;">
                ✅ Approved Active
            </div>
            <div style="font-size: 1.95rem; font-weight: 900; color: #34D399; margin-top: 4px; line-height: 1.1;">
                {stats['approved']}
            </div>
            <div style="font-size: 0.70rem; color: #10B981; margin-top: 4px;">Authorized Quant Desk Access</div>
        </div>
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid {pending_border}; border-radius: 12px; padding: 16px 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <div style="font-size: 0.76rem; font-weight: 700; color: {pending_num_color}; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px;">
                ⏳ Pending Approval
            </div>
            <div style="font-size: 1.95rem; font-weight: 900; color: {pending_num_color}; margin-top: 4px; line-height: 1.1;">
                {stats['pending']}
            </div>
            <div style="font-size: 0.70rem; color: {pending_sub_color}; margin-top: 4px;">{pending_sub}</div>
        </div>
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(239, 68, 68, 0.30); border-radius: 12px; padding: 16px 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <div style="font-size: 0.76rem; font-weight: 700; color: #F87171; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px;">
                ⛔ Revoked / Inactive
            </div>
            <div style="font-size: 1.95rem; font-weight: 900; color: #F87171; margin-top: 4px; line-height: 1.1;">
                {stats['revoked']}
            </div>
            <div style="font-size: 0.70rem; color: #EF4444; margin-top: 4px;">Suspended &amp; Unregistered</div>
        </div>
    </div>
    """)

    # Search Bar
    search_query = st.text_input(
        "🔍 Search Trader Records",
        placeholder="Filter by trader name, 10-digit mobile number, or status...",
        key="admin_search_query"
    )

    users = load_users()
    if search_query and search_query.strip():
        sq = search_query.strip().lower()
        users = {m: u for m, u in users.items() if sq in m or sq in u.get("name", "").lower()}

    # Tabs
    t_pending, t_approved, t_revoked, t_all, t_manual = st.tabs([
        f"⏳ Pending Approvals ({stats['pending']})",
        f"✅ Approved Traders ({stats['approved']})",
        f"⛔ Revoked / Unregistered ({stats['revoked']})",
        f"📋 All Records ({len(users)})",
        "➕ Direct Add / Whitelist"
    ])

    def _render_portal_row(mobile: str, u: dict, prefix: str):
        status = str(u.get("status", "PENDING_APPROVAL")).upper()
        name = u.get("name", "Trader")
        reg_time = u.get("registered_at", "--")
        last_login = u.get("last_login", "Never")
        approved_at = u.get("approved_at", "--")
        role = str(u.get("role", "trader")).upper()
        is_super = (mobile == SUPER_ADMIN_MOBILE)

        if status == "APPROVED":
            status_badge = '<span style="background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid #10B981; padding: 2px 8px; border-radius: 10px; font-size: 0.72rem; font-weight: 800;">ACTIVE APPROVED</span>'
            border_c = "rgba(16, 185, 129, 0.35)"
        elif status == "PENDING_APPROVAL":
            status_badge = '<span style="background: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid #F59E0B; padding: 2px 8px; border-radius: 10px; font-size: 0.72rem; font-weight: 800;">AWAITING APPROVAL</span>'
            border_c = "rgba(245, 158, 11, 0.5)"
        else:
            status_badge = '<span style="background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid #EF4444; padding: 2px 8px; border-radius: 10px; font-size: 0.72rem; font-weight: 800;">UNREGISTERED / REVOKED</span>'
            border_c = "rgba(239, 68, 68, 0.35)"

        role_badge = f'<span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; font-size: 0.68rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">{role}</span>'

        st.html(f"""
        <div style="background: rgba(15, 23, 42, 0.75); border: 1.5px solid {border_c}; border-radius: 12px; padding: 14px 18px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.10rem; font-weight: 800; color: #FFFFFF;">👤 {name}</span>
                    {role_badge}
                    {status_badge}
                </div>
                <div style="font-size: 1.05rem; font-weight: 900; color: #38BDF8; font-family: monospace;">
                    📱 +91 {mobile}
                </div>
            </div>
            <div style="font-size: 0.76rem; color: #94A3B8; margin-top: 8px; display: flex; justify-content: space-between; border-top: 1px solid rgba(148, 163, 184, 0.1); padding-top: 6px;">
                <span>📅 Registered: <b style="color: #E2E8F0;">{reg_time}</b></span>
                <span>✅ Approved: <b style="color: #E2E8F0;">{approved_at}</b></span>
                <span>⏱️ Last Login: <b style="color: #E2E8F0;">{last_login}</b></span>
            </div>
        </div>
        """)

        # Action Buttons
        b_c1, b_c2, b_c3, _ = st.columns([1.3, 1.5, 1.2, 2.0])

        with b_c1:
            if status != "APPROVED":
                if st_button_stretch("✅ Approve User", key=f"{prefix}_app_{mobile}", type="primary"):
                    ok, msg = approve_user(mobile, approved_by="admin")
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        with b_c2:
            if status == "PENDING_APPROVAL":
                if st_button_stretch("❌ Reject Request", key=f"{prefix}_rej_{mobile}"):
                    ok, msg = reject_user(mobile, rejected_by="admin")
                    if ok:
                        st.warning(f"⚠️ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
            elif status == "APPROVED":
                if st_button_stretch("⛔ Unregister / Revoke", key=f"{prefix}_rev_{mobile}"):
                    ok, msg = revoke_user(mobile, revoked_by="admin")
                    if ok:
                        st.warning(f"⚠️ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        with b_c3:
            if status != "PENDING_APPROVAL":
                if st_button_stretch("🗑️ Remove User", key=f"{prefix}_del_{mobile}"):
                    ok, msg = delete_user(mobile)
                    if ok:
                        st.toast(f"User +91 {mobile} removed")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    with t_pending:
        pending_users = [item for item in users.items() if item[1].get("status") == "PENDING_APPROVAL"]
        if not pending_users:
            st.html("""
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px dashed rgba(16, 185, 129, 0.4); border-radius: 10px; padding: 18px; text-align: center; color: #34D399; font-weight: 700;">
                🎉 All caught up! No pending registration requests awaiting review.
            </div>
            """)
        else:
            st.warning(f"⚠️ {len(pending_users)} trader registration request(s) awaiting your decision:")
            for m, u in pending_users:
                _render_portal_row(m, u, prefix="portal_pend")

    with t_approved:
        approved_users = [item for item in users.items() if item[1].get("status") == "APPROVED"]
        if not approved_users:
            st.html("""
            <div style="background: rgba(15, 23, 42, 0.5); border: 1px dashed rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 22px; text-align: center; color: #94A3B8; font-size: 0.90rem;">
                ℹ️ No approved traders currently active in registry.
            </div>
            """)
        else:
            for m, u in approved_users:
                _render_portal_row(m, u, prefix="portal_appr")

    with t_revoked:
        revoked_users = [item for item in users.items() if item[1].get("status") == "REVOKED"]
        if not revoked_users:
            st.html("""
            <div style="background: rgba(15, 23, 42, 0.5); border: 1px dashed rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 22px; text-align: center; color: #94A3B8; font-size: 0.90rem;">
                ℹ️ No revoked or suspended traders in registry.
            </div>
            """)
        else:
            for m, u in revoked_users:
                _render_portal_row(m, u, prefix="portal_rev")

    with t_all:
        if not users:
            st.html("""
            <div style="background: rgba(15, 23, 42, 0.5); border: 1px dashed rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 22px; text-align: center; color: #94A3B8; font-size: 0.90rem;">
                ℹ️ Registry is completely clean (0 records). New trader mobile registrations will appear here.
            </div>
            """)
        else:
            for m, u in users.items():
                _render_portal_row(m, u, prefix="portal_all")

    with t_manual:
        st.html("<p style='font-size: 0.82rem; color: #CBD5E1;'>Directly add and pre-approve a trader mobile number without requiring them to wait in pending queue:</p>")
        with st.form("manual_add_trader_form"):
            ca_n, ca_m = st.columns(2)
            with ca_n:
                add_name = st.text_input("👤 Trader Full Name", placeholder="e.g. Vikram Verma")
            with ca_m:
                add_mob = st.text_input("📱 Mobile Number (10 digits)", placeholder="e.g. 9876543210")

            add_submit = st_form_submit_button_stretch("⚡ Add & Pre-Approve Trader", type="primary")
            if add_submit:
                clean_m = _clean_mobile(add_mob)
                if len(clean_m) != 10:
                    st.error("❌ Please enter a valid 10-digit mobile number.")
                elif not add_name or len(add_name.strip()) < 2:
                    st.error("❌ Please enter trader name.")
                else:
                    all_u = load_users()
                    all_u[clean_m] = {
                        "mobile": clean_m,
                        "country_code": "+91",
                        "name": add_name.strip(),
                        "role": "trader",
                        "status": "APPROVED",
                        "registered_at": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST"),
                        "approved_at": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST"),
                        "approved_by": "admin (manual_whitelist)",
                        "last_login": None
                    }
                    save_users(all_u)
                    st.success(f"✅ Trader {add_name} (+91 {clean_m}) has been directly added and APPROVED!")
                    st.rerun()


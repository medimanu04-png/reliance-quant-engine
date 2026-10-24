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
from views.ui_components import st_button_stretch

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
    """Loads all registered users from JSON file, initializing super admin if missing."""
    users = {}
    if os.path.exists(REGISTERED_USERS_FILE):
        try:
            with open(REGISTERED_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    users = data.get("users", {})
        except Exception:
            users = {}

    # Ensure Super Admin always exists and is pre-approved
    if SUPER_ADMIN_MOBILE not in users:
        users[SUPER_ADMIN_MOBILE] = {
            "mobile": SUPER_ADMIN_MOBILE,
            "country_code": "+91",
            "name": "Manoj (Super Admin)",
            "role": "admin",
            "status": "APPROVED",
            "registered_at": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST"),
            "approved_at": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST"),
            "approved_by": "SYSTEM_ROOT",
            "last_login": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
        }
        save_users(users)

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


def register_user(mobile_raw: str, name: str, country_code: str = "+91") -> tuple[bool, str]:
    """
    Registers a new user after mobile OTP verification.
    Sets initial status to 'PENDING_APPROVAL' and dispatches Telegram alert to Admin.
    """
    clean = _clean_mobile(mobile_raw)
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
    if clean == SUPER_ADMIN_MOBILE:
        return False, "Cannot revoke Super Administrator account."

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
    if clean == SUPER_ADMIN_MOBILE:
        return False, "Cannot delete Super Administrator account."

    users = load_users()
    if clean not in users:
        return False, f"User +91 {clean} not found in registry."

    user_name = users[clean].get("name", "Trader")
    del users[clean]
    save_users(users)
    return True, f"User {user_name} (+91 {clean}) permanently deleted from registry."


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
    Determines if current user has administrator privileges.
    Admin accounts:
    - Master key 'admin'
    - Master key 'manoj'
    - Super admin mobile '+91 8328580784' / '8328580784'
    - Any user with role == 'admin' in registered_users.json
    """
    ident = str(user_identifier or st.session_state.get("auth_user", "")).strip().lower()
    if not ident:
        return False

    if ident in ["admin", "manoj"]:
        return True

    clean = _clean_mobile(ident)
    if clean == SUPER_ADMIN_MOBILE:
        return True

    users = load_users()
    user = users.get(clean)
    if user and user.get("role") == "admin":
        return True

    return False


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
            if status == "APPROVED" and not is_super:
                if st_button_stretch("⛔ Unregister / Revoke", key=f"{key_prefix}_rev_{mobile}"):
                    ok, msg = revoke_user(mobile, revoked_by=admin_op)
                    if ok:
                        st.warning(f"⚠️ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        with col_act3:
            if not is_super:
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

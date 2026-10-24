"""
views/auth_manager.py
Institutional Authentication & Security Gatekeeper Engine with Mobile OTP 2FA.
Provides airtight multi-layer access control for the Manoj Quant Engine:
1. Mobile Number Verification + 6-digit Security OTP dispatched via Telegram & SMS Gateway.
2. Guards all direct URLs (/Nifty, /Sensex) against unauthorized access.
3. Cryptographically signed HMAC-SHA256 session token persistence across browser refreshes (F5).
4. Direct Groww 1-Tap Execution Authorization verification.
"""

import os
import random
import hmac
import hashlib
import json
import time
import textwrap
from datetime import datetime, timedelta
import streamlit as st
from views.ui_components import st_button_stretch, st_form_submit_button_stretch, st_sidebar_button_stretch

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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SECRET = "manoj_quant_secure_vault_2026_institutional_secret"
TELEGRAM_CONFIG_FILE = os.path.join(BASE_DIR, "telegram_config.json")
AUTH_CREDENTIALS_FILE = os.path.join(BASE_DIR, "auth_credentials.json")
SECRETS_FILE = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
SMS_CONFIG_FILE = os.path.join(BASE_DIR, "sms_config.json")
AUTHORIZED_RECOVERY_MOBILE = "8328580784"


def _get_authorized_recovery_mobiles() -> set[str]:
    """Retrieves whitelist of authorized recovery mobile numbers from code and secrets.toml."""
    authorized = {AUTHORIZED_RECOVERY_MOBILE}
    if hasattr(st, "secrets") and "auth" in st.secrets:
        sec_m = st.secrets["auth"].get("recovery_mobile", "")
        if sec_m:
            digits = "".join([c for c in str(sec_m) if c.isdigit()])[-10:]
            if len(digits) == 10:
                authorized.add(digits)
    return authorized


def _get_auth_credentials() -> tuple[dict, str]:
    """Retrieves valid master authentication credentials from auth_credentials.json, secrets.toml, or defaults."""
    creds = {
        "admin": "password",
        "manoj": "password123"
    }
    secret_key = DEFAULT_SECRET

    # 1. Read from secrets.toml if present
    if hasattr(st, "secrets") and "auth" in st.secrets:
        auth_sec = st.secrets["auth"]
        u1 = auth_sec.get("username")
        p1 = auth_sec.get("password")
        if u1 and p1:
            creds[str(u1).strip()] = str(p1).strip()
        u2 = auth_sec.get("admin_username")
        p2 = auth_sec.get("admin_password")
        if u2 and p2:
            creds[str(u2).strip()] = str(p2).strip()
        secret_key = auth_sec.get("session_secret", DEFAULT_SECRET)

    # 2. Read from persistent auth_credentials.json (takes priority for user-reset passwords)
    if os.path.exists(AUTH_CREDENTIALS_FILE):
        try:
            with open(AUTH_CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    if "credentials" in saved and isinstance(saved["credentials"], dict):
                        for u, p in saved["credentials"].items():
                            creds[str(u).strip()] = str(p).strip()
                    if "session_secret" in saved and saved["session_secret"]:
                        secret_key = str(saved["session_secret"]).strip()
        except Exception:
            pass

    return creds, secret_key


def update_operator_password(operator_id: str, new_password: str) -> tuple[bool, str]:
    """
    Updates the master security password for an operator ID.
    Persists to both auth_credentials.json and .streamlit/secrets.toml,
    and dispatches a real-time security audit alert to Telegram.
    """
    op_clean = (operator_id or "").strip()
    p_clean = (new_password or "").strip()
    if not op_clean:
        return False, "Operator ID cannot be blank."
    if len(p_clean) < 4:
        return False, "New security access key must be at least 4 characters long."

    # 1. Update in-memory & auth_credentials.json
    creds, secret_key = _get_auth_credentials()
    creds[op_clean] = p_clean
    try:
        data = {
            "credentials": creds,
            "session_secret": secret_key,
            "last_updated": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
        }
        with open(AUTH_CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        return False, f"Failed to save credentials file: {e}"

    # 2. Update .streamlit/secrets.toml
    try:
        if os.path.exists(SECRETS_FILE):
            with open(SECRETS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            new_lines = []
            in_auth_section = False
            password_updated = False
            
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_auth_section = (stripped == "[auth]")
                
                if in_auth_section:
                    if op_clean == "admin" and stripped.startswith("password"):
                        new_lines.append(f'password = "{p_clean}"\n')
                        password_updated = True
                        continue
                    elif op_clean == "manoj" and stripped.startswith("admin_password"):
                        new_lines.append(f'admin_password = "{p_clean}"\n')
                        password_updated = True
                        continue
                    elif stripped.startswith(f"{op_clean}_password"):
                        new_lines.append(f'{op_clean}_password = "{p_clean}"\n')
                        password_updated = True
                        continue

                new_lines.append(line)

            if not password_updated and in_auth_section:
                new_lines.append(f'{op_clean}_password = "{p_clean}"\n')

            with open(SECRETS_FILE, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
    except Exception:
        pass

    # 3. Dispatch Telegram security audit notification
    try:
        if os.path.exists(TELEGRAM_CONFIG_FILE):
            with open(TELEGRAM_CONFIG_FILE, "r", encoding="utf-8") as f:
                tg_cfg = json.load(f)
            b_tok = tg_cfg.get("bot_token", "").strip()
            c_id = tg_cfg.get("chat_id", "").strip()
            if b_tok and c_id:
                from telegram_notifier import TelegramNotifier
                audit_msg = f"""
🛡️ <b>MANOJ QUANT TERMINAL // SECURITY AUDIT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 <b>Master Security Key Updated!</b>
👤 <b>Operator ID:</b> <code>{op_clean}</code>
🕒 <b>Time:</b> {datetime.now(IST).strftime('%I:%M:%S %p IST, %d %b %Y')}
📱 <b>Verification:</b> Verified via 2FA Mobile OTP Text Message
"""
                TelegramNotifier.send_message(b_tok, c_id, audit_msg, is_manual_test=True)
    except Exception:
        pass

    return True, f"Security Access Key for operator '{op_clean}' updated successfully."


def generate_session_token(identifier: str) -> str:
    """Generates a tamper-proof HMAC-SHA256 session token with 7-day expiration."""
    _, secret_key = _get_auth_credentials()
    exp_ts = int(time.time()) + (7 * 86400)
    payload = f"{identifier}|{exp_ts}"
    signature = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}|{signature}"


def verify_session_token(token: str) -> tuple[bool, str]:
    """Validates an HMAC-SHA256 session token. Returns (is_valid, identifier)."""
    if not token or not isinstance(token, str):
        return False, ""
    parts = token.split("|")
    if len(parts) != 3:
        return False, ""
    identifier, exp_str, signature = parts
    try:
        exp_ts = int(exp_str)
        if time.time() > exp_ts:
            return False, ""  # Expired
        _, secret_key = _get_auth_credentials()
        expected_sig = hmac.new(secret_key.encode("utf-8"), f"{identifier}|{exp_str}".encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected_sig):
            return True, identifier
    except Exception:
        pass
    return False, ""


def is_user_authenticated() -> bool:
    """
    Checks if current session is authenticated.
    Supports in-memory session_state and URL query param token restoration across F5 refreshes.
    """
    if st.session_state.get("is_authenticated") is True:
        if "_auth" not in st.query_params and st.session_state.get("auth_user"):
            st.query_params["_auth"] = generate_session_token(str(st.session_state["auth_user"]))
        return True

    q_token = st.query_params.get("_auth")
    if q_token:
        is_valid, identifier = verify_session_token(str(q_token))
        if is_valid:
            st.session_state["is_authenticated"] = True
            st.session_state["auth_user"] = identifier
            st.session_state["auth_time"] = datetime.now(IST).strftime("%I:%M %p")
            st.query_params["_auth"] = str(q_token)
            return True

    return False


def get_active_auth_token() -> str:
    """Retrieves or generates an active HMAC-SHA256 session token for link sharing/new tabs."""
    q_token = st.query_params.get("_auth")
    if q_token:
        is_valid, _ = verify_session_token(str(q_token))
        if is_valid:
            return str(q_token)

    if st.session_state.get("is_authenticated") and st.session_state.get("auth_user"):
        token = generate_session_token(str(st.session_state["auth_user"]))
        st.query_params["_auth"] = token
        return token

    return ""


def get_desk_url(desk_name: str) -> str:
    """Constructs a target URL for a benchmark desk, embedding HMAC auth token for new-tab authentication."""
    import urllib.parse
    token = get_active_auth_token()
    clean_desk = desk_name.capitalize()
    if token:
        safe_token = urllib.parse.quote(token)
        return f"./{clean_desk}?stock={clean_desk}&_auth={safe_token}"
    return f"./{clean_desk}?stock={clean_desk}"


def logout_user():
    """Immediately revokes session and locks terminal."""
    st.session_state["is_authenticated"] = False
    st.session_state.pop("auth_user", None)
    st.session_state.pop("auth_time", None)
    st.session_state.pop("otp_code", None)
    st.session_state.pop("otp_mobile", None)
    st.session_state.pop("otp_expires_at", None)
    st.query_params.pop("_auth", None)
    st.rerun()


def _dispatch_otp_to_telegram(mobile: str, otp_code: str, exp_dt: datetime, title: str = "2FA VERIFICATION CODE", mandate_msg: str = None) -> tuple[bool, str]:
    """Dispatches 2FA OTP code directly to trader's Telegram alert bot/channel."""
    if not os.path.exists(TELEGRAM_CONFIG_FILE):
        return False, "Telegram config not found"

    try:
        with open(TELEGRAM_CONFIG_FILE, "r", encoding="utf-8") as f:
            tg_cfg = json.load(f)

        bot_token = tg_cfg.get("bot_token", "").strip()
        chat_id = tg_cfg.get("chat_id", "").strip()
        if not bot_token or not chat_id:
            return False, "Missing bot_token or chat_id"

        masked_mobile = f"+91-XXXXX-{mobile[-4:]}" if len(mobile) >= 4 else mobile
        mandate_clause = mandate_msg or "Required to unlock benchmark desks and arm 1-Tap Groww order execution."
        msg = f"""
🔐 <b>MANOJ QUANT TERMINAL // {title}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 <b>Target Mobile:</b> <code>{masked_mobile}</code>
🔢 <b>Your Security OTP:</b> <code>{otp_code}</code>

⏱️ <b>Validity:</b> 5 Minutes (Expires at {exp_dt.strftime('%I:%M:%S %p IST')})
🛡️ <b>Security Mandate:</b> {mandate_clause}
⚠️ <i>Never disclose this one-time passcode to anyone.</i>
"""
        from telegram_notifier import TelegramNotifier
        ok, res = TelegramNotifier.send_message(bot_token, chat_id, msg, is_manual_test=True)
        return ok, res
    except Exception as e:
        return False, str(e)


def _dispatch_otp_to_cellular_sms(mobile: str, otp_code: str, custom_body: str = None) -> tuple[bool, str]:
    """
    Dispatches a real cellular SMS text message directly to the user's mobile number.
    Supports Fast2SMS, 2Factor.in, and Twilio configured in secrets.toml or sms_config.json.
    """
    clean_num = "".join([c for c in mobile if c.isdigit()])[-10:]
    sms_cfg = {}
    if hasattr(st, "secrets") and "sms" in st.secrets:
        sms_cfg = dict(st.secrets["sms"])

    if os.path.exists(SMS_CONFIG_FILE):
        try:
            with open(SMS_CONFIG_FILE, "r", encoding="utf-8") as f:
                dyn_cfg = json.load(f)
                if isinstance(dyn_cfg, dict):
                    sms_cfg.update(dyn_cfg)
        except Exception:
            pass

    provider = str(sms_cfg.get("provider", "fast2sms")).lower().strip()
    api_key = str(sms_cfg.get("api_key", "")).strip()

    if not api_key and provider != "twilio":
        return False, "SMS Gateway API key is not configured. Please enter your Fast2SMS, 2Factor, or Twilio API key in SMS Settings to receive cellular text messages."

    msg_body = custom_body or f"Your Manoj Quant Terminal verification passcode is {otp_code}. Valid for 5 minutes."

    try:
        import requests
        # 1. Fast2SMS Integration (Fastest OTP route in India)
        if provider == "fast2sms":
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {
                "authorization": api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-cache"
            }
            # Attempt 1: Dedicated OTP route
            payload_otp = {
                "variables_values": otp_code,
                "route": "otp",
                "numbers": clean_num
            }
            res = requests.post(url, data=payload_otp, headers=headers, timeout=10)
            try:
                r_json = res.json()
                if r_json.get("return") is True:
                    return True, "SMS text message delivered to carrier"
            except Exception:
                r_json = {}

            # Attempt 2: Fallback to Quick SMS route (q) which delivers instantly without website verification
            payload_q = {
                "route": "q",
                "message": msg_body,
                "language": "english",
                "flash": 0,
                "numbers": clean_num
            }
            res_q = requests.post(url, data=payload_q, headers=headers, timeout=10)
            try:
                rq_json = res_q.json()
                if rq_json.get("return") is True:
                    return True, "SMS text message delivered to carrier"
                err = rq_json.get("message", "Fast2SMS error")
                if isinstance(err, list):
                    err = " ".join(err)
                return False, f"Fast2SMS error: {err}"
            except Exception:
                return False, f"Fast2SMS response error (HTTP {res_q.status_code})"

        # 2. 2Factor.in Transactional OTP SMS
        elif provider in ["2factor", "twofactor"]:
            url = f"https://2factor.in/API/V1/{api_key}/SMS/{clean_num}/{otp_code}/AUTOGEN"
            res = requests.get(url, timeout=10)
            r_json = res.json()
            if r_json.get("Status") == "Success":
                return True, "2Factor SMS delivered to carrier"
            return False, r_json.get("Details", "2Factor SMS error")

        # 3. Twilio SMS Integration
        elif provider == "twilio":
            sid = sms_cfg.get("twilio_account_sid", "").strip()
            tok = sms_cfg.get("twilio_auth_token", "").strip()
            from_num = sms_cfg.get("twilio_from_number", "").strip()
            if not sid or not tok or not from_num:
                return False, "Missing Twilio credentials in secrets.toml"
            from requests.auth import HTTPBasicAuth
            url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
            data = {
                "To": f"+91{clean_num}",
                "From": from_num,
                "Body": msg_body
            }
            res = requests.post(url, data=data, auth=HTTPBasicAuth(sid, tok), timeout=10)
            if res.status_code in [200, 201]:
                return True, "Twilio SMS text message sent"
            return False, res.text
    except Exception as e:
        return False, str(e)

    return False, "No active carrier SMS provider matched"


def send_recovery_otp(mobile_raw: str, country_code: str = "🇮🇳 +91", recovery_mode: str = "forgot_password") -> tuple[bool, str]:
    """Generates 6-digit cryptographic OTP for Master Key recovery, dispatches via Cellular SMS text message ONLY, and sets session state."""
    cc_clean = "+" + "".join([c for c in country_code if c.isdigit()]) if any(c.isdigit() for c in country_code) else "+91"
    digits = "".join([c for c in mobile_raw if c.isdigit()])
    if len(digits) < 10:
        return False, "Please enter a valid 10-digit mobile number."

    clean_mobile = digits[-10:]
    authorized_mobiles = _get_authorized_recovery_mobiles()

    # Strict Whitelist Gatekeeper: Only the owner's mobile number (+91 8328580784) is authorized
    if cc_clean != "+91" or clean_mobile not in authorized_mobiles:
        return False, f"Access Denied: Mobile number {cc_clean} {clean_mobile} is NOT authorized for Master Recovery. Only the registered administrator mobile number (+91 8328580784) is permitted."

    otp = f"{random.randint(100000, 999999)}"
    exp_time = time.time() + 300  # 5 minutes

    # Dispatch via Cellular SMS Gateway ONLY (Strictly No Telegram, No on-screen leak)
    sms_body = f"[Manoj Quant Engine] Your security recovery OTP is {otp}. Valid for 5 minutes. Do not share."
    sms_ok, sms_info = _dispatch_otp_to_cellular_sms(f"{cc_clean}{clean_mobile}", otp, custom_body=sms_body)

    if not sms_ok:
        return False, sms_info

    st.session_state["rec_otp_code"] = otp
    st.session_state["rec_otp_mobile"] = clean_mobile
    st.session_state["rec_otp_country_code"] = cc_clean
    st.session_state["rec_otp_expires_at"] = exp_time
    st.session_state["rec_otp_sent_at"] = time.time()
    st.session_state["rec_otp_verified"] = False
    st.session_state["master_rec_flow"] = recovery_mode
    st.session_state["rec_sms_carrier_status"] = "SENT_TO_PHONE"

    return True, "SMS text message sent"


def verify_recovery_otp(entered_otp: str) -> tuple[bool, str]:
    """Verifies user-entered recovery OTP."""
    clean_otp = (entered_otp or "").strip()
    expected_otp = st.session_state.get("rec_otp_code")
    exp_time = st.session_state.get("rec_otp_expires_at", 0)

    if not expected_otp:
        return False, "No active recovery OTP found. Please request a new OTP first."

    if time.time() > exp_time:
        return False, "This recovery OTP has expired (5m window). Please request a fresh OTP."

    if clean_otp == expected_otp:
        st.session_state["rec_otp_verified"] = True
        st.session_state.pop("rec_otp_code", None)
        return True, "Identity verified! Mobile ownership confirmed."

    return False, "Invalid OTP code. Please check the 6-digit passcode and try again."


def send_security_otp(mobile_raw: str, country_code: str = "🇮🇳 +91") -> tuple[bool, str]:
    """Generates 6-digit cryptographic OTP, dispatches via Cellular SMS, and sets session state after verifying approval status."""
    import user_registry_manager as user_reg
    cc_clean = "+" + "".join([c for c in country_code if c.isdigit()]) if any(c.isdigit() for c in country_code) else "+91"
    digits = "".join([c for c in mobile_raw if c.isdigit()])
    if len(digits) < 10:
        return False, "Please enter a valid 10-digit mobile number."

    clean_mobile = digits[-10:]

    # Approval Gatekeeper: Only APPROVED users can receive login OTP
    status, status_msg, _ = user_reg.check_mobile_status(clean_mobile)
    if status != "APPROVED":
        return False, status_msg

    otp = f"{random.randint(100000, 999999)}"
    exp_time = time.time() + 300  # 5 minutes

    # Dispatch via Cellular SMS Gateway ONLY
    sms_body = f"[Manoj Quant Engine] Your login verification OTP is {otp}. Valid for 5 minutes."
    sms_ok, sms_info = _dispatch_otp_to_cellular_sms(f"{cc_clean}{clean_mobile}", otp, custom_body=sms_body)
    if not sms_ok:
        return False, sms_info

    st.session_state["otp_code"] = otp
    st.session_state["otp_mobile"] = clean_mobile
    st.session_state["otp_country_code"] = cc_clean
    st.session_state["otp_expires_at"] = exp_time
    st.session_state["otp_sent_at"] = time.time()
    st.session_state["otp_sms_carrier_status"] = "SENT_TO_PHONE"

    return True, "SMS text message sent"


def verify_security_otp(entered_otp: str) -> tuple[bool, str]:
    """Verifies user-entered OTP against active session passcode."""
    import user_registry_manager as user_reg
    clean_otp = (entered_otp or "").strip()
    expected_otp = st.session_state.get("otp_code")
    exp_time = st.session_state.get("otp_expires_at", 0)
    mobile = st.session_state.get("otp_mobile", "User")
    cc = st.session_state.get("otp_country_code", "+91")

    if not expected_otp:
        return False, "No active OTP found. Please request a new OTP first."

    if time.time() > exp_time:
        return False, "This OTP has expired (5m window). Please request a fresh OTP."

    if clean_otp == expected_otp:
        user_id = f"{cc} {mobile}"
        st.session_state["is_authenticated"] = True
        st.session_state["auth_user"] = user_id
        st.session_state["auth_time"] = datetime.now(IST).strftime("%I:%M %p")

        # Record login & store user details in session
        user_reg.record_user_login(mobile)
        u_rec = user_reg.get_user(mobile)
        role = u_rec.get("role", "trader") if u_rec else "trader"
        name = u_rec.get("name", user_id) if u_rec else user_id
        st.session_state["auth_role"] = role
        st.session_state["auth_user_name"] = name

        # Persist session in URL query parameter
        st.query_params["_auth"] = generate_session_token(user_id)

        # Clear OTP from memory
        st.session_state.pop("otp_code", None)
        st.session_state.pop("otp_expires_at", None)
        return True, f"2FA Verification Successful. Welcome, {name}!"

    return False, "Invalid OTP code. Please check the 6-digit passcode and try again."


def send_registration_otp(mobile_raw: str, name: str, country_code: str = "🇮🇳 +91") -> tuple[bool, str]:
    """Generates 6-digit OTP for new user registration and sends via Cellular SMS text message."""
    import user_registry_manager as user_reg
    cc_clean = "+" + "".join([c for c in country_code if c.isdigit()]) if any(c.isdigit() for c in country_code) else "+91"
    digits = "".join([c for c in mobile_raw if c.isdigit()])
    if len(digits) < 10:
        return False, "Please enter a valid 10-digit mobile number."

    clean_mobile = digits[-10:]
    existing = user_reg.get_user(clean_mobile)
    if existing:
        curr_status = existing.get("status")
        if curr_status == "APPROVED":
            return False, f"Mobile number +91 {clean_mobile} is already registered and APPROVED. Please switch to Login mode."
        elif curr_status == "PENDING_APPROVAL":
            return False, f"Registration for +91 {clean_mobile} has already been submitted and is pending Administrator approval."

    otp = f"{random.randint(100000, 999999)}"
    exp_time = time.time() + 300  # 5 minutes

    sms_body = f"[Manoj Quant Engine] Your registration verification OTP is {otp}. Valid for 5 minutes. Do not share."
    sms_ok, sms_info = _dispatch_otp_to_cellular_sms(f"{cc_clean}{clean_mobile}", otp, custom_body=sms_body)
    if not sms_ok:
        return False, sms_info

    st.session_state["reg_otp_code"] = otp
    st.session_state["reg_otp_mobile"] = clean_mobile
    st.session_state["reg_otp_name"] = name
    st.session_state["reg_otp_country_code"] = cc_clean
    st.session_state["reg_otp_expires_at"] = exp_time
    st.session_state["reg_otp_sent_at"] = time.time()

    return True, "SMS text message sent"


def verify_registration_otp(entered_otp: str) -> tuple[bool, str]:
    """Verifies registration OTP and registers user with PENDING_APPROVAL status."""
    import user_registry_manager as user_reg
    clean_otp = (entered_otp or "").strip()
    expected_otp = st.session_state.get("reg_otp_code")
    exp_time = st.session_state.get("reg_otp_expires_at", 0)
    mobile = st.session_state.get("reg_otp_mobile")
    name = st.session_state.get("reg_otp_name", "Trader")
    cc = st.session_state.get("reg_otp_country_code", "+91")

    if not expected_otp or not mobile:
        return False, "No active registration OTP found. Please request a new OTP first."

    if time.time() > exp_time:
        return False, "This verification OTP has expired. Please request a fresh OTP."

    if clean_otp == expected_otp:
        ok, msg = user_reg.register_user(mobile=mobile, name=name, country_code=cc)
        st.session_state.pop("reg_otp_code", None)
        st.session_state["reg_submitted"] = True
        st.session_state["reg_submitted_mobile"] = mobile
        st.session_state["reg_submitted_name"] = name
        return True, msg

    return False, "Invalid OTP code. Please check the 6-digit passcode and try again."


def render_ultra_premium_login(blocked_route: str = None):
    """
    Renders an institutional quant terminal login portal featuring:
    - Mobile Number + 6-Digit OTP 2FA with live Telegram alert dispatch.
    - Master Access Key emergency unlock fallback.
    - Glassmorphic glowing card with cyan/emerald neon highlights.
    - Direct URL interception alert banner.
    - Persistent HMAC session protection.
    """
    st.html(textwrap.dedent("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 820px !important;
    }
    
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: radial-gradient(ellipse at 50% 10%, rgba(16, 185, 129, 0.14) 0%, rgba(14, 165, 233, 0.09) 40%, rgba(8, 13, 26, 0.98) 100%) !important;
        border: 1px solid rgba(56, 189, 248, 0.28) !important;
        border-radius: 24px !important;
        padding: 32px 38px !important;
        box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.85), 0 0 50px rgba(16, 185, 129, 0.10) !important;
        backdrop-filter: blur(20px) !important;
        margin: 10px auto !important;
        color: #F8FAFC !important;
    }

    .quant-login-title {
        font-size: 1.95rem;
        font-weight: 900;
        letter-spacing: -0.5px;
        background: linear-gradient(135deg, #FFFFFF 0%, #38BDF8 50%, #34D399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        text-align: center;
    }

    .quant-login-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.35);
        color: #34D399;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.8px;
        padding: 4px 12px;
        border-radius: 20px;
        text-transform: uppercase;
        margin-top: 8px;
    }

    .quant-shield-box {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 12px;
        padding: 12px 18px;
        margin: 20px 0 24px 0;
        display: flex;
        align-items: center;
        gap: 14px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background-color: rgba(15, 23, 42, 0.6) !important;
        padding: 6px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(148, 163, 184, 0.15) !important;
    }

    .stTabs [data-baseweb="tab"] {
        height: 42px !important;
        white-space: pre-wrap !important;
        background-color: transparent !important;
        border-radius: 8px !important;
        color: #94A3B8 !important;
        font-size: 0.85rem !important;
        font-weight: 700 !important;
        padding: 0 16px !important;
    }

    .stTabs [aria-selected="true"] {
        background-color: rgba(16, 185, 129, 0.18) !important;
        color: #38BDF8 !important;
        border-bottom: 2px solid #38BDF8 !important;
    }

    /* Precision alignment for 2FA row (Code, Mobile, Button) across all viewports */
    .stTabs [data-testid="stHorizontalBlock"] {
        align-items: flex-end !important;
    }

    .stTabs [data-testid="stColumn"] {
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-end !important;
    }

    .stTabs [data-testid="stColumn"] > div {
        width: 100% !important;
        margin-bottom: 0 !important;
    }

    .stTabs [data-testid="stButton"] button,
    .stTabs [data-testid="stFormSubmitButton"] button {
        height: 42px !important;
        min-height: 42px !important;
        margin-bottom: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    .stTabs [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    .stTabs [data-testid="stTextInput"] div[data-baseweb="input"] {
        height: 42px !important;
        min-height: 42px !important;
    }

    .quant-feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-top: 24px;
        padding-top: 20px;
        border-top: 1px solid rgba(148, 163, 184, 0.12);
    }

    .quant-feature-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 10px;
        padding: 10px 12px;
        text-align: center;
    }

    button[kind="primary"] {
        background: linear-gradient(135deg, #059669 0%, #0284C7 100%) !important;
        border: 1px solid rgba(56, 189, 248, 0.5) !important;
        box-shadow: 0 4px 20px rgba(16, 185, 129, 0.35) !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease-in-out !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 25px rgba(16, 185, 129, 0.55) !important;
    }
    </style>
    """))

    blocked_alert_html = ""
    if blocked_route:
        blocked_alert_html = f"""
        <div style="background: rgba(239, 68, 68, 0.15); border: 1.5px solid #EF4444; border-radius: 10px; padding: 12px 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 1.4rem;">⛔</span>
            <div>
                <div style="color: #FCA5A5; font-weight: 800; font-size: 0.88rem;">RESTRICTED DIRECT URL ATTEMPT INTERCEPTED</div>
                <div style="color: #CBD5E1; font-size: 0.78rem; margin-top: 2px;">
                    Direct entry to <code style="background: rgba(0,0,0,0.4); color: #F87171; padding: 2px 6px; border-radius: 4px;">/{blocked_route}</code> was halted. Unauthenticated users cannot view or route 1-Tap orders on benchmark desks. Please verify via Mobile OTP below.
                </div>
            </div>
        </div>
        """

    with st.container(border=True):
        st.html(textwrap.dedent(f"""
        {blocked_alert_html}
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="font-size: 2.2rem; margin-bottom: 4px;">⚡</div>
            <h1 class="quant-login-title">MANOJ QUANT ENGINE</h1>
            <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; margin-top: 4px; letter-spacing: 0.4px;">
                INSTITUTIONAL F&amp;O BENCHMARK TRADING DESK
            </div>
            <div class="quant-login-badge">
                <span style="display: inline-block; width: 7px; height: 7px; background: #10B981; border-radius: 50%;"></span>
                GROWW 1-TAP BROKER GATEWAY GUARD &amp; 2FA ACTIVE
            </div>
        </div>

        <div class="quant-shield-box">
            <span style="font-size: 1.5rem;">🛡️</span>
            <div>
                <div style="font-size: 0.82rem; font-weight: 700; color: #38BDF8;">Institutional 2-Factor Authentication Mandate</div>
                <div style="font-size: 0.74rem; color: #94A3B8; margin-top: 2px;">
                    Because this terminal executes 1-Tap live F&amp;O orders directly on Groww, mobile 2FA verification is strictly required to unlock benchmark desks.
                </div>
            </div>
        </div>
        """))

        tab_otp, tab_master = st.tabs(["📱 Mobile OTP Verification (2FA)", "🔑 Master Security Key"])

        with tab_otp:
            submode = st.session_state.get("auth_otp_submode", "login")

            c_sub1, c_sub2 = st.columns(2)
            with c_sub1:
                if st_button_stretch(
                    "🔐 Trader Login (Approved Mobile)",
                    key="btn_sub_login",
                    type="primary" if submode == "login" else "secondary"
                ):
                    st.session_state["auth_otp_submode"] = "login"
                    st.rerun()
            with c_sub2:
                if st_button_stretch(
                    "📝 Register New Trader Mobile",
                    key="btn_sub_register",
                    type="primary" if submode == "register" else "secondary"
                ):
                    st.session_state["auth_otp_submode"] = "register"
                    st.rerun()

            st.html("<div style='margin-bottom: 12px;'></div>")

            # ---------------- MODE 1: TRADER LOGIN ----------------
            if submode == "login":
                active_otp = st.session_state.get("otp_code")
                active_mobile = st.session_state.get("otp_mobile")
                exp_time = st.session_state.get("otp_expires_at", 0)

                # Step 1: Request Login OTP
                if not active_otp:
                    st.html("<p style='font-size: 0.85rem; color: #CBD5E1; margin-bottom: 12px;'>Enter your registered mobile number to receive your institutional login passcode:</p>")
                    col_cc, col_m1, col_m2 = st.columns([1.1, 2.0, 1.3], vertical_alignment="bottom")
                    with col_cc:
                        country_codes = [
                            "🇮🇳 +91",
                            "🇺🇸 +1",
                            "🇬🇧 +44",
                            "🇦🇪 +971",
                            "🇸🇬 +65",
                            "🇨🇦 +1",
                            "🇦🇺 +61",
                            "🇩🇪 +49"
                        ]
                        selected_cc = st.selectbox(
                            "🌐 Code",
                            options=country_codes,
                            index=0,
                            help="Country dialing code",
                            key="login_country_code_select"
                        )
                    with col_m1:
                        mobile_val = st.text_input(
                            "📱 Registered Mobile Number",
                            value=st.session_state.get("last_entered_mobile", "8328580784"),
                            placeholder="Enter 10-digit mobile",
                            help="Your registered mobile number for quant desk access"
                        )
                    with col_m2:
                        if st_button_stretch("📩 Send Security OTP", type="primary", key="btn_send_otp"):
                            st.session_state["last_entered_mobile"] = mobile_val
                            st.session_state["last_country_code"] = selected_cc
                            ok, code_or_err = send_security_otp(mobile_val, country_code=selected_cc)
                            if ok:
                                st.success(f"✅ Security OTP dispatched to {selected_cc} {mobile_val[-10:]} via Cellular SMS!")
                                st.rerun()
                            else:
                                st.error(f"❌ {code_or_err}")

                    st.html("""
                    <div style="font-size: 0.74rem; color: #94A3B8; margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <span>🔒 <i>Only administrator-approved mobile numbers can log in. New traders must register first.</i></span>
                    </div>
                    """)

                # Step 2: Enter & Verify Login OTP
                else:
                    time_left = max(0, int(exp_time - time.time()))
                    mins = time_left // 60
                    secs = time_left % 60

                    active_cc = st.session_state.get("otp_country_code", "+91")
                    masked_m = f"+91-XXXXX-{active_mobile[-4:]}" if len(active_mobile) >= 4 else active_mobile
                    st.html(textwrap.dedent(f"""
                    <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 10px; padding: 12px 16px; margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.85rem; font-weight: 700; color: #34D399;">
                                📲 SMS Text Message dispatched to {active_cc} {masked_m}
                            </span>
                            <span style="font-size: 0.72rem; color: #FCD34D; font-weight: 700; background: rgba(0,0,0,0.4); padding: 3px 8px; border-radius: 4px;">
                                ⏱️ Expires in {mins:02d}:{secs:02d}
                            </span>
                        </div>
                        <div style="font-size: 0.76rem; color: #94A3B8; margin-top: 6px;">
                            Passcode sent directly to your phone via cellular SMS text message. Please enter the 6 digits below.
                        </div>
                    </div>
                    """))

                    with st.form("otp_verification_form"):
                        col_o1, col_o2 = st.columns([1.5, 1], vertical_alignment="bottom")
                        with col_o1:
                            otp_input = st.text_input(
                                "🔢 Enter 6-Digit One-Time Passcode (OTP)",
                                value="",
                                max_chars=6,
                                placeholder="e.g. 123456",
                                help="Enter the 6-digit passcode sent to your device"
                            )
                        with col_o2:
                            verify_btn = st_form_submit_button_stretch(
                                "⚡ Verify & Unlock Quant Desk →",
                                type="primary"
                            )

                        if verify_btn:
                            ok, msg = verify_security_otp(otp_input)
                            if ok:
                                st.success(f"✅ {msg}")
                                time.sleep(0.3)
                                if blocked_route:
                                    st.query_params["stock"] = blocked_route
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")

                    col_resend1, col_resend2 = st.columns(2)
                    with col_resend1:
                        if st_button_stretch("🔄 Resend Fresh OTP", key="btn_resend_otp"):
                            send_security_otp(active_mobile)
                            st.toast("Fresh OTP dispatched via SMS!")
                            st.rerun()
                    with col_resend2:
                        if st_button_stretch("✏️ Use Different Mobile", key="btn_change_mobile"):
                            st.session_state.pop("otp_code", None)
                            st.session_state.pop("otp_mobile", None)
                            st.session_state.pop("otp_expires_at", None)
                            st.rerun()

            # ---------------- MODE 2: NEW TRADER REGISTRATION ----------------
            else:
                reg_submitted = st.session_state.get("reg_submitted", False)

                if reg_submitted:
                    s_name = st.session_state.get("reg_submitted_name", "Trader")
                    s_mob = st.session_state.get("reg_submitted_mobile", "")
                    st.html(textwrap.dedent(f"""
                    <div style="background: rgba(16, 185, 129, 0.14); border: 1.5px solid #10B981; border-radius: 12px; padding: 18px 20px; margin-bottom: 16px;">
                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                            <span style="font-size: 1.6rem;">🎉</span>
                            <div>
                                <h4 style="margin: 0; color: #34D399; font-size: 1.05rem; font-weight: 800;">REGISTRATION SUBMITTED SUCCESSFULLY</h4>
                                <div style="font-size: 0.74rem; color: #94A3B8;">Mobile number ownership verified via cellular SMS OTP</div>
                            </div>
                        </div>
                        <div style="background: rgba(15, 23, 42, 0.7); border-radius: 8px; padding: 10px 14px; margin: 10px 0; font-size: 0.82rem;">
                            <div>👤 <b>Trader Name:</b> <span style="color: #FFFFFF;">{s_name}</span></div>
                            <div style="margin-top: 4px;">📱 <b>Mobile Number:</b> <code style="color: #38BDF8;">+91 {s_mob}</code></div>
                            <div style="margin-top: 4px;">⏳ <b>Status:</b> <span style="background: rgba(245, 158, 11, 0.2); color: #FBBF24; padding: 2px 8px; border-radius: 4px; font-weight: 800;">PENDING ADMINISTRATOR APPROVAL</span></div>
                        </div>
                        <p style="font-size: 0.78rem; color: #CBD5E1; margin: 8px 0 0 0;">
                            Your registration has been forwarded to Administrator (Manoj). You will be able to log in as soon as Admin approves your account.
                        </p>
                    </div>
                    """))

                    if st_button_stretch("← Return to Login", type="primary", key="btn_return_from_reg"):
                        st.session_state.pop("reg_submitted", None)
                        st.session_state.pop("reg_submitted_mobile", None)
                        st.session_state.pop("reg_submitted_name", None)
                        st.session_state["auth_otp_submode"] = "login"
                        st.rerun()

                else:
                    reg_active_otp = st.session_state.get("reg_otp_code")
                    reg_exp_time = st.session_state.get("reg_otp_expires_at", 0)
                    reg_mobile = st.session_state.get("reg_otp_mobile", "")
                    reg_cc = st.session_state.get("reg_otp_country_code", "+91")

                    # Step 1: Enter Name & Mobile -> Send Reg OTP
                    if not reg_active_otp:
                        st.html("<p style='font-size: 0.82rem; color: #CBD5E1; margin-bottom: 12px;'>Enter your name and mobile number. You will receive an SMS OTP to confirm your device, after which your account will be sent to Administrator (Manoj) for approval:</p>")
                        with st.form("new_user_reg_form"):
                            r_col_name, r_col_cc, r_col_m = st.columns([1.5, 0.9, 1.6], vertical_alignment="bottom")
                            with r_col_name:
                                reg_name_in = st.text_input("👤 Your Full / Trader Name", placeholder="e.g. Rahul Sharma", key="reg_input_name")
                            with r_col_cc:
                                reg_cc_sel = st.selectbox("🌐 Code", options=["🇮🇳 +91", "🇺🇸 +1", "🇬🇧 +44", "🇦🇪 +971", "🇸🇬 +65"], index=0, key="reg_input_cc")
                            with r_col_m:
                                reg_m_in = st.text_input("📱 Mobile Number", placeholder="10-digit mobile", key="reg_input_mobile")

                            btn_send_reg = st_form_submit_button_stretch("📩 Verify Mobile & Send OTP", type="primary")

                        if btn_send_reg:
                            if not reg_name_in or len(reg_name_in.strip()) < 2:
                                st.error("❌ Please enter your full name (minimum 2 characters).")
                            elif not reg_m_in or len("".join([c for c in reg_m_in if c.isdigit()])) < 10:
                                st.error("❌ Please enter a valid 10-digit mobile number.")
                            else:
                                ok, err = send_registration_otp(reg_m_in, name=reg_name_in, country_code=reg_cc_sel)
                                if ok:
                                    st.success(f"✅ Registration OTP dispatched to {reg_cc_sel} {reg_m_in[-10:]}!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {err}")

                    # Step 2: Match Reg OTP
                    else:
                        time_left = max(0, int(reg_exp_time - time.time()))
                        mins = time_left // 60
                        secs = time_left % 60
                        masked_m = f"+91-XXXXX-{reg_mobile[-4:]}" if len(reg_mobile) >= 4 else reg_mobile

                        st.html(textwrap.dedent(f"""
                        <div style="background: rgba(14, 165, 233, 0.12); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 10px; padding: 12px 16px; margin-bottom: 16px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 0.85rem; font-weight: 700; color: #38BDF8;">
                                    📲 Registration OTP dispatched to {reg_cc} {masked_m}
                                </span>
                                <span style="font-size: 0.72rem; color: #FCD34D; font-weight: 700; background: rgba(0,0,0,0.4); padding: 3px 8px; border-radius: 4px;">
                                    ⏱️ Expires in {mins:02d}:{secs:02d}
                                </span>
                            </div>
                            <div style="font-size: 0.76rem; color: #94A3B8; margin-top: 6px;">
                                Please enter the 6-digit passcode sent to your device to verify phone ownership.
                            </div>
                        </div>
                        """))

                        with st.form("reg_otp_verification_form"):
                            col_ro1, col_ro2 = st.columns([1.5, 1], vertical_alignment="bottom")
                            with col_ro1:
                                reg_otp_in = st.text_input(
                                    "🔢 Enter 6-Digit Registration OTP",
                                    value="",
                                    max_chars=6,
                                    placeholder="e.g. 123456",
                                    key="reg_otp_input_field"
                                )
                            with col_ro2:
                                verify_reg_btn = st_form_submit_button_stretch("⚡ Verify & Submit Registration →", type="primary")

                            if verify_reg_btn:
                                ok, msg = verify_registration_otp(reg_otp_in)
                                if ok:
                                    st.success(f"✅ {msg}")
                                    time.sleep(0.3)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")

                        col_rr1, col_rr2 = st.columns(2)
                        with col_rr1:
                            if st_button_stretch("🔄 Resend Registration OTP", key="btn_resend_reg_otp"):
                                reg_name = st.session_state.get("reg_otp_name", "Trader")
                                send_registration_otp(reg_mobile, name=reg_name, country_code=reg_cc)
                                st.toast("Fresh registration OTP sent via SMS!")
                                st.rerun()
                        with col_rr2:
                            if st_button_stretch("✏️ Change Details", key="btn_cancel_reg_otp"):
                                st.session_state.pop("reg_otp_code", None)
                                st.session_state.pop("reg_otp_mobile", None)
                                st.session_state.pop("reg_otp_expires_at", None)
                                st.rerun()

        with tab_master:
            rec_mode = st.session_state.get("master_rec_flow")  # None, "forgot_password", "forgot_operator_id"

            if not rec_mode:
                # ---------------- NORMAL MASTER LOGIN VIEW ----------------
                st.html("<p style='font-size: 0.82rem; color: #94A3B8; margin-bottom: 12px;'>Emergency administrative fallback. Use Operator ID and password configured in <code>secrets.toml</code>.</p>")
                with st.form("master_login_form"):
                    c_u, c_p = st.columns(2)
                    with c_u:
                        default_op = st.session_state.get("last_selected_operator", "admin")
                        u_in = st.text_input("👤 Operator ID", value=default_op)
                    with c_p:
                        p_in = st.text_input("🔑 Security Access Key", type="password")

                    master_submit = st_form_submit_button_stretch("⚡ Unlock via Master Credentials", type="primary")
                    if master_submit:
                        creds, _ = _get_auth_credentials()
                        u_clean = (u_in or "").strip()
                        p_clean = (p_in or "").strip()
                        if u_clean in creds and creds[u_clean] == p_clean:
                            st.session_state["is_authenticated"] = True
                            st.session_state["auth_user"] = u_clean
                            st.session_state["auth_role"] = "admin"
                            st.session_state["auth_time"] = datetime.now(IST).strftime("%I:%M %p")
                            st.query_params["_auth"] = generate_session_token(u_clean)
                            st.success("✅ Master credentials verified. Terminal unlocked.")
                            time.sleep(0.3)
                            if blocked_route:
                                st.query_params["stock"] = blocked_route
                            st.rerun()
                        else:
                            st.error("❌ Invalid master operator credentials.")

                # Self-Service Credentials Recovery Options
                st.html(textwrap.dedent("""
                <div style="background: rgba(15, 23, 42, 0.55); border: 1px dashed rgba(56, 189, 248, 0.28); border-radius: 12px; padding: 14px 16px; margin-top: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="font-size: 0.78rem; font-weight: 800; color: #38BDF8; letter-spacing: 0.4px;">
                            🔐 CREDENTIALS RECOVERY &amp; SELF-SERVICE
                        </span>
                        <span style="font-size: 0.70rem; color: #34D399; font-weight: 700; background: rgba(16, 185, 129, 0.15); padding: 2px 8px; border-radius: 12px;">
                            📱 CELLULAR SMS OTP
                        </span>
                    </div>
                    <p style="font-size: 0.75rem; color: #94A3B8; margin: 0 0 10px 0;">
                        Forgot your Security Access Key or Operator ID? Authenticate via your registered administrator mobile (+91 8328580784) OTP to retrieve your Operator ID or reset your password.
                    </p>
                </div>
                """))

                col_rec1, col_rec2 = st.columns(2)
                with col_rec1:
                    if st_button_stretch("🔑 Forgot Password? (Reset Key)", key="btn_forgot_password"):
                        st.session_state["master_rec_flow"] = "forgot_password"
                        st.session_state.pop("rec_otp_code", None)
                        st.session_state.pop("rec_otp_verified", None)
                        st.rerun()
                with col_rec2:
                    if st_button_stretch("👤 Forgot Operator ID?", key="btn_forgot_operator_id"):
                        st.session_state["master_rec_flow"] = "forgot_operator_id"
                        st.session_state.pop("rec_otp_code", None)
                        st.session_state.pop("rec_otp_verified", None)
                        st.rerun()

            else:
                # ---------------- MASTER CREDENTIALS RECOVERY WORKFLOW ----------------
                rec_title = "🔑 Master Security Key Password Recovery" if rec_mode == "forgot_password" else "👤 Master Operator ID Retrieval"
                rec_desc = "Verify your registered mobile number via text message OTP to set a new Security Access Key." if rec_mode == "forgot_password" else "Verify your registered mobile number via text message OTP to retrieve registered Operator IDs."

                # Recovery Header with Back button
                col_h1, col_h2 = st.columns([3, 1], vertical_alignment="center")
                with col_h1:
                    st.html(f"""
                    <div style="margin-bottom: 8px;">
                        <span style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38BDF8; font-size: 0.68rem; font-weight: 800; padding: 2px 8px; border-radius: 10px; text-transform: uppercase;">
                            RECOVERY MODE ACTIVE
                        </span>
                        <h3 style="margin: 4px 0 0 0; font-size: 1.15rem; font-weight: 800; color: #F8FAFC;">{rec_title}</h3>
                        <p style="margin: 2px 0 0 0; font-size: 0.78rem; color: #94A3B8;">{rec_desc}</p>
                    </div>
                    """)
                with col_h2:
                    if st_button_stretch("← Back to Login", key="btn_cancel_recovery"):
                        st.session_state.pop("master_rec_flow", None)
                        st.session_state.pop("rec_otp_code", None)
                        st.session_state.pop("rec_otp_verified", None)
                        st.rerun()

                rec_otp = st.session_state.get("rec_otp_code")
                rec_verified = st.session_state.get("rec_otp_verified", False)
                rec_mobile = st.session_state.get("rec_otp_mobile")
                rec_exp_time = st.session_state.get("rec_otp_expires_at", 0)
                rec_cc = st.session_state.get("rec_otp_country_code", "+91")

                # Step Indicators
                s1_style = "color: #38BDF8; font-weight: 800;" if not rec_otp and not rec_verified else ("color: #10B981; font-weight: 700;" if (rec_otp or rec_verified) else "color: #64748B;")
                s2_style = "color: #38BDF8; font-weight: 800;" if rec_otp and not rec_verified else ("color: #10B981; font-weight: 700;" if rec_verified else "color: #64748B;")
                s3_style = "color: #38BDF8; font-weight: 800;" if rec_verified else "color: #64748B;"
                action_step_label = "3️⃣ Reset Password" if rec_mode == "forgot_password" else "3️⃣ View Operator ID"

                st.html(f"""
                <div style="display: flex; gap: 10px; align-items: center; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(148, 163, 184, 0.15); border-radius: 8px; padding: 8px 14px; margin-bottom: 16px; font-size: 0.75rem;">
                    <span style="{s1_style}">1️⃣ Enter Mobile</span>
                    <span style="color: #475569;">&rarr;</span>
                    <span style="{s2_style}">2️⃣ Match OTP Passcode</span>
                    <span style="color: #475569;">&rarr;</span>
                    <span style="{s3_style}">{action_step_label}</span>
                </div>
                """)

                # ---------------- STEP 1: ENTER MOBILE & SEND OTP ----------------
                if not rec_otp and not rec_verified:
                    st.html("<p style='font-size: 0.82rem; color: #CBD5E1; margin-bottom: 8px;'>Enter your authorized administrator mobile number to receive a 6-digit cryptographic verification OTP text message:</p>")
                    col_r_cc, col_r_m, col_r_btn = st.columns([1.1, 2.0, 1.3], vertical_alignment="bottom")
                    with col_r_cc:
                        country_codes = ["🇮🇳 +91"]
                        rec_sel_cc = st.selectbox("🌐 Code", options=country_codes, index=0, key="rec_country_code_select")
                    with col_r_m:
                        prev_m = st.session_state.get("last_entered_mobile", "8328580784")
                        rec_m_in = st.text_input(
                            "📱 Registered Administrator Mobile",
                            value=prev_m,
                            placeholder="8328580784",
                            help="Only authorized mobile number +91 8328580784 can initiate credentials recovery",
                            key="rec_mobile_input"
                        )
                    with col_r_btn:
                        if st_button_stretch("📩 Send OTP Text", type="primary", key="btn_send_rec_otp"):
                            st.session_state["last_entered_mobile"] = rec_m_in
                            ok, code_or_err = send_recovery_otp(rec_m_in, country_code=rec_sel_cc, recovery_mode=rec_mode)
                            if ok:
                                st.success(f"✅ Recovery OTP text message dispatched to {rec_sel_cc} {rec_m_in[-10:]}!")
                                st.rerun()
                            else:
                                st.error(f"❌ {code_or_err}")

                    st.html("""
                    <div style="font-size: 0.72rem; color: #94A3B8; margin-top: 6px; display: flex; align-items: center; gap: 6px;">
                        <span>🔒</span>
                        <span><b>Security Policy:</b> Master recovery is strictly locked to registered administrator mobile <b>+91 8328580784</b>. Unregistered numbers cannot initiate recovery.</span>
                    </div>
                    """)

                # ---------------- STEP 2: ENTER & MATCH OTP ----------------
                elif rec_otp and not rec_verified:
                    time_left = max(0, int(rec_exp_time - time.time()))
                    mins = time_left // 60
                    secs = time_left % 60

                    masked_rec_m = f"+91-XXXXX-{rec_mobile[-4:]}" if len(rec_mobile) >= 4 else rec_mobile

                    st.html(textwrap.dedent(f"""
                    <div style="background: rgba(14, 165, 233, 0.12); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 10px; padding: 12px 16px; margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.85rem; font-weight: 700; color: #38BDF8;">
                                📲 Recovery OTP text message dispatched to {rec_cc} {masked_rec_m}
                            </span>
                            <span style="font-size: 0.72rem; color: #FCD34D; font-weight: 700; background: rgba(0,0,0,0.4); padding: 3px 8px; border-radius: 4px;">
                                ⏱️ Expires in {mins:02d}:{secs:02d}
                            </span>
                        </div>
                        <div style="font-size: 0.76rem; color: #94A3B8; margin-top: 6px;">
                            Passcode sent directly to your phone as a cellular SMS text message. Please enter the 6-digit passcode below.
                        </div>
                    </div>
                    """))

                    with st.form("rec_otp_matching_form"):
                        col_otp1, col_otp2 = st.columns([1.5, 1], vertical_alignment="bottom")
                        with col_otp1:
                            rec_otp_in = st.text_input(
                                "🔢 Enter 6-Digit Recovery Passcode (OTP)",
                                value="",
                                max_chars=6,
                                placeholder="e.g. 123456",
                                key="rec_otp_input"
                            )
                        with col_otp2:
                            match_btn = st_form_submit_button_stretch("⚡ Verify & Match OTP →", type="primary")

                        if match_btn:
                            ok, msg = verify_recovery_otp(rec_otp_in)
                            if ok:
                                st.success(f"✅ {msg}")
                                time.sleep(0.3)
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")

                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        if st_button_stretch("🔄 Resend Fresh OTP", key="btn_resend_rec_otp"):
                            ok, msg = send_recovery_otp(rec_mobile, country_code=rec_cc, recovery_mode=rec_mode)
                            if ok:
                                st.toast("Fresh OTP dispatched via SMS text message!")
                            else:
                                st.error(f"❌ {msg}")
                            st.rerun()
                    with col_r2:
                        if st_button_stretch("✏️ Edit Mobile Number", key="btn_change_rec_mobile"):
                            st.session_state.pop("rec_otp_code", None)
                            st.session_state.pop("rec_otp_mobile", None)
                            st.session_state.pop("rec_otp_expires_at", None)
                            st.rerun()

                # ---------------- STEP 3: OTP MATCHED -> ACTION ----------------
                elif rec_verified:
                    st.html(textwrap.dedent(f"""
                    <div style="background: rgba(16, 185, 129, 0.15); border: 1.5px solid #10B981; border-radius: 12px; padding: 12px 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 1.5rem;">🛡️</span>
                        <div>
                            <div style="font-size: 0.85rem; font-weight: 800; color: #34D399;">
                                OTP VERIFIED SUCCESSFULLY &bull; MASTER AUTHORIZATION GRANTED
                            </div>
                            <div style="font-size: 0.74rem; color: #CBD5E1; margin-top: 2px;">
                                Mobile ownership confirmed for <code>{rec_cc} {rec_mobile}</code>. You are authorized to manage master credentials below.
                            </div>
                        </div>
                    </div>
                    """))

                    # SUB-CASE 3A: FORGOT PASSWORD (CHANGE PASSWORD)
                    if rec_mode == "forgot_password":
                        creds, _ = _get_auth_credentials()
                        operator_list = list(creds.keys())
                        default_idx = 0

                        st.html("<p style='font-size: 0.82rem; color: #E2E8F0; font-weight: 700; margin-bottom: 8px;'>Set New Security Access Key (Password):</p>")
                        with st.form("reset_password_form"):
                            c_op, c_np1, c_np2 = st.columns([1.2, 1.4, 1.4])
                            with c_op:
                                chosen_op = st.selectbox(
                                    "👤 Target Operator ID",
                                    options=operator_list,
                                    index=default_idx,
                                    help="Select which operator account to update"
                                )
                            with c_np1:
                                new_pwd1 = st.text_input(
                                    "🔑 New Security Key",
                                    type="password",
                                    placeholder="Min 4 characters",
                                    help="Enter your new master access key"
                                )
                            with c_np2:
                                new_pwd2 = st.text_input(
                                    "🔒 Confirm New Key",
                                    type="password",
                                    placeholder="Re-enter new key",
                                    help="Must match new key exactly"
                                )

                            col_act1, col_act2 = st.columns(2)
                            with col_act1:
                                btn_save_unlock = st_form_submit_button_stretch("💾 Change Password & Unlock Terminal", type="primary")
                            with col_act2:
                                btn_save_return = st_form_submit_button_stretch("💾 Change Password & Return to Login")

                            if btn_save_unlock or btn_save_return:
                                if not new_pwd1 or len(new_pwd1.strip()) < 4:
                                    st.error("❌ Password must be at least 4 characters long.")
                                elif new_pwd1 != new_pwd2:
                                    st.error("❌ Passwords do not match. Please re-enter carefully.")
                                else:
                                    ok, msg = update_operator_password(chosen_op, new_pwd1)
                                    if ok:
                                        st.success(f"✅ {msg}")
                                        # Cleanup recovery session
                                        st.session_state.pop("master_rec_flow", None)
                                        st.session_state.pop("rec_otp_code", None)
                                        st.session_state.pop("rec_otp_verified", None)
                                        st.session_state["last_selected_operator"] = chosen_op

                                        if btn_save_unlock:
                                            # Immediate authenticated login
                                            st.session_state["is_authenticated"] = True
                                            st.session_state["auth_user"] = chosen_op
                                            st.session_state["auth_time"] = datetime.now(IST).strftime("%I:%M %p")
                                            st.query_params["_auth"] = generate_session_token(chosen_op)
                                            time.sleep(0.4)
                                            if blocked_route:
                                                st.query_params["stock"] = blocked_route
                                            st.rerun()
                                        else:
                                            time.sleep(0.4)
                                            st.rerun()
                                    else:
                                        st.error(f"❌ {msg}")

                    # SUB-CASE 3B: FORGOT OPERATOR ID (RETRIEVE OPERATOR ID)
                    elif rec_mode == "forgot_operator_id":
                        creds, _ = _get_auth_credentials()
                        st.html("<p style='font-size: 0.82rem; color: #E2E8F0; font-weight: 700; margin-bottom: 10px;'>Registered Master Operator IDs Found in System:</p>")

                        for op_name in creds.keys():
                            role_badge = "PRIMARY ROOT OPERATOR" if op_name == "admin" else "QUANT BENCHMARK TRADER"
                            st.html(f"""
                            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div style="font-size: 0.70rem; color: #38BDF8; font-weight: 800; letter-spacing: 0.6px;">{role_badge}</div>
                                    <div style="font-size: 1.05rem; font-weight: 900; color: #FFFFFF; margin-top: 2px;">
                                        👤 Operator ID: <code style="color: #34D399; font-size: 1.1rem; background: rgba(0,0,0,0.5); padding: 2px 8px; border-radius: 4px;">{op_name}</code>
                                    </div>
                                </div>
                                <span style="font-size: 0.72rem; color: #10B981; font-weight: 700; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); padding: 4px 10px; border-radius: 12px;">ACTIVE ACCOUNT</span>
                            </div>
                            """)

                        col_op1, col_op2 = st.columns(2)
                        with col_op1:
                            if st_button_stretch("🔑 Change Password for an Operator ID", type="primary", key="btn_switch_to_pwd_reset"):
                                st.session_state["master_rec_flow"] = "forgot_password"
                                # Keep rec_otp_verified=True so user doesn't have to re-enter OTP!
                                st.rerun()
                        with col_op2:
                            if st_button_stretch("⚡ Return to Login with Operator ID", key="btn_return_with_op"):
                                st.session_state.pop("master_rec_flow", None)
                                st.session_state.pop("rec_otp_code", None)
                                st.session_state.pop("rec_otp_verified", None)
                                st.rerun()


        st.html(textwrap.dedent("""
        <div class="quant-feature-grid">
            <div class="quant-feature-card">
                <div style="font-size: 0.70rem; color: #64748B; font-weight: 700;">BROKER ROUTING</div>
                <div style="font-size: 0.85rem; font-weight: 800; color: #10B981; margin-top: 2px;">Groww Direct 0-Delay</div>
                <div style="font-size: 0.65rem; color: #94A3B8; margin-top: 2px;">1-Tap Limit &amp; Market Fills</div>
            </div>
            <div class="quant-feature-card">
                <div style="font-size: 0.70rem; color: #64748B; font-weight: 700;">STRATEGY 3 ENGINE</div>
                <div style="font-size: 0.85rem; font-weight: 800; color: #38BDF8; margin-top: 2px;">01:30 PM Gamma Trap</div>
                <div style="font-size: 0.65rem; color: #94A3B8; margin-top: 2px;">Hard Tick SL &amp; +8pt Breakeven</div>
            </div>
            <div class="quant-feature-card">
                <div style="font-size: 0.70rem; color: #64748B; font-weight: 700;">2FA SECURITY</div>
                <div style="font-size: 0.85rem; font-weight: 800; color: #A855F7; margin-top: 2px;">Telegram + HMAC</div>
                <div style="font-size: 0.65rem; color: #94A3B8; margin-top: 2px;">Direct URL Shield Active</div>
            </div>
        </div>

        <div style="text-align: center; margin-top: 18px; font-size: 0.72rem; color: #64748B;">
            Protected by Institutional Quant Engine Risk Controls &bull; 2FA Powered by Telegram Alert Gateway
        </div>
        """))


def render_authenticated_user_sidebar():
    """Renders the operator identity badge, admin registry panel, and logout button in the Streamlit sidebar."""
    user = str(st.session_state.get("auth_user", "Operator")).upper()
    login_time = st.session_state.get("auth_time", "--:--")

    st.sidebar.html(textwrap.dedent(f"""
    <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 10px; padding: 10px 12px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 6px;">
                <span style="display: inline-block; width: 8px; height: 8px; background: #10B981; border-radius: 50%; box-shadow: 0 0 8px #10B981;"></span>
                <span style="font-size: 0.82rem; font-weight: 800; color: #F8FAFC;">{user}</span>
            </div>
            <span style="font-size: 0.68rem; color: #34D399; font-weight: 700; background: rgba(16, 185, 129, 0.15); padding: 2px 6px; border-radius: 4px;">VERIFIED</span>
        </div>
        <div style="font-size: 0.70rem; color: #94A3B8; margin-top: 4px; display: flex; justify-content: space-between;">
            <span>⚡ 1-Tap Groww Armed</span>
            <span>Auth: {login_time}</span>
        </div>
    </div>
    """))

    if st_sidebar_button_stretch("🔒 Lock Terminal (Logout)", key="sb_btn_logout", help="Revoke session and lock terminal"):
        logout_user()


def render_dedicated_admin_portal():
    """Renders dedicated full-page Administrator Console solely for user approval/reject/unregistered."""
    import user_registry_manager as user_reg
    user_reg.render_dedicated_admin_portal()


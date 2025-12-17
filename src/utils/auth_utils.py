import hmac
import time
import re
import datetime
import streamlit as st
from typing import Tuple, Optional

# Constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 5
GUEST_KEY_PATTERN = r"^AIza[0-9A-Za-z-_]{35}$"

def init_auth_state():
    """Initialize session state variables for authentication."""
    if "auth_status" not in st.session_state:
        st.session_state["auth_status"] = None  # None: not attempted, True: success, False: failed
    if "auth_user_type" not in st.session_state:
        st.session_state["auth_user_type"] = None # 'master' or 'guest'
    if "api_key" not in st.session_state:
        st.session_state["api_key"] = None
    if "failed_attempts" not in st.session_state:
        st.session_state["failed_attempts"] = 0
    if "locked_until" not in st.session_state:
        st.session_state["locked_until"] = None

def is_locked_out() -> Tuple[bool, Optional[float]]:
    """Check if the user is currently locked out."""
    if st.session_state["locked_until"]:
        remaining = (st.session_state["locked_until"] - datetime.datetime.now()).total_seconds()
        if remaining > 0:
            return True, remaining
        else:
            # Lockout expired, reset
            st.session_state["locked_until"] = None
            st.session_state["failed_attempts"] = 0
            return False, None
    return False, None

def handle_failed_attempt():
    """Handle a failed login attempt: increment counter, apply delay, and check lockout."""
    st.session_state["failed_attempts"] += 1
    attempts = st.session_state["failed_attempts"]
    
    # Exponential backoff (max 3 seconds to avoid UX frustration, but enough to slow attacks)
    delay = min(0.5 * (2 ** (attempts - 1)), 3.0)
    time.sleep(delay)
    
    if attempts >= MAX_FAILED_ATTEMPTS:
        st.session_state["locked_until"] = datetime.datetime.now() + datetime.timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    
    st.session_state["auth_status"] = False
    st.error(f"Access Denied. Incorrect credentials.")

def login(user_input: str) -> bool:
    """
    Authenticate the user based on input.
    - If input matches APP_PASSWORD (HMAC) -> Master Mode
    - If input matches Guest Key Pattern -> Guest Mode
    """
    # 1. Check Lockout
    locked, remaining = is_locked_out()
    if locked:
        st.error(f"Too many failed attempts. Try again in {int(remaining // 60)}m {int(remaining % 60)}s.")
        return False

    # 2. Check Input
    if not user_input:
        st.warning("Please enter a password or API key.")
        return False

    # Get Master Password from secrets (handle nested [general] section)
    master_password = st.secrets.get("APP_PASSWORD")
    if not master_password and "general" in st.secrets:
        master_password = st.secrets["general"].get("APP_PASSWORD")

    # 3. Verify Master Password (HMAC for timing attack protection)
    if master_password and hmac.compare_digest(user_input.encode("utf-8"), master_password.encode("utf-8")):
        st.session_state["auth_status"] = True
        st.session_state["auth_user_type"] = "master"
        
        # Load API Key from secrets
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key and "general" in st.secrets:
             api_key = st.secrets["general"].get("GEMINI_API_KEY")
             
        if api_key:
            st.session_state["api_key"] = api_key
            st.session_state["failed_attempts"] = 0
            st.rerun()
            return True
        else:
            st.error("System Error: GEMINI_API_KEY not found in secrets.")
            return False

    # 4. Verify Guest Key (Regex)
    if re.match(GUEST_KEY_PATTERN, user_input):
        st.session_state["auth_status"] = True
        st.session_state["auth_user_type"] = "guest"
        st.session_state["api_key"] = user_input
        st.session_state["failed_attempts"] = 0
        st.rerun()
        return True

    # 5. Failed
    handle_failed_attempt()
    return False

def logout():
    """Clear session state for logout."""
    keys_to_reset = ["auth_status", "auth_user_type", "api_key"]
    for key in keys_to_reset:
        st.session_state[key] = None
    st.rerun()

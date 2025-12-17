import streamlit as st
import os
from src.core.analyzer_service import analyze_image
from src.core.excel_service import render_excel
from src.utils import auth_utils, image_utils

# --- Configuration ---
st.set_page_config(
    page_title="Smart Layout OCR (S-LOE)",
    page_icon="📄",
    layout="centered"
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-family: 'Inter', sans-serif; color: #1a73e8; text-align: center; font-weight: 700; }
    .sub-header { font-family: 'Inter', sans-serif; color: #5f6368; text-align: center; margin-bottom: 2rem; }
    .stButton>button { background-color: #1a73e8; color: white; border-radius: 20px; padding: 0 20px; }
    .error-box { padding: 1rem; background-color: #ffebee; border-radius: 8px; color: #c62828; }
</style>
""", unsafe_allow_html=True)

import hashlib
import hmac

# --- Caching Wrapper ---
@st.cache_data(show_spinner=False, ttl=3600, max_entries=100)
def get_cached_analysis(image_bytes: bytes, mime_type: str, model_name: str, cache_seed: str, prompt_version: str, _api_key: str):
    """
    Cached wrapper for image analysis.
    - image_bytes, mime_type: The content.
    - model_name: The model version.
    - cache_seed: "master_shared" OR HMAC(api_key). Ensures cached data is strictly isolated per user/scope.
    - prompt_version: Manual cache invalidation key.
    - _api_key: Excluded from cache key (starts with underscore), used only for API call.
    """
    return analyze_image(image_bytes, mime_type=mime_type, model_name=model_name, api_key=_api_key)

# --- Main App ---
def main():
    st.markdown("<h1 class='main-header'>Smart Layout OCR to Excel</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Gemini 3 Pro Powered Document Digitization</p>", unsafe_allow_html=True)

    # 1. Initialize Auth State
    auth_utils.init_auth_state()

    # 2. Sidebar Login
    with st.sidebar:
        st.header("🔑 Authentication")
        
        if st.session_state["auth_status"]:
            st.success(f"Logged in as: {st.session_state['auth_user_type'].upper()}")
            if st.button("Logout"):
                auth_utils.logout()
        else:
            with st.form("login_form"):
                user_input = st.text_input("Enter App Password or API Key", type="password")
                submitted = st.form_submit_button("Login")
                
                if submitted:
                    auth_utils.login(user_input)
            
            st.info("💡 **Password**: Use for unrestricted access.\n💡 **API Key**: Use your own `AIza...` key.")

    # 3. Main Content (Protected)
    if not st.session_state["auth_status"]:
        st.markdown("""
        <div style='text-align: center; margin-top: 50px;'>
            <h3>🔒 Access Restricted</h3>
            <p>Please login using the sidebar to verify your access.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # 4. Authenticated UI
    st.write("### 📤 문서 이미지 업로드")
    st.caption("지원 형식: **PNG, JPG, JPEG, WEBP** (최대 20MB)")

    uploaded_file = st.file_uploader(
        "Upload Document Image", 
        type=['png', 'jpg', 'jpeg', 'webp']
    )

    if uploaded_file is not None:
        # Validate Image Logic (Security)
        image_bytes, mime_type, error = image_utils.validate_and_process_image(uploaded_file)
        
        if error:
            st.error(f"❌ {error}")
            return

        # Preview
        st.image(uploaded_file, caption=f"Uploaded Image ({mime_type})", use_container_width=True)
        
        if st.button("Convert to Excel"):
            with st.status("Processing...", expanded=True) as status:
                st.write("🔍 Analyzing Layout with Gemini...")
                
                try:
                    # Fetch from Cache or API
                    api_key = st.session_state["api_key"]
                    model_name = st.secrets.get("GEMINI_MODEL_NAME")
                    if not model_name and "general" in st.secrets:
                        model_name = st.secrets["general"].get("GEMINI_MODEL_NAME")
                    if not model_name:
                        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3-pro-preview")
                    
                    auth_user_type = st.session_state["auth_user_type"]
                    
                    # Determine Cache Seed (Security: Isolation)
                    if auth_user_type == "master":
                        cache_seed = "master_shared"
                    else:
                        # Guest: Generate HMAC based Seed using Server Secret
                        # This prevents guests from guessing cache keys or sharing data by accident
                        secret = st.secrets.get("APP_PASSWORD") or st.secrets.get("general", {}).get("APP_PASSWORD") or "default_salt"
                        cache_seed = hmac.new(secret.encode(), api_key.encode(), hashlib.sha256).hexdigest()

                    layout_data = get_cached_analysis(
                        image_bytes=image_bytes,
                        mime_type=mime_type,
                        model_name=model_name,
                        cache_seed=cache_seed,
                        prompt_version="v1",
                        _api_key=api_key
                    )
                    
                    st.write("✅ Structure Extracted.")
                    st.write("📊 Rendering Excel File...")
                    
                    excel_bytes = render_excel(layout_data)
                    
                    status.update(label="Conversion Complete!", state="complete", expanded=False)
                    st.success("Your Excel file is ready!")
                    
                    st.download_button(
                        label="Download Excel File",
                        data=excel_bytes,
                        file_name="Converted_Result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                except Exception as e:
                    status.update(label="Error Occurred", state="error")
                    st.error(f"Failed to convert. Please check your API usage or file content.\nDetails: {str(e)}")

if __name__ == "__main__":
    main()

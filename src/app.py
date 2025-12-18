import streamlit as st
import os
import sys

# Fix for ModuleNotFoundError: Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.analyzer_service import analyze_image
from src.core.excel_service import render_excel
from src.utils import auth_utils, image_utils
from streamlit_cropper import st_cropper
from PIL import Image, ImageOps
import io

# --- Caching for Image Normalization ---
@st.cache_data(max_entries=50, ttl=3600) 
def load_normalized_image_bytes(image_bytes: bytes) -> bytes:
    """
    입력 바이트를 받아 EXIF 회전 및 RGB 변환을 거친 정규화된 이미지의 바이트(PNG)를 반환합니다.
    PIL 객체 자체를 캐싱하는 것보다 bytes 캐싱이 Pickling 이슈에서 안전합니다.
    """
    image = Image.open(io.BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image) # EXIF 회전 반영
    image = image.convert("RGB") # 항상 RGB로 변환
    
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()

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

import pandas as pd
import io

# --- Helper Callback ---
def reset_state():
    """Reset conversion result when file changes."""
    if "conversion_result" in st.session_state:
        st.session_state["conversion_result"] = None

# --- Main App ---
def main():
    st.markdown("<h1 class='main-header'>Smart Layout OCR to Excel</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Gemini 3 Flash Powered Document Digitization</p>", unsafe_allow_html=True)

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
        type=['png', 'jpg', 'jpeg', 'webp'],
        key="uploader",
        on_change=reset_state
    )

    if uploaded_file is not None:
        # Validate Image Logic (Security)
        image_bytes, mime_type, error = image_utils.validate_and_process_image(uploaded_file)
        
        if error:
            st.error(f"❌ {error}")
            return

        # Preview (Persistent)
        # st.image(uploaded_file, caption=f"Uploaded Image ({mime_type})", use_container_width=True) # REMOVED: Replaced by Cropper UI Logic

        # --- 1. Load & Normalize Image (Cached) ---
        try:
            normalized_bytes = load_normalized_image_bytes(image_bytes)
            # Create lightweight PIL object for UI from cached bytes
            pil_image = Image.open(io.BytesIO(normalized_bytes))
        except Exception as e:
            st.error(f"Failed to process image: {e}")
            return

        # --- 2. Crop Mode Toggle ---
        use_crop = st.toggle("✂️ 자르기 모드 (Crop Mode)", value=False, help="표 영역만 선택하여 변환 정확도를 높이세요.")
        
        cropped_img = None # Variable to hold the final PIL image to show/use

        if use_crop:
            st.info("💡 박스 모서리를 드래그하여 변환할 **표(Table)** 영역을 선택하세요.")
            
            # Safe File ID Generation
            file_id = getattr(uploaded_file, "file_id", None) or f"{uploaded_file.name}_{uploaded_file.size}"
            
            # Render Cropper
            cropped_img = st_cropper(
                img_file=pil_image,
                realtime_update=True,
                box_color='#0000FF',
                aspect_ratio=None,
                key=f"cropper_{file_id}"
            )
            
            # Note: cropped_img is a PIL Image returned by st_cropper
        else:
            # Standard View (Using Normalized Image for Consistency)
            st.image(pil_image, caption=f"Original Image ({mime_type}) - EXIF Rotated", use_container_width=True)
            cropped_img = pil_image # Use full image
        
        # Action Button
        if st.button("Convert to Excel"):
            # Reset previous result immediately before processing
            reset_state()
            
            # --- 3. Finalize Image for API ---
            final_image_bytes = None
            final_mime_type = "image/png" # We always convert to PNG

            if use_crop and cropped_img:
                # Convert the cropped PIL image to PNG bytes
                output = io.BytesIO()
                cropped_img.save(output, format='PNG')
                final_image_bytes = output.getvalue()
            else:
                # Use the normalized full image bytes
                final_image_bytes = normalized_bytes

            
            with st.status("Processing...", expanded=True) as status:
                st.write("🔍 Analyzing Layout with Gemini...")
                
                try:
                    # Fetch from Cache or API
                    api_key = st.session_state["api_key"]
                    model_name = st.secrets.get("GEMINI_MODEL_NAME")
                    if not model_name and "general" in st.secrets:
                        model_name = st.secrets["general"].get("GEMINI_MODEL_NAME")
                    if not model_name:
                        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash")
                    
                    auth_user_type = st.session_state["auth_user_type"]
                    
                    # Determine Cache Seed (Security: Isolation)
                    if auth_user_type == "master":
                        cache_seed = "master_shared"
                    else:
                        # Guest: Generate HMAC based Seed using Server Secret
                        secret = st.secrets.get("APP_PASSWORD") or st.secrets.get("general", {}).get("APP_PASSWORD") or "default_salt"
                        cache_seed = hmac.new(secret.encode(), api_key.encode(), hashlib.sha256).hexdigest()

                    layout_data = get_cached_analysis(
                        image_bytes=final_image_bytes, # Use the finalized bytes
                        mime_type=final_mime_type,     # Always image/png
                        model_name=model_name,
                        cache_seed=cache_seed,
                        prompt_version="v1_crop", # Version bump for crop support
                        _api_key=api_key
                    )
                    
                    st.write("✅ Structure Extracted.")
                    st.write("📊 Rendering Excel File...")
                    
                    excel_bytes = render_excel(layout_data)
                    
                    # Generate Preview DataFrame (Limit to top 100 rows for performance)
                    try:
                        preview_df = pd.read_excel(io.BytesIO(excel_bytes), nrows=100)
                    except Exception:
                        preview_df = None # Fallback if pandas fails to read generated excel
                    
                    # Store result in Session State for Persistence
                    st.session_state["conversion_result"] = {
                        "excel_bytes": excel_bytes,
                        "preview_df": preview_df
                    }
                    
                    status.update(label="Conversion Complete!", state="complete", expanded=False)
                    st.success("Your Excel file is ready! See preview below.")
                    
                except Exception as e:
                    status.update(label="Error Occurred", state="error")
                    st.error(f"Failed to convert. Please check your API usage or file content.\nDetails: {str(e)}")

        # Result Section (Persistent)
        if st.session_state.get("conversion_result"):
            st.divider()
            st.write("### 📊 엑셀 미리보기")
            
            result_data = st.session_state["conversion_result"]
            preview_df = result_data.get("preview_df")
            excel_bytes = result_data.get("excel_bytes")
            
            if preview_df is not None:
                st.warning("⚠️ **미리보기는 상위 100행만 표시됩니다.** 전체 내용은 다운로드하여 확인하세요.")
                st.dataframe(preview_df, use_container_width=True)
            else:
                st.warning("⚠️ 미리보기를 불러올 수 없습니다. 다운로드하여 확인해주세요.")
            
            st.download_button(
                label="📥 Download Excel File",
                data=excel_bytes,
                file_name="Converted_Result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_btn"
            )

if __name__ == "__main__":
    main()

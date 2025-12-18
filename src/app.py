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
    layout="wide" # CHANGED: Wide mode for split view
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-family: 'Inter', sans-serif; color: #1a73e8; text-align: center; font-weight: 700; }
    .sub-header { font-family: 'Inter', sans-serif; color: #5f6368; text-align: center; margin-bottom: 2rem; }
    .stButton>button { background-color: #1a73e8; color: white; border-radius: 20px; padding: 0 20px; width: 100%; } /* Button full width in col */
    .error-box { padding: 1rem; background-color: #ffebee; border-radius: 8px; color: #c62828; }
    
    /* File Uploader Customization */
    section[data-testid="stFileUploader"] {
        /* Wrapper style if needed */
    }
    
    /* Target the Dropzone Area to match result panel size (Approx 314px) */
    [data-testid="stFileUploaderDropzone"] {
        min-height: 314px; /* Matches right panel height */
        /* display: flex; already flex */
        /* flex-direction: column; already column */
        /* justify-content: center; already center */
    }

    /* Hide the second span which contains the 'Limit 200MB...' text */
    [data-testid="stFileUploaderDropzoneInstructions"] > div:nth-child(1) > span:nth-child(2) {
       visibility: hidden;
       height: 0;
       display: block;
    }
    /* Fallback: target based on content (not possible in pure CSS easily without checking structure)
       Usually standard Streamlit flow:
       stFileUploaderDropzoneInstructions
         > div > small (older) OR > div > span (newer)
       Let's try a broader hit for the instructions text container if needed.
    */
    
    /* Inject custom text */
    [data-testid="stFileUploaderDropzoneInstructions"] > div:nth-child(1) > span:nth-child(2)::before {
        content: "지원 형식: PNG, JPG, JPEG, WEBP (최대 20MB)";
        visibility: visible;
        display: block;
        height: auto;
        color: #757575; /* Gray text to match design */
        font-size: 14px;
        margin-top: 10px; 
    }
    
    /* Note: "Drag and drop file here" is usually the first span. We leave it. */
    
    /* Responsive adjustment handled by Streamlit default stacking */
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
    # Strict Reset: Clear result and metadata
    if "conversion_result" in st.session_state:
        st.session_state["conversion_result"] = None
    if "result_meta" in st.session_state:
        st.session_state["result_meta"] = None

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

    # 4. Authenticated UI - Split Layout
    
    # Create Columns
    col1, col2 = st.columns([1, 1], gap="medium")

    # --- LEFT COLUMN: Input & Action ---
    with col1:
        st.write("### 📤 문서 이미지 업로드")
        # st.caption("지원 형식: **PNG, JPG, JPEG, WEBP** (최대 20MB)") # REMOVED: Moved to CSS injection

        uploaded_file = st.file_uploader(
            "Upload Document Image", 
            type=['png', 'jpg', 'jpeg', 'webp'],
            key="uploader",
            on_change=reset_state # Callback ensures reset on new file
        )

        final_image_bytes = None
        final_mime_type = "image/png"
        
        current_file_id = None
        current_crop_id = None # (left, top, width, height) or None

        if uploaded_file is not None:
            # Generate Safe File ID
            # Using basic properties + size for simple ID. Ideally sha256 but this is fast.
            current_file_id = getattr(uploaded_file, "file_id", None) or f"{uploaded_file.name}_{uploaded_file.size}"

            # Validate Image Logic (Security)
            image_bytes, mime_type, error = image_utils.validate_and_process_image(uploaded_file)
            
            if error:
                st.error(f"❌ {error}")
                return

            # --- Load & Normalize Image (Cached) ---
            try:
                normalized_bytes = load_normalized_image_bytes(image_bytes)
                pil_image = Image.open(io.BytesIO(normalized_bytes))
            except Exception as e:
                st.error(f"Failed to process image: {e}")
                return

            # --- Crop Mode Toggle ---
            use_crop = st.toggle("✂️ 자르기 모드 (Crop Mode)", value=False, help="표 영역만 선택하여 변환 정확도를 높이세요.", on_change=reset_state)
            
            cropped_img = None
            
            if use_crop:
                st.info("💡 박스 모서리를 드래그하여 변환할 **표(Table)** 영역을 선택하세요.")
                
                # Render Cropper
                # Note: st_cropper doesn't expose on_change/box return easily without rerun.
                # using st_cropper's return value to detect change implies rerun.
                cropped_box = st_cropper(
                    img_file=pil_image,
                    realtime_update=True, # Performance vs UX trade-off
                    box_color='#0000FF',
                    aspect_ratio=None,
                    key=f"cropper_{current_file_id}",
                    return_type='box' # Get coordinates for ID generation
                )
                
                # Re-crop manually to get image and consistent ID
                # cropped_box response: {'left': int, 'top': int, 'width': int, 'height': int}
                if cropped_box:
                     current_crop_id = (cropped_box['left'], cropped_box['top'], cropped_box['width'], cropped_box['height'])
                     cropped_img = pil_image.crop((
                         cropped_box['left'], 
                         cropped_box['top'], 
                         cropped_box['left'] + cropped_box['width'], 
                         cropped_box['top'] + cropped_box['height']
                     ))
                else:
                    # Default full image if box is weird
                    current_crop_id = None
                    cropped_img = pil_image

            else:
                st.image(pil_image, caption=f"Original Image ({mime_type}) - EXIF Rotated", use_container_width=True)
                current_crop_id = None # Full image
                cropped_img = pil_image 
            
            # --- Prepare Final Bytes ---
            if use_crop and cropped_img:
                output = io.BytesIO()
                cropped_img.save(output, format='PNG')
                final_image_bytes = output.getvalue()
            else:
                final_image_bytes = normalized_bytes


            # Action Button
            if st.button("Convert to Excel"):
                # Explicit Reset before start
                reset_state()
                
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
                            image_bytes=final_image_bytes, 
                            mime_type=final_mime_type,     
                            model_name=model_name,
                            cache_seed=cache_seed,
                            prompt_version="v1_crop", 
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
                        # Store Meta for ID Matching
                        st.session_state["result_meta"] = {
                            "file_id": current_file_id,
                            "crop_id": current_crop_id
                        }
                        
                        status.update(label="Conversion Complete!", state="complete", expanded=False)
                        st.success("Your Excel file is ready! Check the right panel.")
                        
                    except Exception as e:
                        status.update(label="Error Occurred", state="error")
                        st.error(f"Failed to convert. Please check your API usage or file content.\nDetails: {str(e)}")

    # --- RIGHT COLUMN: Result & Preview ---
    with col2:
        st.write("### 📊 엑셀 변환 결과")
        
        # ID Matching Logic for Safe Rendering
        result_data = st.session_state.get("conversion_result")
        result_meta = st.session_state.get("result_meta")
        
        is_result_valid = False
        if result_data and result_meta:
            # Check if stored ID matches current input state
            # Logic: If user changed upload or crop without clicking Convert, IDs won't match.
            # However, if uploaded_file is None, we shouldn't show old result anyway?
            # Plan said: "UX Consistency: Show result if session exists."
            # Codex 3rd Review said: "Only show if IDs match current state."
            
            # Case 1: Upload matches (or result exists and user is viewing same file)
            # If uploaded_file is None (page refresh?), current_file_id is None.
            # We relax check: If current_file_id is None, maybe hide? Or keep showing old result?
            # Strict approach: Must match CURRENT input.
            
            if uploaded_file is None:
                 # No input present. Hide result or show strict empty state?
                 # Let's clean up state if file is gone defined by st.file_uploader logic
                 is_result_valid = False
            else:
                 # Check IDs
                 if result_meta.get("file_id") == current_file_id and result_meta.get("crop_id") == current_crop_id:
                     is_result_valid = True
                 else:
                     is_result_valid = False

        if is_result_valid:
            st.info("✅ 변환이 완료되었습니다. 내용을 확인하고 다운로드하세요.")
            
            preview_df = result_data.get("preview_df")
            excel_bytes = result_data.get("excel_bytes")
            
            # Mobile Optimization: container width
            if preview_df is not None:
                st.caption("⚠️ **미리보기 (상위 100행)**")
                st.dataframe(preview_df, use_container_width=True)
            else:
                st.warning("⚠️ 미리보기를 불러올 수 없습니다.")
            
            st.download_button(
                label="📥 엑셀 파일 다운로드 (Download .xlsx)",
                data=excel_bytes,
                file_name="Converted_Result.xlsx",
                key="download_btn",
                use_container_width=True # Wide button for touch targets
            )
        else:
            # Empty / Placeholder State
            st.markdown("""
            <div style='
                text-align: center; 
                padding: 40px 20px; 
                border: 2px dashed #e0e0e0; 
                border-radius: 10px; 
                color: #757575;
                margin-top: 20px;
            '>
                <div style='font-size: 40px; margin-bottom: 10px;'>👈</div>
                <h4>변환할 이미지를 업로드하세요</h4>
                <p>왼쪽 패널에서 이미지를 선택하고 <b>[Convert to Excel]</b> 버튼을 눌러주세요.</p>
                <p style='font-size: 0.9em; margin-top: 10px;'>
                    변환 결과와 미리보기가 이 영역에 표시됩니다.<br>
                    모바일에서는 스크롤하여 하단에서 확인하실 수 있습니다.
                </p>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

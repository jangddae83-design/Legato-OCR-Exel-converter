import streamlit as st
import os
import sys
import io
import uuid
import tempfile
import shutil
from pathlib import Path
from PIL import Image

# Fix for ModuleNotFoundError: Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.analyzer_service import analyze_image
from src.core.excel_service import render_excel
from src.utils import auth_utils, image_utils
from streamlit_cropper import st_cropper

# --- Security Constants ---
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_PIXELS = 20_000_000           # 20MP (e.g. approx 4k x 5k)
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

# --- Security Helpers ---
def copy_limited(src, dst, limit):
    """
    Copy data from src to dst, enforcing a byte limit to prevent DoS.
    """
    total = 0
    while True:
        chunk = src.read(1024 * 1024) # 1MB chunk
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValueError(f"File size limit exceeded ({limit / 1024 / 1024}MB).")
        dst.write(chunk)
    return total

def validate_image_security(path):
    """
    Enforce strict image validation:
    1. Pixel Bomb Protection (Decompression Bomb)
    2. Format Verification (Magic Numbers via Pillow)
    """
    # Protect against Decompression Bomb
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS 
    
    try:
        # 1. Format & Structure Check
        with Image.open(path) as img:
            if img.format not in ALLOWED_FORMATS:
                raise ValueError(f"지원하지 않는 포맷입니다: {img.format} (허용: JPEG, PNG, WEBP)")
            
            # Simulate loading to catch truncated/corrupt files (Verify only checks headers)
            img.verify() 
        
        # 2. Detail Check (Dimensions/Pixels) - Re-open required after verify()
        with Image.open(path) as img:
            w, h = img.size
            if w * h > MAX_PIXELS:
                raise ValueError(f"이미지 해상도가 너무 큽니다. (limit: {MAX_PIXELS/1_000_000}MP)")
                
    except Exception as e:
        raise ValueError(f"이미지 보안 검증 실패: {str(e)}")

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
    [data-testid="stFileUploader"] {
        padding-top: 0; /* Align closely with container top */
    }
    
    /* Target the Dropzone Area to match result panel size (Approx 314px) */
    [data-testid="stFileUploaderDropzone"] {
        min-height: 314px; /* Matches right panel height */
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center; 
        border: 1px dashed #ccc; /* Ensure border integration */
        border-radius: 8px;
    }

    /* Hide the standard file list to "replace" it with our Custom Header */
    [data-testid="stFileUploader"] ul {
        display: none;
    }

    /* Hide default limit text and inject custom message */
    [data-testid="stFileUploaderDropzoneInstructions"] > div:nth-child(1) > span:nth-child(2) {
       visibility: hidden;
       height: 0;
       display: block;
    }
    
    [data-testid="stFileUploaderDropzoneInstructions"] > div:nth-child(1) > span:nth-child(2)::before {
        content: "지원 형식: PNG, JPG, JPEG, WEBP (최대 20MB)";
        visibility: visible;
        display: block;
        height: auto;
        color: #757575; 
        font-size: 14px;
        margin-top: 10px; 
    }
</style>
""", unsafe_allow_html=True)

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


# --- Helper Callback ---
def init_session_state():
    """Initialize session state variables including State Machine."""
    if "api_key" not in st.session_state:
        st.session_state.api_key = auth_utils.get_api_key_from_env()

    # --- UI State Machine ---
    if "ui_step" not in st.session_state:
        st.session_state.ui_step = "upload"  # upload -> process -> error
    if "current_file_path" not in st.session_state:
        st.session_state.current_file_path = None
    if "current_file_name" not in st.session_state:
        st.session_state.current_file_name = None
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = str(uuid.uuid4())
    if "error_msg" not in st.session_state:
        st.session_state.error_msg = None

    # --- Processing State ---
    if "excel_data" not in st.session_state:
        st.session_state.excel_data = None
    if "cropping" not in st.session_state:
        st.session_state.cropping = False

def handle_file_upload_secure():
    """
    Handle file upload with 7-Layer Defense Strategy (Enterprise Grade).
    """
    # 0. Cleanup Old State (Strict Cleanup)
    if st.session_state.current_file_path and os.path.exists(st.session_state.current_file_path):
        try:
            os.remove(st.session_state.current_file_path)
        except OSError:
            pass # Logging recommended in production
    
    uploaded = st.session_state.get(st.session_state.uploader_key)
    
    if uploaded:
        # Layer 1: Private Temp Dir (Symlink/TOCTOU Prevention)
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Layer 2: Generated Filename (UUID) - Prevent Path Traversal
                safe_name = f"{uuid.uuid4()}.tmp"
                temp_path = os.path.join(temp_dir, safe_name)
                
                # Layer 3: Stream Copy with Limit (DoS Prevention)
                with open(temp_path, 'wb') as dst:
                    uploaded.seek(0)
                    copy_limited(uploaded, dst, MAX_FILE_SIZE)
                
                # Layer 4 & 5: Pixel Bomb & Format Whitelisting (Pillow)
                validate_image_security(temp_path)
                
                # Layer 6: Atomic Save (Move to Persistent Temp)
                # Note: We move to system temp because 'temp_dir' is wiped after 'with' block
                final_path = os.path.join(tempfile.gettempdir(), f"legato_{safe_name}")
                shutil.move(temp_path, final_path)
                
                # Update State
                st.session_state.current_file_path = final_path
                st.session_state.current_file_name = uploaded.name
                st.session_state.ui_step = "process"
                st.session_state.error_msg = None
                
            except Exception as e:
                # Layer 7: Error State & implicit cleanup (temp_dir wipes itself)
                st.session_state.error_msg = f"업로드 실패 ({str(e)})"
                st.session_state.ui_step = "error"

def handle_remove_file():
    """Reset to upload state and cleanup resources."""
    if st.session_state.current_file_path and os.path.exists(st.session_state.current_file_path):
        try:
            os.remove(st.session_state.current_file_path)
        except OSError:
            pass
            
    st.session_state.current_file_path = None
    st.session_state.current_file_name = None
    st.session_state.excel_data = None
    st.session_state.cropping = False
    st.session_state.error_msg = None
    
    # Reset Uploader Widget
    st.session_state.uploader_key = str(uuid.uuid4())
    st.session_state.ui_step = "upload"
# --- Main App ---
def main():
    st.markdown("<h1 class='main-header'>Smart Layout OCR to Excel</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Gemini 3 Flash Powered Document Digitization</p>", unsafe_allow_html=True)

    # 1. Initialize Auth State & App State
    auth_utils.init_auth_state()
    init_session_state()

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
    col1, col2 = st.columns([1, 1], gap="medium")

    # --- LEFT COLUMN: State Machine UI ---
    with col1:
        st.write("### 📤 문서 이미지 업로드")
        
        # State: UPLOAD
        if st.session_state.ui_step == "upload":
            with st.container(border=True):
                st.file_uploader(
                    "Upload Document Image", 
                    type=['png', 'jpg', 'jpeg', 'webp'],
                    key=st.session_state["uploader_key"],
                    on_change=handle_file_upload_secure
                )
                st.info("지원 형식: PNG, JPG, WEBP (Max 20MB)")

        # State: PROCESS
        elif st.session_state.ui_step == "process":
            # Self-Healing: Check if file still exists
            if not st.session_state.current_file_path or not os.path.exists(st.session_state.current_file_path):
                st.warning("⚠️ 파일이 만료되었거나 삭제되었습니다. 다시 업로드해주세요.")
                handle_remove_file()
                st.rerun()

            with st.container(border=True):
                # 1. Custom Header (File Name + Remove Button)
                col_h1, col_h2 = st.columns([0.85, 0.15])
                with col_h1:
                    st.write(f"📄 **{st.session_state.current_file_name}**")
                with col_h2:
                    if st.button("🗑️", help="파일 제거 및 초기화"):
                        handle_remove_file()
                        st.rerun()

                # 2. Image Processing & Preview
                try:
                    # Security: Load from Secure Temp Path
                    pil_image = Image.open(st.session_state.current_file_path)
                    
                    st.image(pil_image, use_container_width=True)

                    # 3. Controls (Crop)
                    use_crop = st.toggle("✂️ 자르기 모드 (Crop Mode)", value=st.session_state.cropping, key="toggle_crop")
                    st.session_state.cropping = use_crop # Sync state
                    
                    cropped_img = None
                    current_crop_id = None
                    
                    if use_crop:
                        st.info("💡 박스 모서리를 드래그하여 변환할 **표(Table)** 영역을 선택하세요.")
                        # Generate a unique key for cropper based on file path to avoid conflicts
                        cropper_key = f"cropper_{os.path.basename(st.session_state.current_file_path)}"
                        
                        cropped_box = st_cropper(
                            img_file=pil_image,
                            realtime_update=True,
                            box_color='#0000FF',
                            aspect_ratio=None,
                            key=cropper_key,
                            return_type='box'
                        )
                        if cropped_box:
                            current_crop_id = (cropped_box['left'], cropped_box['top'], cropped_box['width'], cropped_box['height'])
                            cropped_img = pil_image.crop((
                                cropped_box['left'], 
                                cropped_box['top'], 
                                cropped_box['left'] + cropped_box['width'], 
                                cropped_box['top'] + cropped_box['height']
                            ))
                        else:
                            cropped_img = pil_image
                    else:
                        cropped_img = pil_image 
                    
                    st.divider()

                    # 4. Action Button
                    if st.button("Convert to Excel", use_container_width=True):
                        # Reset Result State
                        st.session_state.excel_data = None
                        
                        with st.status("Processing...", expanded=True) as status:
                            st.write("🔍 Analyzing Layout with Gemini...")
                            
                            try:
                                # Prepare Image Bytes for API
                                img_byte_arr = io.BytesIO()
                                cropped_img.save(img_byte_arr, format='PNG')
                                final_image_bytes = img_byte_arr.getvalue()

                                # API Call Logic
                                api_key = st.session_state["api_key"]
                                
                                # Robust Model Name Fetching 
                                # Debug: Print loading priority
                                secret_model = st.secrets.get("GEMINI_MODEL_NAME")
                                general_model = st.secrets.get("general", {}).get("GEMINI_MODEL_NAME")
                                env_model = os.getenv("GEMINI_MODEL_NAME")
                                
                                # Priority: Secrets(Top) -> Secrets(General) -> Env -> Default "gemini-3-flash-preview"
                                model_name = secret_model or general_model or env_model or "gemini-3-flash-preview"
                                
                                # Log for debugging
                                print(f"DEBUG: Selected Model Name: {model_name}")
                                print(f"DEBUG: Sources - Top:{secret_model}, General:{general_model}, Env:{env_model}")

                                # Force Override if it's unintentionally picking up the expensive model
                                if "pro" in model_name and "flash" not in model_name:
                                    print(f"WARNING: 'pro' model detected ({model_name}). Fallback to 'gemini-3-flash-preview' for safety.")
                                    model_name = "gemini-3-flash-preview"
                                
                                auth_user_type = st.session_state["auth_user_type"]
                                
                                # Determine Cache Seed (Security: Isolation)
                                if auth_user_type == "master":
                                    cache_seed = "master_shared"
                                else:
                                    # Unique per session/file to avoid cross-user leaks in guest mode
                                    cache_seed = str(uuid.uuid4())

                                # Analyze with Caching
                                structure_data = get_cached_analysis(
                                    image_bytes=final_image_bytes,
                                    mime_type="image/png",
                                    model_name=model_name,
                                    cache_seed=cache_seed,
                                    prompt_version="v1_crop", # Preserving original prompt version
                                    _api_key=api_key
                                )
                                st.write("✅ Layout Analysis Complete!")
                                
                                # Render
                                st.write("📊 Rendering Excel...")
                                excel_file = render_excel(structure_data)
                                
                                # Save Result to Session
                                st.session_state.excel_data = excel_file
                                
                                status.update(label="Conversion Complete!", state="complete", expanded=False)
                                st.rerun() # Refresh to show result in right column
                                
                            except Exception as e:
                                st.error(f"Error during conversion: {str(e)}")
                                status.update(label="Conversion Failed", state="error")
                
                except Exception as e:
                    st.error(f"이미지 로드 실패: {e}")
                    # Fallback to upload if critical error
                    if st.button("다시 업로드"):
                        handle_remove_file()
                        st.rerun()

        # State: ERROR
        elif st.session_state.ui_step == "error":
            with st.container(border=True):
                st.error(f"❌ {st.session_state.error_msg or '알 수 없는 오류'}")
                if st.button("메인으로 돌아가기"):
                    handle_remove_file()
                    st.rerun()

    # --- RIGHT COLUMN: Result ---
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

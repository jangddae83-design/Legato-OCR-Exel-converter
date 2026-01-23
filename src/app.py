import streamlit as st
import os
import sys
import io
import uuid
import time
from pathlib import Path
from PIL import Image, ImageOps

# Fix for ModuleNotFoundError: Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.analyzer_service import analyze_image
from src.core.excel_service import render_excel
from src.utils import auth_utils, file_utils, pdf_utils
from streamlit_cropper import st_cropper

# --- Caching Wrapper ---
@st.cache_data(show_spinner=False, ttl=3600, max_entries=100)
def get_cached_analysis(image_bytes: bytes, mime_type: str, model_name: str, cache_seed: str, prompt_version: str, _api_key: str):
    """
    Cached wrapper for image analysis.
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

    # --- PDF State ---
    if "is_pdf" not in st.session_state:
        st.session_state.is_pdf = False
    if "pdf_page_count" not in st.session_state:
        st.session_state.pdf_page_count = 0
    if "current_page_idx" not in st.session_state:
        st.session_state.current_page_idx = 0

def handle_file_upload_secure():
    """
    Handle file upload with enhanced security via file_utils.
    """
    # 0. Cleanup Old Session Files if any (Optional policy)
    # For this simple app, we just ensure we have a fresh start for the new file.
    if st.session_state.current_file_path:
        p = Path(st.session_state.current_file_path)
        if p.exists():
            # Try to remove the parent UUID folder of the file
            file_utils.safe_remove(p.parent)

    uploaded = st.session_state.get(st.session_state.uploader_key)
    
    if uploaded:
        try:
            # 1. Save File (Secure Copy)
            saved_path = file_utils.save_uploaded_file(uploaded)
            
            # 2. Validate Type (Image vs PDF)
            file_type = file_utils.validate_file(saved_path)
            
            # 3. PDF Processing
            if file_type == "pdf":
                # PDF Validation
                pdf_utils.validate_pdf(saved_path)
                
                # Get Info
                info = pdf_utils.get_pdf_info(saved_path)
                st.session_state.is_pdf = True
                st.session_state.pdf_page_count = info["page_count"]
                st.session_state.current_page_idx = 0
            else:
                st.session_state.is_pdf = False
                st.session_state.pdf_page_count = 0
            
            # Update State
            st.session_state.current_file_path = str(saved_path)
            st.session_state.current_file_name = uploaded.name
            st.session_state.ui_step = "process"
            st.session_state.error_msg = None
            
        except Exception as e:
            # Error State
            st.session_state.error_msg = f"Error: {str(e)}"
            st.session_state.ui_step = "error"
            # Cleanup failed file if path exists
            if 'saved_path' in locals() and saved_path.exists():
                 file_utils.safe_remove(saved_path.parent)

def handle_remove_file():
    """Reset to upload state and cleanup resources."""
    if st.session_state.current_file_path:
        p = Path(st.session_state.current_file_path)
        if p.exists():
            file_utils.safe_remove(p.parent)
            
    st.session_state.current_file_path = None
    st.session_state.current_file_name = None
    st.session_state.excel_data = None
    st.session_state.cropping = False
    st.session_state.error_msg = None
    st.session_state.is_pdf = False
    
    # Reset Uploader Widget
    st.session_state.uploader_key = str(uuid.uuid4())
    st.session_state.ui_step = "upload"

# --- Main App ---
def main():
    # Startup Cleanup (Run once per thread/process approx)
    # In Streamlit, this runs on every script rerun, but the function inside has checks.
    # To be strictly 'once', we would need a lock or singleton, but simplified check is okay.
    file_utils.cleanup_stale_files(file_utils.get_session_temp_dir())

    st.set_page_config(
        page_title="Smart Layout OCR (S-LOE)",
        page_icon="📄",
        layout="wide"
    )

    # Custom CSS
    st.markdown("""
    <style>
        .main-header { font-family: 'Inter', sans-serif; color: #1a73e8; text-align: center; font-weight: 700; }
        .sub-header { font-family: 'Inter', sans-serif; color: #5f6368; text-align: center; margin-bottom: 2rem; }
        .stButton>button { background-color: #1a73e8; color: white; border-radius: 20px; padding: 0 20px; width: 100%; } 
        .error-box { padding: 1rem; background-color: #ffebee; border-radius: 8px; color: #c62828; }
        
        [data-testid="stFileUploader"] { padding-top: 0; }
        [data-testid="stFileUploaderDropzone"] {
            min-height: 314px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            border: 1px dashed #ccc;
            border-radius: 8px;
        }
        [data-testid="stFileUploader"] ul { display: none; }
        [data-testid="stFileUploaderDropzoneInstructions"] > div:nth-child(1) > span:nth-child(2) {
           visibility: hidden;
           height: 0;
           display: block;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] > div:nth-child(1) > span:nth-child(2)::before {
            content: "지원 형식: PNG, JPG, JPEG, WEBP, PDF (Max 20MB)";
            visibility: visible;
            display: block;
            height: auto;
            color: #757575; 
            font-size: 14px;
            margin-top: 10px; 
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 class='main-header'>Smart Layout OCR to Excel</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Gemini 2.5 Flash Lite Powered Document Digitization</p>", unsafe_allow_html=True)

    # 1. Initialize Auth & State
    auth_utils.init_auth_state()
    init_session_state()

    # 2. Sidebar
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

    # 3. Validation
    if not st.session_state["auth_status"]:
        st.markdown("<div style='text-align: center; margin-top: 50px;'><h3>🔒 Access Restricted</h3></div>", unsafe_allow_html=True)
        return

    # 4. Split Layout
    col1, col2 = st.columns([1, 1], gap="medium")

    with col1:
        st.write("### 📤 문서 업로드")
        
        if st.session_state.ui_step == "upload":
            with st.container(border=True):
                st.file_uploader(
                    "Upload Document", 
                    type=['png', 'jpg', 'jpeg', 'webp', 'pdf'],
                    key=st.session_state["uploader_key"],
                    on_change=handle_file_upload_secure
                )
                st.info("지원 형식: PNG, JPG, WEBP, PDF (Max 20MB)")

        elif st.session_state.ui_step == "process":
            if not st.session_state.current_file_path or not os.path.exists(st.session_state.current_file_path):
                st.warning("⚠️ 파일이 만료되었습니다.")
                handle_remove_file()
                st.rerun()

            with st.container(border=True):
                col_h1, col_h2 = st.columns([0.85, 0.15])
                with col_h1:
                    st.write(f"📄 **{st.session_state.current_file_name}**")
                with col_h2:
                    if st.button("🗑️", help="파일 제거"):
                        handle_remove_file()
                        st.rerun()

                try:
                    # --- Image / PDF Rendering Logic ---
                    pil_image = None
                    file_path_obj = Path(st.session_state.current_file_path)

                    if st.session_state.is_pdf:
                        # PDF Page Selector
                        total_pages = st.session_state.pdf_page_count
                        if total_pages > 1:
                            page_num = st.slider("페이지 선택 (Page)", 1, total_pages, value=st.session_state.current_page_idx + 1)
                            st.session_state.current_page_idx = page_num - 1
                        else:
                            st.session_state.current_page_idx = 0
                            st.caption("단일 페이지 PDF (Page 1/1)")

                        # Render
                        img_bytes = pdf_utils.render_pdf_page(file_path_obj, st.session_state.current_page_idx)
                        pil_image = Image.open(io.BytesIO(img_bytes))
                    else:
                        # Standard Image
                        pil_image = Image.open(file_path_obj)

                    st.image(pil_image, use_container_width=True)

                    # --- Crop & Process ---
                    use_crop = st.toggle("✂️ 자르기 모드 (Crop)", value=st.session_state.cropping, key="toggle_crop")
                    st.session_state.cropping = use_crop
                    
                    cropped_img = None
                    current_crop_id = None
                    
                    if use_crop:
                        # Unique key per page to reset crop box when page changes
                        cropper_key = f"cropper_{file_path_obj.name}_{st.session_state.current_page_idx}"
                        
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

                    # Convert Button
                    # Prevent Double Click (Optimization)
                    if st.button("Convert to Excel", use_container_width=True):
                        st.session_state.conversion_result = None
                        st.session_state.result_meta = None
                        
                        with st.status("Processing...", expanded=True) as status:
                            st.write("🔍 Analyzing Layout...")
                            try:
                                img_byte_arr = io.BytesIO()
                                cropped_img.save(img_byte_arr, format='PNG')
                                final_image_bytes = img_byte_arr.getvalue()

                                # Model selection logic
                                secret_model = st.secrets.get("GEMINI_MODEL_NAME")
                                env_model = os.getenv("GEMINI_MODEL_NAME")
                                model_name = secret_model or env_model or "gemini-2.5-flash-lite"
                                
                                cache_seed = "master_shared" if st.session_state["auth_user_type"] == "master" else str(uuid.uuid4())
                                
                                structure_data = get_cached_analysis(
                                    image_bytes=final_image_bytes,
                                    mime_type="image/png",
                                    model_name=model_name,
                                    cache_seed=cache_seed,
                                    prompt_version="v1_crop",
                                    _api_key=st.session_state["api_key"]
                                )
                                
                                st.write("✅ Layout Analysis Complete!")
                                conversion_output = render_excel(structure_data)
                                
                                st.session_state.conversion_result = conversion_output
                                st.session_state.result_meta = {
                                    "file_id": st.session_state.current_file_path,
                                    "page_idx": st.session_state.current_page_idx,
                                    "crop_id": current_crop_id,
                                    "timestamp": time.time()
                                }
                                status.update(label="Conversion Complete!", state="complete", expanded=False)
                                st.rerun()

                            except Exception as e:
                                st.error(f"Conversion Error: {str(e)}")
                                status.update(label="Failed", state="error")

                except Exception as e:
                    st.error(f"Load Error: {str(e)}")
                    if st.button("Reset"):
                        handle_remove_file()
                        st.rerun()

        elif st.session_state.ui_step == "error":
            with st.container(border=True):
                st.error(f"❌ {st.session_state.error_msg}")
                if st.button("Back"):
                    handle_remove_file()
                    st.rerun()

    with col2:
        st.write("### 📊 결과 (Result)")
        
        result_data = st.session_state.get("conversion_result")
        result_meta = st.session_state.get("result_meta")
        
        is_valid = False
        if result_data and result_meta and st.session_state.current_file_path:
             # Validate File ID and Page Index
             if (result_meta.get("file_id") == st.session_state.current_file_path and 
                 result_meta.get("page_idx", 0) == st.session_state.get("current_page_idx", 0)):
                 is_valid = True
        
        if is_valid:
            st.success(f"변환 완료! ({result_data.row_count} Rows)")
            st.download_button(
                label="📥 Download Excel (.xlsx)",
                data=result_data.excel_bytes,
                file_name="Converted_Table.xlsx",
                key="download_btn",
                use_container_width=True
            )
            st.divider()
            st.caption("Preivew (Top 50 Rows)")
            st.dataframe(result_data.preview_df, use_container_width=True, height=400)
            
            # AGPL License Notice (Mandatory update)
            st.divider()
            st.caption("Powered by **PyMuPDF** (AGPL) & **Google Gemini**")

        if not is_valid:
            st.markdown("""
            <div style='text-align: center; padding: 40px 20px; border: 2px dashed #e0e0e0; border-radius: 10px; color: #757575; margin-top: 20px;'>
                <div style='font-size: 40px; margin-bottom: 10px;'>👈</div>
                <h4>Ready to Convert</h4>
                <p>Upload a file and click [Convert to Excel].</p>
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

import streamlit as st
import os
from dotenv import load_dotenv
from src.core.analyzer_service import analyze_image
from src.core.excel_service import render_excel

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="Smart Layout OCR (S-LOE)",
    page_icon="📄",
    layout="centered"
)

# Custom CSS for "Professional" look
st.markdown("""
<style>
    .main-header {
        font-family: 'Inter', sans-serif;
        color: #1a73e8; /* Google Blue */
        text-align: center;
        font-weight: 700;
    }
    .sub-header {
        font-family: 'Inter', sans-serif;
        color: #5f6368;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        background-color: #1a73e8;
        color: white;
        border-radius: 20px;
        padding-left: 20px;
        padding-right: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-header'>Smart Layout OCR to Excel</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Gemini 3 Pro Powered Document Digitization</p>", unsafe_allow_html=True)

# API Key Check
if not os.getenv("GEMINI_API_KEY"):
    st.warning("⚠️ GEMINI_API_KEY not found in environment variables. Using MOCK mode.")
    api_key_input = st.text_input("Enter Gemini API Key (Optional for Mock)", type="password")
    if api_key_input:
        os.environ["GEMINI_API_KEY"] = api_key_input

uploaded_file = st.file_uploader("Upload Document Image", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    # Preview
    st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
    
    if st.button("Convert to Excel"):
        with st.status("Processing...", expanded=True) as status:
            st.write("🔍 Analyzing Layout with Gemini...")
            image_bytes = uploaded_file.getvalue()
            
            try:
                layout_data = analyze_image(image_bytes)
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
                st.error(f"Failed to convert: {str(e)}")

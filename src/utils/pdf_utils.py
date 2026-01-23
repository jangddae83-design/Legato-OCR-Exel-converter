import fitz  # pymupdf
import io
import streamlit as st
from pathlib import Path
from PIL import Image
from src.utils.file_utils import MAX_IMAGE_PIXELS

PDF_PAGE_LIMIT = 10

def validate_pdf(file_path: Path):
    """
    Validates a PDF file:
    1. Checks if it's password protected.
    2. Checks page count limit.
    3. Checks for simple corruption.
    """
    try:
        # fitz.open will raise exception if not a valid document
        with fitz.open(file_path) as doc:
            # 1. Check Encryption
            if doc.needs_pass:
                raise ValueError("Password protected PDFs are not supported.")
            
            # 2. Check Page Count
            if doc.page_count > PDF_PAGE_LIMIT:
                raise ValueError(f"PDF exceeds page limit ({doc.page_count}/{PDF_PAGE_LIMIT}). Please upload a smaller file.")
                
            # 3. Check for JS (Security Risk)
            # Check catalog for JavaScript keys
            catalog_xref = doc.pdf_catalog()
            if catalog_xref > 0:
                catalog_str = doc.xref_object(catalog_xref)
                if "/JavaScript" in catalog_str or "/JS" in catalog_str:
                     raise ValueError("PDF contains Javascript which is restricted for security.")

    except fitz.FileDataError:
        raise ValueError("Invalid or corrupted PDF file.")
    except Exception as e:
        # Re-raise known ValueErrors, wrap others
        if isinstance(e, ValueError):
            raise e
        raise ValueError(f"PDF Validation Error: {str(e)}")

def get_pdf_info(file_path: Path) -> dict:
    """
    Returns basic info about the PDF.
    """
    try:
        with fitz.open(file_path) as doc:
            return {
                "page_count": doc.page_count,
                "is_encrypted": doc.is_encrypted
            }
    except Exception:
        return {"page_count": 0, "is_encrypted": False}

@st.cache_data(ttl=3600, max_entries=20)
def render_pdf_page(file_path: Path, page_index: int, dpi: int = 200) -> bytes:
    """
    Renders a specific page of a PDF to PNG bytes.
    Cached to improve performance on re-renders/crops.
    """
    try:
        doc = fitz.open(file_path)
        
        if page_index < 0 or page_index >= doc.page_count:
            raise ValueError("Invalid page index.")
            
        page = doc.load_page(page_index)
        
        # Calculate expected pixels safely
        # Default 72 DPI. Scaling factor = dpi / 72
        scale = dpi / 72.0
        rect = page.rect
        expected_width = rect.width * scale
        expected_height = rect.height * scale
        expected_pixels = expected_width * expected_height * 3 # 3 channels (RGB) approx for memory
        
        # Bomb Protection
        if expected_width * expected_height > MAX_IMAGE_PIXELS:
            # Auto-downscale strategy
            # Calculate safe scale
            safe_scale = (MAX_IMAGE_PIXELS / (rect.width * rect.height)) ** 0.5
            scale = min(scale, safe_scale)
            # st.toast not callable inside cache function efficiently, 
            # effectively logic handles silent resize to safe limit.
        
        matrix = fitz.Matrix(scale, scale)
        
        # Rotation handling: 
        # fitz automatically handles page.rotation in get_pixmap if not overridden.
        # We ensure it's used.
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        img_bytes = pix.tobytes("png")
        
        # Explicit Clean-up
        pix = None
        doc.close()
        
        return img_bytes

    except Exception as e:
        if 'doc' in locals():
            try:
                doc.close()
            except:
                pass
        raise ValueError(f"Failed to render page: {str(e)}")

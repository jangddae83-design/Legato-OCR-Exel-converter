from PIL import Image, UnidentifiedImageError
import io
import streamlit as st
import warnings
from typing import Tuple, Optional

# Constants
MAX_IMAGE_PIXELS = 80_000_000 # 80MP (Limit decompression bombs)
MAX_FILE_SIZE_MB = 20
ALLOWED_MIME_TYPES = ["image/png", "image/jpeg", "image/jpg", "image/webp"]

# Global Safety Configuration (Applies on Import)
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
warnings.simplefilter('error', Image.DecompressionBombWarning)

def validate_and_process_image(uploaded_file) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """
    Validates the uploaded image file.
    
    Checks:
    1. File size.
    2. Format (using PIL verify).
    3. Decompression Bomb risk.
    
    Returns:
    (image_bytes, mime_type, error_message)
    """
    # 1. Check File Size (Streamlit usually limits this, but good to double check)
    if uploaded_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        return None, None, f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB."

    try:
        # Read bytes
        image_bytes = uploaded_file.getvalue()
        
        # 2. Content-based Validation (PIL)
        # Open image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        
        # Verify (checks headers and structural integrity)
        image.verify()
        
        # 3. Determine MIME type based on format (detected by PIL)
        # Re-open is required after verify() because verify() consumes the file pointer
        # Note: image.format is available after open()
        fmt = image.format.lower() if image.format else "unknown"
        
        # Map PIL format to MIME
        mime_map = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "webp": "image/webp"
        }
        
        mime_type = mime_map.get(fmt)
        
        if not mime_type:
            return None, None, f"Unsupported image format detected: {fmt}. Please upload PNG or JPG."
            
        return image_bytes, mime_type, None

    except Image.DecompressionBombWarning:
        return None, None, "Security Error: Image exceeds pixel limit (Potential Decompression Bomb)."
    except UnidentifiedImageError:
        return None, None, "Invalid image file. Could not identify text format."
    except Exception as e:
        return None, None, f"Image validation failed: {str(e)}"

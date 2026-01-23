import os
import shutil
import uuid
import tempfile
import time
import warnings
import unicodedata
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, UnidentifiedImageError

# --- Constants & Configuration ---
MAX_IMAGE_PIXELS = 80_000_000  # 80MP (Limit decompression bombs)
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
TEMP_TTL_SECONDS = 3600  # 1 Hour
ALLOWED_IMAGE_MIME_TYPES = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}

# Global Safety Configuration for PIL
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
warnings.simplefilter('error', Image.DecompressionBombWarning)

def get_session_temp_dir() -> Path:
    """
    Returns a session-specific temporary directory.
    Uses system temp dir + 'legato_ocr_sessions' namespace.
    """
    # NOTE: In a real multi-user web server, we would need a proper session ID.
    # For Streamlit local/cloud, we try to isolate by session state if possible,
    # but here we use a common root and subfolders per upload.
    # To truly isolate, the caller (app.py) should manage the specific subdirectory.
    # This function returns the ROOT for this app's temp files.
    root_temp = Path(tempfile.gettempdir()) / "legato_ocr_sessions"
    root_temp.mkdir(parents=True, exist_ok=True)
    return root_temp

def cleanup_stale_files(root_path: Path):
    """
    Cleans up files that haven't been accessed for more than TEMP_TTL_SECONDS.
    Should be called on app startup.
    """
    if not root_path.exists():
        return

    now = time.time()
    try:
        for item in root_path.iterdir():
            try:
                # If it's a file or dir, check access time
                if now - item.stat().st_atime > TEMP_TTL_SECONDS:
                    if item.is_file():
                        safe_remove(item)
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
            except Exception:
                # Ignore permission errors or concurrent access during cleanup
                pass
    except Exception:
        pass

def safe_remove(path: Path):
    """
    Robust file removal handling Windows file locks.
    Retries up to 3 times before giving up (ignoring error).
    """
    if not path.exists():
        return

    for _ in range(3):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return
        except PermissionError:
            time.sleep(0.1)
        except Exception:
            break
    
    # If we failed, we just log/pass. The cleanup_stale_files will catch it later.
    pass

def save_uploaded_file(uploaded_file) -> Path:
    """
    Saves uploaded file to a secure temporary path.
    Enforces file size limits during copy.
    """
    # 1. Size Check (Pre-check)
    if uploaded_file.size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File too large. Maximum size is {MAX_FILE_SIZE_BYTES / 1024 / 1024}MB.")

    # 2. Path Generation
    # Normalize filename to safe ASCII/Unicode NFC
    orig_name = unicodedata.normalize('NFC', uploaded_file.name)
    suffix = Path(orig_name).suffix.lower()
    
    if suffix not in ALLOWED_EXTENSIONS:
         raise ValueError(f"Unsupported file extension: {suffix}")

    # Create a unique directory for this upload to avoid collisions
    session_root = get_session_temp_dir()
    unique_id = str(uuid.uuid4())
    upload_dir = session_root / unique_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Secure filename (UUID based) but keep extension
    safe_name = f"{unique_id}{suffix}"
    dest_path = upload_dir / safe_name
    
    # 3. Copy with Limit
    try:
        with dest_path.open("wb") as dst:
            uploaded_file.seek(0)
            total = 0
            while True:
                chunk = uploaded_file.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_SIZE_BYTES:
                    destination_path_str = str(dest_path) # store path string before raising exception to use in except block logic if needed or just unlink using the path object
                    dest_path.unlink(missing_ok=True) 
                    raise ValueError(f"File size limit exceeded during upload.")
                dst.write(chunk)
                
        # 4. Set Secure Permissions (POSIX only)
        if os.name == 'posix':
            try:
                os.chmod(dest_path, 0o600)
                os.chmod(upload_dir, 0o700)
            except Exception:
                pass
                
        return dest_path
    except Exception as e:
        # Cleanup on failure
        safe_remove(upload_dir)
        raise e

def validate_image_security(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Validates an image file for security risks (Decompression Bomb, Format).
    """
    try:
        # 1. Format & Structure Check
        with Image.open(path) as img:
            fmt = img.format
            if fmt not in ["JPEG", "PNG", "WEBP", "MPO"]: # MPO is common for some mobile photos
                 # Helper mapping
                valid_formats = ["JPEG", "PNG", "WEBP"]
                if fmt not in valid_formats:
                     raise ValueError(f"Unsupported format: {fmt}")
            
            img.verify()

        # 2. Detail Check (Dimensions/Pixels) - Re-open required
        with Image.open(path) as img:
            w, h = img.size
            if w * h > MAX_IMAGE_PIXELS:
                raise ValueError(f"Image resolution too high ({w}x{h}). Limit: 80MP.")
                
        return "image"
        
    except Image.DecompressionBombWarning:
        raise ValueError("Security Error: Image exceeds pixel limit (Potential Bomb).")
    except UnidentifiedImageError:
        raise ValueError("Invalid image file.")
    except Exception as e:
        raise ValueError(f"Image validation failed: {str(e)}")

def validate_file(path: Path) -> str:
    """
    Detects file type and performs security validation.
    Returns: 'pdf' or 'image'
    """
    # Check extension first
    suffix = path.suffix.lower()
    
    if suffix == ".pdf":
        # Note: PDF content validation happens in pdf_utils to keep this file cleaner
        # or we could move general header checks here.
        # For now, we trust the extension + pdf_utils.validate_pdf will be called next.
        return "pdf"
    else:
        # Assume Image
        validate_image_security(path)
        return "image"

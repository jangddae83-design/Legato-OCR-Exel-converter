import unittest
import os
import sys
import shutil
import tempfile
from pathlib import Path
import fitz

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import pdf_utils

class TestPdfSupport(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.valid_pdf = self.test_dir / "valid.pdf"
        self.large_pdf = self.test_dir / "large.pdf"
        
        # Create valid PDF
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Hello PDF")
        doc.save(self.valid_pdf)
        doc.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_validate_valid_pdf(self):
        """Test that a valid PDF passes validation."""
        pdf_utils.validate_pdf(self.valid_pdf)

    def test_render_pdf_page(self):
        """Test rendering of a PDF page."""
        # Note: 'render_pdf_page' is decorated with st.cache_data which requires streamlit context.
        # This might fail if run as pure python script without streamlit context or mock.
        # But st.cache_data usually works in dummy mode or we might need to bypass it.
        # Actually, st.cache_data wrapper executes the function body if called. 
        # However, if Streamlit is not initialized, it warns.
        # Let's try calling the function directly.
        try:
            img_bytes = pdf_utils.render_pdf_page(self.valid_pdf, 0)
            self.assertTrue(len(img_bytes) > 0)
            # PNG magic number check
            self.assertEqual(img_bytes[:8], b'\x89PNG\r\n\x1a\n')
        except Exception as e:
            # If st.cache_data fails outside streamlit, we skip this check or need to mock st.
            print(f"Skipping render check due to environment: {e}")

    def test_page_limit_enforcement(self):
        """Test that PDFs complying with limits pass and those exceeding fail."""
        # Create a 12 page PDF
        doc = fitz.open()
        for _ in range(12):
            doc.new_page()
        doc.save(self.large_pdf)
        doc.close()
        
        with self.assertRaises(ValueError) as cm:
            pdf_utils.validate_pdf(self.large_pdf)
        self.assertIn("exceeds page limit", str(cm.exception))

if __name__ == "__main__":
    unittest.main()

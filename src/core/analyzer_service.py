import os
import json
import google.generativeai as genai
from typing import Optional
from src.core.models import TableLayout, CellData
import typing_extensions as typing
import threading

# Global Lock for API Safety
API_LOCK = threading.Lock()

# Fallback/Mock response for testing without API key
MOCK_RESPONSE = {
    "cells": [
        {"row_index": 0, "col_index": 0, "row_span": 1, "col_span": 2, "text": "Header Merged"},
        {"row_index": 1, "col_index": 0, "row_span": 1, "col_span": 1, "text": "Row 1 Col 1"},
        {"row_index": 1, "col_index": 1, "row_span": 1, "col_span": 1, "text": "Row 1 Col 2"},
    ]
}

ANALYSIS_PROMPT = """
Analyze this image containing a table working as a Optical Character Recognition (OCR) engine. 
Extract the table structure and content into a JSON format.
Return an object satisfying the `TableLayout` schema.

For each cell:
- Identify the text content.
- Identify the starting row_index and col_index (0-based).
- Identify row_span and col_span. You MUST provide these values for every cell (use 1 for single cells).
- If a cell is merged, only output it once with the correct span.

Ensure all visible text is captured.
"""

def analyze_image(image_bytes: bytes, mime_type: str = "image/png", model_name: str = "gemini-1.5-pro", api_key: Optional[str] = None) -> TableLayout:
    """
    Analyzes the image using Gemini 3 Pro and returns the structural layout.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        print("Warning: No API Key provided. Returning mock data.")
        return TableLayout(**MOCK_RESPONSE)
    # Structured output configuration
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=TableLayout,
        max_output_tokens=65536 # Increase token limit for large tables
    )

    try:
        # Prepare image parts (Outside Lock to save time)
        image_part = {
            "mime_type": mime_type, 
            "data": image_bytes
        }
        
        # CRITICAL: Serialized API Access for Thread Safety
        # genai.configure() is global. We must lock to prevent one user's key from being used by another's request.
        if API_LOCK.acquire(timeout=30):
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name)
                
                response = model.generate_content(
                    [ANALYSIS_PROMPT, image_part],
                    generation_config=generation_config
                )
            finally:
                API_LOCK.release()
        else:
            raise TimeoutError("Server is busy. Please try again later.")
        
        json_text = response.text
        # Parse JSON to Pydantic
        return TableLayout.model_validate_json(json_text)
        
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # In a real app, re-raise or handle gracefully
        raise e

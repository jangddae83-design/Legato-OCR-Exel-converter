import os
import json
import google.generativeai as genai
from typing import Optional
from src.core.models import TableLayout, CellData
import typing_extensions as typing
from pydantic import ValidationError
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
You are an expert Optical Character Recognition (OCR) engine specialized in Table and Grid reconstruction.
Analyze the provided image and extract the structure into a JSON object matching the `TableLayout` schema.

**CORE OBJECTIVE**:
Reconstruct the EXACT visual row and column structure of the table, calendar, or grid in the image.
Do NOT output a simple list of text. You MUST infer the 2D grid coordinates.

**CRITICAL INSTRUCTIONS**:
1. **Grid Inference**: 
   - Visualize hidden grid lines especially for designs like **Calendars**, **Forms**, or **Reports**.
   - Items visually aligned vertically MUST have the same `col_index`.
   - Items visually aligned horizontally MUST have the same `row_index`.
2. **Coordinates**:
   - `row_index`: 0-based index from top to bottom.
   - `col_index`: 0-based index from left to right.
   - **WARNING**: Do NOT assign `col_index: 0` to all cells. Spread them out across columns as they appear visually.
3. **Spans**: 
   - Use `row_span` and `col_span` for headers or large blocks of text that cover multiple grid cells.
   - Default to 1 if the cell occupies a single grid unit.
4. **Content**:
   - Capture ALL visible text.
   - Do NOT return `null`. Use empty string `""` for no text.
   - Ensure `row_span` and `col_span` are always integers >= 1.
"""

def analyze_image(image_bytes: bytes, mime_type: str = "image/png", model_name: str = "gemini-2.5-flash-lite", api_key: Optional[str] = None) -> TableLayout:
    """
    Analyzes the image using Gemini 1.5 Flash and returns the structural layout.
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
        # Parse JSON to Pydantic
        return TableLayout.model_validate_json(json_text)

    except ValidationError as e:
        print(f"Validation Error: {e}")
        # Raise a user-friendly error that streamlit can display nicely
        raise ValueError(f"AI 모델이 올바르지 않은 형식을 반환했습니다. (Validation Error)")
        
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # In a real app, re-raise or handle gracefully
        raise e

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from dataclasses import dataclass
import pandas as pd

@dataclass
class ConversionResult:
    """
    Result object containing the generated Excel file and a preview.
    Using a dataclass ensures strict typing and consistent access.
    """
    excel_bytes: bytes
    preview_df: pd.DataFrame
    row_count: int

class CellData(BaseModel):
    """
    Represents a single cell in the extracted table layout.
    """
    # Use Optional + Field(None) to prevent "default" keyword in generated JSON Schema
    # This fixes the "Unknown field for Schema: default" error from Google GenAI SDK
    text: str = Field(..., description="The text content of the cell")
    row_index: int = Field(..., description="0-based row index")
    col_index: int = Field(..., description="0-based column index")
    row_span: int = Field(..., description="Number of rows this cell spans (must be at least 1)")
    col_span: int = Field(..., description="Number of columns this cell spans (must be at least 1)")

    @model_validator(mode='before')
    @classmethod
    def pre_process_defaults(cls, data: Any) -> Any:
        """
        Pre-process raw input to handle 'null' or missing fields from AI.
        This allows 'Strict Schema' for API (no defaults) but 'Loose Parsing' for runtime (safe defaults).
        """
        if isinstance(data, dict):
            # 1. Text Field Safe Guard
            if 'text' not in data or data.get('text') is None:
                 data['text'] = ""
            
            # 2. Span Field Safe Guard
            for field in ['row_span', 'col_span']:
                if field not in data or data.get(field) is None:
                    data[field] = 1
            
            # 3. Index Field Safe Guard
            for field in ['row_index', 'col_index']:
                if field not in data or data.get(field) is None:
                    data[field] = 0
                    
        return data

    @model_validator(mode='after')
    def set_defaults(self):
        """
        Enforce strict types for application logic after parsing.
        """
        # Ensure spans are at least 1
        if self.row_span < 1:
            self.row_span = 1
        if self.col_span < 1:
            self.col_span = 1
        return self

class TableLayout(BaseModel):
    """
    Represents the full structure of the table.
    """
    cells: List[CellData] = Field(..., description="List of all cells in the table")
    
    @property
    def max_rows(self) -> int:
        if not self.cells:
            return 0
        return max(c.row_index + c.row_span for c in self.cells)

    @property
    def max_cols(self) -> int:
        if not self.cells:
            return 0
        return max(c.col_index + c.col_span for c in self.cells)

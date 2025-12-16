from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class CellData(BaseModel):
    """
    Represents a single cell in the extracted table layout.
    """
    text: str = Field(..., description="The text content of the cell")
    row_index: int = Field(..., description="0-based row index")
    col_index: int = Field(..., description="0-based column index")
    row_span: int = Field(..., description="Number of rows this cell spans (must be at least 1)")
    col_span: int = Field(..., description="Number of columns this cell spans (must be at least 1)")
    # style_hints temporarily removed to prevent schema default value errors

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

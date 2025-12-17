from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Border, Side, Alignment
from src.core.models import TableLayout

def render_excel(layout: TableLayout) -> bytes:
    """
    Converts a TableLayout into an Excel file (bytes).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Converted Table"
    
    # Common styles
    thin_border = Border(
        left=Side(style='thin'), 
        right=Side(style='thin'), 
        top=Side(style='thin'), 
        bottom=Side(style='thin')
    )
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    for cell in layout.cells:
        # 1-based indexing for openpyxl
        r = cell.row_index + 1
        c = cell.col_index + 1
        
        # Write text
        curr_cell = ws.cell(row=r, column=c, value=cell.text)
        
        # Apply style
        curr_cell.border = thin_border
        curr_cell.alignment = center_align
        
        # Merge if needed
        if cell.row_span > 1 or cell.col_span > 1:
            end_r = r + cell.row_span - 1
            end_c = c + cell.col_span - 1
            ws.merge_cells(start_row=r, start_column=c, end_row=end_r, end_column=end_c)
            
            # Re-apply border to the merged range (openpyxl sometimes needs this)
            # For simplicity, we just formatted the top-left logic above. 
            # Ideally verify borders on edges of merged range.
    
    from openpyxl.utils import get_column_letter
    
    # Auto-adjust column widths (rough approximation)
    for col in ws.columns:
        max_length = 0
        # col is a tuple of cells. Even if merged, openpyxl iterates them.
        # But 'MergedCell' objects don't have all attributes.
        # Safest way: get letter from the index of the first cell (which implies column index).
        column = get_column_letter(col[0].column)
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = min(adjusted_width, 50) # Cap at 50

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()

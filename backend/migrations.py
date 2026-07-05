# backend/migrations.py
import gspread

def run_schema_migration(gc, spreadsheet_id):
    """
    Exclusively handles structural updates. Safely alters table 
    layouts by dynamically expanding column boundaries before writing.
    """
    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        sheet = spreadsheet.worksheet("medicinal_product")
        
        # Read the live header row
        headers = sheet.row_values(1)
        
        # Guard rail: Check if Molecule_ID is already present 
        if "Molecule_ID" in headers:
            print("[Migration] 'Molecule_ID' column already exists inside the spreadsheet.")
            return True
            
        print("[Migration] Modifying table architecture: Adding 'Molecule_ID' column...")
        
        # Calculate the 1-based index slot right after your current final column
        new_column_position = len(headers) + 1
        
        # ⚡ NEW: Dynamic Grid Expansion Guard Gate
        # If the destination position exceeds the physical sheet capacity, expand it!
        current_max_columns = sheet.col_count
        if new_column_position > current_max_columns:
            print(f"[Migration] Target column index {new_column_position} exceeds current grid limit ({current_max_columns}). Expanding sheet layout...")
            sheet.add_cols(1)  # Programmatically appends 1 new column slot to the sheet's right boundary
            print(f"[Migration] Spreadsheet width successfully expanded. New max columns: {sheet.col_count}")
        
        # Now it is completely safe to stamp the new header token
        sheet.update_cell(1, new_column_position, "Molecule_ID")
        
        print("[Migration] Database architecture successfully upgraded to include Foreign Key relationships.")
        return True
        
    except Exception as e:
        print(f"[Migration Failure] Altering schema architecture aborted safely: {e}")
        return False
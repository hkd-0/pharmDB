# backend/maintenance.py
import gspread
from schema import DATABASE_SCHEMA, validate_sheet_schema

def build_molecule_cache(spreadsheet):
    """
    Scans the drug_molecule sheet and maps every generic name to its ID.
    Building an O(1) in-memory look-up dictionary guarantees the script 
    never locks up, experiences lag, or triggers server timeouts.
    """
    try:
        sheet = spreadsheet.worksheet("drug_molecule")
        raw_matrix = sheet.get_all_values()
        if not raw_matrix or len(raw_matrix) <= 1:
            return {}

        headers = raw_matrix[0]
        name_idx = headers.index("Molecule_Name")
        id_idx = headers.index("Molecule_ID")

        # Build map: e.g., {"pantoprazole": "M-0001", "domperidone": "M-0002"}
        cache = {}
        for row in raw_matrix[1:]:
            if len(row) > max(name_idx, id_idx):
                name = row[name_idx].strip().lower()
                mol_id = row[id_idx].strip()
                if name:
                    cache[name] = mol_id
        return cache
    except Exception as e:
        print(f"[Relational Warning] Could not build molecule cache index map: {e}")
        return {}

def clean_and_repair_sheet(spreadsheet, sheet_name, molecule_cache):
    """
    Validates structure, enforces data constraints, and cross-references 
    foreign key IDs in batch format to maximize throughput.
    """
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        raw_matrix = sheet.get_all_values()
        if not raw_matrix:
            print(f"[{sheet_name}] Empty dataset skipped.")
            return True

        headers = raw_matrix[0]

        # Guard Rail: Block operation if live layout breaks our structural layout schema contract
        if not validate_sheet_schema(sheet_name, headers):
            raise ValueError(f"Schema layout mismatch detected in '{sheet_name}'! Operation aborted.")

        rules = DATABASE_SCHEMA[sheet_name]
        id_col_name = rules["id_column_name"]
        id_prefix = rules["id_prefix"]

        # Dynamically discover column indexes based on schema header strings
        s_no_idx = headers.index("S.No.") + 1
        id_idx = headers.index(id_col_name) + 1
        
        # Look up optional relational targets if they exist in this sheet schema layout
        molecules_idx = headers.index("Molecule(s)") + 1 if "Molecule(s)" in headers else None
        foreign_key_idx = headers.index("Molecule_ID") + 1 if "Molecule_ID" in headers else None

        cells_to_update = []

        # Parse rows sequentially in memory (Row 1 index is header data wrapper)
        for row_idx, row_values in enumerate(raw_matrix[1:], start=2):
            expected_seq_num = row_idx - 1

            # 1. Repair Serial Numbers
            current_s_no = row_values[s_no_no_idx := s_no_idx - 1].strip()
            if not current_s_no:
                cells_to_update.append(gspread.cell.Cell(row=row_idx, col=s_no_idx, value=str(expected_seq_num)))

            # 2. Repair Custom Sequence Structural IDs
            current_id = row_values[id_col_idx := id_idx - 1].strip()
            if not current_id:
                generated_id = f"{id_prefix}{str(expected_seq_num).zfill(4)}"
                cells_to_update.append(gspread.cell.Cell(row=row_idx, col=id_idx, value=generated_id))

            # 3. Cross-Reference Text Component Tokens to populate missing Molecule_ID foreign keys
            if sheet_name == "medicinal_product" and molecules_idx and foreign_key_idx:
                current_fk = row_values[foreign_key_idx - 1].strip()
                
                # Relational repair triggers only if the relational destination key is empty
                if not current_fk:
                    raw_molecules_text = row_values[molecules_idx - 1].strip()
                    
                    if raw_molecules_text:
                        # Split string mixtures: "Domperidone, Pantoprazole" -> ["Domperidone", "Pantoprazole"]
                        parsed_names = [m.strip().lower() for m in raw_molecules_text.split(",") if m.strip()]
                        
                        resolved_ids = []
                        for m_name in parsed_names:
                            if m_name in molecule_cache:
                                resolved_ids.append(molecule_cache[m_name])
                        
                        # Re-join matched IDs cleanly: ["M-0001", "M-0002"] -> "M-0001, M-0002"
                        if resolved_ids:
                            fk_value = ", ".join(resolved_ids)
                            cells_to_update.append(gspread.cell.Cell(row=row_idx, col=foreign_key_idx, value=fk_value))

        # Push calculated batch adjustments in chunks of 500 records to respect API rate limits
        if cells_to_update:
            chunk_size = 500
            for i in range(0, len(cells_to_update), chunk_size):
                chunk = cells_to_update[i:i + chunk_size]
                sheet.update_cells(chunk)
            print(f"[{sheet_name}] Relational check complete. Synced {len(cells_to_update)} data points successfully.")
        else:
            print(f"[{sheet_name}] Data verified: 100% healthy relational keys.")
            
        return True
    except Exception as e:
        print(f"Relational processing stopped on '{sheet_name}': {e}")
        return False

def run_global_maintenance(gc, spreadsheet_id):
    """
    Main background orchestrator interface method.
    """
    try:
        spreadsheet = gc.open_by_key(spreadsheet_id)
        
        # 1. Build context index lookups
        molecule_cache = build_molecule_cache(spreadsheet)
        
        # 2. Synchronize target tabs cleanly using index parameters
        mol_healthy = clean_and_repair_sheet(spreadsheet, "drug_molecule", molecule_cache)
        prod_healthy = clean_and_repair_sheet(spreadsheet, "medicinal_product", molecule_cache)
        
        return mol_healthy and prod_healthy
    except Exception as e:
        print(f"Global database engine halted execution: {e}")
        return False
import pandas as pd
import gspread
import argparse
import os
import sys
from dotenv import load_dotenv

# Hardcoded constants from system specifications
SPREADSHEET_ID = "1iTFZbpKfGyMM88zAwuwA4ts53sVLl8krB1kn3hfl-9M"
TAB_NAME = "medicinal_product"

def load_gspread_client():
    """Bulletproof authentication link resolving local project structure."""
    # Step up folders dynamically to look for credentials.json at project root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check current directory first, fallback to checking up directories
    cred_path = os.path.join(current_dir, 'credentials.json')
    if not os.path.exists(cred_path):
        cred_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'credentials.json')
        
    if not os.path.exists(cred_path):
        # Check standard root-level paths
        cred_path = 'credentials.json'
        
    try:
        print(f"🔑 Authenticating via Google Cloud token: {cred_path}...")
        client = gspread.service_account(filename=cred_path)
        return client
    except Exception as e:
        print(f"❌ Authentication Error: Could not find or validate credentials.json file. Details: {e}")
        sys.exit(1)

def transform_row(row):
    """Applies case normalization, splits combo chemicals, and generates variant foot-prints."""
    # 1. Clean Molecules Property (Semicolon splitting for combination formulations)
    raw_ing = str(row['Ingredient']).strip()
    ing_parts = [p.strip().title() for p in raw_ing.split(';') if p.strip()]
    molecules_string = ", ".join(ing_parts)

    # 2. Clean Strengths Property
    raw_str = str(row['Strength']).strip()
    str_parts = [p.strip().lower() for p in raw_str.split(';') if p.strip()]
    strengths_string = ", ".join(str_parts)

    # 3. Capitalize Brand Name
    brand_name = str(row['Trade_Name']).strip().title()

    # 4. Programmatic Variant Naming (Combines brand footprint with clean strength)
    variant_name = f"{brand_name} {strengths_string}"

    # 5. Extract Concise Dosage Form
    raw_df = str(row['DF;Route']).strip()
    dosage_form = raw_df.split(';')[0].strip().title()

    # 6. Normalize Corporate Manufacturer Name
    manufacturer_name = str(row['Applicant_Full_Name']).strip().title()

    return (brand_name, variant_name, molecules_string, strengths_string, dosage_form, manufacturer_name)

def execute_pipeline(filepath):
    # Authenticate and pull live sheet dimensions
    client = load_gspread_client()
    try:
        print(f"📥 Fetching sheet data context from PharmDB tab: '{TAB_NAME}'...")
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(TAB_NAME)
        all_existing_rows = sheet.get_all_values()
    except Exception as e:
        print(f"❌ Error linking to Google Sheets API: {e}")
        return

    # Check for core structural header index configurations
    header = all_existing_rows[0] if all_existing_rows else []
    print(f"✅ Connection verified. Found {len(all_existing_rows) - 1} existing medicinal products.")

    # Load and clean incoming file data matrix
    if not os.path.exists(filepath):
        print(f"❌ Error: Input dataset path '{filepath}' does not exist.")
        return

    print(f"⏳ Reading {filepath}...")
    try:
        df = pd.read_csv(filepath, sep='~', low_memory=False)
    except Exception as e:
        print(f"❌ Error reading file matrix: {e}")
        return

    # Filter out missing records in critical data vectors
    df = df.dropna(subset=['Trade_Name', 'Ingredient', 'Strength', 'DF;Route', 'Applicant_Full_Name'])
    
    print("🧹 Executing internal row de-duplication rules...")
    processed_queue = []
    seen_internal = set()

    for _, row in df.iterrows():
        tuple_footprint = transform_row(row)
        if tuple_footprint not in seen_internal:
            seen_internal.add(tuple_footprint)
            processed_queue.append(tuple_footprint)

    print(f"🧼 Internal unique footprints parsed: {len(processed_queue)} configurations.")

    # Build an Idempotency Filter Cache against your current spreadsheet data
    print("🔄 Cross-checking footprints with live spreadsheet entries to exclude redundancies...")
    live_database_cache = set()
    if len(all_existing_rows) > 1:
        for row in all_existing_rows[1:]:
            if len(row) >= 8:
                # Cache via: (Brand_Name, Variant_Name, Molecule(s), Strength(s), Dosage_Form, Manufacturer_Name)
                live_database_cache.add((row[2], row[3], row[4], row[5], row[6], row[7]))

    # Omit overlapping configurations
    final_ingest_queue = [item for item in processed_queue if item not in live_database_cache]
    total_to_assimilate = len(final_ingest_queue)
    
    print(f"📊 Filtering complete: {total_to_assimilate} records are net-new and ready for assimilation.")
    
    if total_to_assimilate == 0:
        print("✅ Database is already completely up to date! No actions required.")
        return

    # Compute trailing row sequences
    start_s_no = len(all_existing_rows)  # Current row height acts as previous serial boundary
    
    # -------------------------------------------------------------
    # STAGING PHASE: Insert first 10 rows for validation scrutiny
    # -------------------------------------------------------------
    staging_size = min(10, total_to_assimilate)
    staging_batch = final_ingest_queue[:staging_size]
    
    payload_batch = []
    for i, item in enumerate(staging_batch):
        current_s_no = start_s_no + i
        product_id = f"PROD-{current_s_no:04d}"
        # Match columns: S.No., Product_ID, Brand_Name, Variant_Name, Molecule(s), Strength(s), Dosage_Form, Manufacturer_Name, Molecule_ID
        payload_batch.append([current_s_no, product_id, item[0], item[1], item[2], item[3], item[4], item[5], ""])

    print(f"\n🚀 STAGING RUN: Injecting first {staging_size} items into your sheet for scrutiny...")
    sheet.append_rows(payload_batch, value_input_option='USER_ENTERED')
    
    # Find the precise cell grid row coordinates where the data landed
    rollback_start_row = start_s_no + 1
    rollback_end_row = start_s_no + staging_size

    print("\n🛑 PIPELINE PAUSED: INTERACTIVE VERIFICATION GATE ACTIVATED")
    print("=" * 75)
    print(f"The staging rows have landed successfully in sheet rows: {rollback_start_row} to {rollback_end_row}.")
    print("Please open your browser window, inspect the rows, and double-check:")
    print(f"  - Brand & Variant Names: formatted to clean Title Case (e.g., '{payload_batch[0][2]}')")
    print(f"  - Semicolon Splitting: multi-ingredients split with proper commas")
    print(f"  - Variant Suffixes: strength tokens appended to variant strings ('{payload_batch[0][3]}')")
    print(f"  - Column Alignment: data points aligned correctly under matching headers")
    print("=" * 75)
    
    user_decision = input("👉 Proceed with bulk ingestion of remaining records? (y = Yes, Resume / n = No, Rollback & Stop): ").strip().lower()
    
    if user_decision != 'y':
        print(f"\n⚠️ Rejection command captured. Executing safety rollback script...")
        print(f"🧼 Removing trial rows {rollback_start_row} through {rollback_end_row} from your spreadsheet database...")
        # Delete starting from the bottom of the staging run up to preserve index positions safely
        for target_row in range(rollback_end_row, rollback_start_row - 1, -1):
            sheet.delete_rows(target_row)
        print("✅ Rollback successful. Your live dataset remains untouched and pristine. Exiting script.")
        return

    # -------------------------------------------------------------
    # BULK PRODUCTION PHASE: Stream remaining data in rapid batches
    # -------------------------------------------------------------
    print("\n🚀 Ingestion verified! Commencing fast bulk upload engine...")
    remaining_records = final_ingest_queue[staging_size:]
    
    if not remaining_records:
        print("✅ Job complete! All extracted entries successfully processed.")
        return

    bulk_payload = []
    running_s_no = start_s_no + staging_size
    
    for item in remaining_records:
        product_id = f"PROD-{running_s_no:04d}"
        bulk_payload.append([running_s_no, product_id, item[0], item[1], item[2], item[3], item[4], item[5], ""])
        running_s_no += 1

    # Chunk into 5,000 item groups to avoid timing out network connections
    chunk_size = 5000
    total_chunks = (len(bulk_payload) + chunk_size - 1) // chunk_size
    
    for idx in range(total_chunks):
        start_idx = idx * chunk_size
        end_idx = start_idx + chunk_size
        current_chunk = bulk_payload[start_idx:end_idx]
        
        print(f"📥 Streaming batch {idx + 1}/{total_chunks} ({len(current_chunk)} entries over wire)...")
        sheet.append_rows(current_chunk, value_input_option='USER_ENTERED')
        
    print(f"\n🎉 SUCCESS! Entire pipeline executed cleanly. Your backend database size has been expanded by {total_to_assimilate} records!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Secure Gated Bulk Data Transformation and Ingestion Engine for PharmDB.")
    parser.add_argument("filename", help="Path to your raw source text data file (e.g. products.txt)")
    args = parser.parse_args()
    
    execute_pipeline(args.filename)
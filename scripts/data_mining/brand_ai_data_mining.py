import sys
import time
import json
import os
import gspread
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Load local environment configuration
load_dotenv()

# 1. Clean Local File Authentication & Configuration Extraction
SCOPES = ["[https://www.googleapis.com/auth/spreadsheets](https://www.googleapis.com/auth/spreadsheets)"]
CREDENTIALS_FILE = "credentials.json"

# Extract configuration targets from .env
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Safety checks to ensure .env is correctly filled out
if not SPREADSHEET_ID:
    print("⚠️ Error: SPREADSHEET_ID not found in your .env file.")
    exit()
if not GEMINI_API_KEY:
    print("⚠️ Error: GEMINI_API_KEY not found in your .env file.")
    exit()

# Authenticate with Google Sheets using the local credentials file
try:
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    # Direct Parity: Target the live production brand workspace
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("medicinal_product")
except FileNotFoundError:
    print(f"⚠️ Error: Missing required structural file '{CREDENTIALS_FILE}' in your project root.")
    exit()
except Exception as e:
    print(f"⚠️ Google Sheets Authorization Failure: {e}")
    exit()

# Setup AI Engine securely
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.1-flash-lite')

# 2. File Utilities for Inputs and External Prompts
def read_text_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"⚠️ Error: Could not find file named '{filename}'.")
        return None

def get_lines_from_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print(f"⚠️ Error: Could not find input file named '{filename}'.")
        return []

# Validate Command Line Arguments
if len(sys.argv) < 3:
    print("⚠️ Usage: python production_brand_loader.py <prompt_file.txt> <brands_list.txt>")
    print("👉 Example: python production_brand_loader.py brand_prompt.txt input_brands.txt")
    exit()

prompt_file_path = sys.argv[1]
brands_file_path = sys.argv[2]

base_prompt = read_text_file(prompt_file_path)
all_brands = get_lines_from_file(brands_file_path)

if not base_prompt or not all_brands:
    print("Execution halted due to missing or empty input files.")
    exit()

# 3. Read Existing Data for Strict Deduplication
print("\n📊 Analyzing production tab for existing entries to prevent overlaps...")
existing_records = sheet.get_all_records()
# Duplication lookup matching by the parent brand umbrella name column
existing_brands = {str(row.get('Brand_Name', '')).strip().lower() for row in existing_records}
next_sno = len(existing_records) + 1

# Filter out elements before triggering network processing steps
filtered_brands = [b for b in all_brands if b.strip().lower() not in existing_brands]
skipped_count = len(all_brands) - len(filtered_brands)

if skipped_count > 0:
    print(f"⏭️ Pre-filtered list: Skipping {skipped_count} parent brands already inside your database.")

if not filtered_brands:
    print("🎉 All provided brands are already up to date in production! Exiting gracefully.")
    exit()

# 4. Processing in Large Optimized Batches (Grouped Data Resolution)
# Packs multiple brand names into a single AI prompt lookup operation
BATCH_SIZE = 5 
print(f"🚀 Processing {len(filtered_brands)} brands in optimized chunks of {BATCH_SIZE}...")

for i in range(0, len(filtered_brands), BATCH_SIZE):
    chunk = filtered_brands[i:i + BATCH_SIZE]
    print(f"\n🧠 Querying Gemini to execute batch resolution for: {', '.join(chunk).upper()}")
    
    combined_prompt = f"{base_prompt}\n\nHere is the target list of parent brand names to extract right now:\n{json.dumps(chunk)}"
    
    try:
        response = model.generate_content(combined_prompt)
        raw_text = response.text.strip()
        
        # Strip structural markdown wrap if added by LLM
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json\n", "", 1)
            
        resolved_variants = json.loads(raw_text)
        
        # Matrix box bucket compilation for a single multi-row write update command
        batch_rows_to_upload = []
        
        for variant in resolved_variants:
            brand_name = variant.get("Input_Brand_Name", "Unknown").strip()
            
            # Form relational key sequencing formatting pattern for retail entries: PROD-XXXX
            product_id = f"PROD-{next_sno:04d}"
            
            new_row = [
                next_sno,                           # S.No.
                product_id,                         # Product_ID
                brand_name.capitalize(),            # Brand_Name
                variant.get("Variant_Name", ""),    # Variant_Name
                variant.get("Molecules", ""),       # Molecule(s)
                variant.get("Strengths", ""),       # Strength(s)
                variant.get("Dosage_Form", ""),     # Dosage_Form
                variant.get("Manufacturer_Name", "")# Manufacturer_Name
            ]
            
            batch_rows_to_upload.append(new_row)
            next_sno += 1
            
        if batch_rows_to_upload:
            sheet.append_rows(batch_rows_to_upload)
            print(f"📦 Single-Ping Success: Pushed an optimized packet of {len(batch_rows_to_upload)} brand variants directly to production!")
            
            # Update local duplicate checking sets for each unique input brand verified in this loop pass
            for b in chunk:
                existing_brands.add(b.lower())
        else:
            print("⚠️ No variants extracted from this chunk.")
            
    except Exception as e:
        print(f"⚠️ Batch Pipeline Processing Interrupted: {e}")
        
    # Enforcing strict 15-second tier throttle spacing between major grouped queries to lock down 5 RPM tier limits
    if i + BATCH_SIZE < len(filtered_brands):
        print("⏳ Cooling down for 15 seconds to respect the 5 RPM ceiling...")
        time.sleep(15)

print("\n🎉 Production database population finalized smoothly at maximum efficiency!")
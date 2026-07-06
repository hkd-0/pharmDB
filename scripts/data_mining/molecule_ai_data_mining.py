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
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
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
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("drug_molecule")
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
    print("⚠️ Usage: python production_molecule_loader.py <prompt_file.txt> <molecules_list.txt>")
    print("👉 Example: python production_molecule_loader.py molecule_prompt.txt input_molecules.txt")
    exit()

prompt_file_path = sys.argv[1]
molecules_file_path = sys.argv[2]

base_prompt = read_text_file(prompt_file_path)
all_molecules = get_lines_from_file(molecules_file_path)

if not base_prompt or not all_molecules:
    print("Execution halted due to missing or empty input files.")
    exit()

# 3. Read Existing Data for Strict Deduplication
print("\nAn Analyzing production tab for existing entries to prevent overlaps...")
existing_records = sheet.get_all_records()
existing_names = {str(row.get('Molecule_Name', '')).strip().lower() for row in existing_records}
next_sno = len(existing_records) + 1

# Filter the list before firing any API calls
filtered_molecules = [m for m in all_molecules if m.strip().lower() not in existing_names]
skipped_count = len(all_molecules) - len(filtered_molecules)

if skipped_count > 0:
    print(f"⏭️ Pre-filtered list: Skipping {skipped_count} molecules already inside your database.")

if not filtered_molecules:
    print("🎉 All provided molecules are already up to date in production! Exiting gracefully.")
    exit()

# 4. Processing in Large Optimized Batches (Grouped Data Resolution)
BATCH_SIZE = 5 
print(f"🚀 Processing {len(filtered_molecules)} molecules in optimized chunks of {BATCH_SIZE}...")

for i in range(0, len(filtered_molecules), BATCH_SIZE):
    chunk = filtered_molecules[i:i + BATCH_SIZE]
    print(f"\n🧠 Querying Gemini to execute batch resolution for: {', '.join(chunk).upper()}")
    
    combined_prompt = f"{base_prompt}\n\nHere is the target list of molecules to extract right now:\n{json.dumps(chunk)}"
    
    try:
        response = model.generate_content(combined_prompt)
        raw_text = response.text.strip()
        
        # Strip structural codeblocks if AI wraps JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json\n", "", 1)
            
        resolved_profiles = json.loads(raw_text)
        
        # Build out our matrix block for a single multi-row sheet write
        batch_rows_to_upload = []
        
        for profile in resolved_profiles:
            molecule_name = profile.get("Molecule_Name", "Unknown").strip()
            
            # Double-check to prevent cross-batch anomalies
            if molecule_name.lower() in existing_names:
                continue
                
            molecule_id = f"M-{next_sno:04d}"
            
            new_row = [
                next_sno,
                molecule_id,
                molecule_name.capitalize(),
                profile.get("Pharmacological_Class", ""),
                profile.get("Indications", ""),
                profile.get("Side_Effects", ""),
                profile.get("Contraindications", "")
            ]
            
            batch_rows_to_upload.append(new_row)
            existing_names.add(molecule_name.lower()) # Update local lookup cache
            next_sno += 1
            
        if batch_rows_to_upload:
            sheet.append_rows(batch_rows_to_upload)
            print(f"📦 Single-Ping Success: Pushed an optimized packet of {len(batch_rows_to_upload)} rows to your Sheet!")
        else:
            print("⚠️ No unique rows extracted from this chunk.")
            
    except Exception as e:
        print(f"⚠️ Batch Pipeline Processing Interrupted: {e}")
        
    # Enforcing exact 15-second wait window to keep your pipeline completely free
    if i + BATCH_SIZE < len(filtered_molecules):
        print("⏳ Cooling down for 15 seconds to respect the 5 RPM ceiling...")
        time.sleep(15)

print("\n🎉 Production database population finalized smoothly at maximum efficiency!")
import sys
import time
import json
import os
import gspread
from google import genai
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Load local environment configuration from .env
load_dotenv()

# --- CONFIGURATION ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = "credentials.json"

# Extract configuration targets securely from .env
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
    print("🔑 Authenticating with Google Sheets...")
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    # Target the live production drug_molecule sheet
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("drug_molecule")
    print("✅ Successfully connected to Google Sheets.")
except FileNotFoundError:
    print(f"⚠️ Error: Missing required structural file '{CREDENTIALS_FILE}' in your project root.")
    exit()
except Exception as e:
    print(f"⚠️ Google Sheets Authorization Failure: {e}")
    exit()

# Setup New Gemini AI Client
print("🤖 Initializing Google GenAI Client...")
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3.1-flash-lite" 

# --- UTILITY FUNCTIONS ---

def read_text_file(filename):
    """Safely read prompt or input files."""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"⚠️ Error: Could not find file named '{filename}'.")
        return None

def get_lines_from_file(filename):
    """Read line-by-line inputs."""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print(f"⚠️ Error: Could not find input file named '{filename}'.")
        return []

# --- EXECUTION ---

# Validate Command Line Arguments
if len(sys.argv) < 3:
    print("⚠️ Usage: python molecule_ai_data_mining.py <prompt_file.txt> <molecules_list.txt>")
    print("👉 Example: python molecule_ai_data_mining.py molecule_prompt.txt input_molecules.txt")
    exit()

prompt_file_path = sys.argv[1]
molecules_file_path = sys.argv[2]

base_prompt = read_text_file(prompt_file_path)
all_molecules = get_lines_from_file(molecules_file_path)

if not base_prompt or not all_molecules:
    print("❌ Execution halted: Missing prompt or input list.")
    exit()

# Deduplication logic: Fetch everything once to save API calls
print("\n📊 Analyzing production tab for existing entries to prevent overlaps...")
existing_records = sheet.get_all_records()
# Create a searchable set of molecule names
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

# Processing in Batches of 5 to optimize API throughput
BATCH_SIZE = 5 
print(f"🚀 Processing {len(filtered_molecules)} molecules in optimized chunks of {BATCH_SIZE}...")

for i in range(0, len(filtered_molecules), BATCH_SIZE):
    chunk = filtered_molecules[i:i + BATCH_SIZE]
    print(f"\n🧠 Querying Gemini to execute batch resolution for: {', '.join(chunk).upper()}")
    
    # Bundle inputs for the AI to handle in one go
    combined_prompt = f"{base_prompt}\n\nHere is the target list of molecules to extract right now:\n{json.dumps(chunk)}"
    
    try:
        # Use new GenAI SDK to generate content
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=combined_prompt
        )
        raw_text = response.text.strip()
        
        # Clean potential markdown wrapping from AI output
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json\n", "", 1)
            
        resolved_profiles = json.loads(raw_text)
        
        # Compile row data into a single batch list for efficiency
        batch_rows_to_upload = []
        
        for profile in resolved_profiles:
            molecule_name = profile.get("Molecule_Name", "Unknown").strip()
            
            # Double-check to prevent cross-batch anomalies
            if molecule_name.lower() in existing_names:
                print(f"⏭️ Skipping duplicate found in response: {molecule_name}")
                continue
                
            # Create sequential ID: M-XXXX
            molecule_id = f"M-{next_sno:04d}"
            
            row_data = [
                next_sno,                           # S.No.
                molecule_id,                        # Molecule_ID
                molecule_name.capitalize(),         # Molecule_Name
                profile.get("Pharmacological_Class", ""),
                profile.get("Indications", ""),
                profile.get("Side_Effects", ""),
                profile.get("Contraindications", "")
            ]
            
            batch_rows_to_upload.append(row_data)
            existing_names.add(molecule_name.lower()) # Update local lookup cache
            next_sno += 1
            
        if batch_rows_to_upload:
            sheet.append_rows(batch_rows_to_upload)
            print(f"📦 Success: Pushed an optimized packet of {len(batch_rows_to_upload)} molecule rows to your Sheet!")
        else:
            print("⚠️ No unique rows extracted from this chunk.")
            
    except Exception as e:
        print(f"⚠️ Batch Pipeline Processing Interrupted: {e}")
        
    # Enforcing exact 15-second wait window to keep your pipeline completely free
    if i + BATCH_SIZE < len(filtered_molecules):
        print("⏳ Cooling down for 15 seconds to respect the 5 RPM ceiling...")
        time.sleep(15)

print("\n🎉 Production database population finalized smoothly at maximum efficiency!")
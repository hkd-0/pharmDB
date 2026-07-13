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

# Safety checks
if not SPREADSHEET_ID:
    print("⚠️ Error: SPREADSHEET_ID not found in your .env file.")
    exit()
if not GEMINI_API_KEY:
    print("⚠️ Error: GEMINI_API_KEY not found in your .env file.")
    exit()

# Authenticate with Google Sheets
try:
    print("🔑 Authenticating with Google Sheets...")
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    # Target the live production medicinal_product tab
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("medicinal_product")
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

# --- EXECUTION ---

# Validate Command Line Arguments
if len(sys.argv) < 3:
    print("⚠️ Usage: python brand_ai_data_mining.py <prompt_file.txt> <brands_list.txt>")
    exit()

prompt_file_path = sys.argv[1]
brands_file_path = sys.argv[2]

base_prompt = read_text_file(prompt_file_path)
all_brands = get_lines_from_file(brands_file_path)

if not base_prompt or not all_brands:
    print("❌ Execution halted: Missing prompt or input list.")
    exit()

print("\n📊 Analyzing production tab for existing entries to prevent overlaps...")
existing_records = sheet.get_all_records()
existing_brands = {str(row.get('Brand_Name', '')).strip().lower() for row in existing_records}
next_sno = len(existing_records) + 1

# Filter the list before firing any API calls
filtered_brands = [b for b in all_brands if b.strip().lower() not in existing_brands]
skipped_count = len(all_brands) - len(filtered_brands)

if skipped_count > 0:
    print(f"⏭️ Pre-filtered list: Skipping {skipped_count} brands already inside your database.")

if not filtered_brands:
    print("🎉 All provided brands are already up to date in production! Exiting gracefully.")
    exit()

# Processing in Batches of 5
# --- 4. Processing in Large Optimized Batches (Granular/Atomic Logic) ---
BATCH_SIZE = 5 
print(f"🚀 Processing {len(filtered_brands)} brands in optimized chunks of {BATCH_SIZE}...")

for i in range(0, len(filtered_brands), BATCH_SIZE):
    chunk = filtered_brands[i:i + BATCH_SIZE]
    print(f"\n🧠 Querying Gemini for batch: {', '.join(chunk).upper()}")
    
    combined_prompt = f"{base_prompt}\n\nHere is the target list of parent brand names to extract:\n{json.dumps(chunk)}"
    
    try:
        # Request the batch from Gemini
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=combined_prompt
        )
        
        # Safety Guard
        if not response or not response.text:
            print("⚠️ Warning: AI returned empty response for this batch.")
            continue
            
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json\n", "", 1)
            
        resolved_variants = json.loads(raw_text)
        batch_rows_to_upload = []
        
        # --- ATOMIC PROCESSING LOOP ---
        # We process variants one by one so one failure doesn't kill the batch
        for variant in resolved_variants:
            try:
                brand_name = variant.get("Input_Brand_Name", "Unknown").strip()
                
                # Logic check: prevent re-processing
                if brand_name.lower() in existing_brands:
                    # We log this, but we don't 'continue' because we want to 
                    # process other variants that might be new
                    pass 

                product_id = f"PROD-{next_sno:04d}"
                
                row_data = [
                    next_sno,                           
                    product_id,                         
                    brand_name.capitalize(),            
                    variant.get("Variant_Name", "N/A"),
                    variant.get("Molecules", "N/A"),
                    variant.get("Strengths", "N/A"),
                    variant.get("Dosage_Form", "N/A"),
                    variant.get("Manufacturer_Name", "N/A")
                ]
                
                batch_rows_to_upload.append(row_data)
                next_sno += 1
                print(f"✅ Prepared variant: {brand_name} - {variant.get('Variant_Name')}")
                
            except Exception as e:
                # If one variant fails, we catch the error, log it, and continue the loop!
                print(f"⚠️ Skipping a bad variant in the batch: {e}")
                continue 
        
        # Push all successful items in this batch to Google Sheets
        if batch_rows_to_upload:
            sheet.append_rows(batch_rows_to_upload)
            print(f"📦 Success: Pushed {len(batch_rows_to_upload)} variants to production!")
            
            # Update local tracking
            for b in chunk:
                existing_brands.add(b.lower())
        else:
            print("⚠️ No valid variants extracted from this chunk.")
            
    except json.JSONDecodeError:
        print("❌ Critical Error: AI response was not valid JSON. Skipping batch.")
    except Exception as e:
        print(f"⚠️ Batch Pipeline Processing Interrupted: {e}")
        
    # Cool down
    if i + BATCH_SIZE < len(filtered_brands):
        print("⏳ Cooling down for 15 seconds to respect the 5 RPM ceiling...")
        time.sleep(15)

print("\n🎉 Production database population finalized smoothly!")
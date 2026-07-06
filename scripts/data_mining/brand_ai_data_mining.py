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
# We define scopes as a plain string list to avoid authentication formatting errors
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
    # Target the live production medicinal_product sheet
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
    print("⚠️ Usage: python brand_ai_data_mining.py <prompt_file.txt> <brands_list.txt>")
    print("👉 Example: python brand_ai_data_mining.py brand_prompt.txt input_brands.txt")
    exit()

prompt_file_path = sys.argv[1]
brands_file_path = sys.argv[2]

base_prompt = read_text_file(prompt_file_path)
all_brands = get_lines_from_file(brands_file_path)

if not base_prompt or not all_brands:
    print("❌ Execution halted: Missing prompt or input list.")
    exit()

# Deduplication logic: Fetch everything once to save API calls later
print("\n📊 Analyzing production tab for existing entries to prevent overlaps...")
existing_records = sheet.get_all_records()
# Create a searchable set of brand names
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

# Processing in Batches of 5 to optimize API throughput
BATCH_SIZE = 5 
print(f"🚀 Processing {len(filtered_brands)} brands in optimized chunks of {BATCH_SIZE}...")

for i in range(0, len(filtered_brands), BATCH_SIZE):
    chunk = filtered_brands[i:i + BATCH_SIZE]
    print(f"\n🧠 Querying Gemini to execute batch resolution for: {', '.join(chunk).upper()}")
    
    # Bundle inputs for the AI to handle in one go
    combined_prompt = f"{base_prompt}\n\nHere is the target list of brand names to extract right now:\n{json.dumps(chunk)}"
    
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
            
        resolved_variants = json.loads(raw_text)
        
        # Compile row data into a single batch list for efficiency
        batch_rows_to_upload = []
        
        for variant in resolved_variants:
            brand_name = variant.get("Input_Brand_Name", "Unknown").strip()
            
            # Double check to prevent duplicates sneaking in mid-batch
            if brand_name.lower() in existing_brands:
                print(f"⏭️ Skipping duplicate found in response: {brand_name}")
                continue
                
            # Create our sequential product ID: PROD-XXXX
            product_id = f"PROD-{next_sno:04d}"
            
            row_data = [
                next_sno,                           # S.No.
                product_id,                         # Product_ID
                brand_name.capitalize(),            # Brand_Name
                variant.get("Variant_Name", ""),    # Variant_Name
                variant.get("Molecules", ""),       # Molecule(s)
                variant.get("Strengths", ""),       # Strength(s)
                variant.get("Dosage_Form", ""),     # Dosage_Form
                variant.get("Manufacturer_Name", "")# Manufacturer_Name
            ]
            
            batch_rows_to_upload.append(row_data)
            existing_brands.add(brand_name.lower()) # Update local tracker
            next_sno += 1
            
        if batch_rows_to_upload:
            sheet.append_rows(batch_rows_to_upload)
            print(f"📦 Success: Pushed an optimized batch of {len(batch_rows_to_upload)} brand rows to the sheet!")
        else:
            print("⚠️ No unique rows extracted from this chunk.")
            
    except Exception as e:
        print(f"⚠️ Batch Pipeline Processing Interrupted: {e}")
        
    # Cool down for 15 seconds to stay within the free tier rate limit
    if i + BATCH_SIZE < len(filtered_brands):
        print("⏳ Cooling down for 15 seconds to respect the 5 RPM ceiling...")
        time.sleep(15)

print("\n🎉 Production database population finalized smoothly at maximum efficiency!")
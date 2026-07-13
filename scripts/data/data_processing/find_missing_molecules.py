import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# --- NEW PATHING LOGIC ---
# Dynamically find the root folder (pharmDB/) regardless of where the script is run
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))

# Look for the env and credentials in the project root
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

SHEET_ID = os.environ.get("SPREADSHEET_ID")

# Check if Render/Cloudflare passed a specific path, otherwise use the local one at the root
CREDENTIALS_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", os.path.join(PROJECT_ROOT, "credentials.json"))
OUTPUT_FILE = os.path.join(CURRENT_DIR, "missing_molecules.txt")
# -------------------------

# Load environment variables (to get your GOOGLE_SHEET_ID safely)
load_dotenv()

# Configuration
SHEET_ID = os.environ.get("SPREADSHEET_ID")
CREDENTIALS_FILE = 'credentials.json'  # Ensure this points to your secret key file
OUTPUT_FILE = 'missing_molecules.txt'

def get_google_client():
    """Authenticates and returns the Google Sheets client."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets", 
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)

def main():
    print("🔌 Connecting to Google Sheets...")
    gc = get_google_client()
    
    if not SHEET_ID:
        print("❌ Error: GOOGLE_SHEET_ID not found in environment variables.")
        return
        
    sheet = gc.open_by_key(SHEET_ID)

    print("📥 Fetching data from both tabs (this might take a few seconds)...")
    product_ws = sheet.worksheet("medicinal_product")
    molecule_ws = sheet.worksheet("drug_molecule")

    products = product_ws.get_all_records()
    molecules = molecule_ws.get_all_records()

    # 1. Build a "Set" of existing molecules for instant, fast searching.
    # We convert everything to lowercase to prevent missing a match due to capitalization (e.g. "pantoprazole" vs "Pantoprazole")
    existing_molecules_lower = set(
        str(row.get("Molecule_Name", "")).strip().lower() 
        for row in molecules if row.get("Molecule_Name")
    )

    missing_molecules = set()

    # 2. Loop through every commercial product
    for product in products:
        mols_string = str(product.get("Molecule(s)", ""))
        if not mols_string:
            continue

        # 3. Split comma-separated molecules (e.g. "Abacavir, Lamivudine" -> ["Abacavir", "Lamivudine"])
        mol_list = [m.strip() for m in mols_string.split(',')]
        
        # 4. Check if they exist in the parent database
        for mol in mol_list:
            if mol and mol.lower() not in existing_molecules_lower:
                missing_molecules.add(mol) # Using a Set automatically prevents duplicates!

    # Sort them alphabetically for a clean text file
    sorted_missing = sorted(list(missing_molecules))

    print(f"🔍 Scan complete! Found {len(sorted_missing)} missing distinct molecules.")

    # 5. Write the missing molecules to a clean text file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for mol in sorted_missing:
            f.write(f"{mol}\n")

    print(f"✅ Successfully saved to {OUTPUT_FILE}")
    print("You can now feed this file directly into your AI Molecule Builder!")

if __name__ == "__main__":
    main()
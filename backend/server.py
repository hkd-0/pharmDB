import os
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# --- NEW: Import our decoupled architecture modules ---
from schema import DATABASE_SCHEMA
from migrations import run_schema_migration
from maintenance import run_global_maintenance

# Load the variables from the .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Map the environment variables to your script
SECRET_API_KEY = os.environ.get("X_API_KEY")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
ALLOWED_ORIGIN = os.environ.get("FRONTEND_URL", "*") # Fallback to * for local testing if needed

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# --- REPLACE THIS SECTION IN server.py ---
CREDENTIALS_FILE = 'credentials.json' # Look in the current directory
SECRET_FILE_PATH = '/etc/secrets/credentials.json' # Render secret file path

# Debugging: Print to the logs where we are looking
print(f"[DEBUG] Looking for credentials at: {os.path.abspath(CREDENTIALS_FILE)}")
print(f"[DEBUG] Checking existence of: {os.path.exists(CREDENTIALS_FILE)}")

if os.path.exists(SECRET_FILE_PATH):
    print(f"[DEBUG] Found secret file at {SECRET_FILE_PATH}")
    CREDENTIALS_FILE = SECRET_FILE_PATH

try:
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(credentials)
    print("[Server Init] Google Sheets service client authenticated successfully.")
except Exception as e:
    print(f"[Server Init Error] Critical failure: {e}")
    gc = None


class RequestHandler(BaseHTTPRequestHandler):
    
    def _send_cors_headers(self):
        origin = self.headers.get('Origin')
        # If ALLOWED_ORIGIN is set, verify it. Otherwise, allow it for local testing.
        if origin == ALLOWED_ORIGIN or ALLOWED_ORIGIN == "*":
            self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, x-api-key")

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self._send_cors_headers()
        self.end_headers()

    def get_query_params(self):
        parsed_path = urllib.parse.urlparse(self.path)
        return urllib.parse.parse_qs(parsed_path.query)

    def is_authorized(self):
        # 1. Look for the key in the headers first (case-insensitive check)
        client_key = self.headers.get('X-API-Key') or self.headers.get('x-api-key')
        
        # 2. Fallback: If not in headers, check the URL query parameters
        if not client_key:
            params = self.get_query_params()
            client_key = params.get('key', [None])[0]

        # 3. Validate against your secret key
        if client_key != SECRET_API_KEY:
            self.send_response(403)
            self._send_cors_headers()
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized Access Denied"}).encode('utf-8'))
            return False
        return True

    def do_GET(self):
        # 1. DUMMY ROUTE FOR PINGING (Keeps Render Awake)
        if self.path == '/ping':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*') 
            self.end_headers()
            self.wfile.write(b"Server is awake!")
            return 

        if not self.is_authorized(): return

        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        try:
            spreadsheet = gc.open_by_key(SPREADSHEET_ID)
            
            # Fetch both relational tables
            molecules_sheet = spreadsheet.worksheet("drug_molecule")
            products_sheet = spreadsheet.worksheet("medicinal_product")
            
            m_data = molecules_sheet.get_all_records()
            p_data = products_sheet.get_all_records()
            
            # Attach structural row numbers exactly as requested by your frontend
            for i, row in enumerate(m_data): row['_row_num'] = i + 2
            for i, row in enumerate(p_data): row['_row_num'] = i + 2
                
            # Package into a single JSON response
            response = json.dumps({
                "molecules": m_data,
                "inventory": p_data
            })
        except Exception as e:
            response = json.dumps({"error": str(e)})

        self.wfile.write(response.encode('utf-8'))

    def do_POST(self):
        if not self.is_authorized(): return

        # --- NEW: Architectural Maintenance Routes ---
        if self.path == "/api/migrate":
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            success = run_schema_migration(gc, SPREADSHEET_ID)
            msg = "Schema migration successful." if success else "Schema migration aborted."
            self.wfile.write(json.dumps({"success": success, "message": msg}).encode('utf-8'))
            return

        if self.path == "/api/maintain":
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            success = run_global_maintenance(gc, SPREADSHEET_ID)
            msg = "Data maintenance and relationship mapping successful." if success else "Maintenance aborted."
            self.wfile.write(json.dumps({"success": success, "message": msg}).encode('utf-8'))
            return
        # --- END NEW ROUTES ---

        # ORIGINAL ADD-RECORD ROUTE
        params = self.get_query_params()
        sheet_name = params.get('sheet', ['medicinal_product'])[0]

        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            new_row_data = json.loads(post_data.decode('utf-8'))
            sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
            
            # --- AUTO-GENERATION LOGIC START ---
            all_records = sheet.get_all_records()
            next_sno = len(all_records) + 1
            
            # Ensure S.No. is automatically injected
            new_row_data['S.No.'] = next_sno
            
            # Generate the correct ID based on the tab
            if sheet_name == "medicinal_product":
                new_row_data['Product_ID'] = f"PROD-{str(next_sno).zfill(4)}"
            elif sheet_name == "drug_molecule":
                new_row_data['Molecule_ID'] = f"M-{str(next_sno).zfill(4)}"
            # --- AUTO-GENERATION LOGIC END ---

            # Map the data exactly to the spreadsheet headers
            headers = sheet.row_values(1)
            row_values = [new_row_data.get(header, "") for header in headers]
            
            sheet.append_row(row_values)
            
            # Return the newly generated IDs back to the frontend
            response = json.dumps({
                "success": True, 
                "generated_sno": next_sno,
                "generated_id": row_values[1] # Assuming ID is the second column
            })
            
        except Exception as e:
            response = json.dumps({"error": str(e)})

        self.wfile.write(response.encode('utf-8'))

    def do_DELETE(self):
        if not self.is_authorized(): return
        params = self.get_query_params()
        sheet_name = params.get('sheet', ['medicinal_product'])[0]

        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        content_length = int(self.headers['Content-Length'])
        delete_data = self.rfile.read(content_length)

        try:
            data = json.loads(delete_data.decode('utf-8'))
            row_num = data.get('_row_num')
            if not row_num:
                raise ValueError("Row number is required for deletion")
            
            sheet = gc.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
            sheet.delete_rows(row_num)
            response = json.dumps({"success": True})
        except Exception as e:
            response = json.dumps({"error": str(e)})

        self.wfile.write(response.encode('utf-8'))

def run(server_class=HTTPServer, handler_class=RequestHandler, port=8000):
    # Ensure port matches Render's dynamic port environment if hosted
    port = int(os.environ.get("PORT", port))
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting Pharma Relational API on port {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
import pandas as pd
import argparse
import os

def extract_columns(filepath, columns, sep=',', split_char=None):
    # 1. Check if file exists
    if not os.path.exists(filepath):
        print(f"❌ Error: Could not find the file '{filepath}'")
        return

    print(f"⏳ Loading data from {filepath}...")
    
    try:
        # Load the dataset. low_memory=False prevents warnings on huge files.
        df = pd.read_csv(filepath, sep=sep, low_memory=False)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return

    # 2. Process each requested column
    for col in columns:
        if col not in df.columns:
            print(f"⚠️ Warning: Column '{col}' not found in the header. Skipping.")
            continue

        print(f"🔍 Processing column: '{col}'...")

        # 3. Clean the data
        # - Drop empty cells (NaN)
        # - Convert to string
        # - Strip leading/trailing whitespaces
        raw_items = df[col].dropna().astype(str).str.strip().tolist()
        
        processed_items = set()
        
        for item in raw_items:
            # If the user provided a split character (like a semicolon), split the string
            if split_char and split_char in item:
                parts = item.split(split_char)
                for part in parts:
                    clean_part = part.strip()
                    if clean_part:
                        processed_items.add(clean_part)
            else:
                if item:
                    processed_items.add(item)
        
        # Convert the set to a list and sort alphabetically
        unique_items = sorted(list(processed_items))

        # 4. Generate a safe output filename
        safe_col_name = "".join(x for x in col if x.isalnum() or x in " _-")
        output_filename = f"{safe_col_name}_list.txt"

        # 5. Write exactly one item per line
        written_count = 0
        with open(output_filename, 'w', encoding='utf-8') as f:
            for item in unique_items:
                f.write(f"{item}\n")
                written_count += 1

        print(f"✅ Success: Extracted {written_count} unique items into -> {output_filename}\n")

if __name__ == "__main__":
    # Set up the command line interface
    parser = argparse.ArgumentParser(description="Extract unique, clean values from specific columns in a dataset.")
    parser.add_argument("filename", help="The path to your dataset file")
    parser.add_argument("columns", nargs='+', help="One or more column names exactly as they appear in the header")
    parser.add_argument("--sep", default=',', help="The delimiter used in the file (default is comma ',').")
    parser.add_argument("--split", default=None, help="A character to split multi-value cells (e.g., ';' for FDA ingredients).")
    
    args = parser.parse_args()
    
    extract_columns(args.filename, args.columns, args.sep, args.split)
####### variant b:  a report file per json#################'''
import sys
import os

# 0. FIX IMPORT PATHS
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from chunking_chapters import DataLoader
except ImportError:
    print("\nCRITICAL ERROR: Could not import 'DataLoader' from 'chunking_chapters.py'.")
    print(f"Please ensure 'chunking_chapters.py' exists in this folder: {current_dir}")
    sys.exit(1)

import pandas as pd

BASE_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/ebooks_jsons_for_token_analysis"
OUTPUT_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/chunking/chunking_reports"


# Define the report file path
REPORT_FILE = os.path.join(OUTPUT_PATH, "debug_inspection_report.txt")

# 2. LOAD DATA
print("Loading data... (this might take a moment)")
try:
    loader = DataLoader(BASE_PATH, OUTPUT_PATH)
    work_units = loader.load_and_chunk()
except Exception as e:
    print(f"Error initializing DataLoader: {e}")
    sys.exit(1)

# 3. GENERATE REPORT
# We open the file and define a helper to write to both console and file
print(f"Generating report at: {REPORT_FILE}")

with open(REPORT_FILE, "w", encoding="utf-8") as f:
    def log(msg):
        print(msg)
        f.write(msg + "\n")

    # Get unique files
    unique_files = sorted(list(set(u['source_file'] for u in work_units)))

    log(f"\nFound {len(unique_files)} files in total.")
    log("=" * 105)

    # 4. ITERATE AND PRINT REPORT PER FILE
    for filename in unique_files:
        log(f"\nFILE: {filename}")

        # Filter chunks for this specific file
        my_book_chunks = [u for u in work_units if u['source_file'] == filename]

        log(f"Total chunks: {len(my_book_chunks)}")
        log(f"{'CHUNK ID':<50} | {'TYPE':<20} | {'STRATEGY':<20} | {'LENGTH'}")
        log("-" * 105)

        for chunk in my_book_chunks:
            # Handle None types safely for printing
            inf_type = str(chunk.get('inferred_type', 'None'))
            if len(inf_type) > 20: inf_type = inf_type[:17] + "..."

            strategy = chunk.get('strategy', 'Unknown')
            length = len(chunk.get('html', ''))

            # Adjust ID width to match header
            log(f"{chunk['id']:<50} | {inf_type:<20} | {strategy:<20} | {length}")

        log("=" * 105)

    log("\n--- End of Report ---")

print(f"Done! Full report saved to {REPORT_FILE}")
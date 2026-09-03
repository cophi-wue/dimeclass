import os
import json
import csv
import re
from pathlib import Path

# --- CONFIGURATION ---
TSV_INPUT_PATH = Path("/home/spielberg/code/repos/dimeclass/conversion/scripts/python/evaluation_labels/results/03_12_eval_results.tsv")
TSV_OUTPUT_PATH = Path("/home/spielberg/code/repos/dimeclass/conversion/scripts/python/evaluation_labels/results/03_12_eval_results_with_inferred-type.tsv")
SOURCE_JSON_DIR = Path("/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation/source_json")

def parse_id(chunk_id):
    """
    Parses IDs like: 'filename.json_0_5'
    Returns: (filename, book_idx, chunk_idx)
    """
    match = re.match(r"(.+)\_(\d+)\_(\d+)$", str(chunk_id))
    if match:
        return match.group(1), int(match.group(2)), int(match.group(3))
    return None, None, None

def get_inferred_type(filename, book_idx, chunk_idx):
    """
    Navigates the JSON structure. Returns (type, error_msg).
    """
    file_path = SOURCE_JSON_DIR / filename
    if not file_path.exists():
        return None, f"File not found: {filename}"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        content = data.get("content", [])

        if book_idx == 0:
            if chunk_idx < len(content):
                return content[chunk_idx].get("inferred-type", "unknown"), None
            else:
                return None, f"Index {chunk_idx} out of bounds in {filename}"
        else:
            actual_book_idx = book_idx - 1
            if actual_book_idx < len(content):
                book_content = content[actual_book_idx].get("content", [])
                if chunk_idx < len(book_content):
                    return book_content[chunk_idx].get("inferred-type", "unknown"), None
                else:
                    return None, f"Index {chunk_idx} out of bounds in book {book_idx} of {filename}"
            else:
                return None, f"Book index {book_idx} out of bounds in {filename}"

    except Exception as e:
        return None, f"JSON Error in {filename}: {str(e)}"

def main():
    if not TSV_INPUT_PATH.exists():
        print(f"Input TSV not found at {TSV_INPUT_PATH}")
        return

    rows = []
    headers = []

    with open(TSV_INPUT_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        headers = list(reader.fieldnames)
        for row in reader:
            rows.append(row)

    # Ensure inferred_type column exists
    if "inferred_type" not in headers:
        insert_idx = headers.index("gold_label") + 1 if "gold_label" in headers else len(headers)
        headers.insert(insert_idx, "inferred_type")

    print(f"Processing {len(rows)} rows...")

    success_count = 0
    skipped_count = 0
    errors = []

    for row in rows:
        chunk_id = row.get("id")
        current_val = row.get("inferred_type", "").strip()

        # Skip if already filled and not an error/empty
        if current_val and not current_val.startswith("ERROR"):
            skipped_count += 1
            continue

        if not chunk_id:
            continue

        fname, b_idx, c_idx = parse_id(chunk_id)

        if fname:
            inf_type, err = get_inferred_type(fname, b_idx, c_idx)
            if inf_type:
                row["inferred_type"] = inf_type
                success_count += 1
            else:
                row["inferred_type"] = "" # Leave blank on error
                errors.append(f"ID: {chunk_id} -> {err}")
        else:
            row["inferred_type"] = ""
            errors.append(f"ID: {chunk_id} -> Invalid ID format")

    # Write results
    with open(TSV_OUTPUT_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)

    # Console Reporting
    print(f"\n--- Results ---")
    print(f"Successfully added: {success_count}")
    print(f"Already present (skipped): {skipped_count}")
    print(f"Failed (left blank): {len(errors)}")

    if errors:
        print(f"\n--- Error Log ---")
        for err in errors:
            print(err)

    print(f"\nEnriched TSV saved to: {TSV_OUTPUT_PATH}")

if __name__ == "__main__":
    main()
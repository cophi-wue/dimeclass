import json
import os
from collections import Counter
import pandas as pd
import sys

# --- CONFIGURATION ---

# Set the paths as specified by the user
INPUT_JSON_PATH = '/home/spielberg/code/repos/epub_unpack/11extracted_json'
OUTPUT_ANALYSIS_PATH = '/home/spielberg/code/repos/dimeclass/conversion/logs/analysis_results'


# --- MAIN EXECUTION ---

def main():
    """
    Main function to orchestrate the metadata analysis of all ebooks.
    """
    print("Starting eBook metadata analysis...")
    if not os.path.exists(INPUT_JSON_PATH):
        print(f"Error: Input directory not found at {INPUT_JSON_PATH}", file=sys.stderr)
        return

    os.makedirs(OUTPUT_ANALYSIS_PATH, exist_ok=True)

    # Find all JSON files in subdirectories
    json_files_to_process = []
    for root, dirs, files in os.walk(INPUT_JSON_PATH):
        for file in files:
            if file.endswith('.json'):
                json_files_to_process.append(os.path.join(root, file))

    total_files = len(json_files_to_process)
    if total_files == 0:
        print(f"Error: No .json files found in subdirectories of {INPUT_JSON_PATH}", file=sys.stderr)
        return

    print(f"Found {total_files} JSON files to analyze for metadata.")

    # --- Initialize data aggregators ---
    publisher_frequency = Counter()
    metadata_key_frequency = Counter()
    files_without_publisher = 0
    files_without_metadata = 0

    # --- Process each file ---
    for i, file_path in enumerate(json_files_to_process):
        print(f"Processing file {i+1}/{total_files}: {os.path.basename(file_path)}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"  - Could not read or parse JSON: {e}", file=sys.stderr)
            continue

        # Check for epub_metadata dictionary
        if 'epub_metadata' in data and isinstance(data['epub_metadata'], dict):
            metadata = data['epub_metadata']

            # 1. Analyze metadata keys
            for key in metadata.keys():
                metadata_key_frequency[key] += 1

            # 2. Analyze publisher information
            if 'publisher' in metadata:
                publisher_name = metadata['publisher']
                # Handle cases where publisher might be a list or a single string
                if isinstance(publisher_name, list):
                    for pub in publisher_name:
                        publisher_frequency[pub] += 1
                elif isinstance(publisher_name, str):
                    publisher_frequency[publisher_name] += 1
            else:
                files_without_publisher += 1
        else:
            files_without_metadata += 1
            files_without_publisher += 1 # A file without metadata also has no publisher

    # --- Save aggregated results to CSV files ---
    print("\nMetadata analysis complete. Saving results...")

    # 1. Publisher Analysis Results
    publisher_df = pd.DataFrame(publisher_frequency.most_common(), columns=['Publisher', 'Frequency'])
    # Add a row for files missing the publisher key
    missing_publisher_df = pd.DataFrame([
        {
            'Publisher': '**Files without a publisher entry**',
            'Frequency': files_without_publisher
        }
    ])
    final_publisher_df = pd.concat([publisher_df, missing_publisher_df], ignore_index=True)
    publisher_output_path = os.path.join(OUTPUT_ANALYSIS_PATH, 'metadata_publisher_analysis.csv')
    final_publisher_df.to_csv(publisher_output_path, index=False)
    print(f"Publisher analysis saved to: {publisher_output_path}")


    # 2. Metadata Key Frequency Results
    keys_df = pd.DataFrame(metadata_key_frequency.most_common(), columns=['Metadata_Key', 'Frequency'])
    # Add info about files that had no metadata dictionary at all
    keys_df.loc[len(keys_df)] = ['**Files without epub_metadata dict**', files_without_metadata]
    keys_output_path = os.path.join(OUTPUT_ANALYSIS_PATH, 'metadata_key_frequency.csv')
    keys_df.to_csv(keys_output_path, index=False)
    print(f"Metadata key analysis saved to: {keys_output_path}")

    print("\nAll metadata reports have been generated.")


if __name__ == '__main__':
    main()
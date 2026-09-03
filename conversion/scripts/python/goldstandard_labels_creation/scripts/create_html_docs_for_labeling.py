import os
import json
import glob
import re

def clean_id(original_id):
    """
    Transforms an ID into a string safe for filenames.
    Returns the cleaned ID and a boolean indicating if changes were made.
    """
    # Define illegal characters and their replacements
    replacements = {
        "/": "_",
        "\\": "_",
        ":": "-",
        "*": "",
        "?": "",
        "\"": "",
        "<": "",
        ">": "",
        "|": ""
    }

    cleaned = original_id
    for char, rep in replacements.items():
        cleaned = cleaned.replace(char, rep)

    # Remove any trailing spaces or dots
    cleaned = cleaned.strip(". ")

    was_changed = (cleaned != original_id)
    return cleaned, was_changed

def extract_snippets(source_dir, output_dir, start_index=0, end_index=None, sort_alphabetically=True):
    """
    Extracts snippets from JSON files and saves them as individual HTML files.
    Logs ID alterations to the console and generates a mapping_log.json.
    """

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created base directory: {output_dir}")

    json_files = glob.glob(os.path.join(source_dir, "*.json"))
    if sort_alphabetically:
        json_files.sort()

    files_to_process = json_files[start_index:end_index]
    print(f"Processing files from index {start_index} to {end_index if end_index else 'end'}...")

    total_snippets_created = 0
    modified_ids_count = 0
    id_mapping = {}

    for json_path in files_to_process:
        base_name = os.path.splitext(os.path.basename(json_path))[0]
        folder_path = os.path.join(output_dir, base_name)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                snippets = data if isinstance(data, list) else [data]

                for i, snippet in enumerate(snippets):
                    original_id = snippet.get("id")
                    html_content = snippet.get("text", "")

                    if not original_id:
                        continue

                    # Clean the ID and check if it was modified
                    safe_id_part, was_changed = clean_id(original_id)

                    if was_changed:
                        print(f"  [ID Modified] Original: {original_id}")
                        print(f"               Cleaned:  {safe_id_part}")
                        modified_ids_count += 1

                    filename = f"{i:02d}_{safe_id_part}.xml"
                    filepath = os.path.join(folder_path, filename)

                    # Store the mapping
                    relative_path = os.path.join(base_name, filename)
                    id_mapping[relative_path] = original_id

                    with open(filepath, "w", encoding="utf-8") as out_file:
                        out_file.write(html_content)

                    total_snippets_created += 1

        except Exception as e:
            print(f"Error processing {json_path}: {e}")

    # Save the mapping log
    mapping_log_path = os.path.join(output_dir, "mapping_log.json")
    with open(mapping_log_path, "w", encoding="utf-8") as log_f:
        json.dump(id_mapping, log_f, indent=4, ensure_ascii=False)

    print("-" * 30)
    print(f"Finished! Total snippets created: {total_snippets_created}")
    print(f"Total IDs modified for filesystem compatibility: {modified_ids_count}")
    print(f"Mapping log created at: {mapping_log_path}")

if __name__ == "__main__":
    # --- CONFIGURATION ---
    SOURCE = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation/chunks_for_labeling" #here are the json files with the chunks and their ids
    DESTINATION = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation/goldstandard_verified/manual_TEI_transformation" #here the html files will be created in subfolders named after the json files
    #DESTINATION = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation/chunks_for_transformation" #here the html files will be created in subfolders named after the json files

    # --- RANGE SETTINGS ---
    START = 0
    END = 5

    extract_snippets(SOURCE, DESTINATION, start_index=START, end_index=END)
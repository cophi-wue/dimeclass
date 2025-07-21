import json
import os

def analyze_json_collection_structure(json_file_path, output_file_path=None):
    """
    Analyzes a single JSON file to describe its structure,
    focusing on EPUBs containing multiple sub-works (collections).

    Args:
        json_file_path (str): The path to the single JSON file to analyze.
        output_file_path (str, optional): If provided, the analysis output will be written
                                          to this file. If None, output goes to console.
    """
    
    # Determine where to write output
    if output_file_path:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_file_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
                print(f"Created output directory: {os.path.abspath(output_dir)}")
            except OSError as e:
                print(f"Error creating output directory {output_dir}: {e}. Outputting to console instead.")
                output_file_path = None # Fallback to console if directory creation fails

    if output_file_path:
        try:
            f_out = open(output_file_path, 'w', encoding='utf-8')
            print_func = lambda *args, **kwargs: print(*args, file=f_out, **kwargs)
            print(f"Analysis output will be written to: {os.path.abspath(output_file_path)}\n")
        except IOError as e:
            print(f"Error opening output file {output_file_path}: {e}. Outputting to console instead.")
            print_func = print
            f_out = None
    else:
        print_func = print
        f_out = None

    try:
        print_func(f"Starting analysis for file: {os.path.abspath(json_file_path)}\n")

        if not os.path.exists(json_file_path):
            print_func(f"Error: JSON file not found at '{json_file_path}'.")
            return
        if not json_file_path.endswith(".json"):
            print_func(f"Error: Provided file '{json_file_path}' is not a JSON file.")
            return

        print_func(f"\n--- Analyzing File: {json_file_path} ---")
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            describe_json_collection_logic(data, print_func)

        except json.JSONDecodeError as e:
            print_func(f"Error decoding JSON from {json_file_path}: {e}")
        except Exception as e:
            print_func(f"An unexpected error occurred while processing {json_file_path}: {e}")
    finally:
        if f_out:
            f_out.close()
            print(f"\nAnalysis results saved to {output_file_path}")

def describe_json_collection_logic(data, print_func):
    """
    Describes the structure of the JSON data, focusing on collection logic and key fields.
    """
    print_func("Overall JSON Structure for EPUB Collection:")
    print_func("------------------------------------------")

    # 1. Overall Collection Metadata (Top-Level)
    print_func("\n1. Overall Collection Metadata (Top-Level):")
    print_func(f"  Key: 'title' (string): '{data.get('title', 'N/A')}'")
    print_func(f"  Key: 'source' (string): '{data.get('source', 'N/A')}'")

    print_func("  Key: 'processing_log' (object):")
    if 'processing_log' in data and isinstance(data['processing_log'], dict):
        print_func(f"    Key: 'processing_log.is_collection' (boolean): {data['processing_log'].get('is_collection', 'N/A')}")
        # Optionally add other processing_log fields if desired, e.g.:
        # print_func(f"    Key: 'processing_log.toc_repair' (boolean): {data['processing_log'].get('toc_repair', 'N/A')}")
    else:
        print_func("    'processing_log' object not found or invalid.")

    print_func("  Key: 'epub_metadata' (object):")
    if 'epub_metadata' in data and isinstance(data['epub_metadata'], dict):
        for key, value in data['epub_metadata'].items():
            if isinstance(value, list):
                print_func(f"    Key: 'epub_metadata.{key}' (list): {value[0] if value else '[]'} (first item example)")
            else:
                print_func(f"    Key: 'epub_metadata.{key}' ({type(value).__name__}): '{value}'")
    else:
        print_func("    'epub_metadata' object not found or invalid.")

    # 2. The Main 'content' Array and Nested Volumes
    print_func("\n2. The Main 'content' Array and Nested Volumes:")
    print_func("  Key: 'content' (array):")
    
    if 'content' in data and isinstance(data['content'], list):
        for i, item in enumerate(data['content']):
            if isinstance(item, dict):
                item_type = item.get('type')
                print_func(f"\n  Content Item {i}: (Type: '{item_type}')")
                
                if item_type == "Section":
                    print_func("    This is a 'Section' object (individual book/volume):")
                    print_func(f"    Key: 'title' (string): '{item.get('title', 'N/A')}'")
                    print_func(f"    Key: 'inferred-type' (string): '{item.get('inferred-type', 'N/A')}'")
                    print_func("    Key: 'content' (array) (nested for this sub-volume):")
                    
                    if 'content' in item and isinstance(item['content'], list):
                        if item['content']:
                            first_sub_item = item['content'][0]
                            print_func(f"      First sub-item (Type: '{first_sub_item.get('type', 'N/A')}'):")
                            describe_content_block_fields(first_sub_item, print_func, indent_level=4)
                        else:
                            print_func("      (Nested 'content' array is empty for this Section.)")
                    else:
                        print_func("      (No nested 'content' array found for this Section, or it's empty/invalid.)")
                
                elif item_type == "EpubHtml":
                    print_func("    This is an 'EpubHtml' object (top-level content piece):")
                    describe_content_block_fields(item, print_func, indent_level=3)
                else:
                    print_func(f"    (Other content item type: '{item_type}'):")
                    describe_content_block_fields(item, print_func, indent_level=3)
            else:
                print_func(f"  Content Item {i}: (Non-dictionary item, type: {type(item).__name__}) - Unexpected format.")
    else:
        print_func("  (No 'content' array found at top level, or it's empty/invalid.)")

def describe_content_block_fields(item, print_func, indent_level):
    """
    Helper function to describe common fields found in individual content blocks.
    """
    indent = "  " * indent_level
    print_func(f"{indent}  Content Block Fields:")
    
    print_func(f"{indent}    Key: 'type' (string): '{item.get('type', 'N/A')}'")
    print_func(f"{indent}    Key: 'href' (string): '{item.get('href', 'N/A')}'")
    print_func(f"{indent}    Key: 'title' (string): '{item.get('title', 'N/A')}'")
    print_func(f"{indent}    Key: 'images' (list): {item.get('images', 'N/A')}")
    print_func(f"{indent}    Key: 'inferred-type' (string): '{item.get('inferred-type', 'N/A')}'")
    print_func(f"{indent}    Key: 'true-type' (string): '{item.get('true-type', 'N/A')}'")
    print_func(f"{indent}    Key: 'is_narrative' (boolean): '{item.get('is_narrative', 'N/A')}'")
    print_func(f"{indent}    Key: 'text' (string): (HTML content, not printed in full)")

# Example usage for a single JSON file:
# Assuming your script is in: ~/code/repos/dimeclass/conversion/scripts/python/
# And your JSON file is: ~/code/repos/dimeclass/conversion/data/json/Jerry Cotton Sammelband 1 - Kri - Jerry Cotton.json
# Output to: ~/code/repos/dimeclass/docs/multivolume_structure_analysis.txt

analyze_json_collection_structure(
    json_file_path="./conversion/data/json/Jerry Cotton Sammelband 1 - Kri - Jerry Cotton.json", # Path to your specific JSON file
    output_file_path="./conversion/logs/all_json_structure_analysis.txt"
)

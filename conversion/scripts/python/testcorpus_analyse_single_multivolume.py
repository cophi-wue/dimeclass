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
    print_func("  Key: 'title' (string) - Title of the entire collection.")
    if 'title' in data:
        print_func(f"    Example: '{data['title']}'")
    
    print_func("  Key: 'source' (string) - Original EPUB filename for the whole collection.")
    if 'source' in data:
        print_func(f"    Example: '{data['source']}'")

    print_func("  Key: 'processing_log' (object) - Contains processing details.")
    if 'processing_log' in data and isinstance(data['processing_log'], dict):
        print_func("    Key: 'processing_log.is_collection' (boolean) - CRITICAL: Indicates if this EPUB contains multiple sub-works.")
        if 'is_collection' in data['processing_log']:
            print_func(f"      Example: {data['processing_log']['is_collection']}")
        else:
            print_func("      'is_collection' field not found in processing_log.")
    else:
        print_func("    'processing_log' object not found or invalid.")

    print_func("  Key: 'epub_metadata' (object) - General metadata for the collection (e.g., overall title, creator, identifier, language).")
    if 'epub_metadata' in data and isinstance(data['epub_metadata'], dict):
        print_func("    Contains fields like 'title', 'creator', 'identifier', 'language', etc.")
        print_func(f"    Example 'title': '{data['epub_metadata'].get('title', 'N/A')}'")
        print_func(f"    Example 'creator': '{data['epub_metadata'].get('creator', 'N/A')}'")
    else:
        print_func("    'epub_metadata' object not found or invalid.")

    # 2. The Main 'content' Array and Nested Volumes
    print_func("\n2. The Main 'content' Array and Nested Volumes:")
    print_func("  Key: 'content' (array) - The main array holding all major content blocks.")
    print_func("  This array contains individual 'sections' or 'parts' of the EPUB.")
    print_func("  For collections, this array typically contains 'Section' objects, each representing a distinct sub-volume (book).")
    
    if 'content' in data and isinstance(data['content'], list):
        for i, item in enumerate(data['content']):
            if isinstance(item, dict):
                item_type = item.get('type')
                print_func(f"\n  Content Item {i}: (Type: '{item_type}')")
                
                if item_type == "Section":
                    print_func("    This 'Section' object represents an individual book/volume within the collection.")
                    print_func("    Key: 'title' (string) - Title of this specific sub-volume.")
                    print_func(f"      Example: '{item.get('title', 'N/A')}'")
                    print_func("    Key: 'inferred-type' (string) - Inferred type for this sub-volume (e.g., 'novel').")
                    print_func(f"      Example: '{item.get('inferred-type', 'N/A')}'")
                    print_func("    Key: 'content' (array) - CRITICAL: This nested array contains the content blocks specific to *this* sub-volume.")
                    
                    if 'content' in item and isinstance(item['content'], list):
                        print_func("      This nested 'content' array will contain 'EpubHtml' objects (chapters, prefaces, etc.) for this specific book.")
                        if item['content']:
                            first_sub_item = item['content'][0]
                            print_func(f"      Example of first sub-item (Type: '{first_sub_item.get('type', 'N/A')}'):")
                            describe_content_block_fields(first_sub_item, print_func, indent_level=4)
                        else:
                            print_func("      (Nested 'content' array is empty for this Section.)")
                    else:
                        print_func("      (No nested 'content' array found for this Section, or it's empty/invalid.)")
                
                elif item_type == "EpubHtml":
                    print_func("    This 'EpubHtml' object represents a top-level content piece (e.g., overall collection cover, impressum, or a single book if 'is_collection' is false).")
                    describe_content_block_fields(item, print_func, indent_level=3)
                else:
                    print_func(f"    (Other content item type: '{item_type}'. Describing common fields.)")
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
    print_func(f"{indent}  Common Content Block Fields:")
    
    # Key fields for a content block
    print_func(f"{indent}    Key: 'type' (string) - Type of this content block (e.g., 'EpubHtml'). Example: '{item.get('type', 'N/A')}'")
    print_func(f"{indent}    Key: 'href' (string) - Original HTML file reference. Example: '{item.get('href', 'N/A')}'")
    print_func(f"{indent}    Key: 'title' (string) - Title of this specific content block. Example: '{item.get('title', 'N/A')}'")
    print_func(f"{indent}    Key: 'images' (array of strings) - Paths to images within this block. Example: {item.get('images', 'N/A')}")
    print_func(f"{indent}    Key: 'inferred-type' (string) - Automated classification (e.g., 'cover', 'chapter', 'toc'). Example: '{item.get('inferred-type', 'N/A')}'")
    print_func(f"{indent}    Key: 'true-type' (string) - Manual classification (if available). Example: '{item.get('true-type', 'N/A')}'")
    print_func(f"{indent}    Key: 'is_narrative' (boolean) - Indicates if content is narrative. Example: '{item.get('is_narrative', 'N/A')}'")
    print_func(f"{indent}    Key: 'text' (string) - Contains the actual HTML content. (Not printing full HTML)")

# Example usage for a single JSON file:
# Assuming your script is in: ~/code/repos/dimeclass/conversion/scripts/python/
# And your JSON file is: ~/code/repos/dimeclass/conversion/data/json/Jerry Cotton Sammelband 1 - Kri - Jerry Cotton.json
# Output to: ~/code/repos/dimeclass/docs/multivolume_structure_analysis.txt

# Define the input JSON file path
input_json_file = "./conversion/data/json/Jerry Cotton Sammelband 1 - Kri - Jerry Cotton.json"

# Extract the base name of the JSON file 
json_file_basename = os.path.splitext(os.path.basename(input_json_file))[0]

# Construct the output file path 
output_file_name = f"structure_analysis_{json_file_basename}.txt"
output_directory = "./conversion/logs" # This is relative to the repository root, where you run the script

# Combine directory and filename for the full output path
dynamic_output_file_path = os.path.join(output_directory, output_file_name)


analyze_json_collection_structure(
    json_file_path=input_json_file,
    output_file_path=dynamic_output_file_path
)

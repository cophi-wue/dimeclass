import json
import os

def analyze_json_collection_structure(repo_root_path=".", output_file_path=None):
    """
    Analyzes JSON files within a specified repository path to describe their structure,
    especially for EPUBs containing multiple sub-works (collections).

    Args:
        repo_root_path (str): The relative path to the root of the repository.
                              Defaults to the current directory.
        output_file_path (str, optional): If provided, the analysis output will be written
                                          to this file. If None, output goes to console.
    """
    json_files_found = []
    
    # Determine where to write output
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
        print_func(f"Starting analysis in: {os.path.abspath(repo_root_path)}\n")

        # Walk through the directory to find JSON files
        for dirpath, _, filenames in os.walk(repo_root_path):
            for filename in filenames:
                if filename.endswith(".json"):
                    json_files_found.append(os.path.join(dirpath, filename))

        if not json_files_found:
            print_func("No JSON files found in the specified repository path.")
            return

        print_func(f"Found {len(json_files_found)} JSON files. Analyzing for collection structure...\n")

        for json_file_path in json_files_found:
            print_func(f"\n--- Analyzing File: {json_file_path} ---")
            try:
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                describe_json_structure(data, print_func)

            except json.JSONDecodeError as e:
                print_func(f"Error decoding JSON from {json_file_path}: {e}")
            except Exception as e:
                print_func(f"An unexpected error occurred while processing {json_file_path}: {e}")
    finally:
        if f_out:
            f_out.close()
            print(f"\nAnalysis results saved to {output_file_path}")

def describe_json_structure(data, print_func, indent_level=0, path=""):
    """
    Recursively describes the structure of the JSON data, focusing on collection logic.
    """
    indent = "  " * indent_level

    if indent_level == 0:
        print_func(f"{indent}Overall JSON Structure for EPUB Collection:")
        print_func(f"{indent}------------------------------------------")

        # Top-level collection metadata
        print_func(f"{indent}Key: 'title' (string) - Title of the entire collection.")
        if 'title' in data:
            print_func(f"{indent}  Example: '{data['title']}'")
        
        print_func(f"{indent}Key: 'source' (string) - Original EPUB filename.")
        if 'source' in data:
            print_func(f"{indent}  Example: '{data['source']}'")

        print_func(f"{indent}Key: 'processing_log' (object) - Contains processing details.")
        if 'processing_log' in data and isinstance(data['processing_log'], dict):
            print_func(f"{indent}  Key: 'processing_log.is_collection' (boolean) - CRITICAL: Indicates if this EPUB contains multiple sub-works.")
            if 'is_collection' in data['processing_log']:
                print_func(f"{indent}    Example: {data['processing_log']['is_collection']}")
            print_func(f"{indent}  ... other processing_log fields (e.g., 'toc_repair', 'sanity_check', 'component_log')")

        print_func(f"{indent}Key: 'epub_metadata' (object) - General metadata for the collection.")
        if 'epub_metadata' in data and isinstance(data['epub_metadata'], dict):
            for key, value in data['epub_metadata'].items():
                print_func(f"{indent}  Key: 'epub_metadata.{key}' (type: {type(value).__name__})")
                if isinstance(value, list):
                    print_func(f"{indent}    Example (first item): {value[0] if value else 'N/A'}")
                else:
                    print_func(f"{indent}    Example: '{value}'")
        
        print_func(f"{indent}Key: 'content' (array) - The main array holding all content blocks.")
        print_func(f"{indent}  This array contains individual 'sections' or 'parts' of the EPUB.")
        print_func(f"{indent}  Each item can be a top-level content piece (like a cover for the whole collection)")
        print_func(f"{indent}  OR a nested 'Section' representing an individual book/volume within the collection.")
        
        if 'content' in data and isinstance(data['content'], list):
            for i, item in enumerate(data['content']):
                item_path = f"{path}.content[{i}]"
                if isinstance(item, dict):
                    item_type = item.get('type')
                    print_func(f"\n{indent}  Item {i}: (Type: '{item_type}')")
                    if item_type == "Section":
                        print_func(f"{indent}    This 'Section' object represents an individual book/volume within the collection.")
                        print_func(f"{indent}    Key: 'title' (string) - Title of this specific sub-volume.")
                        print_func(f"{indent}      Example: '{item.get('title')}'")
                        print_func(f"{indent}    Key: 'inferred-type' (string) - Inferred type for this sub-volume (e.g., 'novel').")
                        print_func(f"{indent}      Example: '{item.get('inferred-type')}'")
                        print_func(f"{indent}    Key: 'content' (array) - Contains the content blocks specific to this sub-volume.")
                        if 'content' in item and isinstance(item['content'], list):
                            for j, sub_item in enumerate(item['content']):
                                print_func(f"{indent}      Sub-Item {j} (Type: '{sub_item.get('type')}') - Content block for this sub-volume.")
                                describe_content_item_fields(sub_item, print_func, indent_level + 3)
                        else:
                            print_func(f"{indent}      (No 'content' array found for this Section, or it's empty/invalid.)")
                    elif item_type == "EpubHtml":
                        print_func(f"{indent}    This 'EpubHtml' object represents a top-level content piece (e.g., overall cover, impressum).")
                        describe_content_item_fields(item, print_func, indent_level + 2)
                    else:
                        print_func(f"{indent}    (Unknown or other type of content item.)")
                        describe_content_item_fields(item, print_func, indent_level + 2)
                else:
                    print_func(f"{indent}  Item {i}: (Non-dictionary item, type: {type(item).__name__}) - Unexpected format.")
        else:
            print_func(f"{indent}(No 'content' array found at top level, or it's empty/invalid.)")

def describe_content_item_fields(item, print_func, indent_level):
    """
    Helper function to describe common fields found in content items (EpubHtml, etc.).
    """
    indent = "  " * indent_level
    for key, value in item.items():
        if key == 'text': # HTML content, too verbose to print fully
            print_func(f"{indent}Key: '{key}' (string) - Contains HTML content. (Not printing full HTML)")
        elif key == 'content' and isinstance(value, list): # Nested content for Sections
            # This case is handled specifically by the main describe_json_structure for "Section" type
            continue 
        else:
            value_type = type(value).__name__
            print_func(f"{indent}Key: '{key}' (type: {value_type})")
            if isinstance(value, list):
                if value:
                    print_func(f"{indent}  Example (first item): '{value[0]}'")
                else:
                    print_func(f"{indent}  Example: [] (empty list)")
            elif isinstance(value, dict):
                print_func(f"{indent}  Example: {{...}} (nested object)")
            else:
                print_func(f"{indent}  Example: '{value}'")


# Set your repository root path (where your JSON files are) and the desired output file path.
# Assuming script is in: ~/code/repos/dimeclass/conversion/scripts/python/
# And JSON files are in: ~/code/repos/dimeclass/conversion/data/json/
# Output to: ~/analysis_results/collection_structure_analysis.txt (create a new folder if needed)

# Adjust these paths based on your actual directory structure
analyze_json_collection_structure(
    repo_root_path="./conversion/data/json",
    output_file_path="./conversion/logs/multivolume_structure_analysis.txt" 
)
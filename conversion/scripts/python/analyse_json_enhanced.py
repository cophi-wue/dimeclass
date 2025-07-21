import json
import os
from bs4 import BeautifulSoup
from collections import defaultdict

def analyze_json_for_tei(repo_root_path=".", output_file_path=None):
    """
    Analyzes JSON files within a specified repository path to extract detailed HTML elements,
    attributes, their values, and classification annotations for TEI mapping.

    Args:
        repo_root_path (str): The relative path to the root of the repository.
                              Defaults to the current directory.
        output_file_path (str, optional): If provided, the analysis output will be written
                                          to this file. If None, output goes to console.
    """
    json_files_found = []
    
    # Global collections for overall summary (kept for completeness)
    global_html_tags = set()
    global_html_attributes = set()
    global_rend_values = set()
    global_style_properties = set()
    global_inferred_types = set()
    global_true_types = set()
    global_epub_metadata_keys = set()
    global_processing_log_keys = set()

    # Detailed collections for tag-attribute combinations
    # Structure: { 'tag_name': { 'attributes': { 'attr_name': set('attr_value1', ...), ... },
    #                              'rend_values': set('rend_value1', ...),
    #                              'style_properties': set('prop1', ...),
    #                              'found_in_inferred_types': set('type1', ...),
    #                              'found_in_true_types': set('type1', ...) } }
    tag_details = defaultdict(lambda: {
        'attributes': defaultdict(set),
        'rend_values': set(),
        'style_properties': set(),
        'found_in_inferred_types': set(),
        'found_in_true_types': set()
    })

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

        print_func(f"Found {len(json_files_found)} JSON files. Processing...\n")

        for json_file_path in json_files_found:
            print_func(f"Analyzing {json_file_path}...")
            try:
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Extract epub_metadata keys
                if 'epub_metadata' in data and isinstance(data['epub_metadata'], dict):
                    global_epub_metadata_keys.update(data['epub_metadata'].keys())

                # Extract processing_log keys
                if 'processing_log' in data and isinstance(data['processing_log'], dict):
                    global_processing_log_keys.update(data['processing_log'].keys())
                    if 'component_log' in data['processing_log'] and isinstance(data['processing_log']['component_log'], list):
                        for log_entry in data['processing_log']['component_log']:
                            if 'added_fields' in log_entry and isinstance(log_entry['added_fields'], list):
                                global_processing_log_keys.update(log_entry['added_fields'])


                # Process content section
                if 'content' in data and isinstance(data['content'], list):
                    for item in data['content']:
                        current_inferred_type = item.get('inferred-type')
                        current_true_type = item.get('true-type')

                        # Extract classification annotations (global)
                        if current_inferred_type:
                            global_inferred_types.add(current_inferred_type)
                        if current_true_type:
                            global_true_types.add(current_true_type)

                        # Extract HTML tags and attributes from 'text' field
                        if 'text' in item and isinstance(item['text'], str):
                            soup = BeautifulSoup(item['text'], 'html.parser')
                            for tag in soup.find_all(True):  # Find all HTML tags
                                global_html_tags.add(tag.name)
                                
                                # Add inferred/true types to tag details
                                if current_inferred_type:
                                    tag_details[tag.name]['found_in_inferred_types'].add(current_inferred_type)
                                if current_true_type:
                                    tag_details[tag.name]['found_in_true_types'].add(current_true_type)

                                for attr, value in tag.attrs.items():
                                    global_html_attributes.add(attr)
                                    # Ensure value is a string or convert it before adding to set
                                    if isinstance(value, list): # BeautifulSoup might return list for multi-valued attributes like class
                                        value = " ".join(value)
                                    tag_details[tag.name]['attributes'][attr].add(value) # Store all values for the attribute

                                    if attr == 'rend':
                                        global_rend_values.add(value)
                                        tag_details[tag.name]['rend_values'].add(value)
                                    elif attr == 'style':
                                        # Parse CSS style string
                                        styles = value.split(';')
                                        for style_prop_val in styles:
                                            if ':' in style_prop_val:
                                                prop, _ = style_prop_val.split(':', 1)
                                                prop = prop.strip()
                                                if prop: # Ensure property is not empty
                                                    global_style_properties.add(prop)
                                                    tag_details[tag.name]['style_properties'].add(prop)

            except json.JSONDecodeError as e:
                print_func(f"Error decoding JSON from {json_file_path}: {e}")
            except Exception as e:
                print_func(f"An unexpected error occurred while processing {json_file_path}: {e}")

        print_func("\n--- Analysis Complete ---")
        print_func("\nOverview of extracted elements and attributes for TEI mapping:")

        print_func("\n--- Detailed Tag-Attribute Combinations ---")
        if tag_details:
            for tag_name in sorted(tag_details.keys()):
                details = tag_details[tag_name]
                print_func(f"\nTag: <{tag_name}>")
                
                if details['attributes']:
                    print_func("  Attributes:")
                    for attr_name in sorted(details['attributes'].keys()):
                        values = sorted(list(details['attributes'][attr_name]))
                        print_func(f"    - {attr_name}: {values}")
                
                if details['rend_values']:
                    print_func(f"  Specific 'rend' values found: {sorted(list(details['rend_values']))}")
                
                if details['style_properties']:
                    print_func(f"  Specific CSS 'style' properties found: {sorted(list(details['style_properties']))}")

                if details['found_in_inferred_types']:
                    print_func(f"  Found in inferred types: {sorted(list(details['found_in_inferred_types']))}")
                
                if details['found_in_true_types']:
                    print_func(f"  Found in true types: {sorted(list(details['found_in_true_types']))}")
        else:
            print_func("  No HTML tags found for detailed analysis.")


        print_func("\n--- Global Summaries (for quick reference) ---")
        print_func("\n1. Unique HTML Tags (Global):")
        if global_html_tags:
            for tag in sorted(list(global_html_tags)):
                print_func(f"  - <{tag}>")
        else:
            print_func("  No HTML tags found.")

        print_func("\n2. Unique HTML Attributes (Global):")
        if global_html_attributes:
            for attr in sorted(list(global_html_attributes)):
                print_func(f"  - {attr}")
        else:
            print_func("  No HTML attributes found.")

        print_func("\n3. Unique 'rend' Attribute Values (Global):")
        if global_rend_values:
            for rend in sorted(list(global_rend_values)):
                print_func(f"  - {rend}")
        else:
            print_func("  No 'rend' values found.")

        print_func("\n4. Unique CSS Style Properties (from 'style' attribute, Global):")
        if global_style_properties:
            for prop in sorted(list(global_style_properties)):
                print_func(f"  - {prop}")
        else:
            print_func("  No CSS style properties found.")

        print_func("\n5. Unique Inferred Content Types (Global):")
        if global_inferred_types:
            for i_type in sorted(list(global_inferred_types)):
                print_func(f"  - {i_type}")
        else:
            print_func("  No inferred types found.")

        print_func("\n6. Unique True Content Types (Global):")
        if global_true_types:
            for t_type in sorted(list(global_true_types)):
                print_func(f"  - {t_type}")
        else:
            print_func("  No true types found.")

        print_func("\n7. Unique EPUB Metadata Keys (Global):")
        if global_epub_metadata_keys:
            for key in sorted(list(global_epub_metadata_keys)):
                print_func(f"  - {key}")
        else:
            print_func("  No EPUB metadata keys found.")

        print_func("\n8. Unique Processing Log Keys (Global):")
        if global_processing_log_keys:
            for key in sorted(list(global_processing_log_keys)):
                print_func(f"  - {key}")
        else:
            print_func("  No processing log keys found.")
    finally:
        if f_out:
            f_out.close()
            print(f"\nAnalysis results saved to {output_file_path}") # Print to console for confirmation

# Given your script is in: ~/code/repos/dimeclass/conversion/scripts/python/
# And your JSON files are in: ~/code/repos/dimeclass/conversion/data/json/
# The path from the script to the JSON files is: go up two directories (../../) then down into data/json/
# To output to a file named 'analysis_results.txt' in the 'dimeclass' root directory:
analyze_json_for_tei(
    repo_root_path="conversion/data/json",
    output_file_path="conversion/logs/json_analysis_results.txt"
)
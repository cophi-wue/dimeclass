import json
import os
from collections import Counter, defaultdict
from bs4 import BeautifulSoup
import pandas as pd
import sys

# --- CONFIGURATION ---

# Set the paths as specified by the user
INPUT_JSON_PATH = '/home/spielberg/code/repos/epub_unpack/11extracted_json'
OUTPUT_ANALYSIS_PATH = '/home/spielberg/code/repos/dimeclass/conversion/logs/analysis_results'

# Tags to focus on for specific analyses
STRUCTURAL_TAGS = ['p', 'div', 'table', 'list', 'graphic', 'head', 'row', 'cell', 'item']
NESTING_TAGS = ['div', 'list']


# --- HELPER FUNCTIONS ---

def find_text_recursively(data_dict):
    """
    Recursively finds all values associated with the 'text' key,
    handling nested 'content' dictionaries.
    """
    all_text = []
    if isinstance(data_dict, dict):
        if 'text' in data_dict:
            all_text.append(data_dict['text'])
        if 'content' in data_dict:
            # The content can be a dict or a list of dicts
            content_data = data_dict['content']
            if isinstance(content_data, list):
                for item in content_data:
                    all_text.extend(find_text_recursively(item))
            elif isinstance(content_data, dict):
                all_text.extend(find_text_recursively(content_data))
    return all_text


def get_element_string(tag):
    """Creates a unique string representation of a tag and its attributes."""
    attrs = ' '.join(f'{k}="{v}"' for k, v in sorted(tag.attrs.items()))
    return f"<{tag.name} {attrs}>" if attrs else f"<{tag.name}>"


def get_nesting_depth(tag, current_depth=1):
    """Calculates the maximum nesting depth of a specific tag within itself."""
    max_depth = current_depth
    for child in tag.find_all(tag.name, recursive=False):
        depth = get_nesting_depth(child, current_depth + 1)
        if depth > max_depth:
            max_depth = depth
    return max_depth


# --- ANALYSIS CORE ---

def analyze_ebook(file_path):
    """
    Analyzes a single ebook JSON file and returns structured results.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None

    # 1. Extract HTML content
    html_parts = find_text_recursively(data)
    if not html_parts:
        return None
    # Wrap content in a single root element for valid parsing
    full_html = f"<body>{''.join(str(part) for part in html_parts if part)}</body>"
    soup = BeautifulSoup(full_html, 'lxml')

    # Initialize containers for this book's data
    book_results = {
        'tags_in_doc': set(),
        'tag_freq': Counter(),
        'attr_freq': Counter(),
        'attr_value_freq': defaultdict(Counter),
        'distinct_elements': Counter(),
        'parent_child': defaultdict(Counter),
        'tag_adjacency_2': Counter(),
        'tag_adjacency_3': Counter(),
        'nesting_depth': {tag: {'max': 0, 'depths': []} for tag in NESTING_TAGS}
    }

    all_tags = soup.find_all(True)
    tag_names = [tag.name for tag in all_tags]

    for i, tag in enumerate(all_tags):
        # --- Core Frequency Analysis ---
        book_results['tags_in_doc'].add(tag.name)
        book_results['tag_freq'][tag.name] += 1
        book_results['distinct_elements'][get_element_string(tag)] += 1

        for attr, value in tag.attrs.items():
            book_results['attr_freq'][attr] += 1
            # Store values as a list if they are multi-valued (like class)
            values = value if isinstance(value, list) else [value]
            for val in values:
                book_results['attr_value_freq'][attr][val] += 1

        # --- Structural and Contextual Analysis ---
        # Parent-Child Relationships
        if tag.name in STRUCTURAL_TAGS and tag.parent:
            book_results['parent_child'][tag.name][tag.parent.name] += 1

        # Nesting Depth
        if tag.name in NESTING_TAGS and not tag.find_parents(tag.name):
             # Only calculate from the outermost tag to avoid re-calculation
            max_d = get_nesting_depth(tag)
            book_results['nesting_depth'][tag.name]['depths'].append(max_d)
            if max_d > book_results['nesting_depth'][tag.name]['max']:
                book_results['nesting_depth'][tag.name]['max'] = max_d


    # Tag Adjacency (N-grams)
    for j in range(len(tag_names) - 1):
        book_results['tag_adjacency_2'][(tag_names[j], tag_names[j+1])] += 1
    for j in range(len(tag_names) - 2):
        book_results['tag_adjacency_3'][(tag_names[j], tag_names[j+1], tag_names[j+2])] += 1

    return book_results


# --- MAIN EXECUTION ---

def main():
    """
    Main function to orchestrate the analysis of all ebooks.
    """
    print("Starting eBook analysis...")
    if not os.path.exists(INPUT_JSON_PATH):
        print(f"Error: Input directory not found at {INPUT_JSON_PATH}", file=sys.stderr)
        return

    os.makedirs(OUTPUT_ANALYSIS_PATH, exist_ok=True)

    # --- MODIFIED PART: Find all JSON files in subdirectories ---
    json_files_to_process = []
    for root, dirs, files in os.walk(INPUT_JSON_PATH):
        for file in files:
            if file.endswith('.json'):
                json_files_to_process.append(os.path.join(root, file))

    total_files = len(json_files_to_process)
    if total_files == 0:
        print(f"Error: No .json files found in subdirectories of {INPUT_JSON_PATH}", file=sys.stderr)
        return

    print(f"Found {total_files} JSON files to analyze.")

    # --- Initialize global data aggregators ---
    # Core Frequency
    global_tag_freq = Counter()
    global_doc_freq = Counter()
    global_attr_freq = Counter()
    global_attr_value_freq = defaultdict(Counter)
    global_distinct_elements = Counter()
    # Structural
    global_parent_child = defaultdict(Counter)
    global_tag_adjacency_2 = Counter()
    global_tag_adjacency_3 = Counter()
    global_nesting_depth = {tag: {'max': 0, 'total_depth': 0, 'count': 0} for tag in NESTING_TAGS}


    # --- Process each file ---
    for i, file_path in enumerate(json_files_to_process):
        print(f"Processing file {i+1}/{total_files}: {os.path.basename(file_path)}")
        book_data = analyze_ebook(file_path)

        if book_data:
            # Aggregate Core Frequency data
            global_tag_freq.update(book_data['tag_freq'])
            global_attr_freq.update(book_data['attr_freq'])
            global_distinct_elements.update(book_data['distinct_elements'])
            for tag in book_data['tags_in_doc']:
                global_doc_freq[tag] += 1
            for attr, values in book_data['attr_value_freq'].items():
                global_attr_value_freq[attr].update(values)

            # Aggregate Structural data
            for parent, children in book_data['parent_child'].items():
                global_parent_child[parent].update(children)
            global_tag_adjacency_2.update(book_data['tag_adjacency_2'])
            global_tag_adjacency_3.update(book_data['tag_adjacency_3'])
            for tag in NESTING_TAGS:
                if book_data['nesting_depth'][tag]['depths']:
                    tag_nesting = book_data['nesting_depth'][tag]
                    if tag_nesting['max'] > global_nesting_depth[tag]['max']:
                        global_nesting_depth[tag]['max'] = tag_nesting['max']
                    global_nesting_depth[tag]['total_depth'] += sum(tag_nesting['depths'])
                    global_nesting_depth[tag]['count'] += len(tag_nesting['depths'])


    # --- Save aggregated results to CSV files ---
    print("\nAnalysis complete. Saving results...")

    # 1. Overall Tag Frequency
    df = pd.DataFrame(global_tag_freq.most_common(), columns=['Tag', 'Frequency'])
    df.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, '1_overall_tag_frequency.csv'), index=False)

    # 2. Document Frequency
    df = pd.DataFrame(global_doc_freq.most_common(), columns=['Tag', 'DocumentCount'])
    df['Widespreadness (%)'] = (df['DocumentCount'] / total_files * 100).round(2)
    df.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, '2_document_frequency.csv'), index=False)

    # 3. Attribute Frequency
    df = pd.DataFrame(global_attr_freq.most_common(), columns=['Attribute', 'Frequency'])
    df.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, '3_attribute_frequency.csv'), index=False)

    # 4. Attribute Value Frequency (for class and style)
    for attr_name in ['class', 'style']:
        if global_attr_value_freq[attr_name]:
            df = pd.DataFrame(global_attr_value_freq[attr_name].most_common(500), columns=['Value', 'Frequency'])
            df.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, f'4_attribute_values_{attr_name}.csv'), index=False)

    # 5. Distinct Element Inventory
    df = pd.DataFrame(global_distinct_elements.most_common(), columns=['Element', 'Frequency'])
    df.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, '5_distinct_element_inventory.csv'), index=False)

    # 6. Parent-Child Relationships
    parent_child_list = []
    for child, parents in global_parent_child.items():
        for parent, count in parents.most_common():
            parent_child_list.append({'Child_Tag': child, 'Parent_Tag': parent, 'Frequency': count})
    df = pd.DataFrame(parent_child_list)
    df.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, '6_parent_child_relationships.csv'), index=False)

    # 7. Tag Adjacency (N-grams)
    df_2gram = pd.DataFrame(global_tag_adjacency_2.most_common(), columns=['Tag_Sequence', 'Frequency'])
    df_2gram['Tag_Sequence'] = df_2gram['Tag_Sequence'].apply(lambda x: ' -> '.join(x))
    df_2gram.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, '7a_tag_adjacency_2gram.csv'), index=False)

    df_3gram = pd.DataFrame(global_tag_adjacency_3.most_common(), columns=['Tag_Sequence', 'Frequency'])
    df_3gram['Tag_Sequence'] = df_3gram['Tag_Sequence'].apply(lambda x: ' -> '.join(x))
    df_3gram.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, '7b_tag_adjacency_3gram.csv'), index=False)

    # 8. Nesting Depth Analysis
    nesting_data = []
    for tag, data in global_nesting_depth.items():
        avg_depth = (data['total_depth'] / data['count']) if data['count'] > 0 else 0
        nesting_data.append({
            'Tag': tag,
            'Max_Depth_Found': data['max'],
            'Average_Depth': round(avg_depth, 2)
        })
    df = pd.DataFrame(nesting_data)
    df.to_csv(os.path.join(OUTPUT_ANALYSIS_PATH, '8_nesting_depth.csv'), index=False)

    print(f"\nAll results have been saved to: {OUTPUT_ANALYSIS_PATH}")


if __name__ == '__main__':
    main()
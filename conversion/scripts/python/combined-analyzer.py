import json
import os
import re
from collections import Counter, defaultdict
from bs4 import BeautifulSoup
import pandas as pd
import sys

# --- CONFIGURATION ---
INPUT_JSON_PATH = '/home/spielberg/code/repos/epub_unpack/11extracted_json'
OUTPUT_ANALYSIS_PATH = '/home/spielberg/code/repos/dimeclass/conversion/logs/analysis_results'

# Tags to focus on for specific analyses
STRUCTURAL_TAGS = ['p', 'img', 'table', 'div', 'span', 'h1']


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


def clean_filename(name):
    """Removes invalid characters for directory names."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)


# --- ANALYSIS CORE ---

def analyze_ebook_for_publisher(file_path):
    """
    Analyzes a single ebook JSON file and returns its publisher and
    structured content analysis results.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None, None

    # 1. Determine the publisher
    publisher = "__UNKNOWN_PUBLISHER__"
    if 'epub_metadata' in data and isinstance(data['epub_metadata'], dict):
        metadata = data['epub_metadata']
        if 'publisher' in metadata:
            pub_value = metadata['publisher']
            if isinstance(pub_value, list) and pub_value:
                publisher = pub_value[0]
            elif isinstance(pub_value, str) and pub_value:
                publisher = pub_value

    # 2. Extract and analyze HTML content
    html_parts = find_text_recursively(data)
    if not html_parts:
        return publisher, None
    full_html = f"<body>{''.join(str(part) for part in html_parts if part)}</body>"
    soup = BeautifulSoup(full_html, 'lxml')

    # Initialize containers for this book's data
    book_results = {
        'tags_in_doc': set(),
        'attr_freq': Counter(),
        'attr_value_freq': defaultdict(Counter),
        'distinct_elements': Counter(),
        'parent_child': defaultdict(Counter),
        'book_count': 1 # Used to track document frequency per publisher
    }

    all_tags = soup.find_all(True)
    for tag in all_tags:
        book_results['tags_in_doc'].add(tag.name)
        book_results['distinct_elements'][get_element_string(tag)] += 1

        for attr, value in tag.attrs.items():
            book_results['attr_freq'][attr] += 1
            values = value if isinstance(value, list) else [value]
            for val in values:
                book_results['attr_value_freq'][attr][val] += 1

        if tag.name in STRUCTURAL_TAGS and tag.parent:
            book_results['parent_child'][tag.name][tag.parent.name] += 1

    return publisher, book_results


def save_publisher_results(publisher_name, data, output_base_path):
    """Saves the aggregated analysis results for a single publisher to CSVs."""

    # Create a safe directory name for the publisher
    safe_publisher_name = clean_filename(publisher_name)
    publisher_dir = os.path.join(output_base_path, 'by_publisher', safe_publisher_name)
    os.makedirs(publisher_dir, exist_ok=True)

    print(f"  - Saving results for: {publisher_name}")

    total_books = data['book_count']

    # 1. Distinct Element Inventory (Most important for this request)
    df = pd.DataFrame(data['distinct_elements'].most_common(), columns=['Element', 'Frequency'])
    df.to_csv(os.path.join(publisher_dir, '1_distinct_element_inventory.csv'), index=False)

    # 2. Document Frequency for Tags
    df = pd.DataFrame(data['doc_freq'].most_common(), columns=['Tag', 'DocumentCount'])
    df['Widespreadness (%)'] = (df['DocumentCount'] / total_books * 100).round(2)
    df.to_csv(os.path.join(publisher_dir, '2_document_frequency.csv'), index=False)

    # 3. Attribute Frequency
    df = pd.DataFrame(data['attr_freq'].most_common(), columns=['Attribute', 'Frequency'])
    df.to_csv(os.path.join(publisher_dir, '3_attribute_frequency.csv'), index=False)

    # 4. Attribute Value Frequency (for class and style)
    for attr_name in ['class', 'style']:
        if data['attr_value_freq'][attr_name]:
            df = pd.DataFrame(data['attr_value_freq'][attr_name].most_common(500), columns=['Value', 'Frequency'])
            df.to_csv(os.path.join(publisher_dir, f'4_attribute_values_{attr_name}.csv'), index=False)

    # 5. Parent-Child Relationships
    parent_child_list = []
    for child, parents in data['parent_child'].items():
        for parent, count in parents.most_common():
            parent_child_list.append({'Child_Tag': child, 'Parent_Tag': parent, 'Frequency': count})
    df = pd.DataFrame(parent_child_list)
    df.to_csv(os.path.join(publisher_dir, '5_parent_child_relationships.csv'), index=False)


# --- MAIN EXECUTION ---

def main():
    print("Starting combined publisher and content analysis...")
    if not os.path.exists(INPUT_JSON_PATH):
        print(f"Error: Input directory not found at {INPUT_JSON_PATH}", file=sys.stderr)
        return

    # Find all JSON files
    json_files = [os.path.join(r, f) for r, _, fs in os.walk(INPUT_JSON_PATH) for f in fs if f.endswith('.json')]
    total_files = len(json_files)
    print(f"Found {total_files} JSON files to analyze.")

    # Main data structure to hold aggregations for each publisher
    publisher_data = defaultdict(lambda: {
        'doc_freq': Counter(),
        'attr_freq': Counter(),
        'attr_value_freq': defaultdict(Counter),
        'distinct_elements': Counter(),
        'parent_child': defaultdict(Counter),
        'book_count': 0
    })

    # Process each file and aggregate data by publisher
    for i, file_path in enumerate(json_files):
        print(f"Processing file {i+1}/{total_files}: {os.path.basename(file_path)}")
        publisher, book_data = analyze_ebook_for_publisher(file_path)

        if book_data:
            # Get the dictionary for the current publisher
            p_data = publisher_data[publisher]

            # Aggregate the data
            p_data['book_count'] += 1
            p_data['attr_freq'].update(book_data['attr_freq'])
            p_data['distinct_elements'].update(book_data['distinct_elements'])

            for tag in book_data['tags_in_doc']:
                p_data['doc_freq'][tag] += 1

            for attr, values in book_data['attr_value_freq'].items():
                p_data['attr_value_freq'][attr].update(values)

            for child, parents in book_data['parent_child'].items():
                p_data['parent_child'][child].update(parents)

    # Save the results for each publisher
    print("\nAnalysis complete. Saving results for each publisher...")
    for publisher_name, data in publisher_data.items():
        save_publisher_results(publisher_name, data, OUTPUT_ANALYSIS_PATH)

    print(f"\nAll publisher-specific reports saved to: {os.path.join(OUTPUT_ANALYSIS_PATH, 'by_publisher')}")


if __name__ == '__main__':
    main()
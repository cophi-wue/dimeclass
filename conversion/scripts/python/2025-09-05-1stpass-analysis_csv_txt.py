import os
import json
from collections import defaultdict
from bs4 import BeautifulSoup
import csv
import re

# Define file paths
JSON_DIR = '/home/spielberg/code/repos/epub_unpack/11extracted_json'
LOG_FILE = '/home/spielberg/code/repos/dimeclass/conversion/logs/ebook_analysis_results.txt'
CSV_FILE = '/home/spielberg/code/repos/dimeclass/conversion/logs/tag_analysis.csv'

def find_text_fields(data, text_fields):
    """Recursively finds all 'text' fields in the JSON data."""
    if isinstance(data, dict):
        if 'text' in data and data['text'] and isinstance(data['text'], str):
            text_fields.append(data['text'])
        for key, value in data.items():
            find_text_fields(value, text_fields)
    elif isinstance(data, list):
        for item in data:
            find_text_fields(item, text_fields)

def analyze_html(html_content, stats):
    """Parses HTML and updates analysis statistics."""
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.find_all(True):
        tag_name = tag.name
        stats['tag_counts'][tag_name] += 1

        if 'class' in tag.attrs:
            for cls in tag['class']:
                tag_class = f"{tag_name}.{cls}"
                stats['tag_class_counts'][tag_class] += 1

        for attr, value in tag.attrs.items():
            if isinstance(value, list):
                value = ' '.join(value)
            attr_key = f"{tag_name}@{attr}"
            stats['attribute_counts'][attr_key] += 1
            attr_value_key = f"{attr_key}={value}"
            stats['attribute_value_counts'][attr_value_key] += 1

        if tag_name in ['p', 'div'] and tag.get('style') and 'text-indent' in tag['style']:
            stats['paragraph_start_style_counts'][tag_name] += 1

        if tag_name in ['head', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            context = {
                'tag': str(tag),
                'previous_sibling': str(tag.previous_sibling) if tag.previous_sibling else None,
                'next_sibling': str(tag.next_sibling) if tag.next_sibling else None
            }
            stats['heading_context'].append(context)

def main():
    """Main function to perform the analysis and write results."""
    stats = {
        'tag_counts': defaultdict(int),
        'tag_class_counts': defaultdict(int),
        'attribute_counts': defaultdict(int),
        'attribute_value_counts': defaultdict(int),
        'paragraph_start_style_counts': defaultdict(int),
        'heading_context': []
    }

    # Check if the directory exists and has files
    if not os.path.isdir(JSON_DIR):
        print(f"Error: Directory not found at {JSON_DIR}")
        return

    json_files = []
    for root, dirs, files in os.walk(JSON_DIR):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))

    if not json_files:
        print(f"Error: No JSON files found in {JSON_DIR} or its subdirectories")
        return

    print(f"Found {len(json_files)} JSON files. Starting analysis...")

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            text_fields = []
            find_text_fields(data, text_fields)

            if not text_fields:
                print(f"Warning: No 'text' fields found in {file_path}")

            for html_content in text_fields:
                analyze_html(html_content, stats)

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # Write results to log file
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("--- Ebook HTML/CSS Analysis Results ---\n\n")

        f.write("1. Most Frequent Tags:\n")
        sorted_tags = sorted(stats['tag_counts'].items(), key=lambda item: item[1], reverse=True)
        for tag, count in sorted_tags[:50]:
            f.write(f"- <{tag}>: {count}\n")

        f.write("\n2. Most Frequent Tags with CSS Classes:\n")
        sorted_tag_classes = sorted(stats['tag_class_counts'].items(), key=lambda item: item[1], reverse=True)
        for tag_class, count in sorted_tag_classes[:50]:
            f.write(f"- {tag_class}: {count}\n")

        f.write("\n3. Common Attribute-Value Pairs:\n")
        sorted_attr_values = sorted(stats['attribute_value_counts'].items(), key=lambda item: item[1], reverse=True)
        for attr_value, count in sorted_attr_values[:50]:
            f.write(f"- {attr_value}: {count}\n")

        f.write("\n4. Paragraph Start Style Counts:\n")
        for tag, count in stats['paragraph_start_style_counts'].items():
            f.write(f"- {tag} tags with text-indent style: {count}\n")

        f.write("\n5. Sample Heading Contexts (for Chapter/Section Starts):\n")
        for i, context in enumerate(stats['heading_context'][:10]):
            f.write(f"--- Sample {i+1} ---\n")
            f.write(f"  Tag: {context['tag']}\n")
            f.write(f"  Previous Sibling: {context['previous_sibling']}\n")
            f.write(f"  Next Sibling: {context['next_sibling']}\n\n")

    # Write results to CSV file
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Element', 'Type', 'Count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for tag, count in sorted_tags:
            writer.writerow({'Element': f"<{tag}>", 'Type': 'Tag', 'Count': count})

        for tag_class, count in sorted_tag_classes:
            writer.writerow({'Element': tag_class, 'Type': 'Tag+Class', 'Count': count})

        for attr_value, count in sorted_attr_values:
            writer.writerow({'Element': attr_value, 'Type': 'Attribute', 'Count': count})

    print(f"Analysis complete. Results written to {LOG_FILE} and {CSV_FILE}.")

if __name__ == '__main__':
    main()
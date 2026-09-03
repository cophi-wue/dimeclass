import os
import json
from collections import defaultdict
from bs4 import BeautifulSoup
import csv
import re

# Define file paths
JSON_DIR = '/home/spielberg/code/repos/epub_unpack/11extracted_json'
LOG_FILE = '/home/spielberg/code/repos/dimeclass/conversion/logs/2025-09-05-2-ebook_analysis_round2.txt'
COOCCURRENCE_CSV = '/home/spielberg/code/repos/dimeclass/conversion/logs/2025-09-05-2-cooccurrence.csv'
SNIPPET_LOG = '/home/spielberg/code/repos/dimeclass/conversion/logs/2025-09-05-2-tag_snippets.txt'

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

def analyze_html_publisher_aware(file_path, stats):
    """Parses HTML and updates analysis statistics, aware of publishers."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    publisher = data.get('epub_metadata', {}).get('publisher', 'Unknown')
    if publisher not in stats['publisher_stats']:
        stats['publisher_stats'][publisher] = defaultdict(int)

    text_fields = []
    find_text_fields(data, text_fields)

    for html_content in text_fields:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Co-occurrence and structural analysis
        prev_tag = None
        for tag in soup.find_all(True):
            if prev_tag:
                cooccurrence_key = f"<{prev_tag.name}> -> <{tag.name}>"
                stats['cooccurrence_counts'][cooccurrence_key] += 1
            prev_tag = tag

        # Targeted snippet extraction
        for tag in soup.find_all(['p', 'head']):
            if len(stats['tag_snippets'][tag.name]) < 100:  # Collect a sample of 100
                snippet_text = str(tag.extract())
                # Truncate long snippets for readability
                snippet_text = (snippet_text[:200] + '...') if len(snippet_text) > 200 else snippet_text
                stats['tag_snippets'][tag.name].append({'publisher': publisher, 'snippet': snippet_text})

        # Publisher-specific tag counts
        for tag in soup.find_all(True):
            stats['publisher_stats'][publisher][tag.name] += 1
            if 'class' in tag.attrs:
                for cls in tag['class']:
                    tag_class = f"{tag.name}.{cls}"
                    stats['publisher_stats'][publisher][tag_class] += 1

def main():
    """Main function to perform the analysis and write results."""
    stats = {
        'publisher_stats': {},
        'cooccurrence_counts': defaultdict(int),
        'tag_snippets': defaultdict(list)
    }

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
            analyze_html_publisher_aware(file_path, stats)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # Write results to log files
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("--- Ebook Structural Analysis (Round 2) ---\n\n")

        f.write("1. Top Co-occurring Tag Pairs (likely structural relationships):\n")
        sorted_cooccurrence = sorted(stats['cooccurrence_counts'].items(), key=lambda item: item[1], reverse=True)
        for pair, count in sorted_cooccurrence[:50]:
            f.write(f"- {pair}: {count}\n")

        f.write("\n2. Tag and Class Counts by Publisher:\n")
        for publisher, publisher_data in stats['publisher_stats'].items():
            f.write(f"\n--- Publisher: {publisher} ---\n")
            sorted_publisher_counts = sorted(publisher_data.items(), key=lambda item: item[1], reverse=True)
            for item, count in sorted_publisher_counts[:20]:
                f.write(f"- {item}: {count}\n")

    with open(SNIPPET_LOG, 'w', encoding='utf-8') as f:
        f.write("--- Sampled HTML Snippets for Manual Review ---\n\n")
        for tag_name, snippets in stats['tag_snippets'].items():
            f.write(f"\n--- Snippets for <{tag_name}> Tag ---\n")
            for i, snippet_data in enumerate(snippets):
                f.write(f"Sample {i+1} (Publisher: {snippet_data['publisher']}):\n")
                f.write(f"  Snippet: {snippet_data['snippet']}\n\n")

    # Write co-occurrence data to CSV
    with open(COOCCURRENCE_CSV, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['preceding_tag', 'succeeding_tag', 'count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for pair, count in sorted_cooccurrence:
            preceding, succeeding = pair.split(' -> ')
            writer.writerow({'preceding_tag': preceding, 'succeeding_tag': succeeding, 'count': count})

    print("Second round of analysis complete.")

if __name__ == '__main__':
    main()
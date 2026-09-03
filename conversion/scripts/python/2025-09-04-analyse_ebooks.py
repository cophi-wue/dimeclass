#!/usr/bin/env python3
"""
Analyse ebook JSON files for HTML tags, attributes, and classes.

- Traverses all JSON files under /home/spielberg/code/repos/epub_unpack/11extracted_json
- Recursively extracts "text" fields inside the "content" lists
- Parses HTML fragments to count tags, attributes, and class usage
- Writes CSV outputs into /home/spielberg/code/repos/dimeclass/conversion/logs
"""

from pathlib import Path
import json
from collections import Counter
from lxml import html

# --- Paths ---
JSON_ROOT = Path("/home/spielberg/code/repos/epub_unpack/11extracted_json")
LOG_DIR = Path("/home/spielberg/code/repos/dimeclass/conversion/logs/analysis_results")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Counters ---
tag_counter = Counter()
attr_counter = Counter()
class_counter = Counter()

# --- Recursive extractor for "text" fields ---
def walk_content(content_list):
    """Recursively yield all text fields from the 'content' structures."""
    for entry in content_list:
        if "text" in entry and entry["text"]:
            yield entry["text"]

        if "content" in entry and isinstance(entry["content"], list):
            yield from walk_content(entry["content"])

def process_html_fragment(fragment):
    """Parse an HTML fragment and update counters."""
    try:
        dom = html.fromstring(fragment)
    except Exception:
        return  # skip broken HTML

    for el in dom.iter():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag.lower()
        tag_counter[tag] += 1

        for attr, val in el.attrib.items():
            attr = attr.lower()
            attr_counter[(tag, attr)] += 1

            if attr == "class":
                for c in val.split():
                    class_counter[c] += 1

def analyse_json(path: Path):
    """Analyse a single JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Could not read {path}: {e}")
        return

    if "content" in data and isinstance(data["content"], list):
        for text_fragment in walk_content(data["content"]):
            process_html_fragment(text_fragment)

def dump_counter_to_csv(counter: Counter, filepath: Path, headers: tuple):
    """Write a Counter object into a CSV file."""
    with filepath.open("w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        for key, count in counter.most_common():
            row = list(key) if isinstance(key, tuple) else [key]
            # escape commas in values
            row = [str(x).replace(",", "⟨,⟩") for x in row]
            f.write(",".join(row) + f",{count}\n")

def run_corpus():
    for json_file in JSON_ROOT.rglob("*.json"):
        analyse_json(json_file)

    # Write outputs
    dump_counter_to_csv(tag_counter, LOG_DIR / "tags.csv", ("tag", "count"))
    dump_counter_to_csv(attr_counter, LOG_DIR / "attributes.csv", ("tag", "attribute", "count"))
    dump_counter_to_csv(class_counter, LOG_DIR / "classes.csv", ("class", "count"))

    print(f"Analysis complete. Results written to {LOG_DIR}")

if __name__ == "__main__":
    run_corpus()

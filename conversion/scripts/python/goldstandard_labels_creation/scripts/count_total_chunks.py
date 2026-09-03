import os
import json
import re

# --- HYBRID PATH RESOLUTION ---
ABS_BASE_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation"
ABS_SOURCE_JSON_DIR = os.path.join(ABS_BASE_DIR, "source_json")
ABS_GOLD_FILE = os.path.join(ABS_BASE_DIR, "goldstandard_verified/manual_labels_unsorted_chunks")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR.endswith("scripts"):
    REL_BASE_DIR = os.path.dirname(SCRIPT_DIR)
else:
    REL_BASE_DIR = SCRIPT_DIR

REL_SOURCE_JSON_DIR = os.path.join(REL_BASE_DIR, "source_json")
REL_GOLD_FILE = os.path.join(REL_BASE_DIR, "goldstandard_verified/manual_labels_unsorted_chunks")

if os.path.exists(ABS_SOURCE_JSON_DIR):
    SOURCE_JSON_DIR = ABS_SOURCE_JSON_DIR
    GOLD_FILE = ABS_GOLD_FILE
    path_source = f"Absolute Rechenknecht Paths ({ABS_BASE_DIR})"
else:
    SOURCE_JSON_DIR = REL_SOURCE_JSON_DIR
    GOLD_FILE = REL_GOLD_FILE
    path_source = f"Relative Script Paths ({REL_BASE_DIR})"

STAR_SEPARATOR_PATTERN = r'<p[^>]*>\s*(?:\*\s*)+\s*</p>'
JPG_SEPARATOR_PATTERN = r'<p[^>]*>(?:<p[^>]*>)?\s*<graphic[^>]*url="[^"]+\.jpg"[^>]*/>\s*(?:\s*</p>){1,2}'

def flatten_content(data, current_id, collector):
    """Recursively traverses the book JSON to collect all flat text segments."""
    if isinstance(data, list):
        for idx, item in enumerate(data):
            flatten_content(item, f"{current_id}_{idx}", collector)
    elif isinstance(data, dict):
        if "text" in data and data["text"]:
            collector.append({
                "id": current_id,
                "text": data["text"],
                "inferred_type": data.get("inferred-type", "unknown")
            })
        if "content" in data:
            flatten_content(data["content"], current_id, collector)

def count_chunks_for_node(node):
    """Calculates how many sub-chunks are generated based on splitting rules."""
    text = node["text"]
    inf_type = node["inferred_type"]

    if "chapter" in inf_type:
        return 1

    if re.search(STAR_SEPARATOR_PATTERN, text):
        parts = re.split(STAR_SEPARATOR_PATTERN, text)
        return len([p for p in parts if p.strip()])
    elif re.search(JPG_SEPARATOR_PATTERN, text):
        parts = re.split(JPG_SEPARATOR_PATTERN, text)
        return len([p for p in parts if p.strip()])

    return 1

def main():
    print("================ PATH DEBUGGING ================")
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Script File Location:      {__file__}")
    print(f"Path Source Selected:      {path_source}")
    print(f"Targeting Source JSONs:    {SOURCE_JSON_DIR}")
    print(f"Targeting Gold Labels:     {GOLD_FILE}")
    print("================================================\n")

    if not os.path.exists(SOURCE_JSON_DIR):
        print(f"ERROR: The folder '{SOURCE_JSON_DIR}' could not be resolved!")
        return

    # 1. Gelabelte IDs laden und für robusten Abgleich normalisieren (ohne .json)
    normalized_gold_ids = set()
    raw_gold_count = 0
    if os.path.exists(GOLD_FILE):
        try:
            with open(GOLD_FILE, 'r', encoding='utf-8') as f:
                gold_data = json.load(f)
                for entry in gold_data:
                    for cid in entry.keys():
                        raw_gold_count += 1
                        # Wir entfernen temporär das '.json' für einen fehlerfreien Abgleich
                        normalized_gold_ids.add(cid.replace(".json", ""))
            print(f"✓ {raw_gold_count} verifizierte IDs aus Goldstandard geladen.")
        except Exception as e:
            print(f"⚠️ Fehler beim Lesen der Goldstandard-Datei: {e}")
    else:
        print(f"⚠️ Goldstandard-Datei nicht gefunden unter: {GOLD_FILE}")

    # 2. JSONs parsen und Chunks simulieren
    json_files = [f for f in os.listdir(SOURCE_JSON_DIR) if f.endswith('.json')]
    total_books = len(json_files)
    generated_chunks = []

    print(f"Scanne {total_books} Bücher in {SOURCE_JSON_DIR}...")

    for file_name in json_files:
        file_path = os.path.join(SOURCE_JSON_DIR, file_name)

        # Für den Abgleich nutzen wir den Dateinamen ohne .json am Ende
        base_name_clean = file_name.replace(".json", "")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                book_data = json.load(f)

            nodes = []
            if isinstance(book_data.get("content"), list) and book_data.get("processing_log", {}).get("is_collection", False):
                for book_idx, sub_book in enumerate(book_data["content"]):
                    flatten_content(sub_book, f"{base_name_clean}_{book_idx + 1}", nodes)
            else:
                flatten_content(book_data, f"{base_name_clean}_0", nodes)

            for node in nodes:
                num_parts = count_chunks_for_node(node)
                if num_parts > 1:
                    for i in range(num_parts):
                        generated_chunks.append(f"{node['id']}_part{i+1:02d}")
                else:
                    generated_chunks.append(node['id'])
        except Exception as e:
            print(f"⚠️ Fehler beim Einlesen von {file_name}: {e}")

    total_chunks = len(generated_chunks)

    # Abgleich über die normalisierte ID-Menge (ohne .json)
    already_labeled_count = sum(1 for cid in generated_chunks if cid in normalized_gold_ids)
    unlabeled_count = total_chunks - already_labeled_count

    print("\n================ STATISTIK ================")
    print(f"Anzahl Bücher im Ordner:      {total_books}")
    print(f"Gesamtanzahl Chunks:          {total_chunks}")
    print(f"Bereits gelabelte Chunks:     {already_labeled_count}")
    print(f"Noch zu labelnde Chunks:      {unlabeled_count}")
    print("===========================================")

if __name__ == "__main__":
    main()
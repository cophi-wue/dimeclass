import os
import json
import csv
from pathlib import Path

# Pfad-Definitionen
BASE_DIR = Path(__file__).parent.parent
SOURCE_DIR = BASE_DIR / "source_json"
ANSWERS_FILE = BASE_DIR / "llm_answers" / "llm_label_answer.json"
OUTPUT_DIR = BASE_DIR / "goldstandard_verified_labels"
REPORT_DIR = BASE_DIR / "reports"

def setup_folders():
    """Erstellt notwendige Ordner."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

def load_llm_answers():
    """Lädt die LLM-Antworten und flacht sie zu einem Dictionary ab."""
    if not ANSWERS_FILE.exists():
        print(f"Fehler: {ANSWERS_FILE} nicht gefunden!")
        return {}

    with open(ANSWERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Falls die Daten als Liste von Dicts kommen, mergen wir sie zu einem großen Dict
    if isinstance(data, list):
        merged_answers = {}
        for entry in data:
            if isinstance(entry, dict):
                merged_answers.update(entry)
        return merged_answers
    return data

def merge_labels():
    setup_folders()
    labels_dict = load_llm_answers()

    if not labels_dict:
        print("Keine Labels zum Mergen gefunden.")
        return

    print(f"{len(labels_dict)} Labels aus LLM-Antwort geladen.")

    report_data = []
    total_processed_files = 0
    total_labeled_chunks = 0

    # Alle Original-JSONs im Source-Ordner durchgehen
    for file_path in SOURCE_DIR.glob("*.json"):
        filename = file_path.name
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        is_collection = data.get("processing_log", {}).get("is_collection", False)
        content_list = data.get("content", [])

        # Logik zum Durchlaufen der Chunks (muss identisch zum Extraktions-Skript sein)
        if is_collection:
            sub_book_counter = 1
            global_chunk_counter = 0
            for item in content_list:
                if "content" in item and isinstance(item["content"], list):
                    for chunk_idx, chunk in enumerate(item["content"]):
                        total_labeled_chunks += process_chunk(filename, sub_book_counter, chunk_idx, chunk, labels_dict, report_data)
                    sub_book_counter += 1
                else:
                    total_labeled_chunks += process_chunk(filename, 0, global_chunk_counter, item, labels_dict, report_data)
                    global_chunk_counter += 1
        else:
            for chunk_idx, chunk in enumerate(content_list):
                total_labeled_chunks += process_chunk(filename, 0, chunk_idx, chunk, labels_dict, report_data)

        # Speichern der modifizierten Datei
        with open(OUTPUT_DIR / filename, "w", encoding="utf-8") as out_f:
            json.dump(data, out_f, indent=4, ensure_ascii=False)

        total_processed_files += 1

    # Report erstellen (TSV für Excel/LibreOffice)
    write_report(report_data)

    print(f"\n--- Zusammenfassung ---")
    print(f"Dateien verarbeitet: {total_processed_files}")
    print(f"Chunks erfolgreich gelabelt: {total_labeled_chunks}")
    print(f"Report erstellt unter: {REPORT_DIR / 'verification_report.tsv'}")

def process_chunk(filename, book_idx, chunk_idx, chunk, labels_dict, report_data):
    """Sucht das passende Label und fügt 'true_type' direkt nach 'inferred-type' ein."""
    href = chunk.get("href", "unknown_href")
    href_clean = os.path.basename(href)
    chunk_id = f"{filename}_{book_idx}_{chunk_idx}_{href_clean}"

    label = labels_dict.get(chunk_id)
    old_type = chunk.get("inferred-type", "none")

    if label:
        # Dictionary neu aufbauen, um true_type nach inferred-type zu platzieren
        ordered_chunk = {}
        inserted = False
        for key, value in chunk.items():
            ordered_chunk[key] = value
            if key == "inferred-type":
                ordered_chunk["true_type"] = label
                inserted = True

        # Falls inferred-type nicht existiert, am Ende anfügen
        if not inserted:
            ordered_chunk["true_type"] = label

        # Das Original-Chunk-Objekt in der Liste modifizieren
        chunk.clear()
        chunk.update(ordered_chunk)
        status = "OK"
    else:
        status = "MISSING"
        label = "n/a"

    # Daten für den Kontroll-Report sammeln
    report_data.append({
        "ID": chunk_id,
        "File": filename,
        "Old Type": old_type,
        "True Type": label,
        "Status": status
    })

    return 1 if label != "n/a" else 0

def write_report(data):
    """Schreibt eine TSV-Datei zur manuellen Kontrolle."""
    report_path = REPORT_DIR / "verification_report.tsv"
    keys = ["ID", "File", "Old Type", "True Type", "Status"]

    with open(report_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, delimiter="\t")
        writer.writeheader()
        writer.writerows(data)

if __name__ == "__main__":
    merge_labels()
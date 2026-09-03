import os
import json
import random
import shutil
from pathlib import Path
from collections import defaultdict

# Pfad-Definitionen
BASE_DIR = Path(__file__).parent.parent
EXTERNAL_SOURCE_DIR = Path("/home/spielberg/code/repos/dimeclass/Heftromane/json_inferred_type")
SOURCE_DIR = BASE_DIR / "source_json"
CHUNKS_DIR = BASE_DIR / "chunks_for_goldstandard"

# KONFIGURATION: Ab wie vielen Chunks innerhalb eines Buches soll aufgeteilt werden?
MAX_CHUNKS_PER_BOOK_FILE = 20

def setup_folders(clear_old=False):
    """Erstellt die Ordner oder bereinigt sie."""
    if not SOURCE_DIR.exists():
        SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    if not CHUNKS_DIR.exists():
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    if clear_old:
        print(f"Bereinige Ordner...")
        for folder in [SOURCE_DIR, CHUNKS_DIR]:
            for file in folder.glob("*"):
                if file.is_file():
                    file.unlink()

def select_random_files(count=3, exclude_filenames=None):
    """
    Wählt Zufallsdateien aus der externen Quelle und schließt bereits vorhandene aus.
    """
    if exclude_filenames is None:
        exclude_filenames = set()

    # Alle verfügbaren Dateien finden, die noch nicht lokal liegen
    all_files = [f for f in EXTERNAL_SOURCE_DIR.rglob("*.json") if f.name not in exclude_filenames]

    if not all_files:
        print("Keine weiteren neuen Dateien in der Quelle gefunden.")
        return []

    selected_files = random.sample(all_files, min(count, len(all_files)))
    local_paths = []
    for file_path in selected_files:
        target_path = SOURCE_DIR / file_path.name
        shutil.copy(file_path, target_path)
        local_paths.append(target_path)

    print(f"Erfolgreich {len(local_paths)} neue Dateien nach {SOURCE_DIR.name} kopiert.")
    return local_paths

def process_books(file_paths):
    """Verarbeitet Dateien und trennt Chunks strikt nach Buch-Index."""
    total_chunks_count = 0
    total_files_created = 0

    for file_path in file_paths:
        filename = file_path.name
        print(f"\n--- Verarbeite Datei: {filename} ---")

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Fehler: {filename} ist kein gültiges JSON.")
                continue

        is_collection = data.get("processing_log", {}).get("is_collection", False)
        content_list = data.get("content", [])

        # Dictionary zum Gruppieren: {book_idx: [chunks]}
        chunks_by_book = defaultdict(list)

        if is_collection:
            sub_book_counter = 1
            global_chunk_counter = 0
            for item in content_list:
                if "content" in item and isinstance(item["content"], list):
                    book_content = item.get("content", [])
                    for chunk_idx, chunk in enumerate(book_content):
                        chunk_data = extract_chunk_info(filename, sub_book_counter, chunk_idx, chunk)
                        if chunk_data:
                            chunks_by_book[sub_book_counter].append(chunk_data)
                    sub_book_counter += 1
                else:
                    chunk_data = extract_chunk_info(filename, 0, global_chunk_counter, item)
                    if chunk_data:
                        chunks_by_book[0].append(chunk_data)
                    global_chunk_counter += 1
        else:
            for chunk_idx, chunk in enumerate(content_list):
                chunk_data = extract_chunk_info(filename, 0, chunk_idx, chunk)
                if chunk_data:
                    chunks_by_book[0].append(chunk_data)

        # Jetzt für jedes Buch separate Dateien schreiben
        for b_idx in sorted(chunks_by_book.keys()):
            book_chunks = chunks_by_book[b_idx]
            num_b_chunks = len(book_chunks)
            total_chunks_count += num_b_chunks

            print(f"  > Buch-Index {b_idx}: {num_b_chunks} Chunks gesamt.")

            if num_b_chunks <= MAX_CHUNKS_PER_BOOK_FILE:
                save_name = filename.replace(".json", f"_book{b_idx}.json")
                save_chunk_file(book_chunks, save_name)
                print(f"    [Datei erstellt] text_{save_name} ({num_b_chunks} Chunks)")
                total_files_created += 1
            else:
                # Splitting in Parts
                for i in range(0, num_b_chunks, MAX_CHUNKS_PER_BOOK_FILE):
                    batch = book_chunks[i : i + MAX_CHUNKS_PER_BOOK_FILE]
                    part_num = (i // MAX_CHUNKS_PER_BOOK_FILE) + 1
                    save_name = filename.replace(".json", f"_book{b_idx}_part{part_num}.json")
                    save_chunk_file(batch, save_name)
                    print(f"    [Datei erstellt] text_{save_name} ({len(batch)} Chunks)")
                    total_files_created += 1

    print(f"\n" + "="*50)
    print(f"ABSCHLUSS-BERICHT:")
    print(f"Insgesamt verarbeitete Chunks: {total_chunks_count}")
    print(f"Insgesamt erstellte JSON-Dateien: {total_files_created}")
    print(f"Speicherort: {CHUNKS_DIR}")
    print("="*50)

def save_chunk_file(chunks, save_filename):
    """Speichert die Chunks."""
    output_path = CHUNKS_DIR / f"text_{save_filename}"
    with open(output_path, 'w', encoding='utf-8') as out_f:
        json.dump(chunks, out_f, indent=4, ensure_ascii=False)

def extract_chunk_info(filename, book_idx, chunk_idx, chunk):
    """Extrahiert ID und Text."""
    href = chunk.get("href", "unknown_href")
    href_clean = os.path.basename(href)
    chunk_id = f"{filename}_{book_idx}_{chunk_idx}_{href_clean}"
    text_content = chunk.get("text", "")
    if not text_content and (not href or href == "unknown_href"):
        return None
    return {"id": chunk_id, "text": text_content}

if __name__ == "__main__":
    setup_folders(clear_old=False)
    existing_files = list(SOURCE_DIR.glob("*.json"))

    if existing_files:
        print(f"\nVorhandene Dateien in '{SOURCE_DIR.name}' gefunden: {len(existing_files)}")
        print("Wähle einen Modus:")
        print("[v] Vorhandene Dateien verarbeiten (Chunks neu erstellen)")
        print("[h] Hinzufügen von neuen Zufallsdateien (bestehende bleiben)")
        print("[r] Refresh (Ordner leeren und komplett neue Zufallsdateien)")

        choice = input("Deine Wahl (v/h/r): ").lower()

        if choice == 'v':
            process_books(existing_files)
        elif choice == 'h':
            try:
                count_str = input("Wie viele neue Romane sollen zusätzlich hinzugefügt werden? (Standard: 3): ")
                count = int(count_str) if count_str.strip() else 3
            except ValueError:
                count = 3

            existing_names = {f.name for f in existing_files}
            new_files = select_random_files(count, exclude_filenames=existing_names)
            if new_files:
                process_books(new_files)
        elif choice == 'r':
            setup_folders(clear_old=True)
            process_books(select_random_files(3))
        else:
            print("Ungültige Eingabe. Beende.")
    else:
        # Ordner leer: Standard-Ablauf
        process_books(select_random_files(3))
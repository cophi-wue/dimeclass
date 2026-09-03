import os
import json
import random
import shutil
import sys
import re
from pathlib import Path

# Pfad-Definitionen
EXTERNAL_SOURCE_DIR = Path("/home/spielberg/code/repos/dimeclass/Heftromane/json_inferred_type")
#BASE_DIR = Path("/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation")
BASE_DIR = Path("/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation/new_testdata")
SOURCE_DIR = BASE_DIR / "source_json"
CHUNKS_DIR = BASE_DIR / "chunks_for_labeling"

# ZIEL-KONFIGURATION
TARGET_TOTAL_CHUNKS = 200  # Gesamtzahl der Chunks am Ende
TARGET_TOTAL_BOOKS = 25    # Mindestanzahl an Quellbüchern
CHUNKS_PER_OUTPUT_FILE = 20

def setup_folders():
    """Erstellt die notwendigen Ordner falls nicht vorhanden."""
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

def get_existing_data():
    """Scannt vorhandene Chunk-Dateien nach IDs und Part-Nummern."""
    existing_ids = set()
    max_part = 0

    chunk_files = list(CHUNKS_DIR.glob("gold_chunks_part_*.json"))
    for f in chunk_files:
        match = re.search(r"part_(\d+)\.json", f.name)
        if match:
            max_part = max(max_part, int(match.group(1)))

        try:
            with open(f, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                for item in data:
                    existing_ids.add(item.get("id"))
        except:
            continue

    return existing_ids, max_part + 1

def ensure_source_books():
    """Stellt sicher, dass genügend Quellbücher vorhanden sind mit Interaktion."""
    while True:
        existing_local = list(SOURCE_DIR.glob("*.json"))
        needed = TARGET_TOTAL_BOOKS - len(existing_local)

        if needed <= 0:
            print(f"\nQuellordner bereits gut gefüllt: {len(existing_local)} Bücher vorhanden.")
            return existing_local

        print(f"\nStatus Quellordner: {len(existing_local)} Bücher.")
        print(f"Suche {needed} weitere Bücher in der externen Quelle...")

        exclude_names = {f.name for f in existing_local}
        all_remote = [f for f in EXTERNAL_SOURCE_DIR.rglob("*.json") if f.name not in exclude_names]

        if not all_remote:
            print("Keine weiteren neuen Bücher in der Quelle gefunden.")
            return existing_local

        selected = random.sample(all_remote, min(needed, len(all_remote)))

        print("\n--- VORSCHLAG: NEUE BÜCHER ---")
        for f in selected:
            print(f"  -> {f.name}")

        choice = input(f"\nDiese {len(selected)} Bücher kopieren? (j = Ja / n = Neue Auswahl / w = Weiter mit Vorhandenen / a = Abbrechen): ").lower()

        if choice == 'j':
            for f in selected:
                shutil.copy(f, SOURCE_DIR / f.name)
            return list(SOURCE_DIR.glob("*.json"))
        elif choice == 'n':
            print("Suche andere Bücher aus...")
            continue
        elif choice == 'w':
            print("Verarbeite nur die bereits vorhandenen Bücher.")
            return existing_local
        elif choice == 'a':
            print("Vorgang durch Nutzer abgebrochen.")
            sys.exit()
        else:
            print("Ungültige Eingabe.")

def extract_all_potential_chunks(file_paths, blacklist_ids):
    """Extrahiert alle Chunks, die noch nicht im Goldstandard sind."""
    non_chapter_chunks = []
    chapter_chunks = []

    for file_path in file_paths:
        filename = file_path.name
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except:
                continue

        content = data.get("content", [])
        is_coll = data.get("processing_log", {}).get("is_collection", False)

        if is_coll:
            for b_idx, book in enumerate(content, 1):
                sub = book.get("content", [])
                if isinstance(sub, list):
                    for c_idx, chunk in enumerate(sub):
                        _process(chunk, filename, b_idx, c_idx, blacklist_ids, non_chapter_chunks, chapter_chunks)
        else:
            for c_idx, chunk in enumerate(content):
                _process(chunk, filename, 0, c_idx, blacklist_ids, non_chapter_chunks, chapter_chunks)

    return non_chapter_chunks, chapter_chunks

def _process(chunk, fname, b_idx, c_idx, blacklist, non_list, chap_list):
    cid = f"{fname}_{b_idx}_{c_idx}"
    if cid in blacklist:
        return

    ctype = chunk.get("inferred-type", "unknown")
    cdata = {"id": cid, "text": chunk.get("text", ""), "inferred-type": ctype}

    if ctype not in ["chapter", "novel"]:
        non_list.append(cdata)
    else:
        chap_list.append(cdata)

def save_batches(chunks, start_part):
    """Speichert Chunks in neuen Files."""
    if not chunks:
        print("Keine neuen Chunks zum Speichern gefunden.")
        return

    random.shuffle(chunks)
    for i in range(0, len(chunks), CHUNKS_PER_OUTPUT_FILE):
        batch = chunks[i : i + CHUNKS_PER_OUTPUT_FILE]
        p_num = start_part + (i // CHUNKS_PER_OUTPUT_FILE)
        out_name = f"gold_chunks_part_{p_num:02d}.json"

        clean = [{"id": c["id"], "text": c["text"]} for c in batch]
        with open(CHUNKS_DIR / out_name, 'w', encoding='utf-8') as f:
            json.dump(clean, f, indent=4, ensure_ascii=False)
        print(f"Erstellt: {out_name} ({len(clean)} Chunks)")

if __name__ == "__main__":
    setup_folders()

    # 1. Status Quo prüfen
    existing_ids, next_part = get_existing_data()
    needed_chunks = TARGET_TOTAL_CHUNKS - len(existing_ids)

    print(f"Status: {len(existing_ids)} Chunks bereits gelabelt/vorhanden.")

    if needed_chunks <= 0:
        print(f"Ziel von {TARGET_TOTAL_CHUNKS} bereits erreicht oder überschritten.")
        sys.exit()

    print(f"Ziel: {needed_chunks} weitere Chunks generieren.")

    # 2. Bücher sicherstellen (Interaktiv)
    all_books = ensure_source_books()

    # 3. Neue Chunks suchen
    print(f"\nAnalysiere Chunks in {len(all_books)} Büchern...")
    non_chaps, chaps = extract_all_potential_chunks(all_books, existing_ids)

    total_available = len(non_chaps) + len(chaps)
    print(f"Verfügbar (noch nicht gelabelt): {len(non_chaps)} Non-Chapters, {len(chaps)} Chapters.")

    if total_available < needed_chunks:
        print(f"Warnung: Nur {total_available} neue Chunks gefunden, brauche aber {needed_chunks}.")
        print("Vielleicht mehr Bücher hinzufügen?")
        if input("Trotzdem fortfahren mit dem was da ist? (j/n): ").lower() != 'j':
            sys.exit()

    # 4. Auswahl treffen
    selection = []
    if len(non_chaps) >= needed_chunks:
        selection = random.sample(non_chaps, needed_chunks)
    else:
        selection = non_chaps
        remaining = needed_chunks - len(non_chaps)
        selection.extend(random.sample(chaps, min(remaining, len(chaps))))

    # 5. Speichern
    save_batches(selection, next_part)
    print("\nFertig!")
import os
import sys

# --- PFAD-SETUP ---
current_script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_script_dir)
chunking_dir = os.path.join(parent_dir, 'chunking')

if chunking_dir not in sys.path:
    sys.path.append(chunking_dir)

# --- KONFIGURATION ---
BASE_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/ebooks_jsons_for_token_analysis" # Ordner mit JSON-Dateien
OUTPUT_LOGS = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/pipeline-llm/pipeline-outputs" # Ordner für Ausgaben
REFERENCE_FILE = os.path.join(OUTPUT_LOGS, "chunk_index_reference.txt") # Outputdatei dieses Skripts

try:
    from chunking_chapters import DataLoader
except ImportError:
    print(f"Fehler: chunking_chapters.py nicht gefunden.")
    sys.exit(1)

def main():
    print("--- Lade Chunks zur Analyse ---")
    loader = DataLoader(BASE_PATH, OUTPUT_LOGS)
    work_units = loader.load_and_chunk()

    total = len(work_units)
    if total == 0:
        print("Keine Chunks gefunden.")
        return

    output_lines = []
    output_lines.append(f"--- CHUNK INDEX REFERENZ ---")
    output_lines.append(f"Erstellt am: {os.uname().nodename if hasattr(os, 'uname') else 'System'}")
    output_lines.append(f"Gesamtanzahl Chunks: {total}\n")

    current_file = ""
    file_start_index = 0

    header = f"{'Index':<7} | {'Chunk ID':<65} | {'Strategy'}"
    separator = "-" * 90
    output_lines.append(header)
    output_lines.append(separator)

    for i, unit in enumerate(work_units):
        chunk_id = unit['id']
        strategy = unit.get('strategy', 'unknown')

        # Extrahiere Dateiname aus der Chunk ID (Basis für Gruppierung)
        file_part = "_".join(chunk_id.split("_")[:-1])

        if file_part != current_file:
            if current_file != "":
                output_lines.append(f"\n--- Ende von: {current_file} (Index {file_start_index} bis {i-1}) ---\n")

            current_file = file_part
            file_start_index = i
            output_lines.append(f"\n>>> DATEI: {current_file} (Startet bei Index {i})")
            output_lines.append(separator)

        output_lines.append(f"{i:<7} | {chunk_id:<65} | {strategy}")

    if total > 0:
        output_lines.append(f"\n--- Ende von: {current_file} (Index {file_start_index} bis {total-1}) ---\n")

    # Finaler Output in Datei schreiben
    try:
        with open(REFERENCE_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        print(f"Erfolg! Die Referenzliste wurde erstellt unter:\n{REFERENCE_FILE}")
    except Exception as e:
        print(f"Fehler beim Schreiben der Datei: {e}")

if __name__ == "__main__":
    main()
import json
import re
import os
import argparse
import logging
from typing import List, Dict, Any, Tuple, Set

# Matches the entire <p> element containing the stars
STAR_SEPARATOR_PATTERN = r'<p[^>]*>\s*(?:\*\s*)+\s*</p>'

# Matches <p> Elemente, die ein <graphic> Tag mit einer .jpg URL enthalten.
# Berücksichtigt auch Verschachtelung <p><p>...</p></p>.
JPG_SEPARATOR_PATTERN = r'<p[^>]*>(?:<p[^>]*>)?\s*<graphic[^>]*url="[^"]+\.jpg"[^>]*/>\s*(?:\s*</p>){1,2}'

class DataLoader:
    def __init__(self, output_folder: str):
        self.output_folder = output_folder

    def load_and_chunk(self, files_to_process: List[str]) -> List[Dict[str, Any]]:
        """
        Hauptfunktion zum Laden und Zerlegen von Dateien in Work Units.
        example of a work unit:
        {
        "id": "000449_John_Sinclair_-_Folge_0008_-_Jason_Dark_01",
        "source_file": "000449_John_Sinclair_-_Folge_0008_-_Jason_Dark.json",
        "html": "<p>\n<p><p><p><graphic url=\"imgs/9783838727622_front.jpg\" rend=\"img\" mimeType=\"image/jpeg\"/></p></p></p>\n</p>",
        "inferred_type": "cover",
        "strategy": "non-chapter",
        "status": "pending" # atm there is jsut pending, other statuses can be added later if needed
        }
        """
        all_work_units = []
        logging.info(f"Processing {len(files_to_process)} files.")

        for filepath in files_to_process:
            filename = os.path.basename(filepath)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Extrahiere Chunks und sammle genutzte Strategien
                file_units, strategies_used = self._process_single_file(filename, data)
                all_work_units.extend(file_units)

                # HPC-Stats pro Buch schreiben
                self._save_stats(filename, len(file_units), list(strategies_used))
                logging.info(f"DONE: {filename} | Chunks: {len(file_units)} | Strategies: {','.join(strategies_used)}")

            except Exception as e:
                # Das 'exc_info=True' sorgt dafür, dass der gesamte Traceback (Fehlerstelle) im Log landet
                logging.error(f"FAILED: {filename} | Error: {str(e)}", exc_info=True)

        # Save the report
        return all_work_units

    def _process_single_file(self, filename: str, data: dict) -> Tuple[List[Dict[str, Any]], Set[str]]:
        """
        Flattens the entire book structure (front matter, chapters, back matter)
        and applies the specific splitting logic based on 'inferred-type'.
        """
        book_id = filename.replace(".json", "")

        # 1. Flatten the JSON tree into a linear list of text nodes
        # This ensures we get ALL content (front, back, chapters, volumes)
        raw_nodes = []
        self._flatten_book_content(data, book_id, raw_nodes)

        final_chunks = []
        strategies_used = set()

        # 2. Process each node
        for node in raw_nodes:
            processed = self._apply_chunking_rules(node, filename)
            for chunk in processed:
                strategies_used.add(chunk["strategy"])
                final_chunks.append(chunk)

        return final_chunks, strategies_used

    def _flatten_book_content(self, data: Any, current_id: str, collector: List[Dict]):
        """
        Recursively traverses the JSON to find ANY dict with a 'text' field.
        Collects metadata like 'inferred-type'.
        """
        if isinstance(data, dict):
            # A) Does this node have text content?
            if "text" in data and isinstance(data["text"], str) and data["text"].strip():
                # Capture the content node with its metadata.
                collector.append({
                    "base_id": current_id,
                    "text": data["text"],
                    "inferred_type": data.get("inferred-type", None) # Capture type for logic later
                })

            # B) Recurse into children (usually 'content')
            # Check 'content' key, but also iterate all values just in case structure varies
            # (Prioritize 'content' to keep IDs logical if possible, but recursive is safer)
            if "content" in data:
                self._flatten_book_content(data["content"], current_id, collector)
            else:
                # If no 'content' key, strictly check if we need to recurse other keys?
                pass

        elif isinstance(data, list):
            # Iterate through the list (e.g., volumes, chapters, sections)
            for i, item in enumerate(data):
                # Generate a sequential ID suffix for this list item
                # e.g., book_01, book_02.
                # If current_id is "book", next is "book_01".
                # If current_id is "book_01" (vol), next is "book_01_01" (chap).
                next_id = f"{current_id}_{i+1:02d}"
                self._flatten_book_content(item, next_id, collector)

    def _apply_chunking_rules(self, node: Dict, filename: str) -> List[Dict[str, Any]]:
        """
        Decides whether to split the text node based on its type and content.

        Rule 1: If it is a chapter, keep it whole (explicit_chapter).
        Rule 2: If it is a novel split up by stars (implicit_chapter_stars).
        Rule 3: If it is a novel split up by JPG images (implicit_chapter_jpg).
        Rule 4: Otherwise, keep it whole (non-chapter).
        RUle 5: If novel without any separators then novel_no_separator (to log if such an edge case occurs)
        """
        text = node["text"]
        inf_type = node["inferred_type"]
        base_id = node["base_id"]

        chunks = []

        # Check if this node is explicitly a chapter
        is_explicit_chapter = (inf_type and "chapter" in inf_type.lower())

        # STRATEGY A: It is a Chapter -> Keep Whole
        if is_explicit_chapter:
            chunks.append({
                "id": base_id, # Keep the hierarchical ID
                "source_file": filename,
                "html": text,
                "inferred_type": inf_type,
                "strategy": "explicit_chapter",
                "status": "pending"
            })

        # STRATEGY B: Check for Implicit Splits (Stars)
        elif inf_type == "novel":

            if re.search(STAR_SEPARATOR_PATTERN, text):
                parts = re.split(STAR_SEPARATOR_PATTERN, text)
                parts = [p for p in parts if p.strip()]
                for i, part in enumerate(parts):
                    part_id = f"{base_id}_part{i+1:02d}"
                    chunks.append({
                        "id": part_id,
                        "source_file": filename,
                        "html": part,
                        "inferred_type": inf_type,
                        "strategy": "implicit_chapter_stars",
                        "status": "pending"
                    })

            # STRATEGY C: Check auf JPGs
            elif re.search(JPG_SEPARATOR_PATTERN, text):
                parts = re.split(JPG_SEPARATOR_PATTERN, text)
                parts = [p for p in parts if p.strip()]
                for i, part in enumerate(parts):
                    part_id = f"{base_id}_part{i+1:02d}"
                    chunks.append({
                        "id": part_id,
                        "source_file": filename,
                        "html": part,
                        "inferred_type": inf_type,
                        "strategy": "implicit_chapter_jpg",
                        "status": "pending"
                    })

            else:
                # 'novel' Block ohne Trenner
                chunks.append({
                    "id": base_id,
                    "source_file": filename,
                    "html": text,
                    "inferred_type": inf_type,
                    "strategy": "novel_no_separator",
                    "status": "pending"
                })
        else:
            # everything esle: front matter, back matter, "unkown"
            chunks.append({
                "id": base_id,
                "source_file": filename,
                "html": text,
                "inferred_type": inf_type,
                "strategy": "non-chapter",
                "status": "pending"
            })

        return chunks

    def _save_stats(self, filename: str, count: int, strategies: list):
        """Schreibt eine individuelle Statistik-Datei für HPC-Zwecke."""
        stats_path = os.path.join(self.output_folder, f"{filename}.stats")
        with open(stats_path, "w", encoding="utf-8") as f:
            # Format: Dateiname | Anzahl Chunks | Verwendete Strategien
            f.write(f"{filename}\t{count}\t{','.join(strategies)}\n")

if __name__ == "__main__":
    # Setup
    parser = argparse.ArgumentParser(description="HPC-optimiertes Chunking Script")
    parser.add_argument("-i", "--input", help="JSON-Datei oder Ordner", type=str)
    parser.add_argument("-d", "--data_dir", help="Verzeichnis, in dem die JSONs liegen (falls --input nur Dateiname ist)", type=str)
    parser.add_argument("-o", "--output", help="Output-Ordner für Reports/Stats", type=str)
    args = parser.parse_args()

    # Lokale Fallback-Logik (deine Pfade vom Laptop)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)

    # Pfad-Logik für Input
    if args.input:
        input_path = args.input.strip()
        # Falls es nur ein Dateiname ist und nicht existiert, versuche es im data_dir
        if not os.path.isabs(input_path) and not os.path.exists(input_path) and args.data_dir:
            input_path = os.path.join(args.data_dir.strip(), input_path)
        base_path = os.path.abspath(input_path)
    else:
        # Dein Standard-Pfad auf dem Laptop
        base_path = os.path.abspath(os.path.join(parent_dir, "token_analysis", "ebooks_jsons_for_token_analysis"))

    # Pfad-Logik für Output
    output_path = os.path.abspath(args.output.strip()) if args.output else \
        os.path.join(script_dir, "chunking_reports")
    os.makedirs(output_path, exist_ok=True)

    # 3. Sammle Dateien ein
    files_to_process = []
    if os.path.isfile(base_path):
        files_to_process.append(base_path)
    elif os.path.isdir(base_path):
        # Falls ein Ordner übergeben wurde (Lokaler Modus)
        files_to_process = [os.path.join(base_path, f) for f in os.listdir(base_path) if f.endswith('.json')]

    # Logging konfigurieren
    if len(files_to_process) == 1:
        log_name = f"{os.path.basename(files_to_process[0])}.log"
    else:
        log_name = "process.log"

    log_file = os.path.join(output_path, log_name)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    if not files_to_process:
        logging.warning(f"Keine Dateien gefunden unter: {base_path}")
        exit(0)

    # 4. Ausführung
    loader = DataLoader(output_path)
    work_units = loader.load_and_chunk(files_to_process)

    logging.info(f"Gesamtanzahl Work Units: {len(work_units)}")


'''
Auf dem Server (HPC / Job-Array Modus):**
Hier wird das Skript über die Datei `todo.txt` gesteuert. In deinem Bash-Skript änderst du den Aufruf auf:
```bash
# In deinem Slurm-Script
srun python chunking_chapters.py --input "$INPUT_FILE" --output "./hpc_reports"
Da `$INPUT_FILE` nun ein direkter Pfad zu einer einzelnen JSON ist, wird das Skript nur diese eine Datei verarbeiten, was ideal für das Parallel Processing ist.

Du kannst nach Abschluss aller Jobs einfach diesen Befehl nutzen, um den finalen Report zu bauen:
cat chunking_reports/*.stats > final_report.tsv

.'''
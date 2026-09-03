import json
import re
import os
import uuid
from typing import List, Dict, Any


#  Matches the entire <p> element containing the stars
# # <p[^>]*> -> Finds the opening <p> tag (and any attributes like rend="separator")
# # \s* -> Ignores whitespace inside the tag
# # (?:\*\s*)+ -> Finds the stars
# # </p> -> Finds the closing </p> tag
STAR_SEPARATOR_PATTERN = r'<p[^>]*>\s*(?:\*\s*)+\s*</p>'

# Matches <p> Elemente, die ein <graphic> Tag mit einer .jpg URL enthalten.
# Berücksichtigt auch Verschachtelung <p><p>...</p></p>.
JPG_SEPARATOR_PATTERN = r'<p[^>]*>(?:<p[^>]*>)?\s*<graphic[^>]*url="[^"]+\.jpg"[^>]*/>\s*(?:\s*</p>){1,2}'

class DataLoader:
    def __init__(self, input_folder: str, output_folder: str):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.report_data = [] # To store the summary for the report

    def load_and_chunk(self) -> List[Dict[str, Any]]:
        """
        Main function to load all JSONs and convert them into Work Units (list of dicts).
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

        # Get all json files
        files = [f for f in os.listdir(self.input_folder) if f.endswith('.json')]

        print(f"Found {len(files)} JSON files to process.")

        for filename in files:
            filepath = os.path.join(self.input_folder, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Extract chunks from this specific file
                file_units = self._process_single_file(filename, data)
                all_work_units.extend(file_units)

            except Exception as e:
                print(f"ERROR reading {filename}: {e}")

        # Save the report
        self._save_report()
        return all_work_units

    def _process_single_file(self, filename: str, data: dict) -> List[Dict[str, Any]]:
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

        # 2. Process each node
        for node in raw_nodes:
            processed = self._apply_chunking_rules(node, filename)
            final_chunks.extend(processed)

        # Log for report
        self.report_data.append({
            "file": filename,
            "total_chunks": len(final_chunks),
            "primary_strategy": "entire_book_structure"
        })

        return final_chunks

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
        is_explicit_chapter = False
        if inf_type and "chapter" in inf_type.lower():
            is_explicit_chapter = True

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

    def _save_report(self):
        """
        Saves a TSV report
        """
        report_path = os.path.join(self.output_folder, "chunking_report.tsv")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("filename\tprimary_strategy\ttotal_chunks\n")
            for item in self.report_data:
                f.write(f"{item['file']}\t{item['primary_strategy']}\t{item['total_chunks']}\n")
        print(f"Report saved to {report_path}")

# --- USAGE EXAMPLE ---
if __name__ == "__main__":

    # PATHS
    script_dir = os.path.dirname(os.path.abspath(__file__)) # Verzeichnis dieses Skripts (.../python/chunking)
    parent_dir = os.path.dirname(script_dir)               # Eine Ebene höher (.../python)

    base_path = os.path.abspath(os.path.join(parent_dir, "token_analysis", "ebooks_jsons_for_token_analysis"))
    #base_path ="/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/ebooks_jsons_for_token_analysis" # folder with JSON

    output_path = os.path.join(script_dir, "chunking_reports")
    #output_path = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/chunking/chunking_reports" # folder for output logs

    os.makedirs(output_path, exist_ok=True)

    loader = DataLoader(base_path, output_path)
    work_units = loader.load_and_chunk()

    print(f"\nGenerated {len(work_units)} work units.")

    # INSPECTION: Print the first chunk in full detail
    if work_units:
        print("\n--- INSPECTION: FIRST CHUNK ---")
        # Ensure we don't print massive HTML in the console, just a snippet
        sample = work_units[0].copy()
        if len(sample["html"]) > 200:
            sample["html"] = sample["html"][:200] + "... [TRUNCATED]"
        print(json.dumps(sample, indent=4))
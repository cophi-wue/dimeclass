import json
import os
from collections import Counter
from typing import Any, Dict, List

from chunking_chapters import DataLoader, STAR_SEPARATOR_PATTERN, JPG_SEPARATOR_PATTERN


STRATEGIES = (
    "explicit_chapter",
    "implicit_chapter_stars",
    "implicit_chapter_jpg",
    "novel_no_separator",
    "non-chapter",
)


class InferredTypeDataLoader(DataLoader):
    """Run the existing chunking rules over nested inferred-type JSON files."""

    def __init__(self, input_folder: str, output_folder: str):
        super().__init__(input_folder, output_folder)
        self.report_data: List[Dict[str, Any]] = []
        self.aggregate_counts = Counter({strategy: 0 for strategy in STRATEGIES})

    def load_and_chunk(self) -> List[Dict[str, Any]]:
        all_work_units: List[Dict[str, Any]] = []
        files = self._find_json_files()

        print(f"Found {len(files)} JSON files to process.")

        for filepath in files:
            filename = os.path.basename(filepath)
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    data = json.load(file)

                file_units = self._process_single_file(filename, data)
                all_work_units.extend(file_units)
            except Exception as error:
                print(f"ERROR reading {filepath}: {error}")

        self._save_outputs(all_work_units)
        return all_work_units

    def _find_json_files(self) -> List[str]:
        json_files = []
        for root, _, filenames in os.walk(self.input_folder):
            for filename in filenames:
                if filename.endswith(".json"):
                    json_files.append(os.path.join(root, filename))
        return sorted(json_files)

    def _process_single_file(self, filename: str, data: dict) -> List[Dict[str, Any]]:
        book_id = filename.replace(".json", "")
        raw_nodes: List[Dict[str, Any]] = []
        self._flatten_book_content(data, book_id, raw_nodes)

        final_chunks: List[Dict[str, Any]] = []
        for node in raw_nodes:
            final_chunks.extend(self._apply_chunking_rules(node, filename))

        counts = Counter(chunk["strategy"] for chunk in final_chunks)
        self.aggregate_counts.update(counts)
        self.report_data.append({
            "filename": filename,
            **{strategy: counts.get(strategy, 0) for strategy in STRATEGIES},
            "total_chunks": len(final_chunks),
        })
        return final_chunks

    def _save_outputs(self, work_units: List[Dict[str, Any]]) -> None:
        report_path = os.path.join(self.output_folder, "chunking_report.tsv")
        with open(report_path, "w", encoding="utf-8") as file:
            file.write("filename\t" + "\t".join(STRATEGIES) + "\ttotal_chunks\n")
            for item in self.report_data:
                file.write(
                    item["filename"]
                    + "\t"
                    + "\t".join(str(item[strategy]) for strategy in STRATEGIES)
                    + f"\t{item['total_chunks']}\n"
                )

        aggregate_report_path = os.path.join(
            self.output_folder, "chunking_report_aggregate.tsv"
        )
        with open(aggregate_report_path, "w", encoding="utf-8") as file:
            file.write("strategy\tchunk_count\n")
            for strategy in STRATEGIES:
                file.write(f"{strategy}\t{self.aggregate_counts[strategy]}\n")
            file.write(f"total\t{sum(self.aggregate_counts.values())}\n")

        work_units_path = os.path.join(self.output_folder, "work_units.json")
        with open(work_units_path, "w", encoding="utf-8") as file:
            json.dump(work_units, file, ensure_ascii=False, indent=2)

        print(f"Per-file report saved to {report_path}")
        print(f"Aggregate report saved to {aggregate_report_path}")
        print(f"Work units saved to {work_units_path}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # New run: one JSON file is nested inside each book folder.
    input_path = "/home/spielberg/code/repos/dimeclass/Heftromane/json_inferred_type"
    output_path = os.path.join(script_dir, "chunking_reports_json_inferred_type")

    # Old paths retained for reference; the original script is unchanged.
    # parent_dir = os.path.dirname(script_dir)
    # input_path = os.path.abspath(os.path.join(
    #     parent_dir, "token_analysis", "ebooks_jsons_for_token_analysis"
    # ))
    # output_path = os.path.join(script_dir, "chunking_reports")

    os.makedirs(output_path, exist_ok=True)

    loader = InferredTypeDataLoader(input_path, output_path)
    work_units = loader.load_and_chunk()
    print(f"Generated {len(work_units)} work units.")

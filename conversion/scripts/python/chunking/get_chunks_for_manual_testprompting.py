from chunking_chapters import DataLoader
# from chunking_chapters_stars_atend import DataLoader
import random
import os

# CONFIG
BASE_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/ebooks_jsons_for_token_analysis"
OUTPUT_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/chunking/chunking_reports"
SAMPLE_FILE = os.path.join(OUTPUT_PATH, "prompt_testing_samples.txt")


def get_samples():
    print("Loading chunks...")
    loader = DataLoader(BASE_PATH, OUTPUT_PATH)
    units = loader.load_and_chunk()

    samples = {}

    # 1. Find a Front Matter or weird type (Not chapter, not None)
    front_matter = [u for u in units if u['inferred_type'] and 'chapter' not in u['inferred_type'].lower()]
    if front_matter:
        samples['Front Matter'] = random.choice(front_matter)

    # 2. Find an Explicit Chapter
    chapters = [u for u in units if u['strategy'] == 'explicit_chapter']
    if chapters:
        samples['Explicit Chapter'] = random.choice(chapters)

    # 3. Find an Implicit Star Part (The logic where stars were removed)
    star_parts = [u for u in units if u['strategy'] == 'implicit_stars_split']
    if star_parts:
        samples['Star Split Part'] = random.choice(star_parts)

    # 4. Find an Implicit JPG Part
    jpg_parts = [u for u in units if u['strategy'] == 'implicit_chapter_jpg']
    if jpg_parts:
        samples['JPG Split Part'] = random.choice(jpg_parts)

    # Output to file
    print(f"Writing to: {SAMPLE_FILE}") # Added print for verification

    with open(SAMPLE_FILE, "w", encoding="utf-8") as f:
        f.write("=== PROMPT TESTING SAMPLES ===\n\n")

        for category, unit in samples.items():
            f.write(f"--- CATEGORY: {category} ---\n")
            f.write(f"ID: {unit['id']}\n")
            f.write(f"Inferred Type: {unit['inferred_type']}\n")
            f.write(f"Strategy: {unit['strategy']}\n")
            f.write("--- HTML INPUT START ---\n")
            f.write(unit['html'])
            f.write("\n--- HTML INPUT END ---\n\n" + "="*50 + "\n\n")

    print(f"Samples saved to {SAMPLE_FILE}.")

if __name__ == "__main__":
    get_samples()
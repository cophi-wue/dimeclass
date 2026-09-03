import os
import sys
import csv
import time
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate


# --- PFAD-SETUP ---
current_script_dir = os.path.dirname(os.path.abspath(__file__)) # .../pipeline-llm
parent_dir = os.path.dirname(current_script_dir)               # .../python
chunking_dir = os.path.join(parent_dir, 'chunking')            # .../python/chunking

if chunking_dir not in sys.path:
    sys.path.append(chunking_dir)

# --- KONFIGURATION LADEN ---
env_path = os.path.join(chunking_dir, '.env')
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("OPEN_ROUTER_API_KEY")
BASE_URL = os.getenv("OPEN_ROUTER_BASE_URL")

try:
    from chunking_chapters import DataLoader
except ImportError:
    try:
        from dimeclass.conversion.scripts.python.chunking.chunking_chapters import DataLoader
    except ImportError:
        print(f"CRITICAL ERROR: Could not find 'chunking_chapters.py' in {chunking_dir}")
        sys.exit(1)



# --- PATHS ---
#BASE_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/ebooks_jsons_for_token_analysis" # die jsons aus denen wir chunks herstlellen wollen. im Moment eine kleine Auswahl an Dime Novels für Tests, ob die Pipeline funktioniert
BASE_PATH = os.path.abspath(os.path.join(parent_dir, "token_analysis", "ebooks_jsons_for_token_analysis")) #looks inside token_analysis relative to the script's parent folder.

#OUTPUT_LOGS = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/pipeline-llm/pipeline-outputs"
OUTPUT_LOGS = os.path.join(current_script_dir, "pipeline-outputs")

#TEI_OUTPUT_DIR = os.path.join(OUTPUT_LOGS, "tei_chunks")
TEI_OUTPUT_DIR = os.path.join(OUTPUT_LOGS, "tei_chunks")

LOG_FILE = os.path.join(OUTPUT_LOGS, "pipeline_processing_log.csv")


# --- TESTING & FILTER CONFIG ---
TEST_START = 189   #chunk Nummer
TEST_END = 191     # Erhöhe auf eine beliebige Zahl für einen Testlauf
PROCESS_CHAPTERS = True      # Wenn False, werden Kapitel-Chunks ignoriert
PROCESS_NON_CHAPTERS = True  # Wenn False, werden Front/Backmatter ignoriert

# --- Model Settings ---
#devstral is no longer free (27.01.2026)
#MODEL_NAME = "mistralai/devstral-2512:free"
#PROVIDER = "mistralai"
#MODEL_NAME = "qwen/qwen3-next-80b-a3b-instruct:free"

MODEL_NAME = "deepseek/deepseek-r1-0528:free"
PROVIDER = "openai"
SEED = 50


# --- SYSTEM PROMPTS ---
SYSTEM_PROMPT_CHAPTERS = """
##Instruction
You are a converter from HTML to TEI‑XML.
You will receive a HTML snippet that is a chapter from a dime novel.
Return only the TEI content, without additional tags, comments, header, or explanations.
Keep the text content exactly as it is, do not alter it.
Preserve the paragraph structure using <p> tags.
Chapter titles or numbers should be marked with a <head>.
Mark italics as <hi rend="italics"> and bold as <hi rend="bold">.

##Sections
If the HTML input contains sub-divisions indicated by asterisks like '***' or '*' or '**' or images/figures (.jpeg) acting as separators you must structure these parts using `<div type="section" rend="separator">`.
The separators themselves should be removed as they are replaced by the boundary of the `<div>` tags.

##Cleaning Rules
- Remove all 'rend' attributes from the input (e.g., rend="indent", rend="separator").
- Do not add any new attributes unless specified.
- Do not wrap the entire response in an extra <p> or <div>. However, you MUST use `<div type="section">` for the internal divisions as described above.
- Ensure proper nesting of tags.
- If you do not know a corresponding element, keep the original element unchanged and write it as <uncertain>.
"""

SYSTEM_PROMPT_FRONTBACK = """
##Instruction
You are a converter from HTML to TEI‑XML.
You will receive a HTML snippet that is either frontmatter or backmatter of a dime novel.
Convert the HTML snippet into TEI‑XML.
Return only the TEI content, without additional tags, comments, header, or explanations.
Keep the text content exactly as it is, do not alter it.
Preserve the paragraph structure.
Ensure proper nesting of tags.
Remove all 'rend' attributes from the input (e.g., rend="indent", rend="separator").
Do not add any new attributes unless specified.
If you do not know a corresponding element, keep the original element unchanged and write it as <uncertain>.
Nest the snippet inside a <div type="…"> tag chosen from the list of possible types below.

##List of <div type> options

introduction
interlude
prologue
foreword
reading-sample
prelude
epilogue
afterword
cast-list
toc
advertisement
faq
feedback
preview
copyright-statement
dedication
author-information
unknown
"""

def clean_tei_output(content: str) -> str:
    """
    Cleans the raw LLM output by removing any code block formatting.
    """
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```[a-zA-Z]*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
    return content.strip()

def wrap_tei_chunk(content: str, strategy: str) -> str:
    """
    Wraps the raw LLM content in a div based on the strategy.
    [do I need this?] Adds newlines for a clean hierarchy.
    Even though the XML is valid as a single string, having the root tags on separate lines makes it easier to verify the structure at a glance
    """
    raw_content = content

    # Determine the wrapper tag based on strategy
    if strategy == "explicit_chapter":
        opening_tag = '<div type="chapter">'
    elif strategy == "implicit_chapter_stars":
        opening_tag = '<div type="chapter" rend="separator">'
    elif strategy == "implicit_chapter_jpg":
        opening_tag = '<div type="chapter" rend="image-separator">'
    else:
        raise ValueError(f"Wrapper-Fehler: Strategie '{strategy}' ist nicht definiert.")

    # Return the formatted string
    closing_tag = '</div>'
    return f'{opening_tag}\n{raw_content}\n{closing_tag}'

def log_to_csv(chunk_id, status, strategy, wrapped_div, has_uncertain=False, has_unknown_type=False, error_msg=""):
    """
    Logs the  result of each chunk to a CSV file.
     - chunk_id: Identifier of the processed chunk
     - status: "Success", "Error", or "Skipped"
     - strategy: The strategy used for processing (explicit_chapter, implicit_chapter_stars, implicit_chapter_jpg, "front_backmatter", "novel_no_separator")
     - wrapped_div: Indicates if the output was wrapped in a div and which type
     - has_uncertain: Boolean indicating if <uncertain> tags were found in the output
     - has_unknown_type: Boolean indicating if type="unknown" was found in front/backmatter
     - error_msg: Optional error message in case of failure
    """
    file_exists = os.path.exists(LOG_FILE)
    header = ["timestamp", "chunk_id", "status", "strategy", "wrapped_div", "uncertain_found", "unknown_type_found", "error_message"]
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow([
            datetime.now().isoformat(),
            chunk_id,
            status,
            strategy,
            wrapped_div,
            "YES (<uncertain>)" if has_uncertain else "no",
            "YES (<div type='unknown'>)" if has_unknown_type else "no",
            error_msg
        ])

def invoke_llm_with_retry(llm, prompt, max_retries=5):
    """
    Invokes the LLM with a retry mechanism to handle transient errors.
    """
    for attempt in range(max_retries):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            wait_time = 2**attempt
            time.sleep(wait_time)
    return None

def main():
    """
    initialize the LLM, load data, process each chunk according to the specified strategies and filters, log results.
    """
    if not API_KEY:
        print(f"ERROR: API Key nicht gefunden. Pfad geprüft: {env_path}")
        return

    os.makedirs(TEI_OUTPUT_DIR, exist_ok=True)
    print(f"--- Starte TEI Pipeline (Model: {MODEL_NAME}) ---")
    print(f"Filter: Chapters={PROCESS_CHAPTERS}, Non-Chapters={PROCESS_NON_CHAPTERS}")


    try:
        llm = init_chat_model(
            model=MODEL_NAME,
            model_provider=PROVIDER,
            base_url=BASE_URL,
            api_key=API_KEY,
            temperature=0.0,
            seed=SEED
        )
    except Exception as e:
        print(f"Fehler bei der Initialisierung des Models: {e}")
        return

    loader = DataLoader(BASE_PATH, OUTPUT_LOGS)
    work_units = loader.load_and_chunk()

    if TEST_END is not None:
        work_units = work_units[TEST_START:TEST_END]

    print(f"{len(work_units)} Chunks im aktuellen Batch geladen.")

    for i, unit in enumerate(work_units):
        chunk_id = unit['id']
        html_input = unit['html']
        strategy = unit.get('strategy', 'unknown')
        save_path = os.path.join(TEI_OUTPUT_DIR, f"{chunk_id}.xml")

        # 1. Boundary case 'novel_no_separator'
        # Sicherheit: diese Strategie fängt Fälle ab, in denen die Segmentierung (Chunking) im Vorfeld nicht gegriffen hat, zum Beispiel, wenn ein ganzes Buch als ein einziger Block ohne Trennzeichen im JSON steht; soll nicht konvertiert, sondern nur geloggt werden

        if strategy == "novel_no_separator":
            msg = "ACHTUNG novel_no_separator."
            print(f"[{i+1}/{len(work_units)}] {chunk_id}: {msg}")
            # WICHTIG: has_uncertain und has_unknown_type muss hier False sein
            log_to_csv(chunk_id, "Skipped", strategy, "None", False, False, error_msg=msg)
            continue

        # 2. Filter-Logik für Chapters vs Non-Chapters
        is_chapter = strategy in ["explicit_chapter", "implicit_chapter_stars", "implicit_chapter_jpg"]

        if is_chapter and not PROCESS_CHAPTERS:
            print(f"[{i+1}/{len(work_units)}] Skip {chunk_id} (Chapter-Filter aktiv)")
            continue

        if not is_chapter and not PROCESS_NON_CHAPTERS:
            print(f"[{i+1}/{len(work_units)}] Skip {chunk_id} (Non-Chapter-Filter aktiv)")
            continue

        # Überspringen wenn Datei existiert
        if os.path.exists(save_path):
            print(f"[{i+1}/{len(work_units)}] Skip {chunk_id} (Existiert bereits)")
            continue

        print(f"[{i+1}/{len(work_units)}] Verarbeite {chunk_id} ({strategy})...", end=" ", flush=True)

        # Prompt-Auswahl
        if is_chapter:
            system_prompt = SYSTEM_PROMPT_CHAPTERS
            needs_script_wrapping = True
            success_msg = "konvertiert"
        else:
            system_prompt = SYSTEM_PROMPT_FRONTBACK
            needs_script_wrapping = False
            success_msg = "gelabelt und konvertiert"

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "HTML Input:\n{html_content}")
        ])

        try:
            final_prompt = prompt_template.invoke({"html_content": html_input})
            response = invoke_llm_with_retry(llm, final_prompt)

            if response is None:
                raise Exception("Keine Antwort vom LLM.")

            tei_content = clean_tei_output(response.content)

            # Checks für Logging
            has_uncertain = "<uncertain>" in tei_content
            # Check für type="unknown" bei Front/Backmatter
            has_unknown_type = not is_chapter and 'type="unknown"' in tei_content

            if needs_script_wrapping:
                final_output = wrap_tei_chunk(tei_content, strategy)
                wrapped_status = "Script-Wrapped"
            else:
                final_output = tei_content
                wrapped_status = "LLM-Wrapped"

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(final_output)

            # Finales Logging
            status_suffix = ""
            if has_uncertain: status_suffix += "!!! <UNCERTAIN>"
            if has_unknown_type: status_suffix += " !!! [UNKNOWN_TYPE]"

            print(f"Erfolg! ({success_msg}){status_suffix}")
            log_to_csv(chunk_id, "Success", strategy, wrapped_status, has_uncertain, has_unknown_type)
            time.sleep(0.5)

        except Exception as e:
            print(f"Fehler: {e}")
            # Auch im Fehlerfall 8 Spalten füllen
            log_to_csv(chunk_id, "Error", strategy, "None", False, False, str(e))

if __name__ == "__main__":
    main()
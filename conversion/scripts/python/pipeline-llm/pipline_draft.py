import os
import sys
import csv
import time
import re
from dotenv import load_dotenv

# --- PATH SETUP FOR IMPORTS ---
current_script_dir = os.path.dirname(os.path.abspath(__file__)) # .../pipeline-llm
parent_dir = os.path.dirname(current_script_dir)               # .../python
chunking_dir = os.path.join(parent_dir, 'chunking')            # .../python/chunking

if chunking_dir not in sys.path:
    sys.path.append(chunking_dir)

# Now we can import safely
try:
    from dimeclass.conversion.scripts.python.chunking.chunking_chapters import DataLoader
except ImportError:
    print(f"CRITICAL ERROR: Could not find 'chunking_chapters.py' in {chunking_dir}")
    sys.exit(1)

# LangChain Imports
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate

# --- CONFIGURATION ---
env_path = os.path.join(chunking_dir, '.env')
load_dotenv(dotenv_path=env_path)

# JSON Data Path (Where the ebooks are)
BASE_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/ebooks_jsons_for_token_analysis"

# Output Logs Path
OUTPUT_LOGS = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/pipeline-llm/pipeline-outputs"
TEI_OUTPUT_DIR = os.path.join(OUTPUT_LOGS, "tei_chunks")
LOG_FILE = os.path.join(OUTPUT_LOGS, "simple_pipeline_log.csv")

# Testing Settings
TEST_LIMIT = 1  #Set TEST_LIMIT = None (or 0) to run the full set.

# Model Settings
MODEL_NAME = "openai/gpt-oss-20b:free"
PROVIDER = "openai"
SEED = 50

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
##Instruction
You are a converter from HTML to TEI‑XML.
Convert the HTML snippet in the input into TEI‑XML.
Return only the TEI content, without additional tags, comments, header, or explanations.
Keep the text content exactly as it is, do not alter it.
Preserve the paragraph structure.
Ensure proper nesting of tags.
Chapter titles should be marked with a <head>.
Enclose each section in a <div type="…"> chosen from the list of possible types below.
Each chapter must be enclosed in a <div type="chapter">.
Ignore layout attributes that only affect appearance.
If you do not know a corresponding element, keep the original element unchanged and write it as <uncertain>.

##List of <div type> options


Introduction
Interlude
Prologue
Foreword
Chapter
Reading-sample
Prelude
Epilogue
Afterword
Cast-list
Toc
Advertisement
Faq
Feedback
Preview
Copyright-statement
Dedication
Author-information
"""

# --- USER PROMPT ---
USER_PROMPT = """HTML Input:
{html_content}
"""

def clean_tei_output(content: str) -> str:
    """Removes '```xml' wrappers if the LLM includes them."""
    if "```" in content:
        parts = content.split("```")
        if len(parts) >= 2:
            code_block = parts[1]
            if code_block.lower().startswith("xml"):
                code_block = code_block[3:]
            return code_block.strip()
    return content.strip()

def extract_div_type(tei_content: str) -> str:
    """Helper to find what <div type="..."> the LLM actually chose."""
    match = re.search(r'<div[^>]*type=["\']([^"\']+)["\']', tei_content)
    if match:
        return match.group(1)
    return "unknown"

def log_to_csv(chunk_id, status, chosen_type, error_msg=""):
    """Writes a simple status line to the CSV."""
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["chunk_id", "status", "chosen_div_type", "error_message"])
        writer.writerow([chunk_id, status, chosen_type, error_msg])

def main():
    # Setup folders
    os.makedirs(TEI_OUTPUT_DIR, exist_ok=True)

    print(f"--- Starting Simple Pipeline with {MODEL_NAME} ---")

    # 1. Initialize AI
    try:
        llm = init_chat_model(
            model=MODEL_NAME,
            model_provider=PROVIDER,
            base_url=os.getenv("OPEN_ROUTER_BASE_URL"),
            api_key=os.getenv("OPEN_ROUTER_API_KEY"),
            temperature=0.0,
            seed = SEED,
        )
    except Exception as e:
        print(f"Error initializing Model: {e}")
        return

    # 2. Setup Prompt
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", USER_PROMPT)
    ])

    # 3. Load Chunks
    print(f"Loading data from: {BASE_PATH}")
    loader = DataLoader(BASE_PATH, OUTPUT_LOGS)
    work_units = loader.load_and_chunk()
    print(f"Loaded {len(work_units)} chunks total.")

    # Apply Test Limit
    if TEST_LIMIT:
        print(f"TEST MODE: Processing first {TEST_LIMIT} chunks only.")
        work_units = work_units[:TEST_LIMIT]

    # 4. Processing Loop
    for i, unit in enumerate(work_units):
        chunk_id = unit['id']
        html_input = unit['html']
        save_path = os.path.join(TEI_OUTPUT_DIR, f"{chunk_id}.xml")

        print(f"[{i+1}/{len(work_units)}] Converting {chunk_id}...", end=" ", flush=True)

        if os.path.exists(save_path):
            print("Skipped (Exists)")
            log_to_csv(chunk_id, "Skipped", "n/a", "File already exists")
            continue

        try:
            # Run Chain
            final_prompt = prompt_template.invoke({"html_content": html_input})
            response = llm.invoke(final_prompt)

            # Process Output
            tei_result = clean_tei_output(response.content)
            chosen_type = extract_div_type(tei_result)

            # Save
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(tei_result)

            print(f"Done! ({chosen_type})")
            log_to_csv(chunk_id, "Success", chosen_type)

            time.sleep(1)

        except Exception as e:
            print(f"Error: {e}")
            log_to_csv(chunk_id, "Error", "n/a", str(e))

if __name__ == "__main__":
    main()









'''import os
import csv
import time
import json
from datetime import datetime
from dotenv import load_dotenv

# LangChain Imports (Modern LCEL)
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Import your data loader
from chunking_chapters import DataLoader

# --- CONFIGURATION ---
load_dotenv() # Load OPENROUTER_API_KEY from .env

# Paths
BASE_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/ebooks_jsons_for_token_analysis"
OUTPUT_LOGS = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/test_langchain_connection/__pycache__/output_logs/"
TEI_OUTPUT_DIR = os.path.join(OUTPUT_LOGS, "tei_chunks")

# Model Settings
MODEL_NAME = "openai/gpt-oss-20b:free" # Or "google/gemini-2.0-flash-exp:free"
PROVIDER = "openai" # OpenRouter uses OpenAI SDK compatibility
TEMPERATURE = 0.0
SEED = 42

# --- PROMPT TEMPLATES ---

# UPDATED: Added the list of types for self-classification
SYSTEM_PROMPT = """You are an expert Digital Humanities assistant specialized in TEI (Text Encoding Initiative) XML.
Your task is to convert the provided HTML code into valid and well-formed TEI-XML.

Rules:
1. Return ONLY the TEI content. Do NOT include Markdown backticks (```xml), comments, or headers.
2. Content Fidelity: Retain all text content exactly. Do not add or remove words.
3. Structure:
   - <h2>, <h3> -> <head>
   - <p> -> <p>
   - <i>, <em> -> <hi rend="italic">
   - <b>, <strong> -> <hi rend="bold">
4. Nesting: Ensure proper nesting. Close all tags.
5. Root Element: Wrap the entire output in a single <div type="...">.
   - Choose the best type from the list below based on the content (e.g. if it looks like a foreword, use 'Foreword').
   - If the user provides specific context about separators, apply it to the <div> attributes.
6. Uncertainties: If you encounter an unknown element, use <uncertain original="tagname">content</uncertain>.

## List of <div type> options:
Introduction, Interlude, Prologue, Foreword, Reading-sample, Prelude, Epilogue, Afterword, Cast-list, Toc, Advertisement, chapter, Faq, Feedback, Preview, Copyright-statement, Dedication, Author-information

Output Format:
Return strictly the XML string. No "Here is the XML" prefix.
"""

# UPDATED: Simplified User Prompt
USER_PROMPT = """{specific_instructions}

HTML Input:
{html_content}
"""

# --- LOGGING SETUP ---
LOG_FILE = os.path.join(OUTPUT_LOGS, "pipeline_execution_log.csv")

def init_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "chunk_id", "model", "status", "input_tokens", "output_tokens", "latency", "finish_reason", "error_msg"])

def log_result(chunk_id, status, input_tok=0, output_tok=0, latency=0.0, finish_reason="unknown", error=""):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            chunk_id,
            MODEL_NAME,
            status,
            input_tok,
            output_tok,
            f"{latency:.2f}",
            finish_reason,
            error
        ])

# --- HELPER FUNCTIONS ---

def extract_tokens(response):
    """Handle token extraction across different LLM providers."""
    # Try different locations for usage metadata
    usage = getattr(response, 'usage_metadata', {})
    if not usage:
        usage = response.response_metadata.get('token_usage', {})

    # Normalize keys (different providers use different names)
    input_tokens = usage.get('input_tokens') or usage.get('prompt_tokens', 0)
    output_tokens = usage.get('output_tokens') or usage.get('completion_tokens', 0)

    return input_tokens, output_tokens

def clean_tei_output(content: str) -> str:
    """Remove common markdown wrappers safely."""
    if "```" in content:
        parts = content.split("```")
        # Usually parts[1] is the content in ```xml ... ``` blocks
        if len(parts) >= 3:
            inner = parts[1]
            # remove 'xml' or 'html' if it starts with it (case insensitive)
            if inner.lower().startswith('xml'):
                inner = inner[3:]
            elif inner.lower().startswith('html'):
                inner = inner[4:]
            return inner.strip()
    return content.strip()

def main():
    # 1. Setup
    init_log()
    os.makedirs(TEI_OUTPUT_DIR, exist_ok=True)

    print(f"--- Starting TEI Pipeline with {MODEL_NAME} ---")

    # 2. Initialize LLM
    llm = init_chat_model(
        model=MODEL_NAME,
        model_provider=PROVIDER,
        base_url=os.getenv("OPEN_ROUTER_BASE_URL", "[https://openrouter.ai/api/v1](https://openrouter.ai/api/v1)"),
        api_key=os.getenv("OPEN_ROUTER_API_KEY"),
        temperature=TEMPERATURE,
        model_kwargs={
            "seed": SEED,
            "extra_headers": {
                "HTTP-Referer": "[https://dimeclass.local](https://dimeclass.local)",
                "X-Title": "TEI Converter"
            }
        }
    )

    # 3. Create Chain
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", USER_PROMPT)
    ])

    # 4. Load Data
    print("Loading Work Units...")
    loader = DataLoader(BASE_PATH, OUTPUT_LOGS)
    work_units = loader.load_and_chunk()

    print(f"Processing {len(work_units)} chunks...")

    for i, unit in enumerate(work_units):
        chunk_id = unit['id']
        file_path = os.path.join(TEI_OUTPUT_DIR, f"{chunk_id}.xml")
        metadata_path = file_path.replace('.xml', '_metadata.json')

        # Skip if already done
        if os.path.exists(file_path):
            log_result(chunk_id, "skipped", finish_reason="already_exists")
            print(f"[{i+1}/{len(work_units)}] Skipping {chunk_id} (Already exists)")
            continue

        print(f"[{i+1}/{len(work_units)}] Processing {chunk_id} ({unit['strategy']})...")

        # --- DYNAMIC PROMPT LOGIC ---
        strategy = unit['strategy']
        instructions = ""

        if strategy == 'implicit_stars_split':
            # Scenario A: It was split by stars (which are now gone).
            instructions = (
                "Context: This chunk was originally separated by asterisks (***). "
                "Please add rend=\"star-separator\" to the enclosing <div type=\"chapter\">."
            )
        else:
            # Scenario B: Standard Content
            instructions = "Context: Classify this text chunk using the list of types provided."

        start_time = time.time()

        try:
            # 5. Invoke LLM
            formatted_input = prompt.format_messages(
                specific_instructions=instructions,
                html_content=unit['html']
            )

            # Call Model
            response = llm.invoke(formatted_input)

            end_time = time.time()
            latency = end_time - start_time

            # 6. Extract Metadata
            input_tokens, output_tokens = extract_tokens(response)

            # Defensive metadata access
            try:
                meta = response.response_metadata or {}
                finish_reason = meta.get('finish_reason', 'unknown')
            except AttributeError:
                finish_reason = 'unknown'

            # 7. Cleanup
            tei_content = clean_tei_output(response.content)

            # 8. Save Output (XML)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(tei_content)

            # 9. Save Metadata (JSON Sidecar)
            metadata = {
                "chunk_id": chunk_id,
                "strategy": unit['strategy'],
                "was_separated_by_stars": unit['strategy'] == 'implicit_stars_split',
                "inferred_type": unit.get('inferred_type'),
                "model": MODEL_NAME,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency": latency,
                "finish_reason": finish_reason,
                "timestamp": datetime.now().isoformat()
            }
            with open(metadata_path, 'w', encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            # 10. Log Success
            log_result(chunk_id, "success", input_tokens, output_tokens, latency, finish_reason)
            print(f"   -> Success ({latency:.1f}s, {output_tokens} tokens)")

            # Rate limit guard
            time.sleep(2)

        except Exception as e:
            print(f"   -> ERROR: {e}")
            log_result(chunk_id, "error", error=str(e))

if __name__ == "__main__":
    main()'''
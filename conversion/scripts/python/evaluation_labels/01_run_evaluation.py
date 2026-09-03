import os
import json
import time
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# --- CONFIGURATION ---
# Paths
# BASE_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/evaluation_labels"
# CHUNKS_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation/chunks_for_labeling"
# GOLD_FILE = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation/goldstandard_verified/manual_labels_unsorted_chunks"
# RESULTS_FILE = os.path.join(BASE_DIR, "results/03_12_big_models_eval_results.tsv")
# LOG_FILE = os.path.join(BASE_DIR, "logs/03_12_big_models_eval_log.txt")

BASE_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/evaluation_labels"
CHUNKS_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/goldstandard_labels_creation/new_testdata/chunks_for_labeling"
# Falls kein Gold-Standard vorhanden, GOLD_FILE auf None
GOLD_FILE = None
RESULTS_FILE = os.path.join(BASE_DIR, "results_new_testdata/30_03_eval_results.tsv")
LOG_FILE = os.path.join(BASE_DIR, "logs_new_testdata/30_03_eval_log.txt")

# ENV Path
ENV_PATH = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/chunking/.env"

# Ensure directories exist
os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# API Setup
load_dotenv(ENV_PATH)
API_KEY = os.getenv("OPEN_ROUTER_API_KEY")
BASE_URL = os.getenv("OPEN_ROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Models to evaluate with pricing
# active: Set to True to include in evaluation, False to skip
# limit: Optional integer to restrict how many chunks to process for this model in the current run (None = no limit)
MODELS_TO_EVAL = [
    {
        "name": "mistralai/mistral-large-2512",
        "active": False,
        "limit": None
    },
    {
        "name": "qwen/qwen3.5-397b-a17b",
        "active": False,
        "limit": None
    },
    {
        "name": "meta-llama/llama-3.3-70b-instruct",
        "active": False,
        "limit": None
    },
    {
        "name": "z-ai/glm-5",
        "active": False,
        "limit": None
    },
    {
        "name": "deepseek/deepseek-v3.2-speciale",
        "active": True,
        "limit": None
    },


    {
        "name": "openai/gpt-oss-120b",
        "active": False,
        "limit": None
    },
    {
        "name": "openai/gpt-oss-20b",
        "active": False,
        "limit": None
    },
    {
        "name": "deepseek/deepseek-v3.2",
        "active": False,
        "limit": None
    },
     {
        "name": "nvidia/nemotron-3-nano-30b-a3b",
        "active": False,
        "limit": None
    },
    {
        "name": "moonshotai/kimi-k2-0905",
        "active": False,
        "limit": None
    },
]


# Global lookup for chunk texts
CHUNK_LOOKUP = {}

# --- UTILS ---

def logger(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")

def load_chunks_into_memory():
    """
    Scans all JSON files in CHUNKS_DIR and loads texts into a global dictionary.
    This handles the case where IDs are stored in 'gold_chunks_part_XX.json' files.
    """
    global CHUNK_LOOKUP
    logger(f"Scanning {CHUNKS_DIR} for chunk data...")

    if not os.path.exists(CHUNKS_DIR):
        logger(f"Error: CHUNKS_DIR {CHUNKS_DIR} does not exist.")
        return []

    json_files = [f for f in os.listdir(CHUNKS_DIR) if f.endswith('.json')]

    for file_name in json_files:
        file_path = os.path.join(CHUNKS_DIR, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure data is a list of chunks
                if isinstance(data, list):
                    for item in data:
                        if 'id' in item and 'text' in item:
                            CHUNK_LOOKUP[item['id']] = item['text']
        except Exception as e:
            logger(f"Error reading file {file_name}: {e}")

    logger(f"Successfully indexed {len(CHUNK_LOOKUP)} chunks from {len(json_files)} files.")
    return list(CHUNK_LOOKUP.keys())

def load_gold_standard(all_ids):
    """
    Versucht das Gold-Standard zu laden.
    Falls GOLD_FILE None ist oder nicht existiert, wird ein DF mit leeren Labels erstellt.
    """
    if GOLD_FILE and os.path.exists(GOLD_FILE):
        logger(f"Loading Gold Standard from {GOLD_FILE}...")
        try:
            with open(GOLD_FILE, 'r', encoding='utf-8') as f:
                data_list = json.load(f)
            merged_data = {}
            for entry in data_list:
                merged_data.update(entry)
            # Convert dict to DataFrame: {id: label} -> columns [id, gold_label]
            df = pd.DataFrame(list(merged_data.items()), columns=['id', 'gold_label'])
            return df
        except Exception as e:
            logger(f"Error loading GOLD_FILE: {e}. Falling back to empty gold labels.")

    logger("No Gold Standard found. Creating empty 'gold_label' column for all detected chunks.")
    return pd.DataFrame({'id': all_ids, 'gold_label': [None] * len(all_ids)}) # Alternative: statt None [""] also leer

def get_llm_chain(model_name):
    """Initializes the LangChain object."""
    llm = ChatOpenAI(
        model=model_name,
        openai_api_key=API_KEY,
        openai_api_base=BASE_URL,
        temperature=0.0,
        max_retries=5,
        seed = 42
    )

    prompt = ChatPromptTemplate.from_template(
        """
        #Instruction
        You are a specialist in German pulp fiction literature.
        Classify the following HTML text chunk into exactly one category from the "Labels" list.
        If the label is "reader-information" you must also assign a subtype from the "Subtypes" list.

        # Labels
        - **cover-image**: Contains an image. Must not contain text.
        - **title-page**: contains the story title and optionally the author name; may contain an image. No other text is allowed.
        - **imprint**: legal information, publishing house details, copyright
        - **toc**: table of contents
        - **chapter**: prose narrative including prologue, chapters and epilogue of the novel. Note: Does not include previews, plot summaries, "Was bisher geschah" (recap) or series background.
        - **feedback**: letters to the editor (Leserkontaktseite) or prompts for the reader to leave a review or rating (e.g. "Sag uns deine Meinung. Wir freuen unsüber Bewertungen und Rezensionen im Store", "Wir hoffen, dass es dir gefallen hat")
        - **author-information**: biographical information about the author
        - **reader-information**: meta-text regarding the story world or additional content for the readers (e.g. adverisements, series summaries, previews). Note: If the text asks for reader feedback, use "feedback" instead.
        - **unknown**

        # Subtypes (only for "reader-information" label)
        - **meta-information**: series summaries, historical information, "mystery press", "Was bisher geschah" (recaps)
        - **advertisement**: commercial promotional content. May include "coming soon" teasers, reading samples or sales pitches for other novels or other products.
        - **editorial**: forewords, afterwords or acknowledgments by the author/editor
        - **preview**: preview content for the current or next installment/story in a series
        - **dedication**
        - **castlist**
        - **other**

        # Response Format
        Your response must be exclusively a valid JSON object.
        Do not include any introductory text, explanations, or markdown formatting.
        The value for "label" must be one of the items in the "Labels" list. You are forbidden from using a subtype as the primary "label".
        Use the following keys:
        - "label": The assigned category name.
        - "subtype": The assigned subtype if the label is "reader-information". Otherwise, this value must be null.

        example for reader-information:
        {{
        "label": "reader-information",
        "subtype": "advertisement"
        }}

        example for any other label:

        {{
            "label": "chapter",
            "subtype": null
        }}

        # TEXT TO CLASSIFY
        {text}
        """
    )

    return prompt | llm | JsonOutputParser()

# --- MAIN EXECUTION ---

def main():
    logger("Starting Evaluation/Labeling Run")

    # 1. Load Texts into Memory and get all IDs
    all_chunk_ids = load_chunks_into_memory()

    # 2. Load Gold Standard (or create empty one)
    gold_df = load_gold_standard(all_chunk_ids)
    logger(f"Base dataset initialized with {len(gold_df)} chunks.")

    # 3. Load or Create Results DataFrame
    if os.path.exists(RESULTS_FILE):
        results_df = pd.read_csv(RESULTS_FILE, sep='\t')
        # Sicherstellen, dass NaN Werte aus der TSV als leere Strings behandelt werden, im Fall von [""] statt [None] bei def load_gold_standard
        #results_df['gold_label'] = results_df['gold_label'].fillna("")
        logger("Existing results file found. Resuming...")
        # Check if new chunks were added to gold standard since last run
        new_ids = gold_df[~gold_df['id'].isin(results_df['id'])]
        if not new_ids.empty:
            results_df = pd.concat([results_df, new_ids], ignore_index=True)
            logger(f"Added {len(new_ids)} new IDs to Gold Standard.")
    else:
        results_df = gold_df.copy()
        logger(f"New results file initialized at {RESULTS_FILE}")

    # 4. Ensure columns exist for all active models
    for m in MODELS_TO_EVAL:
        if not m.get('active', True): continue

        col_base = m['name'].replace('/', '_').replace(':', '_')
        col_subtype = f"{col_base}_subtype"

        # Ensure both columns exist
        if col_base not in results_df.columns:
            results_df[col_base] = pd.Series([None] * len(results_df), dtype=object)
        if col_subtype not in results_df.columns:
            results_df[col_subtype] = pd.Series([None] * len(results_df), dtype=object)

        model_name = m['name']
        limit = m.get('limit')
        already_done = results_df[col_base].notna().sum()

        # Logic for limit
        if limit is not None:
            to_do = max(0, limit - already_done)
            logger(f"Model: {model_name} | Target: {limit} | Done: {already_done} | Remaining for this run: {to_do}")
        else:
            to_do = len(results_df) - already_done

        if to_do <= 0:
            logger(f"Skipping {model_name} (Already complete).")
            continue

        logger(f"Processing {model_name}: {to_do} chunks remaining.")
        chain = get_llm_chain(model_name)
        processed_this_run = 0

        # 6. Iterate over Chunks
        for idx, row in tqdm(results_df.iterrows(), total=len(results_df), desc=f"Model: {model_name}"):
            # Skip if already processed by this model
            if pd.notna(row[col_base]):
                continue

            # Stop if we hit the limit for this run
            if limit is not None and processed_this_run >= to_do:
                logger(f"Limit of {limit} reached for {model_name}. Stopping.")
                break

            chunk_id = row['id']
            text = CHUNK_LOOKUP.get(chunk_id)

            if not text:
                logger(f"Warning: Text not found in indexed files for ID {chunk_id}")
                continue

            try:
                # LLM Call
                response = chain.invoke({"text": text})

                # Extract label/ Update Dataframe
                label = response.get("label", "unknown")
                subtype = response.get("subtype")

                # Validation: Subtype only allowed for reader-information
                if label != "reader-information" or subtype is None:
                    subtype = "none"

                results_df.at[idx, col_base] = label
                results_df.at[idx, col_subtype] = subtype

                # Increment counter
                processed_this_run += 1
                if processed_this_run % 5 == 0: # Save every 5 chunks
                    results_df.to_csv(RESULTS_FILE, sep='\t', index=False)

            except Exception as e:
                logger(f"Error processing {chunk_id} with {model_name}: {e}")
                time.sleep(5)
                continue

        results_df.to_csv(RESULTS_FILE, sep='\t', index=False)

    logger("Evaluation complete.")

if __name__ == "__main__":
    main()
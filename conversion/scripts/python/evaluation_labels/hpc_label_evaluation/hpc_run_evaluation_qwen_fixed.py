#!/usr/bin/env python3
"""
Qwen3.5-397B-A17B-AWQ Evaluation Job
Processes German pulp fiction chunks with GLM-5 for classification.
Fully compliant with Datenschutz: all data local, no external APIs.

Usage:
  Submitted via SLURM: sbatch run_glm5.sh
  Direct: python hpc_run_evaluation_glm5.py (requires WS env var)
"""

import os
import json
import time
import pandas as pd
import logging
from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

# Enable vLLM debug logging to diagnose model loading
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s')

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
WS = os.environ.get("WS")
if not WS:
    raise ValueError(
        "ERROR: 'WS' environment variable not set. "
        "This script must be run via the SLURM job script which sets WS=$(ws_find mistral_eval_ws)"
    )

# Use local node SSD for model cache (814 GiB available, ~6.8 GB/s read)
# This bypasses the slow NFS/workspace storage during model loading
# Note: HF_HOME is set in the bash script before Python runs
LOCAL_TMPDIR = "/tmp/hf_cache"  # Reference only, don't modify

CHUNKS_DIR = os.path.join(WS, "data/chunks_for_labeling")
GOLD_FILE = os.path.join(WS, "data/manual_labels_unsorted_chunks")
RESULTS_FILE = os.path.join(WS, "results/hpc_qwen_eval_results.tsv")
LOG_FILE = os.path.join(WS, "logs/qwen_log.txt")

# Ensure output directories exist
os.makedirs(os.path.join(WS, "results"), exist_ok=True)
os.makedirs(os.path.join(WS, "logs"), exist_ok=True)

# Model configuration
#MODEL_ID = os.path.join(os.environ.get("HF_HOME", ""), "hub/models--QuantTrio--Qwen3.5-397B-A17B-AWQ")
COL_BASE = "qwen_label"
COL_SUBTYPE = "qwen_subtype"

# Context window and batch settings
MAX_MODEL_LEN = 32768  # Qwen3.5-397B full context length (was 8192, too small)
MAX_CHUNK_CHARS = 500_000  # Match 32K token context (was 100K, now 5x larger)
BATCH_SIZE = 8  # Reduced from 32 for 32K context on 4× H100s

# System prompt for classification
SYSTEM_PROMPT = """\
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
"""

# ─────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────


def logger(message: str):
    """Log message to both file and stdout with timestamp."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def load_chunks_into_memory() -> dict:
    """
    Load all text chunks from JSON files in CHUNKS_DIR.
    Returns dict: {chunk_id: chunk_text}
    """
    chunk_lookup: dict = {}
    logger(f"Scanning {CHUNKS_DIR} for chunk data...")

    if not os.path.exists(CHUNKS_DIR):
        logger(f"ERROR: Directory does not exist: {CHUNKS_DIR}")
        return chunk_lookup

    # Find all .json files
    json_files = [f for f in os.listdir(CHUNKS_DIR) if f.endswith(".json")]
    logger(f"Found {len(json_files)} JSON files to read.")

    for file_name in json_files:
        fp = os.path.join(CHUNKS_DIR, file_name)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Data can be a list of dicts or a dict
            if isinstance(data, list):
                for item in data:
                    if "id" in item and "text" in item:
                        chunk_lookup[item["id"]] = item["text"]
            elif isinstance(data, dict):
                if "id" in data and "text" in data:
                    chunk_lookup[data["id"]] = data["text"]

        except Exception as e:
            logger(f"  WARNING: Error reading {file_name}: {e}")

    logger(f"Successfully indexed {len(chunk_lookup)} chunks from disk.")
    return chunk_lookup


def load_gold_standard() -> pd.DataFrame:
    """
    Load gold-standard labels from JSON file.
    Expected format: list of dicts, each dict maps chunk_id to label.
    Returns DataFrame with columns: [id, gold_label]
    """
    logger(f"Loading gold-standard labels from {GOLD_FILE}...")

    with open(GOLD_FILE, "r", encoding="utf-8") as f:
        data_list = json.load(f)

    # Merge all dicts in the list
    merged: dict = {}
    for entry in data_list:
        if isinstance(entry, dict):
            merged.update(entry)

    df = pd.DataFrame(list(merged.items()), columns=["id", "gold_label"])
    logger(f"Loaded {len(df)} gold-standard labels.")
    return df


def extract_json(raw: str) -> dict:
    """
    Robustly parse JSON from model output.
    Handles:
      - Clean JSON: {"label": ...}
      - Markdown fences: ```json ... ```
      - Brief preamble: 'Here is: {"label": ...}'
    """
    # Try 1: Direct parse (fast path)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try 2: Strip markdown fences
    if "```" in raw:
        for block in raw.split("```"):
            cleaned = block.strip().lstrip("json").strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue

    # Try 3: Find first { ... } substring
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    # All extraction methods failed
    raise ValueError(f"No valid JSON found in output:\n{raw!r}")


def validate_json_label(res: dict) -> tuple[str, str | None]:
    """
    Validate and extract label and subtype from JSON.
    Returns (label, subtype) tuple.
    """
    label = res.get("label", "unknown")
    subtype = res.get("subtype", None)

    # Validate label
    valid_labels = [
        "cover-image",
        "title-page",
        "imprint",
        "toc",
        "chapter",
        "feedback",
        "author-information",
        "reader-information",
        "unknown",
    ]

    if label not in valid_labels:
        label = "unknown"

    # Subtype only valid for reader-information
    if label != "reader-information":
        subtype = None

    return label, subtype


# ─────────────────────────────────────────────────────────────
# MAIN EVALUATION LOOP
# ─────────────────────────────────────────────────────────────


def main():
    """Main evaluation loop."""
    job_start = time.time()

    logger("=" * 70)
    logger("Qwen3.5-397B-A17B-AWQ Evaluation Job")
    logger(f"Model: Qwen/Qwen3.5-397B-A17B (AWQ quantized)")
    logger(f"Config: MAX_MODEL_LEN={MAX_MODEL_LEN}, BATCH_SIZE={BATCH_SIZE}")
    logger(f"Data: {CHUNKS_DIR}")
    logger("=" * 70)

    # ─ Load data ─
    chunk_lookup = load_chunks_into_memory()
    gold_df = load_gold_standard()

    if len(chunk_lookup) == 0:
        logger("ERROR: No chunks loaded. Exiting.")
        return 1

    if len(gold_df) == 0:
        logger("ERROR: No gold labels loaded. Exiting.")
        return 1

    # ─ Setup/resume results file ─
    logger("")
    logger("Setting up results file...")
    if os.path.exists(RESULTS_FILE):
        results_df = pd.read_csv(RESULTS_FILE, sep="\t")
        logger(f"Resuming from existing results file ({len(results_df)} rows).")
    else:
        results_df = gold_df.copy()
        logger(f"Starting new results file with {len(results_df)} rows.")

    # Ensure columns exist
    if COL_BASE not in results_df.columns:
        results_df[COL_BASE] = None
    if COL_SUBTYPE not in results_df.columns:
        results_df[COL_SUBTYPE] = None

    # Identify chunks that still need processing
    remaining = results_df[results_df[COL_BASE].isna()].index.tolist()

    if not remaining:
        logger("All chunks already processed. Exiting.")
        logger("")
        logger("=" * 70)
        logger("Evaluation complete (no work to do)")
        logger("=" * 70)
        return 0

    logger(f"{len(remaining)} chunks to process.")

    # ─ Load tokenizer ─
    logger("")
    logger("Loading Qwen3.5-397B tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen3.5-397B-A17B", trust_remote_code=True
        )
        logger(f"Tokenizer loaded. Vocab size: {tokenizer.vocab_size}")

        # Inspect tokenizer context window
        if hasattr(tokenizer, 'model_max_length'):
            logger(f"Tokenizer model_max_length: {tokenizer.model_max_length}")
        else:
            logger("Tokenizer has no model_max_length attribute")

        # Log tokenizer config if available
        if hasattr(tokenizer, 'chat_template'):
            logger(f"Chat template available: {bool(tokenizer.chat_template)}")

        # Count system prompt tokens
        system_tokens = len(tokenizer.encode(SYSTEM_PROMPT))
        logger(f"System prompt token count: {system_tokens}")

    except Exception as e:
        logger(f"ERROR: Failed to load tokenizer: {e}")
        return 1

    # ─ Load vLLM with tensor parallelism ─
    logger("Initializing vLLM with tensor_parallel_size=4 and AWQ quantization...")
    logger(f"Model cache location: {LOCAL_TMPDIR}")
    logger(f"HF_HOME set to: {os.environ.get('HF_HOME')}")

    model_load_start = time.time()
    try:
        llm = LLM(
            model="QuantTrio/Qwen3.5-397B-A17B-AWQ",
            dtype="float16",
            tensor_parallel_size=4,
            quantization="awq",
            load_format="safetensors",
            trust_remote_code=True,
            gpu_memory_utilization=0.80,
            max_model_len=MAX_MODEL_LEN,
            enforce_eager=True,
        )
        model_load_elapsed = time.time() - model_load_start
        logger(f"vLLM initialized successfully in {model_load_elapsed:.1f}s on 4× H100 GPUs with AWQ quantization.")

        # Diagnose actual vLLM context window
        if hasattr(llm, 'llm_engine') and hasattr(llm.llm_engine, 'model_config'):
            model_config = llm.llm_engine.model_config
            if hasattr(model_config, 'max_model_len'):
                logger(f"vLLM model_config.max_model_len: {model_config.max_model_len}")
            if hasattr(model_config, 'hf_config'):
                logger(f"vLLM model config type: {type(model_config.hf_config)}")

        logger(f"Requested MAX_MODEL_LEN: {MAX_MODEL_LEN}")

    except Exception as e:
        logger(f"ERROR: Failed to initialize vLLM: {e}")
        import traceback
        logger(traceback.format_exc())
        return 1

    sampling_params = SamplingParams(
        temperature=0.0,  # Greedy decoding for deterministic labels
        max_tokens=200,  # JSON label is small, 150 is generous
        top_p=1.0,
        seed =42,
    )
    logger("Sampling parameters set (greedy mode).")

    # ─ Process in large batches ─
    logger("")
    logger("Starting batch processing...")
    logger("")

    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num, i in enumerate(range(0, len(remaining), BATCH_SIZE), start=1):
        batch_indices = remaining[i : i + BATCH_SIZE]
        batch_start = time.time()

        prompts = []
        valid_idx = []

        # Prepare prompts for this batch
        for idx in batch_indices:
            cid = results_df.at[idx, "id"]
            text = chunk_lookup.get(cid, "")

            # Handle missing text
            if not text:
                results_df.at[idx, COL_BASE] = "no_text"
                results_df.at[idx, COL_SUBTYPE] = None
                continue

            # Handle oversized chunks
            if len(text) > MAX_CHUNK_CHARS:
                results_df.at[idx, COL_BASE] = "too_long"
                results_df.at[idx, COL_SUBTYPE] = None
                logger(
                    f"  Chunk {cid}: skipped (too long: {len(text)} chars > {MAX_CHUNK_CHARS})"
                )
                continue

            # Format prompt for GLM-5
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ]

            try:
                # Apply chat template to get prompt text
                prompt_text = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )

                # Count tokens in this prompt
                prompt_tokens = len(tokenizer.encode(prompt_text))
                if prompt_tokens > MAX_MODEL_LEN:
                    logger(f"  WARNING: Chunk {cid} exceeds MAX_MODEL_LEN: {prompt_tokens} tokens > {MAX_MODEL_LEN}")

                prompts.append(prompt_text)
                valid_idx.append(idx)

            except Exception as e:
                results_df.at[idx, COL_BASE] = "encoding_error"
                results_df.at[idx, COL_SUBTYPE] = None
                logger(f"  Chunk {cid}: encoding error - {e}")
                continue

        # Skip batch if all items were skipped
        if not prompts:
            results_df.to_csv(RESULTS_FILE, sep="\t", index=False)
            logger(
                f"Batch {batch_num}/{total_batches}: all items skipped, checkpoint saved."
            )
            continue

        # ─ Generate outputs via vLLM ─
        logger(f"Batch {batch_num}/{total_batches}: sending {len(prompts)} prompts to GPU...")

        # Log token statistics for this batch
        batch_token_counts = [len(tokenizer.encode(p)) for p in prompts]
        max_tokens = max(batch_token_counts) if batch_token_counts else 0
        avg_tokens = sum(batch_token_counts) / len(batch_token_counts) if batch_token_counts else 0
        logger(f"  Batch token stats: max={max_tokens}, avg={avg_tokens:.0f}, total={sum(batch_token_counts)}")

        try:
            outputs = llm.generate(prompts, sampling_params)

            # Process each output
            for idx, output in zip(valid_idx, outputs):
                cid = results_df.at[idx, "id"]
                try:
                    # Extract generated text
                    raw_text = output.outputs[0].text.strip()

                    # Parse JSON from output
                    res = extract_json(raw_text)

                    # Validate and assign
                    label, subtype = validate_json_label(res)
                    results_df.at[idx, COL_BASE] = label
                    results_df.at[idx, COL_SUBTYPE] = subtype

                except Exception as e:
                    logger(f"  Parsing error for chunk {cid}: {e}")
                    logger(f"    Raw output: {raw_text[:100]}...")
                    results_df.at[idx, COL_BASE] = "parsing_error"
                    results_df.at[idx, COL_SUBTYPE] = None

        except Exception as e:
            logger(f"CRITICAL: Batch generation failed (batch {batch_num}): {e}")
            # Mark all items in batch as error
            for idx in valid_idx:
                if pd.isna(results_df.at[idx, COL_BASE]):
                    results_df.at[idx, COL_BASE] = "batch_error"
                    results_df.at[idx, COL_SUBTYPE] = None

        # ─ Checkpoint after every batch ─
        results_df.to_csv(RESULTS_FILE, sep="\t", index=False)
        elapsed_batch = time.time() - batch_start
        logger(f"Batch {batch_num}/{total_batches} done in {elapsed_batch:.1f}s - checkpoint saved")

    # ─ Final summary ─
    total_elapsed = time.time() - job_start
    h, rem = divmod(int(total_elapsed), 3600)
    m, s = divmod(rem, 60)

    # Count errors
    error_mask = results_df[COL_BASE].isin(
        ["parsing_error", "batch_error", "encoding_error", "too_long", "no_text"]
    )
    num_errors = error_mask.sum()
    num_success = len(results_df) - num_errors

    logger("")
    logger("=" * 70)
    logger("Evaluation Complete")
    logger(f"Total runtime: {h}h {m}m {s}s")
    logger(f"Total chunks processed: {len(results_df)}")
    logger(f"Successfully classified: {num_success}")
    logger(f"Errors/skipped: {num_errors}")
    logger(f"Results saved to: {RESULTS_FILE}")
    logger("=" * 70)

    return 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
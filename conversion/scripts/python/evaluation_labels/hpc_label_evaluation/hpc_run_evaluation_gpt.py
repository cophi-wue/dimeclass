import os
import json
import time
import pandas as pd
import traceback
from openai_harmony import (
    HarmonyEncodingName,
    load_harmony_encoding,
    Conversation,
    Message,
    Role,
    SystemContent,
    DeveloperContent,
)
from vllm import LLM, SamplingParams

# ─────────────────────────────────────────────
# HPC CONFIGURATION
# ─────────────────────────────────────────────
WS = os.environ.get("WS")
if not WS:
    raise ValueError("Variable 'WS' is not set. Are you running this via the .sh script?")

CHUNKS_DIR   = os.path.join(WS, "data/chunks_for_labeling")
GOLD_FILE    = os.path.join(WS, "data/manual_labels_unsorted_chunks")
RESULTS_FILE = os.path.join(WS, "results/hpc_gptoss_eval_results.tsv")
LOG_FILE     = os.path.join(WS, "logs/hpc_gptoss_eval_log.txt")

os.makedirs(os.path.join(WS, "results"), exist_ok=True)
os.makedirs(os.path.join(WS, "logs"), exist_ok=True)

MODEL_ID   = "openai/gpt-oss-120b"
COL_BASE   = "gpt_oss_120b"
COL_SUBTYPE = f"{COL_BASE}_subtype"

# ── Context window settings ──────────────────
# 4× H100 in MXFP4: the model weights fit in ~160 GB, leaving plenty for KV.
# 32 768 tokens is very safe; raise to 65 536 if you need it.
MAX_MODEL_LEN  = 32768
# Prompt template is ~800 tokens; max output is 150 tokens.
# Remaining budget for chunk text: ~31 800 tokens ≈ 127 000 chars. Be conservative:
MAX_CHUNK_CHARS = 100_000

# How many prompts to hand to llm.generate() in one call.
# vLLM continuous-batching handles the actual GPU scheduling internally.
# 500 is a good balance: large enough to keep all 4 GPUs fully loaded,
# small enough that we can checkpoint progress every ~500 chunks.
BATCH_SIZE = 200

# ─────────────────────────────────────────────
# DEVELOPER INSTRUCTIONS FOR GPT-OSS / HARMONY
# ─────────────────────────────────────────────
# Split across System / Developer / User roles so Harmony renders them
# with the correct special tokens.
DEVELOPER_INSTRUCTIONS = """\
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
{"label": "reader-information", "subtype": "advertisement"}
example for any other label:
{"label": "chapter", "subtype": null}
"""


# ─────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────

def logger(message: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def load_chunks_into_memory() -> dict:
    chunk_lookup: dict = {}
    logger(f"Scanning {CHUNKS_DIR} for chunk data...")
    if not os.path.exists(CHUNKS_DIR):
        logger(f"ERROR: {CHUNKS_DIR} does not exist!")
        return chunk_lookup
    for file_name in [f for f in os.listdir(CHUNKS_DIR) if f.endswith(".json")]:
        fp = os.path.join(CHUNKS_DIR, file_name)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if "id" in item and "text" in item:
                        chunk_lookup[item["id"]] = item["text"]
        except Exception as e:
            logger(f"Error reading {file_name}: {e}")
    logger(f"Successfully indexed {len(chunk_lookup)} chunks.")
    return chunk_lookup


def load_gold_standard() -> pd.DataFrame:
    with open(GOLD_FILE, "r", encoding="utf-8") as f:
        data_list = json.load(f)
    merged: dict = {}
    for entry in data_list:
        merged.update(entry)
    return pd.DataFrame(list(merged.items()), columns=["id", "gold_label"])


def build_harmony_prompt(text: str, encoding) -> list[int]:
    """Render a single chunk into Harmony token IDs ready for vLLM."""
    convo = Conversation.from_messages([
        Message.from_role_and_content(Role.SYSTEM, SystemContent.new()),
        Message.from_role_and_content(
            Role.DEVELOPER,
            DeveloperContent.new().with_instructions(DEVELOPER_INSTRUCTIONS),
        ),
        Message.from_role_and_content(Role.USER, text),
    ])
    token_ids = encoding.render_conversation_for_completion(convo, Role.ASSISTANT)
    # Flatten if Harmony returned a list of lists
    if token_ids and isinstance(token_ids[0], list):
        token_ids = [t for sublist in token_ids for t in sublist]
    return token_ids


def parse_harmony_output(output, encoding) -> str:
    """Return raw text output without Harmony parsing."""
    return output.outputs[0].text.strip()




def extract_json(raw: str) -> dict:
    """
Robustly parse JSON from model output.
Handles:
    - clean JSON            → {"label": …}
    - markdown fences       → ```json … ```
    - brief preamble text   → 'Here is the JSON: {"label": …}'
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    if "```" in raw:
        for block in raw.split("```"):
            cleaned = block.strip().lstrip("json").strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue

    # Find LAST valid JSON block (in case of duplicates/concatenation)
    start = raw.rfind("{")
    end   = raw.find("}", start) + 1
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in: {raw!r}")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    job_start = time.time()
    logger("=" * 60)
    logger(f"Starting GPT-OSS 120B Evaluation  |  model={MODEL_ID}")
    logger(f"MAX_MODEL_LEN={MAX_MODEL_LEN}  |  MAX_CHUNK_CHARS={MAX_CHUNK_CHARS}  |  BATCH_SIZE={BATCH_SIZE}")
    logger("=" * 60)

    # 1. Load data
    chunk_lookup = load_chunks_into_memory()
    gold_df      = load_gold_standard()

    # 2. Setup / resume results file
    # if os.path.exists(RESULTS_FILE):
    #     results_df = pd.read_csv(RESULTS_FILE, sep="\t")
    #     logger(f"Resuming from existing results file ({len(results_df)} rows).")
    # else:
    #     results_df = gold_df.copy()
    #     logger(f"Starting new results file ({len(results_df)} rows).")

    # if COL_BASE    not in results_df.columns: results_df[COL_BASE]    = None
    # if COL_SUBTYPE not in results_df.columns: results_df[COL_SUBTYPE] = None

    # remaining = results_df[results_df[COL_BASE].isna()].index.tolist()
    # if not remaining:
    #     logger("All chunks already processed. Nothing to do.")
    #     return

    # logger(f"{len(remaining)} chunks to process.")
    # 2. Setup / resume results file
    if os.path.exists(RESULTS_FILE):
        results_df = pd.read_csv(RESULTS_FILE, sep="\t")
        logger(f"Resuming from existing results file ({len(results_df)} rows).")
    else:
        results_df = gold_df.copy()
        logger(f"Starting new results file ({len(results_df)} rows).")

    # Ensure the GPT-specific columns exist (Mirroring your Mistral logic)
    if COL_BASE not in results_df.columns:
        results_df[COL_BASE] = None
    if COL_SUBTYPE not in results_df.columns:
        results_df[COL_SUBTYPE] = None

    # Now identify work to do
    remaining = results_df[results_df[COL_BASE].isna()].index.tolist()

    if not remaining:
        logger("All chunks already processed. Nothing to do.")
        # Safety debug: print what's actually in that column
        if len(results_df) > 0:
             logger(f"Sample from {COL_BASE}: {results_df[COL_BASE].iloc[0]}")
        return

    # 3. Load Harmony encoding
    logger("Loading Harmony encoding…")
    encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    stop_token_ids = encoding.stop_tokens_for_assistant_actions()
    # Flatten if it's a list of lists
    if stop_token_ids and isinstance(stop_token_ids[0], list):
        stop_token_ids = [t for sublist in stop_token_ids for t in sublist]

    # 4. Load vLLM with tensor parallelism across all 4 H100s
    logger("Initialising vLLM (tensor_parallel_size=4)…")
    llm = LLM(
        model                  = MODEL_ID,
        tensor_parallel_size   = 4,        # one shard per H100
        trust_remote_code      = True,     # required for MXFP4 layers
        gpu_memory_utilization = 0.70,     # conservative to avoid OOM; adjust if you see headroom
        max_model_len          = MAX_MODEL_LEN,
    )
    sampling_params = SamplingParams(
        temperature    = 0.0,              # greedy → deterministic labels
        seed           = 42,
        max_tokens     = 500,              # JSON label is short; was 150 before; increased due to cases with incomplete output
        stop_token_ids = stop_token_ids,
    )
    logger("vLLM ready.")

    # 5. Process in large batches (continuous batching inside vLLM)
    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num, i in enumerate(range(0, len(remaining), BATCH_SIZE), start=1):
        batch_indices = remaining[i : i + BATCH_SIZE]
        batch_start   = time.time()

        prompts   = []   # list of {"prompt_token_ids": [...]}
        valid_idx = []   # result-df indices that produced a prompt

        for idx in batch_indices:
            cid  = results_df.at[idx, "id"]
            text = chunk_lookup.get(cid, "")

            if not text:
                results_df.at[idx, COL_BASE]    = "no_text"
                results_df.at[idx, COL_SUBTYPE] = "none"
                logger(f"  Chunk {cid}: no text found in chunk_lookup — skipped.")
                continue

            if len(text) > MAX_CHUNK_CHARS:
                results_df.at[idx, COL_BASE]    = "too_long"
                results_df.at[idx, COL_SUBTYPE] = "none"
                logger(f"  Chunk {cid}: too_long ({len(text)} chars) — skipped.")
                continue

            try:
                token_ids = build_harmony_prompt(text, encoding)
            except Exception as e:
                results_df.at[idx, COL_BASE]    = "encoding_error"
                results_df.at[idx, COL_SUBTYPE] = "none"
                logger(f"  Chunk {cid}: encoding error — {e}")
                continue

            prompts.append({"prompt_token_ids": token_ids})
            valid_idx.append(idx)

        if not prompts:
            # All items in batch were skipped; checkpoint and continue
            results_df.to_csv(RESULTS_FILE, sep="\t", index=False)
            logger(f"  Batch {batch_num}/{total_batches}: all items skipped — checkpoint saved.")
            continue

        logger(f"  Batch {batch_num}/{total_batches}: sending {len(prompts)} prompts to GPU…")

        try:
            # ── Single llm.generate call = continuous batching over all prompts ──
            logger(f"  DEBUG prompts[0] type={type(prompts[0])}, token_ids type={type(prompts[0]['prompt_token_ids'])}, first element type={type(prompts[0]['prompt_token_ids'][0])}")
            outputs = llm.generate(prompts, sampling_params)

            for idx, output in zip(valid_idx, outputs):
                cid = results_df.at[idx, "id"]
                try:
                    raw_text = parse_harmony_output(output, encoding) ## returns plain text
                    res      = extract_json(raw_text) # extract_json will find {"label": ...}
                    results_df.at[idx, COL_BASE]    = res.get("label",   "unknown")
                    results_df.at[idx, COL_SUBTYPE] = res.get("subtype", "none")
                except Exception as e:
                    raw_text = parse_harmony_output(output, encoding)
                    # Check if JSON is incomplete (ends mid-string)
                    has_incomplete_json = "\"label\":" in raw_text and not (raw_text.rstrip().endswith("}"))
                    logger(f"    Parsing error for chunk {cid}: {e}")
                    if has_incomplete_json:
                        logger(f"      → Incomplete JSON detected (truncated output)")
                    logger(f"      → Last 300 chars: ...{raw_text[-300:]}")
                    results_df.at[idx, COL_BASE]    = "parsing_error"
                    results_df.at[idx, COL_SUBTYPE] = "none"

        except Exception as e:
            logger(f"  CRITICAL batch error (batch {batch_num}): {e}")
            logger(f"  TRACEBACK:\n{traceback.format_exc()}")
            # Mark all pending items so we know what failed
            for idx in valid_idx:
                if pd.isna(results_df.at[idx, COL_BASE]):
                    results_df.at[idx, COL_BASE]    = "batch_error"
                    results_df.at[idx, COL_SUBTYPE] = "none"

        # Checkpoint after every batch so progress is never lost
        results_df.to_csv(RESULTS_FILE, sep="\t", index=False)
        elapsed_batch = time.time() - batch_start
        logger(f"  Batch {batch_num}/{total_batches} done in {elapsed_batch:.1f}s — checkpoint saved.")

    # 6. Final summary
    total_elapsed = time.time() - job_start
    h, rem  = divmod(int(total_elapsed), 3600)
    m, s    = divmod(rem, 60)
    error_mask = results_df[COL_BASE].isin(["parsing_error", "batch_error", "encoding_error"])
    logger("=" * 60)
    logger(f"Evaluation complete  |  total runtime: {h}h {m}m {s}s")
    logger(f"Rows with errors: {error_mask.sum()}")
    logger(f"Results saved to: {RESULTS_FILE}")

    # Log error summary by type
    error_counts = results_df[COL_BASE].value_counts()
    logger("Error breakdown:")
    for err_type in ["parsing_error", "batch_error", "encoding_error"]:
        count = error_counts.get(err_type, 0)
        if count > 0:
            logger(f"  {err_type}: {count}")

    # Write failed chunk IDs to separate file for inspection
    failed_chunks = results_df[error_mask][["id"]].copy()
    if len(failed_chunks) > 0:
        failed_file = os.path.join(WS, "logs/failed_chunks.txt")
        failed_chunks["id"].to_csv(failed_file, index=False, header=False)
        logger(f"Failed chunk IDs saved to: {failed_file}")
    logger("=" * 60)


if __name__ == "__main__":
    main()
#!/bin/bash
#SBATCH --job-name=qwen_eval
#SBATCH --partition=capella
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH --mem=500G
#SBATCH --gres=gpu:4
#SBATCH --time=02:00:00
#SBATCH --output=logs/qwen_%j.out
#SBATCH --error=logs/qwen_%j.err

# ─────────────────────────────────────────────────────────────
# Qwen3.5-397B-A17B-AWQ Evaluation Job
# Dresden Cluster (Capella) - Fully Datenschutz Compliant
#
# Data Protection: All processing is local on cluster.
# No external APIs. No data leaves the server.
# Model runs on 4× H100 GPUs with tensor parallelism.
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# CONFIGURATION & ENVIRONMENT
# ─────────────────────────────────────────────────────────────

# Find workspace (required for all file paths)
export WS=$(ws_find mistral_eval_ws)

# NOTE: HF_HOME will be set by the Python script to /tmp/hf_cache for node-local speed

# Project results directory (for archival after job completes)
PROJECT_RESULTS_DIR="/projects/p_dnbnovel/data/pele579g-dnb_novel-1769817765/Marina/llm_eval/results"
PROJECT_LOGS_DIR="/projects/p_dnbnovel/data/pele579g-dnb_novel-1769817765/Marina/llm_eval/logs"

# ─────────────────────────────────────────────────────────────
# JOB HEADER
# ─────────────────────────────────────────────────────────────

echo "============================================================"
echo "  Qwen3.5-397B-A17B-AWQ Evaluation Job"
echo "  Started  : $(date '+%Y-%m-%d %H:%M:%S')"
echo "  SLURM ID : $SLURM_JOB_ID"
echo "  Node     : $SLURMD_NODENAME"
echo "  GPUs     : $(nvidia-smi --list-gpus 2>/dev/null | wc -l) detected"
echo "============================================================"

# ─────────────────────────────────────────────────────────────
# CHECKS
# ─────────────────────────────────────────────────────────────

echo "[CHECK] Running checks..."

# 1. Workspace found
if [ -z "$WS" ]; then
    echo "ERROR: Workspace 'mistral_eval_ws' not found by ws_find. Aborting."
    exit 1
fi
echo "  [OK] Workspace: $WS"

# 2. Data files present
if [ ! -f "$WS/data/manual_labels_unsorted_chunks" ]; then
    echo "ERROR: Gold-standard file not found: $WS/data/manual_labels_unsorted_chunks"
    exit 1
fi
echo "  [OK] Gold-standard file present."

if [ ! -d "$WS/data/chunks_for_labeling" ]; then
    echo "ERROR: Chunks directory not found: $WS/data/chunks_for_labeling"
    exit 1
fi
CHUNK_COUNT=$(find "$WS/data/chunks_for_labeling" -name "*.json" 2>/dev/null | wc -l)
echo "  [OK] Chunks directory present ($CHUNK_COUNT JSON files)."

# 3. Python venv exists
if [ ! -f "$WS/venv_gpt_oss/bin/activate" ]; then
    echo "ERROR: Python venv not found at $WS/venv_gpt_oss/bin/activate"
    exit 1
fi
echo "  [OK] Python venv found."

# 4. Python script exists
SCRIPT_PATH="$WS/hpc_run_evaluation_qwen35.py"
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: Python script not found at $SCRIPT_PATH"
    echo "       Please copy hpc_run_evaluation_qwen35.py to the workspace."
    exit 1
fi
echo "  [OK] Python script found."

# 5. Model weights cached in workspace
MODEL_CACHE_DIR="$WS/hf_home/hub/models--QuantTrio--Qwen3.5-397B-A17B-AWQ"
if [ ! -d "$MODEL_CACHE_DIR" ]; then
    echo "ERROR: Model cache NOT found at $MODEL_CACHE_DIR"
    echo "       This prevents accidental downloads. Aborting."
    exit 1
fi
BLOB_COUNT=$(find "$MODEL_CACHE_DIR/blobs" -type f 2>/dev/null | wc -l)
echo "  [OK] Model weights found in workspace ($BLOB_COUNT blob files)."

# 6. Ensure log/results directories exist
mkdir -p "$WS/logs" "$WS/results"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create log/results directories."
    exit 1
fi
echo "  [OK] Log and results directories ready."

echo "[CHECK] All checks passed."
echo ""

# ─────────────────────────────────────────────────────────────
# MODULE LOADING & ENVIRONMENT SETUP
# ─────────────────────────────────────────────────────────────

echo "[SETUP] Loading modules..."

# Clear any existing modules
module purge

# Load required modules (matched to venv Python version 3.13.1)
module load release/2026 GCCcore/14.2.0 Python/3.13.1

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to load modules."
    exit 1
fi

echo "  Modules loaded successfully."

# Activate Python venv
echo "[SETUP] Activating Python venv..."
source "$WS/venv_gpt_oss/bin/activate"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate venv."
    exit 1
fi

# Set HF_HOME in the environment BEFORE Python runs
export HF_HOME="/tmp/hf_cache"
echo "  HF_HOME exported: $HF_HOME"

# ─ CRITICAL: Copy model to local node SSD ─
echo "[SETUP] Preparing model cache on local SSD..."
MODEL_SRC="$WS/hf_home/hub/models--QuantTrio--Qwen3.5-397B-A17B-AWQ"
MODEL_DST="/tmp/hf_cache/hub/models--QuantTrio--Qwen3.5-397B-A17B-AWQ"

if [ ! -d "$MODEL_SRC" ]; then
    echo "ERROR: Model not found at $MODEL_SRC"
    exit 1
fi

mkdir -p "/tmp/hf_cache/hub"

if [ -d "$MODEL_DST" ] && [ -d "$MODEL_DST/blobs" ]; then
    BLOB_COUNT=$(find "$MODEL_DST/blobs" -type f 2>/dev/null | wc -l)
    if [ "$BLOB_COUNT" -gt 0 ]; then
        echo "  Model already cached locally ($BLOB_COUNT blobs). Skipping copy."
    else
        echo "  Previous copy incomplete. Starting fresh copy..."
        rm -rf "$MODEL_DST"
        COPY_START=$(date +%s)
        cp -r "$MODEL_SRC" "$MODEL_DST"
        COPY_EXIT=$?
        COPY_END=$(date +%s)
        COPY_TIME=$((COPY_END - COPY_START))

        if [ $COPY_EXIT -ne 0 ]; then
            echo "ERROR: Failed to copy model to local SSD."
            exit 1
        fi
        echo "  Model copied successfully in ${COPY_TIME}s."
    fi
else
    echo "  Copying model from workspace to node-local SSD..."
    echo "  Source: $MODEL_SRC"
    echo "  Destination: $MODEL_DST"

    COPY_START=$(date +%s)
    cp -r "$MODEL_SRC" "$MODEL_DST"
    COPY_EXIT=$?
    COPY_END=$(date +%s)
    COPY_TIME=$((COPY_END - COPY_START))

    if [ $COPY_EXIT -ne 0 ]; then
        echo "ERROR: Failed to copy model to local SSD."
        exit 1
    fi
    echo "  Model copied successfully in ${COPY_TIME}s."
fi

# Verify model integrity - WAIT until all blobs are present
echo "  Verifying model integrity..."
EXPECTED_BLOBS=82  # AWQ model has 82 shards
MAX_WAIT=600  # 10 minutes timeout
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    BLOB_COUNT=$(find "$MODEL_DST/blobs" -type f 2>/dev/null | wc -l)
    if [ "$BLOB_COUNT" -ge "$EXPECTED_BLOBS" ]; then
        echo "  [OK] Model cache complete: $BLOB_COUNT blob files present."
        break
    fi

    if [ $((WAITED % 30)) -eq 0 ]; then
        echo "  Waiting for copy to complete... ($BLOB_COUNT/$EXPECTED_BLOBS blobs)"
    fi

    sleep 5
    WAITED=$((WAITED + 5))
done

if [ "$BLOB_COUNT" -lt "$EXPECTED_BLOBS" ]; then
    echo "ERROR: Model copy timed out after ${MAX_WAIT}s. Only $BLOB_COUNT/$EXPECTED_BLOBS blobs present."
    exit 1
fi

echo ""

# Verify Python and key packages
echo "[SETUP] Verifying environment..."
PYTHON_VER=$(python3 --version 2>&1)
echo "  Python: $PYTHON_VER"

VLLM_VER=$(python3 -c "import vllm; print(vllm.__version__)" 2>&1)
if [ $? -eq 0 ]; then
    echo "  vLLM: $VLLM_VER"
else
    echo "  WARNING: Could not verify vLLM version"
fi

TRANSFORMERS_VER=$(python3 -c "import transformers; print(transformers.__version__)" 2>&1)
if [ $? -eq 0 ]; then
    echo "  Transformers: $TRANSFORMERS_VER"
else
    echo "  WARNING: Could not verify Transformers version"
fi

echo "  HF_HOME: $HF_HOME"
echo ""

# ─────────────────────────────────────────────────────────────
# RUN EVALUATION
# ─────────────────────────────────────────────────────────────

echo "[RUN] Launching evaluation at $(date '+%Y-%m-%d %H:%M:%S')..."
echo ""

# Run with srun for proper MPI coordination on HPC
# --unbuffered ensures output appears in log file in real-time
srun --unbuffered python3 "$SCRIPT_PATH"
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "[RUN] Evaluation completed successfully (exit code 0)."
else
    echo "ERROR: Evaluation failed with exit code $EXIT_CODE"
fi

# ─────────────────────────────────────────────────────────────
# ARCHIVE RESULTS
# ─────────────────────────────────────────────────────────────

#echo ""
#echo "[ARCHIVE] Syncing results to project folder..."

# Create archival directories
#mkdir -p "$PROJECT_RESULTS_DIR" "$PROJECT_LOGS_DIR"

# Copy results
#if cp -r "$WS/results/." "$PROJECT_RESULTS_DIR/"; then
#    RESULT_FILES=$(ls -1 "$PROJECT_RESULTS_DIR" | wc -l)
#    echo "  [OK] Results copied to $PROJECT_RESULTS_DIR ($RESULT_FILES files)"
#else
#    echo "  WARNING: Failed to copy results. Check permissions on $PROJECT_RESULTS_DIR"
#fi

# Copy logs (for debugging and record-keeping)
#if cp -r "$WS/logs/." "$PROJECT_LOGS_DIR/" 2>/dev/null; then
#    LOG_FILES=$(ls -1 "$PROJECT_LOGS_DIR" | wc -l)
#    echo "  [OK] Logs copied to $PROJECT_LOGS_DIR ($LOG_FILES files)"
#fi

#echo ""

# ─────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────

echo "============================================================"
echo "  Evaluation Job Complete"
echo "  Finished : $(date '+%Y-%m-%d %H:%M:%S')"
echo "  SLURM ID : $SLURM_JOB_ID"
echo "  Exit code: $EXIT_CODE"
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "  Status   : SUCCESS ✓"
    echo "  Results  : $WS/results/hpc_qwen_eval_results.tsv"
    echo "  Logs     : $WS/logs/hpc_qwen_eval_log.txt"
else
    echo "  Status   : FAILED ✗"
    echo "  Check logs for details"
fi
echo "============================================================"

exit $EXIT_CODE
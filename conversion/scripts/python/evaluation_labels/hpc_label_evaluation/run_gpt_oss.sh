#!/bin/bash
#SBATCH --job-name=gptoss_eval
#SBATCH --partition=capella
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH --mem=500G
#SBATCH --gres=gpu:4
#SBATCH --time=01:00:00
#SBATCH --output=logs/gptoss_%j.out
#SBATCH --error=logs/gptoss_%j.err

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
export WS=$(ws_find mistral_eval_ws)
#export HF_HOME=$WS/hf_home
export HF_HOME="/home/masp231h/workspaces/horse/masp231h-mistral_eval_ws/hf_home"

PROJECT_RESULTS_DIR="/projects/p_dnbnovel/data/pele579g-dnb_novel-1769817765/Marina/llm_eval/results"

echo "============================================================"
echo "  GPT-OSS 120B Evaluation Job"
echo "  Started  : $(date '+%Y-%m-%d %H:%M:%S')"
echo "  SLURM ID : $SLURM_JOB_ID"
echo "  Node     : $SLURMD_NODENAME"
echo "============================================================"

# ─────────────────────────────────────────────────────────────
# QUALITY / SANITY CHECKS
# ─────────────────────────────────────────────────────────────
echo "[CHECK] Running checks..."

# 1. Workspace found
if [ -z "$WS" ]; then
    echo "ERROR: Workspace 'mistral_eval_ws' not found by ws_find. Aborting."
    exit 1
fi
echo "  [OK] Workspace: $WS"

# 2. Required data files present
if [ ! -f "$WS/data/manual_labels_unsorted_chunks" ]; then
    echo "ERROR: Gold-standard file not found: $WS/data/manual_labels_unsorted_chunks"
    exit 1
fi
echo "  [OK] Gold-standard file present."

if [ ! -d "$WS/data/chunks_for_labeling" ]; then
    echo "ERROR: Chunks directory not found: $WS/data/chunks_for_labeling"
    exit 1
fi
echo "  [OK] Chunks directory present."

# 3. Python venv exists
if [ ! -f "$WS/venv_gpt_oss/bin/activate" ]; then
    echo "ERROR: Python venv not found at $WS/venv_gpt_oss. Aborting."
    exit 1
fi
echo "  [OK] Python venv found."

# 4. Python script present
SCRIPT_PATH="$WS/hpc_run_evaluation_gpt.py"
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: Python script not found at $SCRIPT_PATH. Aborting."
    exit 1
fi
echo "  [OK] Python script found."

# 5. Model weights cached in HF_HOME
MODEL_CACHE_DIR="$HF_HOME/hub/models--openai--gpt-oss-120b"
if [ ! -d "$MODEL_CACHE_DIR" ]; then
    echo "ERROR: Model cache NOT found at $MODEL_CACHE_DIR."
    echo "Aborting to prevent accidental downloads."
    exit 1
else
    echo "  [OK] Model weights found in HF cache."
fi


# 8. Ensure log/results directories exist (Python also does this, belt-and-suspenders)
mkdir -p "$WS/logs" "$WS/results"
echo "  [OK] Log and results directories ready."

echo "[CHECK] All checks passed."
echo ""

# ─────────────────────────────────────────────────────────────
# MODULE LOAD & VENV ACTIVATION
# ─────────────────────────────────────────────────────────────
module purge
module load release/2026 GCCcore/14.2.0 Python/3.13.1

source "$WS/venv_gpt_oss/bin/activate"

echo "[INFO] Python: $(which python3)"
echo "[INFO] Python version: $(python3 --version)"

# ─────────────────────────────────────────────────────────────
# RUN INFERENCE
# ─────────────────────────────────────────────────────────────
echo ""
echo "[RUN] Launching evaluation at $(date '+%Y-%m-%d %H:%M:%S')..."
echo ""

# --unbuffered ensures stdout/stderr appear in the .out file in real time
srun --unbuffered python3 "$SCRIPT_PATH"
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "[RUN] Python script finished successfully (exit 0)."
else
    echo "ERROR: Python script exited with code $EXIT_CODE."
fi

# ─────────────────────────────────────────────────────────────
# SYNC RESULTS TO PROJECT FOLDER
# ─────────────────────────────────────────────────────────────
echo ""
echo "[SYNC] Copying results to project folder..."

mkdir -p "$PROJECT_RESULTS_DIR"

if cp -r "$WS/results/." "$PROJECT_RESULTS_DIR/"; then
    echo "  [OK] Results copied to $PROJECT_RESULTS_DIR"
else
    echo "  WARNING: cp failed for results. Check permissions on $PROJECT_RESULTS_DIR"
fi

# Also copy logs so you have the full runtime record alongside the results
LOG_BACKUP_DIR="/projects/p_dnbnovel/data/pele579g-dnb_novel-1769817765/Marina/llm_eval/logs"
mkdir -p "$LOG_BACKUP_DIR"
cp -r "$WS/logs/." "$LOG_BACKUP_DIR/" 2>/dev/null && \
    echo "  [OK] Logs copied to $LOG_BACKUP_DIR"

# ─────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Job finished : $(date '+%Y-%m-%d %H:%M:%S')"
echo "  SLURM job ID : $SLURM_JOB_ID"
echo "  Exit code    : $EXIT_CODE"
echo "============================================================"

exit $EXIT_CODE
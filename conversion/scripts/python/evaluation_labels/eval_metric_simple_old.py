import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score, precision_score, recall_score

# --- CONFIGURATION ---
BASE_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/evaluation_labels"
RESULTS_FILE = os.path.join(BASE_DIR, "results/eval_results.tsv")
OUTPUT_DIR = os.path.join(BASE_DIR, "metrics_output_subtypes")

# Columns to ignore/delete (as requested)
#COLUMNS_TO_DROP = [
 #   "meta-llama_llama-3.1-405b-instruct_free",
  #  "moonshotai_kimi-k2-0905_thinking",
#]

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "confusion_matrices"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "reports_per_model"), exist_ok=True)

def load_and_clean_data():
    if not os.path.exists(RESULTS_FILE):
        print(f"Error: Results file not found at {RESULTS_FILE}")
        return None

    # Load TSV
    df = pd.read_csv(RESULTS_FILE, sep='\t')

    # 1. Cleaning: Drop unwanted columns
    cols_to_remove = [c for c in df.columns if any(target in c for target in ["free", "thinking"])]
    if cols_to_remove:
        print(f"Dropping columns: {cols_to_remove}")
        df = df.drop(columns=cols_to_remove)

    # 2. Label Normalization
    # Strip and lowercase to avoid "Label" != "label" issues
    df['gold_label'] = df['gold_label'].astype(str).str.strip().str.lower()

    return df

def analyze_gold_set(df):
    print("\n--- [1] GOLD STANDARD DESCRIPTIVE ANALYSIS ---")
    counts = df['gold_label'].value_counts()
    percentages = df['gold_label'].value_counts(normalize=True) * 100

    summary = pd.DataFrame({'Count': counts, 'Percentage': percentages})
    print(summary)

    # Visualization of label distribution
    plt.figure(figsize=(10, 6))
    sns.barplot(x=counts.values, y=counts.index, palette='viridis')
    plt.title(f"Label Distribution in Gold Set (N={len(df)})")
    plt.xlabel("Number of Chunks")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "gold_set_distribution.png"))
    plt.close()

def run_model_evaluation(df):
    # Identify model columns (those that aren't metadata)
    model_cols = [c for c in df.columns if c not in ['id', 'gold_label']]
    leaderboard_data = []

    for model in model_cols:
        print(f"\nProcessing Model: {model}")

        # Only evaluate rows where this model has a prediction
        valid_df = df[df[model].notna()].copy()
        if len(valid_df) == 0:
            continue

        y_true = valid_df['gold_label']
        # Normalize model predictions to match gold standard format
        y_pred = valid_df[model].astype(str).str.strip().str.lower()
        # y_pred = y_pred.replace('author-information', 'author-info')

        # 1. Calculate Multi-Class Metrics
        # Accuracy: Simple percentage of correct hits
        acc = accuracy_score(y_true, y_pred)

        # Macro Metrics: Treats every class as equally important
        # Helpful to see if the model is generally "accurate" (Precision) or "thorough" (Recall)
        f1_macro = f1_score(y_true, y_pred, average='macro', zero_division=0)
        prec_macro = precision_score(y_true, y_pred, average='macro', zero_division=0)
        rec_macro = recall_score(y_true, y_pred, average='macro', zero_division=0)

        # Weighted Metrics: Performance proportional to class size
        f1_weighted = f1_score(y_true, y_pred, average='weighted', zero_division=0)

        leaderboard_data.append({
            'Model': model,
            'Accuracy': acc,
            'Macro_Precision': prec_macro,
            'Macro_Recall': rec_macro,
            'Macro_F1': f1_macro,
            'Weighted_F1': f1_weighted,
            'Samples': len(valid_df)
        })

        # 2. Per-Model Classification Report (Prettified for CSV)
        report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
        report_df = pd.DataFrame(report).transpose()
        report_df.index.name = "Label"
        report_df.to_csv(os.path.join(OUTPUT_DIR, f"reports_per_model/report_{model}.csv"))

        # 3. Confusion Matrix Visualization
        all_labels = sorted(list(set(y_true) | set(y_pred)))
        cm = confusion_matrix(y_true, y_pred, labels=all_labels)

        plt.figure(figsize=(12, 10))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=all_labels, yticklabels=all_labels)
        plt.title(f"Confusion Matrix: {model}")
        plt.ylabel('Actual Label (Gold)')
        plt.xlabel('Predicted Label (Model)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, f"confusion_matrices/cm_{model}.png"))
        plt.close()

    # Create Leaderboard (Ranked by Macro F1)
    leaderboard_df = pd.DataFrame(leaderboard_data).sort_values(by='Macro_F1', ascending=False)
    print("\n--- [2] MODEL LEADERBOARD ---")
    print(leaderboard_df.to_string(index=False))
    leaderboard_df.to_csv(os.path.join(OUTPUT_DIR, "model_leaderboard.csv"), index=False)

def main():
    print("Starting Metrics Generation...")
    df = load_and_clean_data()
    if df is not None:
        analyze_gold_set(df)
        run_model_evaluation(df)
        print(f"\nEvaluation Complete.")
        print(f"Check the '{OUTPUT_DIR}' folder for detailed CSVs and Plots.")

if __name__ == "__main__":
    main()
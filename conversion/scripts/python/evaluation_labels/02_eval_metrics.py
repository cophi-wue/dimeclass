import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (classification_report, confusion_matrix, accuracy_score, f1_score, precision_score,recall_score)

# --- KONFIGURATION ---
BASE_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/evaluation_labels"
#RESULTS_FILE = os.path.join(BASE_DIR, "results/03_12_eval_results.tsv")
#RESULTS_FILE = os.path.join(BASE_DIR, "results_new_testdata/30_03_eval_results.tsv")
#RESULTS_FILE = os.path.join(BASE_DIR, "results/eval_results_full.tsv")
RESULTS_FILE = os.path.join(BASE_DIR, "hpc_label_evaluation/hpc_gptoss_eval_results.tsv")
# Ausgabeordner
OUTPUT_DIR_FULL = os.path.join(BASE_DIR, "metrics_output")
OUTPUT_DIR_FILTERED = os.path.join(BASE_DIR, "metrics_output_less_labels")
OUTPUT_DIR_NO_CHAPTER = os.path.join(BASE_DIR, "metrics_output_without_chapter")

# Schwellenwert für die gefilterte Evaluation
#MIN_SAMPLES =  5


def setup_directories(base_output_path):
    """Erstellt die notwendige Ordnerstruktur für die Ergebnisse."""
    os.makedirs(base_output_path, exist_ok=True)
    os.makedirs(os.path.join(base_output_path, "confusion_matrices"), exist_ok=True)
    os.makedirs(os.path.join(base_output_path, "reports_per_model"), exist_ok=True)

def load_and_clean_data():
    """Lädt die TSV-Datei und bereinigt die Labels/Spalten (entfernt Subtypen und Meta-Modelle)."""
    if not os.path.exists(RESULTS_FILE):
        print(f"Fehler: Ergebnisdatei nicht gefunden unter {RESULTS_FILE}")
        return None

    # TSV laden
    df = pd.read_csv(RESULTS_FILE, sep='\t')

    # 1. Bereinigung: Unerwünschte Spalten entfernen
    # 'subtype' Spalten entfernen
    cols_to_remove = [c for c in df.columns if any(target in c.lower() for target in ["subtype"])]

    if cols_to_remove:
        print(f"Entferne Subtype-Spalten: {cols_to_remove}")
        df = df.drop(columns=cols_to_remove)

    # 2. Label-Normalisierung
    # Whitespace entfernen und Kleinschreibung zur Vereinheitlichung
    df['gold_label'] = df['gold_label'].astype(str).str.strip().str.lower()

    # Synonyme korrigieren (falls nötig)
    #df['gold_label'] = df['gold_label'].replace('author-information', 'author-info')

    return df

def analyze_gold_set(df, output_dir):
    """Erstellt eine deskriptive Statistik der Gold-Labels."""
    print(f"\n--- [1] DESKRIPTIVE ANALYSE (N={len(df)}) ---")
    counts = df['gold_label'].value_counts()
    percentages = df['gold_label'].value_counts(normalize=True) * 100

    summary = pd.DataFrame({'Anzahl': counts, 'Prozent': percentages})
    print(summary)

    # Visualisierung der Label-Verteilung
    plt.figure(figsize=(10, 6))
    sns.barplot(x=counts.values, y=counts.index, hue=counts.index, palette='viridis', legend=False)
    plt.title(f"Label-Verteilung im Gold Set (N={len(df)})")
    plt.xlabel("Anzahl der Chunks")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "gold_set_distribution.png"))
    plt.close()

def run_model_evaluation(df, output_path, run_name="Standard"):
    """Führt die Evaluation für alle Modelle durch und speichert Ergebnisse in output_path."""
    setup_directories(output_path)

    # Identifiziere Modell-Spalten (alles außer Metadaten)
    model_cols = [c for c in df.columns if c not in ['id', 'gold_label']]
    leaderboard_data = []

    print(f"\nStarte Evaluation: {run_name} (Ziel: {output_path})")

    for model in model_cols:
        # Nur Zeilen evaluieren, für die das Modell eine Vorhersage hat
        valid_df = df[df[model].notna()].copy()
        if len(valid_df) == 0:
            continue

        y_true = valid_df['gold_label']
        # Vorhersagen normalisieren
        y_pred = valid_df[model].astype(str).str.strip().str.lower()
       # y_pred = y_pred.replace('author-information', 'author-info')

        # 1. Metriken berechnen
        acc = accuracy_score(y_true, y_pred)

        # Macro Metriken
        f1_macro = f1_score(y_true, y_pred, average='macro', zero_division=0)
        prec_macro = precision_score(y_true, y_pred, average='macro', zero_division=0)
        rec_macro = recall_score(y_true, y_pred, average='macro', zero_division=0)

        # Weighted Metriken
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

        # 2. Klassifikationsbericht pro Modell
        report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
        report_df = pd.DataFrame(report).transpose()
        report_df.index.name = "Label"
        report_df.to_csv(os.path.join(output_path, f"reports_per_model/report_{model}.csv"))

        # 3. Confusion Matrix Visualisierung
        all_labels = sorted(list(set(y_true) | set(y_pred)))
        cm = confusion_matrix(y_true, y_pred, labels=all_labels)
        cm_relative = (cm.astype('float') + 1e-10) / (cm.sum(axis=1)[:, np.newaxis] + 1e-10)

        plt.figure(figsize=(12, 10))
        sns.heatmap(cm_relative, annot=True, fmt='.2f', cmap='Blues', xticklabels=all_labels, yticklabels=all_labels)
        plt.title(f"Confusion Matrix ({run_name}): {model}")
        plt.ylabel('Tatsächliches Label (Gold)')
        plt.xlabel('Vorhergesagtes Label (Model)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_path, f"confusion_matrices/cm_{model}.png"))
        plt.close()

    # Leaderboard erstellen (Sortiert nach Macro F1)
    leaderboard_df = pd.DataFrame(leaderboard_data).sort_values(by='Macro_F1', ascending=False)
    print(f"\n--- MODEL LEADERBOARD ({run_name}) ---")
    print(leaderboard_df.to_string(index=False))
    leaderboard_df.to_csv(os.path.join(output_path, f"model_leaderboard_{run_name.lower()}.csv"), index=False)

def main():
    print("Starte erweiterte Metrik-Generierung (Subtypen werden ignoriert)...")

    # WICHTIG: Verzeichnisse VOR der Analyse erstellen, damit Plots gespeichert werden können
    setup_directories(OUTPUT_DIR_FULL)
    #setup_directories(OUTPUT_DIR_FILTERED)
    setup_directories(OUTPUT_DIR_NO_CHAPTER)

    # 1. Daten laden und säubern
    df = load_and_clean_data()
    if df is None:
        return

    # --- TEIL A: Vollständige Evaluation ---
    analyze_gold_set(df, OUTPUT_DIR_FULL)
    run_model_evaluation(df, OUTPUT_DIR_FULL, run_name="Gesamt")

    # --- TEIL B: Gefilterte Evaluation (Labels >= MIN_SAMPLES) ---
    #print(f"\n--- FILTERUNG: Labels mit mindestens {MIN_SAMPLES} Beispielen ---")

    # Bestimme Labels, die den Schwellenwert erreichen
    #label_counts = df['gold_label'].value_counts()
    #valid_labels = label_counts[label_counts >= MIN_SAMPLES].index.tolist()
    #removed_labels = label_counts[label_counts < MIN_SAMPLES].index.tolist()

    #if removed_labels:
    #    print(f"Folgende Labels werden für die reduzierte Evaluation entfernt: {removed_labels}")

    # Filter den DataFrame
    #filtered_df = df[df['gold_label'].isin(valid_labels)].copy()

    #if not filtered_df.empty:
     #   run_model_evaluation(filtered_df, OUTPUT_DIR_FILTERED, run_name=f"Filter_GE_{MIN_SAMPLES}")
    #else:
     #   print("Warnung: Keine Daten nach der Filterung übrig!")

    # --- TEIL C: Evaluation ohne das Label 'chapter' ---
    print("\n--- EVALUATION: Ohne das Label 'chapter' ---")

    # Filter alle Zeilen heraus, deren Gold-Label 'chapter' ist
    df_no_chapter = df[df['gold_label'] != 'chapter'].copy()

    if not df_no_chapter.empty:
        run_model_evaluation(df_no_chapter, OUTPUT_DIR_NO_CHAPTER, run_name="Ohne_Chapter")
    else:
        print("Warnung: Keine Daten übrig nach Ausschluss von 'chapter'!")

    print(f"\nEvaluation abgeschlossen.")
    print(f"Ergebnisse (Alle): {OUTPUT_DIR_FULL}")
   # print(f"Ergebnisse (Gefiltert): {OUTPUT_DIR_FILTERED}")
    print(f"Ergebnisse (Ohne Chapter): {OUTPUT_DIR_NO_CHAPTER}")

if __name__ == "__main__":
    main()
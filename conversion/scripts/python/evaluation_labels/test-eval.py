import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (classification_report, confusion_matrix, accuracy_score, f1_score, precision_score, recall_score)

# --- KONFIGURATION ---
BASE_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/evaluation_labels"
RESULTS_FILE = os.path.join(BASE_DIR, "results/kombiniert.tsv")

# Ausgabeordner
OUTPUT_DIR_FULL = os.path.join(BASE_DIR, "metrics_output")
OUTPUT_DIR_FILTERED = os.path.join(BASE_DIR, "metrics_output_less_labels")
OUTPUT_DIR_NO_CHAPTER = os.path.join(BASE_DIR, "metrics_output_without_chapter")

def setup_directories(base_output_path):
    """Erstellt die notwendige Ordnerstruktur für die Ergebnisse."""
    os.makedirs(base_output_path, exist_ok=True)
    os.makedirs(os.path.join(base_output_path, "confusion_matrices"), exist_ok=True)
    os.makedirs(os.path.join(base_output_path, "reports_per_model"), exist_ok=True)

def load_and_clean_data():
    """Lädt die TSV-Datei und bereinigt die Labels/Spalten."""
    if not os.path.exists(RESULTS_FILE):
        print(f"Fehler: Ergebnisdatei nicht gefunden unter {RESULTS_FILE}")
        return None

    # TSV laden
    df = pd.read_csv(RESULTS_FILE, sep='\t')

    # 1. Bereinigung: Unerwünschte Spalten entfernen (Subtypen)
    cols_to_remove = [c for c in df.columns if any(target in c.lower() for target in ["subtype"])]

    if cols_to_remove:
        print(f"Entferne Subtype-Spalten: {cols_to_remove}")
        df = df.drop(columns=cols_to_remove)

    # 2. Label-Normalisierung
    # Whitespace entfernen und Kleinschreibung zur Vereinheitlichung für Gold und Inferred
    df['gold_label'] = df['gold_label'].astype(str).str.strip().str.lower()

    if 'inferred-type' in df.columns:
        df['inferred-type'] = df['inferred-type'].astype(str).str.strip().str.lower()

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
    """Führt die Evaluation für alle Modelle (inkl. inferred-type) durch."""
    setup_directories(output_path)

    # Identifiziere Modell-Spalten: Alles außer Metadaten ('id', 'gold_label')
    # 'inferred-type' wird hier automatisch als Modell-Spalte behandelt
    metadata_cols = ['id', 'gold_label']
    model_cols = [c for c in df.columns if c not in metadata_cols]

    leaderboard_data = []

    print(f"\nStarte Evaluation: {run_name} (Ziel: {output_path})")

    for model in model_cols:
        # Nur Zeilen evaluieren, für die das Modell eine Vorhersage hat
        valid_df = df[df[model].notna()].copy()
        if len(valid_df) == 0:
            continue

        y_true = valid_df['gold_label']
        # Vorhersagen normalisieren (Sicherstellung von Strings und Lowercase)
        y_pred = valid_df[model].astype(str).str.strip().str.lower()

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
            'Type': 'Hard-coded' if model == 'inferred-type' else 'LLM',
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

        plt.figure(figsize=(12, 10))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=all_labels, yticklabels=all_labels)
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
    print("Starte erweiterte Metrik-Generierung...")

    setup_directories(OUTPUT_DIR_FULL)
    setup_directories(OUTPUT_DIR_NO_CHAPTER)

    # 1. Daten laden und säubern
    df = load_and_clean_data()
    if df is None:
        return

    # --- TEIL A: Vollständige Evaluation ---
    # Hier wird 'inferred-type' automatisch mit allen anderen Modellen verglichen
    analyze_gold_set(df, OUTPUT_DIR_FULL)
    run_model_evaluation(df, OUTPUT_DIR_FULL, run_name="Gesamt")

    # --- TEIL C: Evaluation ohne das Label 'chapter' ---
    print("\n--- EVALUATION: Ohne das Label 'chapter' ---")
    df_no_chapter = df[df['gold_label'] != 'chapter'].copy()

    if not df_no_chapter.empty:
        run_model_evaluation(df_no_chapter, OUTPUT_DIR_NO_CHAPTER, run_name="Ohne_Chapter")
    else:
        print("Warnung: Keine Daten übrig nach Ausschluss von 'chapter'!")

    print(f"\nEvaluation abgeschlossen.")
    print(f"Ergebnisse gespeichert in: {OUTPUT_DIR_FULL}")

if __name__ == "__main__":
    main()
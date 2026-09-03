import pandas as pd
import glob
import os

# Ihr Pfad zu den Ergebnissen
RESULTS_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/token_analysis_results"

def analyze_file(filepath):
    try:
        df = pd.read_csv(filepath, sep='\t')
    except Exception as e:
        print(f"Fehler beim Lesen von {os.path.basename(filepath)}: {e}")
        return

    # Wir schauen nur auf den 'narrative' Teil (Romaninhalt)
    if 'type' not in df.columns:
        print(f"Warnung: Spalte 'type' fehlt in {os.path.basename(filepath)}")
        return

    narrative_df = df[df['type'] == 'narrative']

    if narrative_df.empty:
        print("Keine narrativen Daten (Roman-Inhalt) gefunden.")
        return

    # 1. Das absolute Monster-Kapitel finden (Max Tokens Markup)
    max_idx = narrative_df['tokens_markup'].idxmax()
    worst_row = narrative_df.loc[max_idx]

    print("\n" + "-"*60)
    print(f"🚩 GRÖSSTES KAPITEL in: {os.path.basename(filepath)}")
    print("-"*60)
    print(f"Buch-Datei:     {worst_row['filename']}")
    print(f"Kapitel-ID:     {worst_row['id']}")
    print(f"Tokens (HTML):  {worst_row['tokens_markup']:,.0f}")
    print(f"Wörter (Text):  {worst_row['words_plain']:,.0f}")
    print(f"Overhead:       {worst_row['ratio_markup']:.2f}x")

    # Diagnose
    if worst_row['tokens_markup'] > 20000:
        if "novel" in str(worst_row['id']) and "split" not in str(worst_row['id']):
            print("URSACHE: ⚠️  Buch wurde NICHT gesplittet (Ganzes Buch = 1 Kapitel).")
        elif worst_row['ratio_markup'] > 3.0:
            print("URSACHE: ⚠️  Extremes HTML-Markup (Ratio > 3.0).")
        else:
            print("URSACHE: ℹ️  Tatsächlich sehr langes Kapitel.")
    print("-" * 60)

def main():
    if not os.path.exists(RESULTS_DIR):
        print(f"Ordner nicht gefunden: {RESULTS_DIR}")
        return

    # Alle TSV Dateien finden
    tsv_files = glob.glob(os.path.join(RESULTS_DIR, "*.tsv"))

    if not tsv_files:
        print(f"Keine .tsv Dateien in {RESULTS_DIR} gefunden.")
        return

    print(f"Gefundene Analyse-Dateien: {len(tsv_files)}")

    for tsv_file in sorted(tsv_files):
        analyze_file(tsv_file)

if __name__ == "__main__":
    main()
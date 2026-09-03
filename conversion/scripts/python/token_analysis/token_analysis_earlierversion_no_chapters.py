import json
import glob
import os
import math
import pandas as pd
from bs4 import BeautifulSoup
from transformers import AutoTokenizer
from tqdm import tqdm

# --- KONFIGURATION ---
INPUT_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/ebooks_jsons_for_token_analysis"
OUTPUT_DIR = "/home/spielberg/code/repos/dimeclass/conversion/scripts/python/token_analysis/token_analysis_results"
OUTPUT_FILE_NAME = "token_stats_openai_gpt-oss-20b.tsv"

# Modell (bei jedem Model tsv umbenennen!)
#MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct" # just for testing the code
MODEL_NAME = "openai/gpt-oss-20b"
#MODEL_NAME = "openai/gpt-oss-120b"
#MODEL_NAME = "mistralai/Mixtral-8x22B-Instruct-v0.1"
#MODEL_NAME = "mistralai/Mistral-Small-3.1-24B-Instruct-2503"
#MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct"
WINDOW_SIZES = [4096, 8192, 32768, 128000]

def setup_tokenizer():
    print(f"Lade Tokenizer: {MODEL_NAME}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
        return tokenizer
    except Exception as e:
        print(f"KRITISCHER FEHLER beim Laden des Tokenizers: {e}")
        exit(1)

def count_tokens(tokenizer, text):
    if not text: return 0
    try:
        return len(tokenizer.encode(text, add_special_tokens=False))
    except:
        return 0

def clean_html(html_content):
    if not html_content: return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def process_file(filepath, tokenizer):
    results = []
    filename = os.path.basename(filepath)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Fehler beim Lesen von {filename}: {e}")
        return []

    content_list = data.get("content", [])

    for entry in content_list:
        inferred_type = entry.get("inferred-type", "unknown")
        raw_content = entry.get("text", "")

        # Logik: Was ist Roman (Narrative)?
        is_narrative = True if inferred_type in ["chapter", "novel"] else False

        if not raw_content:
            continue

        chunks = []
        # Split Logik für 'novel' Typen
        if inferred_type == "novel" and "***" in raw_content:
            parts = raw_content.split("***")
            for idx, part in enumerate(parts):
                if part.strip():
                    chunks.append((f"{inferred_type}_split_{idx+1}", part))
        else:
            chunks.append((inferred_type, raw_content))

        for chunk_id, chunk_html in chunks:
            chunk_plain = clean_html(chunk_html)
            word_count = len(chunk_plain.split())

            tokens_markup = count_tokens(tokenizer, chunk_html)
            tokens_plain = count_tokens(tokenizer, chunk_plain)

            ratio = tokens_markup / tokens_plain if tokens_plain > 0 else 1.0
            markup_overhead = tokens_markup - tokens_plain

            tag_count = chunk_html.count("<")

            row = {
                "filename": filename,
                "id": chunk_id,
                "type": "narrative" if is_narrative else "meta",
                "inferred_type": inferred_type,
                "words_plain": word_count,
                "tokens_plain": tokens_plain,
                "tokens_markup": tokens_markup,
                "tokens_overhead": markup_overhead,
                "ratio_markup": round(ratio, 4),
                "tags_approx": tag_count
            }

            # Simulation Context Window
            for window in WINDOW_SIZES:
                row[f"chunks_needed_{window}"] = math.ceil(tokens_markup / window)

            results.append(row)

    return results

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    full_output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE_NAME)

    tokenizer = setup_tokenizer()
    json_files = glob.glob(os.path.join(INPUT_DIR, "*.json"))

    print(f"--- START ANALYSE ({len(json_files)} Dateien) ---")

    all_data = []
    for f in tqdm(json_files, desc="Verarbeite Dateien"):
        file_stats = process_file(f, tokenizer)
        all_data.extend(file_stats)

    df = pd.DataFrame(all_data)

    if df.empty:
        print("Keine Daten extrahiert.")
        return

    # TSV Speichern (unverändert)
    df.to_csv(full_output_path, sep="\t", index=False)
    print(f"\nTSV gespeichert: {full_output_path}")

    # ==========================================
    # NEUE OUTPUT STATISTIK: Pro Buch & Global
    # ==========================================

    print("\n" + "="*85)
    print(f" {'STATISTIK PRO BUCH':^80} ")
    print("="*85)

    # Liste um die Summen pro Buch für den globalen Durchschnitt zu speichern
    book_summaries = []

    unique_files = df['filename'].unique()

    for filename in unique_files:
        file_df = df[df['filename'] == filename]

        # Hilfsfunktion um Summen zu berechnen
        def calc_sums(sub_df):
            if sub_df.empty: return 0, 0, 0, 0.0
            w = sub_df['words_plain'].sum()
            tp = sub_df['tokens_plain'].sum()
            tm = sub_df['tokens_markup'].sum()
            # Overhead % = (HTML - Text) / Text
            oh = ((tm - tp) / tp * 100) if tp > 0 else 0.0
            return w, tp, tm, oh

        # 1. Narrative
        n_w, n_tp, n_tm, n_oh = calc_sums(file_df[file_df['type'] == 'narrative'])

        # 2. Meta
        m_w, m_tp, m_tm, m_oh = calc_sums(file_df[file_df['type'] == 'meta'])

        # 3. Gesamt
        t_w, t_tp, t_tm, t_oh = calc_sums(file_df)

        print(f"\nDATEI: {filename}")
        print(f"{'Bereich':<15} | {'Wörter':>10} | {'Token(Text)':>12} | {'Token(HTML)':>12} | {'Overhead':>10}")
        print("-" * 73)
        print(f"{'Roman Inhalt':<15} | {n_w:10,.0f} | {n_tp:12,.0f} | {n_tm:12,.0f} | {n_oh:9.1f}%")
        print(f"{'Metadaten':<15} | {m_w:10,.0f} | {m_tp:12,.0f} | {m_tm:12,.0f} | {m_oh:9.1f}%")
        print("-" * 73)
        print(f"{'GESAMT':<15} | {t_w:10,.0f} | {t_tp:12,.0f} | {t_tm:12,.0f} | {t_oh:9.1f}%")

        # Daten sammeln für globale Statistik
        book_summaries.append({
            "Narr_Words": n_w, "Narr_TokPlain": n_tp, "Narr_TokHTML": n_tm,
            "Total_Words": t_w, "Total_TokPlain": t_tp, "Total_TokHTML": t_tm
        })

    # ==========================================
    # GLOBALE DURCHSCHNITTE & MEDIAN
    # ==========================================

    summary_df = pd.DataFrame(book_summaries)

    print("\n" + "="*85)
    print(f" {'DURCHSCHNITT & MEDIAN ÜBER ALLE {len(unique_files)} BÜCHER':^80} ")
    print("="*85)

    # Berechnung Mean und Median
    mean_vals = summary_df.mean()
    median_vals = summary_df.median()

    print("\n--- DURCHSCHNITT (Mean) pro Buch ---")
    print(f"{'Kategorie':<15} | {'Wörter':>10} | {'Token(Text)':>12} | {'Token(HTML)':>12}")
    print("-" * 56)
    print(f"{'Roman Inhalt':<15} | {mean_vals['Narr_Words']:10,.0f} | {mean_vals['Narr_TokPlain']:12,.0f} | {mean_vals['Narr_TokHTML']:12,.0f}")
    print(f"{'Ganzes Buch':<15} | {mean_vals['Total_Words']:10,.0f} | {mean_vals['Total_TokPlain']:12,.0f} | {mean_vals['Total_TokHTML']:12,.0f}")

    print("\n--- MEDIAN (Typischer Wert) pro Buch ---")
    print(f"{'Kategorie':<15} | {'Wörter':>10} | {'Token(Text)':>12} | {'Token(HTML)':>12}")
    print("-" * 56)
    print(f"{'Roman Inhalt':<15} | {median_vals['Narr_Words']:10,.0f} | {median_vals['Narr_TokPlain']:12,.0f} | {median_vals['Narr_TokHTML']:12,.0f}")
    print(f"{'Ganzes Buch':<15} | {median_vals['Total_Words']:10,.0f} | {median_vals['Total_TokPlain']:12,.0f} | {median_vals['Total_TokHTML']:12,.0f}")
    print("\n")

if __name__ == "__main__":
    main()
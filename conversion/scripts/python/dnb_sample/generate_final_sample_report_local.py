import pandas as pd
import os
from pathlib import Path

def generate_report(sample_tsv, collected_dir, total_extracted_count):
    # 1. Load the original sample plan
    if not os.path.exists(sample_tsv):
        print(f"Error: {sample_tsv} not found.")
        return
    
    df = pd.read_csv(sample_tsv, sep='\t', dtype={'ID': str})
    
    # 2. Check what is actually in the collected folder
    collected_path = Path(collected_dir)
    if not collected_path.exists():
        print(f"Error: Directory {collected_dir} not found.")
        return
        
    collected_ids = set()
    for d in collected_path.iterdir():
        if d.is_dir():
            # Extract the ID from the folder name (e.g., "000347_Jerry...")
            collected_ids.add(d.name.split('_')[0])
            
    # 3. Filter the dataframe to only include found books
    final_sample_df = df[df['ID'].isin(collected_ids)].copy()
    
    # 4. Calculate Final Statistics
    total_samples = len(final_sample_df)
    coverage_pct = (total_samples / total_extracted_count) * 100
    
    print("="*50)
    print("FINAL COLLECTED SAMPLE AUDIT (LOCAL)")
    print("="*50)
    print(f"Total Books Extracted on HPC: {total_extracted_count}")
    print(f"Final Books in Sample:        {total_samples}")
    print(f"Real Sampling Rate:           {coverage_pct:.2f}%")
    
    print("\nSTRATIFICATION OF ACTUAL COLLECTED DATA:")
    print("-" * 30)
    print("By Publisher Tier:")
    tier_counts = final_sample_df['publisher_tier'].value_counts().sort_index()
    print(tier_counts)
    
    print("\nBy Book Type:")
    print(final_sample_df['book_type'].value_counts())
    
    print("\nBy Sampling Strategy:")
    print(final_sample_df['sampling_strategy'].value_counts())
    
    # 5. Save the updated TSV
    output_file = 'final_collected_sample_metadata.tsv'
    final_sample_df.to_csv(output_file, sep='\t', index=False)
    print(f"\n✓ Saved updated metadata to: {output_file}")
    
    # Return some values for a quick summary in the terminal
    return total_samples, coverage_pct

if __name__ == "__main__":
    # Settings for local run
    generate_report(
        sample_tsv='sample_data_version.tsv', 
        collected_dir='sample_jsons_only',
        total_extracted_count=35068
    )


"""
Create a stratified representative sample for DNB ebook extraction quality evaluation.

Combines:
- Publisher stratification (Tier A/B/C)
- Series vs Standalone stratification
- Series size stratification
- Temporal stratification (first, middle, last book per series)

Output: sample_data.tsv with selected book IDs and sampling metadata
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict
import sys
import os


def define_publisher_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign publisher tiers based on book count distribution.
    
    Tier A: Large publishers (>2000 books)
    Tier B: Medium publishers (500-2000 books)
    Tier C: Small publishers (<500 books)
    """
    publisher_counts = df['Publisher'].value_counts()
    
    tier_a = publisher_counts[publisher_counts > 2000].index.tolist()
    tier_b = publisher_counts[(publisher_counts >= 500) & (publisher_counts <= 2000)].index.tolist()
    tier_c = publisher_counts[publisher_counts < 500].index.tolist()
    
    def assign_tier(pub):
        if pub in tier_a:
            return 'A'
        elif pub in tier_b:
            return 'B'
        elif pub in tier_c:
            return 'C'
        else:
            return 'Unknown'
    
    df['publisher_tier'] = df['Publisher'].apply(assign_tier)
    
    print(f"Publisher Tier Distribution:")
    print(f"  Tier A (>2000 books): {len(tier_a)} publishers, {(df['publisher_tier']=='A').sum()} books")
    print(f"  Tier B (500-2000 books): {len(tier_b)} publishers, {(df['publisher_tier']=='B').sum()} books")
    print(f"  Tier C (<500 books): {len(tier_c)} publishers, {(df['publisher_tier']=='C').sum()} books")
    
    return df


def define_series_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mark books as series books or standalone books.
    
    Series: Series != "?"
    Standalone: Series == "?"
    """
    df['book_type'] = df['Series'].apply(lambda x: 'Series' if x != '?' else 'Standalone')
    
    print(f"\nBook Type Distribution:")
    print(f"  Series books: {(df['book_type']=='Series').sum()}")
    print(f"  Standalone books: {(df['book_type']=='Standalone').sum()}")
    
    return df


def define_series_size_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Categorize series by size: Large (>200), Medium (50-200), Small (<50).
    
    Only applies to books in series.
    """
    series_counts = df[df['book_type'] == 'Series']['Series'].value_counts()
    
    large_series = series_counts[series_counts > 200].index.tolist()
    medium_series = series_counts[(series_counts >= 50) & (series_counts <= 200)].index.tolist()
    small_series = series_counts[series_counts < 50].index.tolist()
    
    def assign_series_size(row):
        if row['book_type'] == 'Standalone':
            return 'N/A'
        series = row['Series']
        if series in large_series:
            return 'Large'
        elif series in medium_series:
            return 'Medium'
        elif series in small_series:
            return 'Small'
        else:
            return 'Unknown'
    
    df['series_size_category'] = df.apply(assign_series_size, axis=1)
    
    print(f"\nSeries Size Distribution (Series books only):")
    print(f"  Large (>200 books): {len(large_series)} series, {(df['series_size_category']=='Large').sum()} books")
    print(f"  Medium (50-200 books): {len(medium_series)} series, {(df['series_size_category']=='Medium').sum()} books")
    print(f"  Small (<50 books): {len(small_series)} series, {(df['series_size_category']=='Small').sum()} books")
    
    return df


def select_temporal_books_from_series(df: pd.DataFrame, series_name: str) -> List[Tuple[int, str]]:
    """
    For a given series, select first, middle, and last book by Date.
    
    Returns list of (book_id, temporal_position) tuples.
    If not enough books or no date info, returns available books.
    """
    series_books = df[df['Series'] == series_name].copy()
    
    # Try to sort by Date, fallback to ID if Date is missing
    series_books['Date_numeric'] = pd.to_numeric(series_books['Date'], errors='coerce')
    
    if series_books['Date_numeric'].notna().sum() > 0:
        # Sort by Date (ascending)
        series_books_sorted = series_books.sort_values('Date_numeric', na_position='last').reset_index(drop=True)
    else:
        # Fallback: sort by ID if no dates
        series_books_sorted = series_books.sort_values('ID').reset_index(drop=True)
    
    n = len(series_books_sorted)
    selected = []
    
    if n == 1:
        selected.append((str(series_books_sorted.iloc[0]['ID']), 'only_book'))
    elif n == 2:
        selected.append((str(series_books_sorted.iloc[0]['ID']), 'first'))
        selected.append((str(series_books_sorted.iloc[-1]['ID']), 'last'))
    elif n == 3:
        selected.append((str(series_books_sorted.iloc[0]['ID']), 'first'))
        selected.append((str(series_books_sorted.iloc[1]['ID']), 'middle'))
        selected.append((str(series_books_sorted.iloc[-1]['ID']), 'last'))
    else:
        # Select first, middle(s), and last
        selected.append((str(series_books_sorted.iloc[0]['ID']), 'first'))
        selected.append((str(series_books_sorted.iloc[n // 2]['ID']), 'middle'))
        selected.append((str(series_books_sorted.iloc[-1]['ID']), 'last'))
        
        # If more than 6 books, add additional quarters
        if n > 6:
            selected.append((str(series_books_sorted.iloc[n // 4]['ID']), 'quarter_1'))
            selected.append((str(series_books_sorted.iloc[(3 * n) // 4]['ID']), 'quarter_3'))
    
    return selected


def stratified_sample_with_temporal_coverage(
    df: pd.DataFrame,
    target_sample_size: int = 500,
    publisher_tier_dist: Dict[str, float] = None,
    book_type_dist: Dict[str, float] = None,
    random_seed: int = 42
) -> pd.DataFrame:
    """
    Create stratified sample with temporal coverage.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input data with stratification columns
    target_sample_size : int
        Target number of books in sample
    publisher_tier_dist : dict
        Distribution {A: 0.6, B: 0.25, C: 0.15}
    book_type_dist : dict
        Distribution {Series: 0.4, Standalone: 0.6}
    random_seed : int
        Random seed for reproducibility
    
    Returns:
    --------
    pd.DataFrame
        Sample data with selection metadata
    """
    
    if publisher_tier_dist is None:
        publisher_tier_dist = {'A': 0.6, 'B': 0.25, 'C': 0.15}
    
    if book_type_dist is None:
        book_type_dist = {'Series': 0.4, 'Standalone': 0.6}
    
    np.random.seed(random_seed)
    
    selected_samples = []
    
    # Iterate through publisher tiers
    for tier in ['A', 'B', 'C']:
        tier_size = int(target_sample_size * publisher_tier_dist[tier])
        tier_df = df[df['publisher_tier'] == tier].copy()
        
        print(f"\n--- Processing Publisher Tier {tier} (target: {tier_size} books) ---")
        
        # Split by book type
        series_target = int(tier_size * book_type_dist['Series'])
        standalone_target = int(tier_size * book_type_dist['Standalone'])
        
        # ============ SERIES BOOKS WITH TEMPORAL COVERAGE ============
        series_df = tier_df[tier_df['book_type'] == 'Series'].copy()
        
        if len(series_df) > 0:
            print(f"  Series books available: {len(series_df)}")
            
            # Get unique series in this tier
            unique_series = series_df['Series'].unique()
            
            # Split by size category
            large_series = series_df[series_df['series_size_category'] == 'Large']['Series'].unique()
            medium_series = series_df[series_df['series_size_category'] == 'Medium']['Series'].unique()
            small_series = series_df[series_df['series_size_category'] == 'Small']['Series'].unique()
            
            # Allocation: Large gets 50%, Medium gets 35%, Small gets 15%
            large_target = int(series_target * 0.50)
            medium_target = int(series_target * 0.35)
            small_target = int(series_target * 0.15)
            
            print(f"    Large series: {len(large_series)} series, allocating {large_target} books")
            print(f"    Medium series: {len(medium_series)} series, allocating {medium_target} books")
            print(f"    Small series: {len(small_series)} series, allocating {small_target} books")
            
            # --- Large Series: Select temporal books ---
            if len(large_series) > 0 and large_target > 0:
                # Estimate books per series (accounting for multiple temporal points)
                books_per_large_series = max(1, large_target // len(large_series))
                
                selected_count = 0
                for series_name in large_series:
                    if selected_count >= large_target:
                        break
                    
                    temporal_books = select_temporal_books_from_series(df, series_name)
                    # Take up to books_per_large_series temporal positions
                    for i, (book_id, position) in enumerate(temporal_books[:books_per_large_series]):
                        if selected_count >= large_target:
                            break
                        
                        book = df[df['ID'] == str(book_id)].iloc[0]
                        selected_samples.append({
                            'ID': book_id,
                            'Title': book['Title'],
                            'Publisher': book['Publisher'],
                            'Series': book['Series'],
                            'Date': book['Date'],
                            'publisher_tier': tier,
                            'book_type': 'Series',
                            'series_size_category': book['series_size_category'],
                            'sampling_strategy': 'Temporal (Large Series)',
                            'temporal_position': position
                        })
                        selected_count += 1
            
            # --- Medium Series: Select temporal books ---
            if len(medium_series) > 0 and medium_target > 0:
                books_per_medium_series = max(1, medium_target // len(medium_series))
                
                selected_count = 0
                for series_name in medium_series:
                    if selected_count >= medium_target:
                        break
                    
                    temporal_books = select_temporal_books_from_series(df, series_name)
                    for i, (book_id, position) in enumerate(temporal_books[:books_per_medium_series]):
                        if selected_count >= medium_target:
                            break
                        
                        book = df[df['ID'] == str(book_id)].iloc[0]
                        selected_samples.append({
                            'ID': book_id,
                            'Title': book['Title'],
                            'Publisher': book['Publisher'],
                            'Series': book['Series'],
                            'Date': book['Date'],
                            'publisher_tier': tier,
                            'book_type': 'Series',
                            'series_size_category': book['series_size_category'],
                            'sampling_strategy': 'Temporal (Medium Series)',
                            'temporal_position': position
                        })
                        selected_count += 1
            
            # --- Small Series: Random sample ---
            if len(small_series) > 0 and small_target > 0:
                small_series_df = tier_df[
                    (tier_df['book_type'] == 'Series') & 
                    (tier_df['series_size_category'] == 'Small')
                ]
                if len(small_series_df) >= small_target:
                    small_sample = small_series_df.sample(n=small_target, random_state=random_seed)
                else:
                    small_sample = small_series_df
                
                for _, book in small_sample.iterrows():
                    selected_samples.append({
                        'ID': book['ID'],
                        'Title': book['Title'],
                        'Publisher': book['Publisher'],
                        'Series': book['Series'],
                        'Date': book['Date'],
                        'publisher_tier': tier,
                        'book_type': 'Series',
                        'series_size_category': book['series_size_category'],
                        'sampling_strategy': 'Random (Small Series)',
                        'temporal_position': 'N/A'
                    })
        
        # ============ STANDALONE BOOKS (RANDOM) ============
        standalone_df = tier_df[tier_df['book_type'] == 'Standalone'].copy()
        
        if len(standalone_df) > 0:
            print(f"  Standalone books available: {len(standalone_df)}")
            print(f"    Allocating {standalone_target} books (random sampling)")
            
            if len(standalone_df) >= standalone_target:
                standalone_sample = standalone_df.sample(n=standalone_target, random_state=random_seed)
            else:
                standalone_sample = standalone_df
            
            for _, book in standalone_sample.iterrows():
                selected_samples.append({
                    'ID': book['ID'],
                    'Title': book['Title'],
                    'Publisher': book['Publisher'],
                    'Series': book['Series'],
                    'Date': book['Date'],
                    'publisher_tier': tier,
                    'book_type': 'Standalone',
                    'series_size_category': 'N/A',
                    'sampling_strategy': 'Random (Standalone)',
                    'temporal_position': 'N/A'
                })
    
    # Remove duplicates (in case same ID selected multiple times)
    sample_df = pd.DataFrame(selected_samples)
    sample_df = sample_df.drop_duplicates(subset=['ID'])
    
    return sample_df


def main():
    """
    Main execution function.
    
    Usage: python create_stratified_sample.py <metadata_file> [output_file]
    """
    
    if len(sys.argv) < 2:
        print("Usage: python create_stratified_sample.py <metadata_tsv> [output_file]")
        print("Example: python create_stratified_sample.py Ebook_metadata.tsv sample_data.tsv")
        sys.exit(1)
    
    metadata_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'sample_data.tsv'
    
    # Check file exists
    if not os.path.exists(metadata_file):
        print(f"ERROR: File not found: {metadata_file}")
        sys.exit(1)
    
    print(f"Loading metadata from: {metadata_file}")
    
    # Load data
    df = pd.read_csv(metadata_file, sep='\t', dtype={'ID': str})
    
    print(f"Total books in dataset: {len(df)}")
    print(f"Columns: {list(df.columns)}\n")
    
    # Apply stratification
    df = define_publisher_tiers(df)
    df = define_series_type(df)
    df = define_series_size_category(df)
    
    # Create stratified sample with temporal coverage
    print("\n" + "="*70)
    print("CREATING STRATIFIED SAMPLE WITH TEMPORAL COVERAGE")
    print("="*70)
    
    sample_df = stratified_sample_with_temporal_coverage(
        df,
        target_sample_size=500,
        publisher_tier_dist={'A': 0.6, 'B': 0.25, 'C': 0.15},
        book_type_dist={'Series': 0.4, 'Standalone': 0.6},
        random_seed=42
    )
    
    # Sort by publisher tier, then by series, then by ID for easier inspection
    sample_df = sample_df.sort_values(['publisher_tier', 'book_type', 'Series', 'ID'])
    
    # Output statistics
    print("\n" + "="*70)
    print("SAMPLE STATISTICS")
    print("="*70)
    print(f"\nTotal books in sample: {len(sample_df)}")
    print(f"\nBy Publisher Tier:")
    print(sample_df['publisher_tier'].value_counts().sort_index())
    print(f"\nBy Book Type:")
    print(sample_df['book_type'].value_counts())
    print(f"\nBy Sampling Strategy:")
    print(sample_df['sampling_strategy'].value_counts())
    print(f"\nBy Series Size Category:")
    print(sample_df['series_size_category'].value_counts())
    
    # Calculate temporal coverage for series
    temporal_series = sample_df[sample_df['book_type'] == 'Series']
    if len(temporal_series) > 0:
        unique_series_in_sample = temporal_series['Series'].nunique()
        print(f"\nTemporal Coverage:")
        print(f"  Unique series represented: {unique_series_in_sample}")
        print(f"  Books from series: {len(temporal_series)}")
        print(f"  Average books per series: {len(temporal_series) / unique_series_in_sample:.2f}")
        print(f"\nTemporal Positions in Series:")
        print(temporal_series['temporal_position'].value_counts())
    
    # Save to TSV
    print(f"\nWriting sample to: {output_file}")
    sample_df.to_csv(output_file, sep='\t', index=False)
    
    print(f"\n✓ Sample created successfully!")
    print(f"  Total books selected: {len(sample_df)}")
    print(f"  Output file: {output_file}")


if __name__ == '__main__':
    main()
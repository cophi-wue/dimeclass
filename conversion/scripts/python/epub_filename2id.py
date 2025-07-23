import os
import csv
import pandas as pd
import shutil

def generate_metadata_csv(directory_path="~/code/repos/dimeclass/Heftromane/source"):
    """
    Scans a directory for EPUB files, generates unique IDs and creates a metadata CSV.

    Args:
        directory_path (str): The path to the directory containing the EPUB files.
                              Defaults to '~/code/repos/dimeclass/Heftromane/source'.
    """
    # Expand the user's home directory path
    directory_path = os.path.expanduser(directory_path)

    # Get the parent directory of 'source', which is 'Heftromane'
    heftromane_dir = os.path.dirname(directory_path)

    if not os.path.isdir(directory_path):
        print(f"Error: Directory not found at '{directory_path}'")
        return

    print(f"Scanning EPUBs in: {directory_path}")

    # List all files in the directory and filter for .epub files
    epub_files = [f for f in os.listdir(directory_path) if f.lower().endswith('.epub')]
    epub_files.sort() # Sort to ensure consistent ID assignment

    if not epub_files:
        print("No EPUB files found in the specified directory.")
        return

    metadata_rows = []
    # Header row for the CSV
    metadata_rows.append(["epub_file_name", "epub_ID"])

    # Start ID from 1, formatted as 6 digits with leading zeros
    current_id_number = 1

    for original_filename in epub_files:
        # Generate a unique 6-digit ID
        numerical_id = f"{current_id_number:06d}"
        # Get filename without .epub extension and replace spaces with underscores
        filename_without_ext = os.path.splitext(original_filename)[0]
        underscored_filename = filename_without_ext.replace(" ", "_")

        # Combine numerical ID and underscored filename for the new epub_ID
        epub_id = f"{numerical_id}_{underscored_filename}"

        # Add row to metadata
        metadata_rows.append([original_filename, epub_id])
        current_id_number += 1

    # Write metadata to a tab-separated CSV file
    metadata_filepath = os.path.join(heftromane_dir, "epub_metadata.csv") 
    try:
        with open(metadata_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter='\t')
            writer.writerows(metadata_rows)
        print(f"\nMetadata written to: {metadata_filepath}")
        print("Please review 'epub_metadata.csv' before proceeding with renaming.")
        print(f"To rename the files, run 'filename2id(directory_path=\"{directory_path}\")'")
    except IOError as e:
        print(f"Error writing metadata.csv: {e}")

def display_metadata_as_table(directory_path="~/code/repos/dimeclass/Heftromane/source", metadata_filename="epub_metadata.csv"):
    """
    Reads the metadata CSV file and displays its content as a formatted table
    using a pandas DataFrame.

    Args:
        directory_path (str): The path to the 'source' subfolder (used to derive the metadata path).
                              Defaults to '~/code/repos/dimeclass/Heftromane/source'.
        metadata_filename (str): The name of the metadata CSV file.
                                 Defaults to 'epub_metadata.csv'.
    """
    # Expand the user's home directory path
    directory_path = os.path.expanduser(directory_path)
    heftromane_dir = os.path.dirname(directory_path) 
    metadata_filepath = os.path.join(heftromane_dir, metadata_filename) 

    if not os.path.isfile(metadata_filepath):
        print(f"Error: Metadata file '{metadata_filepath}' not found. Please run 'generate_metadata_csv()' first.")
        return

    print(f"\nDisplaying metadata from: {metadata_filepath}")
    try:
        # Read the tab-separated CSV into a pandas DataFrame
        df = pd.read_csv(metadata_filepath, sep='\t')
        print(df.to_string(index=False))
    except Exception as e:
        print(f"Error reading or displaying metadata file: {e}")

def filename2id(directory_path="~/code/repos/dimeclass/Heftromane/source", metadata_filename="epub_metadata.csv"):
    """
    Copies EPUB files from 'source' to a new 'IDs' subfolder and renames them based on the
    information in a metadata CSV file, leaving the originals untouched.

    Args:
        directory_path (str): The path to the directory containing the original EPUB files (i.e., 'source').
                              Defaults to '~/code/repos/dimeclass/Heftromane/source'.
        metadata_filename (str): The name of the metadata CSV file.
                                 Defaults to 'epub_metadata.csv'.
    """
    # Expand the user's home directory path
    directory_path = os.path.expanduser(directory_path)

    # Get the parent directory of 'source', which is 'Heftromane'
    heftromane_dir = os.path.dirname(directory_path)
    metadata_filepath = os.path.join(heftromane_dir, metadata_filename) 
    id_folder_path = os.path.join(heftromane_dir, "IDs")

    if not os.path.isdir(directory_path):
        print(f"Error: Original directory not found at '{directory_path}'")
        return

    if not os.path.isfile(metadata_filepath):
        print(f"Error: Metadata file '{metadata_filepath}' not found. Please run 'generate_metadata_csv()' first.")
        return

    # Create the 'IDs' folder if it doesn't exist
    os.makedirs(id_folder_path, exist_ok=True)
    print(f"Ensured 'IDs' folder exists at: {id_folder_path}")

    print(f"Attempting to copy and rename EPUBs from '{directory_path}' to '{id_folder_path}' based on '{metadata_filename}'") # Updated print statement

    try:
        with open(metadata_filepath, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            header = next(reader) # Skip header row

            # Check if the header contains the expected columns
            if header[0] != "epub_file_name" or header[1] != "epub_ID":
                print(f"Error: Unexpected CSV header. Expected 'epub_file_name' and 'epub_ID', got {header}")
                return

            for row in reader:
                if len(row) < 2:
                    print(f"Warning: Skipping malformed row: {row}")
                    continue

                original_filename = row[0]
                epub_id = row[1]
                new_filename = f"{epub_id}.epub" # Construct new filename from ID

                original_filepath = os.path.join(directory_path, original_filename)
                new_filepath_in_id_folder = os.path.join(id_folder_path, new_filename)

                # Check if the original file exists before attempting to copy
                if not os.path.exists(original_filepath):
                    print(f"Warning: Original file '{original_filename}' not found in '{directory_path}'. Skipping copy and rename.") # Updated print statement
                    continue

                try:
                    # Copy the file to the new folder
                    shutil.copy2(original_filepath, new_filepath_in_id_folder)
                    print(f"Copied '{original_filename}' to '{new_filepath_in_id_folder}'")
                except OSError as e:
                    print(f"Error copying '{original_filename}' to '{new_filepath_in_id_folder}': {e}")

        print("\nEPUB copying and renaming process completed in the 'IDs' folder.")

    except IOError as e:
        print(f"Error reading metadata.csv: {e}")

def revert_epubsID2original_names(directory_path="~/code/repos/dimeclass/Heftromane/source", metadata_filename="epub_metadata.csv"):
    """
    Renames EPUB files in the 'IDs' subfolder from their ID-based names back to their
    original names based on the information in a metadata CSV file.

    Args:
        directory_path (str): The path to the 'source' subfolder (used to derive the Heftromane base path).
                              Defaults to '~/code/repos/dimeclass/Heftromane/source'.
        metadata_filename (str): The name of the metadata CSV file.
                                 Defaults to 'epub_metadata.csv'.
    """
    # Expand the user's home directory path
    directory_path = os.path.expanduser(directory_path)
    heftromane_dir = os.path.dirname(directory_path) 
    metadata_filepath = os.path.join(heftromane_dir, metadata_filename)
    id_folder_path = os.path.join(heftromane_dir, "IDs")

    if not os.path.isdir(id_folder_path):
        print(f"Error: 'IDs' directory not found at '{id_folder_path}'")
        return

    if not os.path.isfile(metadata_filepath):
        print(f"Error: Metadata file '{metadata_filepath}' not found. Please run 'generate_metadata_csv()' first.")
        return

    print(f"Attempting to rename EPUBs back to original names in: {id_folder_path} based on '{metadata_filename}'")

    try:
        with open(metadata_filepath, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            header = next(reader) # Skip header row

            # Check if the header contains the expected columns
            if header[0] != "epub_file_name" or header[1] != "epub_ID":
                print(f"Error: Unexpected CSV header. Expected 'epub_file_name' and 'epub_ID', got {header}")
                return

            for row in reader:
                if len(row) < 2:
                    print(f"Warning: Skipping malformed row: {row}")
                    continue

                original_filename = row[0]
                epub_id = row[1]
                current_filename_id_based = f"{epub_id}.epub" # Current name of the file in 'IDs' folder

                current_filepath_id_based = os.path.join(id_folder_path, current_filename_id_based)
                target_filepath_original_name = os.path.join(id_folder_path, original_filename)

                # Check if the ID-based file exists before attempting to rename back
                if not os.path.exists(current_filepath_id_based):
                    print(f"Warning: ID-based file '{current_filename_id_based}' not found in '{id_folder_path}'. Skipping rename to original name.")
                    continue

                # Check if the original filename already exists and is different from the current ID-based name
                if os.path.exists(target_filepath_original_name) and current_filepath_id_based != target_filepath_original_name:
                    print(f"Warning: Original filename '{original_filename}' already exists in '{id_folder_path}'. Skipping rename for '{current_filename_id_based}'.")
                    continue

                try:
                    os.rename(current_filepath_id_based, target_filepath_original_name)
                    print(f"Renamed '{current_filename_id_based}' back to '{original_filename}' in '{id_folder_path}'")
                except OSError as e:
                    print(f"Error renaming '{current_filename_id_based}' back to '{original_filename}': {e}")

        print("\nEPUB renaming back to original names completed in the 'IDs' folder.")

    except IOError as e:
        print(f"Error reading metadata.csv: {e}")

def rename_epubs_to_original_names_from_csv_old(directory_path="~/code/repos/dimeclass/Heftromane/source", metadata_filename="epub_metadata.csv"):
    """
    Renames EPUB files in a directory from their ID-based names back to their original names
    based on the information in a metadata CSV file.

    Args:
        directory_path (str): The path to the directory containing the EPUB files
                              and the metadata CSV. Defaults to '~/data/Heftromane_copy'.
        metadata_filename (str): The name of the metadata CSV file.
                                 Defaults to 'metadata.csv'.
    """
    # Expand the user's home directory path
    directory_path = os.path.expanduser(directory_path)
    metadata_filepath = os.path.join(directory_path, metadata_filename)

    if not os.path.isdir(directory_path):
        print(f"Error: Directory not found at '{directory_path}'")
        return

    if not os.path.isfile(metadata_filepath):
        print(f"Error: Metadata file '{metadata_filepath}' not found. Please run 'generate_metadata_csv()' first.")
        return

    print(f"Attempting to rename EPUBs back to original names in: {directory_path} based on '{metadata_filename}'")

    try:
        with open(metadata_filepath, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            header = next(reader) # Skip header row

            # Check if the header contains the expected columns
            if header[0] != "epub_file_name" or header[1] != "epub_ID":
                print(f"Error: Unexpected CSV header. Expected 'epub_file_name' and 'epub_ID', got {header}")
                return

            for row in reader:
                if len(row) < 2:
                    print(f"Warning: Skipping malformed row: {row}")
                    continue

                original_filename = row[0]
                epub_id = row[1]
                current_filename_id_based = f"{epub_id}.epub" # Current name of the file

                current_filepath_id_based = os.path.join(directory_path, current_filename_id_based)
                target_filepath_original_name = os.path.join(directory_path, original_filename)

                # Check if the ID-based file exists before attempting to rename back
                if not os.path.exists(current_filepath_id_based):
                    print(f"Warning: ID-based file '{current_filename_id_based}' not found. Skipping rename to original name.")
                    continue

                # Check if the original filename already exists and is different from the current ID-based name
                if os.path.exists(target_filepath_original_name) and current_filepath_id_based != target_filepath_original_name:
                    print(f"Warning: Original filename '{original_filename}' already exists. Skipping rename for '{current_filename_id_based}'.")
                    continue

                try:
                    os.rename(current_filepath_id_based, target_filepath_original_name)
                    print(f"Renamed '{current_filename_id_based}' back to '{original_filename}'")
                except OSError as e:
                    print(f"Error renaming '{current_filename_id_based}' back to '{original_filename}': {e}")

        print("\nEPUB renaming back to original names completed.")

    except IOError as e:
        print(f"Error reading metadata.csv: {e}")

###----------------------------------------###
# workflow: first run genreate metadata (check if it was correctly created) and then run filename2id(). optional: dispaly as table. to rename back to filenames run revert_epubsID2original_names()

generate_metadata_csv()
display_metadata_as_table()
filename2id()
#revert_epubsID2original_names() #renames files if they have been turned into IDs in a separate (IDs) folder


#old
#rename_epubs_to_original_names_from_csv_old() #renames files if they have been turned into IDs in same folder

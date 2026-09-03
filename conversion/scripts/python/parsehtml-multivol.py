import json
from bs4 import BeautifulSoup
import os

def create_structured_html_multivolume(input_json_path):
    """
    Reads a JSON file that may contain multiple nested ebooks,
    extracts specific fields, and saves separate HTML files for each book
    plus a main info document.
    """
    if not os.path.exists(input_json_path):
        print(f"Error: The file '{input_json_path}' was not found.")
        return

    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            ebook_data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{input_json_path}'.")
        return

    if 'content' not in ebook_data:
        print("Error: The 'content' key was not found in the JSON file.")
        return

    # Get the book title for the output directory
    book_title = ebook_data.get('title', 'untitled_collection')
    safe_book_title = "".join(c for c in book_title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    output_dir = f"{safe_book_title}_structured_html"

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    print(f"Processing '{book_title}' and creating structured HTML files...")

    # Create main info document with non-Section content
    main_content = []
    books = []

    # Separate main content from book sections
    for item in ebook_data['content']:
        if item.get('type') == 'Section':
            books.append(item)
        else:
            main_content.append(item)

    # Create main info document
    if main_content:
        create_single_html_file(main_content, os.path.join(output_dir, "00_main_info.html"), "Main Information")

    # Process each book section
    book_counter = 1
    for book in books:
        book_title_safe = book.get('title', f'Book_{book_counter}')
        book_title_safe = "".join(c for c in book_title_safe if c.isalnum() or c in (' ', '_', '-')).rstrip()

        if 'content' in book:
            filename = f"{book_counter:02d}_{book_title_safe}.html"
            filepath = os.path.join(output_dir, filename)
            create_single_html_file(book['content'], filepath, book.get('title', f'Book {book_counter}'))
            book_counter += 1

def create_single_html_file(content_list, output_path, document_title):
    """
    Creates a single HTML file from a list of content items.
    Handles nested Section structures recursively.
    """
    html_output = f"""<!DOCTYPE html>
<html>
<head>
    <title>{document_title}</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>{document_title}</h1>
"""

    # Process content recursively
    html_output += process_content_recursive(content_list, level=1)

    html_output += """
</body>
</html>
"""

    # Write the complete HTML string to the output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_output)

    print(f"Created: {output_path}")

def process_content_recursive(content_list, level=1):
    """
    Recursively processes content items, handling nested Sections.
    """
    html_output = ""

    for i, section in enumerate(content_list):
        # Handle nested Sections
        if section.get('type') == 'Section':
            section_title = section.get('title', f"Section {i+1}")
            section_type = section.get('inferred-type', 'section')

            # Add section header
            header_level = min(level + 1, 6)  # HTML only supports h1-h6
            html_output += f"""


"""

            # Recursively process nested content
            if 'content' in section:
                html_output += process_content_recursive(section['content'], level + 1)

            html_output += "    </div>\n"

        else:
            # Handle regular content items (EpubHtml, etc.)
            html_content = section.get('text')
            section_title = section.get('title', f"Item {i+1}")
            section_type = section.get('inferred-type', 'unknown')

            # Add a clear header for each section
            html_output += f"""
    <div class="{section_type}">

"""

            if html_content:
                try:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    structured_html = soup.prettify()
                    html_output += f"        {structured_html}"
                except Exception as e:
                    print(f"Warning: Could not parse HTML content for '{section_title}': {e}")
                    html_output += f"        <p>Could not parse HTML content for this section.</p>"
            else:
                html_output += "        <p>No HTML text found for this section.</p>"

            html_output += "    </div>\n"

    return html_output

def create_single_structured_html(input_json_path):
    """
    Main function that handles both single and multi-volume ebooks.
    For backward compatibility with the original function name.
    """
    if not os.path.exists(input_json_path):
        print(f"Error: The file '{input_json_path}' was not found.")
        return

    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            ebook_data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{input_json_path}'.")
        return

    if 'content' not in ebook_data:
        print("Error: The 'content' key was not found in the JSON file.")
        return

    # Check if this is a multi-volume ebook (contains Section types)
    has_sections = any(item.get('type') == 'Section' for item in ebook_data['content'])

    if has_sections:
        # Use new multi-volume processing
        create_structured_html_multivolume(input_json_path)
    else:
        # Use original single-file processing
        book_title = ebook_data.get('title', 'untitled_book')
        safe_book_title = "".join(c for c in book_title if c.isalnum() or c in (' ',)).rstrip()
        output_filename = f"{safe_book_title}_structured_clean.html"

        html_output = f"""<!DOCTYPE html>
<html>
<head>
    <title>{book_title}</title>
    <meta charset="utf-8">
</head>
<body>

"""

        print(f"Parsing '{book_title}' and combining into a single, structured HTML file...")

        # Iterate through each section and append the formatted HTML
        for i, section in enumerate(ebook_data['content']):
            html_content = section.get('text')
            section_title = section.get('title', f"Section {i+1}")
            section_type = section.get('inferred-type', 'N/A')

            # Add a clear header for each section
            html_output += f"""
    <div class="{section_type}">

"""

            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                structured_html = soup.prettify()
                html_output += f"{structured_html}"
            else:
                html_output += "<p>No HTML text found for this section.</p>"

            html_output += "</div>\n"

        html_output += """
</body>
</html>
"""

        # Write the complete HTML string to the single output file
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(html_output)

        print(f"\nSuccessfully created single structured HTML file: {output_filename}")

# Example usage
if __name__ == "__main__":
    # Replace with your actual JSON file path
    json_file_path = '/home/spielberg/code/repos/dimeclass/conversion/data/json/Gordon_Die-schoensten-Liebesromane-der_9783733729660.json'

    create_single_structured_html(json_file_path)
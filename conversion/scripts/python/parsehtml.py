import json
from bs4 import BeautifulSoup
import os

def create_single_structured_html(input_json_path):
    """
    Reads a JSON file, extracts specific fields, and saves a single
    HTML file with section headers and the original HTML content.
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

    # Get the book title for the output filename
    book_title = ebook_data.get('title', 'untitled_book')
    safe_book_title = "".join(c for c in book_title if c.isalnum() or c in (' ',)).rstrip()
    output_filename = f"{safe_book_title}_structured_clean.html"

    # Start building the complete HTML string
    html_output = f"""<!DOCTYPE html>
<html>

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
    <div class={section_type}>
        <p class="title">{section_title}</p>
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

# Example usage with your provided file path.
#json_file_path = '/home/spielberg/code/repos/dimeclass/conversion/data/json/G. F. Unger Sonder-Edition - Folge 003_ Texas-Marshal (German Edition).json'
json_file_path ='/home/spielberg/code/repos/dimeclass/conversion/data/json/Slade_Lassiter-Sammelband-1793---Wes_9783732562299.json'

create_single_structured_html(json_file_path)
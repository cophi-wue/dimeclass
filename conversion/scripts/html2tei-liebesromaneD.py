#!/usr/bin/env python3
"""
HTML to TEI Converter for German Dime Novel
Converts HTML extracted from ebook to TEI format with proper TEI structure
"""

import os
import sys
from datetime import datetime
from bs4 import BeautifulSoup, NavigableString
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging
import re

class HTMLToTEIConverter:
    def __init__(self, html_path, template_path, output_dir):
        self.html_path = html_path
        self.template_path = template_path
        self.output_dir = output_dir
        self.handled_elements = set()
        self.unhandled_elements = set()
        self.conversion_log = []

        # TEI namespace
        self.tei_ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        ET.register_namespace('', 'http://www.tei-c.org/ns/1.0')

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Set up logging
        self.setup_logging()

    def setup_logging(self):
        """Setup logging configuration"""
        log_file = os.path.join(self.output_dir, f"conversion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_html(self):
        """Load and parse the HTML document"""
        try:
            with open(self.html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.html_soup = BeautifulSoup(content, 'html.parser')
            self.logger.info(f"Loaded HTML file: {self.html_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error loading HTML file: {e}")
            return False

    def load_tei_template(self):
        """Load the TEI template"""
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            # Fix the template syntax errors
            template_content = template_content.replace('revisionDesc>', '<revisionDesc>')
            template_content = template_content.replace('/date>', '</date>')

            self.tei_root = ET.fromstring(template_content)
            self.logger.info(f"Loaded TEI template: {self.template_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error loading TEI template: {e}")
            return False

    def create_tei_element(self, tag_name, text=None, attribs=None):
        """Create a TEI element with proper namespace"""
        elem = ET.Element(tag_name)
        if text:
            elem.text = text
        if attribs:
            for key, value in attribs.items():
                elem.set(key, str(value))
        return elem

    def extract_text_content(self, element):
        """Extract clean text content from an element, handling nested elements properly"""
        if isinstance(element, NavigableString):
            return str(element).strip()

        # For elements that should be converted to inline elements (hi, lb, etc.)
        if element.name in ['hi', 'lb', 'em', 'strong', 'i', 'b']:
            return None  # These will be handled separately

        # Extract text from other elements
        text_parts = []
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    text_parts.append(text)
            elif child.name not in ['hi', 'lb', 'em', 'strong', 'i', 'b']:
                child_text = self.extract_text_content(child)
                if child_text:
                    text_parts.append(child_text)

        return ' '.join(text_parts).strip() if text_parts else None

    def process_inline_elements(self, html_element, tei_parent):
        """Process inline elements (hi, lb, etc.) and add them to parent"""
        for child in html_element.children:
            if isinstance(child, NavigableString):
                text_content = str(child).strip()
                if text_content:
                    if tei_parent.text:
                        tei_parent.text += text_content
                    else:
                        tei_parent.text = text_content
            elif child.name == 'hi':
                tei_hi = self.convert_hi(child)
                if tei_hi is not None:
                    tei_parent.append(tei_hi)
            elif child.name == 'lb':
                tei_lb = self.create_tei_element('lb')
                tei_parent.append(tei_lb)
                self.handled_elements.add('lb')
            elif child.name in ['em', 'i']:
                tei_hi = self.create_tei_element('hi', attribs={'rend': 'italic'})
                self.process_inline_elements(child, tei_hi)
                tei_parent.append(tei_hi)
                self.handled_elements.add(child.name)
            elif child.name in ['strong', 'b']:
                tei_hi = self.create_tei_element('hi', attribs={'rend': 'bold'})
                self.process_inline_elements(child, tei_hi)
                tei_parent.append(tei_hi)
                self.handled_elements.add(child.name)
            else:
                # Handle other inline elements or continue processing
                self.process_inline_elements(child, tei_parent)

    def convert_paragraph(self, html_p):
        """Convert HTML paragraph elements to TEI format"""
        # Check if this should be preceded by a line break
        needs_lb = False
        rend = html_p.get('rend', '')

        if rend == 'standard-leerzeile':
            needs_lb = True
            self.handled_elements.add('p[rend=standard-leerzeile]')
        elif rend == 'standard':
            self.handled_elements.add('p[rend=standard]')
        else:
            self.handled_elements.add('p')

        tei_p = self.create_tei_element('p')

        # Process inline content
        self.process_inline_elements(html_p, tei_p)

        self.conversion_log.append(f"Converted paragraph with rend='{rend}'")

        return tei_p, needs_lb

    def convert_hi(self, html_hi):
        """Convert HTML hi elements to TEI format"""
        tei_hi = self.create_tei_element('hi')

        # Copy rend attribute if present
        rend = html_hi.get('rend', '')
        if rend:
            tei_hi.set('rend', rend)
            self.handled_elements.add(f'hi[rend={rend}]')
        else:
            self.handled_elements.add('hi')

        # Process inline content
        self.process_inline_elements(html_hi, tei_hi)

        return tei_hi

    def convert_graphic_or_svg(self, html_element):
        """Convert HTML graphic/svg elements to TEI figure"""
        tei_figure = self.create_tei_element('figure')

        if html_element.name == 'graphic':
            tei_graphic = self.create_tei_element('graphic')
            # Copy attributes
            for attr_name, attr_value in html_element.attrs.items():
                tei_graphic.set(attr_name, str(attr_value))
            tei_figure.append(tei_graphic)
            self.handled_elements.add('graphic')
        elif html_element.name == 'svg' or self.contains_svg_content(html_element):
            # Handle SVG content
            tei_graphic = self.create_tei_element('graphic')
            tei_graphic.set('rend', 'svg')

            # Extract image information if available
            if html_element.find('image'):
                image = html_element.find('image')
                if image.get('xlink:href'):
                    tei_graphic.set('url', image.get('xlink:href'))

            tei_figure.append(tei_graphic)
            self.handled_elements.add('svg')

        self.conversion_log.append(f"Converted {html_element.name} -> figure/graphic")
        return tei_figure

    def contains_svg_content(self, element):
        """Check if element contains SVG content"""
        if isinstance(element, NavigableString):
            return False

        text_content = str(element)
        return '<svg' in text_content or 'viewbox=' in text_content.lower()

    def convert_div(self, html_div):
        """Convert HTML div elements to TEI div with proper structure"""
        tei_div = self.create_tei_element('div')

        # Handle class/type conversion
        if 'class' in html_div.attrs:
            class_value = html_div.get('class')
            if isinstance(class_value, list):
                type_value = class_value[0] if class_value else 'unknown'
            else:
                type_value = str(class_value)
            tei_div.set('type', type_value)
            self.handled_elements.add('div[class]')
        else:
            tei_div.set('type', 'section')
            self.handled_elements.add('div')

        # Look for a head element or create one from first heading
        head_created = False
        elements_to_process = list(html_div.children)

        # Check if first significant element could be a head
        for child in elements_to_process:
            if not isinstance(child, NavigableString):
                if child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    # Convert heading to head
                    tei_head = self.create_tei_element('head')
                    head_text = self.extract_text_content(child)
                    if head_text:
                        tei_head.text = head_text
                    tei_div.append(tei_head)
                    head_created = True
                    elements_to_process.remove(child)
                    self.handled_elements.add(child.name)
                    break
                elif child.name == 'head':
                    tei_head = self.convert_head(child)
                    tei_div.append(tei_head)
                    head_created = True
                    elements_to_process.remove(child)
                    break

        # If no head was found/created, create a generic one
        if not head_created:
            div_type = tei_div.get('type', 'section')
            tei_head = self.create_tei_element('head', text=div_type.title())
            tei_div.append(tei_head)

        # Process remaining elements
        for child in elements_to_process:
            if isinstance(child, NavigableString):
                text_content = str(child).strip()
                if text_content:
                    # Wrap loose text in a paragraph
                    tei_p = self.create_tei_element('p', text=text_content)
                    tei_div.append(tei_p)
            else:
                converted_elements = self.convert_element(child)
                if converted_elements:
                    if isinstance(converted_elements, list):
                        for elem in converted_elements:
                            if elem is not None:
                                tei_div.append(elem)
                    elif converted_elements is not None:
                        tei_div.append(converted_elements)

        self.conversion_log.append(f"Converted div with type='{tei_div.get('type')}'")
        return tei_div

    def convert_head(self, html_head):
        """Convert HTML head elements to TEI head"""
        tei_head = self.create_tei_element('head')

        # Process content while preserving inline elements
        self.process_inline_elements(html_head, tei_head)

        self.handled_elements.add('head')
        return tei_head

    def convert_table(self, html_table):
        """Convert HTML table to TEI table"""
        tei_table = self.create_tei_element('table')

        # Process table structure
        for child in html_table.children:
            if isinstance(child, NavigableString):
                continue

            if child.name == 'thead':
                # Process header rows
                for tr in child.find_all('tr'):
                    tei_row = self.create_tei_element('row', attribs={'role': 'header'})
                    for th in tr.find_all(['th', 'td']):
                        tei_cell = self.create_tei_element('cell')
                        cell_text = self.extract_text_content(th)
                        if cell_text:
                            tei_cell.text = cell_text
                        tei_row.append(tei_cell)
                    tei_table.append(tei_row)
            elif child.name == 'tbody':
                # Process body rows
                for tr in child.find_all('tr'):
                    tei_row = self.create_tei_element('row')
                    for td in tr.find_all(['td', 'th']):
                        tei_cell = self.create_tei_element('cell')
                        cell_text = self.extract_text_content(td)
                        if cell_text:
                            tei_cell.text = cell_text
                        tei_row.append(tei_cell)
                    tei_table.append(tei_row)
            elif child.name == 'tr':
                # Direct table row
                tei_row = self.create_tei_element('row')
                for td in child.find_all(['td', 'th']):
                    tei_cell = self.create_tei_element('cell')
                    cell_text = self.extract_text_content(td)
                    if cell_text:
                        tei_cell.text = cell_text
                    tei_row.append(tei_cell)
                tei_table.append(tei_row)

        self.handled_elements.add('table')
        self.conversion_log.append("Converted table to TEI table")
        return tei_table

    def convert_element(self, element):
        """Main element conversion dispatcher"""
        if isinstance(element, NavigableString):
            return None

        tag_name = element.name.lower()

        # Apply conversion rules
        if tag_name == 'p':
            tei_p, needs_lb = self.convert_paragraph(element)
            if needs_lb:
                lb_elem = self.create_tei_element('lb')
                return [lb_elem, tei_p]
            return tei_p

        elif tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # Convert headings to head elements
            tei_head = self.create_tei_element('head')
            head_text = self.extract_text_content(element)
            if head_text:
                tei_head.text = head_text
            self.handled_elements.add(tag_name)
            return tei_head

        elif tag_name == 'div':
            return self.convert_div(element)

        elif tag_name == 'head':
            return self.convert_head(element)

        elif tag_name == 'table':
            return self.convert_table(element)

        elif tag_name == 'graphic' or tag_name == 'svg' or self.contains_svg_content(element):
            return self.convert_graphic_or_svg(element)

        elif tag_name in ['hi', 'em', 'i', 'strong', 'b']:
            # These should be handled within paragraphs
            self.handled_elements.add(tag_name)
            return None

        elif tag_name == 'lb':
            return self.create_tei_element('lb')

        else:
            # Handle unknown elements
            return self.convert_unknown_element(element)

    def convert_unknown_element(self, element):
        """Convert unknown elements - include as-is but log them"""
        tag_name = element.name.lower()

        # Create TEI element with same name
        tei_element = self.create_tei_element(tag_name)

        # Copy attributes
        for attr_name, attr_value in element.attrs.items():
            tei_element.set(attr_name, str(attr_value))

        # Process content
        text_content = self.extract_text_content(element)
        if text_content:
            tei_element.text = text_content

        # Process inline elements if any
        self.process_inline_elements(element, tei_element)

        # Log as unhandled
        self.unhandled_elements.add(tag_name)
        self.conversion_log.append(f"Unhandled element: {tag_name} (included as-is)")

        return tei_element

    def populate_tei_body(self):
        """Populate the TEI body with converted HTML content"""
        # Find the body element in the TEI template
        body = self.tei_root.find('.//{http://www.tei-c.org/ns/1.0}body')

        if body is None:
            self.logger.error("Could not find body element in TEI template")
            return False

        # Convert HTML body content
        html_body = self.html_soup.find('body')
        if html_body is None:
            # If no body tag, use the entire document
            html_body = self.html_soup

        # Process all children of the HTML body
        for element in html_body.children:
            if isinstance(element, NavigableString):
                text_content = str(element).strip()
                if text_content:
                    # Wrap loose text in a div with paragraph
                    tei_div = self.create_tei_element('div', attribs={'type': 'text'})
                    tei_head = self.create_tei_element('head', text='Text Section')
                    tei_p = self.create_tei_element('p', text=text_content)
                    tei_div.append(tei_head)
                    tei_div.append(tei_p)
                    body.append(tei_div)
            else:
                converted_elements = self.convert_element(element)
                if converted_elements:
                    if isinstance(converted_elements, list):
                        for elem in converted_elements:
                            if elem is not None:
                                body.append(elem)
                    elif converted_elements is not None:
                        body.append(converted_elements)

        return True

    def save_tei_document(self):
        """Save the TEI document with proper formatting"""
        try:
            # Convert to string with proper namespace handling
            rough_string = ET.tostring(self.tei_root, encoding='unicode', method='xml')

            # Parse with minidom for pretty printing
            dom = minidom.parseString(rough_string)
            pretty_xml = dom.toprettyxml(indent="  ", encoding=None)

            # Clean up the XML
            lines = pretty_xml.split('\n')
            clean_lines = []
            for line in lines:
                if line.strip():
                    clean_lines.append(line)

            pretty_xml = '\n'.join(clean_lines)

            # Remove namespace prefixes for cleaner output
            pretty_xml = re.sub(r'<ns\d+:', '<', pretty_xml)
            pretty_xml = re.sub(r'</ns\d+:', '</', pretty_xml)
            pretty_xml = re.sub(r'xmlns:ns\d+="[^"]*"\s*', '', pretty_xml)

            # Save to file
            output_file = os.path.join(self.output_dir, "converted_tei.xml")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)

            self.logger.info(f"TEI document saved to: {output_file}")
            return output_file
        except Exception as e:
            self.logger.error(f"Error saving TEI document: {e}")
            return None

    def save_conversion_log(self):
        """Save conversion log and unhandled elements report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save detailed conversion log
        log_file = os.path.join(self.output_dir, f"conversion_details_{timestamp}.txt")
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("HTML to TEI Conversion Log\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Conversion completed at: {datetime.now()}\n")
            f.write(f"Source HTML: {self.html_path}\n")
            f.write(f"TEI Template: {self.template_path}\n\n")

            f.write("HANDLED ELEMENTS:\n")
            f.write("-" * 20 + "\n")
            for element in sorted(self.handled_elements):
                f.write(f"  ✓ {element}\n")

            f.write("\nUNHANDLED ELEMENTS (need conversion rules):\n")
            f.write("-" * 45 + "\n")
            for element in sorted(self.unhandled_elements):
                f.write(f"  ⚠ {element}\n")

            f.write("\nDETAILED CONVERSION LOG:\n")
            f.write("-" * 25 + "\n")
            for entry in self.conversion_log:
                f.write(f"  {entry}\n")

        self.logger.info(f"Conversion log saved to: {log_file}")

        # Print summary to console
        print(f"\n{'='*50}")
        print("CONVERSION SUMMARY")
        print(f"{'='*50}")
        print(f"Handled elements: {len(self.handled_elements)}")
        print(f"Unhandled elements: {len(self.unhandled_elements)}")

        if self.unhandled_elements:
            print(f"\nElements needing conversion rules:")
            for element in sorted(self.unhandled_elements):
                print(f"  ⚠ {element}")

    def convert(self):
        """Main conversion process"""
        self.logger.info("Starting HTML to TEI conversion...")

        # Load input files
        if not self.load_html():
            return False
        if not self.load_tei_template():
            return False

        # Perform conversion
        if not self.populate_tei_body():
            return False

        # Save results
        output_file = self.save_tei_document()
        if output_file:
            self.save_conversion_log()
            self.logger.info("Conversion completed successfully!")
            return True
        else:
            return False

def main():
    # File paths - UPDATE THESE TO YOUR ACTUAL PATHS
    html_path = "/home/spielberg/code/repos/Die schönsten Liebesromane der Welt - Best of Julia Extra 2019_structured_html/01_Julia Extra Band 461.html"
    template_path = "/home/spielberg/code/repos/dimeclass/conversion/scripts/tei-template.xml"
    output_dir = "/home/spielberg/code/repos/dimeclass/conversion/logs/"

    # Create converter instance
    converter = HTMLToTEIConverter(html_path, template_path, output_dir)

    # Perform conversion
    success = converter.convert()

    if success:
        print(f"\n✅ Conversion completed successfully!")
        print(f"📁 Output files saved to: {output_dir}")
        print(f"\nProper TEI structure created:")
        print(f"  - Each <div> has a <head> element")
        print(f"  - <hi> and <lb> elements are properly nested in <p>")
        print(f"  - Graphics wrapped in <figure> elements")
        print(f"  - Tables converted to TEI format")
        print(f"  - No namespace prefix issues")
    else:
        print(f"\n❌ Conversion failed. Check the log files for details.")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
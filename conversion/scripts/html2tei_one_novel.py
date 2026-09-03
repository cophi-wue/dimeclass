import lxml.html
from lxml import etree
import os
import logging
from datetime import datetime

def setup_logging(output_dir):
    """Set up simple logging."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(output_dir, f"conversion_{timestamp}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def convert_html_to_tei(html_file, tei_template_file, output_dir):
    """Simple HTML to TEI conversion with logging."""

    logger = setup_logging(output_dir)
    logger.info(f"Converting: {html_file}")

    # Track which elements we handle vs don't handle
    handled_elements = set()
    unhandled_elements = []

    try:
        # Load files
        html_doc = lxml.html.parse(html_file)
        tei_doc = etree.parse(tei_template_file)

        # Find TEI body
        tei_body = tei_doc.find('.//{http://www.tei-c.org/ns/1.0}body')
        if tei_body is None:
            logger.error("No <body> found in TEI template")
            return

        # Process each div in HTML
        for div in html_doc.xpath('//div'):
            div_class = div.get('class', 'unknown')

            # Create TEI div
            tei_div = etree.Element('{http://www.tei-c.org/ns/1.0}div')
            tei_div.set('type', div_class)

            # Process each child element in the div
            for child in div:
                tag = child.tag

                # Our conversion rules
                if tag == 'p' and child.get('class') == 'title':
                    # Title paragraph becomes head
                    head = etree.Element('{http://www.tei-c.org/ns/1.0}head')
                    head.text = child.text_content().strip() if child.text_content() else ''
                    tei_div.append(head)
                    handled_elements.add(f"{tag}[@class='title']")

                elif tag == 'p':
                    # Regular paragraph
                    p = etree.Element('{http://www.tei-c.org/ns/1.0}p')

                    # Handle text and nested elements
                    if len(child) == 0:
                        # Simple text paragraph
                        p.text = child.text_content().strip() if child.text_content() else ''
                    else:
                        # Paragraph with nested elements
                        p.text = child.text or ''
                        for nested in child:
                            if nested.tag == 'hi' and nested.get('rend') == 'class1752':
                                # Italic text
                                hi = etree.Element('{http://www.tei-c.org/ns/1.0}hi')
                                hi.set('rend', 'italic')
                                hi.text = nested.text or ''
                                hi.tail = nested.tail or ''
                                p.append(hi)
                            else:
                                # Unknown nested element - keep as is but log
                                unhandled_elements.append(f"nested {nested.tag} in paragraph")
                                # Copy the element
                                new_elem = etree.Element(nested.tag)
                                for attr, value in nested.attrib.items():
                                    new_elem.set(attr, value)
                                new_elem.text = nested.text or ''
                                new_elem.tail = nested.tail or ''
                                p.append(new_elem)

                    tei_div.append(p)
                    handled_elements.add('p')

                elif tag == 'hi' and child.get('rend') == 'class-0':
                    # Hi element as paragraph
                    p = etree.Element('{http://www.tei-c.org/ns/1.0}p')
                    p.text = child.text_content().strip() if child.text_content() else ''
                    tei_div.append(p)
                    handled_elements.add("hi[@rend='class-0']")

                elif tag == 'graphic':
                    # Graphics
                    graphic = etree.Element('graphic')
                    for attr, value in child.attrib.items():
                        graphic.set(attr, value)
                    tei_div.append(graphic)
                    handled_elements.add('graphic')

                elif tag == 'lb':
                    # Line breaks
                    lb = etree.Element('lb')
                    for attr, value in child.attrib.items():
                        lb.set(attr, value)
                    tei_div.append(lb)
                    handled_elements.add('lb')

                else:
                    # Unhandled element - include it but log it
                    unhandled_elements.append(f"{tag} (class: {child.get('class', 'none')})")

                    # Copy the element as-is
                    new_elem = etree.Element(tag)
                    for attr, value in child.attrib.items():
                        new_elem.set(attr, value)
                    new_elem.text = child.text_content().strip() if child.text_content() else ''
                    tei_div.append(new_elem)

            # Add div to body if it has content
            if len(tei_div) > 0:
                tei_body.append(tei_div)

        # Write output
        html_basename = os.path.splitext(os.path.basename(html_file))[0]
        output_file = os.path.join(output_dir, f"{html_basename}_tei.xml")

        # Pretty print and save
        etree.indent(tei_doc, space="  ")
        tei_doc.write(output_file, pretty_print=True, xml_declaration=True, encoding='utf-8')

        # Log results
        logger.info(f"Output saved to: {output_file}")
        logger.info(f"Handled elements: {sorted(handled_elements)}")

        if unhandled_elements:
            logger.info("UNHANDLED ELEMENTS (included in output but need rules):")
            for elem in sorted(set(unhandled_elements)):
                logger.info(f"  - {elem}")
        else:
            logger.info("All elements were handled by conversion rules!")

        return output_file

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

def main():
    """Main function."""
    # Your specified paths
    tei_template_path = "/home/spielberg/code/repos/dimeclass/conversion/scripts/tei-template.xml"
    output_path = "/home/spielberg/code/repos/dimeclass/conversion/logs/"

    html_file = input("Enter HTML file path: ")

    if not os.path.exists(html_file):
        print(f"HTML file not found: {html_file}")
        return

    if not os.path.exists(tei_template_path):
        print(f"TEI template not found: {tei_template_path}")
        return

    try:
        output_file = convert_html_to_tei(html_file, tei_template_path, output_path)
        print(f"Success! Check: {output_file}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()
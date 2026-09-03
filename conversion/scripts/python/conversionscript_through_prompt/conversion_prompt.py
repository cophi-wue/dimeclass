#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dieses Skript konvertiert eine spezielle JSON-Datei (gemäß dem Beispiel von
'G. F. Unger Sonder-Edition') in ein vollständiges TEI-XML-Dokument.

Es generiert einen <teiHeader>, <text>, <front> und <body> basierend auf
den Metadaten und der 'content'-Liste in der JSON-Datei.

Regeln:
- Es wird ein vollständiges TEI-Dokument erstellt.
- Metadaten aus dem JSON-Root und 'epub_metadata' füllen den <teiHeader>.
- Inhalte aus 'content' werden in <front> oder <body> geroutet.
- 'inferred-type: chapter' geht in <body>.
- 'inferred-type: toc, imprint, unkown' etc. gehen in <front>.
- Bei Kapiteln wird der erste <p>-Tag aus dem HTML als <head> extrahiert.
- Bei <front>-Elementen wird der JSON-'title' als <head> verwendet.
- Top-Level <hi>-Tags im HTML werden in ein neues <p>-Tag eingeschlossen.
- Das 'toc' (Inhaltsverzeichnis) wird speziell als <list><item>... formatiert.
- <graphic> wird zu <figure><graphic>.

Abhängigkeiten:
- beautifulsoup4 (pip install beautifulsoup4)
- lxml (pip install lxml)
"""

import json
import sys
import os
from lxml import etree
from bs4 import BeautifulSoup, element

# Set zur Verfolgung nicht zugeordneter HTML-Tags
unmapped_tags = set()

# TEI-Namespace
TEI_NS = "http://www.tei-c.org/ns/1.0"
NSMAP = {None: TEI_NS}


def load_json_file(filepath):
    """
    Lädt die JSON-Datei vom angegebenen Pfad.
    Erwartet, dass die JSON-Datei ein einzelnes Objekt (dict) ist.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                print(f"Fehler: Die JSON-Struktur in {filepath} ist kein einzelnes Objekt (dict).", file=sys.stderr)
                sys.exit(1)
            return data
    except FileNotFoundError:
        print(f"Fehler: JSON-Datei nicht gefunden unter {filepath}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Fehler: Ungültiges JSON-Format in {filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}", file=sys.stderr)
        sys.exit(1)


def create_tei_header(json_data, tei_header):
    """
    Füllt den <teiHeader> mit Metadaten aus dem JSON-Objekt.
    """
    metadata = json_data.get('epub_metadata', {})

    file_desc = etree.SubElement(tei_header, "fileDesc")

    # --- titleStmt ---
    title_stmt = etree.SubElement(file_desc, "titleStmt")
    title_el = etree.SubElement(title_stmt, "title")
    title_el.text = json_data.get('title')

    # --- author ---
    creators = metadata.get('creator', [])
    if creators and isinstance(creators[0], str):
        author_el = etree.SubElement(title_stmt, "author")
        pers_name = etree.SubElement(author_el, "persName")
        pers_name.text = creators[0]

    # --- publicationStmt ---
    pub_stmt = etree.SubElement(file_desc, "publicationStmt")
    pub_el = etree.SubElement(pub_stmt, "publisher")
    pub_el.text = metadata.get('publisher')

    dates = metadata.get('date', [])
    if dates and isinstance(dates[0], str):
        date_el = etree.SubElement(pub_stmt, "date")
        date_el.set("when", dates[0])

    # --- identifiers ---
    identifiers = metadata.get('identifier', [])
    for ident in identifiers:
        if isinstance(ident, str) and ident.startswith("urn:uuid:"):
            idno_el = etree.SubElement(pub_stmt, "idno", type="urn:uuid")
            idno_el.text = ident
            break # Nimm den ersten URN

    etree.SubElement(pub_stmt, "availability").append(etree.Element("p"))

    # --- sourceDesc ---
    etree.SubElement(file_desc, "sourceDesc").append(etree.Element("p"))

    # --- profileDesc ---
    profile_desc = etree.SubElement(tei_header, "profileDesc")
    lang_usage = etree.SubElement(profile_desc, "langUsage")
    lang_el = etree.SubElement(lang_usage, "language")
    lang_el.text = metadata.get('language')
    if metadata.get('language'):
        lang_el.set("ident", metadata.get('language'))


def get_div_type_and_parent(part_json, tei_front, tei_body):
    """
    Bestimmt basierend auf 'inferred-type' und 'href',
    wo das <div> platziert werden soll (<front> oder <body>)
    und welchen 'type' es haben soll.
    """
    inferred_type = part_json.get('inferred-type')

    if inferred_type == 'chapter':
        return tei_body, 'chapter'

    if inferred_type == 'toc':
        return tei_front, 'toc'

    if inferred_type == 'imprint':
        return tei_front, 'imprint'

    if inferred_type == 'unkown':
        # Spezifische Regeln basierend auf dem TEI-Beispiel
        href = part_json.get('href')
        if href == 'part0000.xhtml': # Das Cover
            return tei_front, 'cover'
        if part_json.get('title') == 'Texas Marshal': # Das Vorwort
            return tei_front, 'foreword'

    # Standard-Fallback für alles andere, das nicht übersprungen werden soll
    if inferred_type:
        return tei_front, inferred_type

    return None, None # Überspringen


def process_recursive_inline(html_node, tei_parent):
    """
    Verarbeitet rekursiv INLINE-Knoten (Text, <i>, <b>, <graphic> etc.)
    und fügt sie dem übergeordneten TEI-Element (z.B. einem <p>) hinzu.
    """

    # --- Fall 1: Reiner Textknoten (NavigableString) ---
    if isinstance(html_node, element.NavigableString):
        text = str(html_node)
        # Text zu LXML-Element hinzufügen (behandelt Mixed Content korrekt)
        if len(tei_parent) > 0:
            last_child = tei_parent[-1]
            if last_child.tail is None:
                last_child.tail = text
            else:
                last_child.tail += text
        else:
            if tei_parent.text is None:
                tei_parent.text = text
            else:
                tei_parent.text += text
        return

    # --- Fall 2: HTML-Tag-Knoten (Tag) ---
    if isinstance(html_node, element.Tag):
        tag_name = html_node.name
        tei_element = None

        # --- Konvertierungsregeln (Inline) ---

        if tag_name == 'hi':
            tei_element = etree.SubElement(tei_parent, "hi")
            if 'rend' in html_node.attrs:
                rend_val = html_node.attrs['rend']
                if isinstance(rend_val, list):
                    tei_element.set("rend", " ".join(rend_val))
                else:
                    tei_element.set("rend", str(rend_val))
            # Spezifische Konvertierung von style="font-style: italic;"
            if 'style' in html_node.attrs and 'italic' in html_node.attrs['style']:
                tei_element.set("rend", "italic") # Überschreibt ggf. class-rend

        elif tag_name in ('i', 'em'):
            tei_element = etree.SubElement(tei_parent, "hi", rend="italic")

        elif tag_name in ('b', 'strong'):
            tei_element = etree.SubElement(tei_parent, "hi", rend="bold")

        elif tag_name == 'br':
            tei_element = etree.SubElement(tei_parent, "lb")

        elif tag_name == 'graphic':
            # <graphic> wird zu <figure><graphic>...
            # Wichtig: <graphic> ist im <p> verschachtelt
            tei_fig = etree.SubElement(tei_parent, "figure")
            tei_graph = etree.SubElement(tei_fig, "graphic")
            if 'url' in html_node.attrs:
                tei_graph.set("url", html_node.attrs['url'])
            if 'mimeType' in html_node.attrs:
                tei_graph.set("mimeType", html_node.attrs['mimeType'])
            if 'rend' in html_node.attrs:
                tei_graph.set("rend", " ".join(html_node.attrs['rend']))
            # Graphic-Tags haben keinen Inhalt
            return

        elif tag_name in ('body', 'html', 'div', 'p', 'lb'):
            # Ignoriere Block-Tags, wenn sie fälschlicherweise inline auftauchen
            # aber verarbeite ihre Kinder
            for child in html_node.children:
                process_recursive_inline(child, tei_parent)
            return

        else:
            # Regel: Unbekanntes Tag -> <uncertain>
            tei_element = etree.SubElement(tei_parent, "uncertain")
            tei_element.set("reason", f"Unmapped inline HTML tag: {tag_name}")
            unmapped_tags.add(tag_name)

        # --- Rekursion für Kind-Elemente ---
        if tei_element is not None:
            for child in html_node.children:
                process_recursive_inline(child, tei_element)


def process_html_fragment(html_nodes, tei_parent_div, div_type):
    """
    Verarbeitet eine LISTE von Top-Level-HTML-Knoten (Geschwister).
    Wickelt Top-Level <hi> in <p> ein.
    Verarbeitet <p> und <lb>/<br> direkt.
    """

    # --- Spezialbehandlung für TOC (Inhaltsverzeichnis) ---
    if div_type == 'toc':
        tei_list = etree.SubElement(tei_parent_div, "list")
        # Finde alle <p>-Tags im Fragment
        soup = BeautifulSoup("".join(str(n) for n in html_nodes), 'html.parser')

        head_text = tei_parent_div.findtext("head") # Titel ("Inhalt") holen

        for p_tag in soup.find_all('p'):
            item_text = p_tag.get_text(strip=True)
            # Füge als <item> hinzu, außer es ist die Überschrift selbst
            if item_text and item_text != head_text:
                etree.SubElement(tei_list, "item").text = item_text
        return # TOC-Verarbeitung hier beendet

    # --- Standardbehandlung für alle anderen div-Typen ---
    for node in html_nodes:
        tei_element = None

        # Ignoriere leere Textknoten auf Top-Level
        if isinstance(node, element.NavigableString) and node.strip() == "":
            continue

        if isinstance(node, element.Tag):
            tag_name = node.name

            # Regel: <p> -> <p>
            if tag_name == 'p':
                tei_element = etree.SubElement(tei_parent_div, "p")
                # Verarbeite den Inhalt des <p> rekursiv
                for child in node.children:
                    process_recursive_inline(child, tei_element)

            # Regel: <hi> (top-level) -> <p><hi>...</hi></p>
            elif tag_name == 'hi':
                # Erzeuge ein <p> als Wrapper
                tei_p_wrapper = etree.SubElement(tei_parent_div, "p")
                # Verarbeite das <hi> Tag *in* dem neuen <p>
                process_recursive_inline(node, tei_p_wrapper)

            # Regel: <br> oder <lb> -> <lb/>
            elif tag_name in ('br', 'lb'):
                etree.SubElement(tei_parent_div, "lb")

            # Regel: <div> (Wrapper) -> Inhalt direkt verarbeiten
            elif tag_name == 'div':
                # Verarbeite Kinder des <div>, als wären sie top-level
                process_html_fragment(node.contents, tei_parent_div, div_type)

            else:
                # Unbekanntes Top-Level-Tag
                tei_element = etree.SubElement(tei_parent_div, "uncertain")
                tei_element.set("reason", f"Unmapped block HTML tag: {tag_name}")
                unmapped_tags.add(tag_name)
                # Versuche trotzdem, den Inhalt zu verarbeiten
                for child in node.children:
                    process_recursive_inline(child, tei_element)


def process_content_list(content_list, tei_front, tei_body):
    """
    Iteriert durch die 'content'-Liste, erstellt die <div>s
    und ruft die HTML-Verarbeitung auf.
    """

    for part in content_list:
        parent_el, div_type = get_div_type_and_parent(part, tei_front, tei_body)

        # Überspringe Sektionen, für die wir keinen Typ/Ort haben
        if parent_el is None or div_type is None:
            continue

        # Erstelle das <div>
        div_el = etree.SubElement(parent_el, "div", type=div_type)

        html_text = part.get('text')
        if not html_text:
            continue

        soup = BeautifulSoup(f"<body>{html_text}</body>", 'html.parser')
        html_nodes = list(soup.body.contents)

        # --- Head-Logik ---
        if div_type == 'chapter':
            # Bei Kapiteln: Extrahiere <head> aus dem ersten <p>
            head_text = None
            first_node_index = -1

            for i, node in enumerate(html_nodes):
                if isinstance(node, element.NavigableString) and node.strip() == "":
                    continue # Leerraum überspringen
                if isinstance(node, element.Tag) and node.name == 'p':
                    head_text = node.get_text(strip=True)
                    first_node_index = i
                    break # Kopf gefunden

            if head_text:
                etree.SubElement(div_el, "head").text = head_text
                # Entferne den Kopf-Knoten aus der Liste, damit er nicht doppelt verarbeitet wird
                if first_node_index != -1:
                    html_nodes = html_nodes[first_node_index + 1:]

        elif div_type in ('toc', 'imprint', 'foreword'):
            # Bei <front>-Sektionen: Nimm den JSON-Titel
            json_title = part.get('title')
            if json_title:
                etree.SubElement(div_el, "head").text = json_title

        # --- Body-Logik ---
        process_html_fragment(html_nodes, div_el, div_type)


def main(json_filepath):
    """
    Hauptfunktion: Lädt, konvertiert, gibt das XML aus UND speichert es in einer Datei.
    """
    if not os.path.exists(json_filepath):
        print(f"FEHLER: Die angegebene Datei wurde nicht gefunden:\n{json_filepath}", file=sys.stderr)
        sys.exit(1)

    print(f"Verarbeite JSON-Datei: {json_filepath}", file=sys.stderr)

    # 1. JSON-Datei laden
    json_data = load_json_file(json_filepath)

    # 2. TEI-Grundstruktur erstellen
    tei_root = etree.Element("TEI", nsmap=NSMAP)

    # 3. <teiHeader> erstellen und füllen
    tei_header = etree.SubElement(tei_root, "teiHeader")
    create_tei_header(json_data, tei_header)

    # 4. <text>-Struktur erstellen (<front> und <body>)
    tei_text = etree.SubElement(tei_root, "text")
    tei_front = etree.SubElement(tei_text, "front")
    tei_body = etree.SubElement(tei_text, "body")

    # 5. 'content'-Liste verarbeiten und <front>/<body> füllen
    content_list = json_data.get("content", [])
    if not content_list:
        print("Warnung: Der 'content'-Schlüssel wurde nicht gefunden oder ist leer.", file=sys.stderr)
    else:
        process_content_list(content_list, tei_front, tei_body)

    # 6. Fertiges TEI-XML als Bytes generieren (für Konsole UND Datei)
    xml_output_bytes = etree.tostring(
        tei_root,
        pretty_print=True,
        encoding='utf-8',       # Wichtig: als Bytes mit UTF-8
        xml_declaration=True
    )

    # 7. XML in Konsole ausgeben
    xml_output_str = xml_output_bytes.decode('utf-8')
    print("\n--- Generiertes TEI-XML (Vollständig) ---")
    print(xml_output_str)

    # --- NEUER TEIL: XML in Datei speichern ---
    output_directory = "/home/spielberg/code/repos/dimeclass/ideas_temp"
    output_filename = "prompt_converted_tei.xml" # .xml hinzugefügt
    output_filepath = os.path.join(output_directory, output_filename)

    try:
        # Stelle sicher, dass das Verzeichnis existiert
        os.makedirs(output_directory, exist_ok=True)

        # Schreibe die Bytes direkt in die Datei
        with open(output_filepath, 'wb') as f:
            f.write(xml_output_bytes)
        print(f"\n--- Datei erfolgreich gespeichert ---", file=sys.stderr)
        print(f"Pfad: {output_filepath}", file=sys.stderr)

    except IOError as e:
        print(f"\n--- FEHLER BEIM SPEICHERN DER DATEI ---", file=sys.stderr)
        print(f"Fehler: {e}", file=sys.stderr)
    # --- ENDE NEUER TEIL ---

    # 8. Nicht konvertierte HTML-Tags melden
    print("\n--- Verarbeitungsbericht ---", file=sys.stderr)
    if unmapped_tags:
        sorted_tags = sorted(list(unmapped_tags))
        print(f"Nicht konvertierte HTML-Tags: {', '.join(sorted_tags)}", file=sys.stderr)
    else:
        print("Alle HTML-Tags wurden erfolgreich konvertiert oder ignoriert.", file=sys.stderr)

if __name__ == "__main__":
    # Pfad zu Ihrer JSON-Datei
    #input_file = "/home/spielberg/code/repos/dimeclass/conversion/data/json/G. F. Unger Sonder-Edition - Folge 003_ Texas-Marshal (German Edition).json"
    #input_file = "/home/spielberg/code/repos/epub_unpack/11json_inferred_type/000347_Jerry_Cotton_-_Folge_3083__Verw_-_Cotton,_Jerry/000347_Jerry_Cotton_-_Folge_3083__Verw_-_Cotton,_Jerry.json"
    input_file = "/home/spielberg/code/repos/epub_unpack/11json_inferred_type/000887_Vlcek_Dorian-Hunter-46---Horror-Seri_9783732597987/000887_Vlcek_Dorian-Hunter-46---Horror-Seri_9783732597987.json"
    # Führe die Hauptfunktion aus
    main(input_file)
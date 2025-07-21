# JSON to TEI Mapping Documetnation for EPUB-to-TEI Conversion

This is a documentation of the mapping between the input JSON structure, as found in the converted JSON files, and TEI elements and attributes. 

*This document is based on the analysis performed by `analyse_json_enhanced.py`.*

The basis for the ODD is TEI Lite. The schema is created with Roma.


It is a work-in-progress documentation.


## Table of Contents


* [1. Complex Elements](#1-complex-elements)
* [2. General Elements](#2-general-elements)
    * [2.1 General TEI Attributes](#1-general-tei-attributes) 
    * [2.2 Structural Elements](#2-structural-elements)
    * [2.3 Renditions/Emphasis/Style Elements](#3-renditions/emphasis/style-elements)
    * [2.4 Visual and Formatting Elements](#4-visual-and-formatting-elements)
    * [2.5 Classifications](#5-classifications)
    * [2.6 Processing and Internal Elements](#6-processing-and-internal-elements)
* [3. TEI Header Mapping](#3-tei-header-mapping)
    * [3.1 fileDesc (File Description)](#1-filedesc-file-description)
    * [3.2 encodingDesc (Encoding Description)](#2-encodingdesc-encoding-description)
    * [3.3 profileDesc (Text-Profile Description)](#3-profiledesc-text-profile-description)
    * [3.4 revisionDesc (Revision Description)](#34-revisiondesc-revision-description)

---
# 1. Complex Elements


# 2. General Elements
## 1. General TEI Attributes


| JSON Path                      | TEI Element/Attribute      | Notes                                                                                                                                                                                                                                                                                                                                |
| :----------------------------- | :------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `epub_metadata.language`      | `xml:lang` on `<TEI>` root | Set the primary language of the document on the root `<TEI>` element (e.g., `xml:lang="en"`).                                                                                                                                                                                                                                      |
|               | `xml:id`                   | Assign a unique `xml:id` to the `<TEI>` root, to each `<div>`, and potentially to `<p>` elements. These should be unique strings generated during conversion (e.g., based on a UUID or a sequential counter).  |
| `content[].level` or inherent order | `n` on `<div>` elements    | Assign `n` (number) to `<div>` elements, particularly chapters, based on their sequence or explicit numbering in the source                                                                                                                                |
---
## 2. Structural Elements

This section deals with elements that define the structure of the document.

| Pattern from JSON (HTML Tag/Rend Value) | TEI Element/Attribute      | Notes                                                                                                                                                                                                                                                                                                                                                     |
| :-------------------------------------- | :------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `<div>`                                 | `<div>`                    |                                                                                                                                                        |
| `<table>`                               | `<table>`                  | Represents a table.                                                                                                                                                                                                                                                                                                                       |
| `<row>`                                 | `<row>` (within `<table>`) | A row within a table.                                                                                                                                                                                                                                                                                                                     |
| `<cell>`                                | `<cell>` (within `<row>`)  | A cell within a table.                                                                                                                                                                                                                                                                                                                    |
| `<list>`                                | `<list>`                   | A list. Use `@type` for ordered (`<list type="ordered">`) or unordered (`<list type="unordered">`) lists.                                                                                                                                                                                                                                 |
| `<item>`                                | `<item>` (within `<list>`) | An item within a list.                                                                                                                                                                                                                                                                                                                    |
| `<lb>`                                  | `<lb/>`                    | Line break. Can be used to preserve lineation, especially in poetry or specific textual layouts.                                                                                                                                                                                                                                         |
| `level` (attribute on `<div>` or `head`) | `@n` or `@level` on `<div>` or `<head>` | Indicates the hierarchical level of a division or heading. This can be mapped to `@n` or `@level` on the corresponding `<div>` or `<head>` element in TEI. For example, `<div type="chapter" n="1">`.                                                                                                                            |
| p |p
|  `<head>`                                                                                            | `<head>`

---

## 3. Renditions/Emphasis/Style Elements

This section focuses on elements that represent various renditions.

Note:  If a style consistently denotes a semantic function (e.g., a specific font-size and font-weight always indicates a section heading), use the semantic TEI element (head). Otherwise, map to @rend on the most appropriate element (<p rend="center", <hi rend="bold").

| Pattern from JSON (HTML Tag/Rend Value) | TEI Element/Attribute      | Notes                                                                                                                                                                                                                                                                                                                                                                            |
| :-------------------------------------- | :------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|                                    |                     |                                                                                                                                                                                                                                                                                                                                                       |
|         `center`, `center bold margin-b`, `center margin-t`, `margin`, `margin-b`, `margin-t`, `Bold`, `bold`, `bigbold`, `bold-italic`, (rend values)                         |  `<hi rend="bold">`, `<hi rend="italic">`, `<hi rend="bold italic">`                 |   consider`<emph>`instead                                                                                                                                                                                                                                                 |
|                                  |              |                                              |
|  `class_s1`, `class_s2`, `class_s3`, `class_s4`, `class_s5`, `class_s7`, `class_s8`, `class_s50w`, `class_s59s`, `class_s5a1`, `class_s5a2`, `class_s5ew`, `class_s5ew1`, `class_s5ey`, `class_s5ez`, `class_s5f`, `class_s5f1` | |  ????The `class` values are styling classes and should be normalized to standard TEI `@rend` values or a controlled vocabulary.                                                                      |
|                                 |       |                                                                                                                                                                                                                                                                                                                                                            |
| `sup`                                   | `<sup>`                    | Superscript text. Often used for footnotes or references. Consider `<ref>` with `@target` if it refers to a specific section.                                                                                                                                                                                                                                          |
| `footnote-text`                         | `<note type="footnote">`   | Content of a footnote.                                                                                                                                                                                                                                                                                                                                                   |
| `text-align: center;` (from `style`)    | `@rend="center"`           | CSS style property for centering. Should be mapped to a `@rend` attribute on the containing element (e.g., `<p rend="center">`).                                                                                                                                                                                                                                     |
| `text-indent`, `indent`, `noindent`, `noindent bold`, `noindent bold margin-t`, `noindent center bold`, `noindent margin-t` (from `style`)            | `@rend="indent"` or `@rend="no-indent"` | CSS style property for text indentation. Can be mapped to a `@rend` attribute. "noindent" values would be mapped to `@rend="no-indent"`.                                                                                                                                                                                                                             |
| `font-size`, `font-family`, `line-height`, `color`, `font-weight`, `font-style`, `text-decoration` (from `style`) | `@rend` or specific TEI elements | These CSS properties usually indicate presentational styling. They can be mapped to `@rend` values (e.g., `<hi rend="large">`, `<hi rend="serif-font">`). For more complex styling, a `<styleDef>` in the TEI header can be used to define custom renditions.                                                                                                                              |
| `author margin`, `copyright margin`, `title margin` | `@rend` on containing element | These appear to be stylistic classes indicating layout. They can be mapped to `@rend` attributes (e.g., `<p rend="author-margin">`). Consider if some are truly structural (e.g., title page) and map to relevant TEI elements.                                                                                                                                        |
| `creator`, `publisher`, `title`, `copyright`, `preview-author bold`, `preview-title` (as `rend` values) | `<persName role="creator">`, `<orgName role="publisher">`, `<title>`, `<p type="copyright">`, `<byline>`, `<docTitle>` | These `rend` values indicate specific content with semantic meaning, not just styling. Mapping them to appropriate TEI elements like `<title>`, `<persName>`, `<orgName>`, or a `<p>` with a `@type` attribute provides more semantic information. `preview-author bold` could be `<byline>` within a `<div type="preview">`.                                                            |

 **Document Vocabulary in the TEI Header:**
    * document within the `<encodingDesc>` element using `<tagsDecl>`

    ```xml
    <encodingDesc>
      <tagsDecl>
        <rendition xml:id="r.bold" scheme="[https://example.com/rendition-vocab](https://example.com/rendition-vocab)">bold</rendition>
        <rendition xml:id="r.italic" scheme="[https://example.com/rendition-vocab](https://example.com/rendition-vocab)">italic</rendition>
        <rendition xml:id="r.center" scheme="[https://example.com/rendition-vocab](https://example.com/rendition-vocab)">center alignment</rendition>
        <rendition xml:id="r.indent" scheme="[https://example.com/rendition-vocab](https://example.com/rendition-vocab)">indented text</rendition>
        <rendition xml:id="r.no-indent" scheme="[https://example.com/rendition-vocab](https://example.com/rendition-vocab)">no indentation</rendition>
        <rendition xml:id="r.large" scheme="[https://example.com/rendition-vocab](https://example.com/rendition-vocab)">large font size</rendition>
        </tagsDecl>
    </encodingDesc>
    ```
    reference these using a `#` prefix, e.g., `<hi rendition="#r.bold">`.
---



## 4. Visual and Formatting Elements

This section covers elements related to visual presentation and embedded media.

| Pattern from JSON (HTML Tag/Attribute/Rend Value) | TEI Element/Attribute      | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| :------------------------------------------------ | :------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `<graphic>`                                       | `<graphic>`                |                                                                                                                                                                                                                                                                                                                                                  |
| `url` (attribute on `<graphic>`)                  | `@url` or `@ref` on `<graphic>` | The URL of the graphic file. `@url` is preferred for direct links, `@ref` for internal references.                                                                                                                                                                                                                                                                                                                                                 |
| `mimetype` (attribute on `<graphic>`)             | `@mimeType` on `<graphic>` | The MIME type of the graphic file (e.g., `image/jpeg`, `image/png`).                                                                                                                                                                                                                                                                                                                                                                                     |
| `width` (attribute on `<graphic>`)                | `@width` on `<graphic>`    | The width of the graphic. Can also be expressed in CSS through `@rend`.                                                                                                                                                                                                                                                                                                                                                                                   |
| `img`, `img class1631-0`, `img class1640-1`, `img class1656`, `img class9`, `img class_s1d`, `img class_s50s`, `img class_s59m` (rend values) | `<graphic>` with `@rend` or `@type` | These `rend` values indicate an image and often contain styling classes. Map to `<graphic>`. The specific classes could be mapped to `@rend` or if they indicate a semantic type of image, to `@type` (e.g., `<graphic type="figure">`). `img-caption center` would indicate a `<fig>` element containing both `<graphic>` and `<head rend="center">`.                                                                                                                               |
| `cover`, `coverFloat` (rend values)               | `<pb type="cover">` or `<graphic type="cover">` | These rend values indicate a cover image. `<pb type="cover"/>` can mark the page, and `<graphic type="cover"/>` can embed the image.                                                                                                                                                                                                                                                                                                                      |
| `separator`                                       | `<fw type="separator">` or `<lb type="separator"/>` | This `rend` value indicates a visual separator line or element. It could be represented as a typographic line (`<fw>`) or a line break (`<lb>`) with a specific type. Use `<fw>` (forme work) for a typographic line or `<lb type="separator">` for a line break that acts as a separator. If it separates logical sections, ensure it is within a `<div>` with `div@type="separator"`                                                                                                                                                                                                                                                                         |
| `border`, `border-bottom-color`, `border-collapse`, `border-color`, `border-left-color`, `border-right-color`, `border-spacing`, `border-top-color`, `clear`, `display`, `margin`, `margin-bottom`, `margin-right`, `margin-top`, `max-height`, `max-width`, `padding`, `padding-left`, `padding-top`, `vertical-align`, `orphans`, `widows` (CSS style properties) | `@rend` or `<row rend="border-bottom">` etc. | These CSS properties are primarily for styling and layout. They should generally be handled by mapping to `@rend` attributes on the relevant TEI elements (e.g., `<table>`, `<p>`, `<div>`). For complex table styling, consider using the TEI `model.tablePart` attributes or external CSS if the TEI is transformed to HTML. `orphans` and `widows` are specific to page breaking and might be best handled by rendering systems. |
|  |            |                                                                                                                                                        |
|  |                |                                                                                                                                                                                                                                                           |
|                         | |                                                                                                                                                                                                                               |


---

## 5. Classifications 

This section focuses on elements that describe the classification annotations.
| JSON Path                      | TEI Element/Attribute      | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| :----------------------------- | :------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `content[].inferred-type`      | ``              | |
| `content[].true-type`          | ``              |                                                                                                                                                                                                                                                                                                            |
| `content[].title` (of section) | `<div>/<head>`             | The heading of the division. If a division has a title, it should be nested as a `<head>` element directly inside that `<div>`.                                                                                                                                                                                                                                                                                                                                                                                       |
| `content[].is_narrative              | `` |                                                                                                                                                                                                                                                                                                                |

  

---
## 6. Processing and Internal Elements

This section covers elements related to the processing of the JSON files or internal mechanisms not directly part of the primary content.

| Pattern from JSON (Processing Log Key) | TEI Element/Attribute      | Notes                                                                                                                                                                                                                                                                                                                                                                                                                            |
| :------------------------------------- | :------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `component_log`                        | `<note type="processing-log">` or `<projectDesc>` |could be added as a note in the TEI header (`<teiHeader>`) or within `<projectDesc>` in `<encodingDesc>` to document the conversion process                                                                                                                                                                                            |
| `contain_subsections`                  |  |                                                                                                                                                                                                                                                                                                        |
|                        |                                                                                                                                                                                                                                                        |
| `is_collection` ,  `processing_log.is_collection`                        | `@type="collection"` on `<TEI>` or `<div type="collection">` |  If it's the entire TEI document, `@type="collection"` on the root `<TEI>` element is appropriate. If it's a section within a larger work, a `<div>` with `@type="collection"` could be used. This could also be a flag in `<projectDesc>`.                                                                                                                                                                                                                                |
|        |         |                                                                                                                                                                                                                                                                                                                                                   |
| `sanity_check`                         | `<note type="sanity-check">` or `<revisionDesc>` | It could be included as a note in the `<teiHeader>` or in `<revisionDesc>` if it reflects changes or validations applied to the document content.                                                                                                                                                                                                                                                                                           |
| `toc_repair`                           | `<note type="toc-repair">` or `<change>` | toc= table of contents. can be noted in the `<teiHeader>` within `<revisionDesc>` using a `<change>` element, or as a general `<note>` about the processing.                                                                                                                                                                                                                                                                                                                          |













---


# 3. TEI Header Mapping 


## 1. fileDesc (File Description)

The `fileDesc` element contains a full bibliographic description of an electronic file. It is mandatory.

fileDesc of global document:

| TEI Element/Attribute | Pattern from JSON | Notes | Check Off |
| :-------------------- | :---------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------- |
| `<titleStmt>` |   `EPUB Metadata  : title`(or from top level)   |  main title of the publication  | [ ] |
| `<titleStmt>` |  if type: section and `Content: title `   | title of subworks | [ ] |
| `<author/>` |   `EPUB Metadata  : creator`   |  | [ ] |
| `<respStmt/>` |   `EPUB Metadata  : contributor`   |bkp | [ ] |
| `<publicationStmt>` |   `EPUB Metadata  : publisher`   |  | [ ] |
| `<publicationStmt>` date|   `EPUB Metadata  : date`   |  | [ ] |
| `<publicationStmt>` `<idno type="ISBN">` |   `EPUB Metadata  : identifier` (with `"{http://www.idpf.org/2007/opf}scheme": "ISBN"`)   | ?where to put this | [ ] |
|`<publicationStmt>` `<availability>` |   `EPUB Metadata  : rights`   | or `<licence>` ?the original epub or our license, use `<availability>` to describe conditions of availability or a `<licence>` element with `@target` if a specific license (e.g., Creative Commons) is referenced.                                        | [ ] |
| `<sourceDesc>` |   `Top Level- source`   | e.g., `heftromane/Slade_Lassiter-Sammelband-1793---Wes_9783732562299.epub`.| [ ] |
| |  |  | [ ] |
| `<editionStmt>` |   |  | [ ] |
| `<notesStmt>` |   | | [ ] |
| `<seriesStmt>` |   | !!!!! https://teibyexample.org/exist/tutorials/TBED02v00.htm#seriesStmt | [ ] |

## 2. encodingDesc (Encoding Description)

The `encodingDesc` element documents the relationship between an electronic text and the source or sources from which it was derived.

| TEI Element/Attribute | Pattern from JSON | Notes | Check Off |
| :-------------------- | :---------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------- |
| `<projectDesc>` |   `Processing Log  : component_log`  | [ ] |
| `<projectDesc>` |   `Processing Log  : contain_subsections`   |  | [ ] |
| `<projectDesc>` |   `Processing Log  : is_collection`, `processing_log.is_collection`   | | [ ] |
| `<projectDesc>` |   `Processing Log  : sanity_check` (with `passed`, `len_extracted`, `len_calibre`)   |  | [ ] |
| `<projectDesc>` |   `Processing Log  : toc_repair`   |  | [ ] |
| `<editorialDecl>` |    |   | [ ] |
| `<classDecl>` |   ` inferred-type` , ` true-type`, is_narrative | https://www.tei-c.org/release/doc/tei-p5-doc/en/html/ref-classDecl.html | [ ] |
| `<refsDecl>` |   |  | [ ] |
| `<samplingDecl>` |   | | [ ] |

## 3. profileDesc (Text-Profile Description)



## 4. revisionDesc (Revision Description)

The `revisionDesc` summarizes the revision history for a file.
https://teibyexample.org/exist/tutorials/TBED02v00.htm#revisionDesc

```xml
<revisionDesc xml:id="revisions">
  <change when="YYYY-MM-DD" who="#MS">
    <item>Description of the change. E.g., "Updated ODD to include new mapping for <div> elements with specific rend attributes."</item>
    <item>Further details if necessary.</item>
  </change>
  <change when="YYYY-MM-DD" who="#MS">
    <item>Description of another change.</item>
  </change>
  </revisionDesc>

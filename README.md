# Aim

This project aims to convert epub files of German dime novels into TEI XML format. In a second phase a classifier will be trained to classify text parts. 

The conversion step involves defining a custom TEI schema (ODD) and developing a Python-based conversion script. 
The basis input files for the converison is the [epub_unpack project by LennartKeller](https://github.com/LennartKeller/epub_unpack.git), which converts epub into JSON files (and performs rule-based classifications).

## Documentation: Goals

- [x] Define a TEI schema (ODD) for the JSON data (with Roma).
* Develop a JSON to TEI conversion script.

## Documentation: working process
1. epub to JSON conversion and rule-based classification: [epub_unpack by LennartKeller](https://github.com/LennartKeller/epub_unpack.git)
2. [machine learning classification by ThoraHagen](https://github.com/LennartKeller/epub_unpack/tree/main/classifier)
3. JSON to TEI conversion: 
    - An initial idea was to check if we could reuse parts of the XSLT conversion structure used by the IDS in their [Epub to KorAP (via TEI I5) conversion project](https://github.com/KorAP/epub2korap) (see ["National Library as Corpus: Introducing DeLiKo@DNB – a Large Synchronous German Fiction Corpus"](https://doi.org/10.5281/zenodo.14943116.)). Upon closer inspection of their TEI conversion logic we decided that their approach does not fit the needs of our data structure. Since their TEI I5 schema is build around specific needs for linguistic data it would differ much from our dime novel data. Furthermore, the conversion uses Saxon EE which would lead to unwanted dependencies. Thus, we decided to continue working with our epub to JSON converter, which will serve as a middle processing step to the final TEI conversion.


## Global To Do
ongoing list with overarching project ideas
-  Lennart's ideas:
- Nora's ideas:
    - Consolidate with rule-based approach (inferred type in JSON, script see extractor/pipeline/type_inference.py)
    - Another classifier for the annotated true-type fields (exact instead of binary classification)
    - Merge these scripts into the full pipeline for an easier workflow (maybe?)

- integrate the project into Text+ monapipe
- enrich metadata for the TEI files by fetching metadata from the DNB (inspired by the [Epub to KorAP (via TEI I5) conversion project](https://github.com/KorAP/epub2korap))

# dimeclass

This repository contains the databse for the project "Erschließung und Strukturanalyse der Heftromane der Deutschen Nationalbibliothek" ( 01.08.2022-30.09.2026).


This project was developed at the [Chair of Computational Philology](https://www.germanistik.uni-wuerzburg.de/computerphilologie/) at the University of Würzburg in cooperation with the National Research Data Infrastructure (NFDI) consortium [Text+](https://text-plus.org/), spanning from 01.08.2022 to 30.09.2026.
It aims at the sematic upconversion of German dime novels. 

For detailed information about the project see the [documenation portal](https://cophi-wue.github.io/semantic-upconversion/).



This repository is research code rather than a packaged end-to-end converter. The individual scripts support different stages of the workflow, but they do not currently share a single command-line interface or portable configuration.

## Workflow

The intended processing stages are:

1. Extract EPUB files into JSON with the external [epub_unpack project](https://github.com/cophi-wue/epub_unpack).
2. Prepare identifiers for the source EPUB collection.
3. Analyse HTML structure and content types in the JSON files.
4. Split chapters and other content into work units for conversion and evaluation.
5. Classify a test set of chunks with a selection of open-weight Large Language Models and evaluate the performance.

The EPUB extraction step is external to this repository. The local scripts expect the resulting JSON structure and several scripts still contain machine-specific paths that must be changed before use.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Input EPUB or extracted JSON data, depending on the script being used

Install the declared dependencies with:

```bash
uv sync
```

The repository also contains `uv.lock` to keep the Python dependencies reproducible.

## Main Components

### EPUB preparation

[`conversion/scripts/python/epub_filename2id.py`](conversion/scripts/python/epub_filename2id.py) creates a tab-separated metadata file and copies EPUBs to ID-based filenames. Its functions are intended to be called from Python; it does not provide a command-line interface.

### JSON analysis

The analysis scripts inspect HTML tags, attributes, classes, nesting, and publisher-specific structure in the extracted JSON files. The outputs are written to `conversion/logs/` and are generated research artifacts, not source data.

### Chunking

[`conversion/scripts/python/chunking/chunking_chapters.py`](conversion/scripts/python/chunking/chunking_chapters.py) contains the reusable chunking logic. It flattens nested JSON content and applies different strategies for explicit chapters, star-separated novel sections, image-separated sections, and non-chapter material.

[`conversion/scripts/python/chunking/chunking_chapters_json_inferred_type.py`](conversion/scripts/python/chunking/chunking_chapters_json_inferred_type.py) applies the same approach to nested JSON files with inferred content types. It writes chunking reports and `work_units.json` to its configured output directory.


### Classification and evaluation

The directories [`conversion/scripts/python/goldstandard_labels_creation`](conversion/scripts/python/goldstandard_labels_creation) and [`conversion/scripts/python/evaluation_labels`](conversion/scripts/python/evaluation_labels) contain scripts for creating labelled chunks, checking labels, running classification experiments, and calculating evaluation metrics. These workflows depend on specific local datasets and, in some cases, external model services or HPC environments.

## Running a Component

The root module is only a basic installation check:

```bash
uv run python main.py
```

For a chunking run, edit the input and output paths in the script first, then run:

```bash
uv run python conversion/scripts/python/chunking/chunking_chapters_json_inferred_type.py
```

The script expects nested JSON files under the configured input directory. It produces per-file and aggregate TSV reports together with a `work_units.json` file.

There is currently no supported command that takes an EPUB and produces a complete TEI corpus without manual path and dataset configuration. The conversion and classification scripts should therefore be treated as independently runnable research components.

## Repository Layout

```text
main.py                         Basic installation check
pyproject.toml                  Project metadata and dependencies
conversion/scripts/             Analysis, chunking, conversion, and evaluation code
conversion/logs/                Generated logs and analysis results
uv.lock                         Locked dependency versions
```


## Data and Paths

Book files and extracted JSON data are local working data. They are ignored by Git and are not supplied by the Python package. Before running a script:

1. Place the required input data in the directory expected by that script.
2. Replace hard-coded absolute paths with paths on your machine.
3. Choose an output directory outside the source data.

The external `epub_unpack` project is responsible for the EPUB-to-JSON extraction stage.

# Heftromane Labeling Task: Guidelines & Instructions

## Goal
You are labeling text chunks from German *Heftromane*. Several AI models have attempted to automatically categorize these chunks, but we need human-verified gold labels to evaluate their performance. Your job: read each chunk and assign the correct label.

---

## Understanding the Chunk ID

Each chunk has a unique ID in this format:
```
filename_sectionIndex_chunkIndex
```

**Example:** `book_001.json_2_5`
- `book_001.json` = which "book" (Heftroman) the chunk comes from
- `2` = book number in a multinovel
- `5` = chunk number within that section


---

## How to Use the Tool

### **On First Visit:**
1. Open the HTML file in your browser
2. The left sidebar shows a list of books: click one to start labeling
3. All chunks from that book appear below

### **During Labeling:**
- **Read the text** in the gray preview box
- **Look at the model predictions** in the table (what AI models guessed)
- **Assign the correct label** in the "Gold Label" field
- **Add a subtype**  in the "Subtype" field
  - *Only "reader-information" chunks require a subtype*
  - Other labels: label as "none"
- Use **Previous/Next buttons** to move between chunks

### **Saving Your Work:**
- Click **"Export All Labels (TSV)"** when done for the day
- A file `gold_labels_YYYY-MM-DD_HH-MM.tsv` downloads to your computer
- Save it

### **Continuing Next Session:**
1. Open the same HTML file
2. Click **"Load Previous Session"** in the sidebar
3. Select your previously exported TSV file
4. All your old labels reload, continue from where you left off or edit previous labels
5. Export again when done

---

## Label Categories

### **Main Labels** (choose one per chunk)

| Label | Meaning |
|-------|---------|
| **chapter** | Narrative prose (prologue, chapters, epilogue), the main story content |
| **title-page** | contains the story title and optionally the author name; may contain an image. No other text is allowed |
| **cover-image** | Just an image, no text |
| **imprint** | Legal info, copyright, publisher details |
| **toc** | Table of contents |
| **author-information** | Author biography |
| **feedback** |letters to the editor (Leserkontaktseite) or prompts for the reader to leave a review or rating (e.g. "Sag uns deine Meinung. Wir freuen unsüber Bewertungen und Rezensionen im Store", "Wir hoffen, dass es dir gefallen hat") |
| **reader-information** | Meta-text for readers (series info, recaps, ads, previews, forewords). *requires subtype!* |
| **unknown** | Unclear or doesn't fit above categories |

### **Subtypes** (only for "reader-information")

| Subtype | Meaning |
|---------|---------|
| **meta-information** | Series summaries, historical info, "Was bisher geschah" (recaps), FAQs |
| **preview** | Preview of next installment or reading samples |
| **advertisement** | Promotional content for other books/products (1 sentence max). No plot summaries. If in doubt classify as "advertisement" and not as "preview"|
| **framing** | Exposition/setup text for the main story (setting, characters, initial situation). Positioned before the main plot (chapters) |
| **editorial** | Forewords, afterwords, acknowledgments by author/editor |
| **dedication** | Personal dedication |
| **castlist** | Character lists/cast |
| **other** | Subtypes that don't fit above |

---



#### If Something Doesn't Work or If You're Unsure About a Label



**Contact:** marina.spielberg@uni-wuerzburg.de

Include:
- What went wrong (screenshot if possible)
- The chunk IDs that caused issues


## Thank you! :)
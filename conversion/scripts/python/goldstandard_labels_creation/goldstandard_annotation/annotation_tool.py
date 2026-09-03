import os
import json
import pandas as pd
from pathlib import Path
import re
from html import escape, unescape

# Configuration
# OLD PATHS for new_testdata:
# TSV_FILE = r'C:\Users\Marina\Downloads\Heftromane_files_alles_mögliche\new_testdata\30_03_eval_results_new_testdata.tsv' #tsv with modl answers
# CHUNKS_DIR = r'C:\Users\Marina\Downloads\Heftromane_files_alles_mögliche\new_testdata\chunks_for_labeling' # chunks for labeling 
# OUTPUT_DIR = r'C:\Users\Marina\Downloads\Heftromane_files_alles_mögliche\new_testdata\comparison_report' # output dir for html report 

# NEW PATHS for old_data:
TSV_FILE = r'C:\Users\Marina\Downloads\Heftromane_files_alles_mögliche\new_testdata\old_data\03_12_eval_results_with_inferred-type.tsv' #tsv with modl answers
CHUNKS_DIR = r'C:\Users\Marina\Downloads\Heftromane_files_alles_mögliche\new_testdata\old_data\chunks_for_labeling' # chunks for labeling 
OUTPUT_DIR = r'C:\Users\Marina\Downloads\Heftromane_files_alles_mögliche\new_testdata\old_data\comparison_report' # output dir for html report 
HTML_OUTPUT = os.path.join(OUTPUT_DIR, 'annotation_tool_old_data.html') # standalone HTML file for colleague

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load TSV
df = pd.read_csv(TSV_FILE, sep='\t')

# Rename gold_label to old_gold_label if it exists
if 'gold_label' in df.columns:
    df = df.rename(columns={'gold_label': 'old_gold_label'})

# Load all chunks from JSON files
chunk_lookup = {}
for file in os.listdir(CHUNKS_DIR):
    if file.endswith('.json'):
        try:
            with open(os.path.join(CHUNKS_DIR, file), 'r', encoding='utf-8') as f:
                chunks = json.load(f)
                if isinstance(chunks, list):
                    for chunk in chunks:
                        if 'id' in chunk and 'text' in chunk:
                            chunk_lookup[chunk['id']] = chunk['text']
        except Exception as e:
            print(f"Warning: Could not load {file}: {e}")

print(f"Loaded {len(chunk_lookup)} chunks from {len([f for f in os.listdir(CHUNKS_DIR) if f.endswith('.json')])} files")

# Parse ID components
def parse_id(chunk_id):
    parts = chunk_id.split('_')
    for i, part in enumerate(parts):
        if part.endswith('.json'):
            book_file = '_'.join(parts[:i+1])
            section_idx = int(parts[i+1])
            chunk_idx = int(parts[i+2])
            return book_file, section_idx, chunk_idx
    return None, None, None

df['book_file'] = df['id'].apply(lambda x: parse_id(x)[0])
df['section_idx'] = df['id'].apply(lambda x: parse_id(x)[1])
df['chunk_idx'] = df['id'].apply(lambda x: parse_id(x)[2])

# Extract text and clean HTML
def clean_text(html_text):
    if not html_text:
        return ""
    # 1. Decode HTML entities (e.g., &#252; -> ü)
    text = unescape(html_text)
    # 2. Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # 3. Add space after punctuation if missing (e.g., "gefallen?Dann" -> "gefallen? Dann")
    text = re.sub(r'([.!?\d,:;])([a-zA-Z])', r'\1 \2', text)
    # 4. Add space between lowercase and uppercase (e.g., "ThanneckFürsten" -> "Thanneck Fürsten")
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # 5. Normalize multiple spaces into a single space
    text = re.sub(r'\s+', ' ', text).strip()
    return text

df['text'] = df['id'].apply(lambda x: clean_text(chunk_lookup.get(x, "")))

# Get model columns
model_cols = [col for col in df.columns if col not in 
              ['id', 'gold_label', 'book_file', 'section_idx', 'chunk_idx', 'text']]
label_models = [col for col in model_cols if not col.endswith('_subtype')]

# Sort by book and section
df_sorted = df.sort_values(['book_file', 'section_idx', 'chunk_idx']).reset_index(drop=True)

# Generate HTML Report with embedded data
html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Chunk Annotation Tool</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; }
        .container { display: flex; height: 100vh; }
        .sidebar { width: 250px; background: #333; color: white; overflow-y: auto; padding: 10px; }
        .sidebar h3 { padding: 10px 0; margin-top: 15px; font-size: 14px; }
        .book-btn { display: block; width: 100%; padding: 8px; margin: 5px 0; background: #555; color: white; 
                    border: none; cursor: pointer; text-align: left; font-size: 12px; }
        .book-btn:hover { background: #777; }
        .book-btn.active { background: #0066cc; }
        .btn-group { margin: 15px 0; }
        .btn { width: 100%; padding: 10px; margin: 5px 0; border: none; cursor: pointer; border-radius: 3px; 
               font-size: 12px; font-weight: bold; }
        .btn-primary { background: #0066cc; color: white; }
        .btn-primary:hover { background: #004a99; }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; }
        .main { flex: 1; overflow-y: auto; padding: 20px; }
        .chunk { background: white; margin: 20px 0; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .chunk-id { font-weight: bold; color: #0066cc; font-size: 14px; margin-bottom: 10px; }
        .chunk-section { color: #666; font-size: 12px; margin-bottom: 5px; }
        .text-preview { background: #f9f9f9; padding: 10px; border-left: 4px solid #ccc; margin: 10px 0; 
                        font-size: 13px; line-height: 1.5; }
        .models-table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }
        .models-table th, .models-table td { padding: 8px; text-align: left; border: 1px solid #ddd; }
        .models-table th { background: #f0f0f0; font-weight: bold; }
        .label-input { width: 100%; padding: 8px; margin: 10px 0; border: 1px solid #ccc; border-radius: 3px; }
        .nav-buttons { margin: 10px 0; }
        .nav-buttons button { padding: 8px 15px; margin-right: 10px; background: #0066cc; color: white; 
                              border: none; cursor: pointer; border-radius: 3px; font-size: 12px; }
        .nav-buttons button:hover { background: #004a99; }
        .progress { color: #666; font-size: 12px; margin: 5px 0; }
        .file-input { padding: 5px; }
        .hidden { display: none; }
        .status { padding: 10px; margin: 10px 0; border-radius: 3px; font-size: 12px; }
        .status-success { background: #d4edda; color: #155724; }
        .status-error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h3>Session</h3>
            <div class="btn-group">
                <input type="file" id="tsvInput" class="file-input" accept=".tsv,.txt" />
                <button class="btn btn-primary" onclick="loadPreviousSession()">Load Previous Session</button>
                <div id="loadStatus"></div>
            </div>
            
            <h3>Books</h3>
            <div id="bookList"></div>
            
            <h3>Export</h3>
            <div class="btn-group">
                <button class="btn btn-success" onclick="exportLabels()">Export All Labels (TSV)</button>
            </div>
        </div>
        <div class="main" id="mainContent">
            <div id="chunksContainer"></div>
        </div>
    </div>

    <script>
        const chunks = """ + json.dumps(df_sorted.to_dict('records')) + """;
        const books = """ + json.dumps(df_sorted['book_file'].unique().tolist()) + """;
        let currentBook = null;
        let labels = {}; // chunk_id -> gold_label
        let subtypes = {}; // chunk_id -> gold_label_subtype
        
        // Load previous session from TSV file
        function loadPreviousSession() {
            const fileInput = document.getElementById('tsvInput');
            const file = fileInput.files[0];
            if (!file) {
                showStatus('Please select a TSV file first', 'error');
                return;
            }
            
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const lines = e.target.result.split('\\n');
                    const header = lines[0].split('\\t');
                    const idIdx = header.indexOf('id');
                    const labelIdx = header.indexOf('gold_label');
                    const subtypeIdx = header.indexOf('gold_label_subtype');
                    
                    if (idIdx === -1 || labelIdx === -1) {
                        showStatus('Invalid TSV format: missing "id" or "gold_label" column', 'error');
                        return;
                    }
                    
                    for (let i = 1; i < lines.length; i++) {
                        if (!lines[i].trim()) continue;
                        const parts = lines[i].split('\\t');
                        const id = parts[idIdx];
                        const label = parts[labelIdx] || '';
                        const subtype = subtypeIdx !== -1 ? (parts[subtypeIdx] || '') : '';
                        
                        labels[id] = label;
                        if (subtype) subtypes[id] = subtype;
                    }
                    
                    showStatus(`Loaded ${Object.keys(labels).length} previous labels`, 'success');
                    renderChunks();
                } catch (error) {
                    showStatus('Error parsing TSV file: ' + error.message, 'error');
                }
            };
            reader.readAsText(file);
        }
        
        function showStatus(message, type) {
            const statusDiv = document.getElementById('loadStatus');
            statusDiv.textContent = message;
            statusDiv.className = 'status status-' + type;
            setTimeout(() => { statusDiv.textContent = ''; statusDiv.className = ''; }, 4000);
        }
        
        // Render sidebar
        function renderSidebar() {
            const bookList = document.getElementById('bookList');
            books.forEach(book => {
                const btn = document.createElement('button');
                btn.className = 'book-btn';
                btn.textContent = book.substring(0, 40) + (book.length > 40 ? '...' : '');
                btn.onclick = () => selectBook(book);
                bookList.appendChild(btn);
            });
        }
        
        // Select book and render chunks
        function selectBook(book) {
            currentBook = book;
            document.querySelectorAll('.book-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.textContent.startsWith(book.substring(0, 40))) {
                    btn.classList.add('active');
                }
            });
            renderChunks();
        }
        
        // Render chunks for current book
        function renderChunks() {
            const container = document.getElementById('chunksContainer');
            container.innerHTML = '';
            const bookChunks = chunks.filter(c => c.book_file === currentBook);
            const labeledCount = bookChunks.filter(c => labels[c.id]).length;
            
            bookChunks.forEach((chunk, idx) => {
                const div = document.createElement('div');
                div.className = 'chunk';
                
                const textPreview = chunk.text ? chunk.text : '(No text)';
                const currentLabel = labels[chunk.id] || '';
                const currentSubtype = subtypes[chunk.id] || '';
                
                const modelsHtml = """ + json.dumps(label_models) + """.map(model => {
                    const prediction = chunk[model] || '';
                    const subtype = chunk[model + '_subtype'] || '';
                    return `<tr><td>${model.replace(/_/g, '/')}</td><td>${prediction}</td><td>${subtype || '-'}</td></tr>`;
                }).join('');
                
                div.innerHTML = `
                    <div class="chunk-id">${chunk.id}</div>
                    <div class="chunk-section">Book: ${chunk.book_file} | Section: ${chunk.section_idx} | Chunk: ${chunk.chunk_idx}</div>
                    <div class="text-preview">${textPreview.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
                    <table class="models-table">
                        <tr><th>Model</th><th>Prediction</th><th>Subtype</th></tr>
                        ${modelsHtml}
                    </table>
                    <div style="display: flex; gap: 15px;">
                        <div style="flex: 1;">
                            <label style="display: block; font-weight: bold; margin-bottom: 5px;">Gold Label:</label>
                            <input type="text" class="label-input gold-label" placeholder="Enter gold label..." value="${escape(currentLabel)}" data-chunk-id="${chunk.id}">
                        </div>
                        <div style="flex: 1;">
                            <label style="display: block; font-weight: bold; margin-bottom: 5px;">Subtype:</label>
                            <input type="text" class="label-input subtype-label" placeholder="Enter subtype..." value="${escape(currentSubtype)}" data-chunk-id="${chunk.id}">
                        </div>
                    </div>
                    <div class="nav-buttons">
                        ${idx > 0 ? `<button onclick="scrollToChunk(${idx-1})">← Previous</button>` : ''}
                        <span class="progress">${idx + 1} / ${bookChunks.length}</span>
                        ${idx < bookChunks.length - 1 ? `<button onclick="scrollToChunk(${idx+1})">Next →</button>` : ''}
                    </div>
                `;
                container.appendChild(div);
                
                // Add event listeners
                const goldInput = div.querySelector('.gold-label');
                const subtypeInput = div.querySelector('.subtype-label');
                const chunkId = goldInput.getAttribute('data-chunk-id');
                
                goldInput.addEventListener('input', function(e) {
                    labels[chunkId] = e.target.value;
                });
                
                subtypeInput.addEventListener('input', function(e) {
                    subtypes[chunkId] = e.target.value;
                });
            });
            
            // Show progress
            const progressDiv = document.createElement('div');
            progressDiv.className = 'progress';
            progressDiv.style.marginTop = '20px';
            progressDiv.textContent = `Progress: ${labeledCount} / ${bookChunks.length} labeled`;
            container.appendChild(progressDiv);
        }
        
        // Export labels as TSV
        function exportLabels() {
            let tsv = 'id\\tgold_label\\tgold_label_subtype\\n';
            chunks.forEach(chunk => {
                const label = labels[chunk.id] || '';
                const subtype = subtypes[chunk.id] || '';
                tsv += `${chunk.id}\\t${label}\\t${subtype}\\n`;
            });
            
            const blob = new Blob([tsv], { type: 'text/tab-separated-values' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const now = new Date();
            const timestamp = now.getFullYear() + '-' + 
                  String(now.getMonth() + 1).padStart(2, '0') + '-' + 
                  String(now.getDate()).padStart(2, '0') + '_' + 
                  String(now.getHours()).padStart(2, '0') + '-' + 
                  String(now.getMinutes()).padStart(2, '0');
            a.download = `${timestamp}_gold_labels.tsv`;
            a.click();
            window.URL.revokeObjectURL(url);
        }
        
        function scrollToChunk(idx) {
            const chunks = document.querySelectorAll('.chunk');
            if (chunks[idx]) chunks[idx].scrollIntoView({ behavior: 'smooth' });
        }
        
        renderSidebar();
        if (books.length > 0) selectBook(books[0]);
    </script>
</body>
</html>
"""

with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Standalone HTML file: {HTML_OUTPUT}")

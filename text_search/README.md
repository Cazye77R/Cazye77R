# text_search

Lightweight local text search with an optional AI chat interface.  
No external search server needed — everything runs in-process.

---

## Features

- **BM25 keyword search** — fast, no model required
- **Semantic search** — sentence-transformer embeddings (~27 MB, downloaded once)
- **Hybrid search** — Reciprocal Rank Fusion of both (default)
- **Chat mode** — RAG pipeline: ask questions, get sourced answers via Ollama / Claude / OpenAI
- Supported file formats: `.txt`, `.md`, `.csv`, `.pdf`, `.docx`
- Index export/import as a safe ZIP (JSON + numpy, no pickle)

---

## Installation

```bash
# Core dependencies
pip install -r requirements.txt

# Optional — DOCX support
pip install python-docx

# Optional — Cloud LLM providers in Chat mode
pip install anthropic   # Claude
pip install openai      # OpenAI
```

---

## Start

```bash
streamlit run text_search/app.py
```

The app opens at `http://localhost:8501`.

---

## Workflow

1. **Upload** one or more files (`.txt`, `.md`, `.csv`, `.pdf`, `.docx`)
2. **Build index** — choose a speed preset in the sidebar first:
   - ⚡ **Schnell** — keyword only, instant, no model
   - ⚖ **Ausgewogen** — hybrid, balanced (default)
   - 🎯 **Präzise** — semantic, highest recall
3. **Search or chat** — the index stays active for the whole browser session

---

## Search modes

| Mode | How it works | When to use |
|---|---|---|
| **Hybrid** | RRF fusion of BM25 + embeddings | Best overall quality (default) |
| **Keyword** | BM25 inverted index, pure stdlib | Exact terms, no model needed |
| **Semantic** | Cosine similarity on embeddings | Synonyms, paraphrases, meaning |
| **💬 Chat** | RAG: retrieve chunks → LLM answer | Natural language questions |

---

## Chat mode

The chat mode retrieves the most relevant document chunks and passes them to
an LLM together with the question. The LLM is instructed to answer exclusively
from the provided text and to cite each chunk inline as `[1]`, `[2]`, etc.

### Providers

| Provider | Setup | Default model |
|---|---|---|
| **Ollama** (default) | `ollama serve` + `ollama pull llama3.2:1b` | `llama3.2:1b` |
| Claude API | API key in sidebar | `claude-3-5-haiku-20241022` |
| OpenAI API | API key in sidebar | `gpt-4o-mini` |

The app includes a setup wizard that detects whether Ollama is installed,
running, and has the selected model — and guides through each step if not.

**API keys** are held only in browser session memory.
They are never written to disk or logged.

---

## Offline mode

Check **Offline-Modus** in the sidebar before building an index.  
Sets `TRANSFORMERS_OFFLINE=1` — the embedding model is loaded from the local
HuggingFace cache (`~/hf_cache`) without any network access.

To pre-download the model while online:

```python
from sentence_transformers import SentenceTransformer
SentenceTransformer("all-MiniLM-L6-v2")  # downloads ~27 MB once
```

---

## Index persistence

Use **Index herunterladen** in the sidebar to save the current index as a
`.zip` file. Upload it later with **Gespeicherten Index laden** to skip
re-indexing.

The ZIP contains plain JSON (BM25 data) and a numpy array (embeddings).
No pickle — loading the file cannot execute arbitrary code.

---

## Running tests

```bash
pip install pytest
python -m pytest text_search/tests/ -v
```

16 tests covering `index.py`, `loader.py`, and `searcher.py`.

---

## Module structure

```
text_search/
├── app.py        Streamlit UI
├── loader.py     File loading + sentence-based chunking
├── index.py      BM25 inverted index
├── semantic.py   Sentence-transformer embeddings
├── searcher.py   Unified search (keyword / semantic / hybrid RRF)
├── chat.py       RAG pipeline + streaming LLM providers
└── tests/        pytest unit tests
```

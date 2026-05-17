# Elephant

A local memory system for AI assistants, backed by Markdown files with YAML frontmatter. Exposes a FastAPI REST interface and integrates with Ollama for LLM inference.

## Project Layout

```
elephant/
├── main.py                  # FastAPI entry point
├── config.py                # Settings (Ollama URL, model name, paths)
├── memory/
│   ├── __init__.py
│   ├── markdown_store.py    # CRUD for Markdown files
│   └── schemas.py           # Pydantic models for memory entries
├── data/
│   └── memories/
│       ├── general/         # General knowledge about the user
│       ├── projects/        # Project-related memories
│       └── conversations/   # Conversation summaries
└── requirements.txt
```

## Setup

```bash
pip install -r elephant/requirements.txt
```

Optionally copy `.env.example` to `.env` and adjust:

```
ELEPHANT_OLLAMA_URL=http://localhost:11434
ELEPHANT_MODEL_NAME=llama3
ELEPHANT_MEMORIES_BASE_PATH=elephant/data/memories
```

## Run

```bash
uvicorn elephant.main:app --reload
```

API docs available at <http://localhost:8000/docs>.

## Markdown Memory Format

```markdown
---
title: "Example"
tags: ["python", "project"]
importance: 0.7
created_at: "2026-05-17T10:00:00"
updated_at: "2026-05-17T10:00:00"
---
Here is the actual memory content.
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/memories` | List all memories (optional `?category=`) |
| `POST` | `/memories` | Create a new memory |
| `GET` | `/memories/search?q=` | Full-text search |
| `PATCH` | `/memories/{filepath}` | Update content / tags / importance |
| `DELETE` | `/memories/{filepath}` | Delete a memory |

## Tests

```bash
pytest tests/ -v
```

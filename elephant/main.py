from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from elephant.chat.engine import ChatEngine
from elephant.chat.history import ConversationHistory
from elephant.config import settings
from elephant.memory import (
    delete_memory,
    list_memories,
    save_memory,
    search_memories_text,
    update_memory,
)
from elephant.memory.vector_store import (
    delete_embedded,
    embed_memory,
    init_collection,
    search_similar,
    sync_all_memories,
)

# Module-level singletons — pre-set in tests to bypass the lifespan initialiser.
_engine: Optional[ChatEngine] = None
_sessions: dict[str, ConversationHistory] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    if _engine is None:
        collection = init_collection()
        _engine = ChatEngine(model=settings.model_name, collection=collection)
    yield


app = FastAPI(title="Elephant Memory API", version="0.2.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SaveRequest(BaseModel):
    category: str
    title: str
    content: str
    tags: list[str] = []
    importance: float = 0.5


class UpdateRequest(BaseModel):
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: Optional[float] = None


class EmbedRequest(BaseModel):
    filepath: str


class ChatRequest(BaseModel):
    message: str
    session_id: str


# ---------------------------------------------------------------------------
# Memory CRUD
# ---------------------------------------------------------------------------

@app.get("/memories")
def get_memories(category: Optional[str] = None):
    memories = list_memories(category)
    return [
        {
            "filepath": str(m.filepath),
            "category": m.category,
            "metadata": m.metadata.model_dump(),
            "content": m.content,
        }
        for m in memories
    ]


@app.post("/memories", status_code=201)
def create_memory(req: SaveRequest):
    path = save_memory(req.category, req.title, req.content, req.tags, req.importance)
    return {"filepath": str(path)}


@app.get("/memories/search")
def text_search(q: str):
    results = search_memories_text(q)
    return [
        {
            "filepath": str(m.filepath),
            "category": m.category,
            "metadata": m.metadata.model_dump(),
            "content": m.content,
        }
        for m in results
    ]


@app.patch("/memories/{filepath:path}")
def patch_memory(filepath: str, req: UpdateRequest):
    p = Path(filepath)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Memory not found")
    memory = update_memory(p, req.content, req.tags, req.importance)
    return {"filepath": str(memory.filepath), "metadata": memory.metadata.model_dump()}


@app.delete("/memories/{filepath:path}", status_code=204)
def remove_memory(filepath: str):
    p = Path(filepath)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Memory not found")
    delete_memory(p)


# ---------------------------------------------------------------------------
# Vector store endpoints
# ---------------------------------------------------------------------------

@app.post("/memories/embed")
def embed_memory_endpoint(req: EmbedRequest):
    """Embed a single Markdown memory file into ChromaDB."""
    p = Path(req.filepath)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Memory file not found")
    n = embed_memory(p)
    return {"filepath": req.filepath, "chunks": n}


@app.post("/memories/sync")
def sync_memories_endpoint():
    """Sync all Markdown files to ChromaDB, skipping unchanged ones."""
    report = sync_all_memories()
    return report


@app.get("/memories/semantic-search")
def semantic_search(
    q: str,
    top_k: int = 5,
    min_importance: float = 0.0,
    category: Optional[str] = None,
):
    return search_similar(q, top_k=top_k, min_importance=min_importance, category_filter=category)


@app.delete("/memories/embedded/{filepath:path}", status_code=204)
def remove_embedded(filepath: str):
    delete_embedded(Path(filepath))


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    if _engine is None:
        raise HTTPException(status_code=503, detail="Chat engine not initialised")

    if req.session_id not in _sessions:
        _sessions[req.session_id] = ConversationHistory()

    history = _sessions[req.session_id]
    response_text, sources = _engine.chat(
        req.message,
        conversation_history=history.messages(),
    )

    history.add("user", req.message)
    history.add("assistant", response_text)

    return {
        "response": response_text,
        "sources": [
            {
                "source_file": s["source_file"],
                "title": s["metadata"].get("title", ""),
                "score": s["score"],
                "chunk": s["chunk"],
            }
            for s in sources
        ],
    }


@app.get("/sessions/{session_id}/summary")
def session_summary(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    summary = _sessions[session_id].export_summary()
    return {"session_id": session_id, "summary": summary}


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    _sessions.pop(session_id, None)

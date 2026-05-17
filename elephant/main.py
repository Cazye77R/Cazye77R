import datetime
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons
# Pre-set in tests to bypass the lifespan initialiser.
# ---------------------------------------------------------------------------

_engine: Optional[ChatEngine] = None
_sessions: dict[str, ConversationHistory] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    if _engine is None:
        collection = init_collection()
        _engine = ChatEngine(model=settings.model_name, collection=collection)
        logger.info("ChatEngine initialised with model=%s", settings.model_name)
    yield


app = FastAPI(title="Elephant Memory API", version="0.3.0", lifespan=lifespan)


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
    model: Optional[str] = None


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------

def _auto_extract(conversation: list[dict], session_id: str) -> None:
    """Run in background after each chat turn (>= 4 messages)."""
    if _engine is None:
        return
    try:
        n = _engine.extract_and_save(conversation)
        if n:
            logger.info(
                "[%s] Auto-extraction session=%s: %d memories saved",
                datetime.datetime.utcnow().isoformat(),
                session_id,
                n,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Auto-extraction failed session=%s: %s", session_id, exc)


def _close_session_bg(conversation: list[dict], session_id: str) -> None:
    """Triggered by close endpoint: extract facts + save conversation summary."""
    if _engine is None or not conversation:
        return
    try:
        # 1 — Extract and save individual facts
        n = _engine.extract_and_save(conversation)

        # 2 — Persist conversation summary in conversations/
        hist = ConversationHistory.from_messages(conversation)
        summary_text = hist.export_summary()
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = save_memory(
            category="conversations",
            title=f"session_{session_id}_{ts}",
            content=summary_text,
            tags=["session", "summary"],
            importance=0.4,
        )
        embed_memory(path, collection=_engine.collection)

        logger.info(
            "[%s] Session %s closed — %d facts + summary saved",
            datetime.datetime.utcnow().isoformat(),
            session_id,
            n,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Close-session task failed session=%s: %s", session_id, exc)


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
    logger.info("Memory created: %s", path)
    return {"filepath": str(path)}


@app.get("/memories/search")
def text_search(q: str):
    return [
        {
            "filepath": str(m.filepath),
            "category": m.category,
            "metadata": m.metadata.model_dump(),
            "content": m.content,
        }
        for m in search_memories_text(q)
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
    logger.info("Memory deleted: %s", filepath)


# ---------------------------------------------------------------------------
# Vector store endpoints
# ---------------------------------------------------------------------------

@app.post("/memories/embed")
def embed_memory_endpoint(req: EmbedRequest):
    p = Path(req.filepath)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Memory file not found")
    n = embed_memory(p)
    return {"filepath": req.filepath, "chunks": n}


@app.post("/memories/sync")
def sync_memories_endpoint():
    report = sync_all_memories()
    logger.info("Memory sync complete: %s", report)
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
def chat_endpoint(req: ChatRequest, background_tasks: BackgroundTasks):
    if _engine is None:
        raise HTTPException(status_code=503, detail="Chat engine not initialised")

    if req.session_id not in _sessions:
        _sessions[req.session_id] = ConversationHistory()

    history = _sessions[req.session_id]
    response_text, sources = _engine.chat(
        req.message,
        conversation_history=history.messages(),
        model=req.model,
    )

    history.add("user", req.message)
    history.add("assistant", response_text)

    # Auto-extract after >= 4 messages (>= 2 full turns)
    if len(history.messages()) >= 4:
        background_tasks.add_task(
            _auto_extract,
            history.messages(),  # snapshot (messages() returns a copy)
            req.session_id,
        )

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


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

@app.post("/sessions/{session_id}/close")
def close_session(session_id: str, background_tasks: BackgroundTasks):
    """Trigger final memory extraction and conversation summary, then remove session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    history = _sessions.pop(session_id)
    conversation = history.messages()

    if conversation and _engine is not None:
        background_tasks.add_task(_close_session_bg, conversation, session_id)
        logger.info("Session %s closing — %d messages queued for extraction", session_id, len(conversation))

    return {"session_id": session_id, "status": "closing", "turns": history.turn_count()}


@app.get("/sessions/{session_id}/summary")
def session_summary(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    summary = _sessions[session_id].export_summary()
    return {"session_id": session_id, "summary": summary}


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    _sessions.pop(session_id, None)

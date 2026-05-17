from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from elephant.memory import (
    delete_memory,
    list_memories,
    load_memory,
    save_memory,
    search_memories_text,
    update_memory,
)

app = FastAPI(title="Elephant Memory API", version="0.1.0")


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
def search(q: str):
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

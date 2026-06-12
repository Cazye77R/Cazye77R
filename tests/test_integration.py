"""End-to-end integration test: save memory → embed → chat via HTTP.

All Ollama network calls are mocked so the suite runs without a running
Ollama instance. ChromaDB runs in a per-test PersistentClient directory.
"""

from unittest.mock import MagicMock, patch

import chromadb
import pytest
from fastapi.testclient import TestClient

import elephant.main as main_module
from elephant.chat.engine import ChatEngine
from elephant.memory.markdown_store import save_memory
from elephant.memory.vector_store import init_collection

FAKE_EMBEDDING = [0.1] * 768
FAKE_CHAT_REPLY = "List Comprehensions sind effizienter als For-Schleifen in Python."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_ollama():
    """Single patch that routes /api/embeddings vs /api/chat by URL.

    Patching both modules separately conflicts because both reference the same
    requests.post object — the last patch entered wins and overwrites the first.
    """
    embed_resp = MagicMock()
    embed_resp.json.return_value = {"embedding": FAKE_EMBEDDING}
    embed_resp.raise_for_status = MagicMock()

    chat_resp = MagicMock()
    chat_resp.json.return_value = {"message": {"content": FAKE_CHAT_REPLY}}
    chat_resp.raise_for_status = MagicMock()

    def _route(url, *args, **kwargs):
        return embed_resp if "/api/embeddings" in url else chat_resp

    with patch("requests.post", side_effect=_route):
        yield


@pytest.fixture()
def tmp_memories(tmp_path, monkeypatch):
    for cat in ("general", "projects", "conversations"):
        (tmp_path / cat).mkdir()
    import elephant.config as cfg
    import elephant.memory.markdown_store as store
    import elephant.memory.vector_store as vs
    monkeypatch.setattr(cfg.settings, "memory_path", tmp_path)
    monkeypatch.setattr(store.settings, "memory_path", tmp_path)
    monkeypatch.setattr(vs.settings, "memory_path", tmp_path)
    return tmp_path


@pytest.fixture()
def client(tmp_path, tmp_memories):
    """TestClient with isolated engine — bypasses the production lifespan."""
    chroma_client = chromadb.PersistentClient(path=str(tmp_path / "chromadb"))
    collection = init_collection(chroma_client)

    # Pre-set engine: lifespan checks `if _engine is None` before initialising
    main_module._engine = ChatEngine(collection=collection)
    main_module._sessions = {}

    with TestClient(main_module.app) as c:
        yield c

    main_module._engine = None
    main_module._sessions = {}


# ---------------------------------------------------------------------------
# Full RAG flow
# ---------------------------------------------------------------------------

def test_save_embed_chat(client):
    """Core flow: create a memory, embed it, then chat about it."""
    # 1 — Save memory
    resp = client.post("/memories", json={
        "category": "general",
        "title": "Python Tipps",
        "content": (
            "List Comprehensions sind effizienter als For-Schleifen.\n\n"
            "Nutze enumerate() statt range(len())."
        ),
        "tags": ["python", "tipps"],
        "importance": 0.9,
    })
    assert resp.status_code == 201
    filepath = resp.json()["filepath"]

    # 2 — Embed memory
    resp = client.post("/memories/embed", json={"filepath": filepath})
    assert resp.status_code == 200
    embed_data = resp.json()
    assert embed_data["chunks"] >= 1

    # 3 — Chat
    resp = client.post("/chat", json={
        "message": "Was sind gute Python-Tipps?",
        "session_id": "flow-test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == FAKE_CHAT_REPLY
    assert isinstance(data["sources"], list)


def test_chat_sources_contain_embedded_memory(client, tmp_memories):
    path = save_memory("general", "Go Tipps", "Use goroutines for concurrency.", ["go"])
    client.post("/memories/embed", json={"filepath": str(path)})

    resp = client.post("/chat", json={"message": "Go Tipps?", "session_id": "src-test"})
    assert resp.status_code == 200
    sources = resp.json()["sources"]
    # Sources include title and score
    assert all("title" in s and "score" in s for s in sources)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def test_new_session_created_automatically(client):
    resp = client.post("/chat", json={"message": "Hallo", "session_id": "new-42"})
    assert resp.status_code == 200
    assert "new-42" in main_module._sessions


def test_session_stores_conversation_turns(client):
    sid = "turn-test"
    client.post("/chat", json={"message": "Erste Frage", "session_id": sid})
    client.post("/chat", json={"message": "Zweite Frage", "session_id": sid})
    session = main_module._sessions[sid]
    assert session.turn_count() == 2


def test_session_history_passed_to_engine(client):
    """Second request should include prior turn in messages sent to Ollama."""
    sid = "history-test"
    chat_calls = []

    def _route(url, *args, **kwargs):
        resp = MagicMock()
        if "/api/embeddings" in url:
            resp.json.return_value = {"embedding": FAKE_EMBEDDING}
        else:
            resp.json.return_value = {"message": {"content": "ok"}}
            chat_calls.append(kwargs)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("requests.post", side_effect=_route):
        client.post("/chat", json={"message": "Runde 1", "session_id": sid})
        client.post("/chat", json={"message": "Runde 2", "session_id": sid})

    second_call_messages = chat_calls[1]["json"]["messages"]
    roles = [m["role"] for m in second_call_messages]
    # system + user(R1) + assistant(R1) + user(R2)
    assert roles == ["system", "user", "assistant", "user"]


def test_delete_session(client):
    client.post("/chat", json={"message": "x", "session_id": "del-me"})
    assert "del-me" in main_module._sessions

    resp = client.delete("/sessions/del-me")
    assert resp.status_code == 204
    assert "del-me" not in main_module._sessions


def test_delete_nonexistent_session_is_noop(client):
    resp = client.delete("/sessions/ghost-session")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Sync endpoint
# ---------------------------------------------------------------------------

def test_sync_endpoint(client, tmp_memories):
    save_memory("general", "Sync Test", "content", [])
    resp = client.post("/memories/sync")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "synced" in data and "skipped" in data


def test_sync_idempotent(client, tmp_memories):
    save_memory("general", "Stable", "content", [])
    r1 = client.post("/memories/sync").json()
    r2 = client.post("/memories/sync").json()
    assert r1["synced"] == 1
    assert r2["synced"] == 0
    assert r2["skipped"] == 1


# ---------------------------------------------------------------------------
# Session summary
# ---------------------------------------------------------------------------

def test_session_summary_endpoint(client):
    client.post("/chat", json={"message": "Was ist Elephant?", "session_id": "sum-s"})

    summary_resp = MagicMock()
    summary_resp.json.return_value = {"message": {"content": "Elephant ist ein Memory-System."}}
    summary_resp.raise_for_status = MagicMock()

    with patch("elephant.chat.history.requests.post", return_value=summary_resp):
        resp = client.get("/sessions/sum-s/summary")

    assert resp.status_code == 200
    assert resp.json()["summary"] == "Elephant ist ein Memory-System."


def test_session_summary_404_for_unknown(client):
    resp = client.get("/sessions/does-not-exist/summary")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Close session endpoint
# ---------------------------------------------------------------------------

def test_close_session_returns_closing_status(client):
    client.post("/chat", json={"message": "Hallo", "session_id": "close-1"})
    resp = client.post("/sessions/close-1/close")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "close-1"
    assert data["status"] == "closing"
    assert data["turns"] == 1


def test_close_session_removes_session(client):
    client.post("/chat", json={"message": "Hallo", "session_id": "close-2"})
    assert "close-2" in main_module._sessions
    client.post("/sessions/close-2/close")
    assert "close-2" not in main_module._sessions


def test_close_session_404_for_unknown(client):
    resp = client.post("/sessions/ghost-close/close")
    assert resp.status_code == 404


def test_close_session_saves_conversation_summary(client, tmp_memories):
    """Background task persists a summary file in conversations/."""
    client.post("/chat", json={"message": "Was ist Elephant?", "session_id": "close-s"})
    client.post("/sessions/close-s/close")
    conv_files = list((tmp_memories / "conversations").iterdir())
    assert len(conv_files) == 1
    assert conv_files[0].name.startswith("session_close")


def test_close_session_summary_content(client, tmp_memories):
    """Summary file content comes from Ollama's export_summary response."""
    client.post("/chat", json={"message": "Python Projekt", "session_id": "close-c"})
    client.post("/sessions/close-c/close")
    conv_files = list((tmp_memories / "conversations").iterdir())
    assert len(conv_files) == 1
    content = conv_files[0].read_text()
    assert FAKE_CHAT_REPLY in content


def test_close_session_turn_count_reflects_history(client):
    """turn_count in response equals number of completed user+assistant pairs."""
    sid = "close-turns"
    client.post("/chat", json={"message": "Eins", "session_id": sid})
    client.post("/chat", json={"message": "Zwei", "session_id": sid})
    client.post("/chat", json={"message": "Drei", "session_id": sid})
    resp = client.post(f"/sessions/{sid}/close")
    assert resp.json()["turns"] == 3


# ---------------------------------------------------------------------------
# Auto-extraction background task
# ---------------------------------------------------------------------------

def test_auto_extract_not_triggered_below_four_messages(client):
    """Single chat turn (2 messages) must NOT trigger extract_and_save."""
    extract_mock = MagicMock(return_value=0)
    main_module._engine.extract_and_save = extract_mock
    client.post("/chat", json={"message": "Erste Frage", "session_id": "ae-1"})
    extract_mock.assert_not_called()


def test_auto_extract_triggered_at_four_messages(client):
    """Second chat turn (4 messages total) must trigger extract_and_save once."""
    extract_mock = MagicMock(return_value=0)
    main_module._engine.extract_and_save = extract_mock
    sid = "ae-2"
    client.post("/chat", json={"message": "Runde 1", "session_id": sid})
    client.post("/chat", json={"message": "Runde 2", "session_id": sid})
    extract_mock.assert_called_once()


def test_auto_extract_called_with_full_conversation_snapshot(client):
    """extract_and_save receives all messages up to that point."""
    captured: list[list[dict]] = []
    original = main_module._engine.extract_and_save

    def _capture(conv):
        captured.append(conv)
        return 0

    main_module._engine.extract_and_save = _capture
    sid = "ae-snap"
    client.post("/chat", json={"message": "Hallo", "session_id": sid})
    client.post("/chat", json={"message": "Wie geht's?", "session_id": sid})

    # Background ran synchronously in TestClient
    assert len(captured) == 1
    assert len(captured[0]) == 4  # user + assistant + user + assistant
    assert captured[0][0]["role"] == "user"
    assert captured[0][1]["role"] == "assistant"

    main_module._engine.extract_and_save = original


def test_auto_extract_triggered_again_on_subsequent_turns(client):
    """extract_and_save fires on every turn once the threshold is reached."""
    extract_mock = MagicMock(return_value=0)
    main_module._engine.extract_and_save = extract_mock
    sid = "ae-multi"
    for i in range(4):
        client.post("/chat", json={"message": f"Frage {i}", "session_id": sid})
    # Turns 2, 3, 4 each trigger extraction (6, 8 msgs also >= 4)
    assert extract_mock.call_count == 3

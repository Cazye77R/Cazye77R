"""Unit tests for ChatEngine and ConversationHistory."""

from unittest.mock import MagicMock, patch

import pytest

from elephant.chat.engine import ChatEngine
from elephant.chat.history import ConversationHistory

FAKE_SOURCES = [
    {
        "chunk": "# Python Tips\n\nUse list comprehensions.",
        "metadata": {"title": "Python Tips", "importance": 0.8, "tags": ["python"]},
        "score": 0.95,
        "source_file": "/data/memories/general/python_tips.md",
    }
]


@pytest.fixture(autouse=True)
def mock_search():
    with patch("elephant.chat.engine.search_similar", return_value=FAKE_SOURCES):
        yield


@pytest.fixture
def ollama_mock():
    resp = MagicMock()
    resp.json.return_value = {"message": {"content": "Das ist die Antwort."}}
    resp.raise_for_status = MagicMock()
    with patch("elephant.chat.engine.requests.post", return_value=resp) as m:
        yield m


# ---------------------------------------------------------------------------
# ChatEngine
# ---------------------------------------------------------------------------

def test_chat_returns_response_string(ollama_mock):
    response, _ = ChatEngine().chat("Was ist Python?")
    assert response == "Das ist die Antwort."


def test_chat_returns_sources(ollama_mock):
    _, sources = ChatEngine().chat("Was ist Python?")
    assert len(sources) == 1
    assert sources[0]["chunk"].startswith("# Python Tips")


def test_system_prompt_contains_memory_markers(ollama_mock):
    ChatEngine().chat("Frage?")
    messages = ollama_mock.call_args[1]["json"]["messages"]
    system = next(m for m in messages if m["role"] == "system")
    assert "[MEMORY START]" in system["content"]
    assert "[MEMORY END]" in system["content"]
    assert "Use list comprehensions." in system["content"]


def test_system_prompt_no_context_when_empty_search(ollama_mock):
    with patch("elephant.chat.engine.search_similar", return_value=[]):
        ChatEngine().chat("Frage?")
    messages = ollama_mock.call_args[1]["json"]["messages"]
    system = messages[0]["content"]
    assert "[MEMORY START]" not in system


def test_multiple_chunks_separated_by_dashes(ollama_mock):
    two_chunks = FAKE_SOURCES + [
        {**FAKE_SOURCES[0], "chunk": "# Go Tips\n\nUse goroutines."}
    ]
    with patch("elephant.chat.engine.search_similar", return_value=two_chunks):
        ChatEngine().chat("Vergleich?")
    system = ollama_mock.call_args[1]["json"]["messages"][0]["content"]
    assert "---" in system
    assert "Use goroutines." in system


def test_conversation_history_inserted_between_system_and_new_user(ollama_mock):
    history = [
        {"role": "user", "content": "Hallo"},
        {"role": "assistant", "content": "Hi!"},
    ]
    ChatEngine().chat("Nächste Frage?", conversation_history=history)
    messages = ollama_mock.call_args[1]["json"]["messages"]
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "user"]


def test_user_message_is_last_message(ollama_mock):
    ChatEngine().chat("Spezifische Frage?")
    last = ollama_mock.call_args[1]["json"]["messages"][-1]
    assert last["role"] == "user"
    assert last["content"] == "Spezifische Frage?"


def test_custom_model_forwarded_to_ollama(ollama_mock):
    ChatEngine(model="mistral").chat("Test")
    assert ollama_mock.call_args[1]["json"]["model"] == "mistral"


def test_stream_is_always_false(ollama_mock):
    ChatEngine().chat("Test")
    assert ollama_mock.call_args[1]["json"]["stream"] is False


def test_empty_history_defaults_gracefully(ollama_mock):
    response, _ = ChatEngine().chat("Test", conversation_history=None)
    assert response == "Das ist die Antwort."


# ---------------------------------------------------------------------------
# ConversationHistory
# ---------------------------------------------------------------------------

def test_history_initially_empty():
    h = ConversationHistory()
    assert h.messages() == []
    assert h.turn_count() == 0


def test_history_add_and_retrieve():
    h = ConversationHistory()
    h.add("user", "Hallo")
    h.add("assistant", "Hi!")
    msgs = h.messages()
    assert len(msgs) == 2
    assert msgs[0] == {"role": "user", "content": "Hallo"}
    assert msgs[1] == {"role": "assistant", "content": "Hi!"}


def test_history_messages_returns_copy():
    h = ConversationHistory()
    h.add("user", "test")
    snapshot = h.messages()
    snapshot.clear()
    assert len(h.messages()) == 1


def test_history_sliding_window_evicts_oldest_turn():
    h = ConversationHistory(max_turns=2)
    for i in range(3):
        h.add("user", f"msg {i}")
        h.add("assistant", f"resp {i}")
    msgs = h.messages()
    assert len(msgs) == 4  # 2 turns * 2 messages each
    assert msgs[0]["content"] == "msg 1"  # turn 0 (msg 0 + resp 0) evicted
    assert msgs[1]["content"] == "resp 1"


def test_history_sliding_window_exactly_at_limit():
    h = ConversationHistory(max_turns=2)
    for i in range(2):
        h.add("user", f"msg {i}")
        h.add("assistant", f"resp {i}")
    assert len(h.messages()) == 4  # exactly at limit, nothing evicted


def test_history_turn_count():
    h = ConversationHistory()
    for _ in range(5):
        h.add("user", "x")
        h.add("assistant", "y")
    assert h.turn_count() == 5


def test_history_export_summary_empty():
    assert "Keine" in ConversationHistory().export_summary()


def test_history_export_summary_calls_ollama():
    h = ConversationHistory()
    h.add("user", "Was ist Python?")
    h.add("assistant", "Python ist eine Programmiersprache.")

    resp = MagicMock()
    resp.json.return_value = {"message": {"content": "Eine Zusammenfassung."}}
    resp.raise_for_status = MagicMock()

    with patch("elephant.chat.history.requests.post", return_value=resp) as mock:
        result = h.export_summary()

    assert result == "Eine Zusammenfassung."
    assert mock.called


def test_history_export_summary_transcript_included():
    h = ConversationHistory()
    h.add("user", "UNIQUE_Q_XYZ")
    h.add("assistant", "UNIQUE_A_ABC")

    resp = MagicMock()
    resp.json.return_value = {"message": {"content": "summary"}}
    resp.raise_for_status = MagicMock()

    with patch("elephant.chat.history.requests.post", return_value=resp) as mock:
        h.export_summary()

    prompt = mock.call_args[1]["json"]["messages"][0]["content"]
    assert "UNIQUE_Q_XYZ" in prompt
    assert "UNIQUE_A_ABC" in prompt
    assert "Fasse" in prompt

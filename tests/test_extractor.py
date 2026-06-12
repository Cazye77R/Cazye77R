"""Unit tests for MemoryExtractor (extract_facts + deduplicate)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from elephant.memory.extractor import MemoryExtractor, MemoryFact

CONVERSATION = [
    {"role": "user", "content": "Ich arbeite an einem Python-Projekt namens Elephant."},
    {"role": "assistant", "content": "Klingt interessant! Was macht Elephant?"},
    {"role": "user", "content": "Es ist ein Memory-System mit RAG-Funktionalität."},
    {"role": "assistant", "content": "Welche Technologien verwendest du?"},
]

VALID_FACTS_JSON = [
    {
        "fact": "Der User arbeitet an einem Python-Projekt namens Elephant.",
        "category": "projects",
        "tags": ["python", "elephant"],
        "importance": 0.8,
    },
    {
        "fact": "Elephant ist ein Memory-System mit RAG-Funktionalität.",
        "category": "projects",
        "tags": ["rag", "memory"],
        "importance": 0.9,
    },
]


@pytest.fixture
def ollama_mock():
    resp = MagicMock()
    resp.json.return_value = {"message": {"content": json.dumps(VALID_FACTS_JSON)}}
    resp.raise_for_status = MagicMock()
    with patch("elephant.memory.extractor.requests.post", return_value=resp) as m:
        yield m


# ---------------------------------------------------------------------------
# extract_facts
# ---------------------------------------------------------------------------

def test_extract_facts_returns_memory_fact_instances(ollama_mock):
    facts = MemoryExtractor().extract_facts(CONVERSATION)
    assert len(facts) == 2
    assert all(isinstance(f, MemoryFact) for f in facts)


def test_extract_facts_correct_values(ollama_mock):
    facts = MemoryExtractor().extract_facts(CONVERSATION)
    assert facts[0].fact == "Der User arbeitet an einem Python-Projekt namens Elephant."
    assert facts[0].category == "projects"
    assert facts[0].tags == ["python", "elephant"]
    assert facts[0].importance == 0.8


def test_extract_facts_empty_conversation():
    assert MemoryExtractor().extract_facts([]) == []


def test_extract_facts_invalid_json_returns_empty():
    resp = MagicMock()
    resp.json.return_value = {"message": {"content": "Das ist kein JSON"}}
    resp.raise_for_status = MagicMock()
    with patch("elephant.memory.extractor.requests.post", return_value=resp):
        assert MemoryExtractor().extract_facts(CONVERSATION) == []


def test_extract_facts_json_fenced_in_code_block():
    resp = MagicMock()
    resp.json.return_value = {
        "message": {"content": f"```json\n{json.dumps(VALID_FACTS_JSON)}\n```"}
    }
    resp.raise_for_status = MagicMock()
    with patch("elephant.memory.extractor.requests.post", return_value=resp):
        facts = MemoryExtractor().extract_facts(CONVERSATION)
    assert len(facts) == 2


def test_extract_facts_skips_invalid_category():
    bad = VALID_FACTS_JSON + [{"fact": "ok", "category": "INVALID", "tags": [], "importance": 0.5}]
    resp = MagicMock()
    resp.json.return_value = {"message": {"content": json.dumps(bad)}}
    resp.raise_for_status = MagicMock()
    with patch("elephant.memory.extractor.requests.post", return_value=resp):
        facts = MemoryExtractor().extract_facts(CONVERSATION)
    assert len(facts) == 2  # invalid item silently skipped


def test_extract_facts_importance_clamped_by_pydantic():
    data = [{"fact": "Test", "category": "general", "tags": [], "importance": 1.5}]
    resp = MagicMock()
    resp.json.return_value = {"message": {"content": json.dumps(data)}}
    resp.raise_for_status = MagicMock()
    with patch("elephant.memory.extractor.requests.post", return_value=resp):
        facts = MemoryExtractor().extract_facts(CONVERSATION)
    assert facts == []  # ValidationError: 1.5 > 1.0 → skipped


def test_extract_facts_transcript_included_in_prompt(ollama_mock):
    MemoryExtractor().extract_facts(CONVERSATION)
    prompt = ollama_mock.call_args[1]["json"]["messages"][0]["content"]
    assert "Elephant" in prompt
    assert "Memory-System" in prompt
    assert "RAG" in prompt


def test_extract_facts_custom_model_forwarded(ollama_mock):
    MemoryExtractor(model="mistral").extract_facts(CONVERSATION)
    assert ollama_mock.call_args[1]["json"]["model"] == "mistral"


def test_extract_facts_stream_disabled(ollama_mock):
    MemoryExtractor().extract_facts(CONVERSATION)
    assert ollama_mock.call_args[1]["json"]["stream"] is False


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

def test_deduplicate_no_collection_returns_all():
    facts = [MemoryFact(fact="Test", category="general", tags=[], importance=0.5)]
    result = MemoryExtractor().deduplicate(facts, [], collection=None)
    assert result == facts


def test_deduplicate_no_existing_returns_all():
    facts = [MemoryFact(fact="Test", category="general", tags=[], importance=0.5)]
    result = MemoryExtractor().deduplicate(facts, [], collection=MagicMock())
    assert result == facts


def test_deduplicate_filters_above_threshold():
    facts = [MemoryFact(fact="Python is great", category="general", tags=[], importance=0.5)]
    with patch("elephant.memory.extractor.search_similar", return_value=[{"score": 0.92}]):
        result = MemoryExtractor().deduplicate(facts, [MagicMock()], collection=MagicMock())
    assert result == []


def test_deduplicate_keeps_below_threshold():
    facts = [MemoryFact(fact="Something novel", category="general", tags=[], importance=0.5)]
    with patch("elephant.memory.extractor.search_similar", return_value=[{"score": 0.60}]):
        result = MemoryExtractor().deduplicate(facts, [MagicMock()], collection=MagicMock())
    assert len(result) == 1


def test_deduplicate_threshold_exactly_at_boundary():
    facts = [MemoryFact(fact="Borderline", category="general", tags=[], importance=0.5)]
    # At threshold → filtered
    with patch("elephant.memory.extractor.search_similar", return_value=[{"score": 0.85}]):
        assert MemoryExtractor().deduplicate(facts, [MagicMock()], collection=MagicMock()) == []
    # Just below threshold → kept
    with patch("elephant.memory.extractor.search_similar", return_value=[{"score": 0.849}]):
        assert len(MemoryExtractor().deduplicate(facts, [MagicMock()], collection=MagicMock())) == 1


def test_deduplicate_empty_search_result_keeps_fact():
    facts = [MemoryFact(fact="Brand new", category="general", tags=[], importance=0.5)]
    with patch("elephant.memory.extractor.search_similar", return_value=[]):
        result = MemoryExtractor().deduplicate(facts, [MagicMock()], collection=MagicMock())
    assert len(result) == 1


def test_deduplicate_custom_threshold():
    facts = [MemoryFact(fact="Test", category="general", tags=[], importance=0.5)]
    # score=0.70 — above a custom threshold of 0.60, should be filtered
    with patch("elephant.memory.extractor.search_similar", return_value=[{"score": 0.70}]):
        result = MemoryExtractor().deduplicate(
            facts, [MagicMock()], collection=MagicMock(), similarity_threshold=0.60
        )
    assert result == []


def test_deduplicate_processes_each_fact_independently():
    facts = [
        MemoryFact(fact="Fact A", category="general", tags=[], importance=0.5),
        MemoryFact(fact="Fact B", category="general", tags=[], importance=0.5),
    ]
    scores = iter([{"score": 0.95}, {"score": 0.40}])
    with patch("elephant.memory.extractor.search_similar", side_effect=lambda *a, **kw: [next(scores)]):
        result = MemoryExtractor().deduplicate(facts, [MagicMock()], collection=MagicMock())
    # Fact A filtered (0.95 >= 0.85), Fact B kept (0.40 < 0.85)
    assert len(result) == 1
    assert result[0].fact == "Fact B"

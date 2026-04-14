"""Tests for file loading and chunking (loader.py)."""
import sys
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from text_search.loader import _chunk_text, _split_sentences, load_file


def test_split_sentences_basic():
    """Sentence splitter splits on . ! ? boundaries."""
    sents = _split_sentences("First sentence. Second one! Third?")
    assert sents == ["First sentence.", "Second one!", "Third?"]


def test_split_sentences_empty():
    """Empty or whitespace-only input returns an empty list."""
    assert _split_sentences("") == []
    assert _split_sentences("   ") == []


def test_chunk_text_no_sentence_split():
    """No chunk boundary falls in the middle of a sentence."""
    # 10 short sentences, chunk_size=10 words → multiple chunks
    text = " ".join(f"Sentence number {i} ends here." for i in range(10))
    chunks = _chunk_text(text, source="t.txt", chunk_size=10, overlap=0)
    for c in chunks:
        # Each chunk must end with sentence-ending punctuation (last non-space char)
        last_char = c.text.rstrip()[-1]
        assert last_char in ".!?", f"chunk does not end on sentence boundary: {c.text!r}"


def test_chunk_text_overlap_creates_shared_content():
    """With overlap > 0 adjacent chunks share words from the boundary."""
    text = " ".join(f"Word{i}." for i in range(40))
    chunks = _chunk_text(text, source="t.txt", chunk_size=10, overlap=5)
    assert len(chunks) >= 2
    tail = set(chunks[0].text.split()[-5:])
    head = set(chunks[1].text.split()[:5])
    assert tail & head, "expected overlap between consecutive chunks"


def test_load_file_txt(tmp_path: Path):
    """load_file reads a .txt file and returns non-empty chunks."""
    f = tmp_path / "sample.txt"
    f.write_text("This is the first sentence. This is the second sentence.", encoding="utf-8")
    chunks = load_file(f, chunk_size=20, overlap=0)
    assert len(chunks) >= 1
    assert all(c.source == "sample.txt" for c in chunks)
    assert all(c.text.strip() for c in chunks)


def test_load_file_csv(tmp_path: Path):
    """load_file reads a .csv file with one chunk per data row."""
    f = tmp_path / "data.csv"
    f.write_text("name,value\nalpha,1\nbeta,2\ngamma,3\n", encoding="utf-8")
    chunks = load_file(f)
    assert len(chunks) == 3
    assert "alpha" in chunks[0].text


def test_load_pdf_corrupt_file_raises(tmp_path: Path):
    """pdfplumber.open() error on a corrupt file is wrapped in RuntimeError."""
    bad_pdf = tmp_path / "corrupt.pdf"
    bad_pdf.write_bytes(b"this is not a pdf file at all")

    # Inject a mock so the test doesn't require a working pdfplumber install.
    mock_plumber = MagicMock()
    mock_plumber.open.side_effect = Exception("PDF parse error")
    sys.modules["pdfplumber"] = mock_plumber
    try:
        with pytest.raises(RuntimeError, match="konnte nicht als PDF geöffnet werden"):
            load_file(bad_pdf)
    finally:
        sys.modules.pop("pdfplumber", None)


def test_load_pdf_nonexistent_raises():
    """FileNotFoundError from pdfplumber.open() is wrapped in RuntimeError."""
    mock_plumber = MagicMock()
    mock_plumber.open.side_effect = FileNotFoundError("no such file")
    sys.modules["pdfplumber"] = mock_plumber
    try:
        with pytest.raises(RuntimeError, match="konnte nicht als PDF geöffnet werden"):
            load_file(Path("/tmp/does_not_exist_xyz.pdf"))
    finally:
        sys.modules.pop("pdfplumber", None)


def test_load_pdf_bad_page_skipped_with_warning(tmp_path: Path):
    """When page.extract_text() raises, the page is skipped with a warning — no crash."""
    mock_page = MagicMock()
    mock_page.extract_text.side_effect = ValueError("simulated page parse error")

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)

    mock_plumber = MagicMock()
    mock_plumber.open.return_value = mock_pdf
    sys.modules["pdfplumber"] = mock_plumber
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            chunks = load_file(tmp_path / "fake.pdf")
    finally:
        sys.modules.pop("pdfplumber", None)

    assert chunks == [], "bad page must be skipped, result must be empty"
    assert any("konnte nicht gelesen werden" in str(w.message) for w in caught), (
        "expected a warning about the unreadable page"
    )

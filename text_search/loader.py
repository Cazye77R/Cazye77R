"""Load text files of various formats and split them into searchable chunks."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Chunk:
    text: str
    source: str
    chunk_id: int
    page: int | None
    line_start: int | None


def load_file(path: Path, chunk_size: int = 300, overlap: int = 50) -> List[Chunk]:
    """Dispatch to the correct loader based on file suffix."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path, chunk_size=chunk_size, overlap=overlap)
    if suffix == ".csv":
        return _load_csv(path)  # CSV: 1 Chunk pro Zeile, chunk_size irrelevant
    return _load_text(path, chunk_size=chunk_size, overlap=overlap)


def _load_text(path: Path, chunk_size: int = 300, overlap: int = 50) -> List[Chunk]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return _chunk_text(text, source=path.name, base_line=1,
                       chunk_size=chunk_size, overlap=overlap)


def _load_csv(path: Path) -> List[Chunk]:
    import csv

    chunks: List[Chunk] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        header_str = ", ".join(header) if header else ""
        for row_idx, row in enumerate(reader):
            row_text = header_str + ": " + ", ".join(row) if header_str else ", ".join(row)
            row_text = row_text.strip()
            if row_text:
                chunks.append(
                    Chunk(
                        text=row_text,
                        source=path.name,
                        chunk_id=row_idx,
                        page=None,
                        line_start=row_idx + 2,  # 1-based, +1 for header
                    )
                )
    return chunks


def _load_pdf(path: Path, chunk_size: int = 300, overlap: int = 50) -> List[Chunk]:
    import pdfplumber

    chunks: List[Chunk] = []
    chunk_id = 0
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            page_chunks = _chunk_text(
                text,
                source=path.name,
                base_line=None,
                page=page_num,
                chunk_size=chunk_size,
                overlap=overlap,
                start_chunk_id=chunk_id,
            )
            chunks.extend(page_chunks)
            chunk_id += len(page_chunks)
    return chunks


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences on . ! ? followed by whitespace or end of string.

    Limitation: does not handle abbreviations (e.g. 'Dr. Smith') — acceptable
    for a zero-dependency implementation using only re.split().
    """
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _chunk_text(
    text: str,
    source: str,
    base_line: int | None = 1,
    page: int | None = None,
    chunk_size: int = 300,
    overlap: int = 50,
    start_chunk_id: int = 0,
) -> List[Chunk]:
    """Split text into chunks by accumulating whole sentences up to chunk_size words.

    A new chunk begins where the previous one ended, minus an overlap tail of
    ~overlap words (by rewinding to the sentences that cover them). This keeps
    sentences intact — no sentence is split across chunk boundaries.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: List[Chunk] = []
    chunk_id = start_chunk_id
    i = 0  # index of the first sentence of the current chunk

    while i < len(sentences):
        # Accumulate sentences until chunk_size words is reached.
        # Always include at least one sentence even if it alone exceeds chunk_size.
        current: List[str] = []
        word_count = 0
        j = i
        while j < len(sentences):
            sent_words = len(sentences[j].split())
            if current and word_count + sent_words > chunk_size:
                break
            current.append(sentences[j])
            word_count += sent_words
            j += 1

        chunk_text = " ".join(current)

        # Approximate line_start: count newlines in all text before this chunk
        line_start: int | None = None
        if base_line is not None:
            prefix = " ".join(sentences[:i])
            line_start = base_line + prefix.count("\n")

        chunks.append(Chunk(
            text=chunk_text,
            source=source,
            chunk_id=chunk_id,
            page=page,
            line_start=line_start,
        ))
        chunk_id += 1

        # Determine next start position with overlap.
        # Walk backward through sentences of this chunk until ~overlap words
        # are covered; the first of those sentences becomes the next start.
        # next_i > i is guaranteed to prevent infinite loops.
        if overlap > 0 and j > i + 1:
            overlap_counted = 0
            k = j - 1
            while k > i and overlap_counted < overlap:
                overlap_counted += len(sentences[k].split())
                k -= 1
            i = max(i + 1, k + 1)
        else:
            i = j

    return chunks

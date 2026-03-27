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


def _chunk_text(
    text: str,
    source: str,
    base_line: int | None = 1,
    page: int | None = None,
    chunk_size: int = 300,
    overlap: int = 50,
    start_chunk_id: int = 0,
) -> List[Chunk]:
    """Split text into overlapping word-window chunks."""
    words = re.split(r"(\s+)", text)
    tokens: List[str] = []
    for w in words:
        stripped = w.strip()
        if stripped:
            tokens.append(stripped)

    if not tokens:
        return []

    chunks: List[Chunk] = []
    step = max(1, chunk_size - overlap)
    chunk_id = start_chunk_id

    for start in range(0, len(tokens), step):
        end = start + chunk_size
        window = tokens[start:end]
        if not window:
            break
        chunk_text = " ".join(window)

        line_start: int | None = None
        if base_line is not None:
            prefix_text = " ".join(tokens[:start])
            line_start = base_line + prefix_text.count("\n")

        chunks.append(
            Chunk(
                text=chunk_text,
                source=source,
                chunk_id=chunk_id,
                page=page,
                line_start=line_start,
            )
        )
        chunk_id += 1

        if end >= len(tokens):
            break

    return chunks

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter
import markdown2


_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_INLINE_TAG_RE = re.compile(r"(?<!\w)#([\w/-]+)")
_WIKILINK_HREF_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def extract_frontmatter(text: str) -> dict[str, Any]:
    try:
        post = frontmatter.loads(text)
        return dict(post.metadata)
    except Exception:
        return {}


def extract_wikilinks(text: str) -> list[str]:
    return [m.group(1).strip() for m in _WIKILINK_RE.finditer(text)]


def extract_tags(text: str, fm: dict[str, Any] | None = None) -> list[str]:
    inline = _INLINE_TAG_RE.findall(text)
    yaml_tags: list[str] = []
    if fm:
        raw = fm.get("tags", [])
        if isinstance(raw, list):
            yaml_tags = [str(t) for t in raw]
        elif isinstance(raw, str):
            yaml_tags = [t.strip() for t in raw.split(",") if t.strip()]
    seen: set[str] = set()
    result: list[str] = []
    for t in yaml_tags + inline:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _replace_wikilink(match: re.Match) -> str:
    target = match.group(1).strip()
    alias = match.group(2).strip() if match.group(2) else target
    slug = target.replace(" ", "_")
    return f'<a href="/note/{slug}">{alias}</a>'


def render_markdown(text: str) -> str:
    # Strip YAML frontmatter before rendering
    try:
        post = frontmatter.loads(text)
        body = post.content
    except Exception:
        body = text

    # Replace wikilinks before markdown conversion
    body = _WIKILINK_HREF_RE.sub(_replace_wikilink, body)

    return markdown2.markdown(
        body,
        extras=["tables", "fenced-code-blocks", "wiki-tables", "strike", "header-ids"],
    )


def parse_note(filepath: str | Path) -> dict[str, Any]:
    path = Path(filepath)
    raw_text = path.read_text(encoding="utf-8")

    try:
        post = frontmatter.loads(raw_text)
        fm = dict(post.metadata)
        body = post.content
    except Exception:
        fm = {}
        body = raw_text

    stat = path.stat()
    title = fm.get("title") or path.stem
    tags = extract_tags(body, fm)
    wikilinks = extract_wikilinks(body)
    word_count = len(body.split())

    fm_created = fm.get("created")
    if isinstance(fm_created, str):
        try:
            created_at = datetime.fromisoformat(fm_created)
        except ValueError:
            created_at = datetime.fromtimestamp(stat.st_ctime)
    elif isinstance(fm_created, datetime):
        created_at = fm_created
    else:
        created_at = datetime.fromtimestamp(stat.st_ctime)

    return {
        "title": title,
        "content": body,
        "frontmatter": fm,
        "tags": tags,
        "wikilinks": wikilinks,
        "raw_text": raw_text,
        "word_count": word_count,
        "created_at": created_at,
        "modified_at": datetime.fromtimestamp(stat.st_mtime),
        "filename": path.name,
        "filepath": str(path),
    }

"""Reusable note card component."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import streamlit as st


def note_card_html(
    note: dict[str, Any],
    selected: bool = False,
    max_excerpt: int = 150,
) -> str:
    title = _esc(note.get("title", "Ohne Titel"))
    content = note.get("content", "")
    excerpt = _esc(content[:max_excerpt]) + ("…" if len(content) > max_excerpt else "")
    tags = note.get("tags", [])[:5]
    word_count = note.get("word_count", 0)
    modified = _fmt_date(note.get("modified_at"))

    border_color = "#89b4fa" if selected else "#45475a"
    tag_badges = "".join(
        f'<span style="background:#1e1e2e;color:#89b4fa;border:1px solid #89b4fa;'
        f'border-radius:10px;padding:1px 7px;font-size:11px;margin-right:4px;">{_esc(t)}</span>'
        for t in tags
    )

    return (
        f'<div style="background:#313244;border:1.5px solid {border_color};border-radius:8px;'
        f'padding:12px 14px;margin-bottom:6px;">'
        f'<div style="font-weight:600;color:#cdd6f4;margin-bottom:4px;font-size:14px;">{title}</div>'
        f'<div style="color:#a6adc8;font-size:12px;margin-bottom:6px;line-height:1.4;">{excerpt}</div>'
        f'<div style="margin-bottom:4px;">{tag_badges}</div>'
        f'<div style="color:#6c7086;font-size:11px;">{word_count} Wörter&nbsp;·&nbsp;{modified}</div>'
        f"</div>"
    )


def note_card_button(
    note: dict[str, Any],
    selected: bool = False,
    on_click: Callable | None = None,
) -> bool:
    """Render note card HTML + an invisible select button. Returns True if clicked."""
    st.markdown(note_card_html(note, selected=selected), unsafe_allow_html=True)
    filename = note.get("filename", "")
    clicked = st.button(
        "Öffnen",
        key=f"card_btn_{filename}",
        use_container_width=True,
        type="primary" if selected else "secondary",
    )
    if clicked and on_click:
        on_click(filename)
    return clicked


def tag_badge(tag: str, color: str = "#89b4fa") -> str:
    return (
        f'<span style="background:#1e1e2e;color:{color};border:1px solid {color};'
        f'border-radius:10px;padding:2px 9px;font-size:12px;margin-right:4px;'
        f'display:inline-block;margin-bottom:4px;">{_esc(tag)}</span>'
    )


def stat_card_html(icon: str, label: str, value: str | int) -> str:
    return (
        f'<div style="background:#313244;border:1px solid #45475a;border-radius:10px;'
        f'padding:18px;text-align:center;">'
        f'<div style="font-size:28px;">{icon}</div>'
        f'<div style="font-size:22px;font-weight:700;color:#cdd6f4;margin:4px 0;">{value}</div>'
        f'<div style="color:#a6adc8;font-size:13px;">{label}</div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_date(val: Any) -> str:
    if isinstance(val, datetime):
        return val.strftime("%d.%m.%Y")
    if isinstance(val, str) and val:
        return val[:10]
    return "–"

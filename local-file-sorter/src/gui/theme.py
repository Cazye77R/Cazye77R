"""Central design tokens – every GUI component imports from here only."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG_DEEP        = "#0a0e14"   # main window background
SURFACE        = "#161b22"   # card / panel background
SURFACE_HI     = "#1f2937"   # hover / selected surface
ACCENT_PRIMARY = "#00d9ff"   # cyan – primary action
ACCENT_DIM     = "#4cc9f0"   # softer cyan – secondary indicators
SUCCESS        = "#00ff9d"   # operation success
WARNING        = "#ffa500"   # non-critical warning
ERROR          = "#ff3860"   # error / danger
TEXT           = "#e6edf3"   # primary text
TEXT_MUTED     = "#8b949e"   # muted / secondary text
BORDER_ACTIVE  = "#00d9ff"   # 1 px border on active / focused elements

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
RADIUS_BUTTON = 6
RADIUS_CARD   = 10

# ---------------------------------------------------------------------------
# Typography – tuples accepted by CustomTkinter and ttk
# ---------------------------------------------------------------------------
_MONO = "Courier New"   # guaranteed fallback; overridden at runtime if better font found
_SANS = ""              # empty = CTk system default

FONT_MONO      = (_MONO, 12)
FONT_MONO_SM   = (_MONO, 10)
FONT_MONO_LG   = (_MONO, 14)
FONT_MONO_BOLD = (_MONO, 12, "bold")
FONT_BODY      = (_SANS, 13)
FONT_BODY_SM   = (_SANS, 11)
FONT_BODY_BOLD = (_SANS, 13, "bold")
FONT_TITLE     = (_SANS, 15, "bold")
FONT_LABEL     = (_SANS, 11)
FONT_SECTION   = (_SANS, 10, "bold")   # ALL-CAPS section headers


def resolve_mono_family() -> str:
    """Return the best available monospace font family after Tk is initialised."""
    candidates = [
        "JetBrains Mono",
        "Cascadia Mono",
        "Cascadia Code",
        "Consolas",
        "Courier New",
    ]
    try:
        import tkinter.font as tkfont
        available = set(tkfont.families())
        for fam in candidates:
            if fam in available:
                return fam
    except Exception:
        pass
    return "Courier New"


def apply_mono_family(family: str) -> None:
    """Patch the module-level font tuples after the best family is known."""
    global FONT_MONO, FONT_MONO_SM, FONT_MONO_LG, FONT_MONO_BOLD
    FONT_MONO      = (family, 12)
    FONT_MONO_SM   = (family, 10)
    FONT_MONO_LG   = (family, 14)
    FONT_MONO_BOLD = (family, 12, "bold")


# ---------------------------------------------------------------------------
# CustomTkinter widget keyword defaults
# ---------------------------------------------------------------------------

def btn_primary() -> dict:
    return dict(
        fg_color=ACCENT_PRIMARY,
        hover_color=ACCENT_DIM,
        text_color=BG_DEEP,
        corner_radius=RADIUS_BUTTON,
        font=FONT_BODY_BOLD,
    )


def btn_danger() -> dict:
    return dict(
        fg_color=ERROR,
        hover_color="#cc2d4a",
        text_color=TEXT,
        corner_radius=RADIUS_BUTTON,
        font=FONT_BODY_BOLD,
    )


def btn_success() -> dict:
    return dict(
        fg_color=SUCCESS,
        hover_color="#00cc7d",
        text_color=BG_DEEP,
        corner_radius=RADIUS_BUTTON,
        font=FONT_BODY_BOLD,
    )


def btn_ghost() -> dict:
    return dict(
        fg_color=SURFACE_HI,
        hover_color="#2d3748",
        text_color=TEXT,
        border_width=1,
        border_color=SURFACE_HI,
        corner_radius=RADIUS_BUTTON,
        font=FONT_BODY,
    )


def card() -> dict:
    return dict(
        fg_color=SURFACE,
        corner_radius=RADIUS_CARD,
    )

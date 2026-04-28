# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for SecondBrain Agent
# Build:  pyinstaller second_brain.spec --clean --noconfirm
#
# Produces:  dist/SecondBrain.exe  (one self-contained file)

from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── Collect whole packages that use dynamic imports / entry-points ────────────
datas_st,    binaries_st,    hiddens_st    = collect_all("streamlit")
datas_chroma, binaries_chroma, hiddens_chroma = collect_all("chromadb")
datas_pyvis, binaries_pyvis, hiddens_pyvis  = collect_all("pyvis")
datas_alt,   binaries_alt,   hiddens_alt   = collect_all("altair")
datas_pkg,   binaries_pkg,   hiddens_pkg   = collect_all("pkg_resources")

# ── Additional hidden imports ─────────────────────────────────────────────────
extra_hiddens = [
    # SQLAlchemy dialects
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "sqlalchemy.orm",
    "sqlalchemy.ext.declarative",

    # Streamlit internals
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.web.cli",
    "streamlit.elements.widgets.button",

    # ChromaDB backends
    "chromadb.api.segment",
    "chromadb.segment.impl.metadata.sqlite",
    "chromadb.segment.impl.vector.local_persistent_hnsw",
    "chromadb.segment.impl.vector.local_hnsw",
    "hnswlib",

    # Watchdog
    "watchdog.observers",
    "watchdog.observers.polling",
    "watchdog.events",

    # Markdown / YAML / frontmatter
    "markdown2",
    "yaml",
    "frontmatter",

    # NetworkX / pyvis
    "networkx",
    "networkx.algorithms",

    # Plotly
    "plotly",
    "plotly.graph_objects",
    "plotly.express",

    # Pandas
    "pandas",

    # Pillow
    "PIL",
    "PIL.Image",

    # Misc
    "click",
    "packaging",
    "importlib_metadata",
    "typing_extensions",
    "pydantic",
    "pydantic.v1",
    "anyio",
    "httpx",
    "httpcore",
    "certifi",
    "charset_normalizer",
    "urllib3",
    "overrides",
    "posthog",
    "bcrypt",
    "mmh3",
    "onnxruntime",
    "tokenizers",
]

# ── Application data files ────────────────────────────────────────────────────
app_datas = [
    ("ui",           "ui"),
    ("core",         "core"),
    ("ai",           "ai"),
    ("plugins",      "plugins"),
    ("assets",       "assets"),
    ("requirements.txt", "."),
]

# ── Icon (optional – remove the icon= line if no .ico exists) ─────────────────
import os as _os
_ico = "assets/icon.ico"
_icon_arg = _ico if _os.path.exists(_ico) else None

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=binaries_st + binaries_chroma + binaries_pyvis + binaries_alt,
    datas=(
        app_datas
        + datas_st
        + datas_chroma
        + datas_pyvis
        + datas_alt
        + datas_pkg
    ),
    hiddenimports=(
        hiddens_st
        + hiddens_chroma
        + hiddens_pyvis
        + hiddens_alt
        + hiddens_pkg
        + extra_hiddens
    ),
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "pytest", "unittest", "test", "tests",
        "matplotlib", "tkinter", "_tkinter",
        "IPython", "ipykernel", "jupyter",
        "sphinx", "docutils",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="SecondBrain",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # keep console for startup status output
    icon=_icon_arg,
    onefile=True,
)

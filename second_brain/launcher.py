"""SecondBrain Agent – launcher / EXE entry point.

Works both as a plain `python launcher.py` script and as a PyInstaller
one-file EXE.  When frozen, sys.executable is the EXE itself so all
subprocess calls automatically use the embedded Python runtime.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths – work both for source layout and inside a PyInstaller bundle
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    # Running as PyInstaller EXE: _MEIPASS holds the extracted bundle root
    _BUNDLE_DIR: Path = Path(sys._MEIPASS)          # type: ignore[attr-defined]
    _BASE_DIR: Path = Path(sys.executable).parent
else:
    _BUNDLE_DIR = Path(__file__).resolve().parent
    _BASE_DIR = _BUNDLE_DIR

_APP_PY = _BUNDLE_DIR / "ui" / "streamlit_app.py"
_REQ_TXT = _BUNDLE_DIR / "requirements.txt"
_OLLAMA_URL = "http://localhost:11434"
_APP_URL = "http://localhost:8501"

# ---------------------------------------------------------------------------
# Step 1 – package check / auto-install
# ---------------------------------------------------------------------------

_IMPORT_MAP: dict[str, str] = {
    "PIL": "Pillow",
    "yaml": "PyYAML",
    "frontmatter": "python-frontmatter",
    "sklearn": "scikit-learn",
}

_REQUIRED_IMPORTS = [
    "streamlit", "chromadb", "networkx", "pyvis",
    "watchdog", "frontmatter", "markdown2", "yaml",
    "sqlalchemy", "PIL", "pandas", "plotly",
]


def check_python_packages() -> None:
    """Install any missing packages from requirements.txt."""
    missing = []
    for imp in _REQUIRED_IMPORTS:
        try:
            __import__(imp)
        except ImportError:
            missing.append(imp)

    if not missing:
        return

    print(f"📦 Installiere {len(missing)} fehlende Pakete…")
    req = str(_REQ_TXT) if _REQ_TXT.exists() else "requirements.txt"
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "-r", req],
            stdout=subprocess.DEVNULL if sys.platform == "win32" else None,
        )
        print("✅ Pakete installiert.")
    except subprocess.CalledProcessError as exc:
        print(f"❌ Paket-Installation fehlgeschlagen: {exc}")
        print("   Führe manuell aus: pip install -r requirements.txt")


# ---------------------------------------------------------------------------
# Step 2 – Ollama health check
# ---------------------------------------------------------------------------

def check_ollama() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{_OLLAMA_URL}/api/tags", timeout=2) as resp:
            if resp.status == 200:
                print("✅ Ollama läuft.")
                return True
    except Exception:
        pass
    print("⚠️  Ollama nicht gefunden – KI-Funktionen sind eingeschränkt.")
    print("   → Ollama installieren: https://ollama.ai")
    print("   → Danach ausführen:    ollama pull llama3")
    print("                          ollama pull nomic-embed-text")
    return False


# ---------------------------------------------------------------------------
# Step 3 – database + vault sync
# ---------------------------------------------------------------------------

def init_database() -> None:
    # Extend sys.path so core modules are importable when running as EXE
    if str(_BUNDLE_DIR) not in sys.path:
        sys.path.insert(0, str(_BUNDLE_DIR))

    from core.config import VAULT_DIR
    from core.database import full_sync, init_db

    print("🗄  Initialisiere Datenbank…")
    init_db()
    print("   ✔ Tabellen bereit.")

    print("   🔄 Synchronisiere Vault…")
    try:
        stats = full_sync(VAULT_DIR)
        print(
            f"   ✔ {stats['inserted']} neu · "
            f"{stats['updated']} aktualisiert · "
            f"{stats['deleted']} entfernt."
        )
    except Exception as exc:
        print(f"   ⚠ Vault-Sync fehlgeschlagen: {exc}")


# ---------------------------------------------------------------------------
# Step 4 – file watcher
# ---------------------------------------------------------------------------

def start_watcher():
    try:
        from core.config import VAULT_DIR
        from core.file_watcher import VaultWatcher
        watcher = VaultWatcher()

        def _on_event(event_type: str, filename: str) -> None:
            icon = "📝" if event_type == "upsert" else "🗑"
            print(f"  {icon} {event_type}: {filename}")

        watcher.start_watching(VAULT_DIR, callback=_on_event)
        print("   ✔ Vault-Watcher aktiv.")
        return watcher
    except Exception as exc:
        print(f"   ⚠ Watcher konnte nicht gestartet werden: {exc}")
        return None


# ---------------------------------------------------------------------------
# Step 5 – optional embedding index
# ---------------------------------------------------------------------------

def auto_index(ollama_ok: bool) -> None:
    if not ollama_ok:
        return
    try:
        from core.config import VAULT_DIR
        from ai.embedder import ensure_indexed_from_vault
        ensure_indexed_from_vault(VAULT_DIR)
        print("   ✔ Embeddings aktuell.")
    except Exception as exc:
        print(f"   ⚠ Auto-Indexierung fehlgeschlagen: {exc}")


# ---------------------------------------------------------------------------
# Step 6 – Streamlit subprocess
# ---------------------------------------------------------------------------

def start_streamlit():
    if not _APP_PY.exists():
        print(f"❌ App-Datei nicht gefunden: {_APP_PY}")
        sys.exit(1)

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(_APP_PY),
            "--server.port=8501",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 52)
    print("  🧠 SecondBrain Agent – startet…")
    print("=" * 52)

    # 1. Packages
    if not getattr(sys, "frozen", False):
        # Skip auto-install inside the EXE bundle (deps are frozen in)
        check_python_packages()

    # 2. Ollama
    print()
    ollama_ok = check_ollama()

    # 3. Database
    print()
    init_database()

    # 4. Watcher
    watcher = start_watcher()

    # 5. Embeddings
    print()
    print("🤖 Prüfe Embeddings…")
    auto_index(ollama_ok)

    # 6. Streamlit
    print()
    print(f"🚀 Starte Web-Interface auf {_APP_URL} …")
    proc = start_streamlit()

    # Wait for Streamlit to become ready (poll /healthz)
    import urllib.request as _ur
    for _ in range(20):
        time.sleep(0.5)
        try:
            with _ur.urlopen(f"{_APP_URL}/_stcore/health", timeout=1):
                break
        except Exception:
            pass

    webbrowser.open(_APP_URL)
    print(f"   ✔ Browser geöffnet: {_APP_URL}")

    print()
    print("=" * 52)
    print("  ✅ SecondBrain läuft.")
    print(f"     URL:  {_APP_URL}")
    print("     Dieses Fenster NICHT schließen.")
    print("=" * 52)

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n👋 Wird beendet…")
    finally:
        if watcher:
            watcher.stop_watching()
        proc.terminate()
        print("👋 SecondBrain Agent beendet.")


if __name__ == "__main__":
    main()

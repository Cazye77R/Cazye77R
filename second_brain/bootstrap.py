import importlib.util
import subprocess
import sys
from pathlib import Path


def check_and_install_dependencies() -> bool:
    req_file = Path(__file__).resolve().parent / "requirements.txt"
    if not req_file.exists():
        print("❌ requirements.txt nicht gefunden.")
        return False

    missing = []
    with open(req_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Extract bare package name (strip version specifiers)
            pkg_name = line.split(">=")[0].split("<=")[0].split("==")[0].split("!=")[0].strip()
            # Normalize: python-frontmatter → frontmatter, PyYAML → yaml, etc.
            import_name = _to_import_name(pkg_name)
            if importlib.util.find_spec(import_name) is None:
                missing.append(line)

    if not missing:
        print("✅ Alle Abhängigkeiten sind bereits installiert.")
        return True

    print(f"🔍 {len(missing)} fehlende Paket(e) gefunden. Starte Installation...\n")
    for pkg in missing:
        pkg_display = pkg.split(">=")[0].split("==")[0].strip()
        print(f"📦 Installiere: {pkg_display}...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"   ✔ {pkg_display} erfolgreich installiert.")
        except subprocess.CalledProcessError:
            print(f"   ✘ Fehler beim Installieren von {pkg_display}.")
            return False

    print("\n✅ Alle Abhängigkeiten erfolgreich installiert.")
    return True


def _to_import_name(pkg_name: str) -> str:
    overrides = {
        "python-frontmatter": "frontmatter",
        "PyYAML": "yaml",
        "Pillow": "PIL",
        "pyvis": "pyvis",
        "chromadb": "chromadb",
        "SQLAlchemy": "sqlalchemy",
        "markdown2": "markdown2",
        "watchdog": "watchdog",
        "networkx": "networkx",
        "plotly": "plotly",
        "streamlit": "streamlit",
        "ollama": "ollama",
        "pandas": "pandas",
    }
    return overrides.get(pkg_name, pkg_name.lower().replace("-", "_"))


if __name__ == "__main__":
    check_and_install_dependencies()

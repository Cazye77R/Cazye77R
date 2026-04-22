import subprocess
import sys
import webbrowser
from pathlib import Path

import bootstrap

STREAMLIT_APP = Path(__file__).resolve().parent / "ui" / "streamlit_app.py"
APP_URL = "http://localhost:8501"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"


def check_ollama() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    print("=" * 50)
    print("  SecondBrain Agent – Starte...")
    print("=" * 50)

    print("\n🔧 Prüfe Abhängigkeiten...")
    if not bootstrap.check_and_install_dependencies():
        print("❌ Abhängigkeiten konnten nicht installiert werden. Abbruch.")
        input("\nEnter zum Beenden...")
        sys.exit(1)

    print("\n🤖 Prüfe Ollama-Verbindung...")
    if check_ollama():
        print("   ✔ Ollama läuft auf http://localhost:11434")
    else:
        print("   ⚠ Ollama nicht erreichbar – KI-Funktionen sind eingeschränkt.")
        print("     Starte Ollama und führe 'ollama pull llama3' aus, um KI zu aktivieren.")

    if not STREAMLIT_APP.exists():
        print(f"\n⚠ ui/streamlit_app.py nicht gefunden. Erstelle Platzhalter...")
        STREAMLIT_APP.parent.mkdir(parents=True, exist_ok=True)
        STREAMLIT_APP.write_text(
            'import streamlit as st\nst.title("SecondBrain Agent")\nst.info("App wird aufgebaut...")\n'
        )

    print(f"\n🚀 Starte Streamlit auf {APP_URL} ...")
    proc = subprocess.Popen(
        ["streamlit", "run", str(STREAMLIT_APP), "--server.port=8501"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    import time
    time.sleep(2)
    webbrowser.open(APP_URL)
    print(f"   ✔ Browser geöffnet: {APP_URL}")

    print("\n" + "=" * 50)
    print("  App läuft. Schließe dieses Fenster NICHT.")
    print("=" * 50)

    try:
        input("\nEnter zum Beenden...")
    finally:
        proc.terminate()
        print("👋 SecondBrain Agent beendet.")


if __name__ == "__main__":
    main()

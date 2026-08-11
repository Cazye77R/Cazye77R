#!/usr/bin/env python3
"""
LocalTranscribe launcher – the single source of start logic.

Responsibilities:
  * check the Python version and print a readable error instead of a traceback
  * create .venv and install dependencies         (only with --setup)
  * download exactly the models the project needs (only with --setup)
  * apply the offline network lock, then start Streamlit

Usage:
    python launcher.py              start only – nothing is fetched, no network
    python launcher.py --setup      install/update dependencies + models, then start
    python launcher.py --print-env  show the environment lock and exit
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
APP = ROOT / "app.py"

MIN_PYTHON = (3, 9)

# ---------------------------------------------------------------------------
# Network lock
# ---------------------------------------------------------------------------

# Applied in every mode: no component may phone home, ever.
_NO_TELEMETRY_ENV = {
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    "DO_NOT_TRACK": "1",
}

# Applied when NOT setting up. Without these, huggingface_hub contacts
# huggingface.co on every from_pretrained() call just to revalidate the cache –
# even when the model is already fully downloaded.
_OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}


def build_env(*, offline: bool) -> dict[str, str]:
    """Return the environment the child process should run with."""
    env = os.environ.copy()
    env.update(_NO_TELEMETRY_ENV)
    if offline:
        env.update(_OFFLINE_ENV)
    else:
        # Setup mode needs to reach PyPI and HuggingFace. Make sure a lock left
        # over from a previous offline run does not block the download.
        for key in _OFFLINE_ENV:
            env.pop(key, None)
    return env


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def info(msg: str) -> None:
    print(f"  {msg}", flush=True)


def fail(msg: str) -> None:
    """Print a readable error and exit – never a traceback."""
    print(f"\n  FEHLER: {msg}\n", file=sys.stderr, flush=True)
    sys.exit(1)


def venv_python() -> Path:
    """Path to the interpreter inside .venv, platform aware."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def check_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        found = ".".join(str(p) for p in sys.version_info[:3])
        want = ".".join(str(p) for p in MIN_PYTHON)
        fail(
            f"Python {want} oder neuer wird benoetigt, gefunden wurde {found}.\n"
            f"  Interpreter: {sys.executable}\n"
            f"  Neuere Version von python.org installieren und erneut starten."
        )


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> int:
    """Run a command, returning its exit code. Never raises on failure."""
    try:
        return subprocess.call(cmd, cwd=str(ROOT), env=env)
    except OSError as exc:
        fail(f"Befehl konnte nicht gestartet werden: {' '.join(cmd)}\n  {exc}")
        return 1  # unreachable – fail() exits


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def create_venv() -> None:
    info("Erstelle virtuelle Umgebung (.venv)…")
    try:
        venv.EnvBuilder(with_pip=True, clear=False).create(str(VENV_DIR))
    except Exception as exc:
        fail(f"Virtuelle Umgebung konnte nicht erstellt werden.\n  {exc}")
    if not venv_python().is_file():
        fail(f"Virtuelle Umgebung unvollstaendig – {venv_python()} fehlt.")


def install_dependencies(env: dict[str, str]) -> bool:
    """Install requirements.txt. Returns True on success."""
    if not REQUIREMENTS.is_file():
        fail(f"requirements.txt nicht gefunden unter {REQUIREMENTS}")

    py = str(venv_python())
    # --no-cache-dir: a corrupted system pip cache otherwise floods the console
    # with "Cache entry deserialization failed" warnings.
    base = [py, "-m", "pip", "install", "--no-cache-dir"]

    info("Aktualisiere pip…")
    run(base + ["--quiet", "--upgrade", "pip"], env=env)

    info("Installiere Abhaengigkeiten… (das kann beim ersten Mal einige Minuten dauern)")
    return run(base + ["-r", str(REQUIREMENTS)], env=env) == 0


def rebuild_venv_and_retry(env: dict[str, str]) -> None:
    """Last resort when installing into an existing venv fails."""
    info("")
    info("Installation fehlgeschlagen – baue die Umgebung neu auf…")
    shutil.rmtree(VENV_DIR, ignore_errors=True)
    create_venv()
    if not install_dependencies(env):
        fail(
            "Die Abhaengigkeiten konnten auch mit frischer Umgebung nicht "
            "installiert werden.\n"
            "  Pruefe die Fehlermeldungen oben und die Internetverbindung."
        )


# ---------------------------------------------------------------------------
# Model download – only what this project actually uses
# ---------------------------------------------------------------------------

# Runs inside the venv. Downloads exactly the configured Whisper size and, if a
# token is available, the diarization pipeline. Nothing else is fetched.
_FETCH_MODELS = r'''
import os, sys

try:
    from config import WHISPER_MODEL
except Exception as exc:                       # pragma: no cover
    print(f"  Konfiguration nicht lesbar: {exc}")
    sys.exit(0)

print(f"  Whisper-Modell '{WHISPER_MODEL}' …")
try:
    from faster_whisper.utils import download_model
    path = download_model(WHISPER_MODEL)
    print(f"    bereit: {path}")
except Exception as exc:
    print(f"    uebersprungen ({exc})")

token = os.getenv("HF_TOKEN", "").strip()
if not token:
    try:
        from dotenv import dotenv_values
        token = (dotenv_values(".env").get("HF_TOKEN") or "").strip()
    except Exception:
        pass

if not token:
    print("  Sprechererkennung: kein HF_TOKEN gesetzt – Modell wird nicht geladen.")
    print("    (Die App laeuft trotzdem, nur ohne Sprecher-Labels.)")
else:
    print("  Diarisierungs-Modell 'pyannote/speaker-diarization-3.1' …")
    try:
        from pyannote.audio import Pipeline
        Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=token
        )
        print("    bereit.")
    except Exception as exc:
        print(f"    uebersprungen ({exc})")
        print("    Nutzungsbedingungen akzeptieren unter:")
        print("    https://huggingface.co/pyannote/speaker-diarization-3.1")
'''


def fetch_models(env: dict[str, str]) -> None:
    info("")
    info("Lade benoetigte Modelle (nur diese, nichts darueber hinaus)…")
    run([str(venv_python()), "-c", _FETCH_MODELS], env=env)


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------


def start_app(env: dict[str, str], *, offline: bool) -> int:
    if not APP.is_file():
        fail(f"app.py nicht gefunden unter {APP}")

    info("")
    info("Starte LocalTranscribe" + (" (Offline-Modus)" if offline else "") + "…")
    if offline:
        info("Netzwerkzugriff auf Modell-Server ist gesperrt.")
    info("Beenden mit Strg+C.")
    info("")

    try:
        return run([str(venv_python()), "-m", "streamlit", "run", str(APP)], env=env)
    except KeyboardInterrupt:
        info("")
        info("Beendet.")
        return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Startet LocalTranscribe lokal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Abhaengigkeiten und Modelle installieren/aktualisieren, dann starten.",
    )
    parser.add_argument(
        "--print-env",
        action="store_true",
        help="Zeigt die gesetzten Umgebungsvariablen und beendet sich.",
    )
    args = parser.parse_args()

    offline = not args.setup
    env = build_env(offline=offline)

    if args.print_env:
        mode = "Offline (Start)" if offline else "Setup (Installation)"
        print(f"\n  Modus: {mode}\n")
        for key in sorted(set(_NO_TELEMETRY_ENV) | set(_OFFLINE_ENV)):
            print(f"    {key:<38} {env.get(key, '(nicht gesetzt)')}")
        print()
        return 0

    check_python_version()

    if args.setup:
        if not venv_python().is_file():
            create_venv()
        if not install_dependencies(env):
            rebuild_venv_and_retry(env)
        fetch_models(env)
    elif not venv_python().is_file():
        fail(
            "Keine virtuelle Umgebung gefunden.\n"
            "  Bitte zuerst 'start_online.bat' ausfuehren – das richtet alles ein.\n"
            "  Danach startet 'start_offline.bat' die App ohne Internetzugriff."
        )

    return start_app(env, offline=offline)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Abgebrochen.\n")
        sys.exit(130)

#!/usr/bin/env python3
"""HandCursor launcher — sets up the environment and starts the app.

    python run.py              interactive menu
    python run.py ui           Streamlit interface
    python run.py app          OpenCV window
    python run.py calibrate    calibration wizard
    python run.py test         test suite
    python run.py build        standalone executable
    python run.py doctor       diagnose the installation

On first run this creates a .venv and installs the dependencies, then restarts
itself inside it. Afterwards startup is immediate — the install is skipped
unless requirements.txt changed.

STDLIB ONLY. This file runs on the *system* interpreter before the virtual
environment exists, so it must not import cv2, mediapipe, pyautogui, numpy or
streamlit at module level.
"""

import argparse
import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
STAMP = VENV_DIR / ".deps-stamp"
REQS = ROOT / "requirements.txt"
REQS_DEV = ROOT / "requirements-dev.txt"
REEXEC_FLAG = "HANDCURSOR_LAUNCHER_REEXEC"

# MediaPipe publishes no wheels above 3.12; below 3.10 the code uses `X | None`.
MIN_PY = (3, 10)
MAX_PY = (3, 12)

GUI_MODES = {"app", "ui", "calibrate"}
MODES = ["ui", "app", "calibrate", "test", "build", "doctor"]

MENU = """
  HandCursor
  ─────────────────────────────────
   1) Streamlit-Oberflaeche   (ui)
   2) OpenCV-Fenster          (app)
   3) Kalibrierung            (calibrate)
   4) Tests                   (test)
   5) EXE bauen               (build)
   6) Diagnose                (doctor)
   0) Beenden
"""


def info(msg):
    print(f"[HandCursor] {msg}")


def die(code, msg):
    print(f"\n{msg}\n", file=sys.stderr)
    sys.exit(code)


# ── Environment ───────────────────────────────────────────────────────────

def in_venv() -> bool:
    return sys.prefix != sys.base_prefix


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def check_python_version() -> None:
    ver = sys.version_info[:2]
    if ver < MIN_PY:
        die(1, f"Python {ver[0]}.{ver[1]} ist zu alt.\n"
               f"HandCursor braucht mindestens Python {MIN_PY[0]}.{MIN_PY[1]}.")
    if ver > MAX_PY:
        die(1, f"Python {ver[0]}.{ver[1]} wird von MediaPipe noch nicht "
               f"unterstuetzt.\nBitte Python {MIN_PY[0]}.{MIN_PY[1]}–"
               f"{MAX_PY[0]}.{MAX_PY[1]} verwenden.\n"
               f"Mit einer vorhandenen 3.12: py -3.12 run.py  (Windows) "
               f"bzw. python3.12 run.py")


def _stamp_value(with_dev: bool) -> str:
    digest = hashlib.sha256()
    for path in (REQS, REQS_DEV if with_dev else None):
        if path and path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_venv(with_dev: bool, reinstall: bool) -> Path:
    """Create .venv and install dependencies if needed. Returns its python."""
    python = venv_python()
    if not python.is_file():
        info(f"Lege virtuelle Umgebung an: {VENV_DIR}")
        venv.EnvBuilder(with_pip=True, clear=False).create(VENV_DIR)
        reinstall = True

    wanted = _stamp_value(with_dev)
    current = STAMP.read_text().strip() if STAMP.is_file() else ""
    if reinstall or current != wanted:
        info("Installiere Abhaengigkeiten (das kann beim ersten Mal dauern) …")
        cmd = [str(python), "-m", "pip", "install", "--upgrade", "pip"]
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL)
        cmd = [str(python), "-m", "pip", "install", "-r", str(REQS)]
        if with_dev and REQS_DEV.is_file():
            cmd += ["-r", str(REQS_DEV)]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            die(result.returncode,
                "Installation der Abhaengigkeiten fehlgeschlagen.\n"
                "Diagnose:  python run.py doctor")
        STAMP.write_text(wanted)
    return python


def reexec_in_venv(python: Path, argv: list) -> int:
    env = dict(os.environ, **{REEXEC_FLAG: "1"})
    return subprocess.run([str(python), str(Path(__file__).resolve()), *argv],
                          env=env).returncode


# ── Preflight ─────────────────────────────────────────────────────────────

def guard_display(force: bool) -> None:
    """Refuse to start a GUI mode with no display, with a readable message."""
    if force or not sys.platform.startswith("linux"):
        return
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return
    die(2, "Keine grafische Anzeige gefunden (DISPLAY ist nicht gesetzt).\n"
           "HandCursor steuert die echte Maus und braucht einen Desktop mit "
           "Bildschirm.\nUeber SSH ohne X11-Weiterleitung ist das nicht "
           "moeglich.\n\n"
           "Trotzdem versuchen:  python run.py <modus> --force\n"
           "Diagnose:            python run.py doctor")


def warn_no_camera() -> None:
    if sys.platform.startswith("linux") and not list(Path("/dev").glob("video*")):
        info("Warnung: keine /dev/video* gefunden – ist eine Webcam angeschlossen?")


# ── Doctor ────────────────────────────────────────────────────────────────

REMEDIES = {
    "cv2": "pip install opencv-python  (unter Linux zusaetzlich: "
           "sudo apt install libgl1 libglib2.0-0)",
    "mediapipe": "pip install mediapipe  (benoetigt Python 3.10–3.12)",
    "pyautogui": "pip install pyautogui  (Linux: sudo apt install "
                 "python3-tk python3-dev scrot)",
    "numpy": "pip install numpy",
    "streamlit": "pip install streamlit",
    "pytest": "pip install -r requirements-dev.txt",
}


def doctor() -> int:
    print("HandCursor – Diagnose")
    print("=" * 52)
    print(f"Python           : {sys.version.split()[0]}  ({sys.executable})")
    print(f"Plattform        : {sys.platform}")
    print(f"In venv          : {'ja' if in_venv() else 'nein'}")
    print(f"venv-Pfad        : {VENV_DIR if VENV_DIR.is_dir() else '(nicht angelegt)'}")
    print(f"DISPLAY          : {os.environ.get('DISPLAY') or '(nicht gesetzt)'}")
    print(f"WAYLAND_DISPLAY  : {os.environ.get('WAYLAND_DISPLAY') or '(nicht gesetzt)'}")

    if sys.platform.startswith("linux"):
        cams = sorted(p.name for p in Path("/dev").glob("video*"))
        print(f"Kameras          : {', '.join(cams) if cams else '(keine gefunden)'}")

    print("\nAbhaengigkeiten:")
    missing = []
    for name in ("numpy", "cv2", "mediapipe", "pyautogui", "streamlit", "pytest"):
        try:
            __import__(name)
            print(f"  [ok]     {name}")
        except Exception as exc:
            missing.append(name)
            print(f"  [fehlt]  {name}: {type(exc).__name__}: {exc}")
            print(f"           -> {REMEDIES.get(name, 'pip install ' + name)}")

    print("\nProfile:")
    try:
        sys.path.insert(0, str(ROOT))
        import profile_manager
        print(f"  Verzeichnis : {profile_manager.user_dir()}")
        print(f"  Verfuegbar  : {', '.join(profile_manager.list_profiles()) or '(keine)'}")
        print(f"  Aktiv       : {profile_manager.get_active_profile_name() or '(keins)'}")
    except Exception as exc:
        print(f"  Fehler beim Lesen der Profile: {exc}")

    print("=" * 52)
    print("Alles bereit." if not missing else
          f"{len(missing)} Abhaengigkeit(en) fehlen – siehe oben.")
    return 0 if not missing else 1


# ── Launching ─────────────────────────────────────────────────────────────

def streamlit_cmd(python: Path, args) -> list:
    cmd = [str(python), "-m", "streamlit", "run", str(ROOT / "app.py")]
    if args.port:
        cmd += ["--server.port", str(args.port)]
    return cmd


def open_calibrate_later(port: int) -> None:
    """Open the calibration page once the server accepts connections."""
    import socket
    import threading
    import time
    import webbrowser

    def wait():
        for _ in range(120):
            with socket.socket() as sock:
                sock.settimeout(0.5)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    webbrowser.open(f"http://localhost:{port}/calibrate")
                    return
            time.sleep(0.5)

    threading.Thread(target=wait, daemon=True).start()


def launch(mode: str, python: Path, args) -> int:
    if mode == "doctor":
        return doctor()

    if mode == "test":
        return subprocess.run([str(python), "-m", "pytest", "tests/", "-v"],
                              cwd=ROOT).returncode

    if mode == "build":
        return subprocess.run([str(python), str(ROOT / "build.py")], cwd=ROOT).returncode

    guard_display(args.force)
    warn_no_camera()

    if mode == "app":
        cmd = [str(python), str(ROOT / "hand_cursor.py")]
        if args.profile:
            cmd += ["--profile", args.profile]
        if args.camera is not None:
            cmd += ["--camera", str(args.camera)]
        return subprocess.run(cmd, cwd=ROOT).returncode

    # ui / calibrate
    port = args.port or 8501
    args.port = port
    if mode == "calibrate":
        open_calibrate_later(port)
        info(f"Kalibrierung oeffnet sich unter http://localhost:{port}/calibrate")
    else:
        info(f"Oberflaeche startet unter http://localhost:{port}")
    return subprocess.run(streamlit_cmd(python, args), cwd=ROOT).returncode


def choose_mode() -> str:
    if not sys.stdin.isatty():
        return ""
    print(MENU)
    mapping = dict(enumerate(MODES, start=1))
    while True:
        try:
            choice = input("  Auswahl [1]: ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if choice == "0":
            sys.exit(0)
        if choice.isdigit() and int(choice) in mapping:
            return mapping[int(choice)]
        if choice in MODES:
            return choice
        print("  Ungueltige Auswahl.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py", description="HandCursor starten.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Modi:\n  " + "\n  ".join(
            f"{m:<10} {d}" for m, d in [
                ("ui", "Streamlit-Oberflaeche mit Live-Bild und Profilen"),
                ("app", "reines OpenCV-Fenster"),
                ("calibrate", "Kalibrierungs-Wizard"),
                ("test", "Testsuite"),
                ("build", "Standalone-EXE bauen"),
                ("doctor", "Installation pruefen"),
            ]))
    parser.add_argument("mode", nargs="?", choices=MODES,
                        help="Was gestartet werden soll (ohne Angabe: Menue)")
    parser.add_argument("--no-venv", action="store_true",
                        help="Aktuellen Interpreter benutzen, keine .venv anlegen")
    parser.add_argument("--reinstall", action="store_true",
                        help="Abhaengigkeiten neu installieren")
    parser.add_argument("--profile", metavar="NAME", help="Profil (nur bei 'app')")
    parser.add_argument("--camera", type=int, metavar="N", help="Kamera-Index")
    parser.add_argument("--port", type=int, metavar="N",
                        help="Port fuer die Oberflaeche (Standard 8501)")
    parser.add_argument("--force", action="store_true",
                        help="Start auch ohne erkannte Anzeige erzwingen")
    args = parser.parse_args(argv)

    check_python_version()
    mode = args.mode or choose_mode()
    if not mode:
        parser.print_help()
        return 0

    # doctor must stay usable even when the environment is broken
    if mode == "doctor" and (in_venv() or args.no_venv):
        return doctor()

    if args.no_venv or in_venv() or os.environ.get(REEXEC_FLAG):
        python = Path(sys.executable)
        if not (args.no_venv or os.environ.get(REEXEC_FLAG)):
            ensure_venv(mode == "test", args.reinstall)
    else:
        python = ensure_venv(with_dev=(mode == "test"), reinstall=args.reinstall)
        forwarded = [mode] + [a for a in (sys.argv[1:] if argv is None else argv)
                              if a != mode]
        return reexec_in_venv(python, forwarded)

    code = launch(mode, python, args)
    if code != 0:
        print(f"\n[HandCursor] '{mode}' endete mit Code {code}.", file=sys.stderr)
        print("Diagnose:  python run.py doctor", file=sys.stderr)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)

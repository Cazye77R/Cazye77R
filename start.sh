#!/usr/bin/env bash
# Start the live camera detection & body tracking app.
#
#   ./start.sh                     start the app
#   ./start.sh --setup             install dependencies, then start
#   ./start.sh --update            git pull + install dependencies, then start
#   ./start.sh --server.port 8502  any other argument is passed to streamlit
#
# The script never touches the repository unless you ask it to with --update.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3}"
BRANCH="claude/camera-detection-tracking-KtYyH"

do_setup=0
do_update=0
streamlit_args=()

for arg in "$@"; do
    case "$arg" in
        --setup)  do_setup=1 ;;
        --update) do_update=1; do_setup=1 ;;
        --help|-h)
            sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) streamlit_args+=("$arg") ;;
    esac
done

if [[ "$do_update" -eq 1 ]]; then
    echo "==> Aktualisiere Repository (Branch: $BRANCH)"
    git pull origin "$BRANCH"
fi

# Python-Version prüfen, bevor irgendetwas installiert wird.
#   Obergrenze < 3.13: mediapipe wird dafür nicht als fertiges Paket
#     angeboten; ohne diese Prüfung versucht pip einen Build aus dem
#     Quelltext, der mit einer irreführenden Compiler-Meldung abbricht.
#   Untergrenze >= 3.10: streamlit, streamlit-webrtc und aiortc
#     deklarieren alle requires_python >= 3.10.
if ! "$PYTHON" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info < (3,13) else 1)' 2>/dev/null; then
    version="$("$PYTHON" -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo 'nicht gefunden')"
    cat >&2 <<EOF
FEHLER: Python-Version wird nicht unterstützt.

  Gefunden:  $version
  Benötigt:  Python 3.10 - 3.12

Gründe: mediapipe (Körper-Tracking) gibt es für Python 3.13 und neuer
nicht als fertiges Paket; streamlit und streamlit-webrtc setzen
mindestens 3.10 voraus.

Falls eine passende Version installiert ist, gezielt auswählen:

    PYTHON=python3.12 ./start.sh --setup
EOF
    exit 1
fi

if [[ "$do_setup" -eq 1 ]]; then
    echo "==> Installiere Abhängigkeiten"
    # --upgrade, damit ein bereits vorhandener, zu alter Paketstand aktiv
    # hochgezogen wird statt stehen zu bleiben.
    # --only-binary für die kompilierten Pakete: fehlt ein Wheel, bricht pip
    # sofort verständlich ab statt einen aussichtslosen Compiler-Lauf zu starten.
    "$PYTHON" -m pip install --upgrade \
        --only-binary=av,mediapipe,torch,opencv-contrib-python \
        -r requirements.txt
fi

# Preflight: fail with a readable message instead of a Python traceback.
if ! "$PYTHON" - <<'EOF' 2>/dev/null
import importlib
for module in ("streamlit", "streamlit_webrtc", "av", "cv2", "ultralytics", "mediapipe"):
    importlib.import_module(module)
EOF
then
    cat >&2 <<'EOF'
FEHLER: Es fehlen Python-Abhängigkeiten.

Installiere sie mit:

    ./start.sh --setup

Benötigt werden: streamlit, streamlit-webrtc, av, cv2 (OpenCV),
ultralytics und mediapipe.

Bleibt der Fehler nach --setup bestehen, ist der Paketstand
widersprüchlich. Dann die Umgebung neu aufbauen:

    rm -rf .venv && ./start.sh --setup
EOF
    exit 1
fi

echo "==> Starte Kamera-Erkennung"
exec "$PYTHON" -m streamlit run camera_detection/app.py "${streamlit_args[@]}"

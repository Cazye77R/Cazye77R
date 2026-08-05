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

if [[ "$do_setup" -eq 1 ]]; then
    echo "==> Installiere Abhängigkeiten"
    "$PYTHON" -m pip install -r requirements.txt
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
EOF
    exit 1
fi

echo "==> Starte Kamera-Erkennung"
exec "$PYTHON" -m streamlit run camera_detection/app.py "${streamlit_args[@]}"

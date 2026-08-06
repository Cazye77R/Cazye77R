#!/usr/bin/env bash
# HandCursor launcher for Linux / macOS.
#   ./start.sh            interactive menu
#   ./start.sh ui         Streamlit interface
#   ./start.sh app        OpenCV window
#   ./start.sh --help     all options
set -euo pipefail

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "Python 3 wurde nicht gefunden. Bitte Python 3.10-3.12 installieren." >&2
    exit 1
fi

exec "$PY" run.py "$@"

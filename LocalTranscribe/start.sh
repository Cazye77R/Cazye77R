#!/usr/bin/env bash
# LocalTranscribe – Start unter Linux/macOS.
#
#   ./start.sh            normaler Start, ohne Netzwerkzugriff
#   ./start.sh --setup    Pakete und Modelle installieren, dann starten
set -euo pipefail
cd "$(dirname "$0")"

for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        exec "$candidate" launcher.py "$@"
    fi
done

echo "  FEHLER: Kein Python gefunden. Bitte Python 3.9 oder neuer installieren." >&2
exit 1

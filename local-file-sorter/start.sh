#!/usr/bin/env bash
# ============================================================
#  LOCAL-FILE-SORTER  –  Setup & Start (Linux / macOS)
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11

echo ""
echo " ============================================"
echo "  LOCAL-FILE-SORTER  //  Setup & Start"
echo " ============================================"
echo ""

# ---- Farb-Codes (optional) -----------------------------------
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARNUNG]${NC} $*"; }
err()  { echo -e "${RED}[FEHLER]${NC} $*"; }

# ---- 1. Python-Binary ermitteln ------------------------------
PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    err "Python wurde nicht gefunden."
    echo "     Ubuntu/Debian:  sudo apt install python3.11 python3.11-venv python3-tk"
    echo "     macOS:          brew install python@3.11 python-tk@3.11"
    exit 1
fi

# ---- 2. Version prüfen ---------------------------------------
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [[ "$PY_MAJOR" -lt "$PYTHON_MIN_MAJOR" ]] || \
   { [[ "$PY_MAJOR" -eq "$PYTHON_MIN_MAJOR" ]] && [[ "$PY_MINOR" -lt "$PYTHON_MIN_MINOR" ]]; }; then
    err "Python $PY_MAJOR.$PY_MINOR ist zu alt (Mindestversion: $PYTHON_MIN_MAJOR.$PYTHON_MIN_MINOR)."
    echo "     Ubuntu/Debian:  sudo apt install python3.11 python3.11-venv python3-tk"
    echo "     macOS:          brew install python@3.11 python-tk@3.11"
    exit 1
fi
ok "Python $PY_MAJOR.$PY_MINOR gefunden ($("$PYTHON" -c "import sys; print(sys.executable)"))."

# ---- 3. tkinter prüfen ---------------------------------------
if ! "$PYTHON" -c "import tkinter" &>/dev/null; then
    err "tkinter ist nicht verfügbar."
    echo "     Ubuntu/Debian:  sudo apt install python3-tk"
    echo "     macOS:          brew install python-tk@3.11"
    exit 1
fi
ok "tkinter verfügbar."

# ---- 4. python3-venv prüfen ----------------------------------
if ! "$PYTHON" -m venv --help &>/dev/null; then
    err "python3-venv fehlt."
    echo "     Ubuntu/Debian:  sudo apt install python3.11-venv"
    exit 1
fi

# ---- 5. Virtuelle Umgebung -----------------------------------
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    ok "Virtuelle Umgebung bereits vorhanden."
else
    echo "[..] Erstelle virtuelle Umgebung ..."
    "$PYTHON" -m venv "$VENV_DIR"
    ok "Virtuelle Umgebung erstellt."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---- 6. pip aktualisieren ------------------------------------
echo "[..] pip aktualisieren ..."
python -m pip install --upgrade pip --quiet
ok "pip aktuell."

# ---- 7. Abhängigkeiten installieren --------------------------
echo "[..] Abhängigkeiten installieren ..."
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
ok "Alle Abhängigkeiten installiert."

# ---- 8. Ollama prüfen (Hinweis, kein Abbruch) ----------------
if curl -s --connect-timeout 2 http://localhost:11434 &>/dev/null; then
    ok "Ollama erreichbar."
else
    echo ""
    warn "Ollama läuft nicht auf localhost:11434."
    echo "     Starte Ollama und lade das Modell:"
    echo "       ollama pull qwen2.5:7b-instruct-q4_K_M"
    echo "     Das Programm startet trotzdem. Pläne können erst"
    echo "     generiert werden wenn Ollama erreichbar ist."
    echo ""
fi

# ---- 9. Programm starten -------------------------------------
echo "[..] Starte LOCAL-FILE-SORTER ..."
echo ""
cd "$SCRIPT_DIR"
python main.py

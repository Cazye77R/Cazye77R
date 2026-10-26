#!/bin/bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -x ".venv/bin/python" ]; then
    echo "Lege Python-Umgebung an..."
    python3 -m venv .venv
fi
source .venv/bin/activate
export PIP_DISABLE_PIP_VERSION_CHECK=1

# Nur installieren, wenn sich requirements.txt seit der letzten Installation geaendert hat.
# --no-cache-dir: umgeht einen beschaedigten pip-Cache ("Cache entry deserialization failed").
if ! cmp -s requirements.txt .venv/installed-requirements.txt; then
    echo "Installiere Abhaengigkeiten..."
    python -m pip install --quiet --no-cache-dir --upgrade pip
    python -m pip install --quiet --no-cache-dir -r requirements.txt
    cp requirements.txt .venv/installed-requirements.txt
fi

echo "Starte StockMind auf http://localhost:8501 ..."
python -m streamlit run app.py

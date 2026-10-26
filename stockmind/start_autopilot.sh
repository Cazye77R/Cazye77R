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

if [ "$#" -eq 0 ]; then
    read -r -p "Ticker (mit Leerzeichen, z.B. AAPL MSFT BMW.DE): " TICKERS
    # shellcheck disable=SC2086
    python autopilot.py $TICKERS
else
    python autopilot.py "$@"
fi

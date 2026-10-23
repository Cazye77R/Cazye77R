#!/bin/bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ "$#" -eq 0 ]; then
    read -r -p "Ticker (mit Leerzeichen, z.B. AAPL MSFT BMW.DE): " TICKERS
    # shellcheck disable=SC2086
    python autopilot.py $TICKERS
else
    python autopilot.py "$@"
fi

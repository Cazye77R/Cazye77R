#!/bin/bash
# Autostart des Autopilots per systemd (Benutzer-Dienst).
#   ./autostart.sh install AAPL MSFT   -> Ticker speichern, Dienst einrichten und starten
#   ./autostart.sh remove              -> Dienst entfernen
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT="$UNIT_DIR/stockmind-autopilot.service"

case "${1:-}" in
install)
    shift
    [ -d "$DIR/.venv" ] || python3 -m venv "$DIR/.venv"
    "$DIR/.venv/bin/pip" install --quiet -r "$DIR/requirements.txt"
    if [ "$#" -gt 0 ]; then
        (cd "$DIR" && .venv/bin/python autopilot.py "$@" --save-tickers --once)
    fi
    mkdir -p "$UNIT_DIR" "$DIR/data"
    cat > "$UNIT" <<UNITEOF
[Unit]
Description=StockMind Autopilot (Paper-Trading)

[Service]
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python autopilot.py
Restart=on-failure
RestartSec=60
StandardOutput=append:$DIR/data/autopilot.log
StandardError=append:$DIR/data/autopilot.log

[Install]
WantedBy=default.target
UNITEOF
    systemctl --user daemon-reload
    systemctl --user enable --now stockmind-autopilot.service
    loginctl enable-linger "$USER" 2>/dev/null || true
    echo "Autopilot läuft und startet beim Booten. Log: $DIR/data/autopilot.log"
    ;;
remove)
    systemctl --user disable --now stockmind-autopilot.service 2>/dev/null || true
    rm -f "$UNIT"
    systemctl --user daemon-reload
    echo "Autostart entfernt."
    ;;
*)
    echo "Verwendung: $0 install [TICKER...] | remove"
    exit 1
    ;;
esac

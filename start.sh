#!/usr/bin/env bash
# Startet agent-office (React/Vite Dev-Server)
# Verwendung: sh start.sh  oder  ./start.sh (nach chmod +x start.sh)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/agent-office"

if [ ! -d "$APP_DIR" ]; then
  echo "Fehler: Ordner '$APP_DIR' nicht gefunden." >&2
  exit 1
fi

cd "$APP_DIR"

if [ ! -d node_modules ]; then
  echo ">> npm install ..."
  npm install
fi

echo ">> npm run dev"
npm run dev

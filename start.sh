#!/usr/bin/env bash
# Start the Elephant backend (FastAPI) and frontend (Streamlit) together.
# Press Ctrl-C once to shut both down cleanly.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BACKEND_PORT=8000
FRONTEND_PORT=8501

cleanup() {
    echo ""
    echo "Shutting down…"
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── Backend ──────────────────────────────────────────────────────────────────
echo "🐘 Starting Elephant backend on port $BACKEND_PORT…"
python -m uvicorn elephant.main:app \
    --host 127.0.0.1 \
    --port "$BACKEND_PORT" \
    --reload \
    --log-level warning &
BACKEND_PID=$!

# Wait until the backend is ready (up to 30 s)
echo "   Waiting for backend to be ready…"
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/memories" >/dev/null 2>&1; then
        echo "   Backend ready."
        break
    fi
    sleep 1
done

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "🖥️  Starting Elephant frontend on port $FRONTEND_PORT…"
echo ""
echo "   Backend:  http://127.0.0.1:${BACKEND_PORT}"
echo "   Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo ""

python -m streamlit run ui/app.py \
    --server.port "$FRONTEND_PORT" \
    --server.address 127.0.0.1

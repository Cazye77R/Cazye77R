#!/usr/bin/env bash
# Elephant — one-shot setup & start.
# Installs all dependencies, then launches backend (FastAPI) and frontend (Streamlit).
# Press Ctrl-C once to shut both down cleanly.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BACKEND_PORT=8000
FRONTEND_PORT=8501
PYTHON="${PYTHON:-python3}"

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'
info()  { echo -e "${GREEN}$*${RESET}"; }
warn()  { echo -e "${YELLOW}$*${RESET}"; }
error() { echo -e "${RED}$*${RESET}" >&2; }

# ── Helpers ───────────────────────────────────────────────────────────────────
require_python() {
    if ! command -v "$PYTHON" &>/dev/null; then
        error "Python 3.11+ is required but '$PYTHON' was not found."
        error "Set the PYTHON env var to your interpreter path and re-run."
        exit 1
    fi
    local ver
    ver=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local major minor
    major=${ver%%.*}; minor=${ver##*.}
    if [[ "$major" -lt 3 || ( "$major" -eq 3 && "$minor" -lt 11 ) ]]; then
        error "Python 3.11+ required (found $ver)."
        exit 1
    fi
    info "   Python $ver — OK"
}

check_ollama() {
    if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
        warn "   ⚠️  Ollama not detected on port 11434."
        warn "      Start it with:  ollama serve"
        warn "      Pull models:    ollama pull llama3.1 && ollama pull nomic-embed-text"
        warn "      Continuing anyway — chat/embed will fail until Ollama is running."
    else
        info "   Ollama — OK"
    fi
}

install_deps() {
    info "📦 Installing / verifying dependencies…"

    # Prefer the project's own venv if it exists; otherwise use the system Python.
    if [[ -f ".venv/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source ".venv/bin/activate"
        info "   Virtual environment: .venv"
    elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
        info "   Virtual environment: $VIRTUAL_ENV"
    else
        warn "   No .venv found — installing into system Python."
        warn "   Tip: run  python3 -m venv .venv && source .venv/bin/activate  first."
    fi

    # Install the package in editable mode (covers all deps from pyproject.toml)
    "$PYTHON" -m pip install --quiet --upgrade pip
    "$PYTHON" -m pip install --quiet -e ".[dev]"

    info "   Dependencies installed."
}

setup_env() {
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            warn "   .env not found — copied from .env.example. Edit it if needed."
        else
            warn "   .env not found and no .env.example to copy from."
        fi
    else
        info "   .env — OK"
    fi
}

cleanup() {
    echo ""
    info "Shutting down…"
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── Pre-flight checks ─────────────────────────────────────────────────────────
echo ""
info "🐘 Elephant — pre-flight checks"
require_python
check_ollama
install_deps
setup_env
echo ""

# ── Backend ───────────────────────────────────────────────────────────────────
info "🚀 Starting backend on port $BACKEND_PORT…"
"$PYTHON" -m uvicorn elephant.main:app \
    --host 127.0.0.1 \
    --port "$BACKEND_PORT" \
    --reload \
    --log-level warning &
BACKEND_PID=$!

# Wait until the backend is ready (up to 30 s)
echo -n "   Waiting for backend"
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/memories" >/dev/null 2>&1; then
        echo ""
        info "   Backend ready."
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# ── Frontend ──────────────────────────────────────────────────────────────────
info "🖥️  Starting frontend on port $FRONTEND_PORT…"
echo ""
info "   Backend:  http://127.0.0.1:${BACKEND_PORT}/docs"
info "   Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo ""

"$PYTHON" -m streamlit run ui/app.py \
    --server.port "$FRONTEND_PORT" \
    --server.address 127.0.0.1


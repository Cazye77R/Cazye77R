#!/usr/bin/env bash
# Start the live camera detection & body tracking app.
# Usage: bash start.sh [streamlit options]
# Example: bash start.sh --server.port 8502
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure the local branch is up to date with the remote so that
# camera_detection/ is present (the branch may lag behind the remote).
git pull origin claude/camera-detection-tracking-KtYyH

# Install / update Python dependencies (quiet, non-interactive)
pip install -r requirements.txt -q

# Launch the camera detection app; forward any extra CLI arguments
exec streamlit run camera_detection/app.py "$@"

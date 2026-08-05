#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/wifi_heatmap"
python main.py "$@"

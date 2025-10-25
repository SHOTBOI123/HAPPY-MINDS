#!/usr/bin/env bash
set -euo pipefail
set -x  # echo commands

# Pick a Python: prefer $PYTHON_BIN, else python3, else python
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python || true)}"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "ERROR: No python interpreter found. Install Python 3 or activate your venv, e.g.:
    - macOS system:    /usr/bin/python3
    - Homebrew:        /opt/homebrew/bin/python3
    - venv:            source .venv/bin/activate" >&2
  exit 1
fi

# Start FastAPI (Uvicorn) on 8000 in background
"$PYTHON_BIN" -m uvicorn main:app --reload --port 8000 &
UVICORN_PID=$!

# Clean up FastAPI when this script exits
cleanup() { set +e; kill "$UVICORN_PID" 2>/dev/null || true; }
trap cleanup INT TERM EXIT

# Start Flask (foreground) on 5001
"$PYTHON_BIN" app.py

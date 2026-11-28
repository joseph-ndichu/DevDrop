#!/bin/sh
# Starts DevDrop and opens it in your browser.  Usage:  ./start.sh
# Stop it with Ctrl+C.

cd "$(dirname "$0")" || exit 1

# First run only: set up Python and install what DevDrop needs.
if [ ! -x .venv/bin/python ]; then
    echo "First run: installing DevDrop (takes a minute)..."
    python3 -m venv .venv || exit 1
    .venv/bin/python -m pip install -q -r requirements.txt || exit 1
fi

echo "DevDrop is starting at http://localhost:8765  (press Ctrl+C to stop)"
( sleep 2; xdg-open http://localhost:8765 >/dev/null 2>&1 ) &
exec .venv/bin/python -m uvicorn app.main:app --port 8765

#!/usr/bin/env bash
# Launch the app with the PROJECT venv, not whatever `streamlit` is on PATH.
#
# Running bare `streamlit run app.py` picks up the system Python, which does not
# have chromadb/openpyxl installed — producing a confusing ImportError. This
# script always uses .venv.
set -e
cd "$(dirname "$0")"

PY=".venv/Scripts/python.exe"          # Windows (git-bash)
[ -x "$PY" ] || PY=".venv/bin/python"  # Linux / macOS

if [ ! -x "$PY" ]; then
  echo "No virtualenv found. Create one first:"
  echo "  uv venv .venv && uv pip install --python $PY -r requirements.txt"
  exit 1
fi

# Refuse to start a SECOND server on a port that is already serving.
#
# Windows lets two processes bind the same port, and the first one wins. If a
# stale system-Python instance is already on 8501, a new venv instance starts
# "successfully" but the browser keeps hitting the old one — so code fixes
# appear to have no effect and stale warnings seem to reappear forever.
PORT=8501
case " $* " in *" --server.port "*) PORT=$(echo " $* " | sed 's/.*--server.port \([0-9]*\).*/\1/');; esac

if command -v netstat >/dev/null 2>&1 && netstat -ano 2>/dev/null | grep -q ":$PORT .*LISTENING"; then
  echo "Port $PORT is already in use by:"
  netstat -ano | grep ":$PORT .*LISTENING" | awk '{print "  PID " $NF}' | sort -u
  echo
  echo "Stop it first, or pass a different port:"
  echo "  bash run_app.sh --server.port 8502"
  exit 1
fi

exec "$PY" -m streamlit run app.py "$@"

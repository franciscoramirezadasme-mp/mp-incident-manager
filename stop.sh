#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/logs/daemon.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No PID file found — daemon may not be running"
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm -f "$PID_FILE"
    echo "✅ Daemon stopped (PID $PID)"
else
    rm -f "$PID_FILE"
    echo "⚠️  Daemon was not running (stale PID file removed)"
fi

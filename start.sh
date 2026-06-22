#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/logs/daemon.pid"
LOG_FILE="$SCRIPT_DIR/logs/incident_manager.log"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "⚠️  Daemon already running (PID $PID)"
        echo "   Run ./stop.sh to stop it first"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

mkdir -p logs

if [ ! -f ".venv/bin/python3" ]; then
    echo "❌ Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

echo "🚀 Starting MP Incident Manager..."
nohup .venv/bin/python3 main.py >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

echo "✅ Started (PID $(cat "$PID_FILE"))"
echo "📋 Logs: tail -f $LOG_FILE"

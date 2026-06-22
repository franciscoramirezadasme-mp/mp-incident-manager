#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/logs/daemon.pid"
LOG_FILE="$SCRIPT_DIR/logs/incident_manager.log"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        osascript -e 'display dialog "⚠️ MP Incident Manager ya está corriendo." buttons {"OK"} default button "OK" with title "MP Incident Manager"' 2>/dev/null
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

mkdir -p logs

if [ ! -f ".venv/bin/python3" ]; then
    osascript -e 'display dialog "❌ Entorno no configurado. Ejecuta ./setup.sh primero." buttons {"OK"} default button "OK" with title "MP Incident Manager"' 2>/dev/null
    exit 1
fi

# Start daemon in background
nohup .venv/bin/python3 main.py >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

# Open a Terminal window showing live status
osascript << EOF
tell application "Terminal"
    activate
    set w to do script "bash '$SCRIPT_DIR/monitor_status.sh'"
    set custom title of tab 1 of w to "MP Incident Manager — En escucha"
end tell
EOF

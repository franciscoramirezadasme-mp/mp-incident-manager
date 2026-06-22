#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/logs/daemon.pid"

if [ ! -f "$PID_FILE" ]; then
    osascript -e 'display dialog "⚠️ MP Incident Manager no estaba corriendo." buttons {"OK"} default button "OK" with title "MP Incident Manager"' 2>/dev/null
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm -f "$PID_FILE"
    # monitor_status.sh detects the PID disappearing and closes its own window automatically
else
    rm -f "$PID_FILE"
    # No daemon running — close the status window manually if still open
    osascript << 'EOF'
    tell application "Terminal"
        repeat with w in windows
            if name of w contains "MP Incident Manager" then
                close w
                exit repeat
            end if
        end repeat
    end tell
EOF
fi

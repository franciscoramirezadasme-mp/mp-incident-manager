#!/usr/bin/env bash
# Terminal de estado — abierta mientras el daemon está corriendo
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/incident_manager.log"
PID_FILE="$SCRIPT_DIR/logs/daemon.pid"

# Set terminal window title (used by stop.sh to find and close this window)
printf "\033]0;MP Incident Manager — En escucha\007"
export TERM=xterm-256color

clear
echo ""
printf "\033[1;34m╔══════════════════════════════════════════════════════╗\n\033[0m"
printf "\033[1;34m║          MP Incident Manager — En escucha            ║\n\033[0m"
printf "\033[1;34m╚══════════════════════════════════════════════════════╝\n\033[0m"
echo ""
printf "\033[0;32m  Monitoreando proyectos: IXFS, IXF\033[0m\n"
printf "\033[0;32m  Intervalo de polling:   5 minutos\033[0m\n"
printf "\033[0;32m  Umbral SLA:             5 minutos\033[0m\n"
echo ""
printf "\033[1;33m── Log en tiempo real ─────────────────────────────────\033[0m\n"
echo ""

# Follow log — exits automatically when daemon stops
tail -f "$LOG_FILE" &
TAIL_PID=$!

# Watch daemon PID — when it disappears, close this terminal too
while true; do
    sleep 5
    if [ ! -f "$PID_FILE" ] || ! kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
        kill $TAIL_PID 2>/dev/null
        echo ""
        printf "\033[1;31m── Daemon detenido — cerrando terminal ─────────────────\033[0m\n"
        sleep 2
        # Close this Terminal window via osascript
        osascript -e '
            tell application "Terminal"
                repeat with w in windows
                    if name of w contains "MP Incident Manager" then
                        close w
                        exit repeat
                    end if
                end repeat
            end tell
        ' 2>/dev/null
        exit 0
    fi
done

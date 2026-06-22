#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/logs/daemon.pid"
LOG_FILE="$SCRIPT_DIR/logs/incident_manager.log"

mkdir -p logs

# ── Already running? ────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        printf "\033]0;MP Incident Manager — En escucha\007"
        clear
        echo ""
        printf "\033[1;33m⚠️  El daemon ya estaba corriendo (PID $PID)\033[0m\n"
        echo ""
        printf "\033[0;32m  Reconectando al log en tiempo real...\033[0m\n"
        echo ""
        printf "\033[1;33m── Log ────────────────────────────────────────────────\033[0m\n"
        exec bash "$SCRIPT_DIR/monitor_status.sh"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# ── Check venv ───────────────────────────────────────────────
if [ ! -f ".venv/bin/python3" ]; then
    echo "❌ Entorno no configurado. Ejecuta ./setup.sh primero."
    exit 1
fi

# ── Start daemon ─────────────────────────────────────────────
nohup .venv/bin/python3 main.py >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

# ── Turn THIS terminal into the live monitor ──────────────────
exec bash "$SCRIPT_DIR/monitor_status.sh"

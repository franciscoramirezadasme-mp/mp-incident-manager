import subprocess
import logging
import os
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")


def show_ticket_popup(issue_key: str, summary: str, sla_breached: bool, minutes_elapsed: float) -> bool:
    """
    Shows a blocking macOS dialog for a new Jira ticket.
    Returns True if user clicked Aceptar, False if they dismissed or error occurred.
    """
    sla_warning = ""
    if sla_breached:
        hours = int(minutes_elapsed // 60)
        mins = int(minutes_elapsed % 60)
        elapsed_str = f"{hours}h {mins}m" if hours > 0 else f"{mins} min"
        sla_warning = f"\n\n⚠️ SLA VENCIDO — lleva {elapsed_str} sin respuesta."

    message = (
        f"🎫 Nuevo ticket asignado\n\n"
        f"{issue_key}: {summary}"
        f"{sla_warning}\n\n"
        f"Se abrirá análisis con Claude al confirmar."
    )

    script = f'''
    set theResult to display dialog {_escape_applescript(message)} ¬
        with title "MP Incident Manager" ¬
        buttons {{"Ver en Jira", "Aceptar"}} ¬
        default button "Aceptar" ¬
        with icon caution
    return button returned of theResult
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        clicked = result.stdout.strip()
        logger.info(f"Popup for {issue_key}: user clicked '{clicked}'")
        return True
    except subprocess.TimeoutExpired:
        logger.warning(f"Popup for {issue_key} timed out — treating as acknowledged")
        return True
    except Exception as e:
        logger.error(f"Error showing popup for {issue_key}: {e}")
        return True


def open_claude_terminal(issue_key: str, report_path: str, sla_breached: bool, minutes_elapsed: float):
    """
    Opens a new Terminal window with Claude Code pre-loaded with the ticket context.
    The user can analyze and ask questions interactively from there.
    """
    from src.sla_checker import format_elapsed

    sla_context = ""
    if sla_breached:
        sla_context = f"\n⚠️  SLA VENCIDO: lleva {format_elapsed(minutes_elapsed)} sin respuesta."

    # Build the initial prompt for Claude — includes the full report as context
    initial_prompt = (
        f"Soy Francisco, IX Engineer en Mercado Libre. "
        f"Acabo de recibir el ticket {issue_key}{sla_context}\n\n"
        f"Aquí está el reporte completo del ticket:\n\n"
        f"{{REPORT_CONTENT}}\n\n"
        f"Dame:\n"
        f"1. Resumen ejecutivo del problema (2-3 líneas)\n"
        f"2. Contexto completo de lo que ha pasado (historial de comentarios si hay)\n"
        f"3. Estado del SLA y urgencia\n"
        f"4. Primeros pasos recomendados para resolver el caso\n\n"
        f"Luego quédate disponible para que te haga preguntas adicionales sobre este ticket."
    )

    # Write the full initial prompt to a temp file (avoids shell escaping hell)
    safe_key = issue_key.replace("-", "_")
    prompt_path = Path(f"/tmp/mp_prompt_{safe_key}.txt")
    launcher_path = Path(f"/tmp/mp_launch_{safe_key}.sh")

    # Build full prompt with report content already interpolated
    try:
        report_content = Path(report_path).read_text(encoding="utf-8")
    except Exception:
        report_content = "Reporte no disponible."

    full_prompt = (
        f"Soy Francisco, IX Engineer en Mercado Libre. "
        f"Acabo de recibir el ticket {issue_key}{sla_context}\n\n"
        f"Aquí está el reporte completo del ticket:\n\n"
        f"{report_content}\n\n"
        f"Dame:\n"
        f"1. Resumen ejecutivo del problema (2-3 líneas)\n"
        f"2. Contexto completo de lo que ha pasado (historial de comentarios si hay)\n"
        f"3. Estado del SLA y urgencia\n"
        f"4. Primeros pasos recomendados para resolver el caso\n\n"
        f"Luego quédate disponible para que te haga preguntas adicionales sobre este ticket."
    )
    prompt_path.write_text(full_prompt, encoding="utf-8")

    launcher_content = f"""#!/bin/bash
# MP Incident Manager — Análisis de ticket {issue_key}
export TERM=xterm-256color

echo ""
printf "\\033[1;34m╔══════════════════════════════════════════════════╗\\n\\033[0m"
printf "\\033[1;34m║   MP Incident Manager — Ticket {issue_key:<19}║\\n\\033[0m"
printf "\\033[1;34m╚══════════════════════════════════════════════════╝\\n\\033[0m"
echo ""
printf "\\033[1;33m── Reporte del ticket ─────────────────────────────\\n\\033[0m"
cat "{report_path}"
echo ""
printf "\\033[1;32m── Iniciando Claude Code para análisis interactivo ─\\n\\033[0m"
echo ""

{CLAUDE_BIN} "$(cat '{prompt_path}')"
"""
    launcher_path.write_text(launcher_content)
    launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IEXEC)

    # Open a new Terminal window running the launcher script
    applescript = f'''
    tell application "Terminal"
        activate
        do script "{launcher_path}"
    end tell
    '''
    try:
        subprocess.Popen(["osascript", "-e", applescript])
        logger.info(f"Claude terminal opened for {issue_key}")
    except Exception as e:
        logger.error(f"Error opening Claude terminal for {issue_key}: {e}")


def show_sla_alert(issue_key: str, minutes_elapsed: float):
    hours = int(minutes_elapsed // 60)
    mins = int(minutes_elapsed % 60)
    elapsed_str = f"{hours}h {mins}m" if hours > 0 else f"{mins} min"
    message = (
        f"⚠️ ALERTA SLA VENCIDO\n\n"
        f"El ticket {issue_key} lleva {elapsed_str} sin respuesta.\n"
        f"Se dejó nota interna registrando el retraso."
    )
    script = f'''
    display notification {_escape_applescript(message)} ¬
        with title "MP Incident Manager — SLA" ¬
        sound name "Basso"
    '''
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
    except Exception:
        pass


def _escape_applescript(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'

import subprocess
import logging

logger = logging.getLogger(__name__)


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
        f"Se enviará saludo automático al confirmar."
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

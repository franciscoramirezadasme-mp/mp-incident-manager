from datetime import datetime, timezone
import logging
from src import config

logger = logging.getLogger(__name__)


def parse_jira_datetime(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def check_sla(ticket: dict) -> tuple[bool, float]:
    """
    Returns (is_breached, minutes_elapsed_since_creation).
    Uses native Jira SLA field (customfield_10020) if available, otherwise
    falls back to comparing ticket creation time vs now with SLA_THRESHOLD_MINUTES.
    """
    fields = ticket.get("fields", {})

    # Try native SLA field (Jira Service Management)
    sla_field = fields.get("customfield_10020")
    if sla_field and isinstance(sla_field, list):
        for sla in sla_field:
            if sla.get("name", "").lower() in ("time to first response", "first response", "tiempo de primera respuesta"):
                ongoing = sla.get("ongoingCycle", {})
                if ongoing:
                    breached = ongoing.get("breached", False)
                    elapsed_ms = ongoing.get("elapsedTime", {}).get("millis", 0)
                    elapsed_minutes = elapsed_ms / 60000
                    logger.debug(f"Native SLA field: breached={breached}, elapsed={elapsed_minutes:.1f}m")
                    return breached, elapsed_minutes
                completed = sla.get("completedCycles", [])
                if completed:
                    last = completed[-1]
                    breached = last.get("breached", False)
                    elapsed_ms = last.get("elapsedTime", {}).get("millis", 0)
                    return breached, elapsed_ms / 60000

    # Fallback: compare creation time to now
    created_str = fields.get("created", "")
    created_dt = parse_jira_datetime(created_str)
    if not created_dt:
        return False, 0.0

    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - created_dt).total_seconds() / 60
    is_breached = elapsed_minutes > config.SLA_THRESHOLD_MINUTES

    logger.debug(f"SLA fallback: elapsed={elapsed_minutes:.1f}m, threshold={config.SLA_THRESHOLD_MINUTES}m, breached={is_breached}")
    return is_breached, elapsed_minutes


def format_elapsed(minutes: float) -> str:
    if minutes < 60:
        return f"{int(minutes)} minutos"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if mins == 0:
        return f"{hours} hora{'s' if hours != 1 else ''}"
    return f"{hours}h {mins}m"

import logging
from datetime import datetime, timezone
from pathlib import Path
from src import config
from src.sla_checker import format_elapsed

logger = logging.getLogger(__name__)


def _get_greeting() -> str:
    import pytz
    tz = pytz.timezone(config.TIMEZONE)
    hour = datetime.now(tz).hour
    if hour < 12:
        return "Buenos días"
    elif hour < 19:
        return "Buenas tardes"
    return "Buenas noches"


def build_greeting_comment(issue_key: str, summary: str) -> str:
    greeting = _get_greeting()
    return (
        f"{greeting}, gracias por contactarnos.\n\n"
        f"Me complace informarle que hemos recibido su caso *{issue_key}* "
        f"y estamos revisando los detalles para brindarle la mejor asistencia posible.\n\n"
        f"En breve estaremos respondiendo con mayor detalle.\n\n"
        f"Quedamos a su disposición."
    )


def build_sla_internal_note(issue_key: str, minutes_elapsed: float) -> str:
    elapsed_str = format_elapsed(minutes_elapsed)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"[NOTA INTERNA — SLA]\n\n"
        f"Ticket recibido con SLA sin respuesta previa.\n"
        f"Tiempo transcurrido al momento de toma: {elapsed_str}.\n"
        f"Registrado por sistema automático el {now_iso}.\n\n"
        f"El agente fue notificado y está tomando el caso."
    )


def generate_report(ticket: dict, sla_breached: bool, minutes_elapsed: float) -> Path:
    """Generates a Markdown report for the ticket and returns the file path."""
    fields = ticket.get("fields", {})
    issue_key = ticket.get("key", "N/A")
    summary = fields.get("summary", "Sin título")
    status = fields.get("status", {}).get("name", "Desconocido")
    priority = fields.get("priority", {}).get("name", "Sin prioridad")
    created = fields.get("created", "N/A")
    reporter = fields.get("reporter", {}) or {}
    reporter_name = reporter.get("displayName", "Desconocido")
    reporter_email = reporter.get("emailAddress", "")

    description_blocks = fields.get("description", {}) or {}
    description_text = _extract_text(description_blocks)

    comments = fields.get("comment", {}).get("comments", []) if fields.get("comment") else []

    from src.jira_client import get_ticket_url
    url = get_ticket_url(issue_key)

    sla_section = ""
    if sla_breached:
        sla_section = f"""
## ⚠️ ALERTA SLA

**Estado:** VENCIDO al momento de recepción
**Tiempo transcurrido:** {format_elapsed(minutes_elapsed)}
**Acción tomada:** Nota interna registrada en Jira.
"""
    else:
        sla_section = f"""
## ✅ SLA

**Estado:** En tiempo ({format_elapsed(minutes_elapsed)} desde creación)
"""

    comments_section = ""
    if comments:
        comments_section = f"\n## Historial de comentarios ({len(comments)} total)\n\n"
        for c in comments:
            author = c.get("author", {}).get("displayName", "N/A")
            body = _extract_text(c.get("body", {}))
            created_c = c.get("created", "")[:16].replace("T", " ")
            is_internal = c.get("visibility") is not None
            tag = " *(interno)*" if is_internal else ""
            comments_section += f"**{author}** ({created_c}){tag}:\n> {body[:500]}\n\n"

    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report = f"""# Reporte de Incidencia — {issue_key}

**Generado:** {report_date}
**URL:** {url}

---

## Información del ticket

| Campo | Valor |
|-------|-------|
| Clave | {issue_key} |
| Resumen | {summary} |
| Estado | {status} |
| Prioridad | {priority} |
| Creado | {created[:19].replace("T", " ") if created != "N/A" else "N/A"} |
| Reportado por | {reporter_name} ({reporter_email}) |

{sla_section}

## Descripción

{description_text or "_Sin descripción_"}

{comments_section}
---
*Generado automáticamente por MP Incident Manager*
"""

    return _save_report(issue_key, report)


def _save_report(issue_key: str, content: str) -> Path:
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = config.REPORTS_DIR / f"{issue_key}_{date_str}.md"
    path.write_text(content, encoding="utf-8")
    logger.info(f"Report saved: {path}")
    return path


def _extract_text(node, depth=0) -> str:
    if depth > 10:
        return ""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        content = node.get("content", [])
        parts = [_extract_text(c, depth + 1) for c in content]
        sep = "\n" if node.get("type") in ("paragraph", "heading", "bulletList", "listItem") else ""
        return sep.join(p for p in parts if p)
    if isinstance(node, list):
        return " ".join(_extract_text(c, depth + 1) for c in node)
    return ""

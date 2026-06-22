#!/usr/bin/env python3
"""
MP Incident Manager — Regresión de tickets abiertos.

Recorre todos los tickets asignados, extrae datos del cliente
(collector_id, payment_id, links, packages, serials) y genera
un reporte consolidado que abre en Claude para análisis interactivo.

Uso:
    .venv/bin/python3 regression.py
"""

import sys
import logging
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "logs" / "regression.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("regression")

from src import config
from src import jira_client
from src.extractor import extract
from src.reporter import _extract_text
from src.sla_checker import check_sla, format_elapsed

CLAUDE_BIN = str(Path.home() / ".local/bin/claude")


def _all_text(ticket: dict) -> str:
    """Concatenates description + all comment bodies into a single string."""
    fields = ticket.get("fields", {})
    parts = [_extract_text(fields.get("description") or {})]
    comments = fields.get("comment", {}).get("comments", []) if fields.get("comment") else []
    for c in comments:
        parts.append(_extract_text(c.get("body") or {}))
    return "\n".join(filter(None, parts))


def _last_real_comment(ticket: dict) -> tuple[str, str, str]:
    """Returns (author, date, body) of last non-bot comment."""
    BOT = ["automation for jira", "automation", "noreply", "servicedesk"]
    comments = ticket.get("fields", {}).get("comment", {}).get("comments", []) if ticket.get("fields", {}).get("comment") else []
    for c in reversed(comments):
        email = c.get("author", {}).get("emailAddress", "").lower()
        name  = c.get("author", {}).get("displayName", "")
        if any(b in (email + name).lower() for b in BOT):
            continue
        body = _extract_text(c.get("body") or {})[:200].replace("\n", " ")
        return name, c.get("created", "")[:16].replace("T", " "), body
    return "", "", ""


def run_regression() -> Path:
    logger.info("Starting regression over all open tickets...")
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")

    all_tickets = []
    for project in config.JIRA_PROJECTS:
        # Tickets needing my action
        tickets = jira_client.get_assigned_tickets(project)
        # Tickets waiting on client
        waiting  = jira_client.get_waiting_on_client_tickets(project)
        all_tickets.extend([(t, "acción_requerida") for t in tickets])
        all_tickets.extend([(t, "esperando_cliente") for t in waiting])

    logger.info(f"Total tickets: {len(all_tickets)}")

    rows = []
    for ticket, bucket in all_tickets:
        key     = ticket["key"]
        fields  = ticket.get("fields", {})
        summary = fields.get("summary", "")
        status  = fields.get("status", {}).get("name", "")

        # Get full detail for comments + description
        detail = jira_client.get_ticket_details(key)
        if not detail:
            continue

        full_text = _all_text(detail)
        data      = extract(full_text)
        sla_breached, elapsed = check_sla(detail)
        author, ts, last_body = _last_real_comment(detail)
        url = jira_client.get_ticket_url(key)

        rows.append({
            "key":       key,
            "summary":   summary,
            "status":    status,
            "bucket":    bucket,
            "url":       url,
            "sla":       {"breached": sla_breached, "elapsed": format_elapsed(elapsed)},
            "data":      data,
            "last_comment": {"author": author, "date": ts, "body": last_body},
        })

    # ── Build report ──────────────────────────────────────────────────────
    action   = [r for r in rows if r["bucket"] == "acción_requerida"]
    waiting  = [r for r in rows if r["bucket"] == "esperando_cliente"]

    report = f"""# Regresión de Tickets Abiertos
**Generado:** {date_str}
**Total tickets:** {len(rows)}  |  **Requieren acción:** {len(action)}  |  **Esperando cliente:** {len(waiting)}

---

## Tickets que requieren tu acción ({len(action)})

"""
    for r in action:
        sla_tag = f"⚠️ SLA VENCIDO ({r['sla']['elapsed']})" if r['sla']['breached'] else f"✅ {r['sla']['elapsed']}"
        report += f"### {r['key']} — {r['summary']}\n"
        report += f"**Estado:** {r['status']}  |  **SLA:** {sla_tag}  |  [Ver en Jira]({r['url']})\n\n"
        if r["data"]:
            report += _data_section(r["data"])
        if r["last_comment"]["author"]:
            report += f"**Último comentario** ({r['last_comment']['date']}) — {r['last_comment']['author']}:\n"
            report += f"> {r['last_comment']['body']}\n\n"
        report += "---\n\n"

    report += f"## Esperando respuesta del cliente ({len(waiting)})\n\n"
    for r in waiting:
        sla_tag = f"⚠️ {r['sla']['elapsed']}" if r['sla']['breached'] else r['sla']['elapsed']
        report += f"### {r['key']} — {r['summary']}\n"
        report += f"**Estado:** {r['status']}  |  **Tiempo abierto:** {sla_tag}  |  [Ver en Jira]({r['url']})\n\n"
        if r["data"]:
            report += _data_section(r["data"])
        if r["last_comment"]["author"]:
            report += f"**Último comentario** ({r['last_comment']['date']}) — {r['last_comment']['author']}:\n"
            report += f"> {r['last_comment']['body']}\n\n"
        report += "---\n\n"

    report += "_Generado por MP Incident Manager — regression.py_\n"

    # Save report
    config.REPORTS_DIR.mkdir(exist_ok=True)
    report_path = config.REPORTS_DIR / f"regression_{now.strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"Report saved: {report_path}")
    return report_path


def _data_section(data: dict) -> str:
    lines = []
    labels = {
        "collector_ids": "Collector/Customer IDs",
        "payment_ids":   "Payment IDs",
        "urls":          "Links",
        "packages":      "Packages (APK)",
        "serials":       "Seriales de dispositivo",
        "versions":      "Versiones",
    }
    for key, label in labels.items():
        if data.get(key):
            values = " · ".join(data[key])
            lines.append(f"**{label}:** {values}")
    return "\n".join(lines) + "\n\n" if lines else ""


def open_claude_terminal(report_path: Path):
    prompt_path = Path("/tmp/mp_regression_prompt.txt")
    report_content = report_path.read_text(encoding="utf-8")

    prompt = (
        "Soy Francisco, IX Engineer en Mercado Libre. "
        "Ejecuté una regresión sobre todos mis tickets abiertos. "
        "Aquí está el reporte consolidado con los datos extraídos de cada ticket:\n\n"
        f"{report_content}\n\n"
        "Por favor:\n"
        "1. Dame un resumen ejecutivo del estado general de mi cartera\n"
        "2. Identifica qué tickets son más urgentes y por qué\n"
        "3. Para cada ticket con collector_id o payment_id, indícame qué datos podría "
        "necesitar verificar en el sistema de MP\n"
        "4. Detecta si hay patrones comunes entre tickets (mismo cliente, mismo producto, etc.)\n\n"
        "Luego quédate disponible para que consulte por tickets específicos."
    )
    prompt_path.write_text(prompt, encoding="utf-8")

    launcher_path = Path("/tmp/mp_regression_launch.sh")
    launcher_content = f"""#!/bin/bash
printf "\\033]0;MP Incident Manager — Regresión\\007"
export TERM=xterm-256color
clear
echo ""
printf "\\033[1;35m╔══════════════════════════════════════════════════════╗\\n\\033[0m"
printf "\\033[1;35m║        MP Incident Manager — Regresión               ║\\n\\033[0m"
printf "\\033[1;35m╚══════════════════════════════════════════════════════╝\\n\\033[0m"
echo ""
printf "\\033[1;33m── Reporte de regresión ───────────────────────────────\\n\\033[0m"
cat "{report_path}"
echo ""
printf "\\033[1;32m── Análisis con Claude Code ───────────────────────────\\n\\033[0m"
echo ""
{CLAUDE_BIN} "$(cat '{prompt_path}')"
"""
    launcher_path.write_text(launcher_content)
    launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IEXEC)

    subprocess.Popen([
        "osascript", "-e",
        f'tell application "Terminal" to activate',
        "-e",
        f'tell application "Terminal" to do script "{launcher_path}"'
    ])
    logger.info("Claude regression terminal opened")


if __name__ == "__main__":
    report_path = run_regression()
    open_claude_terminal(report_path)
    print(f"\n✅ Regresión completa — reporte: {report_path}")

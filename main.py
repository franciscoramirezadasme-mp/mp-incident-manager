#!/usr/bin/env python3
"""
MP Incident Manager — daemon de monitoreo de tickets Jira.

Cada ciclo de polling hace dos cosas:
1. Detecta tickets NUEVOS asignados → popup + saludo automático + Claude terminal
2. Detecta NUEVOS COMENTARIOS en tickets ya asignados → popup de alerta + Claude terminal
"""

import logging
import sys
import time
import signal
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "logs" / "incident_manager.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

from src import config
from src import jira_client, notifier, sla_checker, reporter, history


def _get_latest_external_comment(ticket: dict) -> tuple[str | None, str | None, str | None]:
    """
    Returns (comment_id, author_display, created_ts) of the most recent comment
    NOT written by the logged-in user, or (None, None, None) if none exists.
    """
    comments = ticket.get("fields", {}).get("comment", {})
    if not comments:
        return None, None, None
    all_comments = comments.get("comments", [])
    for c in reversed(all_comments):
        author_email = c.get("author", {}).get("emailAddress", "")
        if author_email.lower() != config.JIRA_EMAIL.lower():
            return c.get("id"), c.get("author", {}).get("displayName", ""), c.get("created")
    return None, None, None


def process_new_ticket(ticket: dict, project: str):
    """Full flow for a ticket being seen for the first time."""
    issue_key = ticket["key"]
    fields = ticket.get("fields", {})
    summary = fields.get("summary", "Sin resumen")
    url = jira_client.get_ticket_url(issue_key)

    logger.info(f"NEW ticket: {issue_key} — {summary}")

    # If user already commented on this ticket: just register it silently, no popup, no SLA note.
    already_responded = jira_client.has_user_commented(issue_key)
    if already_responded:
        logger.info(f"{issue_key}: user already commented — marking as seen silently, no alert needed")
        detail = jira_client.get_ticket_details(issue_key)
        latest_ts = None
        if detail:
            _, _, latest_ts = _get_latest_external_comment(detail)
        history.mark_seen(issue_key, last_comment_ts=latest_ts)
        history.record_ticket(
            issue_key=issue_key, summary=summary, project=project,
            sla_breached=False, minutes_elapsed=0, responded=True, url=url,
        )
        return

    # User has NOT responded yet — full alert flow
    sla_breached, minutes_elapsed = sla_checker.check_sla(ticket)
    if sla_breached:
        logger.warning(f"{issue_key}: SLA vencido — {sla_checker.format_elapsed(minutes_elapsed)}")

    # Blocking popup
    notifier.show_ticket_popup(issue_key, summary, sla_breached, minutes_elapsed)

    # Post greeting then transition status to "Esperando por el cliente"
    greeting = reporter.build_greeting_comment(issue_key, summary)
    responded = jira_client.post_public_comment(issue_key, greeting)
    if responded:
        jira_client.transition_to_waiting_for_client(issue_key)

    # Internal SLA note only if user hasn't responded yet (checked above)
    if sla_breached:
        note = reporter.build_sla_internal_note(issue_key, minutes_elapsed)
        jira_client.post_internal_note(issue_key, note)
        notifier.show_sla_alert(issue_key, minutes_elapsed)

    # Generate report and open Claude terminal
    detail = jira_client.get_ticket_details(issue_key)
    report_path = None
    if detail:
        report_path = reporter.generate_report(detail, sla_breached, minutes_elapsed)
        _, _, latest_ts = _get_latest_external_comment(detail)
        history.mark_seen(issue_key, last_comment_ts=latest_ts)

    if report_path:
        notifier.open_claude_terminal(issue_key, str(report_path), sla_breached, minutes_elapsed)

    history.record_ticket(
        issue_key=issue_key, summary=summary, project=project,
        sla_breached=sla_breached, minutes_elapsed=minutes_elapsed,
        responded=responded, url=url,
    )
    logger.info(f"Done processing new ticket {issue_key}")


def process_new_comment(issue_key: str, summary: str, author: str, comment_ts: str):
    """Alert flow when an existing ticket gets a new external comment."""
    logger.info(f"NEW COMMENT on {issue_key} by {author} at {comment_ts}")

    url = jira_client.get_ticket_url(issue_key)

    # Show popup alerting about the new reply
    notifier.show_new_comment_popup(issue_key, summary, author)

    # Update tracked comment timestamp
    history.update_last_comment_ts(issue_key, comment_ts)
    history.record_comment_alert(issue_key)

    # Generate fresh report and open Claude terminal
    detail = jira_client.get_ticket_details(issue_key)
    if detail:
        _, _, sla_breached, minutes_elapsed = False, 0.0, *sla_checker.check_sla(detail)
        report_path = reporter.generate_report(detail, sla_breached, minutes_elapsed)
        notifier.open_claude_terminal(
            issue_key, str(report_path), sla_breached, minutes_elapsed,
            context_note=f"Nuevo comentario de {author}. Revisa el historial y decide cómo responder."
        )

    logger.info(f"Done processing new comment on {issue_key}")


def poll_once():
    new_tickets = 0
    new_comments = 0

    for project in config.JIRA_PROJECTS:
        logger.info(f"Polling {project}...")

        # ── 1. Tickets waiting for MY response ───────────────────
        # Status: "Esperando por ayuda", "En revisión", etc.
        action_needed = jira_client.get_assigned_tickets(project)
        logger.info(f"{project}: {len(action_needed)} ticket(s) waiting for my response")

        for ticket in action_needed:
            issue_key = ticket["key"]
            if history.is_new_ticket(issue_key):
                new_tickets += 1
                try:
                    process_new_ticket(ticket, project)
                except Exception as e:
                    logger.error(f"Error processing new ticket {issue_key}: {e}", exc_info=True)
                    history.mark_seen(issue_key)

        # ── 2. Tickets waiting for CLIENT — check if client replied ──
        # Only alert if a new external comment arrived since last check
        waiting_client = jira_client.get_waiting_on_client_tickets(project)
        logger.info(f"{project}: {len(waiting_client)} ticket(s) waiting on client")

        for ticket in waiting_client:
            issue_key = ticket["key"]
            summary = ticket.get("fields", {}).get("summary", "")

            # Ensure ticket is registered as seen (silent, no popup)
            if history.is_new_ticket(issue_key):
                history.mark_seen(issue_key)

            # Check for new client reply
            detail = jira_client.get_ticket_details(issue_key)
            if not detail:
                continue
            _, author, latest_ts = _get_latest_external_comment(detail)
            if not latest_ts:
                continue

            last_known_ts = history.get_last_comment_ts(issue_key)
            if last_known_ts is None or latest_ts > last_known_ts:
                new_comments += 1
                try:
                    process_new_comment(issue_key, summary, author or "Desconocido", latest_ts)
                except Exception as e:
                    logger.error(f"Error processing new comment on {issue_key}: {e}", exc_info=True)
                    history.update_last_comment_ts(issue_key, latest_ts)

    if new_tickets == 0 and new_comments == 0:
        logger.info("No new tickets or comments found")
    else:
        logger.info(f"Processed: {new_tickets} new ticket(s), {new_comments} new comment(s)")


def run_daemon():
    logger.info("=" * 60)
    logger.info("MP Incident Manager started")
    logger.info(f"Monitoring projects: {', '.join(config.JIRA_PROJECTS)}")
    logger.info(f"SLA threshold: {config.SLA_THRESHOLD_MINUTES} minutes")
    logger.info(f"Poll interval: {config.POLL_INTERVAL_SECONDS} seconds")
    logger.info("=" * 60)

    def handle_shutdown(signum, frame):
        logger.info("Shutdown signal received. Stopping.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        poll_once()
    except Exception as e:
        logger.error(f"Error in initial poll: {e}", exc_info=True)

    while True:
        time.sleep(config.POLL_INTERVAL_SECONDS)
        try:
            poll_once()
        except Exception as e:
            logger.error(f"Error in poll: {e}", exc_info=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--poll-once":
        poll_once()
    else:
        run_daemon()

#!/usr/bin/env python3
"""
MP Incident Manager — daemon de monitoreo de tickets Jira.
Polls IXFS e IXF cada 5 minutos, notifica con popup macOS, responde automáticamente
con saludo, verifica SLA y genera reportes.
"""

import logging
import sys
import time
import signal
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "logs" / "incident_manager.log"

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


def process_ticket(ticket: dict, project: str):
    issue_key = ticket["key"]
    fields = ticket.get("fields", {})
    summary = fields.get("summary", "Sin resumen")
    url = jira_client.get_ticket_url(issue_key)

    logger.info(f"Processing new ticket: {issue_key} — {summary}")

    # Check SLA
    sla_breached, minutes_elapsed = sla_checker.check_sla(ticket)
    if sla_breached:
        logger.warning(f"{issue_key}: SLA vencido — {sla_checker.format_elapsed(minutes_elapsed)}")

    # Show blocking popup — user must acknowledge
    logger.info(f"Showing popup for {issue_key}")
    notifier.show_ticket_popup(issue_key, summary, sla_breached, minutes_elapsed)

    # Check if already responded before auto-posting
    already_responded = jira_client.has_user_commented(issue_key)
    responded = False

    if not already_responded:
        greeting = reporter.build_greeting_comment(issue_key, summary)
        responded = jira_client.post_public_comment(issue_key, greeting)
        if responded:
            logger.info(f"Greeting comment posted on {issue_key}")
        else:
            logger.error(f"Failed to post greeting on {issue_key}")
    else:
        logger.info(f"{issue_key}: already has a comment from us, skipping greeting")
        responded = True

    # Post internal SLA note if breached
    if sla_breached:
        note = reporter.build_sla_internal_note(issue_key, minutes_elapsed)
        jira_client.post_internal_note(issue_key, note)
        notifier.show_sla_alert(issue_key, minutes_elapsed)

    # Generate and save report, then open interactive Claude terminal
    detail = jira_client.get_ticket_details(issue_key)
    report_path = None
    if detail:
        report_path = reporter.generate_report(detail, sla_breached, minutes_elapsed)
        logger.info(f"Report generated for {issue_key}")

    # Open new Terminal window with Claude Code pre-loaded with ticket context
    if report_path:
        notifier.open_claude_terminal(issue_key, str(report_path), sla_breached, minutes_elapsed)

    # Record in history
    history.record_ticket(
        issue_key=issue_key,
        summary=summary,
        project=project,
        sla_breached=sla_breached,
        minutes_elapsed=minutes_elapsed,
        responded=responded,
        url=url,
    )

    # Mark as seen so we don't process it again
    history.mark_seen(issue_key)
    logger.info(f"Done processing {issue_key}")


def poll_once():
    seen = history.get_seen_tickets()
    new_tickets_found = 0

    for project in config.JIRA_PROJECTS:
        logger.info(f"Polling {project}...")
        tickets = jira_client.get_assigned_tickets(project)
        logger.info(f"{project}: {len(tickets)} ticket(s) assigned")

        for ticket in tickets:
            issue_key = ticket["key"]
            if issue_key not in seen:
                new_tickets_found += 1
                try:
                    process_ticket(ticket, project)
                except Exception as e:
                    logger.error(f"Error processing {issue_key}: {e}", exc_info=True)
                    history.mark_seen(issue_key)

    if new_tickets_found == 0:
        logger.info("No new tickets found")
    else:
        logger.info(f"Processed {new_tickets_found} new ticket(s)")


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

    # Initial poll immediately on start
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

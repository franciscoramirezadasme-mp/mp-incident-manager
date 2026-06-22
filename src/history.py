import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from src import config

logger = logging.getLogger(__name__)

HISTORY_FILE = config.DATA_DIR / "ticket_history.json"
SEEN_FILE = config.DATA_DIR / "seen_tickets.json"


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ── Seen tickets tracking ──────────────────────────────────────────────────

def get_seen_data() -> dict:
    """Returns full seen data dict: {key: {last_comment: iso, ...}}"""
    return _load_json(SEEN_FILE)


def is_new_ticket(issue_key: str) -> bool:
    data = _load_json(SEEN_FILE)
    return issue_key not in data.get("tickets", {})


def mark_seen(issue_key: str, last_comment_ts: str | None = None):
    data = _load_json(SEEN_FILE)
    tickets = data.get("tickets", {})
    if issue_key not in tickets:
        tickets[issue_key] = {}
    if last_comment_ts:
        tickets[issue_key]["last_comment_ts"] = last_comment_ts
    data["tickets"] = tickets
    _save_json(SEEN_FILE, data)


def get_last_comment_ts(issue_key: str) -> str | None:
    data = _load_json(SEEN_FILE)
    return data.get("tickets", {}).get(issue_key, {}).get("last_comment_ts")


def update_last_comment_ts(issue_key: str, ts: str):
    data = _load_json(SEEN_FILE)
    tickets = data.get("tickets", {})
    if issue_key not in tickets:
        tickets[issue_key] = {}
    tickets[issue_key]["last_comment_ts"] = ts
    data["tickets"] = tickets
    _save_json(SEEN_FILE, data)


def get_last_bot_ts(issue_key: str) -> str | None:
    data = _load_json(SEEN_FILE)
    return data.get("tickets", {}).get(issue_key, {}).get("last_bot_ts")


def update_last_bot_ts(issue_key: str, ts: str):
    data = _load_json(SEEN_FILE)
    tickets = data.get("tickets", {})
    if issue_key not in tickets:
        tickets[issue_key] = {}
    tickets[issue_key]["last_bot_ts"] = ts
    data["tickets"] = tickets
    _save_json(SEEN_FILE, data)


def is_bot_suppressed(issue_key: str) -> bool:
    data = _load_json(SEEN_FILE)
    return data.get("tickets", {}).get(issue_key, {}).get("suppress_bots", False)


def suppress_bots(issue_key: str):
    data = _load_json(SEEN_FILE)
    tickets = data.get("tickets", {})
    if issue_key not in tickets:
        tickets[issue_key] = {}
    tickets[issue_key]["suppress_bots"] = True
    data["tickets"] = tickets
    _save_json(SEEN_FILE, data)
    logger.info(f"{issue_key}: automation notifications suppressed")


# ── Ticket history ─────────────────────────────────────────────────────────

def record_ticket(
    issue_key: str,
    summary: str,
    project: str,
    sla_breached: bool,
    minutes_elapsed: float,
    responded: bool,
    url: str,
):
    now_iso = datetime.now(timezone.utc).isoformat()
    data = _load_json(HISTORY_FILE)
    history = data.get("tickets", {})

    if issue_key not in history:
        history[issue_key] = {
            "key": issue_key,
            "summary": summary,
            "project": project,
            "url": url,
            "first_seen": now_iso,
            "first_response_sent": now_iso if responded else None,
            "sla_breached_on_arrival": sla_breached,
            "elapsed_minutes_on_arrival": round(minutes_elapsed, 1),
            "new_comment_alerts": 0,
        }
    else:
        if responded and not history[issue_key].get("first_response_sent"):
            history[issue_key]["first_response_sent"] = now_iso

    data["tickets"] = history
    _save_json(HISTORY_FILE, data)
    logger.info(f"Recorded {issue_key} in history (sla_breached={sla_breached})")


def record_comment_alert(issue_key: str):
    data = _load_json(HISTORY_FILE)
    history = data.get("tickets", {})
    if issue_key in history:
        history[issue_key]["new_comment_alerts"] = history[issue_key].get("new_comment_alerts", 0) + 1
        history[issue_key]["last_comment_alert"] = datetime.now(timezone.utc).isoformat()
    data["tickets"] = history
    _save_json(HISTORY_FILE, data)


def get_history() -> list[dict]:
    data = _load_json(HISTORY_FILE)
    return list(data.get("tickets", {}).values())

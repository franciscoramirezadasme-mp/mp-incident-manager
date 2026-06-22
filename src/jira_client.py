import requests
import logging
from requests.auth import HTTPBasicAuth
from src import config

logger = logging.getLogger(__name__)


def _get_auth_and_url(project_key: str):
    project = project_key.split("-")[0] if "-" in project_key else project_key
    base_url = config.INSTANCE_MAP.get(project, config.JIRA_URL)
    token = config.TOKEN_MAP.get(project, config.JIRA_TOKEN)
    auth = HTTPBasicAuth(config.JIRA_EMAIL, token)
    return base_url, auth


def get_assigned_tickets(project: str) -> list[dict]:
    base_url, auth = _get_auth_and_url(project)
    body = {
        "jql": (
            f"project = {project} "
            f"AND assignee = currentUser() "
            f"AND statusCategory != Done "
            f"ORDER BY created DESC"
        ),
        "maxResults": 50,
        "fields": ["summary", "status", "created", "assignee", "reporter", "priority", "customfield_10020"],
    }
    try:
        resp = requests.post(
            f"{base_url}/rest/api/3/search/jql",
            json=body,
            auth=auth,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("issues", [])
    except Exception as e:
        logger.error(f"Error fetching tickets from {project}: {e}")
        return []


def get_ticket_details(issue_key: str) -> dict | None:
    base_url, auth = _get_auth_and_url(issue_key)
    fields = "summary,status,created,assignee,reporter,priority,comment,description,customfield_10020,customfield_10015"
    try:
        resp = requests.get(
            f"{base_url}/rest/api/3/issue/{issue_key}",
            params={"fields": fields},
            auth=auth,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Error fetching ticket {issue_key}: {e}")
        return None


def has_user_commented(issue_key: str) -> bool:
    base_url, auth = _get_auth_and_url(issue_key)
    try:
        resp = requests.get(
            f"{base_url}/rest/api/3/issue/{issue_key}/comment",
            params={"maxResults": 100},
            auth=auth,
            timeout=15,
        )
        resp.raise_for_status()
        comments = resp.json().get("comments", [])
        for c in comments:
            author_email = c.get("author", {}).get("emailAddress", "")
            if author_email.lower() == config.JIRA_EMAIL.lower():
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking comments on {issue_key}: {e}")
        return False


def post_public_comment(issue_key: str, text: str) -> bool:
    base_url, auth = _get_auth_and_url(issue_key)
    body = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        }
    }
    try:
        resp = requests.post(
            f"{base_url}/rest/api/3/issue/{issue_key}/comment",
            json=body,
            auth=auth,
            timeout=15,
        )
        resp.raise_for_status()
        logger.info(f"Public comment posted on {issue_key}")
        return True
    except Exception as e:
        logger.error(f"Error posting comment on {issue_key}: {e}")
        return False


def post_internal_note(issue_key: str, text: str) -> bool:
    base_url, auth = _get_auth_and_url(issue_key)

    # Try Service Desk API first (Jira Service Management internal note)
    sd_body = {"body": text, "public": False}
    try:
        resp = requests.post(
            f"{base_url}/rest/servicedeskapi/request/{issue_key}/comment",
            json=sd_body,
            auth=auth,
            timeout=15,
        )
        if resp.ok:
            logger.info(f"Internal note posted on {issue_key} via servicedeskapi")
            return True
    except Exception:
        pass

    # Fallback: ADF comment with Service Desk Team visibility
    body = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        },
        "visibility": {
            "type": "role",
            "value": "Service Desk Team",
        },
    }
    try:
        resp = requests.post(
            f"{base_url}/rest/api/3/issue/{issue_key}/comment",
            json=body,
            auth=auth,
            timeout=15,
        )
        resp.raise_for_status()
        logger.info(f"Internal note posted on {issue_key} via api/3")
        return True
    except Exception as e:
        logger.error(f"Error posting internal note on {issue_key}: {e}")
        return False


def get_ticket_url(issue_key: str) -> str:
    base_url, _ = _get_auth_and_url(issue_key)
    return f"{base_url}/browse/{issue_key}"

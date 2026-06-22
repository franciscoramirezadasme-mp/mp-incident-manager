import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

JIRA_URL = os.getenv("JIRA_URL", "https://mercadolibre-externals.atlassian.net")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN = os.getenv("JIRA_TOKEN", "")

JIRA_INTERNAL_URL = os.getenv("JIRA_INTERNAL_URL", "https://mercadolibre.atlassian.net")
JIRA_INTERNAL_TOKEN = os.getenv("JIRA_INTERNAL_TOKEN", JIRA_TOKEN)

JIRA_PROJECTS = [p.strip() for p in os.getenv("JIRA_PROJECTS", "IXFS,IXF").split(",")]

SLA_THRESHOLD_MINUTES = int(os.getenv("SLA_THRESHOLD_MINUTES", "5"))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TIMEZONE = os.getenv("TIMEZONE", "America/Santiago")

DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

INSTANCE_MAP = {
    "IXFS": JIRA_URL,
    "IXF": JIRA_INTERNAL_URL,
    "WCS": JIRA_INTERNAL_URL,
}

TOKEN_MAP = {
    "IXFS": JIRA_TOKEN,
    "IXF": JIRA_INTERNAL_TOKEN,
    "WCS": JIRA_INTERNAL_TOKEN,
}

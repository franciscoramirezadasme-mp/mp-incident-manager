"""
Extrae datos estructurados de clientes desde el contenido de tickets Jira:
collector_id, payment_id, user, links, package_name, device SN, etc.
"""
import re

# MercadoPago collector/customer IDs (7-12 digit numbers that appear near keywords)
_RE_COLLECTOR = re.compile(
    r'(?:collector[_\s]?id|customer[_\s]?id|seller[_\s]?id|cust[_\s]?id|client[_\s]?id'
    r'|cliente|vendedor|user[_\s]?id)[:\s#=]+(\d{6,12})',
    re.IGNORECASE
)
# Standalone long numeric IDs (payment IDs are typically 11-19 digits)
_RE_PAYMENT = re.compile(
    r'(?:payment[_\s]?id|pago[_\s]?id|order[_\s]?id|transaction|transacci[oó]n)[:\s#=]+(\d{10,19})',
    re.IGNORECASE
)
# Fallback: bare long numbers that look like MP payment IDs
_RE_BARE_PAYMENT = re.compile(r'\b(\d{11,19})\b')

# URLs
_RE_URL = re.compile(r'https?://[^\s\)\]\"\'<>]+', re.IGNORECASE)

# Android package names
_RE_PACKAGE = re.compile(r'\b([a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*){2,})\b')

# Device serial numbers (Newland/PAX format: letters+digits, 8-16 chars)
_RE_SN = re.compile(
    r'(?:serie|serial|s/?n|device|dispositivo|terminal)[:\s#=]+([A-Z0-9]{8,16})',
    re.IGNORECASE
)

# App version numbers
_RE_VERSION = re.compile(
    r'(?:version|versi[oó]n|apk)[:\s#=v]+(\d+[\.\d]*)',
    re.IGNORECASE
)


def extract(text: str) -> dict:
    if not text:
        return {}

    collector_ids = list(dict.fromkeys(_RE_COLLECTOR.findall(text)))
    payment_ids   = list(dict.fromkeys(_RE_PAYMENT.findall(text)))
    urls          = list(dict.fromkeys(_RE_URL.findall(text)))
    packages      = list(dict.fromkeys(_RE_PACKAGE.findall(text)))
    serials       = list(dict.fromkeys(_RE_SN.findall(text)))
    versions      = list(dict.fromkeys(_RE_VERSION.findall(text)))

    # Fallback bare payment IDs (only if no labeled ones found)
    if not payment_ids:
        candidates = _RE_BARE_PAYMENT.findall(text)
        # Exclude values that look like dates, zip codes, phone numbers
        payment_ids = [c for c in candidates if not _looks_like_noise(c)]

    # Filter packages to plausible Android package names
    packages = [p for p in packages if _is_android_package(p)][:5]

    return {k: v for k, v in {
        "collector_ids": collector_ids,
        "payment_ids":   payment_ids[:10],
        "urls":          [u for u in urls if "atlassian" not in u][:10],
        "packages":      packages,
        "serials":       serials,
        "versions":      versions[:5],
    }.items() if v}


def _looks_like_noise(n: str) -> bool:
    # Skip sequences that are clearly not payment IDs
    if re.match(r'^(19|20)\d{6,}$', n):  # date-like
        return True
    return False


def _is_android_package(p: str) -> bool:
    parts = p.split(".")
    if len(parts) < 3:
        return False
    # Must have at least one part that's a real word, not just numbers
    return any(re.search(r'[a-z]{2,}', part) for part in parts)

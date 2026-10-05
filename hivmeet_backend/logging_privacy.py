"""Privacy-preserving filters for application logs.

The filter is deliberately installed on handlers rather than individual
loggers so third-party and legacy application messages receive the same
redaction before they leave the process.
"""
from __future__ import annotations

import hashlib
import logging
import re
import traceback
from urllib.parse import urlsplit


_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
_URL_RE = re.compile(r"https?://[^\s\]\[{}()<>'\"]+")
_PHONE_RE = re.compile(r"(?<!\w)\+\d(?:[\s().-]*\d){7,14}(?!\w)")
_COORDINATE_RE = re.compile(
    r"(?i)\b(latitude|longitude|lat|lng)\b\s*[:=]\s*"
    r"[-+]?\d{1,3}(?:\.\d+)?"
)
_SENSITIVE_FIELD_RE = re.compile(
    r"(?i)(\b(?:display_?name|first_?name|last_?name|bio|address|city|"
    r"location|photo(?:_url)?|thumbnail(?:_url)?|media_url|fcm_?token)\b"
    r"\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^,\s}\]\n]+)"
)
# JWT (three base64url segments) and bearer tokens, wherever they appear —
# not just after a recognized field name like the pattern above requires.
_JWT_OR_BEARER_RE = re.compile(
    r"(?:Bearer\s+)?\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]


def redact_log_text(value) -> str:
    """Redact direct identifiers while retaining useful technical context."""
    text = str(value)
    text = _EMAIL_RE.sub(
        lambda match: f"<email:{_fingerprint(match.group(0).lower())}>",
        text,
    )
    text = _UUID_RE.sub(
        lambda match: f"<id:{_fingerprint(match.group(0).lower())}>",
        text,
    )
    text = _PHONE_RE.sub('<phone:redacted>', text)
    text = _JWT_OR_BEARER_RE.sub('<token:redacted>', text)
    text = _COORDINATE_RE.sub(
        lambda match: f"{match.group(1)}=<coordinate:redacted>",
        text,
    )
    text = _SENSITIVE_FIELD_RE.sub(
        lambda match: f"{match.group(1)}<redacted>",
        text,
    )

    def _safe_url(match: re.Match) -> str:
        try:
            hostname = urlsplit(match.group(0)).hostname or 'unknown'
        except ValueError:
            hostname = 'unknown'
        return f"<url:{hostname}>"

    return _URL_RE.sub(_safe_url, text)


class PrivacyRedactionFilter(logging.Filter):
    """Scrub PII from a record before any formatter writes it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_log_text(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = redact_log_text(
                ''.join(traceback.format_exception(*record.exc_info))
            )
        elif record.exc_text:
            record.exc_text = redact_log_text(record.exc_text)
        return True

import logging
import re

REDACTIONS = (
    (
        re.compile(r"(?i)\b(sk|pk|rk)_(test|live)_[A-Za-z0-9_-]+"),
        "[REDACTED_STRIPE_KEY]",
    ),
    (re.compile(r"(?i)\bwhsec_[A-Za-z0-9_-]+"), "[REDACTED_WEBHOOK_SECRET]"),
    (
        re.compile(r"(?i)(Stripe-Signature\s*[:=]\s*)[^\s;]+"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"/(?:e|i|p)/[A-Za-z0-9_-]{20,}(?=/|\?|\s|$)"),
        "/public/[REDACTED_TOKEN]",
    ),
    (
        re.compile(r"(?i)((?:token|secret|password)\s*[:=]\s*)[^\s,;]+"),
        r"\1[REDACTED]",
    ),
)


def redact(value):
    if not isinstance(value, str):
        return value
    for pattern, replacement in REDACTIONS:
        value = pattern.sub(replacement, value)
    return value


def _redact_args(value):
    if isinstance(value, dict):
        return {key: _redact_args(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_redact_args(item) for item in value)
    if isinstance(value, list):
        return [_redact_args(item) for item in value]
    return redact(value)


class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:
            record.msg = redact(record.msg)
            record.args = _redact_args(record.args)
        return True

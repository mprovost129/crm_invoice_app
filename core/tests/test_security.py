import logging
import re
from pathlib import Path

from django.conf import settings

from core.logging import SensitiveDataFilter


def test_security_headers_and_subresource_integrity_are_present(client):
    response = client.get("/")

    assert response.status_code == 200
    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "'unsafe-eval'" not in csp
    assert response["Permissions-Policy"]
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"
    assert b'integrity="sha384-' in response.content
    assert b'"allowEval":false' in response.content


def test_inline_event_handlers_are_not_used_in_templates():
    templates = Path(settings.BASE_DIR, "templates")
    inline_handler = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)

    violations = []
    for path in templates.rglob("*.html"):
        if inline_handler.search(path.read_text(encoding="utf-8")):
            violations.append(str(path.relative_to(templates)))

    assert violations == []


def test_invalid_or_oversized_request_id_is_replaced(client):
    supplied = "unsafe header value!" * 20
    response = client.get("/", HTTP_X_REQUEST_ID=supplied)

    assert response["X-Request-ID"] != supplied
    assert re.fullmatch(r"[a-f0-9]{32}", response["X-Request-ID"])


def test_logging_filter_redacts_keys_signatures_passwords_and_public_tokens():
    public_token = "A" * 43
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=("key=%s path=%s Stripe-Signature=%s password=%s secret=%s"),
        args=(
            "sk_test_not-a-real-key-123",
            f"/p/{public_token}/",
            "t=1,v1=not-real",
            "do-not-log",
            "whsec_not-real-secret",
        ),
        exc_info=None,
    )

    assert SensitiveDataFilter().filter(record)
    message = record.getMessage()
    assert "sk_test_" not in message
    assert public_token not in message
    assert "do-not-log" not in message
    assert "whsec_" not in message
    assert "v1=not-real" not in message

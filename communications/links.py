import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.http import Http404
from django.utils import timezone

from .models import PublicDocumentLink


def token_digest(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_public_link(*, estimate=None, invoice=None, purpose):
    document = estimate or invoice
    if (estimate is None) == (invoice is None):
        raise ValueError("Create a link for exactly one document.")
    raw_token = secrets.token_urlsafe(32)
    link = PublicDocumentLink(
        business=document.business,
        estimate=estimate,
        invoice=invoice,
        purpose=purpose,
        token_digest=token_digest(raw_token),
        expires_at=timezone.now()
        + timedelta(days=settings.PUBLIC_DOCUMENT_LINK_TTL_DAYS),
    )
    link.full_clean()
    link.save()
    return link, raw_token


def resolve_public_link(*, raw_token, allowed_purposes, target="estimate"):
    digest = token_digest(raw_token)
    link = (
        PublicDocumentLink.objects.select_related(
            "business",
            "estimate",
            "estimate__document_snapshot",
            "invoice",
            "invoice__document_snapshot",
        )
        .filter(token_digest=digest, purpose__in=allowed_purposes)
        .first()
    )
    if target == "estimate" and link and link.estimate_id is None:
        link = None
    if target == "invoice" and link and link.invoice_id is None:
        link = None
    if link is None or not link.is_active:
        raise Http404("Document link not found.")
    return link

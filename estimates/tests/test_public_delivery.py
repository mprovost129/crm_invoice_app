import hashlib
import re
from datetime import timedelta

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http import Http404
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from communications.emailing import process_outbox_event, queue_estimate_email
from communications.links import create_public_link, resolve_public_link, token_digest
from communications.models import (
    EmailDelivery,
    FileAsset,
    OutboxEvent,
    PublicDocumentLink,
)
from communications.pdf import get_or_create_estimate_pdf
from estimates.models import Estimate, EstimateAcceptance
from estimates.public_services import accept_public_estimate, record_public_view
from workspaces.tests.helpers import create_business, create_owner_tenancy

from .helpers import create_issued_estimate


@pytest.mark.django_db
def test_public_link_stores_only_digest_and_enforces_purpose_and_expiry():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    link, token = create_public_link(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.VIEW,
    )

    assert token not in link.token_digest
    assert link.token_digest == token_digest(token)
    assert (
        resolve_public_link(
            raw_token=token, allowed_purposes=(PublicDocumentLink.Purpose.VIEW,)
        )
        == link
    )
    with pytest.raises(Http404):
        resolve_public_link(
            raw_token=token,
            allowed_purposes=(PublicDocumentLink.Purpose.RESPOND,),
        )
    link.expires_at = timezone.now() - timedelta(seconds=1)
    link.save(update_fields=("expires_at", "updated_at"))
    with pytest.raises(Http404):
        resolve_public_link(
            raw_token=token, allowed_purposes=(PublicDocumentLink.Purpose.VIEW,)
        )


@pytest.mark.django_db
def test_first_public_view_changes_status_once_and_tracks_accesses():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    link, _ = create_public_link(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.VIEW,
    )

    record_public_view(link=link)
    first_viewed_at = Estimate.objects.get(pk=estimate.pk).first_viewed_at
    record_public_view(link=link)

    estimate.refresh_from_db()
    link.refresh_from_db()
    assert estimate.status == Estimate.Status.VIEWED
    assert estimate.first_viewed_at == first_viewed_at
    assert link.access_count == 2


@pytest.mark.django_db
def test_public_acceptance_records_evidence_and_revokes_response_links():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    link, _ = create_public_link(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.RESPOND,
    )

    acceptance = accept_public_estimate(
        link=link,
        accepted_by_name="Jordan Taylor",
        accepted_by_email="jordan@example.com",
        ip_address="203.0.113.5",
        user_agent="Example Browser",
    )

    estimate.refresh_from_db()
    link.refresh_from_db()
    assert estimate.status == Estimate.Status.ACCEPTED
    assert acceptance.method == EstimateAcceptance.Method.ONLINE
    assert acceptance.ip_address == "203.0.113.5"
    assert acceptance.total_snapshot == estimate.total
    assert link.revoked_at is not None
    with pytest.raises(ValidationError):
        accept_public_estimate(
            link=link,
            accepted_by_name="Again",
            accepted_by_email="",
        )


@pytest.mark.django_db
def test_pdf_generation_is_content_addressed_and_reused(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)

    first = get_or_create_estimate_pdf(estimate=estimate)
    second = get_or_create_estimate_pdf(estimate=estimate)

    assert first.pk == second.pk
    assert FileAsset.objects.count() == 1
    with default_storage.open(first.storage_name, "rb") as generated:
        content = generated.read()
    assert content.startswith(b"%PDF-")
    assert hashlib.sha256(content).hexdigest() == first.content_sha256
    assert len(content) == first.byte_size


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_outbox_email_contains_private_links_and_pdf(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)

    delivery = queue_estimate_email(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
        recipient="customer@example.com",
    )

    delivery.refresh_from_db()
    event = OutboxEvent.objects.get(payload__delivery_id=str(delivery.pk))
    if event.status != OutboxEvent.Status.COMPLETED:
        process_outbox_event(event.pk)
        event.refresh_from_db()
        delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.SENT
    assert event.status == OutboxEvent.Status.COMPLETED
    assert event.attempts == 1
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["customer@example.com"]
    assert message.attachments[0][2] == "application/pdf"
    tokens = re.findall(r"/e/([^/]+)/", message.body)
    assert len(tokens) == 2
    assert set(PublicDocumentLink.objects.values_list("token_digest", flat=True)) == {
        token_digest(token) for token in tokens
    }
    assert not any(token in event.payload.values() for token in tokens)


@pytest.mark.django_db
def test_processing_outbox_event_is_not_claimed_twice(monkeypatch):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    delivery = EmailDelivery.objects.create(
        business=business,
        estimate=estimate,
        recipient="customer@example.com",
        subject="Estimate",
    )
    event = OutboxEvent.objects.create(
        business=business,
        event_type="estimate.email",
        dedupe_key=f"already-processing:{delivery.pk}",
        payload={"delivery_id": str(delivery.pk)},
        status=OutboxEvent.Status.PROCESSING,
    )
    rendered = []
    monkeypatch.setattr(
        "communications.emailing.get_or_create_estimate_pdf",
        lambda **kwargs: rendered.append(kwargs),
    )

    process_outbox_event(event.pk)

    event.refresh_from_db()
    assert event.status == OutboxEvent.Status.PROCESSING
    assert event.attempts == 0
    assert rendered == []


@pytest.mark.django_db
def test_public_web_routes_are_non_enumerating_and_set_privacy_headers(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    link, token = create_public_link(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.VIEW,
    )

    response = client.get(reverse("estimates:public-view", args=(token,)))

    assert response.status_code == 200
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert estimate.number.encode() in response.content
    assert (
        client.get(reverse("estimates:public-view", args=("invalid",))).status_code
        == 404
    )
    assert (
        client.get(reverse("estimates:public-respond", args=(token,))).status_code
        == 404
    )
    link.refresh_from_db()
    assert link.access_count == 1

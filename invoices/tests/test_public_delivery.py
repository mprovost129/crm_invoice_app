import hashlib
import re
from decimal import Decimal

import pytest
from django.core import mail
from django.core.files.storage import default_storage
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from communications.emailing import (
    process_outbox_event,
    queue_invoice_email,
    queue_payment_receipt,
)
from communications.links import create_public_link, token_digest
from communications.models import (
    EmailDelivery,
    FileAsset,
    OutboxEvent,
    PublicDocumentLink,
)
from communications.pdf import (
    get_or_create_invoice_pdf,
    get_or_create_payment_receipt_pdf,
)
from invoices.models import Invoice
from payments.models import Payment
from payments.services import post_manual_payment
from workspaces.tests.helpers import create_business, create_owner_tenancy

from .helpers import create_converted_invoice


def _process_delivery(delivery):
    event = OutboxEvent.objects.get(payload__delivery_id=str(delivery.pk))
    if event.status != OutboxEvent.Status.COMPLETED:
        process_outbox_event(event.pk)
    delivery.refresh_from_db()
    event.refresh_from_db()
    return event


@pytest.mark.django_db
def test_invoice_pdf_is_reused_until_live_balance_changes(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)

    first = get_or_create_invoice_pdf(invoice=invoice)
    second = get_or_create_invoice_pdf(invoice=invoice)
    assert first.pk == second.pk

    post_manual_payment(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        amount=Decimal("25"),
        paid_on=timezone.localdate(),
        method=Payment.Method.CASH,
    )
    invoice.refresh_from_db()
    after_payment = get_or_create_invoice_pdf(invoice=invoice)
    assert after_payment.pk != first.pk
    assert FileAsset.objects.filter(invoice=invoice).count() == 2
    with default_storage.open(after_payment.storage_name, "rb") as generated:
        content = generated.read()
    assert content.startswith(b"%PDF-")
    assert hashlib.sha256(content).hexdigest() == after_payment.content_sha256


@pytest.mark.django_db
def test_receipt_pdf_is_immutable_and_reused(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    payment = post_manual_payment(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        amount=Decimal("50"),
        paid_on=timezone.localdate(),
        method=Payment.Method.CHECK,
        reference="CHK-1042",
    )

    first = get_or_create_payment_receipt_pdf(payment=payment)
    second = get_or_create_payment_receipt_pdf(payment=payment)
    assert first.pk == second.pk
    assert first.payment == payment
    with default_storage.open(first.storage_name, "rb") as generated:
        content = generated.read()
    assert content.startswith(b"%PDF-")
    assert hashlib.sha256(content).hexdigest() == first.content_sha256


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_invoice_reminder_and_receipt_emails_are_durable_and_private(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)

    invoice_delivery = queue_invoice_email(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        recipient="customer@example.com",
        reminder=True,
    )
    invoice_event = _process_delivery(invoice_delivery)
    payment = post_manual_payment(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        amount=Decimal("50"),
        paid_on=timezone.localdate(),
        method=Payment.Method.ACH,
    )
    receipt_delivery = queue_payment_receipt(
        actor=user,
        business_id=business.pk,
        payment_id=payment.pk,
        recipient="customer@example.com",
    )
    receipt_event = _process_delivery(receipt_delivery)

    assert (
        invoice_delivery.status == receipt_delivery.status == EmailDelivery.Status.SENT
    )
    assert invoice_event.status == receipt_event.status == OutboxEvent.Status.COMPLETED
    assert len(mail.outbox) == 2
    assert all(
        message.attachments[0][2] == "application/pdf" for message in mail.outbox
    )
    tokens = [
        re.search(r"/i/([^/]+)/", message.body).group(1) for message in mail.outbox
    ]
    assert set(PublicDocumentLink.objects.values_list("token_digest", flat=True)) == {
        token_digest(token) for token in tokens
    }
    assert all(
        token not in str(event.payload)
        for token in tokens
        for event in (invoice_event, receipt_event)
    )


@pytest.mark.django_db
def test_public_invoice_view_tracks_access_and_uses_privacy_headers(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    link, token = create_public_link(
        invoice=invoice, purpose=PublicDocumentLink.Purpose.VIEW
    )

    response = client.get(reverse("invoices:public-view", args=(token,)))

    invoice.refresh_from_db()
    link.refresh_from_db()
    assert response.status_code == 200
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert invoice.status == Invoice.Status.VIEWED
    assert invoice.number.encode() in response.content
    assert link.access_count == 1
    assert (
        client.get(reverse("invoices:public-view", args=("invalid",))).status_code
        == 404
    )

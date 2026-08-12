from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from communications.links import create_public_link
from communications.models import PublicDocumentLink
from invoices.tests.helpers import create_direct_invoice
from payments.models import (
    ConnectedAccount,
    ConnectWebhookEvent,
    InvoicePaymentAttempt,
    Payment,
)
from payments.online_services import (
    process_connect_webhook,
    start_invoice_checkout,
    store_connect_webhook,
)
from payments.services import post_manual_payment
from payments.stripe_gateway import InvoiceCheckoutResult, to_minor_units
from workspaces.tests.helpers import create_business, create_owner_tenancy


def ready_account(business, provider_id="acct_business_1"):
    return ConnectedAccount.objects.create(
        business=business,
        provider_account_id=provider_id,
        status=ConnectedAccount.Status.READY,
        details_submitted=True,
        charges_enabled=True,
        payouts_enabled=True,
        provider_synced_at=timezone.now(),
    )


def prepare_checkout(monkeypatch):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_direct_invoice(user=user, business=business)
    ready_account(business)
    link, token = create_public_link(
        invoice=invoice, purpose=PublicDocumentLink.Purpose.PAY
    )

    def fake_checkout(**kwargs):
        return InvoiceCheckoutResult(
            session_id="cs_invoice_1",
            url="https://checkout.stripe.test/cs_invoice_1",
            expires_at=timezone.now() + timedelta(minutes=30),
        )

    monkeypatch.setattr(
        "payments.online_services.create_invoice_checkout", fake_checkout
    )
    attempt = start_invoice_checkout(link=link, raw_token=token)
    return user, business, invoice, attempt


@pytest.mark.django_db
def test_online_checkout_success_posts_one_separate_invoice_payment(monkeypatch):
    _, business, invoice, attempt = prepare_checkout(monkeypatch)
    payload = {
        "id": "evt_connect_checkout_1",
        "type": "checkout.session.completed",
        "account": "acct_business_1",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_invoice_1",
                "object": "checkout.session",
                "payment_status": "paid",
                "payment_intent": "pi_invoice_1",
                "metadata": {"payment_attempt_id": str(attempt.pk)},
            }
        },
    }
    event, created = store_connect_webhook(payload=payload)
    assert created

    process_connect_webhook(event_id=event.pk)
    process_connect_webhook(event_id=event.pk)

    invoice.refresh_from_db()
    attempt.refresh_from_db()
    event.refresh_from_db()
    payment = Payment.objects.get(provider_payment_id="pi_invoice_1")
    assert payment.source == Payment.Source.ONLINE
    assert payment.business_id == business.pk
    assert payment.amount == invoice.total
    assert invoice.balance_due == Decimal("0.00")
    assert attempt.status == InvoicePaymentAttempt.Status.COMPLETED
    assert event.status == ConnectWebhookEvent.Status.COMPLETED
    assert event.attempts == 1
    assert Payment.objects.count() == 1


@pytest.mark.django_db
def test_connect_webhook_rejects_cross_account_payment_attempt(monkeypatch):
    _, _, _, attempt = prepare_checkout(monkeypatch)
    payload = {
        "id": "evt_connect_wrong_account",
        "type": "payment_intent.succeeded",
        "account": "acct_someone_else",
        "livemode": False,
        "data": {
            "object": {
                "id": "pi_wrong_account",
                "object": "payment_intent",
                "metadata": {"payment_attempt_id": str(attempt.pk)},
            }
        },
    }
    event, _ = store_connect_webhook(payload=payload)

    with pytest.raises(ValidationError, match="does not match"):
        process_connect_webhook(event_id=event.pk)

    event.refresh_from_db()
    assert event.status == ConnectWebhookEvent.Status.FAILED
    assert not Payment.objects.exists()


@pytest.mark.django_db
def test_active_online_checkout_blocks_manual_payment(monkeypatch):
    user, business, invoice, _ = prepare_checkout(monkeypatch)

    with pytest.raises(ValidationError, match="online checkout is active"):
        post_manual_payment(
            actor=user,
            business_id=business.pk,
            invoice_id=invoice.pk,
            amount=Decimal("10.00"),
            paid_on=timezone.localdate(),
            method=Payment.Method.CASH,
        )


@pytest.mark.django_db
def test_connect_account_updated_event_is_tenant_matched():
    _, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    account = ConnectedAccount.objects.create(
        business=business,
        provider_account_id="acct_update_1",
    )
    payload = {
        "id": "evt_connect_account_1",
        "type": "account.updated",
        "account": "acct_update_1",
        "livemode": False,
        "data": {
            "object": {
                "id": "acct_update_1",
                "object": "account",
                "details_submitted": True,
                "charges_enabled": True,
                "payouts_enabled": True,
                "requirements": {"currently_due": [], "disabled_reason": None},
            }
        },
    }
    event, _ = store_connect_webhook(payload=payload)

    process_connect_webhook(event_id=event.pk)

    account.refresh_from_db()
    assert account.status == ConnectedAccount.Status.READY


def test_minor_unit_conversion_is_exact_and_currency_checked():
    assert to_minor_units(amount=Decimal("10.25"), currency="USD") == 1025
    with pytest.raises(ValueError, match="precision"):
        to_minor_units(amount=Decimal("10.001"), currency="USD")
    with pytest.raises(ValueError, match="Unsupported"):
        to_minor_units(amount=Decimal("10.00"), currency="JPY")


@pytest.mark.django_db
def test_connect_webhook_rejects_wrong_environment_mode(settings):
    settings.STRIPE_LIVE_MODE = True
    payload = {
        "id": "evt_connect_test_in_live_environment",
        "type": "payment_intent.succeeded",
        "account": "acct_test",
        "livemode": False,
        "data": {"object": {}},
    }

    with pytest.raises(ValueError, match="mode"):
        store_connect_webhook(payload=payload)

    assert not ConnectWebhookEvent.objects.exists()

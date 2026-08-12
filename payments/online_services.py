from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from billing.entitlements import Feature, require_feature
from communications.emailing import queue_payment_receipt
from communications.models import PublicDocumentLink
from communications.notifications import notify_business_owner
from invoices.models import Invoice
from workspaces.policies import owner_business_for_actor

from .models import (
    ConnectedAccount,
    ConnectWebhookEvent,
    InvoicePaymentAttempt,
    Payment,
)
from .stripe_gateway import (
    create_express_account,
    create_invoice_checkout,
    create_onboarding_link,
    retrieve_account,
)


def _status_from_account(data):
    requirements = data.get("requirements") or {}
    disabled_reason = requirements.get("disabled_reason") or ""
    details = bool(data.get("details_submitted"))
    charges = bool(data.get("charges_enabled"))
    payouts = bool(data.get("payouts_enabled"))
    if disabled_reason:
        return ConnectedAccount.Status.DISABLED
    if details and charges and payouts:
        return ConnectedAccount.Status.READY
    if details or requirements.get("currently_due"):
        return ConnectedAccount.Status.RESTRICTED
    return ConnectedAccount.Status.PENDING


def _sync_account(*, connected_account, data):
    requirements = data.get("requirements") or {}
    connected_account.details_submitted = bool(data.get("details_submitted"))
    connected_account.charges_enabled = bool(data.get("charges_enabled"))
    connected_account.payouts_enabled = bool(data.get("payouts_enabled"))
    connected_account.requirements_due = requirements.get("currently_due") or []
    connected_account.disabled_reason = requirements.get("disabled_reason") or ""
    connected_account.status = _status_from_account(data)
    connected_account.provider_synced_at = timezone.now()
    connected_account.full_clean()
    connected_account.save()
    return connected_account


def ensure_connected_account(*, actor, business_id):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    existing = ConnectedAccount.objects.filter(business=business).first()
    if existing:
        return existing
    data = create_express_account(
        business=business,
        idempotency_key=f"connect-account:{business.pk}",
    )
    try:
        with transaction.atomic():
            account = ConnectedAccount(
                business=business,
                provider_account_id=data["id"],
            )
            return _sync_account(connected_account=account, data=data)
    except Exception:
        existing = ConnectedAccount.objects.filter(business=business).first()
        if existing:
            return existing
        raise


def onboarding_url(*, actor, business_id, refresh_url, return_url):
    account = ensure_connected_account(actor=actor, business_id=business_id)
    return create_onboarding_link(
        provider_account_id=account.provider_account_id,
        refresh_url=refresh_url,
        return_url=return_url,
    )


def refresh_connected_account(*, actor, business_id):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    account = ConnectedAccount.objects.filter(business=business).first()
    if account is None:
        raise ValidationError("Connect an account first.")
    data = retrieve_account(provider_account_id=account.provider_account_id)
    with transaction.atomic():
        account = ConnectedAccount.objects.select_for_update().get(pk=account.pk)
        return _sync_account(connected_account=account, data=data)


def _active_attempt(invoice):
    now = timezone.now()
    InvoicePaymentAttempt.objects.filter(
        invoice=invoice,
        status__in=(
            InvoicePaymentAttempt.Status.PENDING,
            InvoicePaymentAttempt.Status.OPEN,
        ),
        expires_at__lte=now,
    ).update(status=InvoicePaymentAttempt.Status.EXPIRED)
    return (
        InvoicePaymentAttempt.objects.filter(
            invoice=invoice,
            status__in=(
                InvoicePaymentAttempt.Status.PENDING,
                InvoicePaymentAttempt.Status.OPEN,
                InvoicePaymentAttempt.Status.PROCESSING,
            ),
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )


@transaction.atomic
def _prepare_invoice_attempt(*, link):
    link = PublicDocumentLink.objects.select_for_update().get(pk=link.pk)
    if not link.is_active or link.purpose != PublicDocumentLink.Purpose.PAY:
        raise PermissionDenied("This payment link is no longer available.")
    invoice = (
        Invoice.objects.select_for_update()
        .select_related("business", "contact")
        .get(pk=link.invoice_id)
    )
    if invoice.status in {Invoice.Status.DRAFT, Invoice.Status.VOID}:
        raise ValidationError("This invoice cannot be paid online.")
    if invoice.balance_due <= 0:
        raise ValidationError("This invoice is already paid.")
    require_feature(business=invoice.business, feature=Feature.ONLINE_PAYMENTS)
    connected_account = ConnectedAccount.objects.filter(
        business=invoice.business, status=ConnectedAccount.Status.READY
    ).first()
    if connected_account is None:
        raise ValidationError("Online payments are not available for this business.")
    existing = _active_attempt(invoice)
    if existing:
        return existing, connected_account, False
    attempt = InvoicePaymentAttempt(
        business=invoice.business,
        invoice=invoice,
        public_link=link,
        amount=invoice.balance_due,
        currency=invoice.currency,
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    attempt.idempotency_key = f"invoice-checkout:{attempt.pk}"
    attempt.full_clean()
    attempt.save()
    return attempt, connected_account, True


def start_invoice_checkout(*, link, raw_token):
    attempt, connected_account, created = _prepare_invoice_attempt(link=link)
    if not created and attempt.checkout_url:
        return attempt
    success_url = f"{settings.SITE_URL}{reverse('payments:payment-return')}"
    cancel_url = (
        f"{settings.SITE_URL}"
        f"{reverse('payments:public-payment', kwargs={'token': raw_token})}"
    )
    try:
        result = create_invoice_checkout(
            attempt=attempt,
            connected_account=connected_account,
            customer_email=attempt.invoice.contact.email,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as exc:
        InvoicePaymentAttempt.objects.filter(pk=attempt.pk).update(
            status=InvoicePaymentAttempt.Status.FAILED,
            failure_code=exc.__class__.__name__[:80],
            failure_message=str(exc)[:500],
        )
        raise
    with transaction.atomic():
        attempt = InvoicePaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        attempt.status = InvoicePaymentAttempt.Status.OPEN
        attempt.provider_checkout_session_id = result.session_id
        attempt.checkout_url = result.url
        attempt.expires_at = result.expires_at
        attempt.save()
    return attempt


@transaction.atomic
def post_online_payment(*, attempt_id, provider_payment_id, paid_at=None):
    existing = Payment.objects.filter(provider_payment_id=provider_payment_id).first()
    if existing:
        return existing
    attempt = (
        InvoicePaymentAttempt.objects.select_for_update()
        .select_related("business__workspace__owner_user", "invoice__contact")
        .get(pk=attempt_id)
    )
    invoice = Invoice.objects.select_for_update().get(pk=attempt.invoice_id)
    if attempt.status == InvoicePaymentAttempt.Status.COMPLETED:
        return Payment.objects.get(provider_payment_id=provider_payment_id)
    if attempt.amount != invoice.balance_due:
        raise ValidationError(
            "The invoice balance changed while checkout was open; reconcile the provider payment manually."
        )
    paid_at = paid_at or timezone.now()
    paid_on = timezone.localtime(paid_at, ZoneInfo(attempt.business.timezone)).date()
    payment = Payment(
        business=attempt.business,
        invoice=invoice,
        source=Payment.Source.ONLINE,
        amount=attempt.amount,
        currency=attempt.currency,
        invoice_total_snapshot=invoice.total,
        balance_after_snapshot=invoice.balance_due - attempt.amount,
        paid_on=paid_on,
        method=Payment.Method.CREDIT_CARD,
        reference=provider_payment_id,
        note="Stripe Checkout payment",
        provider_payment_id=provider_payment_id,
        recorded_by=None,
    )
    payment.full_clean()
    payment.save()
    invoice.amount_paid += payment.amount
    invoice.balance_due -= payment.amount
    invoice.full_clean()
    invoice.save(update_fields=("amount_paid", "balance_due", "updated_at"))
    attempt.status = InvoicePaymentAttempt.Status.COMPLETED
    attempt.provider_payment_intent_id = provider_payment_id
    attempt.completed_at = paid_at
    attempt.save()
    PublicDocumentLink.objects.filter(
        invoice=invoice,
        purpose=PublicDocumentLink.Purpose.PAY,
        revoked_at__isnull=True,
    ).update(revoked_at=paid_at)
    record_activity(
        business=attempt.business,
        actor=None,
        event_type=ActivityEvent.EventType.PAYMENT_POSTED,
        summary=(
            f"Received online {invoice.currency} {payment.amount:.2f} payment on {invoice.number}."
        ),
        payment=payment,
        metadata={"provider": "stripe", "payment_attempt_id": str(attempt.pk)},
    )
    notify_business_owner(
        business=attempt.business,
        kind="payment_received",
        title=f"Online payment received for {invoice.number}",
        body=f"{invoice.currency} {payment.amount:.2f} was received online.",
        target_path=f"/app/invoices/{invoice.pk}/",
        dedupe_key=f"payment-received:{payment.pk}",
    )
    if invoice.contact.email:
        queue_payment_receipt(
            actor=attempt.business.workspace.owner_user,
            business_id=attempt.business_id,
            payment_id=payment.pk,
            recipient=invoice.contact.email,
        )
    return payment


def store_connect_webhook(*, payload):
    if bool(payload.get("livemode", False)) != settings.STRIPE_LIVE_MODE:
        raise ValueError("Stripe event mode does not match this environment.")
    event, created = ConnectWebhookEvent.objects.get_or_create(
        provider_event_id=payload["id"],
        defaults={
            "connected_account_id": payload.get("account", ""),
            "event_type": payload["type"],
            "livemode": bool(payload.get("livemode", False)),
            "payload": payload,
            "signature_verified_at": timezone.now(),
        },
    )
    return event, created


def _attempt_from_object(data):
    attempt_id = (data.get("metadata") or {}).get("payment_attempt_id")
    if attempt_id:
        return InvoicePaymentAttempt.objects.filter(pk=attempt_id).first()
    if data.get("object") == "checkout.session":
        return InvoicePaymentAttempt.objects.filter(
            provider_checkout_session_id=data.get("id")
        ).first()
    return InvoicePaymentAttempt.objects.filter(
        provider_payment_intent_id=data.get("id")
    ).first()


def _validate_event_account(*, event, attempt):
    account_id = (
        ConnectedAccount.objects.filter(business=attempt.business)
        .values_list("provider_account_id", flat=True)
        .first()
    )
    if not account_id or event.connected_account_id != account_id:
        raise ValidationError(
            "Connect webhook account does not match the payment attempt business."
        )


def process_connect_webhook(*, event_id):
    try:
        with transaction.atomic():
            event = ConnectWebhookEvent.objects.select_for_update().get(pk=event_id)
            if event.status in {
                ConnectWebhookEvent.Status.COMPLETED,
                ConnectWebhookEvent.Status.IGNORED,
            }:
                return event
            event.status = ConnectWebhookEvent.Status.PROCESSING
            event.attempts += 1
            event.last_error = ""
            event.save()
            data = event.payload["data"]["object"]
            handled = False
            if event.event_type == "account.updated":
                if event.connected_account_id != data.get("id"):
                    raise ValidationError(
                        "Connect webhook account does not match its account payload."
                    )
                account = ConnectedAccount.objects.select_for_update().filter(
                    provider_account_id=data.get("id")
                ).first()
                if account:
                    _sync_account(connected_account=account, data=data)
                    handled = True
            elif event.event_type in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
                "payment_intent.succeeded",
            }:
                attempt = _attempt_from_object(data)
                if attempt:
                    _validate_event_account(event=event, attempt=attempt)
                    payment_intent_id = (
                        data.get("payment_intent")
                        if data.get("object") == "checkout.session"
                        else data.get("id")
                    )
                    is_paid = data.get("object") != "checkout.session" or data.get(
                        "payment_status"
                    ) == "paid"
                    if payment_intent_id and is_paid:
                        post_online_payment(
                            attempt_id=attempt.pk,
                            provider_payment_id=payment_intent_id,
                        )
                        handled = True
            elif event.event_type in {
                "checkout.session.expired",
                "checkout.session.async_payment_failed",
                "payment_intent.payment_failed",
            }:
                attempt = _attempt_from_object(data)
                if attempt and attempt.status != InvoicePaymentAttempt.Status.COMPLETED:
                    _validate_event_account(event=event, attempt=attempt)
                    attempt.status = (
                        InvoicePaymentAttempt.Status.EXPIRED
                        if event.event_type == "checkout.session.expired"
                        else InvoicePaymentAttempt.Status.FAILED
                    )
                    attempt.failure_code = event.event_type
                    attempt.failure_message = "Stripe reported that payment did not complete."
                    attempt.save()
                    handled = True
            event.status = (
                ConnectWebhookEvent.Status.COMPLETED
                if handled
                else ConnectWebhookEvent.Status.IGNORED
            )
            event.processed_at = timezone.now()
            event.save()
            return event
    except Exception as exc:
        ConnectWebhookEvent.objects.filter(pk=event_id).update(
            status=ConnectWebhookEvent.Status.FAILED,
            last_error=str(exc)[:500],
        )
        raise

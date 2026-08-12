import logging
from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from estimates.models import Estimate
from invoices.models import Invoice
from payments.models import Payment
from workspaces.policies import owner_business_for_actor

from .links import create_public_link
from .models import EmailDelivery, OutboxEvent, PublicDocumentLink
from .pdf import (
    get_or_create_estimate_pdf,
    get_or_create_invoice_pdf,
    get_or_create_payment_receipt_pdf,
)

ESTIMATE_EMAIL_EVENT = "estimate.email"
INVOICE_EMAIL_EVENT = "invoice.email"
INVOICE_REMINDER_EVENT = "invoice.reminder"
PAYMENT_RECEIPT_EVENT = "payment.receipt"
logger = logging.getLogger(__name__)


def _schedule(event):
    transaction.on_commit(partial(process_outbox_event, event.pk), robust=True)


@transaction.atomic
def queue_estimate_email(*, actor, business_id, estimate_id, recipient):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    estimate = (
        Estimate.objects.select_for_update()
        .for_business(business)
        .filter(pk=estimate_id)
        .first()
    )
    if estimate is None:
        raise ValidationError("Estimate not found.")
    if estimate.status == Estimate.Status.DRAFT:
        raise ValidationError("Issue the estimate before sending it.")
    if estimate.status in (Estimate.Status.DECLINED, Estimate.Status.CONVERTED):
        raise ValidationError("This estimate cannot be emailed in its current state.")
    delivery = EmailDelivery.objects.create(
        business=business,
        estimate=estimate,
        kind=EmailDelivery.Kind.ESTIMATE,
        recipient=recipient,
        subject=f"Estimate {estimate.number} from {business.display_name}",
    )
    event = OutboxEvent.objects.create(
        business=business,
        event_type=ESTIMATE_EMAIL_EVENT,
        dedupe_key=f"estimate-email:{delivery.pk}",
        payload={"delivery_id": str(delivery.pk)},
    )
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_EMAIL_QUEUED,
        summary=f"Queued estimate {estimate.number} for {recipient}.",
        estimate=estimate,
    )
    _schedule(event)
    return delivery


@transaction.atomic
def queue_invoice_email(*, actor, business_id, invoice_id, recipient, reminder=False):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    invoice = (
        Invoice.objects.select_for_update()
        .for_business(business)
        .filter(pk=invoice_id)
        .first()
    )
    if invoice is None:
        raise ValidationError("Invoice not found.")
    if invoice.status == Invoice.Status.DRAFT:
        raise ValidationError("Issue the invoice before sending it.")
    if invoice.status == Invoice.Status.VOID:
        raise ValidationError("Void invoices cannot be emailed.")
    if reminder and invoice.balance_due <= 0:
        raise ValidationError("Paid invoices do not need a reminder.")
    kind = EmailDelivery.Kind.REMINDER if reminder else EmailDelivery.Kind.INVOICE
    event_type = INVOICE_REMINDER_EVENT if reminder else INVOICE_EMAIL_EVENT
    subject_prefix = "Reminder: " if reminder else ""
    delivery = EmailDelivery.objects.create(
        business=business,
        invoice=invoice,
        kind=kind,
        recipient=recipient,
        subject=(
            f"{subject_prefix}Invoice {invoice.number} from {business.display_name}"
        ),
    )
    event = OutboxEvent.objects.create(
        business=business,
        event_type=event_type,
        dedupe_key=f"{event_type}:{delivery.pk}",
        payload={"delivery_id": str(delivery.pk)},
    )
    record_activity(
        business=business,
        actor=actor,
        event_type=(
            ActivityEvent.EventType.INVOICE_REMINDER_QUEUED
            if reminder
            else ActivityEvent.EventType.INVOICE_EMAIL_QUEUED
        ),
        summary=(
            f"Queued {'a reminder for' if reminder else 'invoice'} "
            f"{invoice.number} to {recipient}."
        ),
        invoice=invoice,
    )
    _schedule(event)
    return delivery


@transaction.atomic
def queue_payment_receipt(*, actor, business_id, payment_id, recipient):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    payment = (
        Payment.objects.select_for_update()
        .filter(pk=payment_id, business=business)
        .select_related("invoice")
        .first()
    )
    if payment is None:
        raise ValidationError("Payment not found.")
    delivery = EmailDelivery.objects.create(
        business=business,
        payment=payment,
        kind=EmailDelivery.Kind.RECEIPT,
        recipient=recipient,
        subject=f"Receipt for invoice {payment.invoice.number}",
    )
    event = OutboxEvent.objects.create(
        business=business,
        event_type=PAYMENT_RECEIPT_EVENT,
        dedupe_key=f"payment-receipt:{delivery.pk}",
        payload={"delivery_id": str(delivery.pk)},
    )
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.PAYMENT_RECEIPT_QUEUED,
        summary=f"Queued a receipt for payment on {payment.invoice.number}.",
        payment=payment,
    )
    _schedule(event)
    return delivery


def _estimate_message(delivery):
    estimate = delivery.estimate
    asset = get_or_create_estimate_pdf(estimate=estimate)
    _, view_token = create_public_link(
        estimate=estimate, purpose=PublicDocumentLink.Purpose.VIEW
    )
    _, response_token = create_public_link(
        estimate=estimate, purpose=PublicDocumentLink.Purpose.RESPOND
    )
    view_url = (
        f"{settings.SITE_URL}"
        f"{reverse('estimates:public-view', kwargs={'token': view_token})}"
    )
    response_url = (
        f"{settings.SITE_URL}"
        f"{reverse('estimates:public-respond', kwargs={'token': response_token})}"
    )
    return (
        EmailMessage(
            subject=delivery.subject,
            body=(
                f"{estimate.business.display_name} sent estimate {estimate.number}.\n\n"
                f"View estimate: {view_url}\n\n"
                f"Accept or decline: {response_url}\n\n"
                "The response link is private. Do not forward it."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[delivery.recipient],
        ),
        asset,
        f"Estimate-{estimate.number}.pdf",
    )


def _invoice_message(delivery):
    invoice = delivery.invoice
    asset = get_or_create_invoice_pdf(invoice=invoice)
    _, token = create_public_link(
        invoice=invoice, purpose=PublicDocumentLink.Purpose.VIEW
    )
    view_url = (
        f"{settings.SITE_URL}{reverse('invoices:public-view', kwargs={'token': token})}"
    )
    if delivery.kind == EmailDelivery.Kind.REMINDER:
        opening = (
            f"This is a reminder that invoice {invoice.number} has a balance of "
            f"{invoice.currency} {invoice.balance_due:.2f}, due {invoice.due_date}."
        )
    else:
        opening = f"{invoice.business.display_name} sent invoice {invoice.number}."
    return (
        EmailMessage(
            subject=delivery.subject,
            body=(
                f"{opening}\n\nView invoice: {view_url}\n\n"
                "The invoice link is private. Do not forward it."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[delivery.recipient],
        ),
        asset,
        f"Invoice-{invoice.number}.pdf",
    )


def _receipt_message(delivery):
    payment = delivery.payment
    invoice = payment.invoice
    asset = get_or_create_payment_receipt_pdf(payment=payment)
    _, token = create_public_link(
        invoice=invoice, purpose=PublicDocumentLink.Purpose.VIEW
    )
    view_url = (
        f"{settings.SITE_URL}{reverse('invoices:public-view', kwargs={'token': token})}"
    )
    return (
        EmailMessage(
            subject=delivery.subject,
            body=(
                f"We recorded your {payment.currency} {payment.amount:.2f} payment "
                f"for invoice {invoice.number}.\n\n"
                f"Balance after payment: {payment.currency} "
                f"{payment.balance_after_snapshot:.2f}\n\n"
                f"View invoice: {view_url}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[delivery.recipient],
        ),
        asset,
        f"Receipt-{invoice.number}-{payment.pk}.pdf",
    )


def _mark_failed(*, event_id, delivery_id, error):
    safe_message = str(error).replace("\n", " ")[:500]
    with transaction.atomic():
        OutboxEvent.objects.filter(pk=event_id).update(
            status=OutboxEvent.Status.FAILED, last_error=safe_message
        )
        EmailDelivery.objects.filter(pk=delivery_id).update(
            status=EmailDelivery.Status.FAILED,
            failure_code=error.__class__.__name__[:80],
            failure_message=safe_message,
        )
    delivery = EmailDelivery.objects.select_related("business").get(pk=delivery_id)
    try:
        from .models import Notification
        from .notifications import notify_business_owner

        notify_business_owner(
            business=delivery.business,
            kind=Notification.Kind.DELIVERY_FAILED,
            title=f"Email delivery failed: {delivery.subject}",
            body=safe_message or "The email provider did not confirm delivery.",
            target_path="/app/communications/",
            dedupe_key=f"delivery-failed:{delivery.pk}",
        )
    except Exception:
        logger.exception(
            "Unable to create delivery-failure notification for delivery %s.",
            delivery_id,
        )


def process_outbox_event(event_id):
    with transaction.atomic():
        event = OutboxEvent.objects.select_for_update().filter(pk=event_id).first()
        if event is None or event.status not in (
            OutboxEvent.Status.PENDING,
            OutboxEvent.Status.FAILED,
        ):
            return
        event.status = OutboxEvent.Status.PROCESSING
        event.attempts += 1
        event.last_error = ""
        event.save(update_fields=("status", "attempts", "last_error", "updated_at"))
        delivery_id = event.payload["delivery_id"]
        event_type = event.event_type
    try:
        delivery = EmailDelivery.objects.select_related(
            "estimate",
            "estimate__business",
            "estimate__document_snapshot",
            "invoice",
            "invoice__business",
            "invoice__document_snapshot",
            "payment",
            "payment__invoice",
            "payment__invoice__document_snapshot",
        ).get(pk=delivery_id)
        if event_type == ESTIMATE_EMAIL_EVENT:
            message, asset, filename = _estimate_message(delivery)
        elif event_type in (INVOICE_EMAIL_EVENT, INVOICE_REMINDER_EVENT):
            message, asset, filename = _invoice_message(delivery)
        elif event_type == PAYMENT_RECEIPT_EVENT:
            message, asset, filename = _receipt_message(delivery)
        else:
            raise RuntimeError("Unsupported outbox event type.")
        with default_storage.open(asset.storage_name, "rb") as pdf_file:
            message.attach(filename, pdf_file.read(), "application/pdf")
        if message.send(fail_silently=False) != 1:
            raise RuntimeError("The email backend did not confirm delivery.")
    except Exception as exc:
        _mark_failed(event_id=event_id, delivery_id=delivery_id, error=exc)
        return
    now = timezone.now()
    with transaction.atomic():
        EmailDelivery.objects.filter(pk=delivery_id).update(
            status=EmailDelivery.Status.SENT,
            sent_at=now,
            failure_code="",
            failure_message="",
        )
        OutboxEvent.objects.filter(pk=event_id).update(
            status=OutboxEvent.Status.COMPLETED,
            processed_at=now,
            last_error="",
        )

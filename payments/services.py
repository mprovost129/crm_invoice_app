from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from communications.models import Notification
from communications.notifications import notify_business_owner
from estimates.calculations import quantize_money
from invoices.models import Invoice
from workspaces.policies import owner_business_for_actor

from .models import Payment, PaymentReversal


@transaction.atomic
def post_manual_payment(
    *,
    actor,
    business_id,
    invoice_id,
    amount,
    paid_on,
    method,
    reference="",
    note="",
    send_receipt=False,
    receipt_email="",
):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    invoice = (
        Invoice.objects.select_for_update()
        .for_business(business)
        .select_related("contact", "business")
        .filter(pk=invoice_id)
        .first()
    )
    if invoice is None:
        raise PermissionDenied("Invoice access is required.")
    if invoice.status == Invoice.Status.DRAFT:
        raise ValidationError("Issue the invoice before recording payment.")
    if invoice.status == Invoice.Status.VOID:
        raise ValidationError("Void invoices cannot receive payments.")
    from .models import InvoicePaymentAttempt

    now = timezone.now()
    InvoicePaymentAttempt.objects.filter(
        invoice=invoice,
        status__in=(
            InvoicePaymentAttempt.Status.PENDING,
            InvoicePaymentAttempt.Status.OPEN,
        ),
        expires_at__lte=now,
    ).update(status=InvoicePaymentAttempt.Status.EXPIRED)
    if InvoicePaymentAttempt.objects.filter(
        invoice=invoice,
        status__in=(
            InvoicePaymentAttempt.Status.PENDING,
            InvoicePaymentAttempt.Status.OPEN,
            InvoicePaymentAttempt.Status.PROCESSING,
        ),
        expires_at__gt=now,
    ).exists():
        raise ValidationError(
            "An online checkout is active for this invoice. Wait for it to finish or expire before recording a manual payment."
        )
    amount = quantize_money(amount)
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")
    if amount > invoice.balance_due:
        raise ValidationError("Payment cannot exceed the current balance due.")
    business_today = timezone.localdate(timezone=ZoneInfo(business.timezone))
    if paid_on > business_today:
        raise ValidationError("Payment date cannot be in the future.")
    payment = Payment(
        business=business,
        invoice=invoice,
        source=Payment.Source.MANUAL,
        amount=amount,
        currency=invoice.currency,
        invoice_total_snapshot=invoice.total,
        balance_after_snapshot=invoice.balance_due - amount,
        paid_on=paid_on,
        method=method,
        reference=reference.strip(),
        note=note.strip(),
        recorded_by=actor,
    )
    payment.full_clean()
    payment.save()
    invoice.amount_paid += amount
    invoice.balance_due -= amount
    invoice.full_clean()
    invoice.save(update_fields=("amount_paid", "balance_due", "updated_at"))
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.PAYMENT_POSTED,
        summary=(
            f"Recorded {invoice.currency} {amount:.2f} payment on {invoice.number}."
        ),
        payment=payment,
        metadata={"invoice_id": str(invoice.pk), "invoice_number": invoice.number},
    )
    notify_business_owner(
        business=business,
        kind=Notification.Kind.PAYMENT_RECEIVED,
        title=f"Payment recorded for {invoice.number}",
        body=f"{invoice.currency} {amount:.2f} was recorded. Balance: {invoice.currency} {invoice.balance_due:.2f}.",
        target_path=f"/app/invoices/{invoice.pk}/",
        dedupe_key=f"payment-received:{payment.pk}",
    )
    if send_receipt:
        recipient = receipt_email.strip() or invoice.contact.email
        if not recipient:
            raise ValidationError("Enter an email address to send a receipt.")
        from communications.emailing import queue_payment_receipt

        queue_payment_receipt(
            actor=actor,
            business_id=business.pk,
            payment_id=payment.pk,
            recipient=recipient,
        )
    return payment


@transaction.atomic
def reverse_payment(*, actor, business_id, payment_id, amount, reason):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    payment = (
        Payment.objects.select_for_update()
        .filter(pk=payment_id, business=business)
        .first()
    )
    if payment is None:
        raise PermissionDenied("Payment access is required.")
    invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)
    reversed_total = PaymentReversal.objects.filter(payment=payment).aggregate(
        Sum("amount")
    )["amount__sum"] or Decimal("0")
    amount = quantize_money(amount)
    unreversed = payment.amount - reversed_total
    if amount <= 0:
        raise ValidationError("Reversal amount must be greater than zero.")
    if amount > unreversed:
        raise ValidationError("Reversal cannot exceed the unreversed payment amount.")
    reversal = PaymentReversal(
        business=business,
        payment=payment,
        amount=amount,
        reason=reason.strip(),
        recorded_by=actor,
    )
    reversal.full_clean()
    reversal.save()
    invoice.amount_paid -= amount
    invoice.balance_due += amount
    invoice.full_clean()
    invoice.save(update_fields=("amount_paid", "balance_due", "updated_at"))
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.PAYMENT_REVERSED,
        summary=(
            f"Reversed {invoice.currency} {amount:.2f} payment on {invoice.number}."
        ),
        payment=payment,
        metadata={"reversal_id": str(reversal.pk), "reason": reversal.reason},
    )
    return reversal


def expected_invoice_paid_total(invoice):
    posted = Payment.objects.filter(invoice=invoice).aggregate(Sum("amount"))[
        "amount__sum"
    ] or Decimal("0")
    reversed_total = PaymentReversal.objects.filter(payment__invoice=invoice).aggregate(
        Sum("amount")
    )["amount__sum"] or Decimal("0")
    return quantize_money(posted - reversed_total)

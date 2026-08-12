from calendar import monthrange
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Q, Sum
from django.utils import timezone

from activity.models import ActivityEvent
from communications.models import EmailDelivery, Notification, OutboxEvent
from estimates.models import Estimate
from invoices.models import Invoice
from payments.models import Payment, PaymentReversal


def _zero(value):
    return value or Decimal("0")


def _aware_boundary(day, business):
    return timezone.make_aware(
        datetime.combine(day, time.min), ZoneInfo(business.timezone)
    )


def net_collected(*, business, start, end):
    posted = _zero(
        Payment.objects.filter(
            business=business,
            paid_on__gte=start,
            paid_on__lte=end,
        ).aggregate(total=Sum("amount"))["total"]
    )
    start_at = _aware_boundary(start, business)
    end_at = _aware_boundary(end + timedelta(days=1), business)
    reversed_total = _zero(
        PaymentReversal.objects.filter(
            business=business,
            reversed_at__gte=start_at,
            reversed_at__lt=end_at,
        ).aggregate(total=Sum("amount"))["total"]
    )
    return posted - reversed_total


def open_estimates(*, business, today):
    return Estimate.objects.for_business(business).filter(
        Q(status=Estimate.Status.DRAFT)
        | Q(status=Estimate.Status.ACCEPTED)
        | Q(
            status__in=(Estimate.Status.SENT, Estimate.Status.VIEWED),
            expiration_date__isnull=True,
        )
        | Q(
            status__in=(Estimate.Status.SENT, Estimate.Status.VIEWED),
            expiration_date__gte=today,
        )
    )


def dashboard_summary(*, business, today=None):
    today = today or timezone.localdate(timezone=ZoneInfo(business.timezone))
    month_start = today.replace(day=1)
    month_end = today.replace(day=monthrange(today.year, today.month)[1])
    issued = Invoice.objects.for_business(business).exclude(
        status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID)
    )
    outstanding = issued.filter(balance_due__gt=0)
    overdue = outstanding.filter(due_date__lt=today)
    return {
        "currency": business.default_currency,
        "paid_this_month": net_collected(
            business=business, start=month_start, end=min(today, month_end)
        ),
        "outstanding_total": _zero(
            outstanding.aggregate(total=Sum("balance_due"))["total"]
        ),
        "outstanding_count": outstanding.count(),
        "overdue_total": _zero(overdue.aggregate(total=Sum("balance_due"))["total"]),
        "overdue_count": overdue.count(),
        "open_estimate_total": _zero(
            open_estimates(business=business, today=today).aggregate(
                total=Sum("total")
            )["total"]
        ),
        "open_estimate_count": open_estimates(business=business, today=today).count(),
    }


def communication_alerts(*, business, now=None, stale_minutes=15):
    now = now or timezone.now()
    stale_before = now - timedelta(minutes=stale_minutes)
    failed_deliveries = EmailDelivery.objects.filter(
        business=business, status=EmailDelivery.Status.FAILED
    )
    stuck_outbox = OutboxEvent.objects.filter(business=business).filter(
        Q(status=OutboxEvent.Status.FAILED)
        | Q(status=OutboxEvent.Status.PROCESSING, updated_at__lt=stale_before)
        | Q(status=OutboxEvent.Status.PENDING, available_at__lt=stale_before)
    )
    return {
        "failed_delivery_count": failed_deliveries.count(),
        "stuck_outbox_count": stuck_outbox.count(),
        "failed_deliveries": failed_deliveries.select_related(
            "estimate", "invoice", "payment__invoice"
        )[:10],
        "stuck_outbox": stuck_outbox.order_by("available_at")[:10],
    }


def needs_attention(*, business, today=None, limit=12):
    today = today or timezone.localdate(timezone=ZoneInfo(business.timezone))
    items = []
    overdue = (
        Invoice.objects.for_business(business)
        .filter(
            balance_due__gt=0,
            due_date__lt=today,
        )
        .exclude(status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID))
        .select_related("contact")
        .order_by("due_date")[:limit]
    )
    for invoice in overdue:
        items.append(
            {
                "priority": 10,
                "kind": "Overdue invoice",
                "title": invoice.number,
                "detail": (
                    f"{invoice.contact.display_name} owes {invoice.currency} "
                    f"{invoice.balance_due:.2f}; due {invoice.due_date}."
                ),
                "url_name": "invoices:detail",
                "object_id": invoice.pk,
                "sort_at": invoice.due_date,
            }
        )
    accepted = (
        Estimate.objects.for_business(business)
        .filter(status=Estimate.Status.ACCEPTED, invoice__isnull=True)
        .select_related("contact")
        .order_by("accepted_at")[:limit]
    )
    for estimate in accepted:
        items.append(
            {
                "priority": 20,
                "kind": "Ready to invoice",
                "title": estimate.number,
                "detail": f"Accepted by {estimate.contact.display_name}; convert when ready.",
                "url_name": "estimates:detail",
                "object_id": estimate.pk,
                "sort_at": estimate.accepted_at.date()
                if estimate.accepted_at
                else today,
            }
        )
    alerts = communication_alerts(business=business)
    if alerts["failed_delivery_count"]:
        items.append(
            {
                "priority": 5,
                "kind": "Delivery failure",
                "title": f"{alerts['failed_delivery_count']} email delivery failure(s)",
                "detail": "Review the delivery error and retry after correcting configuration.",
                "url_name": "dashboards:communications",
                "object_id": None,
                "sort_at": today,
            }
        )
    if alerts["stuck_outbox_count"]:
        items.append(
            {
                "priority": 1,
                "kind": "Outbox alert",
                "title": f"{alerts['stuck_outbox_count']} stuck or failed job(s)",
                "detail": "The communication worker needs operator attention.",
                "url_name": "dashboards:communications",
                "object_id": None,
                "sort_at": today,
            }
        )
    return sorted(items, key=lambda item: (item["priority"], item["sort_at"]))[:limit]


def recent_activity(*, business, limit=12):
    return ActivityEvent.objects.for_business(business).select_related(
        "actor", "contact", "product_service", "estimate", "invoice", "payment__invoice"
    )[:limit]


def unread_notifications(*, business, recipient, limit=10):
    return Notification.objects.filter(
        business=business, recipient=recipient, read_at__isnull=True
    )[:limit]


def report_summary(*, business, start, end, today=None):
    today = today or timezone.localdate(timezone=ZoneInfo(business.timezone))
    issued_invoices = (
        Invoice.objects.for_business(business)
        .filter(
            issue_date__gte=start,
            issue_date__lte=end,
        )
        .exclude(status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID))
    )
    estimates = (
        Estimate.objects.for_business(business)
        .filter(
            issue_date__gte=start,
            issue_date__lte=end,
        )
        .exclude(status=Estimate.Status.DRAFT)
    )
    won_count = estimates.filter(
        status__in=(Estimate.Status.ACCEPTED, Estimate.Status.CONVERTED)
    ).count()
    issued_estimate_count = estimates.count()

    receivables = (
        Invoice.objects.for_business(business)
        .filter(balance_due__gt=0)
        .exclude(status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID))
    )
    aging = {
        "current": Decimal("0"),
        "days_1_30": Decimal("0"),
        "days_31_60": Decimal("0"),
        "days_61_90": Decimal("0"),
        "days_91_plus": Decimal("0"),
    }
    for invoice in receivables.only("due_date", "balance_due"):
        days = (today - invoice.due_date).days
        if days <= 0:
            bucket = "current"
        elif days <= 30:
            bucket = "days_1_30"
        elif days <= 60:
            bucket = "days_31_60"
        elif days <= 90:
            bucket = "days_61_90"
        else:
            bucket = "days_91_plus"
        aging[bucket] += invoice.balance_due
    return {
        "currency": business.default_currency,
        "net_collected": net_collected(business=business, start=start, end=end),
        "invoiced": _zero(issued_invoices.aggregate(total=Sum("total"))["total"]),
        "invoice_count": issued_invoices.count(),
        "receivables": _zero(receivables.aggregate(total=Sum("balance_due"))["total"]),
        "aging": aging,
        "estimate_count": issued_estimate_count,
        "estimate_value": _zero(estimates.aggregate(total=Sum("total"))["total"]),
        "won_estimate_count": won_count,
        "acceptance_rate": (
            Decimal(won_count * 100) / Decimal(issued_estimate_count)
            if issued_estimate_count
            else Decimal("0")
        ).quantize(Decimal("0.1")),
        "top_overdue": receivables.filter(due_date__lt=today)
        .select_related("contact")
        .order_by("due_date")[:10],
    }

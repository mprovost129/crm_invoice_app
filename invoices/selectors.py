from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from .models import Invoice


def invoices_for_business(*, business, search="", status=""):
    invoices = Invoice.objects.for_business(business).select_related(
        "business", "contact"
    )
    if search:
        invoices = invoices.filter(
            Q(number__icontains=search)
            | Q(contact__first_name__icontains=search)
            | Q(contact__last_name__icontains=search)
            | Q(contact__company_name__icontains=search)
            | Q(contact__email__icontains=search)
            | Q(contact__phone__icontains=search)
        )
    today = timezone.localdate(timezone=ZoneInfo(business.timezone))
    if status == "paid":
        return invoices.exclude(
            status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID)
        ).filter(balance_due=0)
    if status == "overdue":
        return invoices.exclude(
            status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID)
        ).filter(balance_due__gt=0, due_date__lt=today)
    if status == "partial":
        return invoices.exclude(
            status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID)
        ).filter(amount_paid__gt=0, balance_due__gt=0, due_date__gte=today)
    if status in Invoice.Status.values:
        invoices = invoices.filter(status=status)
    return invoices


def invoice_for_business(*, business, invoice_id):
    return (
        Invoice.objects.for_business(business)
        .select_related("business", "contact", "source_estimate")
        .prefetch_related("line_items", "payments__reversals")
        .filter(pk=invoice_id)
        .first()
    )

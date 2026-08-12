from django.db.models import Q

from .models import Invoice


def invoices_for_business(*, business, search="", status=""):
    invoices = Invoice.objects.for_business(business).select_related("contact")
    if search:
        invoices = invoices.filter(
            Q(number__icontains=search)
            | Q(contact__first_name__icontains=search)
            | Q(contact__last_name__icontains=search)
            | Q(contact__company_name__icontains=search)
        )
    if status in ("partial", "paid", "overdue"):
        return [invoice for invoice in invoices if invoice.effective_status == status]
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

import csv
from collections import defaultdict
from decimal import Decimal
from io import StringIO

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone

from crm.models import Contact
from estimates.models import Estimate
from invoices.models import Invoice
from payments.models import Payment, PaymentReversal


def _safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "@", "\t", "\r")) or (
        text.startswith("-") and (len(text) == 1 or not text[1].isdigit())
    ):
        return f"'{text}"
    return text


def _money(value):
    return f"{Decimal(value or 0):.2f}"


def _csv_response(*, filename, headers, rows):
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_safe(value) for value in row])
    response = HttpResponse(
        stream.getvalue().encode("utf-8-sig"), content_type="text/csv; charset=utf-8"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def contacts_csv(*, business, clients_only=False, filename_label="contacts"):
    estimate_counts = dict(
        Estimate.objects.for_business(business)
        .values("contact_id")
        .annotate(total=Count("id"))
        .values_list("contact_id", "total")
    )
    invoice_counts = dict(
        Invoice.objects.for_business(business)
        .values("contact_id")
        .annotate(total=Count("id"))
        .values_list("contact_id", "total")
    )
    outstanding = dict(
        Invoice.objects.for_business(business)
        .exclude(status=Invoice.Status.VOID)
        .values("contact_id")
        .annotate(total=Sum("balance_due"))
        .values_list("contact_id", "total")
    )
    posted = defaultdict(Decimal)
    for contact_id, total in (
        Payment.objects.filter(business=business)
        .values("invoice__contact_id")
        .annotate(total=Sum("amount"))
        .values_list("invoice__contact_id", "total")
    ):
        posted[contact_id] += total
    for contact_id, total in (
        PaymentReversal.objects.filter(business=business)
        .values("payment__invoice__contact_id")
        .annotate(total=Sum("amount"))
        .values_list("payment__invoice__contact_id", "total")
    ):
        posted[contact_id] -= total
    contacts = Contact.objects.for_business(business).order_by(
        "last_name", "first_name", "company_name", "pk"
    )
    if clients_only:
        contacts = contacts.filter(
            Q(status=Contact.Status.CLIENT)
            | Q(
                status=Contact.Status.ARCHIVED,
                status_before_archive=Contact.Status.CLIENT,
            )
        )
    rows = (
        (
            contact.pk,
            contact.status,
            contact.first_name,
            contact.last_name,
            contact.company_name,
            contact.email,
            contact.phone,
            contact.address_line_1,
            contact.address_line_2,
            contact.city,
            contact.region,
            contact.postal_code,
            contact.country_code,
            estimate_counts.get(contact.pk, 0),
            invoice_counts.get(contact.pk, 0),
            business.default_currency,
            _money(posted[contact.pk]),
            _money(outstanding.get(contact.pk)),
            contact.created_at.isoformat(),
        )
        for contact in contacts
    )
    return _csv_response(
        filename=f"{filename_label}-{timezone.localdate().isoformat()}.csv",
        headers=(
            "contact_id",
            "status",
            "first_name",
            "last_name",
            "company_name",
            "email",
            "phone",
            "address_line_1",
            "address_line_2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "estimate_count",
            "invoice_count",
            "currency",
            "net_paid",
            "outstanding",
            "created_at",
        ),
        rows=rows,
    )


def clients_csv(*, business):
    return contacts_csv(
        business=business,
        clients_only=True,
        filename_label="clients",
    )


def invoices_csv(*, business):
    invoices = (
        Invoice.objects.for_business(business)
        .select_related("business", "contact", "source_estimate")
        .order_by("issue_date", "created_at", "pk")
    )
    rows = (
        (
            invoice.pk,
            invoice.number,
            invoice.effective_status,
            invoice.contact.pk,
            invoice.contact.display_name,
            invoice.contact.company_name,
            invoice.contact.email,
            invoice.issue_date,
            invoice.due_date,
            invoice.currency,
            _money(invoice.subtotal),
            _money(invoice.discount_amount),
            _money(invoice.tax_amount),
            _money(invoice.total),
            _money(invoice.amount_paid),
            _money(invoice.balance_due),
            invoice.source_estimate.number if invoice.source_estimate else "",
            invoice.created_at.isoformat(),
        )
        for invoice in invoices
    )
    return _csv_response(
        filename=f"invoices-{timezone.localdate().isoformat()}.csv",
        headers=(
            "invoice_id",
            "invoice_number",
            "status",
            "contact_id",
            "client",
            "company",
            "email",
            "issue_date",
            "due_date",
            "currency",
            "subtotal",
            "discount",
            "tax",
            "total",
            "amount_paid",
            "balance_due",
            "source_estimate",
            "created_at",
        ),
        rows=rows,
    )


def payments_csv(*, business):
    payments = (
        Payment.objects.filter(business=business)
        .select_related("invoice", "invoice__contact")
        .prefetch_related("reversals")
        .order_by("paid_on", "posted_at", "pk")
    )
    rows = (
        (
            payment.pk,
            payment.invoice.number,
            payment.invoice.contact.display_name,
            payment.paid_on,
            payment.source,
            payment.method,
            payment.reference,
            payment.currency,
            _money(payment.amount),
            _money(payment.reversed_amount),
            _money(payment.net_amount),
            _money(payment.invoice_total_snapshot),
            _money(payment.balance_after_snapshot),
            payment.effective_status,
            payment.posted_at.isoformat(),
        )
        for payment in payments
    )
    return _csv_response(
        filename=f"payments-{timezone.localdate().isoformat()}.csv",
        headers=(
            "payment_id",
            "invoice_number",
            "client",
            "paid_on",
            "source",
            "method",
            "reference",
            "currency",
            "gross_amount",
            "reversed_amount",
            "net_amount",
            "invoice_total_snapshot",
            "balance_after_snapshot",
            "status",
            "posted_at",
        ),
        rows=rows,
    )

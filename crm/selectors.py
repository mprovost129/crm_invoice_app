from decimal import Decimal

from django.db.models import Q, Sum

from activity.models import ActivityEvent

from .models import Contact, ContactNote


def contacts_for_business(*, business, search="", status=""):
    contacts = Contact.objects.for_business(business)
    if status in Contact.Status.values:
        contacts = contacts.filter(status=status)
    if search:
        contacts = contacts.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(company_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone__icontains=search)
        )
    return contacts


def contact_for_business(*, business, contact_id):
    return Contact.objects.for_business(business).filter(pk=contact_id).first()


def contact_notes(*, business, contact):
    return ContactNote.objects.for_business(business).filter(contact=contact)


def contact_activity(*, business, contact):
    return ActivityEvent.objects.for_business(business).filter(
        Q(contact=contact)
        | Q(estimate__contact=contact)
        | Q(invoice__contact=contact)
        | Q(payment__invoice__contact=contact)
    )


def contact_financial_summary(*, business, contact):
    from estimates.models import Estimate
    from invoices.models import Invoice
    from payments.models import Payment, PaymentReversal

    invoices = Invoice.objects.for_business(business).filter(contact=contact)
    posted = Payment.objects.filter(
        business=business, invoice__contact=contact
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    reversed_total = PaymentReversal.objects.filter(
        business=business,
        payment__invoice__contact=contact,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return {
        "estimates": Estimate.objects.for_business(business)
        .filter(contact=contact)
        .count(),
        "invoices": invoices.count(),
        "payments": Payment.objects.filter(
            business=business, invoice__contact=contact
        ).count(),
        "paid": posted - reversed_total,
        "outstanding": invoices.exclude(status=Invoice.Status.VOID).aggregate(
            total=Sum("balance_due")
        )["total"]
        or Decimal("0"),
        "recent_invoices": invoices.exclude(status=Invoice.Status.DRAFT)[:5],
    }

from decimal import Decimal

from crm.services import create_contact
from crm.tests.helpers import CONTACT_DATA
from estimates.models import EstimateAcceptance
from estimates.services import record_manual_acceptance
from estimates.tests.helpers import create_issued_estimate
from invoices.models import Invoice
from invoices.services import (
    add_invoice_line,
    convert_estimate_to_invoice,
    create_invoice,
    issue_invoice,
)

INVOICE_DATA = {
    "due_date": None,
    "discount_type": Invoice.AmountType.NONE,
    "discount_value": Decimal("0"),
    "deposit_required": Decimal("0"),
    "notes": "Thank you for your business.",
    "terms": "Payment is due by the stated due date.",
}

LINE_DATA = {
    "source_catalog_item_id": None,
    "name": "Design consultation",
    "description": "On-site consultation and design recommendations.",
    "unit": "hour",
    "quantity": Decimal("2"),
    "unit_rate": Decimal("125"),
    "is_taxable": True,
    "tax_rate": Decimal("6.25"),
}


def create_direct_invoice(*, user, business, issue=True, invoice_data=None):
    contact = create_contact(actor=user, business_id=business.pk, data=CONTACT_DATA)
    invoice = create_invoice(
        actor=user,
        business_id=business.pk,
        data={
            **INVOICE_DATA,
            "contact_id": contact.pk,
            **(invoice_data or {}),
        },
    )
    line = add_invoice_line(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        data=LINE_DATA,
    )
    invoice.refresh_from_db()
    if issue:
        invoice = issue_invoice(
            actor=user,
            business_id=business.pk,
            invoice_id=invoice.pk,
        )
    return invoice, line, contact


def create_converted_invoice(*, user, business, estimate_data=None):
    estimate, _, contact = create_issued_estimate(
        user=user,
        business=business,
        estimate_data=estimate_data,
    )
    if estimate.requires_acceptance:
        record_manual_acceptance(
            actor=user,
            business_id=business.pk,
            estimate_id=estimate.pk,
            method=EstimateAcceptance.Method.PHONE,
            accepted_by_name=contact.display_name,
        )
    invoice = convert_estimate_to_invoice(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
    )
    return invoice, estimate, contact

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from invoices.models import Invoice
from invoices.services import issue_invoice, update_invoice
from workspaces.tests.helpers import create_business, create_owner_tenancy

from .helpers import INVOICE_DATA, create_direct_invoice


@pytest.mark.django_db
def test_direct_invoice_draft_recalculates_and_issues_immutable_snapshot():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, line, contact = create_direct_invoice(
        user=user, business=business, issue=False
    )

    assert invoice.status == Invoice.Status.DRAFT
    assert line.line_subtotal == Decimal("250.00")
    assert invoice.total == Decimal("265.63")
    invoice = issue_invoice(actor=user, business_id=business.pk, invoice_id=invoice.pk)
    assert invoice.number == "INV-1001"
    assert invoice.document_snapshot.payload["invoice"]["total"] == "265.63"
    contact.refresh_from_db()
    assert contact.status == contact.Status.CLIENT
    with pytest.raises(ValidationError, match="immutable"):
        update_invoice(
            actor=user,
            business_id=business.pk,
            invoice_id=invoice.pk,
            data={**INVOICE_DATA, "contact_id": contact.pk},
        )


@pytest.mark.django_db
def test_overdue_takes_precedence_over_partial_status():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_direct_invoice(user=user, business=business)
    invoice.issue_date = timezone.localdate() - timedelta(days=5)
    invoice.due_date = timezone.localdate() - timedelta(days=1)
    invoice.amount_paid = Decimal("10")
    invoice.balance_due = invoice.total - invoice.amount_paid
    invoice.save(update_fields=("issue_date", "due_date", "amount_paid", "balance_due"))

    assert invoice.effective_status == "overdue"

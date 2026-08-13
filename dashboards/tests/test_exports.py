import csv
from decimal import Decimal
from io import StringIO

import pytest
from django.urls import reverse

from crm.services import create_contact
from crm.tests.helpers import CONTACT_DATA
from invoices.tests.helpers import create_converted_invoice
from payments.models import Payment
from payments.services import post_manual_payment, reverse_payment
from workspaces.tests.helpers import (
    business_today,
    create_business,
    create_owner_tenancy,
)


def rows(response):
    return list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))


@pytest.mark.django_db
def test_exports_are_tenant_safe_and_reconcile_to_invoice_and_ledger(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    payment = post_manual_payment(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        amount=Decimal("100"),
        paid_on=business_today(business),
        method=Payment.Method.ACH,
        reference="BANK-100",
    )
    reverse_payment(
        actor=user,
        business_id=business.pk,
        payment_id=payment.pk,
        amount=Decimal("20"),
        reason="Correction",
    )
    other_user, other_workspace, _ = create_owner_tenancy("other@example.com")
    other_business = create_business(
        other_workspace,
        legal_name="Other LLC",
        display_name="Other",
        email="other-business@example.com",
    )
    other_invoice, _, _ = create_converted_invoice(
        user=other_user, business=other_business
    )
    client.force_login(user)

    invoice_rows = rows(client.get(reverse("dashboards:export", args=("invoices",))))
    payment_rows = rows(client.get(reverse("dashboards:export", args=("payments",))))
    contact_rows = rows(client.get(reverse("dashboards:export", args=("contacts",))))
    client_rows = rows(client.get(reverse("dashboards:export", args=("clients",))))

    invoice.refresh_from_db()
    assert [row["invoice_number"] for row in invoice_rows] == [invoice.number]
    assert str(other_invoice.pk) not in {row["invoice_id"] for row in invoice_rows}
    assert Decimal(invoice_rows[0]["amount_paid"]) == invoice.amount_paid
    assert Decimal(invoice_rows[0]["balance_due"]) == invoice.balance_due
    assert Decimal(payment_rows[0]["gross_amount"]) == Decimal("100.00")
    assert Decimal(payment_rows[0]["reversed_amount"]) == Decimal("20.00")
    assert Decimal(payment_rows[0]["net_amount"]) == invoice.amount_paid
    assert Decimal(contact_rows[0]["net_paid"]) == invoice.amount_paid
    assert Decimal(contact_rows[0]["outstanding"]) == invoice.balance_due
    assert [row["contact_id"] for row in client_rows] == [str(invoice.contact_id)]


@pytest.mark.django_db
def test_contact_export_neutralizes_spreadsheet_formulas(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    create_contact(
        actor=user,
        business_id=business.pk,
        data={**CONTACT_DATA, "company_name": '=HYPERLINK("https://bad.invalid")'},
    )
    client.force_login(user)

    response = client.get(reverse("dashboards:export", args=("contacts",)))
    exported = rows(response)

    assert response.headers["Cache-Control"] == "private, no-store"
    assert exported[0]["company_name"].startswith("'=")

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from invoices.models import Invoice
from payments.models import Payment
from workspaces.tests.helpers import create_business, create_owner_tenancy

from .helpers import create_converted_invoice, create_direct_invoice


@pytest.mark.django_db
def test_owner_can_open_invoice_download_pdf_record_payment_and_receipt(
    client, tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_direct_invoice(user=user, business=business)
    client.force_login(user)

    assert client.get(reverse("invoices:detail", args=(invoice.pk,))).status_code == 200
    pdf_response = client.get(reverse("invoices:pdf", args=(invoice.pk,)))
    assert pdf_response.status_code == 200
    assert pdf_response.headers["Content-Type"] == "application/pdf"
    payment_response = client.post(
        reverse("invoices:payment-create", args=(invoice.pk,)),
        {
            "amount": "50.00",
            "paid_on": timezone.localdate().isoformat(),
            "method": Payment.Method.CHECK,
            "reference": "CHK-1042",
            "note": "Received",
            "receipt_email": "",
        },
    )
    assert payment_response.status_code == 302
    payment = Payment.objects.get(invoice=invoice)
    receipt_response = client.get(
        reverse("invoices:payment-receipt", args=(invoice.pk, payment.pk))
    )
    assert receipt_response.status_code == 200
    assert receipt_response.headers["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_owner_opening_customer_view_does_not_record_a_customer_view(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    client.force_login(user)

    response = client.post(
        reverse("invoices:public-link", args=(invoice.pk,)), follow=True
    )

    invoice.refresh_from_db()
    assert response.status_code == 200
    assert invoice.status == Invoice.Status.SENT
    assert invoice.first_viewed_at is None


@pytest.mark.django_db
def test_owner_invoice_routes_do_not_expose_foreign_documents(client):
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    foreign_invoice, _, _ = create_converted_invoice(
        user=second_user, business=second_business
    )
    client.force_login(first_user)

    assert (
        client.get(reverse("invoices:detail", args=(foreign_invoice.pk,))).status_code
        == 404
    )
    assert (
        client.post(reverse("invoices:issue", args=(foreign_invoice.pk,))).status_code
        == 404
    )
    assert (
        client.post(
            reverse("invoices:payment-create", args=(foreign_invoice.pk,)),
            {"amount": Decimal("10")},
        ).status_code
        == 404
    )

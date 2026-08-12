from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import close_old_connections
from django.utils import timezone

from estimates.models import Estimate
from invoices.models import Invoice
from invoices.services import void_invoice
from invoices.tests.helpers import create_converted_invoice
from payments.models import Payment
from payments.services import post_manual_payment, reverse_payment
from workspaces.tests.helpers import create_business, create_owner_tenancy


def post(*, user, business, invoice, amount, send_receipt=False):
    return post_manual_payment(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        amount=Decimal(amount),
        paid_on=timezone.localdate(),
        method=Payment.Method.CHECK,
        reference="CHK-1042",
        note="Received at the office.",
        send_receipt=send_receipt,
        receipt_email="customer@example.com" if send_receipt else "",
    )


@pytest.mark.django_db
def test_manual_lead_to_paid_exit_workflow():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, estimate, contact = create_converted_invoice(
        user=user,
        business=business,
        estimate_data={
            "deposit_type": Estimate.AmountType.FIXED,
            "deposit_value": Decimal("50"),
        },
    )

    estimate.refresh_from_db()
    contact.refresh_from_db()
    assert estimate.status == Estimate.Status.CONVERTED
    assert contact.status == contact.Status.CLIENT
    assert invoice.deposit_required == Decimal("50.00")

    deposit = post(user=user, business=business, invoice=invoice, amount="50")
    invoice.refresh_from_db()
    assert deposit.balance_after_snapshot == Decimal("215.63")
    assert invoice.effective_status == "partial"

    post(user=user, business=business, invoice=invoice, amount="100")
    invoice.refresh_from_db()
    assert invoice.amount_paid == Decimal("150.00")
    assert invoice.effective_status == "partial"

    final = post(
        user=user,
        business=business,
        invoice=invoice,
        amount=str(invoice.balance_due),
    )
    invoice.refresh_from_db()
    assert final.balance_after_snapshot == 0
    assert invoice.balance_due == 0
    assert invoice.effective_status == "paid"
    call_command("reconciliation_check")


@pytest.mark.django_db
def test_deposit_partial_final_payment_and_reversal_reconcile():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)

    post(user=user, business=business, invoice=invoice, amount="50")
    invoice.refresh_from_db()
    assert invoice.amount_paid == Decimal("50.00")
    assert invoice.balance_due == Decimal("215.63")
    assert invoice.effective_status == "partial"

    second = post(user=user, business=business, invoice=invoice, amount="215.63")
    invoice.refresh_from_db()
    assert invoice.amount_paid == invoice.total
    assert invoice.balance_due == 0
    assert invoice.effective_status == "paid"

    reversal = reverse_payment(
        actor=user,
        business_id=business.pk,
        payment_id=second.pk,
        amount=Decimal("15.63"),
        reason="Bank correction",
    )
    invoice.refresh_from_db()
    assert reversal.amount == Decimal("15.63")
    assert second.net_amount == Decimal("200.00")
    assert invoice.amount_paid == Decimal("250.00")
    assert invoice.balance_due == Decimal("15.63")
    call_command("reconciliation_check")


@pytest.mark.django_db
def test_overpayment_future_date_and_excess_reversal_are_rejected():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    with pytest.raises(ValidationError, match="exceed"):
        post(user=user, business=business, invoice=invoice, amount="300")
    with pytest.raises(ValidationError, match="future"):
        post_manual_payment(
            actor=user,
            business_id=business.pk,
            invoice_id=invoice.pk,
            amount=Decimal("10"),
            paid_on=timezone.localdate() + timedelta(days=1),
            method=Payment.Method.CASH,
        )
    payment = post(user=user, business=business, invoice=invoice, amount="20")
    with pytest.raises(ValidationError, match="unreversed"):
        reverse_payment(
            actor=user,
            business_id=business.pk,
            payment_id=payment.pk,
            amount=Decimal("21"),
            reason="Invalid",
        )


@pytest.mark.django_db
def test_posted_payment_and_reversal_are_immutable():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    payment = post(user=user, business=business, invoice=invoice, amount="20")
    reversal = reverse_payment(
        actor=user,
        business_id=business.pk,
        payment_id=payment.pk,
        amount=Decimal("5"),
        reason="Correction",
    )
    with pytest.raises(ValidationError, match="immutable"):
        payment.save()
    with pytest.raises(ValidationError, match="immutable"):
        reversal.save()


@pytest.mark.django_db
def test_invoice_requires_reversals_before_void_and_revokes_links():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    payment = post(user=user, business=business, invoice=invoice, amount="20")
    with pytest.raises(ValidationError, match="Reverse"):
        void_invoice(
            actor=user,
            business_id=business.pk,
            invoice_id=invoice.pk,
            reason="Cancelled",
        )
    reverse_payment(
        actor=user,
        business_id=business.pk,
        payment_id=payment.pk,
        amount=payment.amount,
        reason="Refunded",
    )
    voided = void_invoice(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        reason="Cancelled project",
    )
    assert voided.status == Invoice.Status.VOID
    assert voided.void_reason == "Cancelled project"


@pytest.mark.django_db(transaction=True)
def test_concurrent_payments_lock_balance_and_do_not_overpay():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, _, _ = create_converted_invoice(user=user, business=business)

    def pay_in_connection(amount):
        close_old_connections()
        try:
            return post_manual_payment(
                actor=user,
                business_id=business.pk,
                invoice_id=invoice.pk,
                amount=Decimal(amount),
                paid_on=timezone.localdate(),
                method=Payment.Method.ACH,
            ).amount
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        amounts = list(executor.map(pay_in_connection, ("100", "165.63")))

    invoice.refresh_from_db()
    assert sum(amounts, Decimal("0")) == invoice.total
    assert invoice.amount_paid == invoice.total
    assert invoice.balance_due == 0


@pytest.mark.django_db
def test_cross_tenant_payment_is_denied():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    first_business = create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    invoice, _, _ = create_converted_invoice(user=second_user, business=second_business)
    with pytest.raises(PermissionDenied):
        post(user=first_user, business=first_business, invoice=invoice, amount="10")

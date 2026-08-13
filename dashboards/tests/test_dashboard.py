from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command

from communications.models import EmailDelivery, Notification, OutboxEvent
from dashboards.selectors import dashboard_summary, needs_attention, report_summary
from estimates.models import EstimateAcceptance
from estimates.selectors import estimates_for_business
from estimates.services import record_manual_acceptance
from estimates.tests.helpers import create_issued_estimate
from invoices.selectors import invoices_for_business
from invoices.tests.helpers import create_converted_invoice
from payments.models import Payment
from payments.services import post_manual_payment, reverse_payment
from workspaces.tests.helpers import (
    business_today,
    create_business,
    create_owner_tenancy,
)


@pytest.mark.django_db
def test_dashboard_and_report_totals_follow_ledger_and_tenant_boundary():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    today = business_today(business)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    invoice.issue_date = today - timedelta(days=10)
    invoice.due_date = today - timedelta(days=5)
    invoice.save(update_fields=("issue_date", "due_date", "updated_at"))
    payment = post_manual_payment(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        amount=Decimal("100"),
        paid_on=today,
        method=Payment.Method.CHECK,
    )
    reverse_payment(
        actor=user,
        business_id=business.pk,
        payment_id=payment.pk,
        amount=Decimal("25"),
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
    post_manual_payment(
        actor=other_user,
        business_id=other_business.pk,
        invoice_id=other_invoice.pk,
        amount=Decimal("50"),
        paid_on=today,
        method=Payment.Method.CASH,
    )

    summary = dashboard_summary(business=business, today=today)
    report = report_summary(
        business=business, start=today.replace(day=1), end=today, today=today
    )
    invoice.refresh_from_db()
    assert summary["paid_this_month"] == Decimal("75.00")
    assert summary["outstanding_total"] == invoice.balance_due == Decimal("190.63")
    assert summary["overdue_total"] == invoice.balance_due
    assert report["net_collected"] == Decimal("75.00")
    assert report["invoiced"] == invoice.total
    assert report["receivables"] == invoice.balance_due
    assert report["aging"]["days_1_30"] == invoice.balance_due


@pytest.mark.django_db
def test_needs_attention_surfaces_conversion_delivery_and_outbox_work():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    record_manual_acceptance(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
        method=EstimateAcceptance.Method.PHONE,
    )
    EmailDelivery.objects.create(
        business=business,
        estimate=estimate,
        kind=EmailDelivery.Kind.ESTIMATE,
        recipient="customer@example.com",
        subject="Estimate",
        status=EmailDelivery.Status.FAILED,
        failure_message="Provider unavailable",
    )
    OutboxEvent.objects.create(
        business=business,
        event_type="estimate.email",
        dedupe_key="failed-dashboard-event",
        payload={},
        status=OutboxEvent.Status.FAILED,
    )

    kinds = {item["kind"] for item in needs_attention(business=business)}
    assert kinds == {"Ready to invoice", "Delivery failure", "Outbox alert"}


@pytest.mark.django_db
def test_notifications_are_idempotent_and_tenant_scoped():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    today = business_today(business)
    invoice, _, _ = create_converted_invoice(user=user, business=business)
    invoice.issue_date = today - timedelta(days=2)
    invoice.due_date = today - timedelta(days=1)
    invoice.save(update_fields=("issue_date", "due_date", "updated_at"))
    post_manual_payment(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        amount=Decimal("10"),
        paid_on=today,
        method=Payment.Method.CASH,
    )

    call_command("sync_notifications")
    call_command("sync_notifications")

    assert (
        Notification.objects.filter(
            business=business, kind=Notification.Kind.PAYMENT_RECEIVED
        ).count()
        == 1
    )
    assert (
        Notification.objects.filter(
            business=business, kind=Notification.Kind.INVOICE_OVERDUE
        ).count()
        == 1
    )
    assert (
        Notification.objects.filter(business=business).exclude(recipient=user).count()
        == 0
    )


@pytest.mark.django_db
def test_document_search_and_derived_filters_remain_database_querysets():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    today = business_today(business)
    invoice, estimate, contact = create_converted_invoice(user=user, business=business)
    post_manual_payment(
        actor=user,
        business_id=business.pk,
        invoice_id=invoice.pk,
        amount=Decimal("10"),
        paid_on=today,
        method=Payment.Method.CASH,
    )
    other_estimate, _, other_contact = create_issued_estimate(
        user=user, business=business
    )
    other_estimate.issue_date = today - timedelta(days=10)
    other_estimate.expiration_date = today - timedelta(days=1)
    other_estimate.save(update_fields=("issue_date", "expiration_date", "updated_at"))

    partial = invoices_for_business(
        business=business, search=contact.email, status="partial"
    )
    expired = estimates_for_business(
        business=business, search=other_contact.phone, status="expired"
    )

    assert hasattr(partial, "query") and list(partial) == [invoice]
    assert hasattr(expired, "query") and list(expired) == [other_estimate]
    assert estimate not in expired

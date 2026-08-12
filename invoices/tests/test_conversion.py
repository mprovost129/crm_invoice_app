from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections

from communications.models import DocumentSnapshot
from core.models import DocumentSequence
from crm.services import update_contact
from crm.tests.helpers import CONTACT_DATA
from estimates.models import Estimate, EstimateAcceptance
from estimates.services import record_manual_acceptance
from estimates.tests.helpers import create_issued_estimate
from invoices.models import Invoice
from invoices.services import convert_estimate_to_invoice
from workspaces.tests.helpers import create_business, create_owner_tenancy

from .helpers import create_converted_invoice


@pytest.mark.django_db
def test_accepted_estimate_converts_once_with_locked_number_and_snapshot():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    invoice, estimate, contact = create_converted_invoice(user=user, business=business)

    estimate.refresh_from_db()
    contact.refresh_from_db()
    assert invoice.number == "INV-1001"
    assert invoice.source_estimate == estimate
    assert invoice.status == Invoice.Status.SENT
    assert invoice.total == estimate.total == Decimal("265.63")
    assert invoice.balance_due == invoice.total
    assert invoice.line_items.count() == estimate.line_items.count()
    assert invoice.document_snapshot.payload["invoice"]["number"] == invoice.number
    assert estimate.status == Estimate.Status.CONVERTED
    assert contact.status == contact.Status.CLIENT
    again = convert_estimate_to_invoice(
        actor=user, business_id=business.pk, estimate_id=estimate.pk
    )
    assert again.pk == invoice.pk
    sequence = DocumentSequence.objects.get(
        business=business,
        document_type=DocumentSequence.DocumentType.INVOICE,
    )
    assert sequence.next_value == 1002


@pytest.mark.django_db
def test_required_acceptance_blocks_conversion_and_optional_acceptance_allows_it():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    required, _, _ = create_issued_estimate(user=user, business=business)
    with pytest.raises(ValidationError, match="Accept"):
        convert_estimate_to_invoice(
            actor=user, business_id=business.pk, estimate_id=required.pk
        )

    optional, _, _ = create_issued_estimate(
        user=user,
        business=business,
        estimate_data={"requires_acceptance": False},
    )
    invoice = convert_estimate_to_invoice(
        actor=user, business_id=business.pk, estimate_id=optional.pk
    )
    optional.refresh_from_db()
    assert optional.status == Estimate.Status.CONVERTED
    assert optional.accepted_at is None
    assert invoice.source_estimate == optional


@pytest.mark.django_db
def test_conversion_uses_issued_snapshot_after_contact_changes():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, contact = create_issued_estimate(user=user, business=business)
    original_snapshot = estimate.document_snapshot.payload
    record_manual_acceptance(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
        method=EstimateAcceptance.Method.EMAIL,
        accepted_by_name=contact.display_name,
    )
    update_contact(
        actor=user,
        business_id=business.pk,
        contact_id=contact.pk,
        data={**CONTACT_DATA, "company_name": "Changed after issue"},
    )

    invoice = convert_estimate_to_invoice(
        actor=user, business_id=business.pk, estimate_id=estimate.pk
    )

    assert invoice.document_snapshot.payload["contact"] == original_snapshot["contact"]
    assert (
        invoice.document_snapshot.payload["contact"]["company_name"]
        == "Taylor Renovations"
    )


@pytest.mark.django_db
def test_conversion_rolls_back_number_and_state_when_snapshot_fails(monkeypatch):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    record_manual_acceptance(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
        method=EstimateAcceptance.Method.PHONE,
    )
    monkeypatch.setattr(
        "invoices.services.create_invoice_snapshot",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("snapshot failed")),
    )

    with pytest.raises(RuntimeError, match="snapshot failed"):
        convert_estimate_to_invoice(
            actor=user, business_id=business.pk, estimate_id=estimate.pk
        )

    estimate.refresh_from_db()
    assert estimate.status == Estimate.Status.ACCEPTED
    assert not Invoice.objects.exists()
    assert not DocumentSnapshot.objects.filter(invoice__isnull=False).exists()
    sequence = DocumentSequence.objects.get(
        business=business,
        document_type=DocumentSequence.DocumentType.INVOICE,
    )
    assert sequence.next_value == 1001


@pytest.mark.django_db(transaction=True)
def test_concurrent_conversion_returns_one_invoice():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    record_manual_acceptance(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
        method=EstimateAcceptance.Method.PHONE,
    )

    def convert_in_connection(_):
        close_old_connections()
        try:
            return convert_estimate_to_invoice(
                actor=user,
                business_id=business.pk,
                estimate_id=estimate.pk,
            ).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        invoice_ids = list(executor.map(convert_in_connection, range(2)))

    assert invoice_ids[0] == invoice_ids[1]
    assert Invoice.objects.filter(source_estimate=estimate).count() == 1


@pytest.mark.django_db
def test_cross_tenant_conversion_is_denied():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    first_business = create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    estimate, _, _ = create_issued_estimate(user=second_user, business=second_business)

    with pytest.raises(PermissionDenied):
        convert_estimate_to_invoice(
            actor=first_user,
            business_id=first_business.pk,
            estimate_id=estimate.pk,
        )

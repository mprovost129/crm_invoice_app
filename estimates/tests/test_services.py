from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from activity.models import ActivityEvent
from communications.links import create_public_link
from communications.models import DocumentSnapshot, PublicDocumentLink
from core.models import DocumentSequence
from crm.services import update_contact
from crm.tests.helpers import CONTACT_DATA
from estimates.models import Estimate, EstimateAcceptance
from estimates.services import (
    add_estimate_line,
    issue_estimate,
    record_manual_acceptance,
    update_estimate,
)
from workspaces.tests.helpers import create_business, create_owner_tenancy

from .helpers import (
    ESTIMATE_DATA,
    LINE_DATA,
    create_estimate_fixture,
    create_issued_estimate,
)


@pytest.mark.django_db
def test_draft_line_recalculation_uses_copied_values_and_activity():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, line, contact = create_estimate_fixture(user=user, business=business)

    assert estimate.contact == contact
    assert estimate.status == Estimate.Status.DRAFT
    assert estimate.number == ""
    assert line.line_subtotal == Decimal("250.00")
    assert line.tax_amount == Decimal("15.63")
    assert estimate.total == Decimal("265.63")
    assert ActivityEvent.objects.filter(estimate=estimate).count() == 2


@pytest.mark.django_db
def test_issue_allocates_locked_business_numbers_and_creates_snapshot():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    first, _, _ = create_estimate_fixture(user=user, business=business)
    second, _, _ = create_estimate_fixture(user=user, business=business)

    first = issue_estimate(actor=user, business_id=business.pk, estimate_id=first.pk)
    second = issue_estimate(actor=user, business_id=business.pk, estimate_id=second.pk)

    assert (first.number, second.number) == ("EST-1001", "EST-1002")
    assert first.status == Estimate.Status.SENT
    assert first.issued_at is not None
    assert first.document_snapshot.payload["estimate"]["number"] == first.number
    sequence = DocumentSequence.objects.get(
        business=business,
        document_type=DocumentSequence.DocumentType.ESTIMATE,
    )
    assert sequence.next_value == 1003


@pytest.mark.django_db(transaction=True)
def test_concurrent_issue_allocates_each_business_number_once():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate_ids = [
        create_estimate_fixture(user=user, business=business)[0].pk for _ in range(4)
    ]

    def issue_in_own_connection(estimate_id):
        close_old_connections()
        try:
            return issue_estimate(
                actor=user,
                business_id=business.pk,
                estimate_id=estimate_id,
            ).number
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=4) as executor:
        numbers = list(executor.map(issue_in_own_connection, estimate_ids))

    assert sorted(numbers) == ["EST-1001", "EST-1002", "EST-1003", "EST-1004"]
    assert Estimate.objects.filter(number__in=numbers).count() == 4


@pytest.mark.django_db
def test_issue_rolls_back_number_and_state_when_snapshot_creation_fails(monkeypatch):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_estimate_fixture(user=user, business=business)

    def fail_snapshot(**kwargs):
        raise RuntimeError("snapshot unavailable")

    monkeypatch.setattr("estimates.services.create_estimate_snapshot", fail_snapshot)
    with pytest.raises(RuntimeError, match="snapshot unavailable"):
        issue_estimate(actor=user, business_id=business.pk, estimate_id=estimate.pk)

    estimate.refresh_from_db()
    assert estimate.status == Estimate.Status.DRAFT
    assert estimate.number == ""
    sequence = DocumentSequence.objects.get(
        business=business,
        document_type=DocumentSequence.DocumentType.ESTIMATE,
    )
    assert sequence.next_value == 1001


@pytest.mark.django_db
def test_issued_estimate_and_snapshot_are_immutable():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, contact = create_issued_estimate(user=user, business=business)
    original_payload = estimate.document_snapshot.payload

    with pytest.raises(ValidationError, match="immutable"):
        update_estimate(
            actor=user,
            business_id=business.pk,
            estimate_id=estimate.pk,
            data={**ESTIMATE_DATA, "contact_id": contact.pk, "notes": "Changed"},
        )
    with pytest.raises(ValidationError, match="immutable"):
        estimate.document_snapshot.save()

    update_contact(
        actor=user,
        business_id=business.pk,
        contact_id=contact.pk,
        data={**CONTACT_DATA, "company_name": "Renamed after issue"},
    )
    snapshot = DocumentSnapshot.objects.get(estimate=estimate)
    assert snapshot.payload == original_payload
    assert snapshot.payload["contact"]["company_name"] == "Taylor Renovations"


@pytest.mark.django_db
def test_cross_tenant_estimate_and_catalog_access_is_denied():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    first_business = create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    foreign_estimate, _, _ = create_estimate_fixture(
        user=second_user, business=second_business
    )

    with pytest.raises(PermissionDenied):
        add_estimate_line(
            actor=first_user,
            business_id=first_business.pk,
            estimate_id=foreign_estimate.pk,
            data=LINE_DATA,
        )


@pytest.mark.django_db
def test_manual_acceptance_is_append_only_evidence():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    response_link, _ = create_public_link(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.RESPOND,
    )

    acceptance = record_manual_acceptance(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
        method=EstimateAcceptance.Method.PHONE,
        accepted_by_name="Jordan Taylor",
        metadata={"evidence_note": "Confirmed during recorded call."},
    )

    estimate.refresh_from_db()
    assert estimate.status == Estimate.Status.ACCEPTED
    assert acceptance.recorded_by == user
    assert acceptance.total_snapshot == estimate.total
    assert (
        acceptance.terms_snapshot
        == estimate.document_snapshot.payload["estimate"]["terms"]
    )
    response_link.refresh_from_db()
    assert response_link.revoked_at is not None
    with pytest.raises(ValidationError, match="immutable"):
        acceptance.save()


@pytest.mark.django_db
def test_effective_status_expires_in_business_calendar():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    estimate.issue_date = timezone.localdate() - timedelta(days=2)
    estimate.expiration_date = timezone.localdate() - timedelta(days=1)
    estimate.save(update_fields=("issue_date", "expiration_date", "updated_at"))

    assert estimate.effective_status == "expired"


@pytest.mark.django_db
def test_database_rejects_duplicate_business_estimate_number():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    first, _, contact = create_issued_estimate(user=user, business=business)

    with pytest.raises(IntegrityError), transaction.atomic():
        Estimate.objects.create(
            business=business,
            contact=contact,
            number=first.number,
            status=Estimate.Status.SENT,
            currency="USD",
            issue_date=timezone.localdate(),
            issued_at=timezone.now(),
        )


@pytest.mark.django_db
def test_draft_rejects_expiration_before_issue_date():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)

    with pytest.raises(ValidationError, match="Expiration date"):
        create_estimate_fixture(
            user=user,
            business=business,
            estimate_data={"expiration_date": timezone.localdate() - timedelta(days=1)},
        )

    assert Estimate.objects.count() == 0

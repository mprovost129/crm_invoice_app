import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.urls import reverse

from activity.models import ActivityEvent
from crm.models import Contact, ContactNote
from crm.selectors import contacts_for_business
from crm.services import (
    add_contact_note,
    archive_contact,
    create_contact,
    promote_contact_to_client,
    restore_contact,
    update_contact,
)
from workspaces.tests.helpers import create_business, create_owner_tenancy

from .helpers import CONTACT_DATA


@pytest.mark.django_db
def test_create_contact_uses_trusted_business_and_records_activity(monkeypatch):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    entitlement_businesses = []
    monkeypatch.setattr(
        "crm.services.enforce_contact_creation_allowed",
        lambda *, business: entitlement_businesses.append(business),
    )

    contact = create_contact(actor=user, business_id=business.pk, data=CONTACT_DATA)

    assert contact.business == business
    assert contact.created_by == user
    assert contact.status == Contact.Status.LEAD
    assert entitlement_businesses == [business]
    event = ActivityEvent.objects.get(contact=contact)
    assert event.event_type == ActivityEvent.EventType.CONTACT_CREATED
    assert event.business == business


@pytest.mark.django_db
def test_lead_becomes_client_without_copying_contact_notes_or_history():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    contact = create_contact(actor=user, business_id=business.pk, data=CONTACT_DATA)
    note = add_contact_note(
        actor=user,
        business_id=business.pk,
        contact_id=contact.pk,
        body="Customer approved the initial consultation.",
    )
    original_id = contact.pk

    promoted = promote_contact_to_client(
        actor=user,
        business_id=business.pk,
        contact_id=contact.pk,
    )

    assert promoted.pk == original_id
    assert Contact.objects.count() == 1
    assert promoted.status == Contact.Status.CLIENT
    assert promoted.converted_at is not None
    assert ContactNote.objects.get(pk=note.pk).contact_id == original_id
    assert ActivityEvent.objects.filter(contact_id=original_id).count() == 3


@pytest.mark.django_db
def test_client_archive_and_restore_preserve_client_state():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    data = {**CONTACT_DATA, "initial_status": Contact.Status.CLIENT}
    contact = create_contact(actor=user, business_id=business.pk, data=data)

    archived = archive_contact(
        actor=user,
        business_id=business.pk,
        contact_id=contact.pk,
    )
    assert archived.status == Contact.Status.ARCHIVED
    assert archived.status_before_archive == Contact.Status.CLIENT
    assert archived.archived_at is not None

    restored = restore_contact(
        actor=user,
        business_id=business.pk,
        contact_id=contact.pk,
    )
    assert restored.status == Contact.Status.CLIENT
    assert restored.status_before_archive == ""
    assert restored.archived_at is None
    assert restored.converted_at is not None


@pytest.mark.django_db
def test_database_rejects_inconsistent_contact_lifecycle():
    _, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)

    with pytest.raises(IntegrityError), transaction.atomic():
        Contact.objects.create(
            business=business,
            first_name="Invalid",
            status=Contact.Status.CLIENT,
            converted_at=None,
        )


@pytest.mark.django_db
def test_contact_services_deny_cross_tenant_access():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    first_business = create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    contact = create_contact(
        actor=second_user,
        business_id=second_business.pk,
        data=CONTACT_DATA,
    )
    changed = {**CONTACT_DATA, "first_name": "Compromised"}

    with pytest.raises(PermissionDenied):
        update_contact(
            actor=first_user,
            business_id=first_business.pk,
            contact_id=contact.pk,
            data=changed,
        )

    contact.refresh_from_db()
    assert contact.first_name == "Jordan"


@pytest.mark.django_db
def test_contact_selector_filters_search_status_and_business():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    first_business = create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    lead = create_contact(
        actor=first_user,
        business_id=first_business.pk,
        data=CONTACT_DATA,
    )
    create_contact(
        actor=first_user,
        business_id=first_business.pk,
        data={**CONTACT_DATA, "first_name": "Alex", "initial_status": "client"},
    )
    create_contact(
        actor=second_user,
        business_id=second_business.pk,
        data={**CONTACT_DATA, "first_name": "Foreign"},
    )

    results = contacts_for_business(
        business=first_business,
        search="Taylor Renovations",
        status="lead",
    )

    assert list(results) == [lead]


@pytest.mark.django_db
def test_contact_web_workflow_and_cross_tenant_404(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    foreign_user, foreign_workspace, _ = create_owner_tenancy("foreign@example.com")
    foreign_business = create_business(
        foreign_workspace,
        legal_name="Foreign LLC",
        display_name="Foreign Business",
        email="foreign-business@example.com",
    )
    foreign_contact = create_contact(
        actor=foreign_user,
        business_id=foreign_business.pk,
        data={**CONTACT_DATA, "first_name": "Foreign"},
    )
    client.force_login(user)

    response = client.post(reverse("crm:contact-create"), CONTACT_DATA)
    assert response.status_code == 302
    contact = Contact.objects.get(business=business)
    assert response.url == reverse("crm:contact-detail", args=(contact.pk,))

    detail = client.get(response.url)
    assert detail.status_code == 200
    assert b"Taylor Renovations" in detail.content
    assert b"Financial summary" in detail.content

    note_response = client.post(
        reverse("crm:contact-note-create", args=(contact.pk,)),
        {"body": "Called to confirm scope."},
    )
    assert note_response.status_code == 302
    assert ContactNote.objects.filter(contact=contact).count() == 1

    promote_response = client.post(
        reverse("crm:contact-status", args=(contact.pk, "promote"))
    )
    assert promote_response.status_code == 302
    contact.refresh_from_db()
    assert contact.status == Contact.Status.CLIENT

    assert (
        client.get(
            reverse("crm:contact-detail", args=(foreign_contact.pk,))
        ).status_code
        == 404
    )
    assert (
        client.post(
            reverse("crm:contact-status", args=(foreign_contact.pk, "archive"))
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_contact_pages_require_owner_role(client):
    owner, workspace, membership = create_owner_tenancy()
    create_business(workspace)
    membership.role = membership.Role.MEMBER
    membership.save(update_fields=("role",))
    client.force_login(owner)

    response = client.get(reverse("crm:contact-list"))

    assert response.status_code == 403

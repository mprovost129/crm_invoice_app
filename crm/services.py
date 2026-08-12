from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from workspaces.policies import owner_business_for_actor

from .entitlements import enforce_contact_creation_allowed
from .models import Contact, ContactNote

CONTACT_PROFILE_FIELDS = (
    "first_name",
    "last_name",
    "company_name",
    "email",
    "phone",
    "address_line_1",
    "address_line_2",
    "city",
    "region",
    "postal_code",
    "country_code",
    "notes",
)


def _contact_for_update(*, actor, business_id, contact_id):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    contact = (
        Contact.objects.select_for_update()
        .for_business(business)
        .filter(pk=contact_id)
        .first()
    )
    if contact is None:
        raise PermissionDenied("Contact access is required.")
    return business, contact


@transaction.atomic
def create_contact(*, actor, business_id, data):
    business = owner_business_for_actor(
        actor=actor,
        business_id=business_id,
        lock=True,
    )
    enforce_contact_creation_allowed(business=business)
    initial_status = data.get("initial_status", Contact.Status.LEAD)
    if initial_status not in (Contact.Status.LEAD, Contact.Status.CLIENT):
        raise ValidationError("A new contact must be a lead or client.")

    contact = Contact(
        business=business,
        created_by=actor,
        status=initial_status,
        converted_at=timezone.now()
        if initial_status == Contact.Status.CLIENT
        else None,
        **{field: data.get(field, "") for field in CONTACT_PROFILE_FIELDS},
    )
    contact.full_clean()
    contact.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CONTACT_CREATED,
        summary=f"Created {contact.get_status_display().lower()} {contact.display_name}.",
        contact=contact,
        metadata={"status": contact.status},
    )
    return contact


@transaction.atomic
def update_contact(*, actor, business_id, contact_id, data):
    business, contact = _contact_for_update(
        actor=actor,
        business_id=business_id,
        contact_id=contact_id,
    )
    changed_fields = []
    for field in CONTACT_PROFILE_FIELDS:
        value = data.get(field, "")
        if getattr(contact, field) != value:
            setattr(contact, field, value)
            changed_fields.append(field)
    if not changed_fields:
        return contact

    contact.full_clean()
    contact.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CONTACT_UPDATED,
        summary=f"Updated {contact.display_name}.",
        contact=contact,
        metadata={"changed_fields": changed_fields},
    )
    return contact


@transaction.atomic
def promote_contact_to_client(*, actor, business_id, contact_id):
    business, contact = _contact_for_update(
        actor=actor,
        business_id=business_id,
        contact_id=contact_id,
    )
    if contact.status != Contact.Status.LEAD:
        raise ValidationError("Only an active lead can become a client.")
    contact.status = Contact.Status.CLIENT
    contact.converted_at = timezone.now()
    contact.full_clean()
    contact.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CONTACT_STATUS_CHANGED,
        summary=f"Converted {contact.display_name} from lead to client.",
        contact=contact,
        metadata={"from": Contact.Status.LEAD, "to": Contact.Status.CLIENT},
    )
    return contact


@transaction.atomic
def archive_contact(*, actor, business_id, contact_id):
    business, contact = _contact_for_update(
        actor=actor,
        business_id=business_id,
        contact_id=contact_id,
    )
    if contact.status == Contact.Status.ARCHIVED:
        raise ValidationError("Contact is already archived.")
    prior_status = contact.status
    contact.status_before_archive = prior_status
    contact.status = Contact.Status.ARCHIVED
    contact.archived_at = timezone.now()
    contact.full_clean()
    contact.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CONTACT_STATUS_CHANGED,
        summary=f"Archived {contact.display_name}.",
        contact=contact,
        metadata={"from": prior_status, "to": Contact.Status.ARCHIVED},
    )
    return contact


@transaction.atomic
def restore_contact(*, actor, business_id, contact_id):
    business, contact = _contact_for_update(
        actor=actor,
        business_id=business_id,
        contact_id=contact_id,
    )
    if contact.status != Contact.Status.ARCHIVED:
        raise ValidationError("Only an archived contact can be restored.")
    restored_status = contact.status_before_archive
    if restored_status not in (Contact.Status.LEAD, Contact.Status.CLIENT):
        raise ValidationError("The archived contact has no valid previous status.")
    contact.status = restored_status
    contact.status_before_archive = ""
    contact.archived_at = None
    contact.full_clean()
    contact.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CONTACT_STATUS_CHANGED,
        summary=f"Restored {contact.display_name} as a {restored_status}.",
        contact=contact,
        metadata={"from": Contact.Status.ARCHIVED, "to": restored_status},
    )
    return contact


@transaction.atomic
def add_contact_note(*, actor, business_id, contact_id, body):
    business, contact = _contact_for_update(
        actor=actor,
        business_id=business_id,
        contact_id=contact_id,
    )
    note = ContactNote(
        business=business,
        contact=contact,
        body=body.strip(),
        created_by=actor,
    )
    note.full_clean()
    note.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CONTACT_NOTE_ADDED,
        summary=f"Added a note to {contact.display_name}.",
        contact=contact,
        metadata={"note_id": str(note.pk)},
    )
    return note

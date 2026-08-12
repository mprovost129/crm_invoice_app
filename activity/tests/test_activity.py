import pytest
from django.core.exceptions import ValidationError

from activity.models import ActivityEvent
from activity.services import record_activity
from crm.services import create_contact
from crm.tests.helpers import CONTACT_DATA
from workspaces.tests.helpers import create_business, create_owner_tenancy


@pytest.mark.django_db
def test_activity_rejects_foreign_business_target_and_is_append_only():
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

    with pytest.raises(ValidationError):
        record_activity(
            business=first_business,
            actor=first_user,
            event_type=ActivityEvent.EventType.CONTACT_UPDATED,
            summary="Invalid foreign event.",
            contact=contact,
        )

    event = ActivityEvent.objects.get(
        business=second_business,
        event_type=ActivityEvent.EventType.CONTACT_CREATED,
    )
    event.summary = "Changed"
    with pytest.raises(ValidationError):
        event.save()

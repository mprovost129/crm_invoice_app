from django.core.exceptions import ValidationError

from .models import ActivityEvent


def record_activity(
    *,
    business,
    actor,
    event_type,
    summary,
    contact=None,
    product_service=None,
    metadata=None,
):
    event = ActivityEvent(
        business=business,
        actor=actor,
        event_type=event_type,
        summary=summary,
        contact=contact,
        product_service=product_service,
        metadata=metadata or {},
    )
    if (contact is None) == (product_service is None):
        raise ValidationError("Activity requires exactly one target.")
    event.full_clean()
    event.save()
    return event

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
    estimate=None,
    metadata=None,
):
    event = ActivityEvent(
        business=business,
        actor=actor,
        event_type=event_type,
        summary=summary,
        contact=contact,
        product_service=product_service,
        estimate=estimate,
        metadata=metadata or {},
    )
    if sum(target is not None for target in (contact, product_service, estimate)) != 1:
        raise ValidationError("Activity requires exactly one target.")
    event.full_clean()
    event.save()
    return event

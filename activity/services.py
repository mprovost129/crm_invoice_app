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
    invoice=None,
    payment=None,
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
        invoice=invoice,
        payment=payment,
        metadata=metadata or {},
    )
    targets = (contact, product_service, estimate, invoice, payment)
    if sum(target is not None for target in targets) != 1:
        raise ValidationError("Activity requires exactly one target.")
    event.full_clean()
    event.save()
    return event

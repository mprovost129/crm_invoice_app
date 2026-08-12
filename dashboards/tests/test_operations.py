from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from communications.models import EmailDelivery, Notification, OutboxEvent
from estimates.tests.helpers import create_issued_estimate
from workspaces.tests.helpers import create_business, create_owner_tenancy


@pytest.mark.django_db
def test_outbox_health_check_detects_failed_delivery_and_stale_work():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    delivery = EmailDelivery.objects.create(
        business=business,
        estimate=estimate,
        kind=EmailDelivery.Kind.ESTIMATE,
        recipient="customer@example.com",
        subject="Estimate",
    )
    event = OutboxEvent.objects.create(
        business=business,
        event_type="estimate.email",
        dedupe_key="health-check-event",
        payload={"delivery_id": str(delivery.pk)},
        available_at=timezone.now() + timedelta(hours=1),
    )

    call_command("outbox_health_check")
    delivery.status = EmailDelivery.Status.FAILED
    delivery.failure_message = "Provider unavailable"
    delivery.save(update_fields=("status", "failure_message", "updated_at"))
    event.status = OutboxEvent.Status.FAILED
    event.save(update_fields=("status", "updated_at"))

    with pytest.raises(CommandError, match="Communication health failed"):
        call_command("outbox_health_check")


@pytest.mark.django_db
def test_delivery_failure_notification_is_deduplicated(monkeypatch):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    delivery = EmailDelivery.objects.create(
        business=business,
        estimate=estimate,
        kind=EmailDelivery.Kind.ESTIMATE,
        recipient="customer@example.com",
        subject="Estimate",
    )
    event = OutboxEvent.objects.create(
        business=business,
        event_type="estimate.email",
        dedupe_key="failing-delivery-event",
        payload={"delivery_id": str(delivery.pk)},
    )
    monkeypatch.setattr(
        "communications.emailing.get_or_create_estimate_pdf",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Storage unavailable")),
    )
    from communications.emailing import process_outbox_event

    process_outbox_event(event.pk)
    process_outbox_event(event.pk)

    assert (
        Notification.objects.filter(
            business=business,
            kind=Notification.Kind.DELIVERY_FAILED,
        ).count()
        == 1
    )

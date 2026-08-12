from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from estimates.models import Estimate
from workspaces.policies import owner_business_for_actor

from .links import create_public_link
from .models import EmailDelivery, OutboxEvent, PublicDocumentLink
from .pdf import get_or_create_estimate_pdf

ESTIMATE_EMAIL_EVENT = "estimate.email"


@transaction.atomic
def queue_estimate_email(*, actor, business_id, estimate_id, recipient):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    estimate = (
        Estimate.objects.select_for_update()
        .for_business(business)
        .filter(pk=estimate_id)
        .first()
    )
    if estimate is None:
        raise ValidationError("Estimate not found.")
    if estimate.status == Estimate.Status.DRAFT:
        raise ValidationError("Issue the estimate before sending it.")
    if estimate.status in (Estimate.Status.DECLINED, Estimate.Status.CONVERTED):
        raise ValidationError("This estimate cannot be emailed in its current state.")

    delivery = EmailDelivery.objects.create(
        business=business,
        estimate=estimate,
        recipient=recipient,
        subject=f"Estimate {estimate.number} from {business.display_name}",
    )
    event = OutboxEvent.objects.create(
        business=business,
        event_type=ESTIMATE_EMAIL_EVENT,
        dedupe_key=f"estimate-email:{delivery.pk}",
        payload={"delivery_id": str(delivery.pk)},
    )
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_EMAIL_QUEUED,
        summary=f"Queued estimate {estimate.number} for {recipient}.",
        estimate=estimate,
    )
    transaction.on_commit(partial(process_outbox_event, event.pk), robust=True)
    return delivery


def _mark_failed(*, event_id, delivery_id, error):
    safe_message = str(error).replace("\n", " ")[:500]
    with transaction.atomic():
        OutboxEvent.objects.filter(pk=event_id).update(
            status=OutboxEvent.Status.FAILED,
            last_error=safe_message,
        )
        EmailDelivery.objects.filter(pk=delivery_id).update(
            status=EmailDelivery.Status.FAILED,
            failure_code=error.__class__.__name__[:80],
            failure_message=safe_message,
        )


def process_outbox_event(event_id):
    with transaction.atomic():
        event = OutboxEvent.objects.select_for_update().filter(pk=event_id).first()
        if event is None or event.status not in (
            OutboxEvent.Status.PENDING,
            OutboxEvent.Status.FAILED,
        ):
            return
        event.status = OutboxEvent.Status.PROCESSING
        event.attempts += 1
        event.last_error = ""
        event.save(update_fields=("status", "attempts", "last_error", "updated_at"))
        delivery_id = event.payload["delivery_id"]

    try:
        delivery = EmailDelivery.objects.select_related(
            "estimate",
            "estimate__business",
            "estimate__document_snapshot",
        ).get(pk=delivery_id)
        estimate = delivery.estimate
        asset = get_or_create_estimate_pdf(estimate=estimate)
        _, view_token = create_public_link(
            estimate=estimate,
            purpose=PublicDocumentLink.Purpose.VIEW,
        )
        _, response_token = create_public_link(
            estimate=estimate,
            purpose=PublicDocumentLink.Purpose.RESPOND,
        )
        view_url = (
            f"{settings.SITE_URL}"
            f"{reverse('estimates:public-view', kwargs={'token': view_token})}"
        )
        response_url = (
            f"{settings.SITE_URL}"
            f"{reverse('estimates:public-respond', kwargs={'token': response_token})}"
        )
        message = EmailMessage(
            subject=delivery.subject,
            body=(
                f"{estimate.business.display_name} sent estimate {estimate.number}.\n\n"
                f"View estimate: {view_url}\n\n"
                f"Accept or decline: {response_url}\n\n"
                "The response link is private. Do not forward it."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[delivery.recipient],
        )
        with default_storage.open(asset.storage_name, "rb") as pdf_file:
            message.attach(
                f"Estimate-{estimate.number}.pdf",
                pdf_file.read(),
                "application/pdf",
            )
        if message.send(fail_silently=False) != 1:
            raise RuntimeError("The email backend did not confirm delivery.")
    except Exception as exc:
        _mark_failed(
            event_id=event_id,
            delivery_id=delivery_id,
            error=exc,
        )
        return

    now = timezone.now()
    with transaction.atomic():
        EmailDelivery.objects.filter(pk=delivery_id).update(
            status=EmailDelivery.Status.SENT,
            sent_at=now,
            failure_code="",
            failure_message="",
        )
        OutboxEvent.objects.filter(pk=event_id).update(
            status=OutboxEvent.Status.COMPLETED,
            processed_at=now,
            last_error="",
        )

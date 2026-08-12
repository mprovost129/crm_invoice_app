from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from communications.models import PublicDocumentLink

from .models import Estimate, EstimateAcceptance


@transaction.atomic
def record_public_view(*, link):
    locked_link = PublicDocumentLink.objects.select_for_update().get(pk=link.pk)
    if not locked_link.is_active:
        raise ValidationError("This document link is no longer available.")
    estimate = (
        Estimate.objects.select_for_update()
        .select_related("business")
        .get(pk=locked_link.estimate_id)
    )
    now = timezone.now()
    PublicDocumentLink.objects.filter(pk=locked_link.pk).update(
        access_count=F("access_count") + 1,
        last_accessed_at=now,
    )
    if estimate.status == Estimate.Status.SENT:
        estimate.status = Estimate.Status.VIEWED
        estimate.first_viewed_at = now
        estimate.save(update_fields=("status", "first_viewed_at", "updated_at"))
        record_activity(
            business=estimate.business,
            actor=None,
            event_type=ActivityEvent.EventType.ESTIMATE_VIEWED,
            summary=f"Customer viewed estimate {estimate.number}.",
            estimate=estimate,
        )
    return estimate


def _respondable_estimate(link):
    if not link.is_active:
        raise ValidationError("This response link is no longer available.")
    estimate = (
        Estimate.objects.select_for_update()
        .select_related("business")
        .get(pk=link.estimate_id)
    )
    if estimate.status not in (Estimate.Status.SENT, Estimate.Status.VIEWED):
        raise ValidationError("This estimate can no longer receive a response.")
    if estimate.effective_status == "expired":
        raise ValidationError("This estimate has expired.")
    return estimate


@transaction.atomic
def accept_public_estimate(
    *, link, accepted_by_name, accepted_by_email, ip_address=None, user_agent=""
):
    locked_link = PublicDocumentLink.objects.select_for_update().get(
        pk=link.pk,
        purpose=PublicDocumentLink.Purpose.RESPOND,
    )
    estimate = _respondable_estimate(locked_link)
    acceptance = EstimateAcceptance(
        business=estimate.business,
        estimate=estimate,
        method=EstimateAcceptance.Method.ONLINE,
        accepted_by_name=accepted_by_name.strip(),
        accepted_by_email=accepted_by_email.strip(),
        ip_address=ip_address,
        user_agent=user_agent[:500],
        terms_snapshot=estimate.document_snapshot.payload["estimate"]["terms"],
        total_snapshot=estimate.total,
    )
    acceptance.full_clean()
    acceptance.save()
    estimate.status = Estimate.Status.ACCEPTED
    estimate.accepted_at = acceptance.accepted_at
    estimate.save(update_fields=("status", "accepted_at", "updated_at"))
    now = timezone.now()
    PublicDocumentLink.objects.filter(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.RESPOND,
        revoked_at__isnull=True,
    ).update(revoked_at=now)
    record_activity(
        business=estimate.business,
        actor=None,
        event_type=ActivityEvent.EventType.ESTIMATE_ACCEPTED,
        summary=f"Customer accepted estimate {estimate.number} online.",
        estimate=estimate,
        metadata={"method": EstimateAcceptance.Method.ONLINE},
    )
    return acceptance


@transaction.atomic
def decline_public_estimate(*, link, reason=""):
    locked_link = PublicDocumentLink.objects.select_for_update().get(
        pk=link.pk,
        purpose=PublicDocumentLink.Purpose.RESPOND,
    )
    estimate = _respondable_estimate(locked_link)
    estimate.status = Estimate.Status.DECLINED
    estimate.declined_at = timezone.now()
    estimate.decline_reason = reason.strip()
    estimate.save(
        update_fields=("status", "declined_at", "decline_reason", "updated_at")
    )
    PublicDocumentLink.objects.filter(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.RESPOND,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())
    record_activity(
        business=estimate.business,
        actor=None,
        event_type=ActivityEvent.EventType.ESTIMATE_DECLINED,
        summary=f"Customer declined estimate {estimate.number} online.",
        estimate=estimate,
    )
    return estimate

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from communications.models import PublicDocumentLink

from .models import Invoice


@transaction.atomic
def record_public_view(*, link):
    locked_link = PublicDocumentLink.objects.select_for_update().get(pk=link.pk)
    if not locked_link.is_active:
        raise ValidationError("This document link is no longer available.")
    invoice = (
        Invoice.objects.select_for_update()
        .select_related("business")
        .get(pk=locked_link.invoice_id)
    )
    now = timezone.now()
    PublicDocumentLink.objects.filter(pk=locked_link.pk).update(
        access_count=F("access_count") + 1,
        last_accessed_at=now,
    )
    if invoice.status == Invoice.Status.SENT:
        invoice.status = Invoice.Status.VIEWED
        invoice.first_viewed_at = now
        invoice.save(update_fields=("status", "first_viewed_at", "updated_at"))
        record_activity(
            business=invoice.business,
            actor=None,
            event_type=ActivityEvent.EventType.INVOICE_VIEWED,
            summary=f"Customer viewed invoice {invoice.number}.",
            invoice=invoice,
        )
    return invoice

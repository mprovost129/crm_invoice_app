import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ActivityEventQuerySet(models.QuerySet):
    def for_business(self, business):
        if business is None:
            return self.none()
        return self.filter(business=business)


class ActivityEvent(models.Model):
    class EventType(models.TextChoices):
        CONTACT_CREATED = "contact.created", "Contact created"
        CONTACT_UPDATED = "contact.updated", "Contact updated"
        CONTACT_STATUS_CHANGED = "contact.status_changed", "Contact status changed"
        CONTACT_NOTE_ADDED = "contact.note_added", "Contact note added"
        CATALOG_CREATED = "catalog.created", "Catalog item created"
        CATALOG_UPDATED = "catalog.updated", "Catalog item updated"
        CATALOG_STATUS_CHANGED = "catalog.status_changed", "Catalog status changed"
        ESTIMATE_CREATED = "estimate.created", "Estimate created"
        ESTIMATE_UPDATED = "estimate.updated", "Estimate updated"
        ESTIMATE_LINE_CHANGED = "estimate.line_changed", "Estimate line changed"
        ESTIMATE_ISSUED = "estimate.issued", "Estimate issued"
        ESTIMATE_EMAIL_QUEUED = "estimate.email_queued", "Estimate email queued"
        ESTIMATE_VIEWED = "estimate.viewed", "Estimate viewed"
        ESTIMATE_ACCEPTED = "estimate.accepted", "Estimate accepted"
        ESTIMATE_DECLINED = "estimate.declined", "Estimate declined"
        ESTIMATE_CONVERTED = "estimate.converted", "Estimate converted"
        INVOICE_CREATED = "invoice.created", "Invoice created"
        INVOICE_LINE_CHANGED = "invoice.line_changed", "Invoice line changed"
        INVOICE_ISSUED = "invoice.issued", "Invoice issued"
        INVOICE_EMAIL_QUEUED = "invoice.email_queued", "Invoice email queued"
        INVOICE_REMINDER_QUEUED = "invoice.reminder_queued", "Reminder queued"
        INVOICE_VIEWED = "invoice.viewed", "Invoice viewed"
        INVOICE_VOIDED = "invoice.voided", "Invoice voided"
        PAYMENT_POSTED = "payment.posted", "Payment posted"
        PAYMENT_REVERSED = "payment.reversed", "Payment reversed"
        PAYMENT_RECEIPT_QUEUED = "payment.receipt_queued", "Receipt queued"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "workspaces.Business",
        on_delete=models.PROTECT,
        related_name="activity_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="activity_events",
        blank=True,
        null=True,
    )
    contact = models.ForeignKey(
        "crm.Contact",
        on_delete=models.PROTECT,
        related_name="activity_events",
        blank=True,
        null=True,
    )
    product_service = models.ForeignKey(
        "catalog.ProductService",
        on_delete=models.PROTECT,
        related_name="activity_events",
        blank=True,
        null=True,
    )
    estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="activity_events",
        blank=True,
        null=True,
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="activity_events",
        blank=True,
        null=True,
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="activity_events",
        blank=True,
        null=True,
    )
    event_type = models.CharField(max_length=64, choices=EventType.choices)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ActivityEventQuerySet.as_manager()

    class Meta:
        ordering = ("-occurred_at", "-created_at")
        indexes = [
            models.Index(fields=("business", "occurred_at")),
            models.Index(fields=("business", "event_type", "occurred_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        contact__isnull=False,
                        product_service__isnull=True,
                        estimate__isnull=True,
                        invoice__isnull=True,
                        payment__isnull=True,
                    )
                    | Q(
                        contact__isnull=True,
                        product_service__isnull=False,
                        estimate__isnull=True,
                        invoice__isnull=True,
                        payment__isnull=True,
                    )
                    | Q(
                        contact__isnull=True,
                        product_service__isnull=True,
                        estimate__isnull=False,
                        invoice__isnull=True,
                        payment__isnull=True,
                    )
                    | Q(
                        contact__isnull=True,
                        product_service__isnull=True,
                        estimate__isnull=True,
                        invoice__isnull=False,
                        payment__isnull=True,
                    )
                    | Q(
                        contact__isnull=True,
                        product_service__isnull=True,
                        estimate__isnull=True,
                        invoice__isnull=True,
                        payment__isnull=False,
                    )
                ),
                name="activity_event_exactly_one_target",
            )
        ]

    def clean(self):
        super().clean()
        target = (
            self.contact
            or self.product_service
            or self.estimate
            or self.invoice
            or self.payment
        )
        if target and target.business_id != self.business_id:
            raise ValidationError("Activity target must belong to the same business.")

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Activity events are append-only.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.summary

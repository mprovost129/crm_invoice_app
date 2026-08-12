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
                    Q(contact__isnull=False, product_service__isnull=True)
                    | Q(contact__isnull=True, product_service__isnull=False)
                ),
                name="activity_event_exactly_one_target",
            )
        ]

    def clean(self):
        super().clean()
        target = self.contact or self.product_service
        if target and target.business_id != self.business_id:
            raise ValidationError("Activity target must belong to the same business.")

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Activity events are append-only.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.summary

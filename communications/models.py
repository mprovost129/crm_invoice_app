import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import BusinessOwnedModel


class DocumentSnapshot(BusinessOwnedModel):
    estimate = models.OneToOneField(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="document_snapshot",
    )
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()
    content_sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Document snapshots are immutable.")
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("Snapshot and estimate must share a business.")

    def __str__(self):
        return f"Snapshot for {self.estimate}"


class PublicDocumentLink(BusinessOwnedModel):
    class Purpose(models.TextChoices):
        VIEW = "view", "View"
        RESPOND = "respond", "View and respond"

    estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="public_links",
    )
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(blank=True, null=True)
    access_count = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("business", "estimate", "purpose", "revoked_at"))
        ]

    @property
    def is_active(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("Public link and estimate must share a business.")


class FileAsset(BusinessOwnedModel):
    class Kind(models.TextChoices):
        ESTIMATE_PDF = "estimate_pdf", "Estimate PDF"

    estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="file_assets",
    )
    snapshot = models.ForeignKey(
        DocumentSnapshot,
        on_delete=models.PROTECT,
        related_name="file_assets",
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    storage_name = models.CharField(max_length=500, unique=True)
    content_type = models.CharField(max_length=100, default="application/pdf")
    byte_size = models.PositiveBigIntegerField()
    content_sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("File and estimate must share a business.")
        if self.snapshot_id and self.business_id != self.snapshot.business_id:
            raise ValidationError("File and snapshot must share a business.")


class EmailDelivery(BusinessOwnedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="email_deliveries",
    )
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    sent_at = models.DateTimeField(blank=True, null=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("Delivery and estimate must share a business.")


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "workspaces.Business",
        on_delete=models.PROTECT,
        related_name="outbox_events",
    )
    event_type = models.CharField(max_length=80)
    dedupe_key = models.CharField(max_length=180, unique=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("status", "available_at"))]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="completed", processed_at__isnull=False)
                    | (~Q(status="completed") & Q(processed_at__isnull=True))
                ),
                name="communications_outbox_completion_consistent",
            )
        ]

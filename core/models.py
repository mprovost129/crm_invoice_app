import uuid

from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models

from .querysets import BusinessOwnedQuerySet


class TimeStampedModel(models.Model):
    """Optional abstract base for the common created/updated timestamp pattern."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BusinessOwnedModel(TimeStampedModel):
    """Abstract base for records that belong directly to one tenant Business."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "workspaces.Business",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_records",
    )

    objects = BusinessOwnedQuerySet.as_manager()

    class Meta:
        abstract = True


class DocumentSequence(TimeStampedModel):
    """Transaction-lockable visible-number sequence scoped to one Business."""

    class DocumentType(models.TextChoices):
        ESTIMATE = "estimate", "Estimate"
        INVOICE = "invoice", "Invoice"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "workspaces.Business",
        on_delete=models.PROTECT,
        related_name="document_sequences",
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    prefix = models.CharField(
        max_length=12,
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9-]{1,12}$",
                message="Use 1-12 uppercase letters, numbers, or hyphens.",
            )
        ],
    )
    next_value = models.PositiveBigIntegerField(default=1001)
    padding_width = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )

    class Meta:
        ordering = ("business_id", "document_type")
        constraints = [
            models.UniqueConstraint(
                fields=("business", "document_type"),
                name="core_document_sequence_business_type_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(next_value__gt=0),
                name="core_document_sequence_next_value_positive",
            ),
        ]

    def __str__(self):
        return f"{self.business}: {self.get_document_type_display()}"

import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import BusinessOwnedModel


class EstimateQuerySet(models.QuerySet):
    def for_business(self, business):
        if business is None:
            return self.none()
        return self.filter(business=business)


class Estimate(BusinessOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        VIEWED = "viewed", "Viewed"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CONVERTED = "converted", "Converted"

    class AmountType(models.TextChoices):
        NONE = "none", "None"
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed amount"

    contact = models.ForeignKey(
        "crm.Contact",
        on_delete=models.PROTECT,
        related_name="estimates",
    )
    number = models.CharField(max_length=40, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    currency = models.CharField(max_length=3)
    issue_date = models.DateField(blank=True, null=True)
    expiration_date = models.DateField(blank=True, null=True)
    discount_type = models.CharField(
        max_length=20,
        choices=AmountType.choices,
        default=AmountType.NONE,
    )
    discount_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(0)],
    )
    deposit_type = models.CharField(
        max_length=20,
        choices=AmountType.choices,
        default=AmountType.NONE,
    )
    deposit_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(0)],
    )
    requires_acceptance = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deposit_required = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    issued_at = models.DateTimeField(blank=True, null=True)
    first_viewed_at = models.DateTimeField(blank=True, null=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    declined_at = models.DateTimeField(blank=True, null=True)
    decline_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_estimates",
        blank=True,
        null=True,
    )

    objects = EstimateQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("business", "status", "created_at")),
            models.Index(fields=("business", "contact", "created_at")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("business", "number"),
                condition=~Q(number=""),
                name="estimates_estimate_business_number_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(discount_value__gte=0)
                    & Q(deposit_value__gte=0)
                    & Q(subtotal__gte=0)
                    & Q(discount_amount__gte=0)
                    & Q(tax_amount__gte=0)
                    & Q(total__gte=0)
                    & Q(deposit_required__gte=0)
                    & Q(discount_amount__lte=models.F("subtotal"))
                    & Q(deposit_required__lte=models.F("total"))
                ),
                name="estimates_estimate_amounts_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="draft", number="", issued_at__isnull=True)
                    | (
                        ~Q(status="draft")
                        & ~Q(number="")
                        & Q(issued_at__isnull=False)
                        & Q(issue_date__isnull=False)
                    )
                ),
                name="estimates_estimate_issue_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(status__in=("accepted", "converted"))
                        & Q(accepted_at__isnull=False)
                    )
                    | (
                        ~Q(status__in=("accepted", "converted"))
                        & Q(accepted_at__isnull=True)
                    )
                ),
                name="estimates_estimate_acceptance_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(status="declined") & Q(declined_at__isnull=False))
                    | (~Q(status="declined") & Q(declined_at__isnull=True))
                ),
                name="estimates_estimate_decline_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(issue_date__isnull=True)
                    | Q(expiration_date__isnull=True)
                    | Q(expiration_date__gte=models.F("issue_date"))
                ),
                name="estimates_estimate_dates_valid",
            ),
        ]

    @property
    def effective_status(self):
        if (
            self.status in (self.Status.SENT, self.Status.VIEWED)
            and self.expiration_date
        ):
            business_today = timezone.localdate(
                timezone=ZoneInfo(self.business.timezone)
            )
            if self.expiration_date < business_today:
                return "expired"
        return self.status

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    def clean(self):
        super().clean()
        if self.contact_id and self.business_id != self.contact.business_id:
            raise ValidationError(
                "Estimate and contact must belong to the same business."
            )
        for amount_type, value, label in (
            (self.discount_type, self.discount_value, "Discount"),
            (self.deposit_type, self.deposit_value, "Deposit"),
        ):
            if amount_type == self.AmountType.NONE and value != 0:
                raise ValidationError(f"{label} value must be zero when type is None.")
            if amount_type == self.AmountType.PERCENTAGE and value > 100:
                raise ValidationError(f"{label} percentage cannot exceed 100.")
        if (
            self.issue_date
            and self.expiration_date
            and self.expiration_date < self.issue_date
        ):
            raise ValidationError("Expiration date cannot be before the issue date.")

    def __str__(self):
        return self.number or f"Draft estimate for {self.contact}"


class EstimateLineItem(BusinessOwnedModel):
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.PROTECT,
        related_name="line_items",
    )
    source_catalog_item = models.ForeignKey(
        "catalog.ProductService",
        on_delete=models.PROTECT,
        related_name="estimate_line_items",
        blank=True,
        null=True,
    )
    position = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=40, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_rate = models.DecimalField(max_digits=14, decimal_places=4)
    is_taxable = models.BooleanField(default=False)
    tax_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    line_subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    allocated_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ("position", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("estimate", "position"),
                name="estimates_line_estimate_position_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(quantity__gt=0)
                    & Q(unit_rate__gte=0)
                    & Q(tax_rate__gte=0)
                    & Q(tax_rate__lte=100)
                    & Q(line_subtotal__gte=0)
                    & Q(allocated_discount__gte=0)
                    & Q(taxable_amount__gte=0)
                    & Q(tax_amount__gte=0)
                    & Q(line_total__gte=0)
                ),
                name="estimates_line_amounts_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("Line item and estimate must share a business.")
        if (
            self.source_catalog_item_id
            and self.business_id != self.source_catalog_item.business_id
        ):
            raise ValidationError("Catalog item must belong to the estimate business.")

    def __str__(self):
        return f"{self.position}. {self.name}"


class EstimateAcceptance(models.Model):
    class Method(models.TextChoices):
        ONLINE = "online", "Online"
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        IN_PERSON = "in_person", "In person"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "workspaces.Business",
        on_delete=models.PROTECT,
        related_name="estimate_acceptances",
    )
    estimate = models.OneToOneField(
        Estimate,
        on_delete=models.PROTECT,
        related_name="acceptance",
    )
    method = models.CharField(max_length=20, choices=Method.choices)
    accepted_by_name = models.CharField(max_length=255, blank=True)
    accepted_by_email = models.EmailField(blank=True)
    accepted_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_estimate_acceptances",
        blank=True,
        null=True,
    )
    terms_snapshot = models.TextField(blank=True)
    total_snapshot = models.DecimalField(max_digits=14, decimal_places=2)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-accepted_at",)

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Estimate acceptance evidence is immutable.")
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("Acceptance and estimate must share a business.")

    def __str__(self):
        return f"Acceptance for {self.estimate}"

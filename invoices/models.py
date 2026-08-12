from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import BusinessOwnedModel


class InvoiceQuerySet(models.QuerySet):
    def for_business(self, business):
        if business is None:
            return self.none()
        return self.filter(business=business)


class Invoice(BusinessOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        VIEWED = "viewed", "Viewed"
        VOID = "void", "Void"

    class AmountType(models.TextChoices):
        NONE = "none", "None"
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed amount"

    contact = models.ForeignKey(
        "crm.Contact",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    source_estimate = models.OneToOneField(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="invoice",
        blank=True,
        null=True,
    )
    number = models.CharField(max_length=40, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    currency = models.CharField(max_length=3)
    issue_date = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
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
    deposit_required = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    issued_at = models.DateTimeField(blank=True, null=True)
    first_viewed_at = models.DateTimeField(blank=True, null=True)
    voided_at = models.DateTimeField(blank=True, null=True)
    void_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_invoices",
        blank=True,
        null=True,
    )

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("business", "status", "created_at")),
            models.Index(fields=("business", "contact", "created_at")),
            models.Index(fields=("business", "due_date")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("business", "number"),
                condition=~Q(number=""),
                name="invoices_invoice_business_number_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(discount_value__gte=0)
                    & Q(subtotal__gte=0)
                    & Q(discount_amount__gte=0)
                    & Q(tax_amount__gte=0)
                    & Q(total__gte=0)
                    & Q(deposit_required__gte=0)
                    & Q(amount_paid__gte=0)
                    & Q(balance_due__gte=0)
                    & Q(discount_amount__lte=models.F("subtotal"))
                    & (Q(status="draft") | Q(deposit_required__lte=models.F("total")))
                    & Q(amount_paid__lte=models.F("total"))
                    & Q(balance_due=models.F("total") - models.F("amount_paid"))
                ),
                name="invoices_invoice_amounts_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="draft",
                        number="",
                        issued_at__isnull=True,
                    )
                    | (
                        ~Q(status="draft")
                        & ~Q(number="")
                        & Q(issued_at__isnull=False)
                        & Q(issue_date__isnull=False)
                        & Q(due_date__isnull=False)
                    )
                ),
                name="invoices_invoice_issue_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(status="void", voided_at__isnull=False) & ~Q(void_reason=""))
                    | (~Q(status="void") & Q(voided_at__isnull=True, void_reason=""))
                ),
                name="invoices_invoice_void_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(issue_date__isnull=True)
                    | Q(due_date__isnull=True)
                    | Q(due_date__gte=models.F("issue_date"))
                ),
                name="invoices_invoice_dates_valid",
            ),
        ]

    @property
    def effective_status(self):
        if self.status == self.Status.VOID:
            return self.Status.VOID
        if self.status != self.Status.DRAFT:
            if self.balance_due == 0:
                return "paid"
            if self.due_date:
                business_today = timezone.localdate(
                    timezone=ZoneInfo(self.business.timezone)
                )
                if self.due_date < business_today:
                    return "overdue"
            if self.amount_paid > 0:
                return "partial"
        return self.status

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    def clean(self):
        super().clean()
        if self.contact_id and self.business_id != self.contact.business_id:
            raise ValidationError(
                "Invoice and contact must belong to the same business."
            )
        if (
            self.source_estimate_id
            and self.business_id != self.source_estimate.business_id
        ):
            raise ValidationError(
                "Invoice and source estimate must belong to the same business."
            )
        if self.discount_type == self.AmountType.NONE and self.discount_value != 0:
            raise ValidationError(
                "Discount value must be zero when discount type is None."
            )
        if (
            self.discount_type == self.AmountType.PERCENTAGE
            and self.discount_value > 100
        ):
            raise ValidationError("Discount percentage cannot exceed 100.")
        if self.issue_date and self.due_date and self.due_date < self.issue_date:
            raise ValidationError("Due date cannot be before the issue date.")
        if self.status == self.Status.VOID and not self.void_reason.strip():
            raise ValidationError("Enter a reason for voiding the invoice.")

    def __str__(self):
        return self.number or f"Draft invoice for {self.contact}"


class InvoiceLineItem(BusinessOwnedModel):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="line_items",
    )
    source_catalog_item = models.ForeignKey(
        "catalog.ProductService",
        on_delete=models.PROTECT,
        related_name="invoice_line_items",
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
                fields=("invoice", "position"),
                name="invoices_line_invoice_position_unique",
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
                name="invoices_line_amounts_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.invoice_id and self.business_id != self.invoice.business_id:
            raise ValidationError("Line item and invoice must share a business.")
        if (
            self.source_catalog_item_id
            and self.business_id != self.source_catalog_item.business_id
        ):
            raise ValidationError("Catalog item must belong to the invoice business.")

    def __str__(self):
        return f"{self.position}. {self.name}"

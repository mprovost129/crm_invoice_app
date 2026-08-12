from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.models import BusinessOwnedModel


class Payment(BusinessOwnedModel):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        ONLINE = "online", "Online"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CHECK = "check", "Check"
        ACH = "ach", "ACH"
        CREDIT_CARD = "credit_card", "Credit card"
        VENMO = "venmo", "Venmo"
        PAYPAL = "paypal", "PayPal"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    currency = models.CharField(max_length=3)
    invoice_total_snapshot = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after_snapshot = models.DecimalField(max_digits=14, decimal_places=2)
    paid_on = models.DateField()
    method = models.CharField(max_length=30, choices=Method.choices)
    reference = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
    provider_payment_id = models.CharField(max_length=255, blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_payments",
        blank=True,
        null=True,
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-paid_on", "-posted_at")
        indexes = [
            models.Index(fields=("business", "invoice", "paid_on")),
            models.Index(fields=("business", "paid_on")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("provider_payment_id",),
                condition=models.Q(provider_payment_id__isnull=False),
                name="payments_payment_provider_id_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(amount__gt=0)
                    & models.Q(invoice_total_snapshot__gte=0)
                    & models.Q(balance_after_snapshot__gte=0)
                ),
                name="payments_payment_amount_positive",
            ),
        ]

    @property
    def reversed_amount(self):
        return sum(
            (reversal.amount for reversal in self.reversals.all()),
            start=self.amount * 0,
        )

    @property
    def net_amount(self):
        return self.amount - self.reversed_amount

    @property
    def effective_status(self):
        if self.reversed_amount == self.amount:
            return "reversed"
        if self.reversed_amount > 0:
            return "partially_reversed"
        return "posted"

    def clean(self):
        super().clean()
        if self.invoice_id and self.business_id != self.invoice.business_id:
            raise ValidationError("Payment and invoice must share a business.")
        if self.invoice_id and self.currency != self.invoice.currency:
            raise ValidationError("Payment and invoice currencies must match.")

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Posted payments are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.currency} {self.amount} for {self.invoice}"


class PaymentReversal(BusinessOwnedModel):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="reversals",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    reason = models.TextField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_payment_reversals",
        blank=True,
        null=True,
    )
    reversed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-reversed_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payments_reversal_amount_positive",
            )
        ]

    def clean(self):
        super().clean()
        if self.payment_id and self.business_id != self.payment.business_id:
            raise ValidationError("Reversal and payment must share a business.")
        if not self.reason.strip():
            raise ValidationError("Enter a reversal reason.")

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Payment reversals are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Reversal for {self.payment}"

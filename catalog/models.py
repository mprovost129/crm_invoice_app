from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import BusinessOwnedModel


class ProductServiceQuerySet(models.QuerySet):
    def for_business(self, business):
        if business is None:
            return self.none()
        return self.filter(business=business)

    def active(self):
        return self.filter(is_active=True, archived_at__isnull=True)


class ProductService(BusinessOwnedModel):
    class ItemType(models.TextChoices):
        SERVICE = "service", "Service"
        PRODUCT = "product", "Product"

    class Unit(models.TextChoices):
        EACH = "each", "Each"
        HOUR = "hour", "Hour"
        DAY = "day", "Day"
        SERVICE = "service", "Service"
        SQUARE_FOOT = "square_foot", "Square foot"
        LINEAR_FOOT = "linear_foot", "Linear foot"
        CUSTOM = "custom", "Custom"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    item_type = models.CharField(
        max_length=20,
        choices=ItemType.choices,
        default=ItemType.SERVICE,
    )
    unit = models.CharField(
        max_length=30,
        choices=Unit.choices,
        default=Unit.SERVICE,
    )
    custom_unit = models.CharField(max_length=40, blank=True)
    default_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_taxable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_catalog_items",
        blank=True,
        null=True,
    )

    objects = ProductServiceQuerySet.as_manager()

    class Meta:
        ordering = ("name", "created_at")
        indexes = [models.Index(fields=("business", "is_active", "item_type", "name"))]
        constraints = [
            models.CheckConstraint(
                condition=Q(default_rate__gte=0),
                name="catalog_product_service_rate_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(unit="custom") & ~Q(custom_unit=""))
                    | (~Q(unit="custom") & Q(custom_unit=""))
                ),
                name="catalog_product_service_custom_unit_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(is_active=True, archived_at__isnull=True)
                    | Q(is_active=False, archived_at__isnull=False)
                ),
                name="catalog_product_service_archive_consistent",
            ),
        ]

    @property
    def unit_label(self):
        if self.unit == self.Unit.CUSTOM:
            return self.custom_unit
        return self.get_unit_display()

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.custom_unit = self.custom_unit.strip()
        if self.unit == self.Unit.CUSTOM and not self.custom_unit:
            raise ValidationError({"custom_unit": "Enter the custom unit."})
        if self.unit != self.Unit.CUSTOM and self.custom_unit:
            raise ValidationError(
                {"custom_unit": "Custom unit is only valid when Unit is Custom."}
            )

    def __str__(self):
        return self.name

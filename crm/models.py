from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import BusinessOwnedModel


class ContactQuerySet(models.QuerySet):
    def for_business(self, business):
        if business is None:
            return self.none()
        return self.filter(business=business)

    def active(self):
        return self.exclude(status=Contact.Status.ARCHIVED)

    def leads(self):
        return self.filter(status=Contact.Status.LEAD)

    def clients(self):
        return self.filter(status=Contact.Status.CLIENT)


class Contact(BusinessOwnedModel):
    class Status(models.TextChoices):
        LEAD = "lead", "Lead"
        CLIENT = "client", "Client"
        ARCHIVED = "archived", "Archived"

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    country_code = models.CharField(max_length=2, default="US")
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LEAD,
    )
    status_before_archive = models.CharField(
        max_length=20,
        choices=(
            (Status.LEAD, "Lead"),
            (Status.CLIENT, "Client"),
        ),
        blank=True,
    )
    converted_at = models.DateTimeField(blank=True, null=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_contacts",
        blank=True,
        null=True,
    )

    objects = ContactQuerySet.as_manager()

    class Meta:
        ordering = ("last_name", "first_name", "company_name", "created_at")
        indexes = [
            models.Index(fields=("business", "status", "last_name", "first_name")),
            models.Index(fields=("business", "company_name")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        status="lead",
                        archived_at__isnull=True,
                        status_before_archive="",
                        converted_at__isnull=True,
                    )
                    | Q(
                        status="client",
                        archived_at__isnull=True,
                        status_before_archive="",
                        converted_at__isnull=False,
                    )
                    | Q(
                        status="archived",
                        status_before_archive="lead",
                        archived_at__isnull=False,
                        converted_at__isnull=True,
                    )
                    | Q(
                        status="archived",
                        status_before_archive="client",
                        archived_at__isnull=False,
                        converted_at__isnull=False,
                    )
                ),
                name="crm_contact_lifecycle_consistent",
            )
        ]

    @property
    def display_name(self):
        personal_name = f"{self.first_name} {self.last_name}".strip()
        return personal_name or self.company_name or self.email

    def clean(self):
        super().clean()
        if not any(
            (
                self.first_name.strip(),
                self.last_name.strip(),
                self.company_name.strip(),
            )
        ):
            raise ValidationError("Enter a contact or company name.")

    def __str__(self):
        return self.display_name


class ContactNote(BusinessOwnedModel):
    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="contact_notes",
    )
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_contact_notes",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("business", "contact", "created_at"))]

    def clean(self):
        super().clean()
        if self.contact_id and self.business_id != self.contact.business_id:
            raise ValidationError(
                "The note and contact must belong to the same business."
            )
        if not self.body.strip():
            raise ValidationError({"body": "Enter a note."})

    def __str__(self):
        return f"Note for {self.contact}"

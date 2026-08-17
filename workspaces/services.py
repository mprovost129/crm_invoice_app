from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from core.models import DocumentSequence

from .models import Business, BusinessSettings, Membership


def _active_owner_membership(actor, *, workspace_id=None, lock=False):
    memberships = Membership.objects.filter(
        user=actor,
        role=Membership.Role.OWNER,
        status=Membership.Status.ACTIVE,
        workspace__status="active",
    ).select_related("workspace")
    if workspace_id is not None:
        memberships = memberships.filter(workspace_id=workspace_id)
    if lock:
        memberships = memberships.select_for_update()
    membership = memberships.order_by("created_at").first()
    if membership is None:
        raise PermissionDenied("An active owner workspace is required.")
    return membership


@transaction.atomic
def complete_business_onboarding(*, actor, data):
    if not actor.is_email_verified:
        raise PermissionDenied("Email verification is required.")

    membership = _active_owner_membership(actor, lock=True)
    if Business.objects.filter(workspace=membership.workspace).active().exists():
        raise ValidationError("This workspace already has an active business.")

    business_fields = {
        field: data[field]
        for field in (
            "legal_name",
            "display_name",
            "owner_name",
            "email",
            "phone",
            "website",
            "logo",
            "address_line_1",
            "address_line_2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "default_currency",
            "timezone",
        )
        if field in data
    }
    business = Business(workspace=membership.workspace, **business_fields)
    business.full_clean()
    business.save()

    settings = BusinessSettings(
        business=business,
        estimate_prefix=data["estimate_prefix"],
        invoice_prefix=data["invoice_prefix"],
        default_payment_terms_days=data["default_payment_terms_days"],
        default_estimate_expiration_days=(data["default_estimate_expiration_days"]),
        default_tax_rate=data["default_tax_rate"],
        default_invoice_notes=data["default_invoice_notes"],
        default_invoice_terms=data["default_invoice_terms"],
        default_estimate_notes=data["default_estimate_notes"],
        default_estimate_terms=data["default_estimate_terms"],
    )
    settings.full_clean()
    settings.save()

    for document_type, prefix, next_value in (
        (
            DocumentSequence.DocumentType.ESTIMATE,
            data["estimate_prefix"],
            data["estimate_starting_number"],
        ),
        (
            DocumentSequence.DocumentType.INVOICE,
            data["invoice_prefix"],
            data["invoice_starting_number"],
        ),
    ):
        sequence = DocumentSequence(
            business=business,
            document_type=document_type,
            prefix=prefix,
            next_value=next_value,
        )
        sequence.full_clean()
        sequence.save()

    return business


@transaction.atomic
def update_business_configuration(*, actor, business_id, profile_data, defaults_data):
    business = (
        Business.objects.select_for_update()
        .filter(
            pk=business_id,
            is_active=True,
            archived_at__isnull=True,
            workspace__status="active",
            workspace__memberships__user=actor,
            workspace__memberships__status=Membership.Status.ACTIVE,
        )
        .first()
    )
    if business is None:
        raise PermissionDenied("Business access is required.")
    _active_owner_membership(
        actor,
        workspace_id=business.workspace_id,
        lock=True,
    )

    for field, value in profile_data.items():
        if field == "logo" and value is False:
            value = ""
        setattr(business, field, value)
    business.full_clean()
    business.save()

    settings = BusinessSettings.objects.select_for_update().get(business=business)
    for field in (
        "estimate_prefix",
        "invoice_prefix",
        "default_payment_terms_days",
        "default_estimate_expiration_days",
        "default_tax_rate",
        "default_invoice_notes",
        "default_invoice_terms",
        "default_estimate_notes",
        "default_estimate_terms",
    ):
        setattr(settings, field, defaults_data[field])
    settings.full_clean()
    settings.save()

    sequence_updates = {
        DocumentSequence.DocumentType.ESTIMATE: (
            defaults_data["estimate_prefix"],
            defaults_data["estimate_starting_number"],
        ),
        DocumentSequence.DocumentType.INVOICE: (
            defaults_data["invoice_prefix"],
            defaults_data["invoice_starting_number"],
        ),
    }
    sequences = {
        sequence.document_type: sequence
        for sequence in DocumentSequence.objects.select_for_update().filter(
            business=business
        )
    }
    if set(sequences) != set(sequence_updates):
        raise ValidationError("Business document sequences are incomplete.")
    for sequence in sequences.values():
        sequence.prefix, sequence.next_value = sequence_updates[sequence.document_type]
        sequence.full_clean()
        sequence.save()

    return business

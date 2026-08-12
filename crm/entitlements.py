def enforce_contact_creation_allowed(*, business):
    from billing.entitlements import entitlements_for_business

    from .models import Contact

    entitlements = entitlements_for_business(business=business)
    limit = entitlements.plan.active_contact_limit
    if limit is not None and Contact.objects.for_business(business).active().count() >= limit:
        from django.core.exceptions import ValidationError

        raise ValidationError(
            f"The {entitlements.plan.name} plan allows {limit} active contacts. Archive a contact or change plans."
        )

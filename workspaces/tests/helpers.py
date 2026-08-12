from django.utils import timezone

from billing.models import Plan, Subscription
from core.models import DocumentSequence
from users.models import User
from workspaces.models import Business, BusinessSettings, Membership, Workspace

PASSWORD = "Truly-Safe-Phase1-Password-472!"

BUSINESS_DATA = {
    "legal_name": "Provost Home Design LLC",
    "display_name": "Provost Home Design",
    "owner_name": "Morgan Provost",
    "email": "billing@example.com",
    "phone": "555-0100",
    "website": "https://example.com",
    "address_line_1": "100 Main Street",
    "address_line_2": "",
    "city": "Boston",
    "region": "MA",
    "postal_code": "02108",
    "country_code": "US",
    "default_currency": "USD",
    "timezone": "America/New_York",
    "estimate_prefix": "EST-",
    "estimate_starting_number": 1001,
    "invoice_prefix": "INV-",
    "invoice_starting_number": 2001,
    "default_payment_terms_days": 30,
    "default_estimate_expiration_days": 14,
    "default_tax_rate": "6.2500",
    "default_invoice_notes": "Thank you.",
    "default_invoice_terms": "Due in 30 days.",
    "default_estimate_notes": "Prepared for you.",
    "default_estimate_terms": "Valid for 14 days.",
}


def create_owner_tenancy(email="owner@example.com", *, verified=True):
    user = User.objects.create_user(email, PASSWORD, first_name="Morgan")
    if verified:
        user.email_verified_at = timezone.now()
        user.save(update_fields=("email_verified_at",))
    workspace = Workspace.objects.create(
        name=f"{email} Workspace",
        slug=f"workspace-{user.pk.hex[:12]}",
        owner_user=user,
    )
    membership = Membership.objects.create(
        workspace=workspace,
        user=user,
        role=Membership.Role.OWNER,
        status=Membership.Status.ACTIVE,
        accepted_at=timezone.now(),
    )
    plan, _ = Plan.objects.get_or_create(
        code="starter",
        defaults={
            "name": "Starter",
            "active_contact_limit": 1000,
            "monthly_estimate_limit": 1000,
            "monthly_invoice_limit": 1000,
            "allow_online_payments": True,
            "allow_custom_branding": True,
            "allow_reminders": True,
            "allow_reporting": True,
            "allow_exports": True,
        },
    )
    Subscription.objects.create(workspace=workspace, plan=plan)
    return user, workspace, membership


def create_business(workspace, **overrides):
    fields = {
        key: value
        for key, value in BUSINESS_DATA.items()
        if key
        in {
            "legal_name",
            "display_name",
            "owner_name",
            "email",
            "phone",
            "website",
            "address_line_1",
            "address_line_2",
            "city",
            "region",
            "postal_code",
            "country_code",
            "default_currency",
            "timezone",
        }
    }
    fields.update(overrides)
    business = Business.objects.create(workspace=workspace, **fields)
    BusinessSettings.objects.create(
        business=business,
        estimate_prefix="EST-",
        invoice_prefix="INV-",
    )
    DocumentSequence.objects.create(
        business=business,
        document_type=DocumentSequence.DocumentType.ESTIMATE,
        prefix="EST-",
    )
    DocumentSequence.objects.create(
        business=business,
        document_type=DocumentSequence.DocumentType.INVOICE,
        prefix="INV-",
    )
    return business

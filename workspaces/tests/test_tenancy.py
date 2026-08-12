import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.urls import reverse

from core.models import DocumentSequence
from users.models import User
from workspaces.models import Business, BusinessSettings, Membership
from workspaces.selectors import business_for_user
from workspaces.services import (
    complete_business_onboarding,
    update_business_configuration,
)

from .helpers import BUSINESS_DATA, PASSWORD, create_business, create_owner_tenancy


@pytest.mark.django_db
def test_onboarding_service_creates_business_defaults_and_sequences():
    user, workspace, _ = create_owner_tenancy()

    business = complete_business_onboarding(actor=user, data=BUSINESS_DATA)

    assert business.workspace == workspace
    settings = BusinessSettings.objects.get(business=business)
    assert settings.default_payment_terms_days == 30
    assert settings.default_tax_rate == 6.25
    sequences = {
        sequence.document_type: sequence
        for sequence in DocumentSequence.objects.filter(business=business)
    }
    assert sequences[DocumentSequence.DocumentType.ESTIMATE].next_value == 1001
    assert sequences[DocumentSequence.DocumentType.INVOICE].next_value == 2001


@pytest.mark.django_db
def test_onboarding_rejects_unverified_user():
    user, _, _ = create_owner_tenancy(verified=False)

    with pytest.raises(PermissionDenied):
        complete_business_onboarding(actor=user, data=BUSINESS_DATA)

    assert Business.objects.count() == 0


@pytest.mark.django_db
def test_workspace_cannot_have_two_active_businesses():
    user, workspace, _ = create_owner_tenancy()
    create_business(workspace)

    with pytest.raises(IntegrityError), transaction.atomic():
        Business.objects.create(
            workspace=workspace,
            legal_name="Second LLC",
            display_name="Second",
            owner_name=user.display_name,
            email="second@example.com",
            address_line_1="2 Main Street",
            city="Boston",
            region="MA",
            postal_code="02108",
        )


@pytest.mark.django_db
def test_workspace_cannot_have_two_active_owners():
    _, workspace, _ = create_owner_tenancy()
    second_user = User.objects.create_user("second@example.com", PASSWORD)

    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(
            workspace=workspace,
            user=second_user,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )


@pytest.mark.django_db
def test_business_selector_blocks_cross_tenant_access():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    first_business = create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )

    assert business_for_user(first_user, first_business.pk) == first_business
    assert business_for_user(first_user, second_business.pk) is None
    assert Business.objects.for_user(second_user).get() == second_business


@pytest.mark.django_db
def test_settings_service_blocks_cross_tenant_update():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    _, second_workspace, _ = create_owner_tenancy("second@example.com")
    create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    profile_data = {
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

    with pytest.raises(PermissionDenied):
        update_business_configuration(
            actor=first_user,
            business_id=second_business.pk,
            profile_data=profile_data,
            defaults_data=BUSINESS_DATA,
        )

    second_business.refresh_from_db()
    assert second_business.display_name == "Second Business"


@pytest.mark.django_db
def test_onboarding_view_reaches_tenant_safe_dashboard(client):
    user, _, _ = create_owner_tenancy()
    client.force_login(user)

    response = client.post(reverse("workspaces:onboarding"), BUSINESS_DATA)

    assert response.status_code == 302
    assert response.url == reverse("workspaces:dashboard")
    dashboard = client.get(response.url)
    assert dashboard.status_code == 200
    assert b"Provost Home Design" in dashboard.content
    assert b"tenant-safe workspace is ready" in dashboard.content


@pytest.mark.django_db
def test_dashboard_gates_anonymous_unverified_and_unonboarded_users(client):
    response = client.get(reverse("workspaces:dashboard"))
    assert response.status_code == 302
    assert reverse("users:login") in response.url

    unverified, _, _ = create_owner_tenancy("unverified@example.com", verified=False)
    client.force_login(unverified)
    response = client.get(reverse("workspaces:dashboard"))
    assert response.url == reverse("users:verification-sent")

    verified, _, _ = create_owner_tenancy("verified@example.com")
    client.force_login(verified)
    response = client.get(reverse("workspaces:dashboard"))
    assert response.url == reverse("workspaces:onboarding")


@pytest.mark.django_db
def test_tenant_middleware_keeps_membership_and_business_in_same_workspace(client):
    user, first_workspace, first_membership = create_owner_tenancy()
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    Membership.objects.filter(user=second_user).delete()
    Membership.objects.create(
        user=user,
        workspace=second_workspace,
        role=Membership.Role.MEMBER,
        status=Membership.Status.ACTIVE,
    )
    client.force_login(user)

    response = client.get(reverse("workspaces:dashboard"))

    assert response.status_code == 302
    assert response.url == reverse("workspaces:onboarding")
    assert first_membership.workspace == first_workspace
    assert second_business.workspace == second_workspace


@pytest.mark.django_db
def test_business_settings_update_profile_defaults_and_sequences(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    client.force_login(user)
    post_data = {
        **{
            f"profile-{key}": value
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
        },
        **{
            f"defaults-{key}": value
            for key, value in BUSINESS_DATA.items()
            if key
            in {
                "estimate_prefix",
                "estimate_starting_number",
                "invoice_prefix",
                "invoice_starting_number",
                "default_payment_terms_days",
                "default_estimate_expiration_days",
                "default_tax_rate",
                "default_invoice_notes",
                "default_invoice_terms",
                "default_estimate_notes",
                "default_estimate_terms",
            }
        },
    }
    post_data["profile-display_name"] = "Updated Design Co"
    post_data["defaults-estimate_prefix"] = "QUOTE-"
    post_data["defaults-invoice_starting_number"] = 9001

    response = client.post(reverse("workspaces:settings"), post_data)

    assert response.status_code == 302
    business.refresh_from_db()
    business.settings.refresh_from_db()
    assert business.display_name == "Updated Design Co"
    assert business.settings.estimate_prefix == "QUOTE-"
    invoice_sequence = DocumentSequence.objects.get(
        business=business,
        document_type=DocumentSequence.DocumentType.INVOICE,
    )
    assert invoice_sequence.next_value == 9001


@pytest.mark.django_db
def test_non_owner_cannot_open_business_settings(client):
    owner, workspace, owner_membership = create_owner_tenancy()
    create_business(workspace)
    member = User.objects.create_user("member@example.com", PASSWORD)
    member.email_verified_at = owner.email_verified_at
    member.save(update_fields=("email_verified_at",))
    Membership.objects.create(
        workspace=workspace,
        user=member,
        role=Membership.Role.MEMBER,
        status=Membership.Status.ACTIVE,
    )
    client.force_login(member)

    response = client.get(reverse("workspaces:settings"))

    assert response.status_code == 403
    assert owner_membership.role == Membership.Role.OWNER

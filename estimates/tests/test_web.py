import pytest
from django.urls import reverse

from communications.models import EmailDelivery
from crm.services import create_contact
from crm.tests.helpers import CONTACT_DATA
from estimates.models import Estimate
from workspaces.tests.helpers import create_business, create_owner_tenancy

from .helpers import (
    ESTIMATE_DATA,
    LINE_DATA,
    create_estimate_fixture,
    create_issued_estimate,
)


@pytest.mark.django_db
def test_owner_can_create_add_line_issue_and_download_pdf(client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    contact = create_contact(actor=user, business_id=business.pk, data=CONTACT_DATA)
    client.force_login(user)

    create_response = client.post(
        reverse("estimates:create"),
        {
            **ESTIMATE_DATA,
            "expiration_date": "",
            "contact": contact.pk,
            "requires_acceptance": "on",
        },
    )
    assert create_response.status_code == 302
    estimate = Estimate.objects.get(business=business)

    line_form_data = {
        key: value
        for key, value in LINE_DATA.items()
        if key != "source_catalog_item_id"
    }
    line_response = client.post(
        reverse("estimates:line-create", args=(estimate.pk,)),
        {
            **line_form_data,
            "source_catalog_item": "",
        },
    )
    assert line_response.status_code == 302
    issue_response = client.post(reverse("estimates:issue", args=(estimate.pk,)))
    assert issue_response.status_code == 302
    estimate.refresh_from_db()
    assert estimate.status == Estimate.Status.SENT

    pdf_response = client.get(reverse("estimates:pdf", args=(estimate.pk,)))
    assert pdf_response.status_code == 200
    assert pdf_response.headers["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_owner_estimate_pages_return_404_for_foreign_estimate(client):
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    foreign_estimate, foreign_line, _ = create_estimate_fixture(
        user=second_user, business=second_business
    )
    client.force_login(first_user)

    assert (
        client.get(reverse("estimates:detail", args=(foreign_estimate.pk,))).status_code
        == 404
    )
    assert (
        client.post(reverse("estimates:issue", args=(foreign_estimate.pk,))).status_code
        == 404
    )
    assert (
        client.post(
            reverse(
                "estimates:line-delete",
                args=(foreign_estimate.pk, foreign_line.pk),
            )
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_issued_estimate_detail_uses_historical_contact_snapshot(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, contact = create_issued_estimate(user=user, business=business)
    contact.company_name = "Changed after issue"
    contact.email = "changed@example.com"
    contact.save(update_fields=("company_name", "email", "updated_at"))
    client.force_login(user)

    response = client.get(reverse("estimates:detail", args=(estimate.pk,)))

    assert response.status_code == 200
    assert b"Taylor Renovations" in response.content
    assert b"jordan@example.com" in response.content
    assert b"Changed after issue" not in response.content


@pytest.mark.django_db
def test_issued_estimate_detail_surfaces_acceptance_dialog_and_delivery_failure(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    EmailDelivery.objects.create(
        business=business,
        estimate=estimate,
        kind=EmailDelivery.Kind.ESTIMATE,
        recipient="customer@example.com",
        subject="Estimate delivery",
        status=EmailDelivery.Status.FAILED,
        failure_message="Mailbox unavailable",
    )
    client.force_login(user)

    response = client.get(reverse("estimates:detail", args=(estimate.pk,)))

    assert response.status_code == 200
    assert b"Mark estimate" in response.content
    assert b"immutable evidence" in response.content
    assert b"Mailbox unavailable" in response.content


@pytest.mark.django_db
def test_invalid_manual_acceptance_reopens_dialog_with_bound_errors(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    estimate, _, _ = create_issued_estimate(user=user, business=business)
    client.force_login(user)

    response = client.post(
        reverse("estimates:manual-acceptance", args=(estimate.pk,)),
        {
            "method": "unsupported",
            "accepted_by_name": "Jordan Taylor",
            "evidence_note": "Customer called.",
        },
    )

    assert response.status_code == 200
    assert b'data-auto-show-modal="manualAcceptanceModal"' in response.content
    assert b"Select a valid choice" in response.content
    assert b"Jordan Taylor" in response.content

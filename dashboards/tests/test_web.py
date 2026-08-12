import pytest
from django.urls import reverse

from communications.models import EmailDelivery, Notification
from estimates.tests.helpers import create_issued_estimate
from workspaces.tests.helpers import create_business, create_owner_tenancy


@pytest.mark.django_db
def test_owner_can_view_dashboard_reports_and_delivery_filters(client):
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
        failure_message="Provider unavailable",
    )
    client.force_login(user)

    dashboard = client.get(reverse("workspaces:dashboard"))
    reports = client.get(reverse("dashboards:reports"))
    deliveries = client.get(
        reverse("dashboards:communications"),
        {"status": "failed", "q": estimate.number},
    )

    assert dashboard.status_code == reports.status_code == deliveries.status_code == 200
    assert b"Paid this month" in dashboard.content
    assert b"Accounts receivable" in reports.content
    assert b"Provider unavailable" in deliveries.content


@pytest.mark.django_db
def test_notification_read_route_rejects_foreign_tenant(client):
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second",
        email="second-business@example.com",
    )
    notification = Notification.objects.create(
        business=second_business,
        recipient=second_user,
        kind=Notification.Kind.PAYMENT_RECEIVED,
        title="Foreign notification",
        body="Do not expose this.",
        dedupe_key="foreign",
    )
    client.force_login(first_user)

    response = client.post(
        reverse("dashboards:notification-read", args=(notification.pk,))
    )

    assert response.status_code == 404
    notification.refresh_from_db()
    assert notification.read_at is None

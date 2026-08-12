import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from billing.entitlements import Feature, entitlements_for_business
from billing.models import Plan, PlatformWebhookEvent, Subscription
from billing.services import process_platform_webhook, store_platform_webhook
from workspaces.tests.helpers import create_business, create_owner_tenancy


@pytest.mark.django_db
def test_seeded_plans_and_subscription_entitlements_are_configurable():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    subscription = Subscription.objects.get(workspace=workspace)

    assert subscription.plan.code == "starter"
    assert entitlements_for_business(business=business).allows(Feature.EXPORTS)

    free = Plan.objects.get(code="free")
    subscription.plan = free
    subscription.save(update_fields=("plan", "updated_at"))
    assert not entitlements_for_business(business=business).allows(
        Feature.ONLINE_PAYMENTS
    )


@pytest.mark.django_db
def test_free_plan_denies_reports_on_the_backend(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    subscription = Subscription.objects.get(workspace=workspace)
    subscription.plan = Plan.objects.get(code="free")
    subscription.save(update_fields=("plan", "updated_at"))
    client.force_login(user)

    response = client.get(reverse("dashboards:reports"))

    assert response.status_code == 403
    assert business.workspace_id == workspace.pk


@pytest.mark.django_db
def test_platform_subscription_webhook_sync_is_idempotent_and_separate():
    _, workspace, _ = create_owner_tenancy()
    plan = Plan.objects.get(code="starter")
    plan.provider_monthly_price_id = "price_starter_monthly"
    plan.save(update_fields=("provider_monthly_price_id", "updated_at"))
    payload = {
        "id": "evt_platform_subscription_1",
        "type": "customer.subscription.updated",
        "livemode": False,
        "data": {
            "object": {
                "id": "sub_123",
                "object": "subscription",
                "customer": "cus_123",
                "status": "active",
                "cancel_at_period_end": False,
                "current_period_end": 1798761600,
                "metadata": {
                    "workspace_id": str(workspace.pk),
                    "plan_code": "starter",
                },
                "items": {
                    "data": [
                        {
                            "price": {
                                "id": "price_starter_monthly",
                                "recurring": {"interval": "month"},
                            }
                        }
                    ]
                },
            }
        },
    }

    event, created = store_platform_webhook(payload=payload)
    assert created
    process_platform_webhook(event_id=event.pk)
    process_platform_webhook(event_id=event.pk)

    subscription = Subscription.objects.get(workspace=workspace)
    event.refresh_from_db()
    assert subscription.provider_customer_id == "cus_123"
    assert subscription.provider_subscription_id == "sub_123"
    assert subscription.billing_interval == Subscription.Interval.MONTH
    assert event.status == PlatformWebhookEvent.Status.COMPLETED
    assert event.attempts == 1


@pytest.mark.django_db
def test_unmatched_platform_webhook_is_retained_as_failed():
    payload = {
        "id": "evt_platform_bad_1",
        "type": "customer.subscription.updated",
        "livemode": False,
        "data": {
            "object": {
                "id": "sub_missing",
                "object": "subscription",
                "status": "active",
                "metadata": {"workspace_id": "00000000-0000-0000-0000-000000000000"},
                "items": {"data": []},
            }
        },
    }
    event, _ = store_platform_webhook(payload=payload)

    with pytest.raises(ValidationError):
        process_platform_webhook(event_id=event.pk)

    event.refresh_from_db()
    assert event.status == PlatformWebhookEvent.Status.FAILED
    assert "workspace" in event.last_error


@pytest.mark.django_db
def test_platform_webhook_rejects_wrong_environment_mode(settings):
    settings.STRIPE_LIVE_MODE = True
    payload = {
        "id": "evt_test_in_live_environment",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {"object": {}},
    }

    with pytest.raises(ValueError, match="mode"):
        store_platform_webhook(payload=payload)

    assert not PlatformWebhookEvent.objects.exists()

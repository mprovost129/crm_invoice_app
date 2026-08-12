from datetime import UTC, datetime

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from workspaces.models import Membership, Workspace

from .models import Plan, PlatformWebhookEvent, Subscription
from .stripe_gateway import create_subscription_checkout


def create_default_subscription(*, workspace):
    plan = Plan.objects.filter(code="free", is_active=True).first()
    if plan is None:
        raise ValidationError("No default plan is configured.")
    subscription, _ = Subscription.objects.get_or_create(
        workspace=workspace,
        defaults={
            "plan": plan,
            "status": Subscription.Status.ACTIVE,
            "billing_interval": Subscription.Interval.NONE,
        },
    )
    return subscription


def _owner_workspace(*, actor):
    workspace = (
        Workspace.objects.filter(
            owner_user=actor,
            status=Workspace.Status.ACTIVE,
            memberships__user=actor,
            memberships__role=Membership.Role.OWNER,
            memberships__status=Membership.Status.ACTIVE,
        )
        .distinct()
        .first()
    )
    if workspace is None:
        raise PermissionDenied("An active owner workspace is required.")
    return workspace


def start_subscription_checkout(
    *, actor, plan_code, interval, success_url, cancel_url
):
    workspace = _owner_workspace(actor=actor)
    plan = Plan.objects.filter(code=plan_code, is_active=True).first()
    if plan is None or plan.is_free:
        raise ValidationError("Select an active paid plan.")
    if interval not in {Subscription.Interval.MONTH, Subscription.Interval.YEAR}:
        raise ValidationError("Select monthly or annual billing.")
    return create_subscription_checkout(
        workspace=workspace,
        plan=plan,
        interval=interval,
        success_url=success_url,
        cancel_url=cancel_url,
        idempotency_key=f"subscription-checkout:{workspace.pk}:{plan.pk}:{interval}",
    )


def store_platform_webhook(*, payload):
    if bool(payload.get("livemode", False)) != settings.STRIPE_LIVE_MODE:
        raise ValueError("Stripe event mode does not match this environment.")
    event, created = PlatformWebhookEvent.objects.get_or_create(
        provider_event_id=payload["id"],
        defaults={
            "event_type": payload["type"],
            "livemode": bool(payload.get("livemode", False)),
            "payload": payload,
            "signature_verified_at": timezone.now(),
        },
    )
    return event, created


def _as_datetime(value):
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value), tz=UTC)


def _plan_for_subscription_object(data):
    metadata = data.get("metadata") or {}
    if metadata.get("plan_code"):
        plan = Plan.objects.filter(code=metadata["plan_code"]).first()
        if plan:
            return plan
    items = ((data.get("items") or {}).get("data") or [])
    price_id = ((items[0].get("price") or {}).get("id")) if items else None
    return Plan.objects.filter(
        models.Q(provider_monthly_price_id=price_id)
        | models.Q(provider_annual_price_id=price_id)
    ).first()


def _sync_subscription(data, *, deleted=False):
    metadata = data.get("metadata") or {}
    workspace_id = metadata.get("workspace_id")
    provider_id = data.get("id")
    subscription = (
        Subscription.objects.select_for_update()
        .filter(provider_subscription_id=provider_id)
        .first()
    )
    if subscription is None and workspace_id:
        subscription = (
            Subscription.objects.select_for_update()
            .filter(workspace_id=workspace_id)
            .first()
        )
    if subscription is None:
        raise ValidationError("Subscription webhook cannot be matched to a workspace.")
    plan = _plan_for_subscription_object(data)
    if plan is None:
        raise ValidationError("Subscription webhook references an unknown plan.")
    items = ((data.get("items") or {}).get("data") or [])
    interval = (
        (((items[0].get("price") or {}).get("recurring") or {}).get("interval"))
        if items
        else None
    )
    status = Subscription.Status.CANCELED if deleted else data.get("status")
    if status not in Subscription.Status.values:
        status = Subscription.Status.INCOMPLETE
    subscription.plan = plan
    subscription.status = status
    subscription.billing_interval = (
        interval if interval in Subscription.Interval.values else Subscription.Interval.NONE
    )
    subscription.provider_customer_id = data.get("customer") or None
    subscription.provider_subscription_id = provider_id
    subscription.current_period_end = _as_datetime(data.get("current_period_end"))
    subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
    subscription.provider_synced_at = timezone.now()
    subscription.save()


def _sync_checkout(data):
    if data.get("mode") != "subscription":
        return False
    workspace_id = data.get("client_reference_id") or (data.get("metadata") or {}).get(
        "workspace_id"
    )
    subscription = Subscription.objects.select_for_update().filter(
        workspace_id=workspace_id
    ).first()
    if subscription is None:
        raise ValidationError("Checkout webhook cannot be matched to a workspace.")
    subscription.provider_customer_id = data.get("customer") or None
    subscription.provider_subscription_id = data.get("subscription") or None
    subscription.provider_synced_at = timezone.now()
    subscription.save(
        update_fields=(
            "provider_customer_id",
            "provider_subscription_id",
            "provider_synced_at",
            "updated_at",
        )
    )
    return True


def process_platform_webhook(*, event_id):
    try:
        with transaction.atomic():
            event = PlatformWebhookEvent.objects.select_for_update().get(pk=event_id)
            if event.status in {
                PlatformWebhookEvent.Status.COMPLETED,
                PlatformWebhookEvent.Status.IGNORED,
            }:
                return event
            event.status = PlatformWebhookEvent.Status.PROCESSING
            event.attempts += 1
            event.last_error = ""
            event.save(
                update_fields=("status", "attempts", "last_error", "updated_at")
            )
            data = event.payload["data"]["object"]
            if event.event_type in {
                "customer.subscription.created",
                "customer.subscription.updated",
            }:
                _sync_subscription(data)
                status = PlatformWebhookEvent.Status.COMPLETED
            elif event.event_type == "customer.subscription.deleted":
                _sync_subscription(data, deleted=True)
                status = PlatformWebhookEvent.Status.COMPLETED
            elif (
                event.event_type == "checkout.session.completed"
                and _sync_checkout(data)
            ):
                status = PlatformWebhookEvent.Status.COMPLETED
            else:
                status = PlatformWebhookEvent.Status.IGNORED
            event.status = status
            event.processed_at = timezone.now()
            event.save(update_fields=("status", "processed_at", "updated_at"))
            return event
    except Exception as exc:
        PlatformWebhookEvent.objects.filter(pk=event_id).update(
            status=PlatformWebhookEvent.Status.FAILED,
            last_error=str(exc)[:500],
        )
        raise

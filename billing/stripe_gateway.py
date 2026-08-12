from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _stripe():
    try:
        import stripe
    except ImportError as exc:
        raise ImproperlyConfigured(
            "Stripe support requires the pinned stripe package."
        ) from exc
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _require(value, setting_name):
    if not value:
        raise ImproperlyConfigured(f"{setting_name} must be configured.")
    return value


def verify_webhook(*, payload, signature, endpoint_secret):
    stripe = _stripe()
    secret = _require(endpoint_secret, "Stripe webhook endpoint secret")
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except Exception as exc:
        raise ValueError("Invalid Stripe webhook signature or payload.") from exc
    if hasattr(event, "to_dict_recursive"):
        return event.to_dict_recursive()
    return dict(event)


@dataclass(frozen=True)
class CheckoutResult:
    session_id: str
    url: str


def create_subscription_checkout(
    *, workspace, plan, interval, success_url, cancel_url, idempotency_key
):
    stripe = _stripe()
    _require(settings.STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
    price_id = (
        plan.provider_monthly_price_id
        if interval == "month"
        else plan.provider_annual_price_id
    )
    _require(price_id, f"Stripe {interval} price for plan {plan.code}")
    subscription = getattr(workspace, "subscription", None)
    customer_id = getattr(subscription, "provider_customer_id", None)
    customer_args = (
        {"customer": customer_id}
        if customer_id
        else {"customer_email": workspace.owner_user.email}
    )
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(workspace.pk),
        metadata={"workspace_id": str(workspace.pk), "plan_code": plan.code},
        subscription_data={
            "metadata": {"workspace_id": str(workspace.pk), "plan_code": plan.code}
        },
        allow_promotion_codes=True,
        **customer_args,
        idempotency_key=idempotency_key,
    )
    return CheckoutResult(session_id=session.id, url=session.url)


def retrieve_subscription(*, provider_subscription_id):
    stripe = _stripe()
    _require(settings.STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
    subscription = stripe.Subscription.retrieve(provider_subscription_id)
    if hasattr(subscription, "to_dict_recursive"):
        return subscription.to_dict_recursive()
    return dict(subscription)

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone


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


def _dict(value):
    if hasattr(value, "to_dict_recursive"):
        return value.to_dict_recursive()
    return dict(value)


def verify_webhook(*, payload, signature, endpoint_secret):
    stripe = _stripe()
    secret = _require(endpoint_secret, "Stripe Connect webhook endpoint secret")
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except Exception as exc:
        raise ValueError("Invalid Stripe webhook signature or payload.") from exc
    return _dict(event)


def create_express_account(*, business, idempotency_key):
    stripe = _stripe()
    _require(settings.STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
    account = stripe.Account.create(
        type="express",
        country=business.country_code,
        email=business.email,
        business_profile={"name": business.display_name},
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        metadata={"business_id": str(business.pk)},
        idempotency_key=idempotency_key,
    )
    return _dict(account)


def retrieve_account(*, provider_account_id):
    stripe = _stripe()
    _require(settings.STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
    return _dict(stripe.Account.retrieve(provider_account_id))


def create_onboarding_link(*, provider_account_id, refresh_url, return_url):
    stripe = _stripe()
    _require(settings.STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
    link = stripe.AccountLink.create(
        account=provider_account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return link.url


@dataclass(frozen=True)
class InvoiceCheckoutResult:
    session_id: str
    url: str
    expires_at: object


def to_minor_units(*, amount, currency):
    if currency.upper() not in {"USD", "CAD", "EUR", "GBP", "AUD"}:
        raise ValueError(f"Unsupported payment currency: {currency}")
    decimal_amount = Decimal(amount)
    minor = decimal_amount * 100
    if minor != minor.to_integral_value():
        raise ValueError("Payment amount has more precision than the currency supports.")
    return int(minor)


def create_invoice_checkout(
    *, attempt, connected_account, customer_email, success_url, cancel_url
):
    stripe = _stripe()
    _require(settings.STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
    metadata = {
        "business_id": str(attempt.business_id),
        "invoice_id": str(attempt.invoice_id),
        "payment_attempt_id": str(attempt.pk),
    }
    expires_at = timezone.now() + timedelta(minutes=30)
    session = stripe.checkout.Session.create(
        stripe_account=connected_account.provider_account_id,
        mode="payment",
        payment_method_types=["card"],
        customer_email=customer_email or None,
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": attempt.currency.lower(),
                    "unit_amount": to_minor_units(
                        amount=attempt.amount, currency=attempt.currency
                    ),
                    "product_data": {
                        "name": f"Invoice {attempt.invoice.number}",
                        "description": f"Payment to {attempt.business.display_name}",
                    },
                },
            }
        ],
        metadata=metadata,
        payment_intent_data={"metadata": metadata},
        success_url=success_url,
        cancel_url=cancel_url,
        expires_at=int(expires_at.timestamp()),
        idempotency_key=attempt.idempotency_key,
    )
    return InvoiceCheckoutResult(
        session_id=session.id,
        url=session.url,
        expires_at=expires_at,
    )


def retrieve_invoice_checkout(*, provider_checkout_session_id, provider_account_id):
    stripe = _stripe()
    _require(settings.STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY")
    session = stripe.checkout.Session.retrieve(
        provider_checkout_session_id,
        stripe_account=provider_account_id,
    )
    return _dict(session)

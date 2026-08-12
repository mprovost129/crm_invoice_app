from dataclasses import dataclass

from django.core.exceptions import ValidationError

from .models import Plan, Subscription


class Feature:
    ONLINE_PAYMENTS = "online_payments"
    CUSTOM_BRANDING = "custom_branding"
    REMINDERS = "reminders"
    REPORTING = "reporting"
    EXPORTS = "exports"


FEATURE_FIELDS = {
    Feature.ONLINE_PAYMENTS: "allow_online_payments",
    Feature.CUSTOM_BRANDING: "allow_custom_branding",
    Feature.REMINDERS: "allow_reminders",
    Feature.REPORTING: "allow_reporting",
    Feature.EXPORTS: "allow_exports",
}


@dataclass(frozen=True)
class Entitlements:
    plan: Plan
    subscription: Subscription | None

    def allows(self, feature):
        field = FEATURE_FIELDS.get(feature)
        if field is None:
            raise ValueError(f"Unknown entitlement feature: {feature}")
        if self.subscription is not None and not self.subscription.grants_access:
            return False
        return bool(getattr(self.plan, field))


def entitlements_for_business(*, business):
    subscription = (
        Subscription.objects.select_related("plan")
        .filter(workspace=business.workspace)
        .first()
    )
    if subscription is not None and subscription.grants_access:
        return Entitlements(plan=subscription.plan, subscription=subscription)
    plan = Plan.objects.filter(code="free", is_active=True).first()
    if plan is None:
        raise ValidationError("No default plan is configured.")
    return Entitlements(plan=plan, subscription=subscription)


def require_feature(*, business, feature):
    entitlements = entitlements_for_business(business=business)
    if not entitlements.allows(feature):
        raise ValidationError(
            f"Your {entitlements.plan.name} plan does not include this feature."
        )
    return entitlements

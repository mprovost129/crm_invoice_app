import json

from django.core.management.base import BaseCommand, CommandError

from billing.models import Subscription
from billing.stripe_gateway import retrieve_subscription


class Command(BaseCommand):
    help = "Reconcile paid local SaaS subscriptions with Stripe Billing identifiers."

    def add_arguments(self, parser):
        parser.add_argument("--provider", action="store_true")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        issues = []
        checked = 0
        subscriptions = Subscription.objects.select_related("plan")
        for subscription in subscriptions.iterator():
            if subscription.plan.is_free:
                continue
            checked += 1
            if (
                not subscription.provider_customer_id
                or not subscription.provider_subscription_id
            ):
                issues.append(
                    {
                        "subscription_id": str(subscription.pk),
                        "code": "missing_provider_identifiers",
                    }
                )
                continue
            if not options["provider"]:
                continue
            try:
                remote = retrieve_subscription(
                    provider_subscription_id=subscription.provider_subscription_id
                )
            except Exception as exc:
                issues.append(
                    {
                        "subscription_id": str(subscription.pk),
                        "code": "provider_lookup_failed",
                        "detail": str(exc)[:200],
                    }
                )
                continue
            if remote.get("customer") != subscription.provider_customer_id:
                issues.append(
                    {
                        "subscription_id": str(subscription.pk),
                        "code": "customer_mismatch",
                    }
                )
            if remote.get("status") != subscription.status:
                issues.append(
                    {
                        "subscription_id": str(subscription.pk),
                        "code": "status_mismatch",
                    }
                )
        result = {"checked": checked, "issues": issues}
        if options["json"]:
            self.stdout.write(json.dumps(result, sort_keys=True))
        else:
            self.stdout.write(
                f"Checked {checked} paid subscription(s); found {len(issues)} issue(s)."
            )
        if issues:
            raise CommandError("Stripe Billing reconciliation failed.")

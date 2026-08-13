import json
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Sum
from django.utils import timezone


def _result(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def collect_launch_checks(*, require_stripe=False):
    from billing.models import Plan, Subscription
    from communications.models import EmailDelivery, OutboxEvent
    from invoices.models import Invoice
    from payments.models import Payment, PaymentReversal
    from workspaces.models import Workspace

    results = []

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        results.append(_result("database", "pass", "Primary database is reachable."))
    except Exception as exc:
        results.append(_result("database", "fail", f"Database unavailable: {exc}"))

    try:
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        results.append(
            _result(
                "migrations",
                "fail" if pending else "pass",
                f"{len(pending)} migration(s) pending."
                if pending
                else "All committed migrations are applied.",
            )
        )
    except Exception as exc:
        results.append(_result("migrations", "fail", f"Migration check failed: {exc}"))

    cache_key = f"launch-gate:{uuid.uuid4().hex}"
    try:
        cache.set(cache_key, "ok", timeout=30)
        cache_ok = cache.get(cache_key) == "ok"
        cache.delete(cache_key)
        results.append(
            _result(
                "cache",
                "pass" if cache_ok else "fail",
                "Cache round trip passed." if cache_ok else "Cache round trip failed.",
            )
        )
    except Exception as exc:
        results.append(_result("cache", "fail", f"Cache unavailable: {exc}"))

    plan_codes = set(
        Plan.objects.filter(code__in=("free", "starter"), is_active=True).values_list(
            "code", flat=True
        )
    )
    results.append(
        _result(
            "plans",
            "pass" if plan_codes == {"free", "starter"} else "fail",
            "Free and Starter plans are active."
            if plan_codes == {"free", "starter"}
            else "Free and Starter plans must both be active.",
        )
    )
    missing_subscriptions = Workspace.objects.exclude(
        pk__in=Subscription.objects.values("workspace_id")
    ).count()
    results.append(
        _result(
            "subscriptions",
            "pass" if missing_subscriptions == 0 else "fail",
            f"{missing_subscriptions} workspace(s) have no subscription.",
        )
    )

    reconciliation_issues = 0
    invoices = Invoice.objects.exclude(status=Invoice.Status.DRAFT).iterator()
    for invoice in invoices:
        posted = (
            Payment.objects.filter(invoice=invoice).aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )
        reversed_total = (
            PaymentReversal.objects.filter(payment__invoice=invoice).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        expected_paid = posted - reversed_total
        if invoice.amount_paid != expected_paid or invoice.balance_due != (
            invoice.total - expected_paid
        ):
            reconciliation_issues += 1
    results.append(
        _result(
            "financial_reconciliation",
            "pass" if reconciliation_issues == 0 else "fail",
            f"{reconciliation_issues} invoice ledger mismatch(es).",
        )
    )

    failed_delivery = EmailDelivery.objects.filter(
        status=EmailDelivery.Status.FAILED
    ).count()
    failed_outbox = OutboxEvent.objects.filter(status=OutboxEvent.Status.FAILED).count()
    results.append(
        _result(
            "communications",
            "pass" if not (failed_delivery or failed_outbox) else "fail",
            f"{failed_delivery} failed delivery(s), {failed_outbox} failed outbox event(s).",
        )
    )

    site_https = settings.SITE_URL.startswith("https://")
    results.append(
        _result(
            "site_url",
            "pass" if site_https else "warn",
            "SITE_URL uses HTTPS."
            if site_https
            else "SITE_URL is not HTTPS; acceptable only for local development.",
        )
    )
    email_is_console = settings.EMAIL_BACKEND.endswith("console.EmailBackend")
    results.append(
        _result(
            "email_provider",
            "warn" if email_is_console else "pass",
            "Console email backend is not production-ready."
            if email_is_console
            else "A non-console email backend is configured.",
        )
    )
    storage_backend = settings.STORAGES["default"]["BACKEND"]
    file_storage = storage_backend.endswith("FileSystemStorage")
    results.append(
        _result(
            "private_storage",
            "warn" if file_storage else "pass",
            "Filesystem media storage requires persistent private disk and backup."
            if file_storage
            else "A non-filesystem media storage backend is configured.",
        )
    )

    stripe_values = {
        "secret key": settings.STRIPE_SECRET_KEY,
        "publishable key": settings.STRIPE_PUBLISHABLE_KEY,
        "platform webhook secret": settings.STRIPE_PLATFORM_WEBHOOK_SECRET,
        "Connect webhook secret": settings.STRIPE_CONNECT_WEBHOOK_SECRET,
    }
    missing_stripe = [name for name, value in stripe_values.items() if not value]
    starter = Plan.objects.filter(code="starter").first()
    has_price = bool(
        starter
        and (starter.provider_monthly_price_id or starter.provider_annual_price_id)
    )
    if not has_price:
        missing_stripe.append("Starter Stripe Price ID")
    stripe_status = "fail" if require_stripe and missing_stripe else "warn"
    if not missing_stripe:
        stripe_status = "pass"
    results.append(
        _result(
            "stripe",
            stripe_status,
            "Stripe sandbox/live configuration is complete."
            if not missing_stripe
            else f"Missing: {', '.join(missing_stripe)}.",
        )
    )

    return {
        "checked_at": timezone.now().isoformat(),
        "checks": results,
        "summary": {
            "pass": sum(item["status"] == "pass" for item in results),
            "warn": sum(item["status"] == "warn" for item in results),
            "fail": sum(item["status"] == "fail" for item in results),
        },
    }


class Command(BaseCommand):
    help = "Run provider-independent launch checks and optional Stripe configuration gates."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--require-stripe", action="store_true")
        parser.add_argument("--fail-on-warning", action="store_true")

    def handle(self, *args, **options):
        report = collect_launch_checks(require_stripe=options["require_stripe"])
        if options["json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
        else:
            for item in report["checks"]:
                self.stdout.write(
                    f"[{item['status'].upper()}] {item['name']}: {item['detail']}"
                )
        summary = report["summary"]
        if summary["fail"] or (options["fail_on_warning"] and summary["warn"]):
            raise CommandError(
                f"Launch gate failed: {summary['fail']} failure(s), "
                f"{summary['warn']} warning(s)."
            )

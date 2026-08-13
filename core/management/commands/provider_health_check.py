import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from billing.models import PlatformWebhookEvent
from payments.models import ConnectWebhookEvent, InvoicePaymentAttempt


def provider_health(*, stale_minutes):
    stale_before = timezone.now() - timedelta(minutes=stale_minutes)
    billing_events = PlatformWebhookEvent.objects.filter(
        Q(status=PlatformWebhookEvent.Status.FAILED)
        | Q(
            status__in=(
                PlatformWebhookEvent.Status.PENDING,
                PlatformWebhookEvent.Status.PROCESSING,
            ),
            updated_at__lt=stale_before,
        )
    ).count()
    connect_events = ConnectWebhookEvent.objects.filter(
        Q(status=ConnectWebhookEvent.Status.FAILED)
        | Q(
            status__in=(
                ConnectWebhookEvent.Status.PENDING,
                ConnectWebhookEvent.Status.PROCESSING,
            ),
            updated_at__lt=stale_before,
        )
    ).count()
    expired_active_attempts = InvoicePaymentAttempt.objects.filter(
        status__in=(
            InvoicePaymentAttempt.Status.PENDING,
            InvoicePaymentAttempt.Status.OPEN,
            InvoicePaymentAttempt.Status.PROCESSING,
        ),
        expires_at__lte=timezone.now(),
    ).count()
    return {
        "billing_events_requiring_attention": billing_events,
        "connect_events_requiring_attention": connect_events,
        "expired_active_payment_attempts": expired_active_attempts,
        "healthy": not (billing_events or connect_events or expired_active_attempts),
    }


class Command(BaseCommand):
    help = "Fail when Stripe webhook inboxes or payment attempts require attention."

    def add_arguments(self, parser):
        parser.add_argument("--stale-minutes", type=int, default=15)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        result = provider_health(stale_minutes=options["stale_minutes"])
        if options["json"]:
            self.stdout.write(json.dumps(result, sort_keys=True))
        elif result["healthy"]:
            self.stdout.write(self.style.SUCCESS("Provider health passed."))
        if not result["healthy"]:
            raise CommandError(
                "Provider health failed: "
                f"{result['billing_events_requiring_attention']} billing event(s), "
                f"{result['connect_events_requiring_attention']} Connect event(s), "
                f"{result['expired_active_payment_attempts']} expired active attempt(s)."
            )

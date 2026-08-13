from django.core.management.base import BaseCommand, CommandError

from billing.models import PlatformWebhookEvent
from billing.services import process_platform_webhook


class Command(BaseCommand):
    help = "Retry pending or failed Stripe Billing webhook inbox events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        event_ids = list(
            PlatformWebhookEvent.objects.filter(
                status__in=(
                    PlatformWebhookEvent.Status.PENDING,
                    PlatformWebhookEvent.Status.FAILED,
                )
            )
            .order_by("created_at")
            .values_list("pk", flat=True)[: options["limit"]]
        )
        failures = 0
        for event_id in event_ids:
            try:
                process_platform_webhook(event_id=event_id)
            except Exception as exc:
                failures += 1
                self.stderr.write(f"{event_id}: {exc}")
        self.stdout.write(f"Processed {len(event_ids)} billing webhook event(s).")
        if failures:
            raise CommandError(f"{failures} billing webhook event(s) failed.")

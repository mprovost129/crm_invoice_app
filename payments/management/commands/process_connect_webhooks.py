from django.core.management.base import BaseCommand, CommandError

from payments.models import ConnectWebhookEvent
from payments.online_services import process_connect_webhook


class Command(BaseCommand):
    help = "Retry pending or failed Stripe Connect webhook inbox events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        event_ids = list(
            ConnectWebhookEvent.objects.filter(
                status__in=(
                    ConnectWebhookEvent.Status.PENDING,
                    ConnectWebhookEvent.Status.FAILED,
                )
            )
            .order_by("created_at")
            .values_list("pk", flat=True)[: options["limit"]]
        )
        failures = 0
        for event_id in event_ids:
            try:
                process_connect_webhook(event_id=event_id)
            except Exception as exc:
                failures += 1
                self.stderr.write(f"{event_id}: {exc}")
        self.stdout.write(f"Processed {len(event_ids)} Connect webhook event(s).")
        if failures:
            raise CommandError(f"{failures} Connect webhook event(s) failed.")

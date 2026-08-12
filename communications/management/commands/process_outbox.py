from django.core.management.base import BaseCommand
from django.utils import timezone

from communications.emailing import process_outbox_event
from communications.models import OutboxEvent


class Command(BaseCommand):
    help = "Process pending or failed transactional outbox events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        event_ids = list(
            OutboxEvent.objects.filter(
                status__in=(OutboxEvent.Status.PENDING, OutboxEvent.Status.FAILED),
                available_at__lte=timezone.now(),
            )
            .order_by("available_at")
            .values_list("pk", flat=True)[: options["limit"]]
        )
        for event_id in event_ids:
            process_outbox_event(event_id)
        self.stdout.write(self.style.SUCCESS(f"Processed {len(event_ids)} event(s)."))

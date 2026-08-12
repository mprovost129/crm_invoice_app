from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from communications.models import EmailDelivery, OutboxEvent


class Command(BaseCommand):
    help = "Fail when email deliveries or outbox jobs require operator attention."

    def add_arguments(self, parser):
        parser.add_argument("--stale-minutes", type=int, default=15)

    def handle(self, *args, **options):
        stale_before = timezone.now() - timedelta(minutes=options["stale_minutes"])
        failed_deliveries = EmailDelivery.objects.filter(
            status=EmailDelivery.Status.FAILED
        ).count()
        stuck_events = OutboxEvent.objects.filter(
            Q(status=OutboxEvent.Status.FAILED)
            | Q(status=OutboxEvent.Status.PROCESSING, updated_at__lt=stale_before)
            | Q(status=OutboxEvent.Status.PENDING, available_at__lt=stale_before)
        ).count()
        if failed_deliveries or stuck_events:
            raise CommandError(
                f"Communication health failed: {failed_deliveries} failed delivery(s), "
                f"{stuck_events} stuck/failed outbox event(s)."
            )
        self.stdout.write(self.style.SUCCESS("Communication health passed."))

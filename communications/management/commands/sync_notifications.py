from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from communications.models import Notification
from communications.notifications import notify_business_owner
from invoices.models import Invoice
from workspaces.models import Business


class Command(BaseCommand):
    help = "Create idempotent owner notifications for newly overdue invoices."

    def handle(self, *args, **options):
        active = 0
        for business in Business.objects.active().select_related("workspace"):
            today = timezone.localdate(timezone=ZoneInfo(business.timezone))
            invoices = (
                Invoice.objects.for_business(business)
                .filter(balance_due__gt=0, due_date__lt=today)
                .exclude(status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID))
                .select_related("contact")
            )
            for invoice in invoices:
                notification = notify_business_owner(
                    business=business,
                    kind=Notification.Kind.INVOICE_OVERDUE,
                    title=f"Invoice {invoice.number} is overdue",
                    body=(
                        f"{invoice.currency} {invoice.balance_due:.2f} remains due "
                        f"from {invoice.contact.display_name}."
                    ),
                    target_path=f"/app/invoices/{invoice.pk}/",
                    dedupe_key=f"invoice-overdue:{invoice.pk}:{invoice.due_date}",
                )
                active += int(notification is not None)
        self.stdout.write(
            self.style.SUCCESS(f"Synchronized overdue notifications ({active} active).")
        )

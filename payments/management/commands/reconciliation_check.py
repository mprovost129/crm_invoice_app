from django.core.management.base import BaseCommand, CommandError

from invoices.models import Invoice
from payments.services import expected_invoice_paid_total


class Command(BaseCommand):
    help = "Verify invoice payment caches against posted payments and reversals."

    def handle(self, *args, **options):
        failures = []
        for invoice in Invoice.objects.exclude(status=Invoice.Status.DRAFT).iterator():
            expected_paid = expected_invoice_paid_total(invoice)
            expected_balance = invoice.total - expected_paid
            if (
                invoice.amount_paid != expected_paid
                or invoice.balance_due != expected_balance
            ):
                failures.append(invoice.number)
        if failures:
            raise CommandError(
                f"Payment reconciliation failed for {len(failures)} invoice(s): "
                + ", ".join(failures[:20])
            )
        self.stdout.write(self.style.SUCCESS("Payment reconciliation passed."))

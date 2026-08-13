import json

from django.core.management.base import BaseCommand, CommandError

from payments.models import ConnectedAccount, InvoicePaymentAttempt, Payment
from payments.stripe_gateway import retrieve_invoice_checkout


class Command(BaseCommand):
    help = "Check local Stripe invoice-payment attempts against the payment ledger."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--provider", action="store_true")

    def handle(self, *args, **options):
        issues = []
        completed = InvoicePaymentAttempt.objects.filter(
            status=InvoicePaymentAttempt.Status.COMPLETED
        )
        for attempt in completed.iterator():
            if not attempt.provider_payment_intent_id:
                issues.append(
                    {
                        "attempt_id": str(attempt.pk),
                        "code": "missing_provider_payment_id",
                    }
                )
        if options["provider"]:
            attempts = InvoicePaymentAttempt.objects.exclude(
                provider_checkout_session_id__isnull=True
            ).exclude(provider_checkout_session_id="")
            for attempt in attempts.select_related("business").iterator():
                account_id = (
                    ConnectedAccount.objects.filter(business=attempt.business)
                    .values_list("provider_account_id", flat=True)
                    .first()
                )
                if not account_id:
                    issues.append(
                        {
                            "attempt_id": str(attempt.pk),
                            "code": "missing_connected_account",
                        }
                    )
                    continue
                try:
                    remote = retrieve_invoice_checkout(
                        provider_checkout_session_id=attempt.provider_checkout_session_id,
                        provider_account_id=account_id,
                    )
                except Exception as exc:
                    issues.append(
                        {
                            "attempt_id": str(attempt.pk),
                            "code": "provider_lookup_failed",
                            "detail": str(exc)[:200],
                        }
                    )
                    continue
                if (
                    attempt.status == InvoicePaymentAttempt.Status.COMPLETED
                    and remote.get("payment_status") != "paid"
                ):
                    issues.append(
                        {"attempt_id": str(attempt.pk), "code": "provider_not_paid"}
                    )
                continue
            payment = Payment.objects.filter(
                provider_payment_id=attempt.provider_payment_intent_id,
                invoice=attempt.invoice,
                business=attempt.business,
                source=Payment.Source.ONLINE,
            ).first()
            if payment is None or payment.amount != attempt.amount:
                issues.append(
                    {
                        "attempt_id": str(attempt.pk),
                        "code": "ledger_mismatch",
                    }
                )
        result = {"checked": completed.count(), "issues": issues}
        if options["json"]:
            self.stdout.write(json.dumps(result, sort_keys=True))
        else:
            self.stdout.write(
                f"Checked {result['checked']} completed online payment attempt(s); "
                f"found {len(issues)} issue(s)."
            )
        if issues:
            raise CommandError("Stripe invoice-payment reconciliation failed.")

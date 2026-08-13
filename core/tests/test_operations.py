import uuid

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from billing.models import PlatformWebhookEvent


@pytest.mark.django_db
def test_launch_gate_reports_no_hard_failures(capsys):
    call_command("launch_gate", "--json")
    output = capsys.readouterr().out

    assert '"fail": 0' in output
    assert '"name": "database"' in output
    assert '"name": "financial_reconciliation"' in output


@pytest.mark.django_db
def test_provider_health_check_fails_for_failed_webhook_event():
    PlatformWebhookEvent.objects.create(
        provider_event_id=f"evt_{uuid.uuid4().hex}",
        event_type="customer.subscription.updated",
        payload={"data": {"object": {}}},
        status=PlatformWebhookEvent.Status.FAILED,
        signature_verified_at=timezone.now(),
        last_error="Test failure",
    )

    with pytest.raises(CommandError, match="Provider health failed"):
        call_command("provider_health_check")

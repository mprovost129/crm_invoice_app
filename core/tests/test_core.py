from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.urls import reverse


@pytest.mark.django_db
def test_health_check(client):
    response = client.get(reverse("core:health"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_liveness_check_does_not_require_database(client):
    response = client.get(reverse("core:health-live"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "ok"}


@pytest.mark.django_db
def test_readiness_check_reports_database_failure(client):
    with patch("core.views.connection.cursor", side_effect=OperationalError):
        response = client.get(reverse("core:health-ready"))

    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "unavailable"}


def test_request_id_is_added(client):
    response = client.get(reverse("core:home"), HTTP_X_REQUEST_ID="known-request-id")
    assert response["X-Request-ID"] == "known-request-id"


def test_home_loads_self_hosted_htmx(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert b"vendor/htmx/htmx.min.js" in response.content
    assert b"cdn.jsdelivr.net/npm/htmx" not in response.content

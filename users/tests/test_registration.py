import pytest
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import User
from users.tokens import email_verification_token
from workspaces.models import Membership, Workspace

PASSWORD = "Truly-Safe-Phase1-Password-472!"


@pytest.mark.django_db
def test_registration_creates_owner_tenancy_and_queues_verification(
    client,
    django_capture_on_commit_callbacks,
):
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            reverse("users:register"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "Ada@Example.COM",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

    assert response.status_code == 302
    assert response.url == reverse("users:verification-sent")
    user = User.objects.get(email="ada@example.com")
    workspace = Workspace.objects.get(owner_user=user)
    membership = Membership.objects.get(workspace=workspace, user=user)
    assert membership.role == Membership.Role.OWNER
    assert membership.status == Membership.Status.ACTIVE
    assert membership.accepted_at is not None
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to
    assert "http://localhost:8000" in mail.outbox[0].body
    assert "/accounts/verify-email/" in mail.outbox[0].body


@pytest.mark.django_db
def test_registration_rejects_case_insensitive_duplicate(client):
    User.objects.create_user("owner@example.com", PASSWORD)

    response = client.post(
        reverse("users:register"),
        {
            "first_name": "Other",
            "last_name": "Owner",
            "email": "OWNER@EXAMPLE.COM",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )

    assert response.status_code == 200
    assert b"An account with this email already exists" in response.content
    assert User.objects.count() == 1
    assert Workspace.objects.count() == 0


@pytest.mark.django_db
def test_email_verification_logs_user_in_and_redirects_to_onboarding(client):
    user = User.objects.create_user("owner@example.com", PASSWORD)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)

    response = client.get(
        reverse("users:verify-email", kwargs={"uidb64": uid, "token": token})
    )

    assert response.status_code == 302
    assert response.url == reverse("workspaces:onboarding")
    user.refresh_from_db()
    assert user.is_email_verified
    assert str(user.pk) == client.session.get("_auth_user_id")
    assert not email_verification_token.check_token(user, token)


@pytest.mark.django_db
def test_login_routes_unverified_user_to_verification(client):
    User.objects.create_user("owner@example.com", PASSWORD)

    response = client.post(
        reverse("users:login"),
        {"username": "OWNER@EXAMPLE.COM", "password": PASSWORD},
    )

    assert response.status_code == 302
    assert response.url == reverse("users:verification-sent")


@pytest.mark.django_db
def test_password_reset_sends_namespaced_link(client):
    user = User.objects.create_user("owner@example.com", PASSWORD)
    user.email_verified_at = timezone.now()
    user.save(update_fields=("email_verified_at",))

    response = client.post(
        reverse("users:password_reset"),
        {"email": user.email},
    )

    assert response.status_code == 302
    assert response.url == reverse("users:password_reset_done")
    assert len(mail.outbox) == 1
    assert "/accounts/reset/" in mail.outbox[0].body
    assert mail.outbox[0].subject == f"Reset your {settings.APP_NAME} password"


@pytest.mark.django_db
def test_password_change_invalidates_existing_reset_token():
    user = User.objects.create_user("owner@example.com", PASSWORD)
    token = default_token_generator.make_token(user)
    assert default_token_generator.check_token(user, token)

    user.set_password("Another-Safe-Phase1-Password-839!")
    user.save(update_fields=("password",))

    assert not default_token_generator.check_token(user, token)


@pytest.mark.django_db
def test_registration_posts_are_rate_limited(client, settings):
    settings.PUBLIC_ACCOUNT_CREATE_LIMIT = 1
    cache.clear()
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    first = client.post(reverse("users:register"), payload)
    payload["email"] = "other@example.com"
    second = client.post(reverse("users:register"), payload)

    assert first.status_code == 302
    assert second.status_code == 429
    assert second["Retry-After"] == "3600"

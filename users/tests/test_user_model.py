import uuid

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from users.models import AccountProfile


@pytest.mark.django_db
def test_auth_user_model_is_custom_email_user():
    User = get_user_model()
    assert settings.AUTH_USER_MODEL == "users.User"
    assert User.USERNAME_FIELD == "email"
    assert not hasattr(User, "username")


@pytest.mark.django_db
def test_create_user_normalizes_email_and_hashes_password():
    User = get_user_model()
    user = User.objects.create_user("Test@EXAMPLE.COM", "safe-test-password")
    assert user.email == "test@example.com"
    assert user.check_password("safe-test-password")
    assert isinstance(user.pk, uuid.UUID)


@pytest.mark.django_db
def test_create_superuser_sets_required_flags():
    User = get_user_model()
    user = User.objects.create_superuser("admin@example.com", "safe-test-password")
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_active is True


@pytest.mark.django_db
def test_account_profile_is_one_to_one():
    User = get_user_model()
    user = User.objects.create_user("customer@example.com", "safe-test-password")
    profile = AccountProfile.objects.create(user=user, company_name="Example Co")
    assert user.account_profile == profile
    assert isinstance(profile.pk, uuid.UUID)


@pytest.mark.django_db
def test_admin_customer_search_is_primary_admin_route(client):
    User = get_user_model()
    admin = User.objects.create_superuser("admin@example.com", "safe-test-password")
    client.force_login(admin)
    response = client.get(reverse("admin:index"))
    assert response.status_code == 200
    assert b"Find a customer" in response.content

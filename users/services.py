from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import slugify

from billing.services import create_default_subscription
from workspaces.models import Membership, Workspace

from .models import User
from .tokens import email_verification_token


def send_verification_email(user_id):
    """Send one verification link without exposing the raw user ID."""
    user = User.objects.get(pk=user_id)
    if user.is_email_verified:
        return 0

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    path = reverse("users:verify-email", kwargs={"uidb64": uid, "token": token})
    verification_url = f"{settings.SITE_URL}{path}"
    return send_mail(
        subject=f"Verify your email for {settings.APP_NAME}",
        message=(
            f"Welcome to {settings.APP_NAME}.\n\n"
            f"Verify your email address: {verification_url}\n\n"
            "If you did not create this account, you can ignore this message."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def register_user(*, email, password, first_name, last_name):
    """Atomically create a user, SaaS workspace, and active owner membership."""
    normalized_email = User.objects.normalize_email(email).casefold()
    try:
        with transaction.atomic():
            if User.objects.filter(email__iexact=normalized_email).exists():
                raise ValidationError("An account with this email already exists.")

            user = User.objects.create_user(
                email=normalized_email,
                password=password,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
            )
            workspace_name = f"{user.display_name}'s Workspace"
            workspace = Workspace(
                name=workspace_name,
                owner_user=user,
            )
            slug_base = slugify(user.display_name) or "workspace"
            workspace.slug = f"{slug_base[:60]}-{workspace.id.hex[:8]}"
            workspace.save()
            create_default_subscription(workspace=workspace)
            Membership.objects.create(
                workspace=workspace,
                user=user,
                role=Membership.Role.OWNER,
                status=Membership.Status.ACTIVE,
                accepted_at=timezone.now(),
            )
            transaction.on_commit(
                partial(send_verification_email, user.pk),
                robust=True,
            )
            return user
    except IntegrityError as exc:
        raise ValidationError("An account with this email already exists.") from exc

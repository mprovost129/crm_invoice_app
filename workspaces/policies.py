from django.core.exceptions import PermissionDenied

from .models import Business, Membership


def business_for_actor(*, actor, business_id, roles=None, lock=False):
    """Resolve a Business through an active, verified membership or deny access."""
    if not getattr(actor, "is_authenticated", False) or not actor.is_email_verified:
        raise PermissionDenied("Verified business access is required.")

    businesses = Business.objects.filter(
        pk=business_id,
        is_active=True,
        archived_at__isnull=True,
        workspace__status="active",
        workspace__memberships__user=actor,
        workspace__memberships__status=Membership.Status.ACTIVE,
    )
    if roles:
        businesses = businesses.filter(workspace__memberships__role__in=roles)
    if lock:
        businesses = businesses.select_for_update()
    business = businesses.first()
    if business is None:
        raise PermissionDenied("Business access is required.")
    return business


def owner_business_for_actor(*, actor, business_id, lock=False):
    return business_for_actor(
        actor=actor,
        business_id=business_id,
        roles=(Membership.Role.OWNER,),
        lock=lock,
    )

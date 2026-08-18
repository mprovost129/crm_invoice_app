from .models import Business, Membership


def active_membership_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return (
        Membership.objects.active()
        .for_user(user)
        .filter(workspace__status="active")
        .select_related("workspace")
        .order_by("created_at")
        .first()
    )


def active_owner_membership_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return (
        Membership.objects.active()
        .for_user(user)
        .filter(
            role=Membership.Role.OWNER,
            workspace__status="active",
        )
        .select_related("workspace")
        .order_by("created_at")
        .first()
    )


def active_business_for_user(user, *, workspace=None):
    if not getattr(user, "is_authenticated", False):
        return None
    businesses = Business.objects.for_user(user).active()
    if workspace is not None:
        businesses = businesses.for_workspace(workspace)
    return (
        businesses.select_related("workspace", "settings")
        .order_by("created_at")
        .first()
    )


def business_for_user(user, business_id):
    return (
        Business.objects.for_user(user)
        .select_related("workspace", "settings")
        .filter(pk=business_id)
        .first()
    )

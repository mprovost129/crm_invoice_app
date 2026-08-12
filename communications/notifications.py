from .models import Notification


def notify_business_owner(*, business, kind, title, body, target_path, dedupe_key):
    membership = (
        business.workspace.memberships.filter(status="active", role="owner")
        .select_related("user")
        .first()
    )
    if membership is None:
        return None
    notification, _ = Notification.objects.get_or_create(
        business=business,
        dedupe_key=dedupe_key,
        defaults={
            "recipient": membership.user,
            "kind": kind,
            "title": title,
            "body": body,
            "target_path": target_path,
        },
    )
    return notification

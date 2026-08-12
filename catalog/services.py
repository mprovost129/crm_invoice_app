from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from workspaces.policies import owner_business_for_actor

from .entitlements import enforce_catalog_item_creation_allowed
from .models import ProductService

CATALOG_FIELDS = (
    "name",
    "description",
    "item_type",
    "unit",
    "custom_unit",
    "default_rate",
    "is_taxable",
)


def _catalog_item_for_update(*, actor, business_id, item_id):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    item = (
        ProductService.objects.select_for_update()
        .for_business(business)
        .filter(pk=item_id)
        .first()
    )
    if item is None:
        raise PermissionDenied("Catalog item access is required.")
    return business, item


@transaction.atomic
def create_catalog_item(*, actor, business_id, data):
    business = owner_business_for_actor(
        actor=actor,
        business_id=business_id,
        lock=True,
    )
    enforce_catalog_item_creation_allowed(business=business)
    item = ProductService(
        business=business,
        created_by=actor,
        **{field: data.get(field, "") for field in CATALOG_FIELDS},
    )
    item.full_clean()
    item.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CATALOG_CREATED,
        summary=f"Created catalog {item.get_item_type_display().lower()} {item.name}.",
        product_service=item,
        metadata={"item_type": item.item_type},
    )
    return item


@transaction.atomic
def update_catalog_item(*, actor, business_id, item_id, data):
    business, item = _catalog_item_for_update(
        actor=actor,
        business_id=business_id,
        item_id=item_id,
    )
    changed_fields = []
    for field in CATALOG_FIELDS:
        value = data.get(field, "")
        if getattr(item, field) != value:
            setattr(item, field, value)
            changed_fields.append(field)
    if not changed_fields:
        return item
    item.full_clean()
    item.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CATALOG_UPDATED,
        summary=f"Updated catalog item {item.name}.",
        product_service=item,
        metadata={"changed_fields": changed_fields},
    )
    return item


@transaction.atomic
def archive_catalog_item(*, actor, business_id, item_id):
    business, item = _catalog_item_for_update(
        actor=actor,
        business_id=business_id,
        item_id=item_id,
    )
    if not item.is_active:
        raise ValidationError("Catalog item is already archived.")
    item.is_active = False
    item.archived_at = timezone.now()
    item.full_clean()
    item.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CATALOG_STATUS_CHANGED,
        summary=f"Archived catalog item {item.name}.",
        product_service=item,
        metadata={"from": "active", "to": "archived"},
    )
    return item


@transaction.atomic
def restore_catalog_item(*, actor, business_id, item_id):
    business, item = _catalog_item_for_update(
        actor=actor,
        business_id=business_id,
        item_id=item_id,
    )
    if item.is_active or item.archived_at is None:
        raise ValidationError("Only an archived catalog item can be restored.")
    item.is_active = True
    item.archived_at = None
    item.full_clean()
    item.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CATALOG_STATUS_CHANGED,
        summary=f"Restored catalog item {item.name}.",
        product_service=item,
        metadata={"from": "archived", "to": "active"},
    )
    return item

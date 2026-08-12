from django.db.models import Q

from .models import ProductService


def catalog_items_for_business(*, business, search="", item_type="", status=""):
    items = ProductService.objects.for_business(business)
    if item_type in ProductService.ItemType.values:
        items = items.filter(item_type=item_type)
    if status == "active":
        items = items.active()
    elif status == "archived":
        items = items.filter(is_active=False, archived_at__isnull=False)
    if search:
        items = items.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    return items


def catalog_item_for_business(*, business, item_id):
    return ProductService.objects.for_business(business).filter(pk=item_id).first()

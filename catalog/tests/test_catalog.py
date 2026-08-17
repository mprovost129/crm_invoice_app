from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from activity.models import ActivityEvent
from catalog.models import ProductService
from catalog.selectors import catalog_items_for_business
from catalog.services import (
    archive_catalog_item,
    create_catalog_item,
    restore_catalog_item,
    update_catalog_item,
)
from workspaces.tests.helpers import create_business, create_owner_tenancy

ITEM_DATA = {
    "name": "Design consultation",
    "description": "On-site design consultation.",
    "item_type": ProductService.ItemType.SERVICE,
    "unit": ProductService.Unit.HOUR,
    "custom_unit": "",
    "default_rate": Decimal("125.00"),
    "is_taxable": False,
}


@pytest.mark.django_db
def test_catalog_lifecycle_records_activity_and_calls_entitlement_hook(monkeypatch):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    checked = []
    monkeypatch.setattr(
        "catalog.services.enforce_catalog_item_creation_allowed",
        lambda *, business: checked.append(business),
    )

    item = create_catalog_item(actor=user, business_id=business.pk, data=ITEM_DATA)
    assert checked == [business]
    assert item.business == business
    assert item.is_active

    archived = archive_catalog_item(
        actor=user,
        business_id=business.pk,
        item_id=item.pk,
    )
    assert not archived.is_active
    assert archived.archived_at is not None

    restored = restore_catalog_item(
        actor=user,
        business_id=business.pk,
        item_id=item.pk,
    )
    assert restored.is_active
    assert restored.archived_at is None
    assert ActivityEvent.objects.filter(product_service=item).count() == 3


@pytest.mark.django_db
def test_custom_unit_and_nonnegative_rate_are_enforced():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)

    with pytest.raises(ValidationError):
        create_catalog_item(
            actor=user,
            business_id=business.pk,
            data={**ITEM_DATA, "unit": "custom", "custom_unit": ""},
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProductService.objects.create(
            business=business,
            name="Invalid",
            unit=ProductService.Unit.HOUR,
            default_rate=Decimal("-1.00"),
        )


@pytest.mark.django_db
def test_catalog_rate_preserves_four_decimal_precision():
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)

    item = create_catalog_item(
        actor=user,
        business_id=business.pk,
        data={**ITEM_DATA, "default_rate": Decimal("125.1234")},
    )

    item.refresh_from_db()
    assert item.default_rate == Decimal("125.1234")


@pytest.mark.django_db
def test_catalog_services_deny_cross_tenant_update():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    first_business = create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    item = create_catalog_item(
        actor=second_user,
        business_id=second_business.pk,
        data=ITEM_DATA,
    )

    with pytest.raises(PermissionDenied):
        update_catalog_item(
            actor=first_user,
            business_id=first_business.pk,
            item_id=item.pk,
            data={**ITEM_DATA, "name": "Compromised"},
        )

    item.refresh_from_db()
    assert item.name == ITEM_DATA["name"]


@pytest.mark.django_db
def test_catalog_selector_searches_filters_and_isolates_business():
    first_user, first_workspace, _ = create_owner_tenancy("first@example.com")
    second_user, second_workspace, _ = create_owner_tenancy("second@example.com")
    first_business = create_business(first_workspace)
    second_business = create_business(
        second_workspace,
        legal_name="Second LLC",
        display_name="Second Business",
        email="second-business@example.com",
    )
    own_item = create_catalog_item(
        actor=first_user,
        business_id=first_business.pk,
        data=ITEM_DATA,
    )
    create_catalog_item(
        actor=first_user,
        business_id=first_business.pk,
        data={**ITEM_DATA, "name": "Cabinet hardware", "item_type": "product"},
    )
    create_catalog_item(
        actor=second_user,
        business_id=second_business.pk,
        data={**ITEM_DATA, "name": "Foreign consultation"},
    )

    results = catalog_items_for_business(
        business=first_business,
        search="consultation",
        item_type="service",
        status="active",
    )

    assert list(results) == [own_item]


@pytest.mark.django_db
def test_catalog_web_create_edit_archive_and_foreign_404(client):
    user, workspace, _ = create_owner_tenancy()
    business = create_business(workspace)
    foreign_user, foreign_workspace, _ = create_owner_tenancy("foreign@example.com")
    foreign_business = create_business(
        foreign_workspace,
        legal_name="Foreign LLC",
        display_name="Foreign Business",
        email="foreign-business@example.com",
    )
    foreign_item = create_catalog_item(
        actor=foreign_user,
        business_id=foreign_business.pk,
        data=ITEM_DATA,
    )
    client.force_login(user)

    response = client.post(reverse("catalog:item-create"), ITEM_DATA)
    assert response.status_code == 302
    item = ProductService.objects.get(business=business)

    response = client.post(
        reverse("catalog:item-update", args=(item.pk,)),
        {**ITEM_DATA, "name": "Updated consultation", "is_taxable": "on"},
    )
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.name == "Updated consultation"
    assert item.is_taxable

    response = client.post(reverse("catalog:item-status", args=(item.pk, "archive")))
    assert response.status_code == 302
    item.refresh_from_db()
    assert not item.is_active

    assert (
        client.get(reverse("catalog:item-update", args=(foreign_item.pk,))).status_code
        == 404
    )
    assert (
        client.post(
            reverse("catalog:item-status", args=(foreign_item.pk, "archive"))
        ).status_code
        == 404
    )

from decimal import Decimal

from crm.services import create_contact
from crm.tests.helpers import CONTACT_DATA
from estimates.models import Estimate
from estimates.services import add_estimate_line, create_estimate, issue_estimate

ESTIMATE_DATA = {
    "expiration_date": None,
    "discount_type": Estimate.AmountType.NONE,
    "discount_value": Decimal("0"),
    "deposit_type": Estimate.AmountType.NONE,
    "deposit_value": Decimal("0"),
    "requires_acceptance": True,
    "notes": "Prepared specifically for this project.",
    "terms": "Valid until the expiration date.",
}

LINE_DATA = {
    "source_catalog_item_id": None,
    "name": "Design consultation",
    "description": "On-site consultation and design recommendations.",
    "unit": "hour",
    "quantity": Decimal("2"),
    "unit_rate": Decimal("125"),
    "is_taxable": True,
    "tax_rate": Decimal("6.25"),
}


def create_estimate_fixture(*, user, business, estimate_data=None, line_data=None):
    contact = create_contact(
        actor=user,
        business_id=business.pk,
        data=CONTACT_DATA,
    )
    estimate = create_estimate(
        actor=user,
        business_id=business.pk,
        data={
            **ESTIMATE_DATA,
            "contact_id": contact.pk,
            **(estimate_data or {}),
        },
    )
    line = add_estimate_line(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
        data={**LINE_DATA, **(line_data or {})},
    )
    estimate.refresh_from_db()
    return estimate, line, contact


def create_issued_estimate(*, user, business, estimate_data=None, line_data=None):
    estimate, line, contact = create_estimate_fixture(
        user=user,
        business=business,
        estimate_data=estimate_data,
        line_data=line_data,
    )
    estimate = issue_estimate(
        actor=user,
        business_id=business.pk,
        estimate_id=estimate.pk,
    )
    return estimate, line, contact

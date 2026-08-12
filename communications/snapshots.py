import hashlib
import json

from .models import DocumentSnapshot


def _address(*parts):
    return ", ".join(str(part).strip() for part in parts if str(part).strip())


def build_estimate_snapshot_payload(*, estimate, lines):
    business = estimate.business
    contact = estimate.contact
    return {
        "schema_version": 1,
        "document_type": "estimate",
        "estimate": {
            "id": str(estimate.pk),
            "number": estimate.number,
            "currency": estimate.currency,
            "issue_date": estimate.issue_date.isoformat(),
            "expiration_date": (
                estimate.expiration_date.isoformat() if estimate.expiration_date else ""
            ),
            "discount_type": estimate.discount_type,
            "discount_value": str(estimate.discount_value),
            "deposit_type": estimate.deposit_type,
            "deposit_value": str(estimate.deposit_value),
            "requires_acceptance": estimate.requires_acceptance,
            "notes": estimate.notes,
            "terms": estimate.terms,
            "subtotal": str(estimate.subtotal),
            "discount_amount": str(estimate.discount_amount),
            "tax_amount": str(estimate.tax_amount),
            "total": str(estimate.total),
            "deposit_required": str(estimate.deposit_required),
            "issued_at": estimate.issued_at.isoformat(),
        },
        "business": {
            "id": str(business.pk),
            "legal_name": business.legal_name,
            "display_name": business.display_name,
            "owner_name": business.owner_name,
            "email": business.email,
            "phone": business.phone,
            "website": business.website,
            "address": _address(
                business.address_line_1,
                business.address_line_2,
                business.city,
                business.region,
                business.postal_code,
                business.country_code,
            ),
        },
        "contact": {
            "id": str(contact.pk),
            "display_name": contact.display_name,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "company_name": contact.company_name,
            "email": contact.email,
            "phone": contact.phone,
            "address": _address(
                contact.address_line_1,
                contact.address_line_2,
                contact.city,
                contact.region,
                contact.postal_code,
                contact.country_code,
            ),
        },
        "lines": [
            {
                "id": str(line.pk),
                "position": line.position,
                "source_catalog_item_id": (
                    str(line.source_catalog_item_id)
                    if line.source_catalog_item_id
                    else ""
                ),
                "name": line.name,
                "description": line.description,
                "unit": line.unit,
                "quantity": str(line.quantity),
                "unit_rate": str(line.unit_rate),
                "is_taxable": line.is_taxable,
                "tax_rate": str(line.tax_rate),
                "line_subtotal": str(line.line_subtotal),
                "allocated_discount": str(line.allocated_discount),
                "taxable_amount": str(line.taxable_amount),
                "tax_amount": str(line.tax_amount),
                "line_total": str(line.line_total),
            }
            for line in lines
        ],
    }


def create_estimate_snapshot(*, estimate, lines):
    payload = build_estimate_snapshot_payload(estimate=estimate, lines=lines)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot = DocumentSnapshot(
        business=estimate.business,
        estimate=estimate,
        payload=payload,
        content_sha256=hashlib.sha256(canonical).hexdigest(),
    )
    snapshot.full_clean()
    snapshot.save()
    return snapshot

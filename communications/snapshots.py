import hashlib
import json

from django.core.files.storage import default_storage

from .models import DocumentSnapshot


def _address(*parts):
    return ", ".join(str(part).strip() for part in parts if str(part).strip())


def _business_payload(business):
    return {
        "id": str(business.pk),
        "legal_name": business.legal_name,
        "display_name": business.display_name,
        "owner_name": business.owner_name,
        "email": business.email,
        "phone": business.phone,
        "website": business.website,
        "logo_storage_name": business.logo.name if business.logo else "",
        "address": _address(
            business.address_line_1,
            business.address_line_2,
            business.city,
            business.region,
            business.postal_code,
            business.country_code,
        ),
    }


def _contact_payload(contact):
    return {
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
    }


def document_display_context(document):
    """Return historical parties for issued documents and live parties for drafts."""
    if not document.is_editable:
        snapshot = getattr(document, "document_snapshot", None)
        if snapshot is not None:
            return {
                "document_business": snapshot.payload["business"],
                "document_contact": snapshot.payload["contact"],
            }
    return {
        "document_business": _business_payload(document.business),
        "document_contact": _contact_payload(document.contact),
    }


def snapshot_logo_url(payload):
    """Resolve the snapshotted logo without coupling templates to storage."""
    storage_name = payload.get("business", {}).get("logo_storage_name", "")
    return default_storage.url(storage_name) if storage_name else ""


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
        "business": _business_payload(business),
        "contact": _contact_payload(contact),
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


def build_invoice_snapshot_payload(
    *, invoice, lines, business_payload=None, contact_payload=None
):
    business = invoice.business
    contact = invoice.contact
    return {
        "schema_version": 1,
        "document_type": "invoice",
        "invoice": {
            "id": str(invoice.pk),
            "number": invoice.number,
            "source_estimate_id": (
                str(invoice.source_estimate_id) if invoice.source_estimate_id else ""
            ),
            "currency": invoice.currency,
            "issue_date": invoice.issue_date.isoformat(),
            "due_date": invoice.due_date.isoformat(),
            "discount_type": invoice.discount_type,
            "discount_value": str(invoice.discount_value),
            "deposit_required": str(invoice.deposit_required),
            "notes": invoice.notes,
            "terms": invoice.terms,
            "subtotal": str(invoice.subtotal),
            "discount_amount": str(invoice.discount_amount),
            "tax_amount": str(invoice.tax_amount),
            "total": str(invoice.total),
            "issued_at": invoice.issued_at.isoformat(),
        },
        "business": business_payload or _business_payload(business),
        "contact": contact_payload or _contact_payload(contact),
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


def create_invoice_snapshot(
    *, invoice, lines, business_payload=None, contact_payload=None
):
    payload = build_invoice_snapshot_payload(
        invoice=invoice,
        lines=lines,
        business_payload=business_payload,
        contact_payload=contact_payload,
    )
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot = DocumentSnapshot(
        business=invoice.business,
        invoice=invoice,
        payload=payload,
        content_sha256=hashlib.sha256(canonical).hexdigest(),
    )
    snapshot.full_clean()
    snapshot.save()
    return snapshot

"""Render representative invoice and receipt PDFs for manual layout verification."""

import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

import django  # noqa: E402

django.setup()

from communications.pdf import (  # noqa: E402,I001
    render_invoice_pdf,
    render_payment_receipt_pdf,
)


payload = {
    "schema_version": 1,
    "document_type": "invoice",
    "invoice": {
        "id": "qa-invoice",
        "source_estimate_id": "qa-estimate",
        "number": "INV-1042",
        "currency": "USD",
        "issue_date": "2026-08-12",
        "due_date": "2026-09-11",
        "discount_type": "percentage",
        "discount_value": "10.0000",
        "deposit_required": "346.64",
        "notes": "Thank you for your business.",
        "terms": "Payment is due by the stated due date.",
        "subtotal": "1450.00",
        "discount_amount": "145.00",
        "tax_amount": "81.56",
        "total": "1386.56",
        "issued_at": "2026-08-12T12:00:00+00:00",
    },
    "business": {
        "id": "qa-business",
        "legal_name": "Provost Home Design LLC",
        "display_name": "Provost Home Design",
        "owner_name": "Morgan Provost",
        "email": "billing@example.com",
        "phone": "555-0100",
        "website": "https://example.com",
        "address": "100 Main Street, Boston, MA, 02108, US",
    },
    "contact": {
        "id": "qa-contact",
        "display_name": "Jordan Taylor",
        "first_name": "Jordan",
        "last_name": "Taylor",
        "company_name": "Taylor Renovations",
        "email": "jordan@example.com",
        "phone": "555-0134",
        "address": "200 Main Street, Suite 3, Boston, MA, 02108, US",
    },
    "lines": [
        {
            "id": "qa-line-1",
            "position": 1,
            "source_catalog_item_id": "",
            "name": "Design consultation",
            "description": "On-site discovery, measurements, and recommendations.",
            "unit": "hour",
            "quantity": "4.0000",
            "unit_rate": "125.0000",
            "is_taxable": True,
            "tax_rate": "6.2500",
            "line_subtotal": "500.00",
            "allocated_discount": "50.00",
            "taxable_amount": "450.00",
            "tax_amount": "28.13",
            "line_total": "478.13",
        },
        {
            "id": "qa-line-2",
            "position": 2,
            "source_catalog_item_id": "",
            "name": "Custom built-in planning package",
            "description": (
                "Detailed layout, materials schedule, and two client revision rounds."
            ),
            "unit": "package",
            "quantity": "1.0000",
            "unit_rate": "950.0000",
            "is_taxable": True,
            "tax_rate": "6.2500",
            "line_subtotal": "950.00",
            "allocated_discount": "95.00",
            "taxable_amount": "855.00",
            "tax_amount": "53.43",
            "line_total": "908.43",
        },
    ],
}

output_dir = Path("tmp/pdfs")
output_dir.mkdir(parents=True, exist_ok=True)
snapshot = SimpleNamespace(payload=payload)
invoice = SimpleNamespace(
    number=payload["invoice"]["number"], document_snapshot=snapshot
)
payment = SimpleNamespace(
    invoice=invoice,
    paid_on=date(2026, 8, 12),
    currency="USD",
    amount=Decimal("346.64"),
    invoice_total_snapshot=Decimal("1386.56"),
    balance_after_snapshot=Decimal("1039.92"),
    reference="ACH-20260812-1042",
    note="Deposit received. Thank you.",
    get_method_display=lambda: "ACH",
)

invoice_path = output_dir / "phase4-invoice-sample.pdf"
receipt_path = output_dir / "phase4-receipt-sample.pdf"
invoice_path.write_bytes(
    render_invoice_pdf(
        snapshot,
        amount_paid=Decimal("346.64"),
        balance_due=Decimal("1039.92"),
        effective_status="partial",
    )
)
receipt_path.write_bytes(render_payment_receipt_pdf(payment))
print(invoice_path)
print(receipt_path)

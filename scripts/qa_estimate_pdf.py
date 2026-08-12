"""Render representative estimate content for manual PDF layout verification."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

import django  # noqa: E402

django.setup()

from communications.pdf import render_estimate_pdf  # noqa: E402,I001


payload = {
    "schema_version": 1,
    "document_type": "estimate",
    "estimate": {
        "id": "qa-estimate",
        "number": "EST-1042",
        "currency": "USD",
        "issue_date": "2026-08-12",
        "expiration_date": "2026-08-26",
        "discount_type": "percentage",
        "discount_value": "10.0000",
        "deposit_type": "percentage",
        "deposit_value": "25.0000",
        "requires_acceptance": True,
        "notes": "Thank you for the opportunity to prepare this estimate.",
        "terms": (
            "Pricing is valid through the expiration date. Changes to the approved "
            "scope may require a written change order."
        ),
        "subtotal": "1450.00",
        "discount_amount": "145.00",
        "tax_amount": "81.56",
        "total": "1386.56",
        "deposit_required": "346.64",
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
            "description": "On-site discovery, measurements, and design recommendations.",
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

output_path = Path("tmp/pdfs/phase3-estimate-sample.pdf")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_bytes(render_estimate_pdf(SimpleNamespace(payload=payload)))
print(output_path)

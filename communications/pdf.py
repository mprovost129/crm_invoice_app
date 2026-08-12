import hashlib
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import FileAsset


def _register_fonts():
    fonts_path = Path(reportlab.__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(TTFont("AppSans", fonts_path / "Vera.ttf"))
    pdfmetrics.registerFont(TTFont("AppSans-Bold", fonts_path / "VeraBd.ttf"))


def _money(currency, value):
    return f"{currency} {Decimal(value):,.2f}"


def _decimal_label(value, *, places=4):
    label = f"{Decimal(value):.{places}f}".rstrip("0").rstrip(".")
    return label or "0"


def render_estimate_pdf(snapshot):
    _register_fonts()
    payload = snapshot.payload
    estimate = payload["estimate"]
    business = payload["business"]
    contact = payload["contact"]
    currency = estimate["currency"]
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=f"Estimate {estimate['number']}",
        author=business["display_name"],
    )
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "AppSans"
    styles["Heading1"].fontName = "AppSans-Bold"
    styles["Heading2"].fontName = "AppSans-Bold"
    styles.add(
        ParagraphStyle(
            name="Right",
            parent=styles["BodyText"],
            alignment=TA_RIGHT,
        )
    )

    story = [
        Table(
            [
                [
                    Paragraph(
                        f"<b>{escape(business['display_name'])}</b><br/>"
                        f"{escape(business['address'])}<br/>"
                        f"{escape(business['email'])}",
                        styles["BodyText"],
                    ),
                    Paragraph(
                        f"<font size='18'><b>ESTIMATE</b></font><br/>"
                        f"<b>{escape(estimate['number'])}</b><br/>"
                        f"Issued: {escape(estimate['issue_date'])}<br/>"
                        f"Expires: {escape(estimate['expiration_date'] or 'No expiration')}",
                        styles["Right"],
                    ),
                ]
            ],
            colWidths=[3.7 * inch, 3.1 * inch],
        ),
        Spacer(1, 0.35 * inch),
        Paragraph("Prepared for", styles["Heading2"]),
        Paragraph(
            f"<b>{escape(contact['display_name'])}</b><br/>"
            f"{escape(contact['company_name'])}<br/>"
            f"{escape(contact['address'])}<br/>"
            f"{escape(contact['email'])}",
            styles["BodyText"],
        ),
        Spacer(1, 0.3 * inch),
    ]

    rows = [["Description", "Qty", "Unit", "Rate", "Tax", "Amount"]]
    for line in payload["lines"]:
        description = f"<b>{escape(line['name'])}</b>"
        if line["description"]:
            description += f"<br/><font size='8'>{escape(line['description'])}</font>"
        rows.append(
            [
                Paragraph(description, styles["BodyText"]),
                Paragraph(_decimal_label(line["quantity"]), styles["Right"]),
                Paragraph(escape(line["unit"]), styles["Right"]),
                Paragraph(_money(currency, line["unit_rate"]), styles["Right"]),
                Paragraph(
                    f"{_decimal_label(line['tax_rate'])}%"
                    if line["is_taxable"]
                    else "No",
                    styles["Right"],
                ),
                Paragraph(_money(currency, line["line_total"]), styles["Right"]),
            ]
        )
    line_table = Table(
        rows,
        colWidths=[
            2.4 * inch,
            0.55 * inch,
            0.8 * inch,
            1.15 * inch,
            0.7 * inch,
            1.2 * inch,
        ],
        repeatRows=1,
    )
    line_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "AppSans-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "AppSans"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f8fafc")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([line_table, Spacer(1, 0.25 * inch)])

    totals = [
        ["Subtotal", _money(currency, estimate["subtotal"])],
        ["Discount", f"- {_money(currency, estimate['discount_amount'])}"],
        ["Tax", _money(currency, estimate["tax_amount"])],
        ["Total", _money(currency, estimate["total"])],
    ]
    if estimate["deposit_required"] != "0.00":
        totals.append(
            ["Requested deposit", _money(currency, estimate["deposit_required"])]
        )
    totals_table = Table(totals, colWidths=[1.4 * inch, 1.6 * inch], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "AppSans"),
                ("FONTNAME", (0, -1), (-1, -1), "AppSans-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#111827")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(totals_table)

    for heading, text in (("Notes", estimate["notes"]), ("Terms", estimate["terms"])):
        if text:
            story.extend(
                [
                    Spacer(1, 0.25 * inch),
                    KeepTogether(
                        [
                            Paragraph(heading, styles["Heading2"]),
                            Paragraph(
                                escape(text).replace("\n", "<br/>"), styles["BodyText"]
                            ),
                        ]
                    ),
                ]
            )

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("AppSans", 8)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawRightString(
            LETTER[0] - 0.65 * inch,
            0.35 * inch,
            f"Estimate {estimate['number']} - Page {doc.page}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()


def get_or_create_estimate_pdf(*, estimate):
    snapshot = estimate.document_snapshot
    existing = (
        FileAsset.objects.filter(
            estimate=estimate,
            snapshot=snapshot,
            kind=FileAsset.Kind.ESTIMATE_PDF,
        )
        .order_by("created_at")
        .first()
    )
    if existing:
        return existing

    pdf_bytes = render_estimate_pdf(snapshot)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    desired_name = (
        f"documents/{estimate.business_id}/estimates/{estimate.pk}/"
        f"{snapshot.content_sha256}.pdf"
    )
    storage_name = default_storage.save(desired_name, ContentFile(pdf_bytes))
    asset = FileAsset(
        business=estimate.business,
        estimate=estimate,
        snapshot=snapshot,
        kind=FileAsset.Kind.ESTIMATE_PDF,
        storage_name=storage_name,
        byte_size=len(pdf_bytes),
        content_sha256=digest,
    )
    asset.full_clean()
    asset.save()
    return asset


def render_invoice_pdf(snapshot, *, amount_paid, balance_due, effective_status):
    _register_fonts()
    payload = snapshot.payload
    invoice = payload["invoice"]
    business = payload["business"]
    contact = payload["contact"]
    currency = invoice["currency"]
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=f"Invoice {invoice['number']}",
        author=business["display_name"],
    )
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "AppSans"
    styles["Heading2"].fontName = "AppSans-Bold"
    styles.add(
        ParagraphStyle(
            name="InvoiceRight", parent=styles["BodyText"], alignment=TA_RIGHT
        )
    )
    right = styles["InvoiceRight"]
    story = [
        Table(
            [
                [
                    Paragraph(
                        f"<b>{escape(business['display_name'])}</b><br/>"
                        f"{escape(business['address'])}<br/>"
                        f"{escape(business['email'])}",
                        styles["BodyText"],
                    ),
                    Paragraph(
                        f"<font size='18'><b>INVOICE</b></font><br/>"
                        f"<b>{escape(invoice['number'])}</b><br/>"
                        f"Issued: {escape(invoice['issue_date'])}<br/>"
                        f"Due: {escape(invoice['due_date'])}<br/>"
                        f"Status: {escape(str(effective_status).replace('_', ' ').title())}",
                        right,
                    ),
                ]
            ],
            colWidths=[3.7 * inch, 3.1 * inch],
        ),
        Spacer(1, 0.35 * inch),
        Paragraph("Bill to", styles["Heading2"]),
        Paragraph(
            f"<b>{escape(contact['display_name'])}</b><br/>"
            f"{escape(contact['company_name'])}<br/>"
            f"{escape(contact['address'])}<br/>"
            f"{escape(contact['email'])}",
            styles["BodyText"],
        ),
        Spacer(1, 0.3 * inch),
    ]
    rows = [["Description", "Qty", "Unit", "Rate", "Tax", "Amount"]]
    for line in payload["lines"]:
        description = f"<b>{escape(line['name'])}</b>"
        if line["description"]:
            description += f"<br/><font size='8'>{escape(line['description'])}</font>"
        rows.append(
            [
                Paragraph(description, styles["BodyText"]),
                Paragraph(_decimal_label(line["quantity"]), right),
                Paragraph(escape(line["unit"]), right),
                Paragraph(_money(currency, line["unit_rate"]), right),
                Paragraph(
                    f"{_decimal_label(line['tax_rate'])}%"
                    if line["is_taxable"]
                    else "No",
                    right,
                ),
                Paragraph(_money(currency, line["line_total"]), right),
            ]
        )
    line_table = Table(
        rows,
        colWidths=[
            2.4 * inch,
            0.55 * inch,
            0.8 * inch,
            1.15 * inch,
            0.7 * inch,
            1.2 * inch,
        ],
        repeatRows=1,
    )
    line_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "AppSans-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "AppSans"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f8fafc")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([line_table, Spacer(1, 0.25 * inch)])
    totals = [
        ["Subtotal", _money(currency, invoice["subtotal"])],
        ["Discount", f"- {_money(currency, invoice['discount_amount'])}"],
        ["Tax", _money(currency, invoice["tax_amount"])],
        ["Total", _money(currency, invoice["total"])],
        ["Paid", f"- {_money(currency, amount_paid)}"],
        ["Balance due", _money(currency, balance_due)],
    ]
    totals_table = Table(totals, colWidths=[1.4 * inch, 1.6 * inch], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "AppSans"),
                ("FONTNAME", (0, -1), (-1, -1), "AppSans-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#111827")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(totals_table)
    for heading, value in (("Notes", invoice["notes"]), ("Terms", invoice["terms"])):
        if value:
            story.extend(
                [
                    Spacer(1, 0.25 * inch),
                    KeepTogether(
                        [
                            Paragraph(heading, styles["Heading2"]),
                            Paragraph(
                                escape(value).replace("\n", "<br/>"),
                                styles["BodyText"],
                            ),
                        ]
                    ),
                ]
            )

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("AppSans", 8)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawRightString(
            LETTER[0] - 0.65 * inch,
            0.35 * inch,
            f"Invoice {invoice['number']} - Page {doc.page}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()


def get_or_create_invoice_pdf(*, invoice):
    snapshot = invoice.document_snapshot
    render_key = hashlib.sha256(
        "|".join(
            (
                snapshot.content_sha256,
                str(invoice.amount_paid),
                str(invoice.balance_due),
                invoice.effective_status,
            )
        ).encode("utf-8")
    ).hexdigest()
    storage_prefix = (
        f"documents/{invoice.business_id}/invoices/{invoice.pk}/{render_key}/"
    )
    existing = FileAsset.objects.filter(
        invoice=invoice,
        kind=FileAsset.Kind.INVOICE_PDF,
        storage_name__startswith=storage_prefix,
    ).first()
    if existing:
        return existing
    pdf_bytes = render_invoice_pdf(
        snapshot,
        amount_paid=invoice.amount_paid,
        balance_due=invoice.balance_due,
        effective_status=invoice.effective_status,
    )
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    desired_name = f"{storage_prefix}invoice.pdf"
    storage_name = default_storage.save(desired_name, ContentFile(pdf_bytes))
    asset = FileAsset(
        business=invoice.business,
        invoice=invoice,
        snapshot=snapshot,
        kind=FileAsset.Kind.INVOICE_PDF,
        storage_name=storage_name,
        byte_size=len(pdf_bytes),
        content_sha256=digest,
    )
    asset.full_clean()
    asset.save()
    return asset


def render_payment_receipt_pdf(payment):
    _register_fonts()
    invoice = payment.invoice
    snapshot = invoice.document_snapshot.payload
    business = snapshot["business"]
    contact = snapshot["contact"]
    currency = payment.currency
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.8 * inch,
        leftMargin=0.8 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title=f"Receipt for {invoice.number}",
        author=business["display_name"],
    )
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "AppSans"
    styles["Heading1"].fontName = "AppSans-Bold"
    styles["Heading2"].fontName = "AppSans-Bold"
    story = [
        Paragraph("PAYMENT RECEIPT", styles["Heading1"]),
        Paragraph(
            f"<b>{escape(business['display_name'])}</b><br/>"
            f"{escape(business['address'])}<br/>"
            f"{escape(business['email'])}",
            styles["BodyText"],
        ),
        Spacer(1, 0.4 * inch),
        Paragraph(
            f"Received from {escape(contact['display_name'])}", styles["Heading2"]
        ),
        Spacer(1, 0.1 * inch),
    ]
    rows = [
        ["Payment date", payment.paid_on.isoformat()],
        ["Invoice", invoice.number],
        ["Method", payment.get_method_display()],
        ["Reference", payment.reference or "-"],
        ["Amount received", _money(currency, payment.amount)],
        ["Invoice total", _money(currency, payment.invoice_total_snapshot)],
        ["Balance after payment", _money(currency, payment.balance_after_snapshot)],
    ]
    table = Table(rows, colWidths=[2.1 * inch, 3.8 * inch], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "AppSans-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "AppSans"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(table)
    if payment.note:
        story.extend(
            [
                Spacer(1, 0.3 * inch),
                Paragraph("Note", styles["Heading2"]),
                Paragraph(
                    escape(payment.note).replace("\n", "<br/>"), styles["BodyText"]
                ),
            ]
        )
    story.extend(
        [
            Spacer(1, 0.5 * inch),
            Paragraph(
                "Thank you. This receipt documents a recorded payment and is not a "
                "credit-card processing statement.",
                styles["BodyText"],
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()


def get_or_create_payment_receipt_pdf(*, payment):
    existing = FileAsset.objects.filter(
        payment=payment,
        kind=FileAsset.Kind.PAYMENT_RECEIPT,
    ).first()
    if existing:
        return existing
    pdf_bytes = render_payment_receipt_pdf(payment)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    desired_name = f"documents/{payment.business_id}/receipts/{payment.pk}/{digest}.pdf"
    storage_name = default_storage.save(desired_name, ContentFile(pdf_bytes))
    asset = FileAsset(
        business=payment.business,
        payment=payment,
        kind=FileAsset.Kind.PAYMENT_RECEIPT,
        storage_name=storage_name,
        byte_size=len(pdf_bytes),
        content_sha256=digest,
    )
    asset.full_clean()
    asset.save()
    return asset

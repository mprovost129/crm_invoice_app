from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_activity
from billing.entitlements import entitlements_for_business
from catalog.models import ProductService
from communications.models import PublicDocumentLink
from communications.snapshots import create_invoice_snapshot
from core.models import DocumentSequence
from core.services import allocate_document_number
from crm.models import Contact
from estimates.calculations import LineInput, calculate_estimate
from estimates.models import Estimate
from workspaces.policies import owner_business_for_actor

from .models import Invoice, InvoiceLineItem

INVOICE_FIELDS = (
    "contact_id",
    "due_date",
    "discount_type",
    "discount_value",
    "deposit_required",
    "notes",
    "terms",
)

LINE_FIELDS = (
    "name",
    "description",
    "unit",
    "quantity",
    "unit_rate",
    "is_taxable",
    "tax_rate",
)


def _business_today(business):
    return timezone.localdate(timezone=ZoneInfo(business.timezone))


def _contact_for_business(*, business, contact_id):
    contact = Contact.objects.for_business(business).filter(pk=contact_id).first()
    if contact is None or contact.status == Contact.Status.ARCHIVED:
        raise ValidationError("Select an active lead or client.")
    return contact


def _draft_for_update(*, actor, business_id, invoice_id):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    invoice = (
        Invoice.objects.select_for_update()
        .for_business(business)
        .select_related("contact", "business")
        .filter(pk=invoice_id)
        .first()
    )
    if invoice is None:
        raise PermissionDenied("Invoice access is required.")
    if not invoice.is_editable:
        raise ValidationError("Issued invoices are immutable.")
    return business, invoice


def _catalog_item(*, business, item_id):
    if not item_id:
        return None
    item = (
        ProductService.objects.for_business(business)
        .active()
        .filter(pk=item_id)
        .first()
    )
    if item is None:
        raise ValidationError("Select an active catalog item from this business.")
    return item


def _recalculate(invoice):
    lines = list(
        InvoiceLineItem.objects.select_for_update()
        .filter(invoice=invoice)
        .order_by("position")
    )
    try:
        calculation = calculate_estimate(
            [
                LineInput(
                    quantity=line.quantity,
                    unit_rate=line.unit_rate,
                    is_taxable=line.is_taxable,
                    tax_rate=line.tax_rate,
                )
                for line in lines
            ],
            discount_type=invoice.discount_type,
            discount_value=invoice.discount_value,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    for line, result in zip(lines, calculation.lines, strict=True):
        line.line_subtotal = result.line_subtotal
        line.allocated_discount = result.allocated_discount
        line.taxable_amount = result.taxable_amount
        line.tax_amount = result.tax_amount
        line.line_total = result.line_total
        line.full_clean()
        line.save()
    invoice.subtotal = calculation.subtotal
    invoice.discount_amount = calculation.discount_amount
    invoice.tax_amount = calculation.tax_amount
    invoice.total = calculation.total
    invoice.amount_paid = Decimal("0")
    invoice.balance_due = calculation.total
    invoice.full_clean()
    invoice.save()
    return lines


def _promote_contact_if_needed(*, contact, business, actor):
    if contact.status != Contact.Status.LEAD:
        return
    contact.status = Contact.Status.CLIENT
    contact.converted_at = timezone.now()
    contact.full_clean()
    contact.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.CONTACT_STATUS_CHANGED,
        summary=f"Converted {contact.display_name} from lead to client.",
        contact=contact,
        metadata={"from": Contact.Status.LEAD, "to": Contact.Status.CLIENT},
    )


@transaction.atomic
def create_invoice(*, actor, business_id, data):
    business = owner_business_for_actor(actor=actor, business_id=business_id, lock=True)
    entitlements = entitlements_for_business(business=business)
    monthly_limit = entitlements.plan.monthly_invoice_limit
    if monthly_limit is not None:
        business_zone = ZoneInfo(business.timezone)
        local_month_start = _business_today(business).replace(day=1)
        next_month = (local_month_start.replace(day=28) + timedelta(days=4)).replace(
            day=1
        )
        month_start = datetime.combine(local_month_start, time.min, business_zone)
        month_end = datetime.combine(next_month, time.min, business_zone)
        if (
            Invoice.objects.for_business(business)
            .filter(created_at__gte=month_start, created_at__lt=month_end)
            .count()
            >= monthly_limit
        ):
            raise ValidationError(
                f"The {entitlements.plan.name} plan allows {monthly_limit} invoices per month."
            )
    contact = _contact_for_business(business=business, contact_id=data["contact_id"])
    today = _business_today(business)
    invoice = Invoice(
        business=business,
        contact=contact,
        currency=business.default_currency,
        issue_date=today,
        due_date=data.get("due_date")
        or today + timedelta(days=business.settings.default_payment_terms_days),
        discount_type=data.get("discount_type", Invoice.AmountType.NONE),
        discount_value=data.get("discount_value", Decimal("0")),
        deposit_required=data.get("deposit_required", Decimal("0")),
        notes=data.get("notes", business.settings.default_invoice_notes),
        terms=data.get("terms", business.settings.default_invoice_terms),
        created_by=actor,
    )
    invoice.full_clean()
    invoice.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.INVOICE_CREATED,
        summary=f"Created a draft invoice for {contact.display_name}.",
        invoice=invoice,
    )
    return invoice


@transaction.atomic
def update_invoice(*, actor, business_id, invoice_id, data):
    business, invoice = _draft_for_update(
        actor=actor, business_id=business_id, invoice_id=invoice_id
    )
    invoice.contact = _contact_for_business(
        business=business, contact_id=data["contact_id"]
    )
    for field in INVOICE_FIELDS[1:]:
        setattr(invoice, field, data[field])
    _recalculate(invoice)
    return invoice


@transaction.atomic
def add_invoice_line(*, actor, business_id, invoice_id, data):
    business, invoice = _draft_for_update(
        actor=actor, business_id=business_id, invoice_id=invoice_id
    )
    item = _catalog_item(business=business, item_id=data.get("source_catalog_item_id"))
    position = (
        InvoiceLineItem.objects.filter(invoice=invoice).aggregate(Max("position"))[
            "position__max"
        ]
        or 0
    ) + 1
    line = InvoiceLineItem(
        business=business,
        invoice=invoice,
        source_catalog_item=item,
        position=position,
        **{field: data[field] for field in LINE_FIELDS},
    )
    line.full_clean()
    line.save()
    _recalculate(invoice)
    line.refresh_from_db()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.INVOICE_LINE_CHANGED,
        summary=f"Added {line.name} to the draft invoice.",
        invoice=invoice,
        metadata={"action": "added", "line_id": str(line.pk)},
    )
    return line


@transaction.atomic
def update_invoice_line(*, actor, business_id, invoice_id, line_id, data):
    business, invoice = _draft_for_update(
        actor=actor, business_id=business_id, invoice_id=invoice_id
    )
    line = (
        InvoiceLineItem.objects.select_for_update()
        .filter(pk=line_id, invoice=invoice, business=business)
        .first()
    )
    if line is None:
        raise PermissionDenied("Invoice line access is required.")
    line.source_catalog_item = _catalog_item(
        business=business, item_id=data.get("source_catalog_item_id")
    )
    for field in LINE_FIELDS:
        setattr(line, field, data[field])
    line.full_clean()
    line.save()
    _recalculate(invoice)
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.INVOICE_LINE_CHANGED,
        summary=f"Updated {line.name} on the draft invoice.",
        invoice=invoice,
        metadata={"action": "updated", "line_id": str(line.pk)},
    )
    return line


@transaction.atomic
def delete_invoice_line(*, actor, business_id, invoice_id, line_id):
    business, invoice = _draft_for_update(
        actor=actor, business_id=business_id, invoice_id=invoice_id
    )
    line = (
        InvoiceLineItem.objects.select_for_update()
        .filter(pk=line_id, invoice=invoice, business=business)
        .first()
    )
    if line is None:
        raise PermissionDenied("Invoice line access is required.")
    line_name = line.name
    line.delete()
    for position, remaining in enumerate(
        InvoiceLineItem.objects.select_for_update()
        .filter(invoice=invoice)
        .order_by("position"),
        start=1,
    ):
        if remaining.position != position:
            remaining.position = position
            remaining.save(update_fields=("position", "updated_at"))
    _recalculate(invoice)
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.INVOICE_LINE_CHANGED,
        summary=f"Removed {line_name} from the draft invoice.",
        invoice=invoice,
        metadata={"action": "removed"},
    )


def _issue_locked_invoice(*, business, invoice, actor):
    lines = _recalculate(invoice)
    if not lines:
        raise ValidationError("Add at least one line before issuing the invoice.")
    if invoice.total <= 0:
        raise ValidationError("Invoice total must be greater than zero.")
    today = _business_today(business)
    if invoice.due_date and invoice.due_date < today:
        raise ValidationError("Due date cannot be before the issue date.")
    invoice.number = allocate_document_number(
        business=business,
        document_type=DocumentSequence.DocumentType.INVOICE,
    )
    invoice.issue_date = today
    invoice.status = Invoice.Status.SENT
    invoice.issued_at = timezone.now()
    invoice.balance_due = invoice.total
    invoice.full_clean()
    invoice.save()
    _promote_contact_if_needed(contact=invoice.contact, business=business, actor=actor)
    create_invoice_snapshot(invoice=invoice, lines=lines)
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.INVOICE_ISSUED,
        summary=f"Issued invoice {invoice.number}.",
        invoice=invoice,
        metadata={"number": invoice.number},
    )
    return invoice


@transaction.atomic
def issue_invoice(*, actor, business_id, invoice_id):
    business, invoice = _draft_for_update(
        actor=actor, business_id=business_id, invoice_id=invoice_id
    )
    return _issue_locked_invoice(business=business, invoice=invoice, actor=actor)


@transaction.atomic
def convert_estimate_to_invoice(*, actor, business_id, estimate_id):
    business = owner_business_for_actor(actor=actor, business_id=business_id, lock=True)
    estimate = (
        Estimate.objects.select_for_update()
        .for_business(business)
        .select_related("contact", "business")
        .filter(pk=estimate_id)
        .first()
    )
    if estimate is None:
        raise PermissionDenied("Estimate access is required.")
    existing = Invoice.objects.filter(source_estimate=estimate).first()
    if existing:
        return existing
    allowed_without_acceptance = (
        not estimate.requires_acceptance
        and estimate.status in (Estimate.Status.SENT, Estimate.Status.VIEWED)
        and estimate.effective_status != "expired"
    )
    if estimate.status != Estimate.Status.ACCEPTED and not allowed_without_acceptance:
        raise ValidationError("Accept the estimate before converting it.")
    estimate_lines = list(estimate.line_items.select_for_update().order_by("position"))
    if not estimate_lines:
        raise ValidationError("The estimate has no line items.")
    source_snapshot = estimate.document_snapshot.payload
    source_estimate = source_snapshot["estimate"]
    today = _business_today(business)
    invoice = Invoice(
        business=business,
        contact=estimate.contact,
        source_estimate=estimate,
        number=allocate_document_number(
            business=business,
            document_type=DocumentSequence.DocumentType.INVOICE,
        ),
        status=Invoice.Status.SENT,
        currency=source_estimate["currency"],
        issue_date=today,
        due_date=today + timedelta(days=business.settings.default_payment_terms_days),
        discount_type=source_estimate["discount_type"],
        discount_value=Decimal(source_estimate["discount_value"]),
        deposit_required=Decimal(source_estimate["deposit_required"]),
        notes=source_estimate["notes"],
        terms=source_estimate["terms"],
        subtotal=Decimal(source_estimate["subtotal"]),
        discount_amount=Decimal(source_estimate["discount_amount"]),
        tax_amount=Decimal(source_estimate["tax_amount"]),
        total=Decimal(source_estimate["total"]),
        amount_paid=Decimal("0"),
        balance_due=Decimal(source_estimate["total"]),
        issued_at=timezone.now(),
        created_by=actor,
    )
    invoice.full_clean()
    invoice.save()
    invoice_lines = []
    live_lines = {str(line.pk): line for line in estimate_lines}
    for source in source_snapshot["lines"]:
        live_source = live_lines[source["id"]]
        line = InvoiceLineItem(
            business=business,
            invoice=invoice,
            source_catalog_item=live_source.source_catalog_item,
            position=source["position"],
            name=source["name"],
            description=source["description"],
            unit=source["unit"],
            quantity=Decimal(source["quantity"]),
            unit_rate=Decimal(source["unit_rate"]),
            is_taxable=source["is_taxable"],
            tax_rate=Decimal(source["tax_rate"]),
            line_subtotal=Decimal(source["line_subtotal"]),
            allocated_discount=Decimal(source["allocated_discount"]),
            taxable_amount=Decimal(source["taxable_amount"]),
            tax_amount=Decimal(source["tax_amount"]),
            line_total=Decimal(source["line_total"]),
        )
        line.full_clean()
        line.save()
        invoice_lines.append(line)
    create_invoice_snapshot(
        invoice=invoice,
        lines=invoice_lines,
        business_payload=source_snapshot["business"],
        contact_payload=source_snapshot["contact"],
    )
    estimate.status = Estimate.Status.CONVERTED
    estimate.save(update_fields=("status", "updated_at"))
    PublicDocumentLink.objects.filter(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.RESPOND,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())
    _promote_contact_if_needed(
        contact=estimate.contact,
        business=business,
        actor=actor,
    )
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_CONVERTED,
        summary=f"Converted estimate {estimate.number} to invoice {invoice.number}.",
        estimate=estimate,
        metadata={"invoice_id": str(invoice.pk), "invoice_number": invoice.number},
    )
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.INVOICE_CREATED,
        summary=f"Created invoice {invoice.number} from estimate {estimate.number}.",
        invoice=invoice,
        metadata={"estimate_id": str(estimate.pk), "estimate_number": estimate.number},
    )
    return invoice


@transaction.atomic
def void_invoice(*, actor, business_id, invoice_id, reason):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    invoice = (
        Invoice.objects.select_for_update()
        .for_business(business)
        .filter(pk=invoice_id)
        .first()
    )
    if invoice is None:
        raise PermissionDenied("Invoice access is required.")
    if invoice.status == Invoice.Status.DRAFT:
        raise ValidationError("Delete or edit a draft instead of voiding it.")
    if invoice.status == Invoice.Status.VOID:
        raise ValidationError("Invoice is already void.")
    if invoice.amount_paid > 0:
        raise ValidationError("Reverse all payments before voiding the invoice.")
    invoice.status = Invoice.Status.VOID
    invoice.voided_at = timezone.now()
    invoice.void_reason = reason.strip()
    invoice.full_clean()
    invoice.save()
    PublicDocumentLink.objects.filter(
        invoice=invoice,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.INVOICE_VOIDED,
        summary=f"Voided invoice {invoice.number}.",
        invoice=invoice,
        metadata={"reason": invoice.void_reason},
    )
    return invoice

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
from communications.models import Notification, PublicDocumentLink
from communications.notifications import notify_business_owner
from communications.snapshots import create_estimate_snapshot
from core.models import DocumentSequence
from core.services import allocate_document_number
from crm.models import Contact
from workspaces.policies import owner_business_for_actor

from .calculations import LineInput, calculate_estimate
from .models import Estimate, EstimateAcceptance, EstimateLineItem

ESTIMATE_FIELDS = (
    "contact_id",
    "expiration_date",
    "discount_type",
    "discount_value",
    "deposit_type",
    "deposit_value",
    "requires_acceptance",
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


def _contact_for_business(*, business, contact_id):
    contact = Contact.objects.for_business(business).filter(pk=contact_id).first()
    if contact is None or contact.status == Contact.Status.ARCHIVED:
        raise ValidationError("Select an active lead or client.")
    return contact


def _draft_for_update(*, actor, business_id, estimate_id):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    estimate = (
        Estimate.objects.select_for_update()
        .for_business(business)
        .select_related("contact", "business")
        .filter(pk=estimate_id)
        .first()
    )
    if estimate is None:
        raise PermissionDenied("Estimate access is required.")
    if not estimate.is_editable:
        raise ValidationError("Issued estimates are immutable.")
    return business, estimate


def _recalculate(estimate):
    lines = list(
        EstimateLineItem.objects.select_for_update()
        .filter(estimate=estimate)
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
            discount_type=estimate.discount_type,
            discount_value=estimate.discount_value,
            deposit_type=estimate.deposit_type,
            deposit_value=estimate.deposit_value,
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

    estimate.subtotal = calculation.subtotal
    estimate.discount_amount = calculation.discount_amount
    estimate.tax_amount = calculation.tax_amount
    estimate.total = calculation.total
    estimate.deposit_required = calculation.deposit_required
    estimate.full_clean()
    estimate.save()
    return lines


@transaction.atomic
def create_estimate(*, actor, business_id, data):
    business = owner_business_for_actor(
        actor=actor,
        business_id=business_id,
        lock=True,
    )
    entitlements = entitlements_for_business(business=business)
    monthly_limit = entitlements.plan.monthly_estimate_limit
    if monthly_limit is not None:
        business_zone = ZoneInfo(business.timezone)
        local_month_start = timezone.localdate(timezone=business_zone).replace(day=1)
        next_month = (local_month_start.replace(day=28) + timedelta(days=4)).replace(
            day=1
        )
        month_start = datetime.combine(local_month_start, time.min, business_zone)
        month_end = datetime.combine(next_month, time.min, business_zone)
        if Estimate.objects.for_business(business).filter(
            created_at__gte=month_start, created_at__lt=month_end
        ).count() >= monthly_limit:
            raise ValidationError(
                f"The {entitlements.plan.name} plan allows {monthly_limit} estimates per month."
            )
    contact = _contact_for_business(business=business, contact_id=data["contact_id"])
    business_today = timezone.localdate(timezone=ZoneInfo(business.timezone))
    expiration_date = data.get("expiration_date") or (
        business_today
        + timedelta(days=business.settings.default_estimate_expiration_days)
    )
    estimate = Estimate(
        business=business,
        contact=contact,
        currency=business.default_currency,
        issue_date=business_today,
        expiration_date=expiration_date,
        discount_type=data.get("discount_type", Estimate.AmountType.NONE),
        discount_value=data.get("discount_value", Decimal("0")),
        deposit_type=data.get("deposit_type", Estimate.AmountType.NONE),
        deposit_value=data.get("deposit_value", Decimal("0")),
        requires_acceptance=data.get("requires_acceptance", True),
        notes=data.get("notes", business.settings.default_estimate_notes),
        terms=data.get("terms", business.settings.default_estimate_terms),
        created_by=actor,
    )
    estimate.full_clean()
    estimate.save()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_CREATED,
        summary=f"Created a draft estimate for {contact.display_name}.",
        estimate=estimate,
    )
    return estimate


@transaction.atomic
def update_estimate(*, actor, business_id, estimate_id, data):
    business, estimate = _draft_for_update(
        actor=actor,
        business_id=business_id,
        estimate_id=estimate_id,
    )
    contact = _contact_for_business(business=business, contact_id=data["contact_id"])
    estimate.contact = contact
    for field in ESTIMATE_FIELDS[1:]:
        setattr(estimate, field, data[field])
    _recalculate(estimate)
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_UPDATED,
        summary=f"Updated draft estimate for {contact.display_name}.",
        estimate=estimate,
    )
    return estimate


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


@transaction.atomic
def add_estimate_line(*, actor, business_id, estimate_id, data):
    business, estimate = _draft_for_update(
        actor=actor,
        business_id=business_id,
        estimate_id=estimate_id,
    )
    item = _catalog_item(
        business=business,
        item_id=data.get("source_catalog_item_id"),
    )
    position = (
        EstimateLineItem.objects.filter(estimate=estimate).aggregate(Max("position"))[
            "position__max"
        ]
        or 0
    ) + 1
    line = EstimateLineItem(
        business=business,
        estimate=estimate,
        source_catalog_item=item,
        position=position,
        **{field: data[field] for field in LINE_FIELDS},
    )
    line.full_clean()
    line.save()
    _recalculate(estimate)
    line.refresh_from_db()
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_LINE_CHANGED,
        summary=f"Added {line.name} to the draft estimate.",
        estimate=estimate,
        metadata={"action": "added", "line_id": str(line.pk)},
    )
    return line


@transaction.atomic
def update_estimate_line(*, actor, business_id, estimate_id, line_id, data):
    business, estimate = _draft_for_update(
        actor=actor,
        business_id=business_id,
        estimate_id=estimate_id,
    )
    line = (
        EstimateLineItem.objects.select_for_update()
        .filter(pk=line_id, estimate=estimate, business=business)
        .first()
    )
    if line is None:
        raise PermissionDenied("Estimate line access is required.")
    line.source_catalog_item = _catalog_item(
        business=business,
        item_id=data.get("source_catalog_item_id"),
    )
    for field in LINE_FIELDS:
        setattr(line, field, data[field])
    line.full_clean()
    line.save()
    _recalculate(estimate)
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_LINE_CHANGED,
        summary=f"Updated {line.name} on the draft estimate.",
        estimate=estimate,
        metadata={"action": "updated", "line_id": str(line.pk)},
    )
    return line


@transaction.atomic
def delete_estimate_line(*, actor, business_id, estimate_id, line_id):
    business, estimate = _draft_for_update(
        actor=actor,
        business_id=business_id,
        estimate_id=estimate_id,
    )
    line = (
        EstimateLineItem.objects.select_for_update()
        .filter(pk=line_id, estimate=estimate, business=business)
        .first()
    )
    if line is None:
        raise PermissionDenied("Estimate line access is required.")
    line_name = line.name
    line.delete()
    for position, remaining in enumerate(
        EstimateLineItem.objects.select_for_update()
        .filter(estimate=estimate)
        .order_by("position"),
        start=1,
    ):
        if remaining.position != position:
            remaining.position = position
            remaining.save(update_fields=("position", "updated_at"))
    _recalculate(estimate)
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_LINE_CHANGED,
        summary=f"Removed {line_name} from the draft estimate.",
        estimate=estimate,
        metadata={"action": "removed"},
    )


@transaction.atomic
def issue_estimate(*, actor, business_id, estimate_id):
    business, estimate = _draft_for_update(
        actor=actor,
        business_id=business_id,
        estimate_id=estimate_id,
    )
    lines = _recalculate(estimate)
    if not lines:
        raise ValidationError("Add at least one line before issuing the estimate.")
    if estimate.total <= 0:
        raise ValidationError("Estimate total must be greater than zero.")
    estimate.number = allocate_document_number(
        business=business,
        document_type=DocumentSequence.DocumentType.ESTIMATE,
    )
    estimate.issue_date = timezone.localdate(timezone=ZoneInfo(business.timezone))
    estimate.status = Estimate.Status.SENT
    estimate.issued_at = timezone.now()
    estimate.full_clean()
    estimate.save()
    create_estimate_snapshot(estimate=estimate, lines=lines)
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_ISSUED,
        summary=f"Issued estimate {estimate.number}.",
        estimate=estimate,
        metadata={"number": estimate.number},
    )
    return estimate


def _issued_for_update(*, actor, business_id, estimate_id):
    business = owner_business_for_actor(actor=actor, business_id=business_id)
    estimate = (
        Estimate.objects.select_for_update()
        .for_business(business)
        .select_related("business")
        .filter(pk=estimate_id)
        .first()
    )
    if estimate is None:
        raise PermissionDenied("Estimate access is required.")
    if estimate.status not in (Estimate.Status.SENT, Estimate.Status.VIEWED):
        raise ValidationError("Estimate cannot be accepted in its current state.")
    if estimate.effective_status == "expired":
        raise ValidationError("Expired estimates cannot be accepted.")
    return business, estimate


@transaction.atomic
def record_manual_acceptance(
    *, actor, business_id, estimate_id, method, accepted_by_name="", metadata=None
):
    business, estimate = _issued_for_update(
        actor=actor,
        business_id=business_id,
        estimate_id=estimate_id,
    )
    if method == EstimateAcceptance.Method.ONLINE:
        raise ValidationError("Use online acceptance only for a public response.")
    acceptance = EstimateAcceptance(
        business=business,
        estimate=estimate,
        method=method,
        accepted_by_name=accepted_by_name.strip(),
        recorded_by=actor,
        terms_snapshot=estimate.document_snapshot.payload["estimate"]["terms"],
        total_snapshot=estimate.total,
        metadata=metadata or {},
    )
    acceptance.full_clean()
    acceptance.save()
    estimate.status = Estimate.Status.ACCEPTED
    estimate.accepted_at = acceptance.accepted_at
    estimate.save()
    PublicDocumentLink.objects.filter(
        estimate=estimate,
        purpose=PublicDocumentLink.Purpose.RESPOND,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())
    record_activity(
        business=business,
        actor=actor,
        event_type=ActivityEvent.EventType.ESTIMATE_ACCEPTED,
        summary=f"Recorded {method.replace('_', ' ')} acceptance for {estimate.number}.",
        estimate=estimate,
        metadata={"method": method},
    )
    notify_business_owner(
        business=business,
        kind=Notification.Kind.ESTIMATE_ACCEPTED,
        title=f"Estimate {estimate.number} accepted",
        body="The estimate was accepted and is ready to convert to an invoice.",
        target_path=f"/app/estimates/{estimate.pk}/",
        dedupe_key=f"estimate-accepted:{estimate.pk}",
    )
    return acceptance

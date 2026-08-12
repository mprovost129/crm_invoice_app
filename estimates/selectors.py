from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from .models import Estimate


def estimates_for_business(*, business, search="", status=""):
    estimates = Estimate.objects.for_business(business).select_related(
        "business", "contact"
    )
    if search:
        estimates = estimates.filter(
            Q(number__icontains=search)
            | Q(contact__first_name__icontains=search)
            | Q(contact__last_name__icontains=search)
            | Q(contact__company_name__icontains=search)
            | Q(contact__email__icontains=search)
            | Q(contact__phone__icontains=search)
        )
    if status == "expired":
        today = timezone.localdate(timezone=ZoneInfo(business.timezone))
        return estimates.filter(
            status__in=(Estimate.Status.SENT, Estimate.Status.VIEWED),
            expiration_date__lt=today,
        )
    if status in Estimate.Status.values:
        estimates = estimates.filter(status=status)
    return estimates


def estimate_for_business(*, business, estimate_id):
    return (
        Estimate.objects.for_business(business)
        .select_related("business", "contact")
        .prefetch_related("line_items")
        .filter(pk=estimate_id)
        .first()
    )

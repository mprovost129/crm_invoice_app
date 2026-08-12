from django.db.models import Q

from .models import Estimate


def estimates_for_business(*, business, search="", status=""):
    estimates = Estimate.objects.for_business(business).select_related("contact")
    if search:
        estimates = estimates.filter(
            Q(number__icontains=search)
            | Q(contact__first_name__icontains=search)
            | Q(contact__last_name__icontains=search)
            | Q(contact__company_name__icontains=search)
        )
    if status == "expired":
        candidates = estimates.filter(
            status__in=(Estimate.Status.SENT, Estimate.Status.VIEWED)
        )
        return [
            estimate
            for estimate in candidates
            if estimate.effective_status == "expired"
        ]
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

import hashlib

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, ListView, TemplateView

from catalog.models import ProductService
from communications.emailing import queue_estimate_email
from communications.links import create_public_link, resolve_public_link
from communications.models import EmailDelivery, PublicDocumentLink
from communications.pdf import get_or_create_estimate_pdf
from communications.snapshots import document_display_context, snapshot_logo_url
from workspaces.mixins import OwnerTenantRequiredMixin

from .forms import (
    EstimateEmailForm,
    EstimateForm,
    EstimateLineForm,
    ManualAcceptanceForm,
    PublicAcceptanceForm,
    PublicDeclineForm,
)
from .models import Estimate, EstimateLineItem
from .public_services import (
    accept_public_estimate,
    decline_public_estimate,
    record_public_view,
)
from .selectors import estimate_for_business, estimates_for_business
from .services import (
    add_estimate_line,
    create_estimate,
    delete_estimate_line,
    issue_estimate,
    record_manual_acceptance,
    update_estimate,
    update_estimate_line,
)


class EstimateListView(OwnerTenantRequiredMixin, ListView):
    template_name = "estimates/estimate_list.html"
    context_object_name = "estimates"
    paginate_by = 25

    def get_queryset(self):
        return estimates_for_business(
            business=self.request.business,
            search=self.request.GET.get("q", "").strip(),
            status=self.request.GET.get("status", "").strip(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search": self.request.GET.get("q", "").strip(),
                "status_filter": self.request.GET.get("status", "").strip(),
                "status_choices": (*Estimate.Status.choices, ("expired", "Expired")),
            }
        )
        return context


class EstimateCreateView(OwnerTenantRequiredMixin, FormView):
    template_name = "estimates/estimate_form.html"
    form_class = EstimateForm

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "business": self.request.business}

    def form_valid(self, form):
        estimate = create_estimate(
            actor=self.request.user,
            business_id=self.request.business.pk,
            data=form.service_data(),
        )
        messages.success(self.request, "Draft estimate created. Add line items next.")
        return redirect("estimates:detail", estimate_id=estimate.pk)


class EstimateObjectMixin:
    estimate = None

    def dispatch(self, request, *args, **kwargs):
        self.estimate = estimate_for_business(
            business=request.business,
            estimate_id=kwargs["estimate_id"],
        )
        if self.estimate is None:
            raise Http404("Estimate not found.")
        return super().dispatch(request, *args, **kwargs)


class EstimateDetailView(
    OwnerTenantRequiredMixin,
    EstimateObjectMixin,
    TemplateView,
):
    template_name = "estimates/estimate_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        display_context = document_display_context(self.estimate)
        delivery_queryset = EmailDelivery.objects.filter(
            business=self.request.business,
            estimate=self.estimate,
        )
        context.update(
            {
                **display_context,
                "estimate": self.estimate,
                "lines": self.estimate.line_items.all(),
                "email_form": EstimateEmailForm(
                    initial={"recipient": display_context["document_contact"]["email"]}
                ),
                "acceptance_form": ManualAcceptanceForm(),
                "recent_deliveries": delivery_queryset[:5],
                "has_failed_delivery": delivery_queryset.filter(
                    status=EmailDelivery.Status.FAILED
                ).exists(),
            }
        )
        return context


class EstimateUpdateView(
    OwnerTenantRequiredMixin,
    EstimateObjectMixin,
    FormView,
):
    template_name = "estimates/estimate_form.html"
    form_class = EstimateForm

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "business": self.request.business,
            "instance": self.estimate,
        }

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "estimate": self.estimate}

    def form_valid(self, form):
        try:
            estimate = update_estimate(
                actor=self.request.user,
                business_id=self.request.business.pk,
                estimate_id=self.estimate.pk,
                data=form.service_data(),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Estimate details updated.")
        return redirect("estimates:detail", estimate_id=estimate.pk)


class EstimateLineObjectMixin(EstimateObjectMixin):
    line = None

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        return response

    def get_line(self):
        if self.line is None:
            self.line = EstimateLineItem.objects.filter(
                pk=self.kwargs["line_id"],
                estimate=self.estimate,
                business=self.request.business,
            ).first()
        if self.line is None:
            raise Http404("Estimate line not found.")
        return self.line


class EstimateLineCreateView(
    OwnerTenantRequiredMixin,
    EstimateObjectMixin,
    FormView,
):
    template_name = "estimates/line_form.html"
    form_class = EstimateLineForm

    def get_catalog_item(self):
        item_id = self.request.GET.get("catalog")
        if not item_id:
            return None
        return (
            ProductService.objects.for_business(self.request.business)
            .active()
            .filter(pk=item_id)
            .first()
        )

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "business": self.request.business,
            "catalog_item": self.get_catalog_item(),
        }

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "estimate": self.estimate}

    def form_valid(self, form):
        try:
            add_estimate_line(
                actor=self.request.user,
                business_id=self.request.business.pk,
                estimate_id=self.estimate.pk,
                data=form.service_data(),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Line item added.")
        return redirect("estimates:detail", estimate_id=self.estimate.pk)


class EstimateLineUpdateView(
    OwnerTenantRequiredMixin,
    EstimateLineObjectMixin,
    FormView,
):
    template_name = "estimates/line_form.html"
    form_class = EstimateLineForm

    def dispatch(self, request, *args, **kwargs):
        self.line = None
        response = super().dispatch(request, *args, **kwargs)
        return response

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "business": self.request.business,
            "instance": self.get_line(),
        }

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "estimate": self.estimate,
            "line": self.get_line(),
        }

    def form_valid(self, form):
        try:
            update_estimate_line(
                actor=self.request.user,
                business_id=self.request.business.pk,
                estimate_id=self.estimate.pk,
                line_id=self.get_line().pk,
                data=form.service_data(),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Line item updated.")
        return redirect("estimates:detail", estimate_id=self.estimate.pk)


class EstimateLineDeleteView(
    OwnerTenantRequiredMixin,
    EstimateLineObjectMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        line = self.get_line()
        delete_estimate_line(
            actor=request.user,
            business_id=request.business.pk,
            estimate_id=self.estimate.pk,
            line_id=line.pk,
        )
        messages.success(request, "Line item removed.")
        return redirect("estimates:detail", estimate_id=self.estimate.pk)


class EstimateIssueView(OwnerTenantRequiredMixin, EstimateObjectMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            estimate = issue_estimate(
                actor=request.user,
                business_id=request.business.pk,
                estimate_id=self.estimate.pk,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            estimate = self.estimate
        else:
            messages.success(request, f"Estimate {estimate.number} issued.")
        return redirect("estimates:detail", estimate_id=estimate.pk)


class EstimateEmailView(OwnerTenantRequiredMixin, EstimateObjectMixin, View):
    def post(self, request, *args, **kwargs):
        form = EstimateEmailForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a valid recipient email address.")
        else:
            try:
                queue_estimate_email(
                    actor=request.user,
                    business_id=request.business.pk,
                    estimate_id=self.estimate.pk,
                    recipient=form.cleaned_data["recipient"],
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Estimate email queued.")
        return redirect("estimates:detail", estimate_id=self.estimate.pk)


class EstimatePDFView(OwnerTenantRequiredMixin, EstimateObjectMixin, View):
    def get(self, request, *args, **kwargs):
        if self.estimate.status == Estimate.Status.DRAFT:
            raise Http404("PDF is available after issue.")
        asset = get_or_create_estimate_pdf(estimate=self.estimate)
        return FileResponse(
            default_storage.open(asset.storage_name, "rb"),
            as_attachment=True,
            filename=f"Estimate-{self.estimate.number}.pdf",
            content_type="application/pdf",
        )


class EstimatePublicLinkView(OwnerTenantRequiredMixin, EstimateObjectMixin, View):
    def post(self, request, *args, **kwargs):
        if self.estimate.status == Estimate.Status.DRAFT:
            messages.error(request, "Issue the estimate before creating a public link.")
            return redirect("estimates:detail", estimate_id=self.estimate.pk)
        purpose = request.POST.get("purpose", PublicDocumentLink.Purpose.VIEW)
        if purpose not in PublicDocumentLink.Purpose.values:
            raise Http404("Link purpose not found.")
        _, token = create_public_link(estimate=self.estimate, purpose=purpose)
        route = (
            "estimates:public-respond"
            if purpose == PublicDocumentLink.Purpose.RESPOND
            else "estimates:public-view"
        )
        return redirect(route, token=token)


class EstimateManualAcceptanceView(
    OwnerTenantRequiredMixin,
    EstimateObjectMixin,
    View,
):
    def post(self, request, *args, **kwargs):
        form = ManualAcceptanceForm(request.POST)
        if form.is_valid():
            try:
                record_manual_acceptance(
                    actor=request.user,
                    business_id=request.business.pk,
                    estimate_id=self.estimate.pk,
                    method=form.cleaned_data["method"],
                    accepted_by_name=form.cleaned_data["accepted_by_name"],
                    metadata={"evidence_note": form.cleaned_data["evidence_note"]},
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Acceptance recorded.")
        else:
            messages.error(request, "Correct the acceptance details.")
        return redirect("estimates:detail", estimate_id=self.estimate.pk)


def _throttle(request):
    identity = request.META.get("REMOTE_ADDR", "unknown")
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    key = f"public-document-rate:{digest}"
    if cache.add(key, 1, timeout=900):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=900)
        return False
    return count > settings.PUBLIC_DOCUMENT_VIEW_LIMIT


def _public_headers(response):
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _throttled_response():
    return _public_headers(HttpResponse("Too many requests.", status=429))


def _public_estimate_for_request(*, request, link):
    if request.user.is_authenticated and request.business == link.business:
        return link.estimate
    return record_public_view(link=link)


@never_cache
def public_estimate_view(request, token):
    if _throttle(request):
        return _throttled_response()
    link = resolve_public_link(
        raw_token=token,
        allowed_purposes=(PublicDocumentLink.Purpose.VIEW,),
    )
    estimate = _public_estimate_for_request(request=request, link=link)
    snapshot = estimate.document_snapshot.payload
    response = render(
        request,
        "estimates/public_estimate.html",
        {
            "snapshot": snapshot,
            "estimate": estimate,
            "logo_url": snapshot_logo_url(snapshot),
        },
    )
    return _public_headers(response)


@never_cache
def public_estimate_respond(request, token):
    if _throttle(request):
        return _throttled_response()
    link = resolve_public_link(
        raw_token=token,
        allowed_purposes=(PublicDocumentLink.Purpose.RESPOND,),
    )
    estimate = _public_estimate_for_request(request=request, link=link)
    snapshot = estimate.document_snapshot.payload
    context = {
        "snapshot": snapshot,
        "estimate": estimate,
        "logo_url": snapshot_logo_url(snapshot),
        "accept_form": PublicAcceptanceForm(),
        "decline_form": PublicDeclineForm(),
        "response_enabled": estimate.status
        in (Estimate.Status.SENT, Estimate.Status.VIEWED)
        and estimate.effective_status != "expired",
    }
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "accept":
            form = PublicAcceptanceForm(request.POST)
            context["accept_form"] = form
            if form.is_valid():
                try:
                    accept_public_estimate(
                        link=link,
                        accepted_by_name=form.cleaned_data["accepted_by_name"],
                        accepted_by_email=form.cleaned_data["accepted_by_email"],
                        ip_address=request.META.get("REMOTE_ADDR"),
                        user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    )
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    return _public_headers(
                        render(
                            request,
                            "estimates/public_response_complete.html",
                            {"outcome": "accepted", "estimate": estimate},
                        )
                    )
        elif action == "decline":
            form = PublicDeclineForm(request.POST)
            context["decline_form"] = form
            if form.is_valid():
                try:
                    decline_public_estimate(
                        link=link,
                        reason=form.cleaned_data["reason"],
                    )
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    return _public_headers(
                        render(
                            request,
                            "estimates/public_response_complete.html",
                            {"outcome": "declined", "estimate": estimate},
                        )
                    )
        else:
            raise Http404("Response action not found.")
    return _public_headers(render(request, "estimates/public_estimate.html", context))


@never_cache
def public_estimate_pdf(request, token):
    if _throttle(request):
        return _throttled_response()
    link = resolve_public_link(
        raw_token=token,
        allowed_purposes=PublicDocumentLink.Purpose.values,
    )
    estimate = _public_estimate_for_request(request=request, link=link)
    asset = get_or_create_estimate_pdf(estimate=estimate)
    response = FileResponse(
        default_storage.open(asset.storage_name, "rb"),
        filename=f"Estimate-{estimate.number}.pdf",
        content_type="application/pdf",
    )
    return _public_headers(response)

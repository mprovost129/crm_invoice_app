import hashlib
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, ListView, TemplateView

from catalog.models import ProductService
from communications.emailing import queue_invoice_email
from communications.links import create_public_link, resolve_public_link
from communications.models import PublicDocumentLink
from communications.pdf import (
    get_or_create_invoice_pdf,
    get_or_create_payment_receipt_pdf,
)
from estimates.selectors import estimate_for_business
from payments.forms import PaymentForm, PaymentReversalForm
from payments.models import Payment
from payments.services import post_manual_payment, reverse_payment
from workspaces.mixins import OwnerTenantRequiredMixin

from .forms import InvoiceEmailForm, InvoiceForm, InvoiceLineForm, VoidInvoiceForm
from .models import Invoice, InvoiceLineItem
from .public_services import record_public_view
from .selectors import invoice_for_business, invoices_for_business
from .services import (
    add_invoice_line,
    convert_estimate_to_invoice,
    create_invoice,
    delete_invoice_line,
    issue_invoice,
    update_invoice,
    update_invoice_line,
    void_invoice,
)


class InvoiceListView(OwnerTenantRequiredMixin, ListView):
    template_name = "invoices/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 25

    def get_queryset(self):
        return invoices_for_business(
            business=self.request.business,
            search=self.request.GET.get("q", "").strip(),
            status=self.request.GET.get("status", "").strip(),
        )

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "search": self.request.GET.get("q", "").strip(),
            "status_filter": self.request.GET.get("status", "").strip(),
            "status_choices": (
                *Invoice.Status.choices,
                ("partial", "Partial"),
                ("paid", "Paid"),
                ("overdue", "Overdue"),
            ),
        }


class InvoiceCreateView(OwnerTenantRequiredMixin, FormView):
    template_name = "invoices/invoice_form.html"
    form_class = InvoiceForm

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "business": self.request.business}

    def form_valid(self, form):
        invoice = create_invoice(
            actor=self.request.user,
            business_id=self.request.business.pk,
            data=form.service_data(),
        )
        messages.success(self.request, "Draft invoice created. Add line items next.")
        return redirect("invoices:detail", invoice_id=invoice.pk)


class InvoiceObjectMixin:
    invoice = None

    def dispatch(self, request, *args, **kwargs):
        self.invoice = invoice_for_business(
            business=request.business,
            invoice_id=kwargs["invoice_id"],
        )
        if self.invoice is None:
            raise Http404("Invoice not found.")
        return super().dispatch(request, *args, **kwargs)


class InvoiceDetailView(OwnerTenantRequiredMixin, InvoiceObjectMixin, TemplateView):
    template_name = "invoices/invoice_detail.html"

    def get_context_data(self, **kwargs):
        today = timezone.localdate(timezone=ZoneInfo(self.request.business.timezone))
        suggested = self.invoice.balance_due
        if self.invoice.amount_paid == 0 and self.invoice.deposit_required > 0:
            suggested = min(self.invoice.deposit_required, self.invoice.balance_due)
        return {
            **super().get_context_data(**kwargs),
            "invoice": self.invoice,
            "lines": self.invoice.line_items.all(),
            "payments": self.invoice.payments.all(),
            "email_form": InvoiceEmailForm(
                initial={"recipient": self.invoice.contact.email}
            ),
            "void_form": VoidInvoiceForm(),
            "payment_form": PaymentForm(
                initial={
                    "amount": suggested,
                    "paid_on": today,
                    "receipt_email": self.invoice.contact.email,
                }
            ),
            "reversal_form": PaymentReversalForm(),
        }


class InvoiceUpdateView(OwnerTenantRequiredMixin, InvoiceObjectMixin, FormView):
    template_name = "invoices/invoice_form.html"
    form_class = InvoiceForm

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "business": self.request.business,
            "instance": self.invoice,
        }

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "invoice": self.invoice}

    def form_valid(self, form):
        try:
            invoice = update_invoice(
                actor=self.request.user,
                business_id=self.request.business.pk,
                invoice_id=self.invoice.pk,
                data=form.service_data(),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        return redirect("invoices:detail", invoice_id=invoice.pk)


class InvoiceLineObjectMixin(InvoiceObjectMixin):
    line = None

    def get_line(self):
        if self.line is None:
            self.line = InvoiceLineItem.objects.filter(
                pk=self.kwargs["line_id"],
                invoice=self.invoice,
                business=self.request.business,
            ).first()
        if self.line is None:
            raise Http404("Invoice line not found.")
        return self.line


class InvoiceLineCreateView(OwnerTenantRequiredMixin, InvoiceObjectMixin, FormView):
    template_name = "invoices/line_form.html"
    form_class = InvoiceLineForm

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
        return {**super().get_context_data(**kwargs), "invoice": self.invoice}

    def form_valid(self, form):
        try:
            add_invoice_line(
                actor=self.request.user,
                business_id=self.request.business.pk,
                invoice_id=self.invoice.pk,
                data=form.service_data(),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        return redirect("invoices:detail", invoice_id=self.invoice.pk)


class InvoiceLineUpdateView(OwnerTenantRequiredMixin, InvoiceLineObjectMixin, FormView):
    template_name = "invoices/line_form.html"
    form_class = InvoiceLineForm

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "business": self.request.business,
            "instance": self.get_line(),
        }

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "invoice": self.invoice,
            "line": self.get_line(),
        }

    def form_valid(self, form):
        try:
            update_invoice_line(
                actor=self.request.user,
                business_id=self.request.business.pk,
                invoice_id=self.invoice.pk,
                line_id=self.get_line().pk,
                data=form.service_data(),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        return redirect("invoices:detail", invoice_id=self.invoice.pk)


class InvoiceLineDeleteView(OwnerTenantRequiredMixin, InvoiceLineObjectMixin, View):
    def post(self, request, *args, **kwargs):
        delete_invoice_line(
            actor=request.user,
            business_id=request.business.pk,
            invoice_id=self.invoice.pk,
            line_id=self.get_line().pk,
        )
        return redirect("invoices:detail", invoice_id=self.invoice.pk)


class InvoiceIssueView(OwnerTenantRequiredMixin, InvoiceObjectMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            invoice = issue_invoice(
                actor=request.user,
                business_id=request.business.pk,
                invoice_id=self.invoice.pk,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            invoice = self.invoice
        else:
            messages.success(request, f"Invoice {invoice.number} issued.")
        return redirect("invoices:detail", invoice_id=invoice.pk)


class EstimateConvertView(OwnerTenantRequiredMixin, View):
    def post(self, request, estimate_id):
        estimate = estimate_for_business(
            business=request.business, estimate_id=estimate_id
        )
        if estimate is None:
            raise Http404("Estimate not found.")
        try:
            invoice = convert_estimate_to_invoice(
                actor=request.user,
                business_id=request.business.pk,
                estimate_id=estimate.pk,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("estimates:detail", estimate_id=estimate.pk)
        messages.success(request, f"Created invoice {invoice.number}.")
        return redirect("invoices:detail", invoice_id=invoice.pk)


class InvoiceEmailView(OwnerTenantRequiredMixin, InvoiceObjectMixin, View):
    def post(self, request, *args, **kwargs):
        form = InvoiceEmailForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a valid recipient email address.")
        else:
            try:
                queue_invoice_email(
                    actor=request.user,
                    business_id=request.business.pk,
                    invoice_id=self.invoice.pk,
                    recipient=form.cleaned_data["recipient"],
                    reminder=request.POST.get("action") == "reminder",
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Invoice email queued.")
        return redirect("invoices:detail", invoice_id=self.invoice.pk)


class InvoicePDFView(OwnerTenantRequiredMixin, InvoiceObjectMixin, View):
    def get(self, request, *args, **kwargs):
        if self.invoice.status == Invoice.Status.DRAFT:
            raise Http404("PDF is available after issue.")
        asset = get_or_create_invoice_pdf(invoice=self.invoice)
        return FileResponse(
            default_storage.open(asset.storage_name, "rb"),
            as_attachment=True,
            filename=f"Invoice-{self.invoice.number}.pdf",
            content_type="application/pdf",
        )


class InvoicePublicLinkView(OwnerTenantRequiredMixin, InvoiceObjectMixin, View):
    def post(self, request, *args, **kwargs):
        if self.invoice.status in (Invoice.Status.DRAFT, Invoice.Status.VOID):
            messages.error(request, "This invoice cannot have a public link.")
            return redirect("invoices:detail", invoice_id=self.invoice.pk)
        _, token = create_public_link(
            invoice=self.invoice, purpose=PublicDocumentLink.Purpose.VIEW
        )
        return redirect("invoices:public-view", token=token)


class InvoiceVoidView(OwnerTenantRequiredMixin, InvoiceObjectMixin, View):
    def post(self, request, *args, **kwargs):
        form = VoidInvoiceForm(request.POST)
        if form.is_valid():
            try:
                void_invoice(
                    actor=request.user,
                    business_id=request.business.pk,
                    invoice_id=self.invoice.pk,
                    reason=form.cleaned_data["reason"],
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Invoice voided.")
        return redirect("invoices:detail", invoice_id=self.invoice.pk)


class PaymentCreateView(OwnerTenantRequiredMixin, InvoiceObjectMixin, View):
    def post(self, request, *args, **kwargs):
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                post_manual_payment(
                    actor=request.user,
                    business_id=request.business.pk,
                    invoice_id=self.invoice.pk,
                    **form.cleaned_data,
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Payment recorded.")
        else:
            messages.error(request, "Correct the payment details.")
        return redirect("invoices:detail", invoice_id=self.invoice.pk)


class PaymentObjectMixin(InvoiceObjectMixin):
    payment = None

    def get_payment(self):
        if self.payment is None:
            self.payment = Payment.objects.filter(
                pk=self.kwargs["payment_id"],
                invoice=self.invoice,
                business=self.request.business,
            ).first()
        if self.payment is None:
            raise Http404("Payment not found.")
        return self.payment


class PaymentReverseView(OwnerTenantRequiredMixin, PaymentObjectMixin, View):
    def post(self, request, *args, **kwargs):
        form = PaymentReversalForm(request.POST)
        if form.is_valid():
            try:
                reverse_payment(
                    actor=request.user,
                    business_id=request.business.pk,
                    payment_id=self.get_payment().pk,
                    amount=form.cleaned_data["amount"],
                    reason=form.cleaned_data["reason"],
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Payment reversal recorded.")
        return redirect("invoices:detail", invoice_id=self.invoice.pk)


class PaymentReceiptView(OwnerTenantRequiredMixin, PaymentObjectMixin, View):
    def get(self, request, *args, **kwargs):
        payment = self.get_payment()
        asset = get_or_create_payment_receipt_pdf(payment=payment)
        return FileResponse(
            default_storage.open(asset.storage_name, "rb"),
            as_attachment=True,
            filename=f"Receipt-{self.invoice.number}-{payment.pk}.pdf",
            content_type="application/pdf",
        )


def _throttle(request):
    identity = request.META.get("REMOTE_ADDR", "unknown")
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    key = f"public-invoice-rate:{digest}"
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


def _public_invoice_for_request(*, request, link):
    if request.user.is_authenticated and request.business == link.business:
        return link.invoice
    return record_public_view(link=link)


@never_cache
def public_invoice_view(request, token):
    if _throttle(request):
        return _public_headers(HttpResponse("Too many requests.", status=429))
    link = resolve_public_link(
        raw_token=token,
        allowed_purposes=(PublicDocumentLink.Purpose.VIEW,),
        target="invoice",
    )
    invoice = _public_invoice_for_request(request=request, link=link)
    return _public_headers(
        render(
            request,
            "invoices/public_invoice.html",
            {
                "snapshot": invoice.document_snapshot.payload,
                "invoice": invoice,
                "token": token,
            },
        )
    )


@never_cache
def public_invoice_pdf(request, token):
    if _throttle(request):
        return _public_headers(HttpResponse("Too many requests.", status=429))
    link = resolve_public_link(
        raw_token=token,
        allowed_purposes=(PublicDocumentLink.Purpose.VIEW,),
        target="invoice",
    )
    invoice = _public_invoice_for_request(request=request, link=link)
    asset = get_or_create_invoice_pdf(invoice=invoice)
    response = FileResponse(
        default_storage.open(asset.storage_name, "rb"),
        filename=f"Invoice-{invoice.number}.pdf",
        content_type="application/pdf",
    )
    return _public_headers(response)
